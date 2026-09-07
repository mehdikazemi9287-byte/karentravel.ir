"""[TEST] leisure demo data for end-to-end verification on the public catalog
tenant (karenseir-public). Every row this script creates is prefixed with
"[TEST]" in its human-facing title/name so it is never mistaken for a real
commercial listing. Run cleanup_leisure_test_data.py to remove it.
"""
import json
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.database import set_tenant_context
from app.main import SessionLocal, Tenant, _sync_leisure_session_offer
from app.operations import ExperienceProduct, LeisureSession, LeisureTicketType, Place, Supplier

PUBLIC_TENANT_SLUG = "karenseir-public"
MARKER = "[TEST]"

CATALOG = [
    {
        "supplier_type": "pool_sport", "supplier_name": f"{MARKER} مجموعه آبی نمونه",
        "place": {"name": f"{MARKER} استخر و مجموعه ورزشی نمونه", "slug": "test-pool-sport-demo", "place_type": "pool_sport", "city": "شیراز", "address": "بلوار نمونه", "amenities": ["پارکینگ", "رختکن"]},
        "product": {"service_type": "pool_sport", "title": f"{MARKER} سانس استخر روباز", "booking_mode": "SESSION_BASED", "description": "سانس دو ساعته استخر با بلیت بزرگ‌سال و کودک مجزا (داده آزمایشی)."},
        "ticket_types": [{"code": "adult", "label": "بزرگ‌سال", "price": 450_000}, {"code": "child", "label": "کودک", "price": 200_000, "max_age": 12}],
        "capacity": 20,
    },
    {
        "supplier_type": "restaurant", "supplier_name": f"{MARKER} رستوران نمونه",
        "place": {"name": f"{MARKER} رستوران سنتی نمونه", "slug": "test-restaurant-demo", "place_type": "restaurant", "city": "شیراز", "address": "خیابان نمونه"},
        "product": {"service_type": "restaurant", "title": f"{MARKER} رزرو میز رستوران", "booking_mode": "TABLE_RESERVATION", "description": "رزرو میز برای شام (داده آزمایشی)."},
        "ticket_types": [{"code": "generic", "label": "نفر", "price": 350_000}],
        "capacity": 40,
    },
    {
        "supplier_type": "attraction", "supplier_name": f"{MARKER} مرکز گردشگری نمونه",
        "place": {"name": f"{MARKER} جاذبه گردشگری نمونه", "slug": "test-attraction-demo", "place_type": "attraction", "city": "شیراز", "address": "میدان نمونه"},
        "product": {"service_type": "attraction", "title": f"{MARKER} بلیت ورود جاذبه", "booking_mode": "TIMED_ENTRY", "description": "بلیت ورود زمان‌بندی‌شده (داده آزمایشی)."},
        "ticket_types": [{"code": "adult", "label": "بزرگ‌سال", "price": 250_000}, {"code": "child", "label": "کودک", "price": 100_000, "max_age": 10}],
        "capacity": 100,
    },
    {
        "supplier_type": "event_hall", "supplier_name": f"{MARKER} تالار رویداد نمونه",
        "place": {"name": f"{MARKER} تالار رویداد نمونه", "slug": "test-event-hall-demo", "place_type": "event_hall", "city": "شیراز", "address": "بلوار نمونه"},
        "product": {"service_type": "event_hall", "title": f"{MARKER} بلیت رویداد نمونه", "booking_mode": "EVENT_TICKET", "description": "بلیت ورود به رویداد نمونه (داده آزمایشی)."},
        "ticket_types": [{"code": "generic", "label": "بلیت ورود", "price": 300_000}, {"code": "vip", "label": "بلیت ویژه", "price": 700_000}],
        "capacity": 60,
    },
]


def main():
    with SessionLocal() as db:
        tenant = db.scalar(select(Tenant).where(Tenant.slug == PUBLIC_TENANT_SLUG))
        set_tenant_context(db, tenant.id)
        created_supplier_ids = []
        for entry in CATALOG:
            supplier = Supplier(tenant_id=tenant.id, supplier_type=entry["supplier_type"], display_name=entry["supplier_name"], status="active")
            db.add(supplier); db.flush()
            created_supplier_ids.append(supplier.id)

            place_data = entry["place"]
            place = Place(tenant_id=tenant.id, supplier_id=supplier.id, name=place_data["name"], slug=place_data["slug"], place_type=place_data["place_type"], city=place_data["city"], address=place_data.get("address"), amenities_json=json.dumps(place_data.get("amenities", [])), status="published")
            db.add(place); db.flush()

            product_data = entry["product"]
            product = ExperienceProduct(tenant_id=tenant.id, place_id=place.id, supplier_id=supplier.id, service_type=product_data["service_type"], title=product_data["title"], description=product_data.get("description", ""), booking_mode=product_data["booking_mode"], status="published")
            db.add(product); db.flush()

            ticket_types = []
            for ticket_data in entry["ticket_types"]:
                ticket_type = LeisureTicketType(tenant_id=tenant.id, experience_product_id=product.id, code=ticket_data["code"], label=ticket_data["label"], price=ticket_data["price"], max_age=ticket_data.get("max_age"), active=True)
                db.add(ticket_type); ticket_types.append(ticket_type)
            db.flush()

            now = datetime.now(timezone.utc)
            for offset_days in (2, 5, 9):
                starts_at = (now + timedelta(days=offset_days)).replace(minute=0, second=0, microsecond=0)
                session_row = LeisureSession(tenant_id=tenant.id, experience_product_id=product.id, starts_at=starts_at, ends_at=starts_at + timedelta(hours=2), capacity_total=entry["capacity"], capacity_available=entry["capacity"])
                db.add(session_row); db.flush()
                _sync_leisure_session_offer(db, tenant_id=tenant.id, product=product, place=place, session=session_row)

            print(f"seeded {entry['supplier_type']}: supplier={supplier.id} place={place.id} product={product.id}")
        db.commit()
        print("SUPPLIER_IDS=" + ",".join(created_supplier_ids))


if __name__ == "__main__":
    main()
