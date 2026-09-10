"""Flight+Hotel combined-quote foundation: combined_quotes table.

Additive, tenant-isolated. The table has FKs to price_checks/offers/reservations
which the app role does not own, so this must be applied by the DB superuser
(same operational note as 20260822_17 / 20260913_29-30); the DML grant to
karenseir_api is re-issued here.

Revision ID: 20260913_31
Revises: 20260913_30
"""
import sqlalchemy as sa
from alembic import op

from app.operations import CombinedQuote

revision = "20260913_31"
down_revision = "20260913_30"
branch_labels = None
depends_on = None
POLICY = "karenseir_tenant_isolation"
NEW_TABLES = (CombinedQuote.__table__,)


def upgrade() -> None:
    bind = op.get_bind()
    for table in NEW_TABLES:
        table.create(bind=bind, checkfirst=True)
    if bind.dialect.name == "postgresql":
        quote = bind.dialect.identifier_preparer.quote
        for table in NEW_TABLES:
            target = quote(table.name)
            op.execute(sa.text(f"ALTER TABLE {target} ENABLE ROW LEVEL SECURITY"))
            op.execute(sa.text(f"ALTER TABLE {target} FORCE ROW LEVEL SECURITY"))
            exists = bind.execute(sa.text(
                "SELECT 1 FROM pg_policies WHERE schemaname = current_schema() "
                "AND tablename = :t AND policyname = :p"), {"t": table.name, "p": POLICY}).scalar()
            if not exists:
                op.execute(sa.text(
                    f"CREATE POLICY {POLICY} ON {target} "
                    "USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::integer) "
                    "WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::integer)"))
            op.execute(sa.text(
                "DO $$ BEGIN IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'karenseir_api') THEN "
                f"EXECUTE 'GRANT SELECT, INSERT, UPDATE, DELETE ON {table.name} TO karenseir_api'; END IF; END $$;"))


def downgrade() -> None:
    bind = op.get_bind()
    for table in reversed(NEW_TABLES):
        table.drop(bind=bind, checkfirst=True)
