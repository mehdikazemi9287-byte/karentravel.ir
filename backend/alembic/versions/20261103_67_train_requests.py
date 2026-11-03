"""train ticket requests and desk hours (tenant-isolated)

Revision ID: 20261103_67
Revises: 20261103_66
"""
from alembic import op
import sqlalchemy as sa

revision = "20261103_67"
down_revision = "20261103_66"
branch_labels = None
depends_on = None

TABLES = ("train_requests", "train_desk_settings")
DELETABLE = ()


def upgrade() -> None:
    from app.database import Base
    import app.train_requests  # noqa: F401  registers the tables on Base.metadata

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
    raise RuntimeError("content history is retained; restore from backup instead of downgrading")
