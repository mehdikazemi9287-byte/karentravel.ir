"""general ledger (accounts, posting rules, vouchers, periods) and supplier reconciliation runs (tenant-isolated)

Revision ID: 20261103_64
Revises: 20261103_63
"""
from alembic import op
import sqlalchemy as sa

revision = "20261103_64"
down_revision = "20261103_63"
branch_labels = None
depends_on = None

TABLES = ("gl_accounts", "gl_posting_rules", "gl_vouchers", "gl_voucher_lines", "gl_periods", "supplier_recon_runs")
DELETABLE = ("gl_accounts", "gl_posting_rules")  # chart/rules are replaced; vouchers are never deleted


def upgrade() -> None:
    from app.database import Base
    import app.ledger  # noqa: F401  registers the tables on Base.metadata
    import app.supplier_insights  # noqa: F401

    bind = op.get_bind()
    for name in TABLES:
        Base.metadata.tables[name].create(bind, checkfirst=True)
    if bind.dialect.name != "postgresql":
        return
    predicate = "tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::integer"
    has_role = bind.scalar(sa.text("SELECT count(*) FROM pg_roles WHERE rolname='karenseir_api'"))
    for name in TABLES:
        op.execute(sa.text(f'ALTER TABLE "{name}" ENABLE ROW LEVEL SECURITY'))
        op.execute(sa.text(f'ALTER TABLE "{name}" FORCE ROW LEVEL SECURITY'))
        op.execute(sa.text(f'DROP POLICY IF EXISTS karenseir_tenant_isolation ON "{name}"'))
        op.execute(sa.text(f'CREATE POLICY karenseir_tenant_isolation ON "{name}" USING ({predicate}) WITH CHECK ({predicate})'))
        if has_role:
            privileges = "SELECT, INSERT, UPDATE, DELETE" if name in DELETABLE else "SELECT, INSERT, UPDATE"
            op.execute(sa.text(f'GRANT {privileges} ON "{name}" TO karenseir_api'))


def downgrade() -> None:
    raise RuntimeError("ledger vouchers are retained; restore from backup instead of downgrading")
