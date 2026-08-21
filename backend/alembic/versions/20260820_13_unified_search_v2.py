"""Add tenant-scoped entity catalog and saved searches.

Revision ID: 20260820_13
Revises: 20260820_12
"""
import sqlalchemy as sa
from alembic import op
from app.operations import SavedSearch, SearchEntity

revision = "20260820_13"
down_revision = "20260820_12"
branch_labels = None
depends_on = None
TABLES = (SearchEntity.__table__, SavedSearch.__table__)


def upgrade() -> None:
    bind = op.get_bind()
    for table in TABLES: table.create(bind=bind, checkfirst=True)
    if bind.dialect.name == "postgresql":
        quote = bind.dialect.identifier_preparer.quote
        for table in TABLES:
            target = quote(table.name); op.execute(sa.text(f"ALTER TABLE {target} ENABLE ROW LEVEL SECURITY")); op.execute(sa.text(f"ALTER TABLE {target} FORCE ROW LEVEL SECURITY"))
            exists = bind.execute(sa.text("SELECT 1 FROM pg_policies WHERE schemaname = current_schema() AND tablename = :table AND policyname = 'karenseir_tenant_isolation'"), {"table": table.name}).scalar()
            if not exists:
                op.execute(sa.text(f"CREATE POLICY karenseir_tenant_isolation ON {target} USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::integer) WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::integer)"))


def downgrade() -> None:
    bind = op.get_bind()
    for table in reversed(TABLES): table.drop(bind=bind, checkfirst=True)
