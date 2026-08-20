"""Add tenant-first indexes for production read and reconciliation paths.

Revision ID: 20260820_09
Revises: 20260819_08
"""
import sqlalchemy as sa
from alembic import op

revision = "20260820_09"
down_revision = "20260819_08"
branch_labels = None
depends_on = None

INDEXES = (
    ("ix_offers_tenant_search", "offers", ["tenant_id", "service_type", "status", "valid_until", "amount"]),
    ("ix_reservations_tenant_user_created", "reservations", ["tenant_id", "user_id", "created_at"]),
    ("ix_payment_reconciliation", "payment_intents", ["tenant_id", "reservation_id", "status"]),
    ("ix_trip_timeline", "trip_events", ["tenant_id", "trip_id", "visibility", "created_at"]),
)


def upgrade() -> None:
    bind = op.get_bind(); inspector = sa.inspect(bind)
    for name, table, columns in INDEXES:
        if name not in {item["name"] for item in inspector.get_indexes(table)}:
            op.create_index(name, table, columns)


def downgrade() -> None:
    pass
