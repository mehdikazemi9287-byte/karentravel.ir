"""Persist V3.1 auditable price decomposition for bookings."""
from alembic import op
from app.operations import PriceBreakdown

revision = "20260912_25"
down_revision = "20260911_24"
branch_labels = None
depends_on = None


def upgrade() -> None:
    PriceBreakdown.__table__.create(op.get_bind(), checkfirst=True)


def downgrade() -> None:
    # Financial audit records are retained; rollback uses the prior image.
    pass
