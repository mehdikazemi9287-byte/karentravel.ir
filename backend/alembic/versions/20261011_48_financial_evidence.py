"""Candidate-only additive financial evidence schema. No existing data modification."""
from alembic import op
import sqlalchemy as sa
revision = "20261011_48"
down_revision = "20261008_47"
branch_labels = None
depends_on = None

def upgrade():
    from app.financial_integrity import TABLES
    from app.database import Base
    bind=op.get_bind()
    for name in TABLES:
        Base.metadata.tables[name].create(bind,checkfirst=False)
        if bind.dialect.name=="postgresql":
            op.execute(sa.text('ALTER TABLE "'+name+'" ENABLE ROW LEVEL SECURITY'))
            op.execute(sa.text('ALTER TABLE "'+name+'" FORCE ROW LEVEL SECURITY'))
            predicate="tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::integer"
            op.execute(sa.text('CREATE POLICY karenseir_tenant_isolation ON "'+name+'" USING ('+predicate+') WITH CHECK ('+predicate+')'))
            if bind.scalar(sa.text("SELECT count(*) FROM pg_roles WHERE rolname='karenseir_api'")):
                op.execute(sa.text('GRANT SELECT,INSERT ON "'+name+'" TO karenseir_api'))
                if name=="financial_evidence_sources":
                    op.execute(sa.text('GRANT UPDATE (status, approved_by, updated_at) ON "'+name+'" TO karenseir_api'))
    # The API role cannot update/delete balances, ownership, allocations or audit snapshots.

def downgrade():
    raise RuntimeError("Financial evidence is retained; downgrade requires a separately reviewed preservation plan")
