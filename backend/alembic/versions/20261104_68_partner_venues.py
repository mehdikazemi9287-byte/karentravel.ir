"""partner venues copied from ShahrShad (global reference table, read by the public API)

Revision ID: 20261104_68
Revises: 20261103_67
"""
from alembic import op
import sqlalchemy as sa

revision = "20261104_68"
down_revision = "20261103_67"
branch_labels = None
depends_on = None


def upgrade() -> None:
    from app.database import Base
    import app.shahrshad_sync  # noqa: F401  registers the table on Base.metadata

    bind = op.get_bind()
    Base.metadata.tables["partner_venues"].create(bind, checkfirst=True)
    if bind.dialect.name != "postgresql":
        return
    if bind.scalar(sa.text("SELECT count(*) FROM pg_roles WHERE rolname='karenseir_api'")):
        op.execute(sa.text('GRANT SELECT, INSERT, UPDATE ON "partner_venues" TO karenseir_api'))


def downgrade() -> None:
    op.drop_table("partner_venues")
