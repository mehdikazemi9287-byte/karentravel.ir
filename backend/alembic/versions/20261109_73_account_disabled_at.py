"""users.disabled_at / tenants.disabled_at: reversible deactivation (demo seed data on production).

Additive and nullable: NULL = active, so every existing account keeps working.
A disabled user or a user of a disabled tenant cannot request/verify OTP,
refresh, or use an existing access token. Reverse by setting the column back
to NULL (deploy/karenseir-demo-data-disable.sh --undo prints the exact SQL).

Revision ID: 20261109_73
Revises: 20261109_72
"""
import sqlalchemy as sa
from alembic import op

revision = "20261109_73"
down_revision = "20261109_72"
branch_labels = None
depends_on = None

TABLES = ("users", "tenants")


def upgrade() -> None:
    bind = op.get_bind()
    for table in TABLES:
        existing = {item["name"] for item in sa.inspect(bind).get_columns(table)}
        if "disabled_at" not in existing:
            op.add_column(table, sa.Column("disabled_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    for table in TABLES:
        existing = {item["name"] for item in sa.inspect(bind).get_columns(table)}
        if "disabled_at" in existing:
            op.drop_column(table, "disabled_at")
