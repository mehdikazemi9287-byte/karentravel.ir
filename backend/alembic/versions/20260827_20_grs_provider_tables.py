"""GRS (hotel provider) integration - the three genuinely new tables this
integration needs (everything else reuses existing schema - see the GRS audit
report / CHECKPOINT.md for the full reuse rationale):

- provider_location_mappings: provider city/country id <-> existing Destination
- provider_webhook_events: inbound webhook inbox (deliberately NOT tenant-scoped
  - see the model docstring in app/operations.py for why)
- provider_reconciliation_cases: ambiguous-outcome review queue

Table creation itself follows this project's existing convention
(Base.metadata.create_all() at app startup creates any new ORM table
automatically); this migration's job is to (a) also create them here so this
migration is independently upgrade/downgrade-testable without booting the full
app, and (b) apply the same RLS/FORCE RLS/tenant-isolation policy every other
tenant-scoped table already has (mirrors 20260819_03_postgresql_rls.py exactly
- no new policy shape invented).

Revision ID: 20260827_20
Revises: 20260823_19
"""
import sqlalchemy as sa
from alembic import op

revision = "20260827_20"
down_revision = "20260823_19"
branch_labels = None
depends_on = None

POLICY_NAME = "karenseir_tenant_isolation"
NEW_TENANT_SCOPED_TABLES = ("provider_location_mappings", "provider_reconciliation_cases")
NEW_PLATFORM_TABLE = "provider_webhook_events"


def upgrade() -> None:
    from app.database import Base
    from app.operations import ProviderLocationMapping, ProviderWebhookEvent, ProviderReconciliationCase  # noqa: F401

    bind = op.get_bind()
    Base.metadata.create_all(
        bind=bind,
        tables=[
            ProviderLocationMapping.__table__,
            ProviderWebhookEvent.__table__,
            ProviderReconciliationCase.__table__,
        ],
        checkfirst=True,
    )

    if bind.dialect.name != "postgresql":
        return
    quote = bind.dialect.identifier_preparer.quote
    for table in NEW_TENANT_SCOPED_TABLES:
        target = quote(table)
        op.execute(sa.text(f"ALTER TABLE {target} ENABLE ROW LEVEL SECURITY"))
        op.execute(sa.text(f"ALTER TABLE {target} FORCE ROW LEVEL SECURITY"))
        op.execute(sa.text(f"DROP POLICY IF EXISTS {POLICY_NAME} ON {target}"))
        op.execute(sa.text(
            f"CREATE POLICY {POLICY_NAME} ON {target} "
            "USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::integer) "
            "WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::integer)"
        ))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing = set(inspector.get_table_names())

    if bind.dialect.name == "postgresql":
        quote = bind.dialect.identifier_preparer.quote
        for table in NEW_TENANT_SCOPED_TABLES:
            if table in existing:
                target = quote(table)
                op.execute(sa.text(f"DROP POLICY IF EXISTS {POLICY_NAME} ON {target}"))

    for table in (*NEW_TENANT_SCOPED_TABLES, NEW_PLATFORM_TABLE):
        if table in existing:
            op.drop_table(table)
