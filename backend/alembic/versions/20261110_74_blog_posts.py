"""blog posts (tenant-isolated)

Revision ID: 20261110_74
Revises: 20261109_73
"""
from alembic import op
import sqlalchemy as sa

revision = "20261110_74"
down_revision = "20261109_73"
branch_labels = None
depends_on = None

TABLES = ("blog_posts",)


def upgrade() -> None:
    from app.database import Base
    import app.blog  # noqa: F401  registers the table on Base.metadata

    bind = op.get_bind()
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
            # posts are unpublished, never deleted, so no DELETE grant
            op.execute(sa.text(f'GRANT SELECT, INSERT, UPDATE ON "{name}" TO karenseir_api'))


def downgrade() -> None:
    op.drop_table("blog_posts")
