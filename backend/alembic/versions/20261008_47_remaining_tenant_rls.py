"""Protect five legacy tenant tables omitted from earlier RLS migrations.

Additive security hardening: no data changes. A downgrade retains the protection;
it only permits the Alembic revision marker to follow the approved rollback.
"""
import sqlalchemy as sa
from alembic import op

revision = "20261008_47"
down_revision = "20261015_46"
branch_labels = None
depends_on = None
TABLES = ("licensed_entities", "supplier_memberships", "sales_channels", "price_breakdowns", "reconciliation_records")
POLICY = "karenseir_tenant_isolation"
PREDICATE = "tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::integer"


def upgrade():
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    for table in TABLES:
        columns = {c["name"] for c in sa.inspect(bind).get_columns(table)}
        if "tenant_id" not in columns:
            raise RuntimeError("Expected existing tenant table: " + table)
        target = '"' + table + '"'
        op.execute(sa.text("ALTER TABLE " + target + " ENABLE ROW LEVEL SECURITY"))
        op.execute(sa.text("ALTER TABLE " + target + " FORCE ROW LEVEL SECURITY"))
        existing = bind.scalar(sa.text("SELECT count(*) FROM pg_policies WHERE schemaname='public' AND tablename=:table AND policyname=:policy"), {"table": table, "policy": POLICY})
        if not existing:
            op.execute(sa.text("CREATE POLICY " + POLICY + " ON " + target + " USING (" + PREDICATE + ") WITH CHECK (" + PREDICATE + ")"))


def downgrade():
    # Do not remove tenant protection during an application rollback.
    pass
