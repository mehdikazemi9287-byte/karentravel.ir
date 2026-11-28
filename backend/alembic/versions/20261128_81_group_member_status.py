"""Direct price-group membership status: active | disabled. Additive; existing rows become active (server_default).

A disabled membership is kept for history and ignored by pricing (commerce.user_group_id), so the user's
organization/agency link or the tenant's default group applies again. Nothing is deleted.
"""
from alembic import op
import sqlalchemy as sa

revision = "20261128_81"
down_revision = "20261128_80"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    name = "commerce_group_members"
    existing = {c["name"] for c in sa.inspect(bind).get_columns(name)}
    if "status" not in existing:
        op.add_column(name, sa.Column("status", sa.String(16), nullable=False, server_default="active"))


def downgrade():
    raise RuntimeError("Group membership status is retained")
