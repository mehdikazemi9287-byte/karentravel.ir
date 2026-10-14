"""Versioned funding references over existing checkout/payment/ledger records."""
import json
from datetime import datetime, timezone
from sqlalchemy import select
from . import operations as m
from .financial_amounts import FinancialInvariantError, minor, currency_code

def declaration(total, currency, wallet_amount, credit_amount, quote_hash,
                wallet_reserve_id=None, credit_reserve_id=None):
    total, wallet_amount, credit_amount = map(minor, (total, wallet_amount, credit_amount))
    currency_code(currency)
    if total <= 0 or wallet_amount + credit_amount > total:
        raise FinancialInvariantError("تخصیص منابع از مبلغ قطعی رزرو بیشتر است")
    if (wallet_amount or credit_amount) and currency != "IRR":
        raise FinancialInvariantError("کیف پول و اعتبار ریالی با قیمت ارزی قابل ترکیب نیستند")
    if wallet_amount and not wallet_reserve_id or credit_amount and not credit_reserve_id:
        raise FinancialInvariantError("مرجع مسدودی هر منبع باید ثبت شود")
    return {"schema_version": 2, "total_amount": total, "currency": currency,
            "price_snapshot_hash": quote_hash, "wallet_amount": wallet_amount,
            "credit_amount": credit_amount, "payable_amount": total-wallet_amount-credit_amount,
            "wallet_reserve_id": wallet_reserve_id, "credit_reserve_id": credit_reserve_id}

def checked_declaration(funding, raw_price, quote_hash, current_quote_hash):
    price = json.loads(raw_price)
    total, currency = minor(price["total_amount"]), currency_code(price["currency"])
    if current_quote_hash != quote_hash:
        raise FinancialInvariantError("قیمت رزرو پس از تخصیص منابع تغییر کرده است")
    if funding.get("schema_version") != 2:
        if funding.get("wallet_amount") or funding.get("credit_amount"):
            raise FinancialInvariantError("تخصیص قدیمی بدون مرجع منابع نیازمند تطبیق است")
        return {"total_amount": total, "currency": currency, "payable_amount": total}
    expected = declaration(total, currency, funding["wallet_amount"], funding["credit_amount"],
                           quote_hash, funding.get("wallet_reserve_id"), funding.get("credit_reserve_id"))
    if expected != funding:
        raise FinancialInvariantError("snapshot تخصیص با مبلغ یا منابع رزرو سازگار نیست")
    return expected

def latest_plan(db, reservation, hash_price):
    checkout = db.scalar(select(m.CheckoutSession).where(
        m.CheckoutSession.tenant_id == reservation.tenant_id,
        m.CheckoutSession.reservation_id == reservation.id,
        m.CheckoutSession.user_id == reservation.user_id
    ).order_by(m.CheckoutSession.created_at.desc(), m.CheckoutSession.id.desc()).limit(1))
    if checkout is None:
        return None, None
    funding = json.loads(checkout.state_json).get("funding", {})
    return checkout, checked_declaration(funding, reservation.price_snapshot_json,
                                         checkout.price_snapshot_hash, hash_price(reservation.price_snapshot_json))

def bank_payable(db, reservation, hash_price):
    checkout, plan = latest_plan(db, reservation, hash_price)
    if checkout is not None:
        expiry = checkout.expires_at.replace(tzinfo=timezone.utc) if checkout.expires_at.tzinfo is None else checkout.expires_at
        if expiry <= datetime.now(timezone.utc): raise FinancialInvariantError("checkout برای پرداخت جدید منقضی شده است")
    if checkout is not None and plan.get("schema_version") == 2:
        for name, amount_name in (("wallet_reserve_id", "wallet_amount"), ("credit_reserve_id", "credit_amount")):
            if not plan[amount_name]: continue
            entry = db.scalar(select(m.FinancialLedgerEntry).where(m.FinancialLedgerEntry.id == plan[name], m.FinancialLedgerEntry.tenant_id == reservation.tenant_id, m.FinancialLedgerEntry.reservation_id == reservation.id, m.FinancialLedgerEntry.entry_type == "reserve"))
            if entry is None or entry.amount != plan[amount_name]:
                raise FinancialInvariantError("مرجع مسدودی منبع با تخصیص رزرو سازگار نیست")
            if name == "wallet_reserve_id":
                account = db.scalar(select(m.Wallet).where(m.Wallet.id == entry.wallet_id, m.Wallet.tenant_id == reservation.tenant_id, m.Wallet.currency == plan["currency"], m.Wallet.owner_type == "user", m.Wallet.owner_reference == str(reservation.user_id))) if entry.wallet_id and not entry.credit_account_id else None
            else:
                organizations = select(m.EmployeeAssignment.organization_id).where(m.EmployeeAssignment.tenant_id == reservation.tenant_id, m.EmployeeAssignment.user_id == reservation.user_id)
                account = db.scalar(select(m.CreditAccount).where(m.CreditAccount.id == entry.credit_account_id, m.CreditAccount.tenant_id == reservation.tenant_id, m.CreditAccount.currency == plan["currency"], m.CreditAccount.organization_id.in_(organizations))) if entry.credit_account_id and not entry.wallet_id else None
            if account is None: raise FinancialInvariantError("مالکیت، نوع یا ارز منبع تخصیص معتبر نیست")
            changed = db.scalar(select(m.FinancialLedgerEntry.id).where(m.FinancialLedgerEntry.tenant_id == reservation.tenant_id, m.FinancialLedgerEntry.reservation_id == reservation.id, m.FinancialLedgerEntry.entry_type.in_(["release", "reverse_capture"]), m.FinancialLedgerEntry.wallet_id == entry.wallet_id if entry.wallet_id else m.FinancialLedgerEntry.credit_account_id == entry.credit_account_id).limit(1))
            if changed is not None: raise FinancialInvariantError("منبع آزادشده یا برگشت‌خورده نیازمند تخصیص مجدد معتبر است")
        return plan["payable_amount"]
    entry = db.scalar(select(m.FinancialLedgerEntry.id).where(
        m.FinancialLedgerEntry.tenant_id == reservation.tenant_id,
        m.FinancialLedgerEntry.reservation_id == reservation.id,
        m.FinancialLedgerEntry.entry_type.in_(["reserve", "capture"])
    ).limit(1))
    if entry is not None:
        raise FinancialInvariantError("گردش اعتبار بدون مرجع تخصیص نیازمند تطبیق است")
    return minor(json.loads(reservation.price_snapshot_json)["total_amount"])
