"""after-sales loop (Panels Phase 1): service-request handling + timeline, two-person refund execution, refund journal,
pending return-from-sale tax documents, reconciliation links — all tenant-isolated

Revision ID: 20261109_71
Revises: 20261109_70
"""
from alembic import op
import sqlalchemy as sa

revision = "20261109_71"
down_revision = "20261109_70"
branch_labels = None
depends_on = None

TABLES = ("service_request_handling", "service_request_events", "refund_executions", "refund_journal_lines",
          "tax_return_documents", "reconciliation_links")
APPEND_ONLY = ("service_request_events", "refund_journal_lines")  # no UPDATE grant: corrections are new rows


def upgrade() -> None:
    from app.database import Base
    import app.after_sales  # noqa: F401  registers the tables on Base.metadata

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
            grants = "SELECT, INSERT" if name in APPEND_ONLY else "SELECT, INSERT, UPDATE"
            op.execute(sa.text(f'GRANT {grants} ON "{name}" TO karenseir_api'))


def downgrade() -> None:
    raise RuntimeError("after-sales and refund records are retained; restore from backup instead of downgrading")
