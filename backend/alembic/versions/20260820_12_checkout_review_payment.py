"""Add review reports, resumable checkout and payment provider references.

Revision ID: 20260820_12
Revises: 20260820_11
"""
import sqlalchemy as sa
from alembic import op
from app.operations import CheckoutSession, ReviewReport

revision = "20260820_12"
down_revision = "20260820_11"
branch_labels = None
depends_on = None

TABLES = (ReviewReport.__table__, CheckoutSession.__table__)
POLICY = "karenseir_tenant_isolation"


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {column["name"] for column in inspector.get_columns("payment_intents")}
    if "provider_authority" not in columns:
        op.add_column("payment_intents", sa.Column("provider_authority", sa.String(160), nullable=True))
    if "provider_capture_reference" not in columns:
        op.add_column("payment_intents", sa.Column("provider_capture_reference", sa.String(160), nullable=True))
    indexes = {index["name"] for index in inspector.get_indexes("payment_intents")}
    if "ix_payment_intents_provider_authority" not in indexes:
        op.create_index("ix_payment_intents_provider_authority", "payment_intents", ["provider_authority"])
    for table in TABLES:
        table.create(bind=bind, checkfirst=True)
    if bind.dialect.name == "postgresql":
        quote = bind.dialect.identifier_preparer.quote
        for table in TABLES:
            target = quote(table.name)
            op.execute(sa.text(f"ALTER TABLE {target} ENABLE ROW LEVEL SECURITY"))
            op.execute(sa.text(f"ALTER TABLE {target} FORCE ROW LEVEL SECURITY"))
            exists = bind.execute(sa.text("SELECT 1 FROM pg_policies WHERE schemaname = current_schema() AND tablename = :table AND policyname = :policy"), {"table": table.name, "policy": POLICY}).scalar()
            if not exists:
                op.execute(sa.text(f"CREATE POLICY {POLICY} ON {target} USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::integer) WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::integer)"))


def downgrade() -> None:
    bind = op.get_bind()
    for table in reversed(TABLES):
        table.drop(bind=bind, checkfirst=True)
    op.drop_index("ix_payment_intents_provider_authority", table_name="payment_intents")
    op.drop_column("payment_intents", "provider_capture_reference")
    op.drop_column("payment_intents", "provider_authority")
