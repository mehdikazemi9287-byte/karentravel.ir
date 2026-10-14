"""Deterministic minor-unit financial calculations; no rates or liabilities are invented."""
from collections import defaultdict
import re

class FinancialInvariantError(ValueError):
    pass

def minor(value):
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise FinancialInvariantError("مبلغ باید عدد صحیح نامنفی در واحد پول ثبت‌شده باشد")
    return value

def currency_code(value):
    if not isinstance(value, str) or not re.fullmatch(r"[A-Z]{3}", value):
        raise FinancialInvariantError("ارز معتبر و صریح ثبت نشده است")
    return value

def installment_schedule(principal, months, fee_bps):
    principal = minor(principal)
    if principal == 0 or isinstance(months, bool) or not isinstance(months, int) or not 2 <= months <= 36:
        raise FinancialInvariantError("اصل مبلغ یا تعداد اقساط معتبر نیست")
    if isinstance(fee_bps, bool) or not isinstance(fee_bps, int) or not 0 <= fee_bps <= 10000:
        raise FinancialInvariantError("کارمزد اقساط معتبر نیست")
    fee = principal * fee_bps // 10000
    total = principal + fee
    base, remainder = divmod(total, months)
    return total, [{"number": i + 1, "amount": base + (1 if i < remainder else 0),
                    "status": "scheduled"} for i in range(months)]

def payment_totals(payments):
    groups = defaultdict(lambda: {"captured": 0, "refunded": 0, "net_captured": 0})
    for row in payments:
        curr = currency_code(row.currency)
        captured, refunded = minor(row.captured_amount), minor(row.refunded_amount)
        if refunded > captured:
            raise FinancialInvariantError("بازپرداخت از وجه ثبت‌شده بیشتر است")
        groups[curr]["captured"] += captured
        groups[curr]["refunded"] += refunded
        groups[curr]["net_captured"] += captured - refunded
    return [{"currency": c, **values} for c, values in sorted(groups.items())]

def supplier_liability(price, currency):
    currency_code(currency)
    if price is None:
        raise FinancialInvariantError("تفکیک قیمت و تعهد تأمین‌کننده ثبت نشده است")
    if currency == "IRR" and price.supplier_net_rate_irr is not None:
        amount = price.supplier_net_rate_irr
    elif price.supplier_currency == currency and price.supplier_net_rate is not None:
        amount = price.supplier_net_rate
    else:
        raise FinancialInvariantError("تعهد تأمین‌کننده در ارز تسویه ثبت نشده است")
    return minor(amount)

def settlement_remaining(price, payments, settlements, supplier_id):
    funded = [p for p in payments if p.captured_amount > 0]
    if not funded:
        raise FinancialInvariantError("وجه تأییدشده برای تسویه وجود ندارد")
    currencies = {currency_code(p.currency) for p in funded}
    if len(currencies) != 1:
        raise FinancialInvariantError("تسویه خودکار پرداخت‌های چندارزی مجاز نیست")
    currency = next(iter(currencies))
    if any(p.refunded_amount for p in funded):
        raise FinancialInvariantError("پس از استرداد، تعهد تأمین‌کننده نیازمند تطبیق مستقل است")
    liability = supplier_liability(price, currency)
    if liability <= 0:
        raise FinancialInvariantError("تعهد مثبت تأمین‌کننده ثبت نشده است")
    if sum(minor(p.captured_amount) for p in funded) < liability:
        raise FinancialInvariantError("وجه تأییدشده برای تعهد تأمین‌کننده کافی نیست")
    reserved = 0
    for row in settlements:
        if row.status in {"cancelled", "canceled", "failed", "rejected"}:
            continue
        if row.status not in {"pending", "approved", "paid", "completed", "settled"}:
            raise FinancialInvariantError("وضعیت تسویه پیشین نیازمند بررسی است")
        if row.currency != currency or row.supplier_id != supplier_id:
            raise FinancialInvariantError("ارز یا تأمین‌کننده تسویه پیشین ناسازگار است")
        reserved += minor(row.amount)
    if reserved > liability:
        raise FinancialInvariantError("تسویه ثبت‌شده از تعهد تأمین‌کننده بیشتر است")
    return {"currency": currency, "supplier_liability": liability,
            "allocated_settlement": reserved, "remaining": liability - reserved}
