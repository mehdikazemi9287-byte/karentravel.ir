"""General ledger: Jalali periods, balanced vouchers, reversal, treasury posting with rules, trial balance, period close/reopen, export."""
import uuid

from sqlalchemy import select

from app.commerce import TreasuryEntry
from app.data_exchange import AccountingCode
from app.ledger import check_balanced, g2j, j2g, period_bounds, period_of
from app.main import SessionLocal, User

PERIOD = "1403-03"     # Khordad 1403 = 2024-05-21 .. 2024-06-20 (closed in the past, untouched by other tests)
DAY = "2024-06-01"


def _h(client, email):
    r = client.post("/auth/dev-login", json={"email": email})
    assert r.status_code == 200
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_calendar_and_balance_rules():
    assert g2j(2026, 11, 3) == (1405, 8, 12) and j2g(1405, 1, 1) == (2026, 3, 21)
    assert period_of("2026-11-03") == "1405-08" and period_bounds("1405-08") == ("2026-10-23", "2026-11-21")
    assert period_bounds("1403-12") == ("2025-02-19", "2025-03-20")   # Esfand 1403 is a leap month (30 days)
    assert period_bounds(PERIOD) == ("2024-05-21", "2024-06-20")
    assert check_balanced([{"debit": 5}, {"credit": 5}]) is None
    assert "تراز" in check_balanced([{"debit": 5}, {"credit": 4}])
    assert check_balanced([{"debit": 5, "credit": 5}, {"credit": 0}]) is not None
    assert check_balanced([{"debit": 5}]) is not None


def _codes(tenant_id, pairs):
    with SessionLocal() as db:
        for (ct, at), code in pairs.items():
            row = db.scalar(select(AccountingCode).where(AccountingCode.tenant_id == tenant_id, AccountingCode.counterparty_type == ct, AccountingCode.account_type == at))
            if row is None:
                db.add(AccountingCode(tenant_id=tenant_id, counterparty_type=ct, account_type=at, code=code, title=f"{ct}/{at}"))
            else:
                row.code = code
        db.commit()


def test_ledger_flow(client):
    fin = _h(client, "finance@aftab.test")
    admin = _h(client, "tenant-admin@aftab.test")
    assert client.get("/ledger/accounts", headers=_h(client, "employee@aftab.test")).status_code == 403
    chart = [{"code": "1110", "title": "بانک", "kind": "asset"}, {"code": "1120", "title": "درگاه پرداخت", "kind": "asset"},
             {"code": "1130", "title": "دریافتنی مشتریان", "kind": "asset"}, {"code": "2110", "title": "پرداختنی تأمین‌کنندگان", "kind": "liability"},
             {"code": "2120", "title": "کیف پول مشتریان", "kind": "liability"}, {"code": "4110", "title": "فروش خدمات سفر", "kind": "revenue"},
             {"code": "5110", "title": "بهای تمام‌شده", "kind": "expense"}]
    r = client.put("/ledger/accounts", json={"items": chart}, headers=fin)
    assert r.status_code == 200 and len(r.json()["items"]) == 7

    # manual voucher: validation, numbering, reversal
    bad = client.post("/ledger/vouchers", json={"voucher_date": DAY, "description": "آزمون", "lines": [{"account_code": "1110", "debit": 100}, {"account_code": "4110", "credit": 90}]}, headers=fin)
    assert bad.status_code == 422 and "تراز" in bad.json()["detail"]
    assert client.post("/ledger/vouchers", json={"voucher_date": DAY, "description": "آزمون", "lines": [{"account_code": "9999", "debit": 100}, {"account_code": "4110", "credit": 100}]}, headers=fin).status_code == 422
    v = client.post("/ledger/vouchers", json={"voucher_date": DAY, "description": "فروش نقدی", "lines": [{"account_code": "1110", "debit": 700}, {"account_code": "4110", "credit": 700}]}, headers=fin)
    assert v.status_code == 201, v.text
    v = v.json()
    assert v["period"] == PERIOD and v["total"] == 700 and [ln["account_title"] for ln in v["lines"]] == ["بانک", "فروش خدمات سفر"]
    rv = client.post(f"/ledger/vouchers/{v['id']}/reverse", json={"reason": "ثبت اشتباه", "voucher_date": DAY}, headers=fin)
    assert rv.status_code == 201 and rv.json()["number"] == v["number"] + 1 and rv.json()["lines"][0]["credit"] == 700
    assert client.post(f"/ledger/vouchers/{v['id']}/reverse", json={"reason": "دوباره"}, headers=fin).status_code == 409
    assert client.put("/ledger/accounts", json={"items": chart[1:]}, headers=fin).status_code == 409  # 1110 has vouchers

    # treasury -> vouchers with mapped codes and posting rules
    with SessionLocal() as db:
        tid = db.scalar(select(User.tenant_id).where(User.email == "finance@aftab.test"))
        tag = uuid.uuid4().hex[:6]
        db.add_all([
            TreasuryEntry(tenant_id=tid, counterparty_type="user", counterparty_ref="1", counterparty_name="مشتری", account_type="receivable", operation="purchase",
                          debit=1000, credit=0, operation_date=DAY, command_id=f"gl-a-{tag}", contract_ref="KS-GL-1"),
            TreasuryEntry(tenant_id=tid, counterparty_type="supplier", counterparty_ref="s1", counterparty_name="هتل", account_type="payable", operation="purchase",
                          debit=0, credit=800, operation_date=DAY, command_id=f"gl-b-{tag}"),
            TreasuryEntry(tenant_id=tid, counterparty_type="user", counterparty_ref="1", account_type="wallet", operation="deposit",
                          debit=0, credit=500, operation_date="2024-06-02", command_id=f"gl-c-{tag}"),
        ])
        db.commit()
    _codes(tid, {("user", "receivable"): "1130", ("supplier", "payable"): "2110"})
    rules = [{"operation": "purchase", "account_type": "receivable", "counter_code": "4110"}, {"operation": "purchase", "account_type": "payable", "counter_code": "5110"}]
    assert client.put("/ledger/posting-rules", json={"items": rules + [{"operation": "deposit", "account_type": "wallet", "counter_code": "0000"}]}, headers=fin).status_code == 422
    assert client.put("/ledger/posting-rules", json={"items": rules}, headers=fin).status_code == 200
    pre = client.post("/ledger/post-treasury", json={"period": PERIOD}, headers=fin).json()
    assert pre["ready"] == 2 and pre["created"] == 0 and sum(x["count"] for x in pre["missing"]) == 1 and pre["amount"] == 1800
    done = client.post("/ledger/post-treasury", json={"period": PERIOD, "confirm": True}, headers=fin).json()
    assert done["created"] == 2
    assert client.post("/ledger/post-treasury", json={"period": PERIOD, "confirm": True}, headers=fin).json()["created"] == 0  # idempotent
    close = client.post(f"/ledger/periods/{PERIOD}/close", headers=fin)
    assert close.status_code == 409 and "صندوق" in close.json()["detail"]

    _codes(tid, {("user", "wallet"): "2120"})
    client.put("/ledger/posting-rules", json={"items": rules + [{"operation": "deposit", "account_type": "wallet", "counter_code": "1120"}]}, headers=fin)
    assert client.post("/ledger/post-treasury", json={"period": PERIOD, "confirm": True}, headers=fin).json()["created"] == 1

    tb = client.get("/ledger/trial-balance", params={"period": PERIOD}, headers=fin).json()
    assert tb["balanced"] and tb["totals"]["debit"] == tb["totals"]["credit"] == 700 + 700 + 1000 + 800 + 500
    rows = {r["code"]: r for r in tb["items"]}
    assert rows["1130"]["closing"] == 1000 and rows["2110"]["closing"] == -800 and rows["2120"]["closing"] == -500 and rows["1110"]["closing"] == 0

    periods = {p["period"]: p for p in client.get("/ledger/periods", headers=fin).json()["items"]}
    assert periods[PERIOD]["unposted"] == 0 and periods[PERIOD]["status"] == "open"
    c = client.post(f"/ledger/periods/{PERIOD}/close", headers=fin)
    assert c.status_code == 200, c.text
    assert client.post("/ledger/vouchers", json={"voucher_date": DAY, "description": "دیرهنگام", "lines": [{"account_code": "1110", "debit": 1}, {"account_code": "4110", "credit": 1}]}, headers=fin).status_code == 409
    assert client.post(f"/ledger/periods/{PERIOD}/reopen", json={"reason": "اصلاح سند خرداد"}, headers=fin).status_code == 403
    assert client.post(f"/ledger/periods/{PERIOD}/reopen", json={"reason": "اصلاح سند خرداد"}, headers=admin).json()["status"] == "open"
    assert client.post("/ledger/periods/1499-01/close", headers=fin).status_code == 409   # future month

    x = client.get("/ledger/export", params={"period": PERIOD}, headers=fin)
    assert x.status_code == 200 and x.content[:2] == b"PK"

    with SessionLocal() as db:
        otid = db.scalar(select(User.tenant_id).where(User.email == "employee@faraz.test"))
        oemail = f"gl-fin-{uuid.uuid4().hex[:6]}@faraz.test"
        db.add(User(tenant_id=otid, email=oemail, name="مالی فراز", role="finance_operator"))
        db.commit()
    other = _h(client, oemail)
    assert client.get(f"/ledger/vouchers/{v['id']}", headers=other).status_code == 404
    assert client.get("/ledger/vouchers", params={"period": PERIOD}, headers=other).json()["items"] == []
