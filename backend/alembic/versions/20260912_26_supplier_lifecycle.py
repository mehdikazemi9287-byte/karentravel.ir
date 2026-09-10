"""Add the V3.1 supplier lifecycle status without changing legacy status."""
from alembic import op
import sqlalchemy as sa

revision = "20260912_26"
down_revision = "20260912_25"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("suppliers", sa.Column("lifecycle_status", sa.String(length=32), nullable=False, server_default="UNSELECTED"))
    op.create_index("ix_suppliers_lifecycle_status", "suppliers", ["lifecycle_status"])


def downgrade() -> None:
    op.drop_index("ix_suppliers_lifecycle_status", table_name="suppliers")
    op.drop_column("suppliers", "lifecycle_status")
