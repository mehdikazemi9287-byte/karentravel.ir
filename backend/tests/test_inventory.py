import uuid
from datetime import date, timedelta


def _h(client, email):
    return {"Authorization": f"Bearer {client.post('/auth/dev-login', json={'email': email}).json()['access_token']}"}


def test_charter_series_publishes_bookable_flights(client):
    admin = _h(client, "platform-admin@aftab.test")
    created = client.post("/inventory/suppliers", json={"name": "چارتر کننده آزمون", "supplier_type": "charterer"}, headers=admin)
    assert created.status_code == 201
    sup = [created.json()]
    import random, string
    o, d = "Q" + "".join(random.choices(string.ascii_uppercase, k=2)), "Z" + "".join(random.choices(string.ascii_uppercase, k=2))
    route = client.post("/inventory/routes", json={"origin": o, "destination": d, "origin_city": "مبدأ آزمون", "destination_city": "مقصد آزمون"}, headers=admin)
    assert route.status_code == 201, route.text
    assert client.post("/inventory/routes", json={"origin": o, "destination": d}, headers=admin).status_code == 409
    start = date.today() + timedelta(days=3)
    body = {"route_id": route.json()["id"], "supplier_id": sup[0]["id"], "airline_code": "ep", "airline_name": "آسمان", "flight_number": "3801",
            "date_from": start.isoformat(), "date_to": (start + timedelta(days=6)).isoformat(),
            "schedule": {str(k): {"time": "08:30", "duration": 70} for k in range(7)}, "capacity": 40,
            "adult_fare": 30_000_000, "child_fare": 30_000_000, "infant_fare": 3_000_000}
    series = client.post("/inventory/flight-series", json=body, headers=admin)
    assert series.status_code == 201, series.text
    sid = series.json()["id"]
    gen = client.post(f"/inventory/flight-series/{sid}/generate", headers=admin).json()
    assert gen["created"] == 7
    assert client.post(f"/inventory/flight-series/{sid}/generate", headers=admin).json() == {"created": 0, "updated": 7, "skipped_past": 0}
    flights = client.get("/inventory/flights", params={"series_id": sid}, headers=admin).json()
    assert len(flights["items"]) == 7 and flights["totals"]["capacity"] == 280 and flights["items"][0]["flight"] == "EP3801"
    first = flights["items"][0]
    # it is a normal bookable offer
    emp = _h(client, "employee@aftab.test")
    detail = client.get(f"/offers/{first['offer_id']}", headers=emp)
    assert detail.status_code == 200 and detail.json()["amount"] == 30_000_000
    # capacity change and closing
    upd = client.put(f"/inventory/flights/{first['id']}", json={"capacity": 10}, headers=admin).json()
    assert upd["capacity"] == 10 and upd["remaining"] == 10
    closed = client.put(f"/inventory/flights/{first['id']}", json={"status": "closed"}, headers=admin).json()
    assert closed["status"] == "closed" and closed["sale_open"] is False
    man = client.get(f"/inventory/flights/{first['id']}/manifest", headers=admin).json()
    assert man["passengers"] == [] and man["seats_booked"] == 0
    assert client.post("/inventory/flight-series", json={**body, "schedule": {}}, headers=admin).status_code == 422
    assert client.get("/inventory/flights", headers=emp).status_code == 403


def test_contract_template_and_sales_report(client):
    admin = _h(client, "platform-admin@aftab.test")
    t = client.post("/inventory/contract-templates", json={"service_type": "any", "title": "قرارداد عمومی خدمات سفر",
                                                           "body": "خریدار {{customer_name}} با کد رزرو {{booking_reference}} خدمت {{service}} را به مبلغ {{amount}} {{currency}} خرید. <script>"}, headers=admin)
    assert t.status_code == 201
    upd = client.put(f"/inventory/contract-templates/{t.json()['id']}", json={**{k: t.json()[k] for k in ("service_type", "title", "status")}, "body": t.json()["body"] + " نسخه دوم"}, headers=admin)
    assert upd.json()["version"] == 2
    rep = client.get("/commerce/reports/sales", headers=admin).json()
    assert "by_service" in rep and isinstance(rep["items"], list)
    if rep["items"]:
        c = client.get(f"/reservations/{rep['items'][0]['id']}/contract", headers=admin)
        assert c.status_code == 200 and "&lt;script&gt;" in c.json()["html"] and "{{" not in c.json()["html"]
    # deactivate so other tests are unaffected
    client.put(f"/inventory/contract-templates/{t.json()['id']}", json={**{k: upd.json()[k] for k in ("service_type", "title", "body")}, "status": "disabled"}, headers=admin)
