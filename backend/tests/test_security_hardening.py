"""Regression tests for the 2026-10-31 security hardening pass."""
import os
import subprocess
import sys

import jwt
import pytest
from starlette.requests import Request

import app.main as m
import app.providers as providers_module


def auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def login(client, email: str) -> dict:
    response = client.post("/auth/dev-login", json={"email": email})
    assert response.status_code == 200
    return response.json()


def _request(headers: dict[str, str], ip: str = "203.0.113.7") -> Request:
    raw = [(k.lower().encode(), v.encode()) for k, v in headers.items()]
    return Request({"type": "http", "method": "GET", "path": "/x", "headers": raw, "client": (ip, 1234), "query_string": b""})


# ---- rate limiting cannot be bypassed with forged Authorization headers ----

def test_forged_authorization_header_does_not_create_new_rate_limit_bucket():
    a = m._rate_limit_identity(_request({"Authorization": "Bearer junk-1"}), "auth")
    b = m._rate_limit_identity(_request({"Authorization": "Bearer junk-2"}), "auth")
    c = m._rate_limit_identity(_request({"Authorization": "Bearer junk-3"}), "api")
    assert a == b == c == "ip:203.0.113.7"


def test_valid_token_buckets_by_user_not_header_text(client):
    token = login(client, "employee@aftab.test")["access_token"]
    claims = jwt.decode(token, options={"verify_signature": False})
    identity = m._rate_limit_identity(_request(auth(token)), "api")
    assert identity == f"user:{claims['tenant']}:{claims['sub']}"
    # login/OTP routes always bucket by IP, even with a valid token
    assert m._rate_limit_identity(_request(auth(token)), "auth") == "ip:203.0.113.7"


# ---- per-account OTP / SMS throttle ----

class CountingOTPAdapter:
    def __init__(self):
        self.calls = 0

    def execute(self, operation, payload, context):
        self.calls += 1
        return {"ok": True, "status": "accepted", "reference": "counting"}


def test_otp_resend_cooldown_blocks_sms_bombing(client, monkeypatch):
    adapter = CountingOTPAdapter()
    monkeypatch.setitem(providers_module.ADAPTERS, "otp", adapter)
    monkeypatch.setattr(m, "OTP_RESEND_COOLDOWN_SECONDS", 60)
    monkeypatch.setattr(m, "OTP_MAX_PER_HOUR", 5)
    body = {"tenant_slug": "aftab-bank", "identifier": "agency@aftab.test"}
    responses = [client.post("/auth/otp/request", json=body) for _ in range(4)]
    assert all(r.status_code == 202 and r.json()["status"] == "accepted" for r in responses)  # enumeration-safe
    assert adapter.calls == 1  # only the first request actually sends an SMS


def test_register_resend_cooldown(client, monkeypatch):
    adapter = CountingOTPAdapter()
    monkeypatch.setitem(providers_module.ADAPTERS, "otp", adapter)
    monkeypatch.setattr(m, "OTP_RESEND_COOLDOWN_SECONDS", 60)
    body = {"mobile": "09351112233", "name": "تست امنیت"}
    for _ in range(3):
        assert client.post("/auth/register/request", json=body).status_code == 202
    assert adapter.calls == 1


# ---- security headers ----

def test_api_security_headers(client):
    r = client.get("/health")
    assert r.headers["x-content-type-options"] == "nosniff"
    assert r.headers["x-frame-options"] == "DENY"
    assert r.headers["referrer-policy"] == "no-referrer"
    assert "frame-ancestors 'none'" in r.headers["content-security-policy"]
    r = client.post("/auth/refresh", json={"refresh_token": "x" * 40})
    assert r.headers["cache-control"] == "no-store"


def test_app_never_sends_hsts_nginx_owns_it(client, monkeypatch):
    # nginx (deploy/karenseir-https.sh) adds HSTS once; a second copy from the app would contradict its max-age.
    monkeypatch.setattr(m, "IS_PRODUCTION", True)
    r = client.get("/health", headers={"X-Forwarded-Proto": "https"})
    assert "strict-transport-security" not in r.headers


# ---- internal endpoints hidden in production ----

def test_metrics_and_version_hidden_in_production(client, monkeypatch):
    monkeypatch.setattr(m, "IS_PRODUCTION", True)
    monkeypatch.setattr(m, "METRICS_TOKEN", "s3cret-metrics-token-value")
    assert client.get("/metrics").status_code == 404
    assert client.get("/system/version").status_code == 404
    assert client.get("/metrics", headers={"X-Metrics-Token": "wrong"}).status_code == 404
    assert client.get("/metrics", headers={"X-Metrics-Token": "s3cret-metrics-token-value"}).status_code == 200


def _import_app_flags(env: dict[str, str]) -> str:
    code = "import app.main as m; print(m.ENVIRONMENT, m.app.docs_url, m.app.openapi_url)"
    full_env = {k: v for k, v in os.environ.items() if k != "ENVIRONMENT"}
    full_env.update(env)
    out = subprocess.run([sys.executable, "-c", code], cwd=os.path.dirname(os.path.dirname(__file__)), env=full_env, capture_output=True, text=True, timeout=120)
    assert out.returncode == 0, out.stderr[-2000:]
    return out.stdout.strip().splitlines()[-1]


def test_environment_defaults_to_production_and_hides_docs():
    assert _import_app_flags({}) == "production None None"


def test_docs_available_in_development_only():
    assert _import_app_flags({"ENVIRONMENT": "development"}) == "development /docs /openapi.json"


def test_dev_login_disabled_outside_development(client, monkeypatch):
    monkeypatch.setattr(m, "ENVIRONMENT", "production")
    assert client.post("/auth/dev-login", json={"email": "employee@aftab.test"}).status_code == 404


# ---- stored XSS via notification deep links ----

@pytest.mark.parametrize("link", ["javascript:alert(1)", "//evil.example/x", "https://evil.example", "/\\evil.example", " /trips", "data:text/html,x"])
def test_notification_template_rejects_unsafe_deep_links(client, link):
    admin = login(client, "org-admin@aftab.test")
    r = client.put("/admin/notification-templates", headers=auth(admin["access_token"]), json={
        "event_type": "payment_success", "channel": "web", "locale": "fa",
        "title_template": "t", "body_template": "b", "deep_link_template": link})
    assert r.status_code == 422


def test_notification_template_accepts_internal_link(client):
    admin = login(client, "org-admin@aftab.test")
    r = client.put("/admin/notification-templates", headers=auth(admin["access_token"]), json={
        "event_type": "payment_success", "channel": "web", "locale": "fa",
        "title_template": "t", "body_template": "b", "deep_link_template": "/trips/{trip_id}?tab=timeline"})
    assert r.status_code == 200


# ---- authorization on admin routes ----

def test_admin_routes_require_auth_and_role(client):
    assert client.get("/admin/notification-templates").status_code == 401
    assert client.get("/admin/notification-templates", headers={"Authorization": "Bearer forged.token.value"}).status_code == 401
    employee = login(client, "employee@aftab.test")
    assert client.get("/admin/notification-templates", headers=auth(employee["access_token"])).status_code == 403
    alg_none = jwt.encode({"sub": "1", "tenant": 1, "role": "platform_admin", "type": "access"}, key="", algorithm="none")
    assert client.get("/admin/users", headers=auth(alg_none)).status_code == 401
