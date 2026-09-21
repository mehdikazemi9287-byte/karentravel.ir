"""Add the V3.1 supplier lifecycle status without changing legacy status."""
from alembic import op
import sqlalchemy as sa

revision = "20260912_26"
down_revision = "20260912_25"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_cols = {c["name"] for c in inspector.get_columns("suppliers")}
    if "lifecycle_status" not in existing_cols:
        op.add_column("suppliers", sa.Column("lifecycle_status", sa.String(length=32), nullable=False, server_default="UNSELECTED"))
    existing_indexes = {i["name"] for i in inspector.get_indexes("suppliers")}
    if "ix_suppliers_lifecycle_status" not in existing_indexes:
        op.create_index("ix_suppliers_lifecycle_status", "suppliers", ["lifecycle_status"])


def downgrade() -> None:
    op.drop_index("ix_suppliers_lifecycle_status", table_name="suppliers")
    op.drop_column("suppliers", "lifecycle_status")
