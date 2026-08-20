import os
os.environ["DATABASE_URL"] = "sqlite:///./test_karenseir.db"
os.environ["ENVIRONMENT"] = "development"
from fastapi.testclient import TestClient
from app.main import app
client = TestClient(app)
def login(email):
    return client.post("/auth/dev-login", json={"email":email}).json()["access_token"]
def auth(token, idempotency_key=None):
    headers = {"Authorization":f"Bearer {token}"}
    if idempotency_key: headers["Idempotency-Key"] = idempotency_key
    return headers
def test_health_and_search():
    assert client.get("/health").json()["status"] == "ok"
    assert client.get("/ready").json()["database"] == "ok"
    assert len(client.get("/hotels").json()) == 3
    metrics = client.get("/metrics")
    assert metrics.status_code == 200
    assert "karenseir_http_requests_total" in metrics.text

def test_booking_cors_preflight_allows_idempotency_header():
    response = client.options("/bookings", headers={
        "Origin":"http://localhost:3000",
        "Access-Control-Request-Method":"POST",
        "Access-Control-Request-Headers":"authorization,content-type,idempotency-key",
    })
    assert response.status_code == 200
    assert "idempotency-key" in response.headers["access-control-allow-headers"].lower()
    put_response = client.options("/me/notification-preferences", headers={
        "Origin":"http://localhost:3000",
        "Access-Control-Request-Method":"PUT",
        "Access-Control-Request-Headers":"authorization,content-type",
    })
    assert put_response.status_code == 200
    assert "PUT" in put_response.headers["access-control-allow-methods"]

def test_health_endpoints_are_not_rate_limited():
    for _ in range(12):
        assert client.get("/health").status_code == 200
def test_booking_approval_and_tenant_isolation():
    employee = login("employee@aftab.test")
    booking = client.post("/bookings", json={"hotel_id":1,"nights":2}, headers=auth(employee, "booking-test-001"))
    assert booking.status_code == 201
    booking_id = booking.json()["id"]
    faraz = login("employee@faraz.test")
    assert client.get("/me/dashboard", headers=auth(faraz)).json()["bookings"] == []
    welfare = login("welfare@aftab.test")
    assert client.post(f"/bookings/{booking_id}/approval", json={"decision":"approve"}, headers=auth(welfare)).json()["status"] == "approved"
    assert client.post(f"/bookings/{booking_id}/approval", json={"decision":"approve"}, headers=auth(welfare)).status_code == 409

def test_booking_creation_is_idempotent_and_rejects_key_reuse():
    employee = login("employee@aftab.test")
    headers = auth(employee, "booking-retry-001")
    first = client.post("/bookings", json={"hotel_id":2,"nights":2}, headers=headers)
    second = client.post("/bookings", json={"hotel_id":2,"nights":2}, headers=headers)
    conflict = client.post("/bookings", json={"hotel_id":2,"nights":3}, headers=headers)
    assert first.status_code == 201
    assert second.status_code == 201
    assert second.json() == first.json()
    assert conflict.status_code == 409

def test_booking_creation_requires_idempotency_key():
    employee = login("employee@aftab.test")
    response = client.post("/bookings", json={"hotel_id":3,"nights":1}, headers=auth(employee))
    assert response.status_code == 422
