"""Add seasonal/weekend/min-stay pricing configuration to vacation units.

Revision ID: 20260822_16
Revises: 20260821_15
"""
import sqlalchemy as sa
from alembic import op

revision = "20260822_16"
down_revision = "20260821_15"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {column["name"] for column in inspector.get_columns("vacation_units")}
    if "pricing_json" not in columns:
        if bind.dialect.name == "sqlite":
            with op.batch_alter_table("vacation_units") as batch:
                batch.add_column(sa.Column("pricing_json", sa.Text(), nullable=False, server_default="{}"))
        else:
            op.add_column("vacation_units", sa.Column("pricing_json", sa.Text(), nullable=False, server_default="{}"))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {column["name"] for column in inspector.get_columns("vacation_units")}
    if "pricing_json" not in columns:
        return
    if bind.dialect.name == "sqlite":
        with op.batch_alter_table("vacation_units") as batch:
            batch.drop_column("pricing_json")
    else:
        op.drop_column("vacation_units", "pricing_json")
