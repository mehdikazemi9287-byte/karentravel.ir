"""Add tenant-isolated saved travel, review, destination and itinerary domains.

Revision ID: 20260820_11
Revises: 20260820_10
"""
import sqlalchemy as sa
from alembic import op
from app.operations import Destination, EditableItinerary, EditableItineraryItem, Review, ReviewSupplierResponse, SavedTrip, SavedTripItem

revision = "20260820_11"
down_revision = "20260820_10"
branch_labels = None
depends_on = None

TABLES = (SavedTrip.__table__, SavedTripItem.__table__, Review.__table__, ReviewSupplierResponse.__table__, Destination.__table__, EditableItinerary.__table__, EditableItineraryItem.__table__)
POLICY = "karenseir_tenant_isolation"


def upgrade() -> None:
    bind = op.get_bind()
    for table in TABLES:
        table.create(bind=bind, checkfirst=True)
    if bind.dialect.name == "postgresql":
        quote = bind.dialect.identifier_preparer.quote
        for table in TABLES:
            target = quote(table.name)
            op.execute(sa.text(f"ALTER TABLE {target} ENABLE ROW LEVEL SECURITY"))
            op.execute(sa.text(f"ALTER TABLE {target} FORCE ROW LEVEL SECURITY"))
            op.execute(sa.text(f"DROP POLICY IF EXISTS {POLICY} ON {target}"))
            op.execute(sa.text(f"CREATE POLICY {POLICY} ON {target} USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::integer) WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::integer)"))


def downgrade() -> None:
    bind = op.get_bind()
    for table in reversed(TABLES):
        table.drop(bind=bind, checkfirst=True)
