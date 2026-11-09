"""Regression tests for the 2026-11-10 urgent audit fixes (KT-01, agency scope, KT-02, KT-03).

Every fix is closed with a negative test: unrelated supplier/agency, other supplier,
replayed command_id with a different payload, customer view of internal price fields.
"""
import uuid

from sqlalchemy import func, select

from app.main import AuditEvent, SessionLocal, User
from app.operations import Agency, AgencyMembership, FinancialLedgerEntry, IdempotencyKey, PaymentIntent, Reservation, Supplier, SupplierMembership, Voucher, Wallet

from test_booking_orchestration import active_supplier, auth, login, policy


def _tenant_id():
    with SessionLocal() as db:
        return db.scalar(select(User.tenant_id).where(User.email == "supplier@aftab.test"))


def _new_user(role, label):
    email = f"{label}-{uuid.uuid4().hex[:8]}@aftab.test"
    with SessionLocal() as db:
        db.add(User(tenant_id=_tenant_id(), email=email, name=f"کاربر آزمون {label}", role=role)); db.commit()
    return email


def _new_supplier(member_email=None):
    with SessionLocal() as db:
        supplier = Supplier(tenant_id=_tenant_id(), supplier_type="travel", display_name="تأمین‌کننده دیگر آزمون", status="active")
        db.add(supplier); db.flush()
        if member_email:
            uid = db.scalar(select(User.id).where(User.email == member_email))
            db.add(SupplierMembership(tenant_id=supplier.tenant_id, user_id=uid, supplier_id=supplier.id, role="owner"))
        db.commit()
        return supplier.id


def _paid_reservation(client, supplier_id=None):
    """A captured-payment, manual_supplier reservation owned by employee@aftab.test."""
    supplier_id = supplier_id or active_supplier()
    supplier = login(client, "supplier@aftab.test")["access_token"]
    employee = login(client, "employee@aftab.test")["access_token"]
    tag = uuid.uuid4().hex[:10]
    attrs = {"origin": "THR", "destination": "MHD", "supplier_net_rate": 600_000, "service_fee": 50_000, "supplier_commission": 20_000, "agent_commission": 10_000, "vat": 30_000}
    offer = client.post("/supplier/offers", headers=auth(supplier), json={"supplier_id": supplier_id, "service_type": "flight", "title": f"audit-{tag}", "amount": 1_000_000, "available_units": 3, "valid_minutes": 60, "policy": policy(), "attributes": attrs, "fulfillment_mode": "manual_supplier", "provider_key": "manual_supplier"})
    assert offer.status_code == 201, offer.text
    checked = client.post(f"/offers/{offer.json()['id']}/price-check", headers=auth(employee), json={"units": 1, "command_id": f"pc-{tag}"})
    assert checked.status_code == 201, checked.text
    booked = client.post("/orchestration/bookings", headers=auth(employee), json={"price_check_id": checked.json()["id"], "command_id": f"bk-{tag}"})
    assert booked.status_code == 201, booked.text
    rid = booked.json()["id"]
    payment = client.post(f"/reservations/{rid}/payment-intents", headers={**auth(employee), "Idempotency-Key": f"pay-{tag}"})
    assert payment.status_code == 201, payment.text
    with SessionLocal() as db:
        intent = db.get(PaymentIntent, payment.json()["id"]); intent.status = "captured"; intent.captured_amount = intent.amount; db.commit()
    return rid, supplier_id


def _fulfill(client, token, rid):
    return client.post(f"/reservations/{rid}/fulfill", headers=auth(token), json={"command_id": f"ff-{uuid.uuid4().hex[:10]}", "provider_reference": "ref-audit", "document_reference": f"document://voucher/{rid}"})


def _issued_reservation(client):
    rid, supplier_id = _paid_reservation(client)
    assert _fulfill(client, login(client, "supplier@aftab.test")["access_token"], rid).status_code == 200
    return rid, supplier_id


def _reissue(client, token, rid, command_id=None, doc=None):
    return client.post(f"/reservations/{rid}/voucher/reissue", headers=auth(token), json={"command_id": command_id or f"ri-{uuid.uuid4().hex[:10]}", "document_reference": doc or f"document://voucher/{rid}/v-next", "reason": "اصلاح اطلاعات"})


def _voucher_state(rid):
    with SessionLocal() as db:
        v = db.scalar(select(Voucher).where(Voucher.reservation_id == rid))
        return v.revision, v.document_reference


def _idem_count(command_id):
    with SessionLocal() as db:
        return db.scalar(select(func.count()).select_from(IdempotencyKey).where(IdempotencyKey.scope == "voucher.reissue", IdempotencyKey.key == command_id))


# ---------------------------------------------------------------- KT-01 reissue scope
def test_reissue_denied_for_supplier_without_membership_and_nothing_changes(client):
    rid, _ = _issued_reservation(client)
    before = _voucher_state(rid)
    outsider = login(client, _new_user("supplier", "no-membership"))["access_token"]
    cmd = f"ri-outsider-{uuid.uuid4().hex[:8]}"
    denied = _reissue(client, outsider, rid, command_id=cmd)
    assert denied.status_code in (403, 404)
    assert "revision" not in denied.text and "document_reference" not in denied.text
    assert _voucher_state(rid) == before
    assert _idem_count(cmd) == 0


def test_reissue_denied_for_member_of_another_supplier(client):
    rid, _ = _issued_reservation(client)
    before = _voucher_state(rid)
    other = _new_user("supplier", "other-supplier")
    _new_supplier(member_email=other)
    denied = _reissue(client, login(client, other)["access_token"], rid)
    assert denied.status_code in (403, 404)
    assert _voucher_state(rid) == before


def test_owner_supplier_and_platform_admin_can_reissue(client):
    rid, _ = _issued_reservation(client)
    owner = _reissue(client, login(client, "supplier@aftab.test")["access_token"], rid, doc=f"document://voucher/{rid}/v2")
    assert owner.status_code == 200 and owner.json()["revision"] == 2
    admin = _reissue(client, login(client, "platform-admin@aftab.test")["access_token"], rid, doc=f"document://voucher/{rid}/v3")
    assert admin.status_code == 200 and admin.json()["revision"] == 3
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(AuditEvent).where(AuditEvent.action == "reservation.voucher_reissue.admin_override", AuditEvent.detail.contains(rid))) == 1


# ---------------------------------------------------------------- agency_partner scope (issue + reissue)
def test_unrelated_agency_partner_cannot_issue_or_reissue(client):
    agency = login(client, _new_user("agency_partner", "agency-unlinked"))["access_token"]
    paid, _ = _paid_reservation(client)
    denied = _fulfill(client, agency, paid)
    assert denied.status_code in (403, 404)
    with SessionLocal() as db:
        assert db.get(Reservation, paid).status != "issued"
        assert db.scalar(select(Voucher.id).where(Voucher.reservation_id == paid)) is None
    issued, _ = _issued_reservation(client)
    before = _voucher_state(issued)
    assert _reissue(client, agency, issued).status_code in (403, 404)
    assert _voucher_state(issued) == before


def test_agency_member_without_supplier_link_is_denied(client):
    email = _new_user("agency_partner", "agency-nolink")
    with SessionLocal() as db:
        uid = db.scalar(select(User.id).where(User.email == email))
        agency = Agency(tenant_id=_tenant_id(), display_name="آژانس بدون تأمین‌کننده", status="active"); db.add(agency); db.flush()
        db.add(AgencyMembership(tenant_id=agency.tenant_id, user_id=uid, agency_id=agency.id)); db.commit()
    paid, _ = _paid_reservation(client)
    assert _fulfill(client, login(client, email)["access_token"], paid).status_code in (403, 404)


def test_agency_linked_to_the_reservation_supplier_can_issue_and_reissue(client):
    email = _new_user("agency_partner", "agency-linked")
    paid, supplier_id = _paid_reservation(client)
    with SessionLocal() as db:
        uid = db.scalar(select(User.id).where(User.email == email))
        agency = Agency(tenant_id=_tenant_id(), display_name="آژانس برگزارکننده آزمون", status="active", supplier_id=supplier_id); db.add(agency); db.flush()
        db.add(AgencyMembership(tenant_id=agency.tenant_id, user_id=uid, agency_id=agency.id)); db.commit()
    token = login(client, email)["access_token"]
    issued = _fulfill(client, token, paid)
    assert issued.status_code == 200, issued.text
    assert _reissue(client, token, paid).json()["revision"] == 2


# ---------------------------------------------------------------- reissue idempotency (request_hash)
def test_reissue_command_id_replay_rules(client):
    supplier = login(client, "supplier@aftab.test")["access_token"]
    first, _ = _issued_reservation(client)
    second, _ = _issued_reservation(client)
    cmd = f"ri-replay-{uuid.uuid4().hex[:8]}"
    doc = f"document://voucher/{first}/v2"
    assert _reissue(client, supplier, first, command_id=cmd, doc=doc).json()["revision"] == 2
    replay = _reissue(client, supplier, first, command_id=cmd, doc=doc)
    assert replay.status_code == 200 and replay.json()["revision"] == 2
    assert _voucher_state(first) == (2, doc)
    # same command_id, different document for the same reservation -> conflict
    assert _reissue(client, supplier, first, command_id=cmd, doc=f"document://voucher/{first}/other").status_code == 409
    assert _voucher_state(first) == (2, doc)
    # same command_id against a different reservation -> conflict, second voucher untouched
    before_second = _voucher_state(second)
    assert _reissue(client, supplier, second, command_id=cmd, doc=doc).status_code == 409
    assert _voucher_state(second) == before_second


# ---------------------------------------------------------------- KT-02 price-breakdown DTO
CUSTOMER_KEYS = {"view", "currency", "id", "booking_id", "total_selling_price", "service_fee", "discount_amount", "discount_source", "promo_code", "vat", "airport_tax", "i6_tax", "red_crescent", "other_taxes", "calculated_at"}
INTERNAL_ONLY = {"source", "source_contract_id", "supplier_net_rate", "supplier_currency", "exchange_rate", "supplier_net_rate_irr", "platform_markup", "platform_markup_type", "supplier_commission", "agent_commission", "wl_channel_id", "wl_revenue_share", "wl_commission_type", "total_cost", "gross_margin", "net_margin", "calculated_by", "override_reason", "approved_by"}


def test_customer_price_breakdown_is_allowlisted_and_finance_sees_internals(client):
    rid, _ = _paid_reservation(client)
    customer = client.get(f"/reservations/{rid}/price-breakdown", headers=auth(login(client, "employee@aftab.test")["access_token"]))
    assert customer.status_code == 200, customer.text
    body = customer.json()
    assert set(body) == CUSTOMER_KEYS
    assert not (set(body) & INTERNAL_ONLY)
    assert body["view"] == "customer" and body["total_selling_price"] == 1_000_000 and body["currency"] == "IRR"
    assert body["service_fee"] == 50_000 and body["vat"] == 30_000
    assert "600000" not in customer.text.replace(",", "")
    finance = client.get(f"/reservations/{rid}/price-breakdown", headers=auth(login(client, "finance@aftab.test")["access_token"]))
    assert finance.status_code == 200, finance.text
    internal = finance.json()
    assert internal["view"] == "internal" and INTERNAL_ONLY <= set(internal)
    assert internal["supplier_net_rate"] == 600_000 and internal["supplier_commission"] == 20_000


def test_price_breakdown_other_customer_and_supplier_get_404(client):
    rid, _ = _paid_reservation(client)
    for email in (_new_user("customer", "stranger"), "supplier@aftab.test"):
        assert client.get(f"/reservations/{rid}/price-breakdown", headers=auth(login(client, email)["access_token"])).status_code == 404


# ---------------------------------------------------------------- KT-03 ledger command_id payload match
def test_wallet_command_id_replay_with_different_payload_conflicts(client):
    finance = login(client, "finance@aftab.test")["access_token"]
    tag = uuid.uuid4().hex[:8]
    with SessionLocal() as db:
        a = Wallet(tenant_id=_tenant_id(), owner_type="organization", owner_reference=f"kt03-a-{tag}")
        b = Wallet(tenant_id=_tenant_id(), owner_type="organization", owner_reference=f"kt03-b-{tag}")
        db.add_all([a, b]); db.commit(); wa, wb = a.id, b.id
    cmd = f"kt03-fund-{tag}"
    first = client.post(f"/wallets/{wa}/commands", headers=auth(finance), json={"command_id": cmd, "entry_type": "allocate", "amount": 100})
    assert first.status_code == 200 and first.json()["available"] == 100
    same = client.post(f"/wallets/{wa}/commands", headers=auth(finance), json={"command_id": cmd, "entry_type": "allocate", "amount": 100})
    assert same.status_code == 200 and same.json()["entry_id"] == first.json()["entry_id"] and same.json()["available"] == 100
    assert client.post(f"/wallets/{wb}/commands", headers=auth(finance), json={"command_id": cmd, "entry_type": "allocate", "amount": 200}).status_code == 409
    assert client.post(f"/wallets/{wa}/commands", headers=auth(finance), json={"command_id": cmd, "entry_type": "allocate", "amount": 150}).status_code == 409
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(FinancialLedgerEntry).where(FinancialLedgerEntry.wallet_id == wb)) == 0
        assert db.scalar(select(func.count()).select_from(FinancialLedgerEntry).where(FinancialLedgerEntry.command_id == cmd)) == 1


# ---------------------------------------------------------------- review N1: admin override audited as an attempt
def _override_count(action, ref):
    with SessionLocal() as db:
        return db.scalar(select(func.count()).select_from(AuditEvent).where(AuditEvent.action == action, AuditEvent.detail.contains(ref)))


def test_admin_override_is_audited_even_on_replay_and_refusal(client):
    admin = login(client, "platform-admin@aftab.test")["access_token"]
    rid, _ = _issued_reservation(client)
    action = "reservation.voucher_reissue.admin_override"
    cmd = f"ri-admin-{uuid.uuid4().hex[:8]}"
    doc = f"document://voucher/{rid}/admin"
    assert _reissue(client, admin, rid, command_id=cmd, doc=doc).status_code == 200
    assert _override_count(action, rid) == 1
    assert _reissue(client, admin, rid, command_id=cmd, doc=doc).status_code == 200  # idempotent replay
    assert _override_count(action, rid) == 2
    assert _reissue(client, admin, rid, command_id=cmd, doc=doc + "-other").status_code == 409  # refused
    assert _override_count(action, rid) == 3
    # idempotent re-fulfil of an already issued reservation is also recorded
    assert _fulfill(client, admin, rid).status_code == 200
    assert _override_count("reservation.fulfill.admin_override", rid) == 1


# ---------------------------------------------------------------- review N3: admission ticket validate/redeem scope
from test_leisure_commerce import full_end_to_end_booking, make_place, make_product, make_session, make_ticket_type, supplier as leisure_supplier


def _admission_ticket(client):
    owner = auth(login(client, "supplier@aftab.test")["access_token"])
    customer = auth(login(client, "employee@aftab.test")["access_token"])
    sid = leisure_supplier(client, owner, kind="event_hall")
    place = make_place(client, owner, sid, place_type="event_hall")
    product = make_product(client, owner, place["id"], service_type="event_hall", booking_mode="EVENT_TICKET")
    ttype = make_ticket_type(client, owner, product["id"], code="generic", price=300_000)
    sess = make_session(client, owner, product["id"], capacity=5)
    _, _, fulfilled = full_end_to_end_booking(client, owner, customer, sess["id"], ttype["id"])
    return fulfilled["admission_ticket"], sid


def _ticket_status(ticket_id):
    from app.operations import Ticket
    with SessionLocal() as db:
        return db.get(Ticket, ticket_id).status


def test_admission_ticket_denied_for_unrelated_agency_and_other_roles(client):
    ticket, _ = _admission_ticket(client)
    agency = login(client, _new_user("agency_partner", "agency-ticket"))["access_token"]
    outsider_supplier = login(client, _new_user("supplier", "ticket-outsider"))["access_token"]
    for token in (agency, outsider_supplier):
        assert client.get("/admission-tickets/validate", headers=auth(token), params={"qr_token": ticket["qr_token"]}).status_code == 403
        assert client.post("/admission-tickets/validate", headers=auth(token), json={"qr_token": ticket["qr_token"]}).status_code == 403
        assert client.post("/admission-tickets/redeem", headers=auth(token), json={"qr_token": ticket["qr_token"]}).status_code == 403
    assert _ticket_status(ticket["id"]) == "issued"


def test_admission_ticket_linked_agency_and_admin_allowed(client):
    ticket, sid = _admission_ticket(client)
    email = _new_user("agency_partner", "agency-venue")
    with SessionLocal() as db:
        uid = db.scalar(select(User.id).where(User.email == email))
        agency = Agency(tenant_id=_tenant_id(), display_name="آژانس محل آزمون", status="active", supplier_id=sid); db.add(agency); db.flush()
        db.add(AgencyMembership(tenant_id=agency.tenant_id, user_id=uid, agency_id=agency.id)); db.commit()
    token = login(client, email)["access_token"]
    assert client.get("/admission-tickets/validate", headers=auth(token), params={"qr_token": ticket["qr_token"]}).status_code == 200
    admin = login(client, "platform-admin@aftab.test")["access_token"]
    assert client.post("/admission-tickets/redeem", headers=auth(admin), json={"qr_token": ticket["qr_token"]}).status_code == 200
    assert _override_count("admission_ticket.redeem.admin_override", ticket["id"]) == 1
    assert _ticket_status(ticket["id"]) == "used"
