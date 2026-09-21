"""Add explicit tenant-scoped supplier portal ownership."""
from alembic import op
import sqlalchemy as sa

revision = "20260913_27"
down_revision = "20260912_26"
branch_labels = None
depends_on = None

def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table("supplier_memberships"):
        op.create_table(
            "supplier_memberships",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id"), nullable=False),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("supplier_id", sa.String(length=36), sa.ForeignKey("suppliers.id"), nullable=False),
            sa.Column("role", sa.String(length=32), nullable=False, server_default="owner"),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.UniqueConstraint("tenant_id", "user_id", "supplier_id", name="uq_supplier_membership"),
        )
        inspector = sa.inspect(bind)
    existing_indexes = {i["name"] for i in inspector.get_indexes("supplier_memberships")}
    if "ix_supplier_memberships_user_id" not in existing_indexes:
        op.create_index("ix_supplier_memberships_user_id", "supplier_memberships", ["user_id"])
    if "ix_supplier_memberships_supplier_id" not in existing_indexes:
        op.create_index("ix_supplier_memberships_supplier_id", "supplier_memberships", ["supplier_id"])

def downgrade() -> None:
    op.drop_index("ix_supplier_memberships_supplier_id", table_name="supplier_memberships")
    op.drop_index("ix_supplier_memberships_user_id", table_name="supplier_memberships")
    op.drop_table("supplier_memberships")
