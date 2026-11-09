"""Test helpers for the maker-checker funding flow (app/approvals.py, H-1)."""
import uuid

from sqlalchemy import select

from app.main import SessionLocal, User


def approve(client, maker_response, checker_headers) -> dict:
    """Approve the pending request returned by a maker endpoint; returns its executed output."""
    body = maker_response.json() if hasattr(maker_response, "json") else maker_response
    assert body.get("status") == "pending_approval", body
    response = client.post(f"/maker-checker/requests/{body['approval_request']['id']}/approve", json={}, headers=checker_headers)
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "executed"
    return response.json()


def ensure_user(like_email: str, role: str, label: str) -> str:
    """A second user in the same tenant as `like_email` (e.g. a second finance/platform checker)."""
    with SessionLocal() as db:
        base = db.scalar(select(User).where(User.email == like_email))
        email = f"{label}-{base.tenant_id}@checker.test"
        if db.scalar(select(User.id).where(User.email == email)) is None:
            db.add(User(tenant_id=base.tenant_id, email=email, name=f"[TEST] {label}", role=role))
            db.commit()
        return email


def command_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex}"
