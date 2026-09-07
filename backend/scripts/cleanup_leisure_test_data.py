"""Deactivates every [TEST]-marked leisure row created by
seed_leisure_test_data.py on the karenseir-public tenant: archived/cancelled
status, removed from search and no longer bookable. This follows the same
convention as the rest of the codebase (statuses, not hard deletes) so any
Reservation/PriceCheck/Ticket a verification pass created against this test
data keeps a consistent, non-orphaned audit trail. Safe to re-run."""
from sqlalchemy import select

from app.database import set_tenant_context
from app.main import SessionLocal, Tenant
from app.operations import ExperienceProduct, LeisureSession, LeisureTicketType, Offer, Place, Supplier

PUBLIC_TENANT_SLUG = "karenseir-public"
MARKER = "[TEST]"


def main():
    with SessionLocal() as db:
        tenant = db.scalar(select(Tenant).where(Tenant.slug == PUBLIC_TENANT_SLUG))
        set_tenant_context(db, tenant.id)
        suppliers = db.scalars(select(Supplier).where(Supplier.tenant_id == tenant.id, Supplier.display_name.like(f"{MARKER}%"))).all()
        supplier_ids = [row.id for row in suppliers]
        if not supplier_ids:
            print("nothing to clean up")
            return
        places = db.scalars(select(Place).where(Place.tenant_id == tenant.id, Place.supplier_id.in_(supplier_ids))).all()
        place_ids = [row.id for row in places]
        products = db.scalars(select(ExperienceProduct).where(ExperienceProduct.tenant_id == tenant.id, ExperienceProduct.place_id.in_(place_ids))).all() if place_ids else []
        product_ids = [row.id for row in products]
        sessions = db.scalars(select(LeisureSession).where(LeisureSession.tenant_id == tenant.id, LeisureSession.experience_product_id.in_(product_ids))).all() if product_ids else []
        offer_ids = [row.offer_id for row in sessions if row.offer_id]
        ticket_types = db.scalars(select(LeisureTicketType).where(LeisureTicketType.tenant_id == tenant.id, LeisureTicketType.experience_product_id.in_(product_ids))).all() if product_ids else []
        offers = db.scalars(select(Offer).where(Offer.tenant_id == tenant.id, Offer.id.in_(offer_ids))).all() if offer_ids else []

        for row in offers:
            row.status = "archived"; row.available_units = 0
        for row in sessions:
            row.status = "cancelled"; row.capacity_available = 0
        for row in ticket_types:
            row.active = False
        for row in products:
            row.status = "archived"
        for row in places:
            row.status = "archived"
        for row in suppliers:
            row.status = "inactive"
        db.commit()
        print("archived:", {"offers": len(offers), "sessions": len(sessions), "ticket_types": len(ticket_types), "products": len(products), "places": len(places), "suppliers": len(suppliers)})


if __name__ == "__main__":
    main()
