"""Own hotel contracts, rooms and nightly rate/allotment calendar. Additive."""
from alembic import op
import sqlalchemy as sa

revision = "20261102_51"
down_revision = "20261102_50"
branch_labels = None
depends_on = None


def upgrade():
    from app.stays import TABLES
    from app.database import Base
    bind = op.get_bind()
    for name in TABLES:
        Base.metadata.tables[name].create(bind, checkfirst=True)
        if bind.dialect.name != "postgresql":
            continue
        op.execute(sa.text(f'ALTER TABLE "{name}" ENABLE ROW LEVEL SECURITY'))
        op.execute(sa.text(f'ALTER TABLE "{name}" FORCE ROW LEVEL SECURITY'))
        predicate = "tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::integer"
        op.execute(sa.text(f'DROP POLICY IF EXISTS karenseir_tenant_isolation ON "{name}"'))
        op.execute(sa.text(f'CREATE POLICY karenseir_tenant_isolation ON "{name}" USING ({predicate}) WITH CHECK ({predicate})'))
        if bind.scalar(sa.text("SELECT count(*) FROM pg_roles WHERE rolname='karenseir_api'")):
            op.execute(sa.text(f'GRANT SELECT, INSERT, UPDATE ON "{name}" TO karenseir_api'))
        if bind.scalar(sa.text("SELECT count(*) FROM pg_roles WHERE rolname='karenseir_worker'")):
            op.execute(sa.text(f'GRANT SELECT ON "{name}" TO karenseir_worker'))


def downgrade():
    raise RuntimeError("Stay contract history is retained; downgrade requires a reviewed preservation plan")
