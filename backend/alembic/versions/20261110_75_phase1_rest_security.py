"""Panels Phase 1 (rest) + security: configurable ops SLA, dated tax rates, change-price proposals, saved passengers of an
organization/agency, gateway settlement imports, bank payout batches (all tenant-isolated with FORCE ROW LEVEL SECURITY),
and the global per-destination SMS counter (deliberately not a tenant table: keyed hash only, no tenant_id, no RLS).

Revision ID: 20261110_75
Revises: 20261110_74
"""
from alembic import op
import sqlalchemy as sa

revision = "20261110_75"
down_revision = "20261110_74"
branch_labels = None
depends_on = None

TENANT_TABLES = ("ops_sla_policies", "tax_rate_periods", "price_change_proposals", "scoped_travellers",
                 "settlement_imports", "settlement_import_lines", "bank_payout_batches", "bank_payout_items")
APPEND_ONLY = ("settlement_import_lines", "bank_payout_items")
DELETABLE = ("ops_sla_policies", "scoped_travellers")  # reset to default / unlink a saved passenger
GLOBAL_TABLES = ("sms_destination_counters",)


def upgrade() -> None:
    from app.database import Base
    import app.after_sales  # noqa: F401  ops_sla_policies
    import app.agency_b2b  # noqa: F401  tax_rate_periods
    import app.panel_ops  # noqa: F401
    import app.sms_guard  # noqa: F401

    bind = op.get_bind()
    for name in TENANT_TABLES + GLOBAL_TABLES:
        Base.metadata.tables[name].create(bind, checkfirst=True)
    if bind.dialect.name != "postgresql":
        return
    predicate = "tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::integer"
    has_role = bind.scalar(sa.text("SELECT count(*) FROM pg_roles WHERE rolname='karenseir_api'"))
    for name in TENANT_TABLES:
        op.execute(sa.text(f'ALTER TABLE "{name}" ENABLE ROW LEVEL SECURITY'))
        op.execute(sa.text(f'ALTER TABLE "{name}" FORCE ROW LEVEL SECURITY'))
        op.execute(sa.text(f'DROP POLICY IF EXISTS karenseir_tenant_isolation ON "{name}"'))
        op.execute(sa.text(f'CREATE POLICY karenseir_tenant_isolation ON "{name}" USING ({predicate}) WITH CHECK ({predicate})'))
        if has_role:
            grants = "SELECT, INSERT" if name in APPEND_ONLY else "SELECT, INSERT, UPDATE, DELETE" if name in DELETABLE else "SELECT, INSERT, UPDATE"
            op.execute(sa.text(f'GRANT {grants} ON "{name}" TO karenseir_api'))
    if has_role:
        for name in GLOBAL_TABLES:
            op.execute(sa.text(f'GRANT SELECT, INSERT, UPDATE, DELETE ON "{name}" TO karenseir_api'))


def downgrade() -> None:
    """Drops the Phase 1-rest tables. Only safe before real settlement/payout records exist: take a backup first."""
    bind = op.get_bind()
    existing = set(sa.inspect(bind).get_table_names())
    for name in reversed(TENANT_TABLES + GLOBAL_TABLES):
        if name in existing:
            op.drop_table(name)
