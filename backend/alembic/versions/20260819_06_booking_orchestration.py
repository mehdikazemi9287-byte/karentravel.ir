"""Add supplier offers, immutable price checks and booking history.

Revision ID: 20260819_06
Revises: 20260819_05
"""
import sqlalchemy as sa
from alembic import op
from app.operations import BookingStatusHistory, Offer, PriceCheck

revision = "20260819_06"
down_revision = "20260819_05"
branch_labels = None
depends_on = None


def _add_column_if_missing(table_name: str, column: sa.Column) -> None:
    bind = op.get_bind()
    if column.name not in {item["name"] for item in sa.inspect(bind).get_columns(table_name)}:
        op.add_column(table_name, column)


def upgrade() -> None:
    bind = op.get_bind()
    for model in (Offer, PriceCheck, BookingStatusHistory):
        model.__table__.create(bind=bind, checkfirst=True)
    _add_column_if_missing("reservations", sa.Column("booking_reference", sa.String(64), nullable=True))
    _add_column_if_missing("reservations", sa.Column("price_check_id", sa.String(36), nullable=True))
    _add_column_if_missing("reservations", sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True))
    indexes = {item["name"] for item in sa.inspect(bind).get_indexes("reservations")}
    if "ix_reservations_price_check_id" not in indexes:
        op.create_index("ix_reservations_price_check_id", "reservations", ["price_check_id"])
    unique_constraints = sa.inspect(bind).get_unique_constraints("reservations")
    if not any("booking_reference" in item.get("column_names", []) for item in unique_constraints):
        op.create_unique_constraint("uq_reservations_booking_reference", "reservations", ["booking_reference"])
    if bind.dialect.name == "postgresql":
        foreign_keys = sa.inspect(bind).get_foreign_keys("reservations")
        if not any(item.get("constrained_columns") == ["price_check_id"] for item in foreign_keys):
            op.create_foreign_key("fk_reservations_price_check", "reservations", "price_checks", ["price_check_id"], ["id"])
        for table in ("offers", "price_checks", "booking_status_history"):
            op.execute(sa.text(f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY'))
            op.execute(sa.text(f'ALTER TABLE "{table}" FORCE ROW LEVEL SECURITY'))
            op.execute(sa.text(f'DROP POLICY IF EXISTS karenseir_tenant_isolation ON "{table}"'))
            op.execute(sa.text(f'CREATE POLICY karenseir_tenant_isolation ON "{table}" USING (tenant_id = NULLIF(current_setting(\'app.tenant_id\', true), \'\')::integer) WITH CHECK (tenant_id = NULLIF(current_setting(\'app.tenant_id\', true), \'\')::integer)'))


def downgrade() -> None:
    pass
