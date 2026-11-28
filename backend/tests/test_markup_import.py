"""PR-7: markup-rule import from Excel/CSV — template, review with per-row errors, all-or-nothing confirm.
TEST FIXTURES ONLY: synthetic groups, suppliers and percentages; created rules are disabled at the end, not deleted."""
import uuid

from sqlalchemy import select

from app.commerce import CustomerGroup, MarkupRule
from app.main import SessionLocal, User
from app.markup_import import TEMPLATE_HEADER, parse_percent
from app.tabular import read_table, write_csv, write_xlsx


def _h(client, email="tenant-admin@aftab.test"):
    return {"Authorization": "Bearer " + client.post("/auth/dev-login", json={"email": email}).json()["access_token"]}


def _group(name, code=None):
    with SessionLocal() as db:
        tid = db.scalar(select(User.tenant_id).where(User.email == "tenant-admin@aftab.test"))
        g = CustomerGroup(tenant_id=tid, code=code or "imp-" + uuid.uuid4().hex[:8], name=name)
        db.add(g); db.commit()
        return g.id


def _upload(client, h, rows, confirm=False, fmt="xlsx"):
    data = write_xlsx(TEMPLATE_HEADER, rows) if fmt == "xlsx" else write_csv(TEMPLATE_HEADER, rows)
    return client.post("/commerce/markup-rules/import", headers=h, data={"confirm": "true" if confirm else "false"},
                       files={"file": (f"rules.{fmt}", data, "application/octet-stream")})


def test_percent_parsing_uses_persian_digits_and_basis_points():
    assert parse_percent("۱۲٫۵٪") == 1250 and parse_percent("5") == 500 and parse_percent("0.25%") == 25 and parse_percent("") is None
    for bad in ("abc", "-1", "1.234"):
        try:
            parse_percent(bad)
        except ValueError:
            continue
        raise AssertionError(bad)


def test_template_is_admin_only_and_has_the_columns(client):
    assert client.get("/commerce/markup-rules/import/template", headers=_h(client, "employee@aftab.test")).status_code == 403
    r = client.get("/commerce/markup-rules/import/template", headers=_h(client))
    assert r.status_code == 200 and r.content.startswith(b"PK")
    assert read_table("t.xlsx", r.content)[0] == TEMPLATE_HEADER


def test_review_then_all_or_nothing_confirm(client):
    h = _h(client)
    gname = "گروه ایمپورت " + uuid.uuid4().hex[:5]
    gid = _group(gname)
    tag = uuid.uuid4().hex[:6]
    good = [f"ایمپورت {tag} الف", "پرواز", gname, "نیرا", "داخلی", "سیستمی", "vr", "THR", "MHD", "۷٫۵", "۵", "۰", "", "", "", "بله"]
    fixed = [f"ایمپورت {tag} ب", "", "", "ماهان", "خارجی", "", "W5", "", "", "", "", "", "۱٬۵۰۰٬۰۰۰", "", "", "خیر"]
    bad = [f"ایمپورت {tag} ج", "", "گروهی که نیست", "تأمین‌کنندهٔ ناشناس", "نیمه", "", "تهران", "", "", "5", "", "", "1000", "", "", "شاید"]
    review = _upload(client, h, [good, fixed, bad]).json()
    assert review["stage"] == "review" and (review["total"], review["valid"], review["errors"]) == (3, 2, 1)
    rows = {r["row"]: r for r in review["rows"]}
    assert rows[2]["data"]["adult"] == 750 and rows[2]["data"]["child"] == 500 and rows[2]["data"]["group_id"] == gid
    assert rows[2]["data"]["supplier_id"] == "nira" and rows[2]["data"]["airline_code"] == "VR"
    assert (rows[3]["data"]["calc"], rows[3]["data"]["adult"], rows[3]["data"]["status"], rows[3]["data"]["scope"]) == ("fixed", 1500000, "disabled", "international")
    assert len(rows[4]["errors"]) >= 5
    count = lambda: len(client.get("/commerce/markup-rules", headers=h).json()["items"])  # noqa: E731
    before = count()
    assert _upload(client, h, [good, fixed, bad], confirm=True).status_code == 422
    assert count() == before                                                     # nothing written while a row has errors
    done = _upload(client, h, [good, fixed], confirm=True, fmt="csv").json()
    assert done["stage"] == "done" and done["created"] == 2 and count() == before + 2
    try:
        quote = client.post("/commerce/markup-rules/preview", headers=h, json={"service_type": "flight", "supplier_id": "nira", "airline_code": "VR", "scope": "domestic",
                                                                              "flight_type": "system", "origin": "THR", "destination": "MHD", "fares": {"adult": {"count": 1, "total": 10_000_000}}}).json()
        assert quote["rule"] is None or quote["rule"]["id"] not in done["rule_ids"]   # group rule needs the group: no leak to everyone
    finally:
        with SessionLocal() as db:
            for rid in done["rule_ids"]:
                db.get(MarkupRule, rid).status = "disabled"
            db.get(CustomerGroup, gid).status = "disabled"
            db.commit()


def test_sample_row_and_empty_file_are_rejected(client):
    h = _h(client)
    sample = _upload(client, h, [["نمونه — این ردیف را پاک کنید", "", "", "", "", "", "", "", "", "5", "", "", "", "", "", ""]]).json()
    assert sample["errors"] == 1
    r = client.post("/commerce/markup-rules/import", headers=h, files={"file": ("x.csv", "عنوان\n".encode(), "text/csv")})
    assert r.status_code == 422


def test_ambiguous_group_name_is_a_row_error_and_reupload_warns(client):
    h = _h(client)
    name = "twin-" + uuid.uuid4().hex[:6]
    a, b = _group(name), _group("گروه دیگر " + name, code=name)     # one group's name is another group's code
    row = [f"دوقلو {name}", "", name, "", "", "", "", "", "", "3", "", "", "", "", "", ""]
    try:
        r = _upload(client, h, [row]).json()["rows"][0]
        assert any("چند گروه" in e for e in r["errors"])
    finally:
        with SessionLocal() as db:
            for gid in (a, b):
                db.get(CustomerGroup, gid).status = "disabled"
            db.commit()
    tag = uuid.uuid4().hex[:6]
    plain = [f"تکرار {tag}", "", "", "", "", "", "", "KIH", "THR", "2", "", "", "", "", "", ""]
    done = _upload(client, h, [plain], confirm=True).json()
    try:
        again = _upload(client, h, [plain]).json()["rows"][0]
        assert any("از قبل هست" in w for w in again["warnings"]) and not again["errors"]
    finally:
        with SessionLocal() as db:
            for rid in done["rule_ids"]:
                db.get(MarkupRule, rid).status = "disabled"
            db.commit()
