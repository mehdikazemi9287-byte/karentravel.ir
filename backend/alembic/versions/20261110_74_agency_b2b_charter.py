"""Panels Phase 2 (B2B agency + charter): agency profile/licences/registry checks, agency account + ledger, markup rules,
agency booking lines, charter blocks, CAO price caps; agency_memberships.agency_role. Every new table is tenant-isolated
with FORCE ROW LEVEL SECURITY; registry checks and the agency ledger are append-only for the API role.

Revision ID: 20261110_74
Revises: 20261109_73
"""
from alembic import op
import sqlalchemy as sa

revision = "20261110_74"
down_revision = "20261109_73"
branch_labels = None
depends_on = None

TABLES = ("agency_profiles", "agency_licences", "agency_licence_checks", "agency_accounts", "agency_ledger_entries",
          "agency_markup_rules", "agency_booking_lines", "charter_price_caps", "charter_blocks")
APPEND_ONLY = ("agency_licence_checks", "agency_ledger_entries")  # corrections are new rows


def upgrade() -> None:
    from app.database import Base
    import app.agency_b2b  # noqa: F401  registers the tables on Base.metadata
    import app.charter_blocks  # noqa: F401

    bind = op.get_bind()
    columns = {c["name"] for c in sa.inspect(bind).get_columns("agency_memberships")}
    if "agency_role" not in columns:
        op.add_column("agency_memberships", sa.Column("agency_role", sa.String(16), nullable=False, server_default="owner"))
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
    """Drops the Phase 2 tables. Only safe before real agency money has moved: take a backup first (BACKUP_RECOVERY.md)."""
    bind = op.get_bind()
    existing = set(sa.inspect(bind).get_table_names())
    for name in reversed(TABLES):
        if name in existing:
            op.drop_table(name)
    columns = {c["name"] for c in sa.inspect(bind).get_columns("agency_memberships")}
    if "agency_role" in columns:
        op.drop_column("agency_memberships", "agency_role")
