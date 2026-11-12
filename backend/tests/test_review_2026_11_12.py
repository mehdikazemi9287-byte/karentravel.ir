"""Review 2026-11-12: KT-1 voucher reissue object scope, KT-2 ledger command_id replay with a different body."""
import uuid

import pytest
from sqlalchemy import select

from app.main import SessionLocal, User
from app import operations as m
from test_credit_fulfilment_sandbox_d1_d6 import auth, fulfil, funded_reservation, login


def _voucher(rid):
    with SessionLocal() as db:
        return db.scalar(select(m.Voucher).where(m.Voucher.reservation_id == rid))


def test_kt1_unrelated_supplier_cannot_reissue_voucher_and_nothing_changes(client):
    ctx = funded_reservation(client)
    rid = ctx["reservation"]["id"]
    supplier = login(client, "supplier@aftab.test")
    assert fulfil(client, supplier, rid, f"kt1-fulfil-{ctx['suffix']}").status_code == 200
    before = _voucher(rid)
    email = f"kt1-stranger-{uuid.uuid4().hex[:8]}@aftab.test"
    with SessionLocal() as db:   # same tenant, supplier role, but no membership of this booking's supplier
        db.add(User(tenant_id=ctx["tenant_id"], email=email, name="تأمین‌کننده نامرتبط", role="supplier")); db.commit()
    stranger = login(client, email)
    body = {"command_id": f"kt1-reissue-{ctx['suffix']}", "document_reference": "document://kt1-forged", "reason": "test"}
    response = client.post(f"/reservations/{rid}/voucher/reissue", headers=auth(stranger), json=body)
    assert response.status_code == 403, response.text
    after = _voucher(rid)
    assert (after.revision, after.document_reference) == (before.revision, before.document_reference)
    # the assigned supplier still can; the same command with another document is a conflict, not a silent replay
    ok = client.post(f"/reservations/{rid}/voucher/reissue", headers=auth(supplier), json={**body, "document_reference": "document://kt1-v2"})
    assert ok.status_code == 200 and ok.json()["revision"] == before.revision + 1
    again = client.post(f"/reservations/{rid}/voucher/reissue", headers=auth(supplier), json={**body, "document_reference": "document://kt1-v3"})
    assert again.status_code == 409


def test_kt2_same_command_id_with_different_body_is_a_conflict():
    with SessionLocal() as db:
        cmd = f"kt2-{uuid.uuid4().hex}"
        first = m.post_ledger(db, tenant_id=1, wallet_id="w-a", command_id=cmd, entry_type="allocate", amount=1000)
        assert m.post_ledger(db, tenant_id=1, wallet_id="w-a", command_id=cmd, entry_type="allocate", amount=1000) is first
        for change in ({"wallet_id": "w-b"}, {"amount": 2000}, {"entry_type": "reserve"}):
            with pytest.raises(m.LedgerCommandConflict):
                m.post_ledger(db, tenant_id=1, **{"wallet_id": "w-a", "command_id": cmd, "entry_type": "allocate", "amount": 1000, **change})
        db.rollback()
