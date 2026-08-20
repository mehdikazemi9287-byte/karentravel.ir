import uuid

from sqlalchemy import select

from app import operations as models
from app.main import SessionLocal, User


def login(client, email):
    response = client.post("/auth/dev-login", json={"email": email})
    assert response.status_code == 200
    return response.json()


def auth(token):
    return {"Authorization": f"Bearer {token}"}


def test_saved_trip_wishlist_basket_are_owned_idempotent_and_audited(client):
    aftab = login(client, "employee@aftab.test"); faraz = login(client, "employee@faraz.test")
    suffix = uuid.uuid4().hex
    payload = {"title": "سفر شیراز", "command_id": f"trip-{suffix}"}
    created = client.post("/saved-trips", headers=auth(aftab["access_token"]), json=payload)
    replay = client.post("/saved-trips", headers=auth(aftab["access_token"]), json=payload)
    assert created.status_code == 201 and replay.json()["id"] == created.json()["id"]
    trip_id = created.json()["id"]
    added = client.post(f"/saved-trips/{trip_id}/items", headers=auth(aftab["access_token"]), json={"service_type": "hotel", "source_reference": "hotel:shiraz:1", "state": "wishlist", "command_id": f"add-{suffix}"})
    assert added.status_code == 201 and added.json()["items"][0]["state"] == "wishlist"
    item_id = added.json()["items"][0]["id"]
    moved = client.put(f"/saved-trips/{trip_id}/items/{item_id}", headers=auth(aftab["access_token"]), json={"state": "basket", "command_id": f"move-{suffix}"})
    replay_move = client.put(f"/saved-trips/{trip_id}/items/{item_id}", headers=auth(aftab["access_token"]), json={"state": "basket", "command_id": f"move-{suffix}"})
    assert moved.json()["items"][0]["state"] == "basket" and replay_move.json() == moved.json()
    assert client.put(f"/saved-trips/{trip_id}/items/{item_id}", headers=auth(faraz["access_token"]), json={"state": "wishlist", "command_id": f"cross-{suffix}"}).status_code == 404
    removed = client.request("DELETE", f"/saved-trips/{trip_id}/items/{item_id}", headers=auth(aftab["access_token"]), json={"command_id": f"remove-{suffix}"})
    assert removed.status_code == 200 and removed.json()["items"] == []
    assert client.get("/me/saved-trips", headers=auth(faraz["access_token"])).json() == []


def test_verified_review_is_server_derived_and_supplier_cannot_rewrite_it(client):
    employee = login(client, "employee@aftab.test"); supplier_user = login(client, "supplier@aftab.test"); backoffice = login(client, "backoffice@aftab.test"); faraz = login(client, "employee@faraz.test")
    suffix = uuid.uuid4().hex
    unverified = client.post("/reviews", headers=auth(employee["access_token"]), json={"rating": 4, "title": "اقامت خوب", "body": "متن معتبر تجربه کاربر برای ثبت بررسی", "service_type": "hotel", "service_reference": "hotel:1", "verified_booking": True, "command_id": f"review-forge-{suffix}"})
    assert unverified.status_code == 422
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.email == "employee@aftab.test"))
        reservation = models.Reservation(tenant_id=user.tenant_id, user_id=user.id, service_type="hotel", status="issued", provider_reference="provider-booking-verified", price_snapshot_json='{"total_amount":1000,"currency":"IRR"}', policy_at_booking_json="{}", current_policy_json="{}")
        db.add(reservation); db.commit(); reservation_id = reservation.id
    payload = {"rating": 5, "title": "رزرو تأییدشده", "body": "تجربه واقعی رزرو صادرشده و اقامت مناسب", "service_type": "hotel", "service_reference": "hotel:verified", "reservation_id": reservation_id, "command_id": f"review-{suffix}"}
    review = client.post("/reviews", headers=auth(employee["access_token"]), json=payload)
    assert review.status_code == 201 and review.json()["verified_booking"] is True
    review_id = review.json()["id"]
    assert client.put(f"/reviews/{review_id}/moderation", headers=auth(employee["access_token"]), json={"state": "approved", "reason": "مجاز نیست"}).status_code == 403
    assert client.put(f"/reviews/{review_id}/moderation", headers=auth(faraz["access_token"]), json={"state": "approved", "reason": "tenant دیگر"}).status_code == 403
    assert client.put(f"/reviews/{review_id}/moderation", headers=auth(backoffice["access_token"]), json={"state": "approved", "reason": "بررسی انسانی"}).status_code == 200
    supplier = client.post("/supplier/onboarding", headers={**auth(supplier_user["access_token"]), "Idempotency-Key": f"supplier-{suffix}"}, json={"supplier_type": "hotel", "display_name": "هتل پاسخگو"}).json()
    response = client.post(f"/reviews/{review_id}/supplier-response", headers=auth(supplier_user["access_token"]), json={"supplier_id": supplier["id"], "body": "از بازخورد شما سپاسگزاریم", "command_id": f"response-{suffix}"})
    assert response.status_code == 201 and response.json()["body"] == payload["body"] and response.json()["supplier_response"]["body"] != payload["body"]
    assert client.get("/me/reviews", headers=auth(faraz["access_token"])).json() == []


def test_destination_catalog_and_editable_itinerary_are_tenant_scoped(client):
    employee = login(client, "employee@aftab.test"); faraz = login(client, "employee@faraz.test"); backoffice = login(client, "backoffice@aftab.test")
    suffix = uuid.uuid4().hex
    destination = client.post("/destinations", headers=auth(backoffice["access_token"]), json={"kind": "city", "name_fa": "شیراز", "name_en": "Shiraz", "slug": f"shiraz-{suffix}", "latitude": 29.59, "longitude": 52.58, "description": "مقصد تاریخی", "seasonality": ["spring"], "categories": ["historical"], "highlights": ["حافظیه"], "nearby_slugs": []})
    assert destination.status_code == 201
    destination_id = destination.json()["id"]
    assert client.get(f"/destinations/{destination.json()['slug']}", headers=auth(employee["access_token"])).status_code == 200
    assert client.get(f"/destinations/{destination.json()['slug']}", headers=auth(faraz["access_token"])).status_code == 404
    created = client.post("/itineraries", headers=auth(employee["access_token"]), json={"title": "سه روز شیراز", "destination_id": destination_id, "budget_amount": 30000000, "command_id": f"itinerary-{suffix}"})
    replay = client.post("/itineraries", headers=auth(employee["access_token"]), json={"title": "سه روز شیراز", "destination_id": destination_id, "budget_amount": 30000000, "command_id": f"itinerary-{suffix}"})
    assert created.status_code == 201 and replay.json()["id"] == created.json()["id"]
    itinerary_id = created.json()["id"]
    item = client.post(f"/itineraries/{itinerary_id}/items", headers=auth(employee["access_token"]), json={"service_type": "attraction", "title": "بازدید حافظیه", "day_number": 1, "position": 1, "command_id": f"item-{suffix}"})
    assert item.status_code == 201 and item.json()["items"][0]["availability_state"] == "needs_live_availability_check"
    item_id = item.json()["items"][0]["id"]
    assert client.put(f"/itineraries/{itinerary_id}", headers=auth(employee["access_token"]), json={"title": "برنامه نهایی شیراز", "budget_amount": 32000000, "status": "saved", "command_id": f"update-{suffix}"}).json()["status"] == "saved"
    duplicate = client.post(f"/itineraries/{itinerary_id}/duplicate", headers=auth(employee["access_token"]), json={"command_id": f"duplicate-{suffix}"})
    assert duplicate.status_code == 201 and len(duplicate.json()["items"]) == 1
    assert client.post(f"/itineraries/{itinerary_id}/duplicate", headers=auth(faraz["access_token"]), json={"command_id": f"cross-{suffix}"}).status_code == 404
    removed = client.request("DELETE", f"/itineraries/{itinerary_id}/items/{item_id}", headers=auth(employee["access_token"]), json={"command_id": f"remove-item-{suffix}"})
    assert removed.status_code == 200 and removed.json()["items"] == []
