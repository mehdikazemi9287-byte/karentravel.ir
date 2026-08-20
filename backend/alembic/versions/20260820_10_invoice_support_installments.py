"""Add tenant-isolated invoice, support case and installment execution tables.

Revision ID: 20260820_10
Revises: 20260820_09
"""
import sqlalchemy as sa
from alembic import op
from app.operations import InstallmentAgreement, Invoice, SupportCase, SupportThreadMessage

revision = "20260820_10"
down_revision = "20260820_09"
branch_labels = None
depends_on = None

TABLES = (Invoice.__table__, SupportCase.__table__, SupportThreadMessage.__table__, InstallmentAgreement.__table__)
POLICY = "karenseir_tenant_isolation"


def upgrade() -> None:
    bind = op.get_bind()
    for table in TABLES:
        table.create(bind=bind, checkfirst=True)
    if bind.dialect.name == "postgresql":
        quote = bind.dialect.identifier_preparer.quote
        for table in TABLES:
            target = quote(table.name)
            op.execute(sa.text(f"ALTER TABLE {target} ENABLE ROW LEVEL SECURITY"))
            op.execute(sa.text(f"ALTER TABLE {target} FORCE ROW LEVEL SECURITY"))
            op.execute(sa.text(f"DROP POLICY IF EXISTS {POLICY} ON {target}"))
            op.execute(sa.text(f"CREATE POLICY {POLICY} ON {target} USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::integer) WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::integer)"))


def downgrade() -> None:
    bind = op.get_bind()
    for table in reversed(TABLES):
        table.drop(bind=bind, checkfirst=True)
