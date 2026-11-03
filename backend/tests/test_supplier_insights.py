"""Supplier cancellation rate and purchase reconciliation against the supplier's statement."""
import json
import uuid
from datetime import date

from sqlalchemy import select

from app import operations as m
from app.commerce import TreasuryEntry
from app.main import SessionLocal, User
from app.supplier_insights import parse_statement, reconcile


def _h(client, email):
    r = client.post("/auth/dev-login", json={"email": email})
    assert r.status_code == 200
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_parse_and_match():
    items, errors = parse_statement([["شماره رزرو", "تاریخ", "مبلغ"], ["A1", "2026-10-01", "۱۰۰٬۰۰۰"], ["", "", ""], ["A2", "", "x"]])
    assert items == [{"ref": "A1", "date": "2026-10-01", "amount": 100000, "row": 2}] and errors == ["سطر 4: شماره یا مبلغ نامعتبر"]
    assert parse_statement([["نام", "توضیح"], ["a", "b"]])[1]
    r = reconcile([{"ref": "a1", "amount": 100, "date": None}, {"ref": "B2", "amount": 50, "date": None}, {"ref": "Z9", "amount": 5, "date": None}],
                  [{"id": "1", "refs": ["A1"], "amount": 100, "date": "d", "booking": "A1"}, {"id": "2", "refs": ["B2"], "amount": 40, "date": "d", "booking": "B2"},
                   {"id": "3", "refs": ["C3"], "amount": 7, "date": "d", "booking": "C3"}])
    assert [x["ref"] for x in r["matched"]] == ["a1"] and r["amount_differs"][0]["difference"] == 10
    assert [x["ref"] for x in r["only_theirs"]] == ["Z9"] and [x["ref"] for x in r["only_ours"]] == ["C3"] and r["totals"]["difference"] == 155 - 147


def test_insights_and_reconciliation(client):
    fin = _h(client, "finance@aftab.test")
    with SessionLocal() as db:
        u = db.scalar(select(User).where(User.email == "employee@aftab.test"))
        sup = m.Supplier(tenant_id=u.tenant_id, supplier_type="hotel", display_name="هتل تطبیق " + uuid.uuid4().hex[:4], status="active")
        db.add(sup); db.flush()
        refs = []
        for i, st in enumerate(["confirmed", "cancelled", "completed", "failed"]):
            ref = f"SI-{uuid.uuid4().hex[:6].upper()}"
            refs.append(ref)
            r = m.Reservation(tenant_id=u.tenant_id, user_id=u.id, service_type="hotel", status=st, booking_reference=ref,
                              price_snapshot_json=json.dumps({"supplier_id": sup.id, "total_amount": 1000}), policy_at_booking_json="{}", current_policy_json="{}")
            db.add(r); db.flush()
            if st in ("confirmed", "completed"):
                db.add(TreasuryEntry(tenant_id=u.tenant_id, counterparty_type="supplier", counterparty_ref=sup.id, counterparty_name=sup.display_name, account_type="payable",
                                     operation="purchase", credit=800 + i, debit=0, operation_date=date.today().isoformat(), command_id=f"cost:{r.id}",
                                     contract_ref=ref, purchase_ref=r.id))
        db.commit()
        sid = sup.id

    assert client.get("/commerce/suppliers/insights", headers=_h(client, "employee@aftab.test")).status_code == 403
    item = next(i for i in client.get("/commerce/suppliers/insights", headers=fin).json()["items"] if i["id"] == sid)
    assert item["reservations"] == 4 and item["cancelled"] == 2 and item["cancellation_rate"] == 50.0 and item["purchases"] == 800 + 802

    today = date.today().isoformat()
    csv = f"شماره رزرو,تاریخ,مبلغ\n{refs[0]},{today},800\n{refs[2]},{today},900\nEXTRA-1,{today},50\n".encode("utf-8")
    form = {"date_from": today, "date_to": today}
    pre = client.post(f"/commerce/suppliers/{sid}/reconcile", data=form, files={"file": ("statement.csv", csv, "text/csv")}, headers=fin)
    assert pre.status_code == 200, pre.text
    p = pre.json()
    assert len(p["matched"]) == 1 and p["amount_differs"][0]["difference"] == 900 - 802 and p["only_theirs"][0]["ref"] == "EXTRA-1" and p["only_ours"] == []
    assert "run_id" not in p and client.get(f"/commerce/suppliers/{sid}/reconciliations", headers=fin).json()["items"] == []
    saved = client.post(f"/commerce/suppliers/{sid}/reconcile", data={**form, "confirm": "true"}, files={"file": ("statement.csv", csv, "text/csv")}, headers=fin).json()
    runs = client.get(f"/commerce/suppliers/{sid}/reconciliations", headers=fin).json()["items"]
    assert runs[0]["id"] == saved["run_id"] and runs[0]["differs"] == 1 and runs[0]["only_theirs"] == 1
    item = next(i for i in client.get("/commerce/suppliers/insights", headers=fin).json()["items"] if i["id"] == sid)
    assert item["last_recon"]["matched"] == 1

    assert client.post(f"/commerce/suppliers/{sid}/reconcile", data={"date_from": today, "date_to": "2000-01-01"}, files={"file": ("s.csv", csv, "text/csv")}, headers=fin).status_code == 422
    with SessionLocal() as db:
        otid = db.scalar(select(User.tenant_id).where(User.email == "employee@faraz.test"))
        oemail = f"si-fin-{uuid.uuid4().hex[:6]}@faraz.test"
        db.add(User(tenant_id=otid, email=oemail, name="مالی فراز", role="finance_operator"))
        db.commit()
    assert client.post(f"/commerce/suppliers/{sid}/reconcile", data=form, files={"file": ("statement.csv", csv, "text/csv")}, headers=_h(client, oemail)).status_code == 404
