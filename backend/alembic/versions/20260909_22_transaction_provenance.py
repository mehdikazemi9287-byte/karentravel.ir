"""Add Licensed Entity and Sales Channel transaction provenance.

Revision ID: 20260909_22
Revises: 20260908_21
"""
import sqlalchemy as sa
from alembic import op
from app.operations import LicensedEntity, SalesChannel

revision = "20260909_22"
down_revision = "20260908_21"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    LicensedEntity.__table__.create(bind, checkfirst=True)
    SalesChannel.__table__.create(bind, checkfirst=True)
    columns = {item["name"] for item in sa.inspect(bind).get_columns("reservations")}
    for column, foreign in (
        (sa.Column("licensed_entity_id", sa.String(length=36), nullable=True), "licensed_entities"),
        (sa.Column("sales_channel_id", sa.String(length=36), nullable=True), "sales_channels"),
    ):
        if column.name not in columns:
            op.add_column("reservations", column)
            op.create_foreign_key(f"fk_reservations_{column.name}", "reservations", foreign, [column.name], ["id"])
            op.create_index(f"ix_reservations_{column.name}", "reservations", [column.name], unique=False)


def downgrade() -> None:
    # Preserve transaction history; rollback uses the previous application image.
    pass
