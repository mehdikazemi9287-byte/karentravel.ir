"""Agency quotes, commission ledger, supplier-hotel assignment, agency credit link (tenant tables with RLS)."""
import sqlalchemy as sa
from alembic import op

from app.operations import AgencyCommissionEntry, AgencyQuote, SupplierCatalogHotel

revision = "20261012_43"
down_revision = "20261011_42"
branch_labels = None
depends_on = None
POLICY = "karenseir_tenant_isolation"
TABLES = {AgencyQuote.__table__: "SELECT, INSERT, UPDATE", AgencyCommissionEntry.__table__: "SELECT, INSERT, UPDATE", SupplierCatalogHotel.__table__: "SELECT, INSERT, DELETE"}


def upgrade() -> None:
    bind = op.get_bind()
    if "credit_account_id" not in {c["name"] for c in sa.inspect(bind).get_columns("agencies")}:
        op.add_column("agencies", sa.Column("credit_account_id", sa.String(36), nullable=True))
    for table, privileges in TABLES.items():
        table.create(bind=bind, checkfirst=True)
        if bind.dialect.name != "postgresql":
            continue
        op.execute(sa.text(f"ALTER TABLE {table.name} ENABLE ROW LEVEL SECURITY"))
        op.execute(sa.text(f"ALTER TABLE {table.name} FORCE ROW LEVEL SECURITY"))
        if not bind.execute(sa.text("SELECT 1 FROM pg_policies WHERE schemaname = current_schema() AND tablename = :t AND policyname = :p"), {"t": table.name, "p": POLICY}).scalar():
            op.execute(sa.text(f"CREATE POLICY {POLICY} ON {table.name} USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::integer) "
                               "WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::integer)"))
        op.execute(sa.text("DO $$ BEGIN IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'karenseir_api') THEN "
                           f"EXECUTE 'REVOKE ALL ON {table.name} FROM karenseir_api'; EXECUTE 'GRANT {privileges} ON {table.name} TO karenseir_api'; END IF; END $$;"))
    if bind.dialect.name == "postgresql":
        op.execute(sa.text("DO $$ BEGIN IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'karenseir_api') THEN EXECUTE 'GRANT DELETE ON agency_memberships TO karenseir_api'; END IF; END $$;"))


def downgrade() -> None:
    bind = op.get_bind()
    for table in reversed(list(TABLES)):
        table.drop(bind=bind, checkfirst=True)
    op.drop_column("agencies", "credit_account_id")
