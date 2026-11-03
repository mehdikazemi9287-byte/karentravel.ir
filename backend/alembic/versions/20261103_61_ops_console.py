"""ops console: Moadian settings and invoice records (tenant-isolated)

Revision ID: 20261103_61
Revises: 20261103_60
"""
from alembic import op
import sqlalchemy as sa

revision = "20261103_61"
down_revision = "20261103_60"
branch_labels = None
depends_on = None

TABLES = ("ops_moadian_settings", "ops_moadian_records")


def upgrade() -> None:
    from app.database import Base
    import app.ops_console  # noqa: F401  registers the tables on Base.metadata

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
            op.execute(sa.text(f'GRANT SELECT, INSERT, UPDATE ON "{name}" TO karenseir_api'))


def downgrade() -> None:
    raise RuntimeError("Moadian records are retained; restore from backup instead of downgrading")
