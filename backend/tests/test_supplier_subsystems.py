"""PR-6: supplier web-service connection fields, one creation service behind both endpoints, idempotent Mahan/Niira rows,
and migration 20261128_80 (additive columns, re-runnable, downgrade refused). TEST FIXTURES ONLY: synthetic names."""
import importlib.util
import uuid
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations

MIGRATION = Path(__file__).resolve().parents[1] / "alembic" / "versions" / "20261128_80_supplier_subsystems.py"


def _h(client, email):
    return {"Authorization": "Bearer " + client.post("/auth/dev-login", json={"email": email}).json()["access_token"]}


def test_both_endpoints_store_connection_fields_and_reject_duplicate_subsystem(client):
    admin = _h(client, "tenant-admin@aftab.test")
    ref = "T" + uuid.uuid4().hex[:6]
    a = client.post("/inventory/suppliers", headers=admin, json={"name": "زیرسیستم آزمون " + ref, "supplier_type": "airline",
                                                                 "provider_key": "nira", "connection_mode": "shared", "external_ref": ref})
    assert a.status_code == 201 and (a.json()["provider_key"], a.json()["connection_mode"], a.json()["external_ref"]) == ("nira", "shared", ref)
    dup = client.post("/admin/partners/suppliers", headers=admin, json={"display_name": "نام دیگر " + ref, "supplier_type": "flight",
                                                                        "provider_key": "nira", "external_ref": ref})
    assert dup.status_code == 409
    b = client.post("/admin/partners/suppliers", headers=admin, json={"display_name": "اختصاصی " + ref, "supplier_type": "flight",
                                                                      "provider_key": "nira", "connection_mode": "dedicated", "external_ref": ref + "X"})
    assert b.status_code == 201 and b.json()["connection_mode"] == "dedicated"
    assert client.post("/admin/partners/suppliers", headers=admin, json={"display_name": "اختصاصی " + ref, "supplier_type": "flight"}).status_code == 409
    assert client.post("/inventory/suppliers", headers=admin, json={"name": "بد", "connection_mode": "half"}).status_code == 422
    items = {i["id"]: i for i in client.get("/inventory/suppliers", headers=admin).json()["items"]}
    assert items[a.json()["id"]]["external_ref"] == ref
    listed = {s["id"]: s for s in client.get("/admin/partners", headers=admin).json()["suppliers"]}
    assert listed[b.json()["id"]]["provider_key"] == "nira"


def test_system_connections_are_idempotent_and_admin_only(client):
    admin = _h(client, "tenant-admin@aftab.test")
    assert client.post("/admin/partners/suppliers/system-connections", headers=_h(client, "employee@aftab.test"), json={}).status_code == 403
    first = client.post("/admin/partners/suppliers/system-connections", headers=admin, json={})
    assert first.status_code == 200
    again = client.post("/admin/partners/suppliers/system-connections", headers=admin, json={"connection_mode": "shared"}).json()["items"]
    assert [i["provider_key"] for i in again] == ["mahan", "nira"] and not any(i["created"] for i in again)
    assert [i["id"] for i in again] == [i["id"] for i in first.json()["items"]]
    assert all(i["connection_mode"] == "dedicated" for i in again if i["id"] in {x["id"] for x in first.json()["items"] if x["created"]})


def _load():
    spec = importlib.util.spec_from_file_location("mig80", MIGRATION)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


def test_migration_80_adds_nullable_columns_idempotently(tmp_path):
    mig = _load()
    assert (mig.revision, mig.down_revision) == ("20261128_80", "20261128_79")
    engine = sa.create_engine(f"sqlite:///{tmp_path}/m.db")
    with engine.begin() as conn:
        conn.execute(sa.text("CREATE TABLE suppliers (id VARCHAR(36) PRIMARY KEY, tenant_id INTEGER, display_name VARCHAR(180))"))
        conn.execute(sa.text("INSERT INTO suppliers VALUES ('s1', 1, 'old')"))
    for _ in range(2):
        with engine.begin() as conn, Operations.context(MigrationContext.configure(conn)):
            mig.upgrade()
    with engine.connect() as conn:
        cols = {c["name"]: c for c in sa.inspect(conn).get_columns("suppliers")}
        assert all(cols[c]["nullable"] for c in ("provider_key", "connection_mode", "external_ref"))
        assert conn.execute(sa.text("SELECT display_name, provider_key FROM suppliers")).all() == [("old", None)]
    with pytest.raises(RuntimeError):
        mig.downgrade()
