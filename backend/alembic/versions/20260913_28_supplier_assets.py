"""Add supplier_assets: persistent tenant-scoped supplier media/document store.

Revision ID: 20260913_28
Revises: 20260913_27
"""
import sqlalchemy as sa
from alembic import op

from app.operations import SupplierAsset

revision = "20260913_28"
down_revision = "20260913_27"
branch_labels = None
depends_on = None
POLICY = "karenseir_tenant_isolation"
NEW_TABLES = (SupplierAsset.__table__,)


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
            exists = bind.execute(
                sa.text(
                    "SELECT 1 FROM pg_policies WHERE schemaname = current_schema() "
                    "AND tablename = :table AND policyname = :policy"
                ),
                {"table": table.name, "policy": POLICY},
            ).scalar()
            if not exists:
                op.execute(
                    sa.text(
                        f"CREATE POLICY {POLICY} ON {target} "
                        "USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::integer) "
                        "WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::integer)"
                    )
                )


def downgrade() -> None:
    bind = op.get_bind()
    for table in reversed(NEW_TABLES):
        table.drop(bind=bind, checkfirst=True)
