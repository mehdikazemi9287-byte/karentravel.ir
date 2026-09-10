"""Add internal ledger reconciliation workflow records."""
from alembic import op
import sqlalchemy as sa
from app.operations import ReconciliationRecord

revision = "20260911_24"
down_revision = "20260910_23"
branch_labels = None
depends_on = None


def upgrade() -> None:
    ReconciliationRecord.__table__.create(op.get_bind(), checkfirst=True)


def downgrade() -> None:
    # Preserve financial audit history; rollback uses the previous application image.
    pass
