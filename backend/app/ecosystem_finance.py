"""Read-only financial relationship views; existing bookings and ledgers stay authoritative.

A booking/request association never authorizes organizational funding.
No credentials, traveller documents, mutable financial commands, or assumed balances.
"""
import json
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session
from . import operations as m
from . import enterprise_models as e
from .financial_amounts import FinancialInvariantError, payment_totals, supplier_liability, settlement_remaining


def ecosystem_finance_router(get_db, current_user, role_has_permission, price_hasher=None):
    api = APIRouter(prefix="/ecosystem", tags=["ecosystem-finance"])

    def rows(db, user, organization_id, limit, offset, owner_id=None, supplier_id=None):
        tenant = user.tenant_id
        statement = (
            select(m.Reservation, m.LicensedEntity, m.PriceBreakdown,
                   m.ProviderContract, e.EnterpriseRequest)
            .outerjoin(m.LicensedEntity, and_(
                m.LicensedEntity.id == m.Reservation.licensed_entity_id,
                m.LicensedEntity.tenant_id == tenant))
            .outerjoin(m.PriceBreakdown, and_(
                m.PriceBreakdown.booking_id == m.Reservation.id,
                m.PriceBreakdown.tenant_id == tenant))
            .outerjoin(m.ProviderContract, and_(
                m.ProviderContract.id == m.PriceBreakdown.source_contract_id,
                m.ProviderContract.tenant_id == tenant))
            .outerjoin(e.EnterpriseBookingLink, and_(
                e.EnterpriseBookingLink.reservation_id == m.Reservation.id,
                e.EnterpriseBookingLink.tenant_id == tenant))
            .outerjoin(e.EnterpriseRequest, and_(
                e.EnterpriseRequest.id == e.EnterpriseBookingLink.request_id,
                e.EnterpriseRequest.tenant_id == tenant))
            .where(m.Reservation.tenant_id == tenant)
        )
        if organization_id is not None:
            statement = statement.where(e.EnterpriseRequest.organization_id == organization_id)
        if owner_id is not None:
            statement = statement.where(m.Reservation.user_id == owner_id)
        if supplier_id is not None:
            suppliers_bookings = select(m.SettlementRecord.reservation_id).where(m.SettlementRecord.tenant_id == tenant, m.SettlementRecord.supplier_id == supplier_id)
            statement = statement.where((m.ProviderContract.supplier_id == supplier_id) | m.Reservation.id.in_(suppliers_bookings))
        total = db.scalar(select(func.count()).select_from(statement.subquery())) or 0
        batch = db.execute(statement.order_by(
            m.Reservation.created_at.desc(), m.Reservation.id.desc()
        ).offset(offset).limit(limit + 1)).all()
        items = []
        for booking, entity, price, contract, request in batch[:limit]:
            gaps = []
            if entity is None:
                gaps.append("legal_entity_missing")
            elif entity.status != "active":
                gaps.append("legal_entity_inactive")
            if price is None:
                gaps.append("price_breakdown_missing")
            elif price.source_contract_id and contract is None:
                gaps.append("provider_contract_unresolved")
            if request is not None:
                gaps.append("organization_funding_not_established_by_link")
            items.append({
                "reservation_id": booking.id,
                "booking_reference": booking.booking_reference,
                "service_type": booking.service_type,
                "status": booking.status,
                "licensed_entity_id": entity.id if entity else None,
                "legal_name": entity.legal_name if entity else None,
                "sales_channel_id": booking.sales_channel_id,
                "request_id": request.id if request else None,
                "organization_id": request.organization_id if request else None,
                "travel_context": request.use_case if request else None,
                "provider_contract_id": contract.id if contract else None,
                "provider_mode": contract.mode if contract else None,
                "has_price_breakdown": price is not None,
                "organization_funding_authorized_by_link": False,
                "relationship_gaps": gaps,
            })
        return {
            "items": items,
            "total": total,
            "limit": limit,
            "offset": offset,
            "next_offset": offset + limit if len(batch) > limit else None,
            "read_only": True,
            "schema_version": "1",
            "live_provider_connection_verified": False,
        }

    @api.get("/financial-links")
    def financial_links(
        user=Depends(current_user), db: Session = Depends(get_db),
        limit: int = Query(default=50, ge=1, le=100),
        offset: int = Query(default=0, ge=0, le=100000),
    ):
        if not (role_has_permission(user.role, "ledger:read") or role_has_permission(user.role, "tenant:manage")):
            raise HTTPException(403, "مجوز مشاهده روابط مالی این مجموعه را ندارید")
        return rows(db, user, None, limit, offset)

    @api.get("/organizations/{organization_id}/financial-links")
    def organization_links(
        organization_id: str, user=Depends(current_user),
        db: Session = Depends(get_db),
        limit: int = Query(default=50, ge=1, le=100),
        offset: int = Query(default=0, ge=0, le=100000),
    ):
        member = db.scalar(select(m.EmployeeAssignment).where(
            m.EmployeeAssignment.tenant_id == user.tenant_id,
            m.EmployeeAssignment.organization_id == organization_id,
            m.EmployeeAssignment.user_id == user.id,
        ))
        org = db.scalar(select(m.Organization).where(
            m.Organization.tenant_id == user.tenant_id,
            m.Organization.id == organization_id,
            m.Organization.status == "active",
        ))
        tenant_manager = role_has_permission(user.role, "tenant:manage")
        if org is None or (member is None and not tenant_manager):
            raise HTTPException(403, "عضویت در این سازمان فعال تأیید نشده است")
        if user.role != "organization_admin" and not tenant_manager:
            grant = db.scalar(select(e.EnterpriseGrant).where(
                e.EnterpriseGrant.tenant_id == user.tenant_id,
                e.EnterpriseGrant.organization_id == organization_id,
                e.EnterpriseGrant.user_id == user.id,
            ))
            if grant is None or "requests.read_all" not in json.loads(grant.permissions_json):
                raise HTTPException(403, "مجوز مشاهده سفرهای سازمان را ندارید")
        return rows(db, user, organization_id, limit, offset)

    def permitted_booking(db, user, reservation_id):
        booking = db.scalar(select(m.Reservation).where(m.Reservation.id == reservation_id, m.Reservation.tenant_id == user.tenant_id))
        if booking is None: raise HTTPException(404, "رزرو در محدوده دسترسی وجود ندارد")
        if role_has_permission(user.role, "ledger:read") or booking.user_id == user.id:
            return booking
        link = db.scalar(select(e.EnterpriseBookingLink).where(e.EnterpriseBookingLink.reservation_id == booking.id, e.EnterpriseBookingLink.tenant_id == user.tenant_id))
        if link is not None:
            if role_has_permission(user.role, "tenant:manage"): return booking
            request = db.scalar(select(e.EnterpriseRequest).where(e.EnterpriseRequest.id == link.request_id, e.EnterpriseRequest.tenant_id == user.tenant_id))
            member = db.scalar(select(m.EmployeeAssignment.id).where(m.EmployeeAssignment.tenant_id == user.tenant_id, m.EmployeeAssignment.organization_id == request.organization_id, m.EmployeeAssignment.user_id == user.id)) if request is not None else None
            if member is not None and request is not None:
                grant = db.scalar(select(e.EnterpriseGrant).where(e.EnterpriseGrant.organization_id == request.organization_id, e.EnterpriseGrant.tenant_id == user.tenant_id, e.EnterpriseGrant.user_id == user.id))
                if user.role == "organization_admin" or (grant is not None and "requests.read_all" in json.loads(grant.permissions_json)): return booking
        raise HTTPException(403, "مجوز مشاهده اطلاعات مالی این رزرو را ندارید")

    @api.get("/me/financial-links")
    def my_links(user=Depends(current_user), db: Session = Depends(get_db), limit: int = Query(default=50, ge=1, le=100), offset: int = Query(default=0, ge=0, le=100000)):
        return rows(db, user, None, limit, offset, owner_id=user.id)

    @api.get("/reservations/{reservation_id}/finance")
    def booking_finance(reservation_id: str, user=Depends(current_user), db: Session = Depends(get_db)):
        booking = permitted_booking(db, user, reservation_id)
        try: return financial_projection(db, user.tenant_id, booking, include_internal=role_has_permission(user.role, "ledger:read"), price_hasher=price_hasher)
        except FinancialInvariantError as exc: raise HTTPException(409, str(exc))

    @api.get("/suppliers/{supplier_id}/financial-links")
    def supplier_links(supplier_id: str, user=Depends(current_user), db: Session = Depends(get_db), limit: int = Query(default=50, ge=1, le=100), offset: int = Query(default=0, ge=0, le=100000)):
        supplier = db.scalar(select(m.Supplier).where(m.Supplier.id == supplier_id, m.Supplier.tenant_id == user.tenant_id))
        member = db.scalar(select(m.SupplierMembership.id).where(m.SupplierMembership.supplier_id == supplier_id, m.SupplierMembership.tenant_id == user.tenant_id, m.SupplierMembership.user_id == user.id))
        if supplier is None or (member is None and not role_has_permission(user.role, "ledger:read")):
            raise HTTPException(403, "دسترسی به اطلاعات این تأمین‌کننده مجاز نیست")
        data = rows(db, user, None, limit, offset, supplier_id=supplier_id)
        own_contract_ids = set(db.scalars(select(m.ProviderContract.id).where(m.ProviderContract.tenant_id == user.tenant_id, m.ProviderContract.supplier_id == supplier_id)))
        ids = [item["reservation_id"] for item in data["items"]]
        settlement_rows = db.scalars(select(m.SettlementRecord).where(m.SettlementRecord.tenant_id == user.tenant_id, m.SettlementRecord.supplier_id == supplier_id, m.SettlementRecord.reservation_id.in_(ids))).all() if ids else []
        for item in data["items"]:
            item.pop("request_id", None); item.pop("organization_id", None); item.pop("travel_context", None)
            item.pop("sales_channel_id", None)
            if item["provider_contract_id"] not in own_contract_ids:
                item["provider_contract_id"] = None; item["provider_mode"] = None
            item["relationship_gaps"] = [gap for gap in item["relationship_gaps"] if not gap.startswith("organization_")]
            item["settlements"] = [{"id": row.id, "amount": row.amount, "currency": row.currency, "status": row.status} for row in settlement_rows if row.reservation_id == item["reservation_id"]]
        return data

    return api


def financial_projection(db, tenant, booking, *, include_internal=False, price_hasher=None):
    """One reservation identity, separate monetary sources; no guessed payer or combined cash."""
    payments = db.scalars(select(m.PaymentIntent).where(m.PaymentIntent.tenant_id == tenant, m.PaymentIntent.reservation_id == booking.id)).all()
    invoices = db.scalars(select(m.Invoice).where(m.Invoice.tenant_id == tenant, m.Invoice.reservation_id == booking.id)).all()
    agreements = db.scalars(select(m.InstallmentAgreement).where(m.InstallmentAgreement.tenant_id == tenant, m.InstallmentAgreement.reservation_id == booking.id)).all()
    ledger = db.scalars(select(m.FinancialLedgerEntry).where(m.FinancialLedgerEntry.tenant_id == tenant, m.FinancialLedgerEntry.reservation_id == booking.id).order_by(m.FinancialLedgerEntry.created_at, m.FinancialLedgerEntry.id)).all()
    price = db.scalar(select(m.PriceBreakdown).where(m.PriceBreakdown.tenant_id == tenant, m.PriceBreakdown.booking_id == booking.id))
    sources = []
    for entry in ledger:
        account = db.scalar(select(m.CreditAccount).where(m.CreditAccount.id == entry.credit_account_id, m.CreditAccount.tenant_id == tenant)) if entry.credit_account_id else db.scalar(select(m.Wallet).where(m.Wallet.id == entry.wallet_id, m.Wallet.tenant_id == tenant))
        sources.append({"id": entry.id, "entry_type": entry.entry_type, "amount": entry.amount, "currency": account.currency if account else None, "source_type": "organization_credit" if entry.credit_account_id and account and account.organization_id else "credit" if entry.credit_account_id else "wallet", "source_id": entry.credit_account_id or entry.wallet_id, "reversal_of_id": entry.reversal_of_id, "account_resolved": account is not None})
    result = {
        "reservation_id": booking.id, "licensed_entity_id": booking.licensed_entity_id,
        "read_only": True, "funding_sources_are_not_combined": True,
        "invoices": [{"id": x.id, "number": x.invoice_number, "subtotal": x.subtotal_amount, "tax": x.tax_amount, "total": x.total_amount, "currency": x.currency, "status": x.status} for x in invoices],
        "payment_totals": payment_totals(payments),
        "funding_ledger": sources,
        "installments": [{"id": x.id, "status": x.status, "principal": x.principal_amount, "fee": x.total_payable - x.principal_amount, "total": x.total_payable, "currency": x.currency, "schedule": json.loads(x.schedule_json)} for x in agreements],
        "price_components": ({"service_fee": price.service_fee, "discount": price.discount_amount, "selling_total": price.total_selling_price, "tax": price.vat + price.airport_tax + price.i6_tax + price.red_crescent + price.other_taxes} if price is not None else None),
        "customer_outstanding": None,
        "outstanding_reason": "منابع مستقل بانک، کیف پول و اعتبار بدون تخصیص مرجع واحد، جمع نمی‌شوند",
    }
    from .financial_integrity import DebtBinding, debt_view
    bindings=db.scalars(select(DebtBinding).where(DebtBinding.tenant_id==tenant,DebtBinding.reservation_id==booking.id)).all()
    visible=[x for x in bindings if include_internal or x.instrument_type!="supplier_liability"]
    result["debt_owner_model"]={
        "status":"EVIDENCE_BOUND" if visible else "BLOCKED_BY_CONTRACT_SOURCE",
        "items":[debt_view(db,tenant,x) for x in visible],
        "instrument_candidates":[
            {"type":"invoice","id":x.id,"currency":x.currency,"principal":x.total_amount,"debtor":None,"creditor":None}
            for x in invoices
        ]+[
            {"type":"installment","id":x.id,"currency":x.currency,"principal":x.principal_amount,"debtor":None,"creditor":None}
            for x in agreements
        ],
        "membership_implies_debt_owner":False,
        "provider_config_implies_financial_contract":False,
    }
    if price_hasher is not None:
        from .funding_references import latest_plan
        try:
            checkout, plan = latest_plan(db, booking, price_hasher)
            result["funding_allocation"] = ({"status": "DECLARED" if plan.get("schema_version") == 2 else "LEGACY_UNVERIFIED", "plan": plan, "checkout_id": checkout.id, "payment_intent_id": checkout.payment_intent_id, "debt_owner_verified": False, "payment_success_claimed": False} if checkout else None)
        except (FinancialInvariantError, KeyError, ValueError):
            result["funding_allocation"] = {"status": "RECONCILIATION_REQUIRED", "debt_owner_verified": False, "payment_success_claimed": False}
    if include_internal:
        settlement_rows = db.scalars(select(m.SettlementRecord).where(m.SettlementRecord.tenant_id == tenant, m.SettlementRecord.reservation_id == booking.id)).all()
        result["settlements"] = [{"id": x.id, "supplier_id": x.supplier_id, "amount": x.amount, "currency": x.currency, "status": x.status} for x in settlement_rows]
        check = db.scalar(select(m.PriceCheck).where(m.PriceCheck.id == booking.price_check_id, m.PriceCheck.tenant_id == tenant)) if booking.price_check_id else None
        offer = db.scalar(select(m.Offer).where(m.Offer.id == check.offer_id, m.Offer.tenant_id == tenant)) if check else None
        try:
            if offer is None: raise FinancialInvariantError("مرجع معتبر تأمین رزرو وجود ندارد")
            result["supplier_settlement_calculation"] = settlement_remaining(price, payments, settlement_rows, offer.supplier_id)
        except FinancialInvariantError as exc:
            result["supplier_settlement_calculation"] = None
            result["supplier_settlement_reason"] = str(exc)
        result["commercial_components"] = ({key: getattr(price, key) for key in ("supplier_net_rate", "supplier_currency", "supplier_net_rate_irr", "platform_markup", "supplier_commission", "agent_commission", "wl_revenue_share", "gross_margin", "net_margin")} if price is not None else None)
    return result
