"""Add white-label persistence, agency hierarchy and notification receipts.

Revision ID: 20260819_08
Revises: 20260819_07
"""
import sqlalchemy as sa
from alembic import op
from app.operations import WhiteLabelConfiguration

revision = "20260819_08"
down_revision = "20260819_07"
branch_labels = None
depends_on = None


def _add(table, column):
    bind = op.get_bind()
    if column.name not in {item["name"] for item in sa.inspect(bind).get_columns(table)}:
        op.add_column(table, column)


def upgrade() -> None:
    bind = op.get_bind()
    WhiteLabelConfiguration.__table__.create(bind=bind, checkfirst=True)
    _add("agencies", sa.Column("parent_agency_id", sa.String(36), nullable=True))
    _add("agencies", sa.Column("markup_bps", sa.Integer(), nullable=False, server_default="0"))
    _add("agencies", sa.Column("commission_bps", sa.Integer(), nullable=False, server_default="0"))
    _add("notification_delivery_attempts", sa.Column("provider_message_id", sa.String(160), nullable=True))
    _add("notification_delivery_attempts", sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True))
    _add("notification_delivery_attempts", sa.Column("receipt_event_id", sa.String(160), nullable=True))
    if bind.dialect.name == "postgresql":
        agency_fks = sa.inspect(bind).get_foreign_keys("agencies")
        if not any(item.get("constrained_columns") == ["parent_agency_id"] for item in agency_fks):
            op.create_foreign_key("fk_agency_parent", "agencies", "agencies", ["parent_agency_id"], ["id"])
        uniques = sa.inspect(bind).get_unique_constraints("notification_delivery_attempts")
        if not any("receipt_event_id" in item.get("column_names", []) for item in uniques):
            op.create_unique_constraint("uq_notification_receipt_event", "notification_delivery_attempts", ["receipt_event_id"])
        op.execute(sa.text('ALTER TABLE "white_label_configurations" ENABLE ROW LEVEL SECURITY'))
        op.execute(sa.text('ALTER TABLE "white_label_configurations" FORCE ROW LEVEL SECURITY'))
        op.execute(sa.text('DROP POLICY IF EXISTS karenseir_tenant_isolation ON "white_label_configurations"'))
        op.execute(sa.text('CREATE POLICY karenseir_tenant_isolation ON "white_label_configurations" USING (tenant_id = NULLIF(current_setting(\'app.tenant_id\', true), \'\')::integer) WITH CHECK (tenant_id = NULLIF(current_setting(\'app.tenant_id\', true), \'\')::integer)'))


def downgrade() -> None:
    pass
