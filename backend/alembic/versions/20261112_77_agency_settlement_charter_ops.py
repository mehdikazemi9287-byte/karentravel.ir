"""Panels Phase 2b: agency periodic settlement (statements, append-only lines, disputes, append-only timeline), refunds to
agency credit, charter schedule changes (append-only) and agency/customer change notices. Every table is tenant-isolated with
FORCE ROW LEVEL SECURITY; statement lines, statement events and schedule changes are append-only for the API role (a
correction is a new line).

Revision ID: 20261112_77
Revises: 20261111_76
"""
from alembic import op
import sqlalchemy as sa

revision = "20261112_77"
down_revision = "20261111_76"
branch_labels = None
depends_on = None

TABLES = ("agency_settlements", "agency_settlement_lines", "agency_settlement_disputes", "agency_settlement_events", "agency_credit_refunds",
          "charter_schedule_changes", "charter_change_notices")
APPEND_ONLY = ("agency_settlement_lines", "agency_settlement_events", "charter_schedule_changes")


def upgrade() -> None:
    from app.database import Base
    import app.agency_settlement  # noqa: F401  registers the tables on Base.metadata
    import app.charter_changes  # noqa: F401

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
            # ALTER DEFAULT PRIVILEGES (deploy/provision-api-role.sql) gives new tables UPDATE/DELETE: take them back where the
            # table is append-only, and DELETE everywhere (nothing in Phase 2b deletes).
            op.execute(sa.text(f'REVOKE {"UPDATE, DELETE" if name in APPEND_ONLY else "DELETE"} ON "{name}" FROM karenseir_api'))


def downgrade() -> None:
    """Drops the Phase 2b tables. Only safe before real settlements or credit refunds exist: take a backup first (BACKUP_RECOVERY.md)."""
    bind = op.get_bind()
    existing = set(sa.inspect(bind).get_table_names())
    for name in reversed(TABLES):
        if name in existing:
            op.drop_table(name)
