"""Add payment intent, immutable callback event and refund records.

Revision ID: 20260819_05
Revises: 20260819_04
"""
import sqlalchemy as sa
from alembic import op
from app.operations import PaymentEvent, PaymentIntent, RefundRecord

revision = "20260819_05"
down_revision = "20260819_04"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    for model in (PaymentIntent, PaymentEvent, RefundRecord):
        model.__table__.create(bind=bind, checkfirst=True)
    if bind.dialect.name == "postgresql":
        for table in ("payment_intents", "payment_events", "refund_records"):
            op.execute(sa.text(f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY'))
            op.execute(sa.text(f'ALTER TABLE "{table}" FORCE ROW LEVEL SECURITY'))
            op.execute(sa.text(f'DROP POLICY IF EXISTS karenseir_tenant_isolation ON "{table}"'))
            op.execute(sa.text(f'CREATE POLICY karenseir_tenant_isolation ON "{table}" USING (tenant_id = NULLIF(current_setting(\'app.tenant_id\', true), \'\')::integer) WITH CHECK (tenant_id = NULLIF(current_setting(\'app.tenant_id\', true), \'\')::integer)'))


def downgrade() -> None:
    pass
