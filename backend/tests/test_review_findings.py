"""Independent-review fixes on top of PRs #120–#125: customer search carries no net figures, a markup rule names a
supplier by id or provider_key, direct price-group membership is disabled (never deleted), only an active agency
prices a user, the v3 gateway holds no DB transaction across the network call, markup-import edge cases, invite rules.
TEST FIXTURES ONLY: synthetic suppliers, offers, groups and 0912-style numbers; rows are disabled at the end, never deleted."""
import importlib.util
import json
import random
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import select

from app import main
from app import operations as m
from app.commerce import CustomerGroup, CustomerGroupLink, CustomerGroupMember, MarkupRule, choose_rule, user_group_id
from app.main import AuditEvent, SessionLocal, User


def _h(client, email):
    return {"Authorization": "Bearer " + client.post("/auth/dev-login", json={"email": email}).json()["access_token"]}


def _tenant(email="tenant-admin@aftab.test"):
    with SessionLocal() as db:
        u = db.scalar(select(User).where(User.email == email))
        return u.tenant_id, u.id


def _disable(model, ids, value="disabled"):
    with SessionLocal() as db:
        for row in db.scalars(select(model).where(model.id.in_(list(ids)))):
            row.status = value
        db.commit()


# ---------------------------------------------------------------- 1. no net figures in customer search
NET, TAXES, FEES, DISCOUNTS, MARKUP = 13_579_000, 111_000, 22_000, 3_000, 1_234_000


def test_customer_search_response_has_no_net_figures(client):
    tid, _ = _tenant("backoffice@aftab.test")
    tag = "NETLEAK" + uuid.uuid4().hex[:6]
    with SessionLocal() as db:
        sup = m.Supplier(tenant_id=tid, supplier_type="hotel", display_name="ت " + tag, status="active")
        db.add(sup); db.flush()
        attrs = {"city": tag, "taxes": TAXES, "fees": FEES, "discounts": DISCOUNTS, "net": NET, "margin": 1, "markup": 1, "net_amount": NET,
                 "room_type": "دو تخته", "observed_at": datetime.now(timezone.utc).isoformat(), "freshness_ttl_seconds": 3600}
        offer = m.Offer(tenant_id=tid, supplier_id=sup.id, service_type="hotel", title="هتل " + tag, amount=NET, available_units=3, status="active",
                        attributes_json=json.dumps(attrs), policy_json="{}", valid_until=datetime.now(timezone.utc) + timedelta(days=3))
        rule = MarkupRule(tenant_id=tid, title="آزمون نشت " + tag, service_type="hotel", supplier_id=sup.id, calc="fixed", adult=MARKUP)
        db.add_all([offer, rule]); db.commit()
        offer_id, rule_id = offer.id, rule.id
    net_final = NET + TAXES + FEES - DISCOUNTS
    sell = net_final + MARKUP
    try:
        r = client.post("/search/offers", json={"service_type": "hotel", "query": tag}, headers=_h(client, "employee@aftab.test"))
        assert r.status_code == 200, r.text
        mine = [o for o in r.json() if o["id"] == offer_id]
        assert len(mine) == 1
        o = mine[0]
        assert o["amount"] == o["final_price"] == o["total_amount"] == sell
        for key in ("base_price", "taxes", "fees", "discounts"):
            assert key not in o
        assert o["attributes"]["room_type"] == "دو تخته" and o["attributes"]["city"] == tag
        blob = json.dumps(r.json())
        for leaked in (NET, net_final, TAXES, FEES):
            assert str(leaked) not in blob, leaked
        for key in ('"net"', '"net_amount"', '"margin"', '"markup"'):
            assert key not in blob
        v2 = client.post("/search/v2", json={"query": tag, "verticals": ["hotel"]}, headers=_h(client, "employee@aftab.test"))
        assert v2.status_code == 200 and str(sell) in json.dumps(v2.json())
        assert all(str(x) not in json.dumps(v2.json()) for x in (NET, net_final, TAXES))
        # staff keep the full breakdown
        staff = [x for x in client.post("/search/offers", json={"service_type": "hotel", "query": tag}, headers=_h(client, "backoffice@aftab.test")).json() if x["id"] == offer_id][0]
        assert staff["base_price"] == NET and staff["taxes"] == TAXES and staff["final_price"] == sell
    finally:
        _disable(MarkupRule, [rule_id])
        _disable(m.Offer, [offer_id], "inactive")


def test_pool_keeps_pass_through_components_but_drops_margin_keys():
    attrs = {"taxes": 5, "fees": 6, "discounts": 1, "net": 9, "margin": 2, "markup": 3, "room_type": "x"}
    cleaned = main._strip_net_attributes(attrs, main._MARGIN_ATTRIBUTE_KEYS)
    assert cleaned == {"taxes": 5, "fees": 6, "discounts": 1, "room_type": "x"}
    assert main._strip_net_attributes(attrs) == {"room_type": "x"}


# ---------------------------------------------------------------- 2. supplier named by id or provider_key
def test_markup_rule_matches_supplier_by_id_or_provider_key():
    tid, _ = _tenant()
    key, other_key = "rv" + uuid.uuid4().hex[:8], "rv" + uuid.uuid4().hex[:8]
    with SessionLocal() as db:
        sup = m.Supplier(tenant_id=tid, supplier_type="hotel", display_name="کلیددار " + key, status="active", provider_key=key)
        other = m.Supplier(tenant_id=tid, supplier_type="hotel", display_name="دیگری " + other_key, status="active", provider_key=other_key)
        db.add_all([sup, other]); db.flush()
        by_key = MarkupRule(tenant_id=tid, title="با کلید " + key, service_type="visa", supplier_id=key, calc="fixed", adult=1000)
        by_id = MarkupRule(tenant_id=tid, title="با شناسه " + key, service_type="cip", supplier_id=sup.id, calc="fixed", adult=1000)
        db.add_all([by_key, by_id]); db.commit()
        ids, sup_id, other_id = [by_key.id, by_id.id], sup.id, other.id
    try:
        with SessionLocal() as db:
            # offer rows carry the supplier UUID; a rule saved with the provider_key (panel / import) must still apply
            assert getattr(choose_rule(db, tid, {"service_type": "visa", "supplier_id": sup_id}, group_id=None), "id", None) == ids[0]
            # flight adapters pass the provider_key; a rule saved with the UUID of that supplier must still apply
            assert getattr(choose_rule(db, tid, {"service_type": "cip", "supplier_id": key}, group_id=None), "id", None) == ids[1]
            # another supplier (by id or by key) never matches
            for value in (other_id, other_key):
                assert choose_rule(db, tid, {"service_type": "visa", "supplier_id": value}, group_id=None) is None
                assert choose_rule(db, tid, {"service_type": "cip", "supplier_id": value}, group_id=None) is None
            # the key of a supplier in another tenant is not this tenant's supplier
            ftid, _ = _tenant("employee@faraz.test")
            assert choose_rule(db, ftid, {"service_type": "visa", "supplier_id": sup_id}, group_id=None) is None
    finally:
        _disable(MarkupRule, ids)


# ---------------------------------------------------------------- 3. direct membership disabled, never deleted
def _new_user(tid, tag):
    with SessionLocal() as db:
        u = User(tenant_id=tid, email=f"rv-{tag}@aftab.test", name="کاربر بازبینی " + tag, role="customer")
        db.add(u); db.commit()
        return u.id


def test_price_group_null_disables_direct_membership_and_links_apply_again(client):
    admin = _h(client, "tenant-admin@aftab.test")
    tid, _ = _tenant()
    tag = uuid.uuid4().hex[:6]
    uid = _new_user(tid, tag)
    with SessionLocal() as db:
        org = m.Organization(tenant_id=tid, name="سازمان بازبینی " + tag, status="active")
        g_org = CustomerGroup(tenant_id=tid, code="rvo-" + tag, name="گروه سازمان " + tag)
        g_dir = CustomerGroup(tenant_id=tid, code="rvd-" + tag, name="گروه مستقیم " + tag)
        db.add_all([org, g_org, g_dir]); db.flush()
        db.add(m.EmployeeAssignment(tenant_id=tid, user_id=uid, organization_id=org.id))
        link = CustomerGroupLink(tenant_id=tid, party_type="organization", party_id=org.id, group_id=g_org.id, status="active")
        db.add(link); db.commit()
        g_org_id, g_dir_id, link_id = g_org.id, g_dir.id, link.id

    def resolved():
        with SessionLocal() as db:
            return user_group_id(db, tid, uid)

    try:
        # null with no membership is a no-op (no row is created, no 422 about a default group)
        r = client.put(f"/admin/users/{uid}/price-group", headers=admin, json={"group_id": None})
        assert r.status_code == 200 and r.json()["price_group"] is None
        with SessionLocal() as db:
            assert db.scalar(select(CustomerGroupMember).where(CustomerGroupMember.tenant_id == tid, CustomerGroupMember.user_id == uid)) is None
        assert resolved() == g_org_id
        assert client.put(f"/admin/users/{uid}/price-group", headers=admin, json={"group_id": g_dir_id}).json()["price_group"]["id"] == g_dir_id
        assert resolved() == g_dir_id
        with SessionLocal() as db:
            row_id = db.scalar(select(CustomerGroupMember.id).where(CustomerGroupMember.tenant_id == tid, CustomerGroupMember.user_id == uid))
        off = client.put(f"/admin/users/{uid}/price-group", headers=admin, json={"group_id": None})
        assert off.status_code == 200 and off.json()["price_group"] is None
        assert resolved() == g_org_id                                    # the organization link applies again
        with SessionLocal() as db:
            row = db.get(CustomerGroupMember, row_id)
            assert row is not None and row.status == "disabled" and row.group_id == g_dir_id   # kept, not deleted
        members = client.get(f"/commerce/groups/{g_dir_id}/members", headers=admin).json()["items"]
        assert uid not in [i["user_id"] for i in members]
        again = client.put(f"/admin/users/{uid}/price-group", headers=admin, json={"group_id": g_dir_id})
        assert again.json()["price_group"]["id"] == g_dir_id and resolved() == g_dir_id
        with SessionLocal() as db:
            assert db.get(CustomerGroupMember, row_id).status == "active"   # the same row is reactivated
            actions = [a.action for a in db.scalars(select(AuditEvent).where(AuditEvent.entity == "user", AuditEvent.entity_id == uid))]
        assert actions.count("user.price_group_changed") == 3
    finally:
        _disable(CustomerGroupLink, [link_id])
        _disable(CustomerGroup, [g_org_id, g_dir_id])
        with SessionLocal() as db:
            db.get(User, uid).disabled_at = datetime.now(timezone.utc); db.commit()


# ---------------------------------------------------------------- 5. only an active agency prices its members
def test_inactive_agency_link_gives_no_group():
    tid, _ = _tenant()
    tag = uuid.uuid4().hex[:6]
    uid = _new_user(tid, "ag" + tag)
    with SessionLocal() as db:
        agency = m.Agency(tenant_id=tid, display_name="آژانس بازبینی " + tag, status="suspended")
        g = CustomerGroup(tenant_id=tid, code="rva-" + tag, name="گروه آژانس " + tag)
        db.add_all([agency, g]); db.flush()
        db.add(m.AgencyMembership(tenant_id=tid, user_id=uid, agency_id=agency.id))
        link = CustomerGroupLink(tenant_id=tid, party_type="agency", party_id=agency.id, group_id=g.id, status="active")
        db.add(link); db.commit()
        agency_id, gid, link_id = agency.id, g.id, link.id
    try:
        with SessionLocal() as db:
            assert user_group_id(db, tid, uid) != gid
            db.get(m.Agency, agency_id).status = "active"; db.commit()
            assert user_group_id(db, tid, uid) == gid
            db.get(m.Agency, agency_id).status = "sample"; db.commit()    # the model default is not an active agency
            assert user_group_id(db, tid, uid) != gid
    finally:
        _disable(CustomerGroupLink, [link_id])
        _disable(CustomerGroup, [gid])


# ---------------------------------------------------------------- 6. v3 gateway: no open transaction during the call
def test_v3_gateway_closes_the_db_transaction_before_the_network_call(client, monkeypatch):
    sessions, seen = [], {}

    def tracked_db():
        db = SessionLocal()
        sessions.append(db)
        try:
            yield db
        finally:
            db.close()

    async def fake_call(data, *, public, tenant_ref, price_group=None):
        seen["open"] = [s.in_transaction() for s in sessions]
        seen["tenant_ref"] = tenant_ref
        return {"entities": []}

    monkeypatch.setattr(main, "_search_service_call", fake_call)
    main.app.dependency_overrides[main.get_db] = tracked_db
    try:
        r = client.post("/search/v3", json={"verticals": ["flight"]}, headers=_h(client, "employee@aftab.test"))
    finally:
        main.app.dependency_overrides.pop(main.get_db, None)
    assert r.status_code == 200
    assert seen["open"] and not any(seen["open"]) and seen["tenant_ref"]


# ---------------------------------------------------------------- 7. markup import edge cases
def test_import_rejects_nan_infinity_and_excel_percent_fractions(client):
    from app.markup_import import TEMPLATE_HEADER, parse_percent
    from app.tabular import write_xlsx
    for bad in ("NaN", "nan", "Infinity", "-Infinity", "inf", "sNaN"):
        with pytest.raises(ValueError):
            parse_percent(bad)
    admin = _h(client, "tenant-admin@aftab.test")
    tag = uuid.uuid4().hex[:6]

    def row(title, adult, child=""):
        return [title, "پرواز", "", "", "", "", "", "", "", adult, child, "", "", "", "", "بله"]

    data = write_xlsx(TEMPLATE_HEADER, [row("نان " + tag, "NaN"), row("بی‌نهایت " + tag, "Infinity"), row("قالب درصد " + tag, "0.05"),
                                        row("کودک " + tag, "5", "0.5"), row("علامت‌دار " + tag, "0.5٪")])
    r = client.post("/commerce/markup-rules/import", headers=admin, data={"confirm": "false"}, files={"file": ("r.xlsx", data, "application/octet-stream")})
    assert r.status_code == 200, r.text
    rows = {x["row"]: x for x in r.json()["rows"]}
    assert any("عدد نیست" in e for e in rows[2]["errors"]) and any("عدد نیست" in e for e in rows[3]["errors"])
    assert any("قالب «درصد»" in e for e in rows[4]["errors"])
    assert any("درصد کودک" in e and "قالب «درصد»" in e for e in rows[5]["errors"])
    assert not rows[6]["errors"] and rows[6]["data"]["adult"] == 50       # an explicit % sign is taken as written
    big = b"x" * (2 * 1024 * 1024 + 1)
    too_big = client.post("/commerce/markup-rules/import", headers=admin, data={"confirm": "false"}, files={"file": ("r.csv", big, "text/csv")})
    assert too_big.status_code == 413


# ---------------------------------------------------------------- 9 + 10. invite: same 409 answer, reason for admin roles
def _mobile():
    return "0912" + str(random.randint(1000000, 9999999))


def test_invite_409_does_not_reveal_another_tenant_and_admin_roles_need_a_reason(client):
    admin = _h(client, "tenant-admin@aftab.test")
    here, there = _mobile(), _mobile()
    first = client.post("/admin/users", headers=admin, json={"name": "دعوت یک", "mobile": here, "role": "employee"})
    assert first.status_code == 201, first.text
    ftid, _ = _tenant("employee@faraz.test")
    with SessionLocal() as db:
        db.add(User(tenant_id=ftid, email=f"98{there[1:]}@mobile.karenseir.local", name="حساب فراز", role="customer", mobile_e164="+98" + there[1:]))
        db.commit()
    same = client.post("/admin/users", headers=admin, json={"name": "دعوت دو", "mobile": here})
    other = client.post("/admin/users", headers=admin, json={"name": "دعوت سه", "mobile": there})
    assert same.status_code == other.status_code == 409 and same.json()["detail"] == other.json()["detail"]

    for role in ("tenant_admin", "finance_operator", "backoffice_expert", "organization_admin"):
        assert client.post("/admin/users", headers=admin, json={"name": "بی‌دلیل", "mobile": _mobile(), "role": role}).status_code == 422
        assert client.post("/admin/users", headers=admin, json={"name": "بی‌دلیل", "mobile": _mobile(), "role": role, "reason": "  "}).status_code == 422
    made = client.post("/admin/users", headers=admin, json={"name": "مدیر مالی آزمون", "mobile": _mobile(), "role": "finance_operator", "reason": "واحد مالی جدید"})
    assert made.status_code == 201, made.text
    uid = made.json()["id"]
    with SessionLocal() as db:
        events = {a.action: json.loads(a.detail) for a in db.scalars(select(AuditEvent).where(AuditEvent.entity == "user", AuditEvent.entity_id == uid))}
        for u in db.scalars(select(User).where(User.id.in_([uid, first.json()["id"]]))):
            u.disabled_at = datetime.now(timezone.utc)
        db.commit()
    assert events["user.invited"]["reason"] == "واحد مالی جدید"
    assert events["user.admin_role_granted"] == {"to": "finance_operator", "via": "invite", "reason": "واحد مالی جدید"}
    # ordinary roles still need no reason
    plain = client.post("/admin/users", headers=admin, json={"name": "کارمند آزمون", "mobile": _mobile(), "role": "employee"})
    assert plain.status_code == 201
    with SessionLocal() as db:
        db.get(User, plain.json()["id"]).disabled_at = datetime.now(timezone.utc); db.commit()


# ---------------------------------------------------------------- migration 81
MIGRATION = Path(__file__).resolve().parents[1] / "alembic" / "versions" / "20261128_81_group_member_status.py"


def test_migration_81_adds_status_with_active_default_idempotently(tmp_path):
    spec = importlib.util.spec_from_file_location("mig81", MIGRATION)
    mig = importlib.util.module_from_spec(spec); spec.loader.exec_module(mig)
    assert (mig.revision, mig.down_revision) == ("20261128_81", "20261128_80")
    engine = sa.create_engine(f"sqlite:///{tmp_path}/m.db")
    with engine.begin() as conn:
        conn.execute(sa.text("CREATE TABLE commerce_group_members (id VARCHAR(36) PRIMARY KEY, tenant_id INTEGER, user_id INTEGER, group_id VARCHAR(36))"))
        conn.execute(sa.text("INSERT INTO commerce_group_members VALUES ('m1', 1, 7, 'g1')"))
    for _ in range(2):
        with engine.begin() as conn, Operations.context(MigrationContext.configure(conn)):
            mig.upgrade()
    with engine.connect() as conn:
        assert conn.execute(sa.text("SELECT id, group_id, status FROM commerce_group_members")).all() == [("m1", "g1", "active")]
    with pytest.raises(RuntimeError):
        mig.downgrade()


def test_alembic_has_a_single_head():
    from alembic.config import Config
    from alembic.script import ScriptDirectory
    root = Path(__file__).resolve().parents[1]
    cfg = Config()
    cfg.set_main_option("script_location", str(root / "alembic"))
    assert ScriptDirectory.from_config(cfg).get_heads() == ["20261128_81"]
