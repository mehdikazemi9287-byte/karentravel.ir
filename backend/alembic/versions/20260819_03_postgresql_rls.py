"""Enable PostgreSQL RLS for every tenant-scoped table.

Revision ID: 20260819_03
Revises: 20260818_02
"""

import sqlalchemy as sa
from alembic import op

revision = "20260819_03"
down_revision = "20260818_02"
branch_labels = None
depends_on = None

POLICY_NAME = "karenseir_tenant_isolation"


def _tenant_tables(bind) -> list[str]:
    inspector = sa.inspect(bind)
    return sorted(
        table for table in inspector.get_table_names()
        if "tenant_id" in {column["name"] for column in inspector.get_columns(table)}
    )


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    quote = bind.dialect.identifier_preparer.quote
    for table in _tenant_tables(bind):
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
    if bind.dialect.name != "postgresql":
        return
    quote = bind.dialect.identifier_preparer.quote
    for table in _tenant_tables(bind):
        target = quote(table)
        op.execute(sa.text(f"DROP POLICY IF EXISTS {POLICY_NAME} ON {target}"))
        op.execute(sa.text(f"ALTER TABLE {target} NO FORCE ROW LEVEL SECURITY"))
        op.execute(sa.text(f"ALTER TABLE {target} DISABLE ROW LEVEL SECURITY"))
