"""Excel/CSV lead import (review -> confirm) and journal export with account codes."""
import io
import uuid
import zipfile

from app.tabular import read_table, write_csv, write_xlsx


def _h(client, email):
    r = client.post("/auth/dev-login", json={"email": email})
    assert r.status_code == 200
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_xlsx_roundtrip_and_csv():
    data = write_xlsx(["نام", "موبایل"], [["سارا", "09121234567"], ["علی", 2]])
    assert zipfile.ZipFile(io.BytesIO(data)).testzip() is None
    assert read_table("a.xlsx", data) == [["نام", "موبایل"], ["سارا", "09121234567"], ["علی", "2"]]
    assert read_table("a.csv", write_csv(["a", "b"], [[1, None]]))[1][0] == "1"


def test_lead_import_review_then_confirm(client):
    desk = _h(client, "backoffice@aftab.test")
    assert client.post("/sales-desk/import", files={"file": ("x.csv", b"a,b\n1,2", "text/csv")}, headers=_h(client, "employee@aftab.test")).status_code == 403
    m1, m2 = "0919" + str(uuid.uuid4().int)[:7], "0919" + str(uuid.uuid4().int)[:7]
    rows = [["سارا", m1, "کیش ۳ شب", "2026-12-01", 2, "instagram", ""],
            ["", "123", "", "", "x", "fax", ""],                  # errors
            ["تکراری", m1, "کیش", "", 1, "", ""],                   # duplicate in file -> skipped
            ["رضا", m2, "مشهد", "15/09", 3, "unknown", "VIP"]]      # warnings only
    xlsx = write_xlsx(["نام", "موبایل", "سفر", "تاریخ سفر", "تعداد مسافر", "کانال", "توضیحات"], rows)
    review = client.post("/sales-desk/import", files={"file": ("leads.xlsx", xlsx, "application/octet-stream")}, headers=desk)
    assert review.status_code == 200, review.text
    r = review.json()
    assert r["stage"] == "review" and r["total"] == 4 and r["importable"] == 2 and r["errors"] == 1
    bad = r["rows"][1]
    assert "موبایل نامعتبر است" in bad["errors"] and "نام خالی است" in bad["errors"] and "تعداد مسافر نامعتبر است" in bad["errors"]
    assert r["rows"][3]["data"]["channel"] == "manual" and r["rows"][3]["data"]["travel_date"] is None
    assert client.get("/sales-desk/cases", params={"q": m1}, headers=desk).json()["items"] == []  # review writes nothing
    done = client.post("/sales-desk/import", files={"file": ("leads.xlsx", xlsx, "application/octet-stream")}, data={"confirm": "true"}, headers=desk).json()
    assert done["stage"] == "done" and done["created"] == 2
    assert len(client.get("/sales-desk/cases", params={"q": m1}, headers=desk).json()["items"]) == 1
    again = client.post("/sales-desk/import", files={"file": ("leads.xlsx", xlsx, "application/octet-stream")}, headers=desk).json()
    assert again["importable"] == 0  # both mobiles now have open cases
    assert client.post("/sales-desk/import", files={"file": ("x.csv", "نام,سفر\nا,ب".encode(), "text/csv")}, headers=desk).status_code == 422
    t = client.get("/sales-desk/import/template", headers=desk)
    assert t.status_code == 200 and read_table("t.xlsx", t.content)[0][1] == "موبایل"


def test_journal_export_with_codes(client):
    fin = _h(client, "finance@aftab.test")
    admin = _h(client, "tenant-admin@aftab.test")
    assert client.put("/commerce/accounting-codes", json={"items": [{"counterparty_type": "user", "account_type": "receivable", "code": "1103", "title": "حساب‌های دریافتنی"}]}, headers=_h(client, "backoffice@aftab.test")).status_code == 403
    assert client.put("/commerce/accounting-codes", json={"items": [{"counterparty_type": "user", "account_type": "receivable", "code": "1103", "title": "a"},
                                                                     {"counterparty_type": "user", "account_type": "receivable", "code": "1104", "title": "b"}]}, headers=admin).status_code == 422
    ok = client.put("/commerce/accounting-codes", json={"items": [{"counterparty_type": "user", "account_type": "receivable", "code": "1103", "title": "حساب‌های دریافتنی"}]}, headers=admin)
    assert ok.status_code == 200 and ok.json()["items"][0]["code"] == "1103"
    tag = uuid.uuid4().hex[:8]
    e = client.post("/commerce/treasury", json={"counterparty_type": "user", "counterparty_ref": "1", "counterparty_name": f"مشتری {tag}", "account_type": "receivable",
                                                "operation": "adjustment", "debit": 1_000_000, "credit": 0, "description": f"آزمون خروجی {tag}"}, headers=_h(client, "platform-admin@aftab.test"))
    assert e.status_code == 201, e.text
    chk = client.get("/commerce/treasury/export/check", headers=fin).json()
    assert chk["rows"] >= 1 and chk["debit"] >= 1_000_000
    x = client.get("/commerce/treasury/export", params={"fmt": "xlsx"}, headers=fin)
    assert x.status_code == 200 and x.headers["content-type"].startswith("application/vnd.openxmlformats")
    rows = read_table("j.xlsx", x.content)
    assert rows[0][3] == "کد حساب"
    mine = [r for r in rows[1:] if f"آزمون خروجی {tag}" in r[6]]
    assert len(mine) == 1 and mine[0][3] == "1103" and mine[0][7] == "1000000"
    assert client.get("/commerce/treasury/export", params={"date_from": "2026-12-01", "date_to": "2026-01-01"}, headers=fin).status_code == 422
    assert client.get("/commerce/treasury/export", headers=_h(client, "employee@aftab.test")).status_code == 403
