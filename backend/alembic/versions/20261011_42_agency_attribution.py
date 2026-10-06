"""Agency attribution: agencies.sales_channel_id and agency_memberships (tenant-isolated, RLS like every tenant table).

A reservation is an agency's only through the sales channel it was sold on; a user sees an agency only through a membership row.
"""
import sqlalchemy as sa
from alembic import op

from app.operations import AgencyMembership

revision = "20261011_42"
down_revision = "20261010_41"
branch_labels = None
depends_on = None
POLICY = "karenseir_tenant_isolation"


def upgrade() -> None:
    bind = op.get_bind()
    if "sales_channel_id" not in {c["name"] for c in sa.inspect(bind).get_columns("agencies")}:
        op.add_column("agencies", sa.Column("sales_channel_id", sa.String(36), nullable=True))
        op.create_index("ix_agencies_sales_channel_id", "agencies", ["sales_channel_id"])
    table = AgencyMembership.__table__
    table.create(bind=bind, checkfirst=True)
    if bind.dialect.name == "postgresql":
        op.execute(sa.text(f"ALTER TABLE {table.name} ENABLE ROW LEVEL SECURITY"))
        op.execute(sa.text(f"ALTER TABLE {table.name} FORCE ROW LEVEL SECURITY"))
        if not bind.execute(sa.text("SELECT 1 FROM pg_policies WHERE schemaname = current_schema() AND tablename = :t AND policyname = :p"), {"t": table.name, "p": POLICY}).scalar():
            op.execute(sa.text(f"CREATE POLICY {POLICY} ON {table.name} USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::integer) "
                               "WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::integer)"))
        op.execute(sa.text("DO $$ BEGIN IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'karenseir_api') THEN "
                           f"EXECUTE 'REVOKE ALL ON {table.name} FROM karenseir_api'; EXECUTE 'GRANT SELECT, INSERT ON {table.name} TO karenseir_api'; END IF; END $$;"))


def downgrade() -> None:
    op.get_bind()
    AgencyMembership.__table__.drop(bind=op.get_bind(), checkfirst=True)
    op.drop_index("ix_agencies_sales_channel_id", table_name="agencies")
    op.drop_column("agencies", "sales_channel_id")
