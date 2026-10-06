"""Explicit hotel state, duplicate matching and supplier hotel mapping for the master catalog.

Additive: verification time, content completeness flag, duplicate link (a linked duplicate is never public),
reviewable match pairs, and provider hotel-id mappings (the only future entry point for rates; none is
created here). No price/availability column. Idempotent for databases built from the live model at 36.
"""
import sqlalchemy as sa
from alembic import op

from app.catalog import HOTEL_LINK_TABLES

revision = "20261007_38"
down_revision = "20261006_37"
branch_labels = None
depends_on = None

COLUMNS = (("last_verified_at", sa.DateTime(timezone=True), None), ("content_complete", sa.Boolean(), sa.false()), ("duplicate_of", sa.String(40), None), ("match_basis", sa.String(40), None))
INDEXES = (("ix_catalog_hotels_content_complete", "content_complete"), ("ix_catalog_hotels_duplicate_of", "duplicate_of"))


def _grant(sql: str) -> None:
    op.execute(sa.text("DO $$ BEGIN IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'karenseir_api') THEN EXECUTE '" + sql + "'; END IF; END $$;"))


def upgrade() -> None:
    bind = op.get_bind()
    have = {c["name"] for c in sa.inspect(bind).get_columns("catalog_hotels")}
    for name, type_, default in COLUMNS:
        if name not in have:
            op.add_column("catalog_hotels", sa.Column(name, type_, nullable=default is None, server_default=default))
    if "duplicate_of" not in have and bind.dialect.name == "postgresql":
        op.create_foreign_key("fk_catalog_hotels_duplicate_of", "catalog_hotels", "catalog_hotels", ["duplicate_of"], ["id"])
    indexes = {i["name"] for i in sa.inspect(bind).get_indexes("catalog_hotels")}
    for name, column in INDEXES:
        if name not in indexes:
            op.create_index(name, "catalog_hotels", [column])
    for table in HOTEL_LINK_TABLES:
        table.create(bind=bind, checkfirst=True)
        if bind.dialect.name == "postgresql":
            _grant(f"GRANT SELECT, INSERT, UPDATE ON {table.name} TO karenseir_api")
            _grant(f"GRANT USAGE, SELECT ON SEQUENCE {table.name}_id_seq TO karenseir_api")


def downgrade() -> None:
    bind = op.get_bind()
    for table in reversed(HOTEL_LINK_TABLES):
        table.drop(bind=bind, checkfirst=True)
    for name, _ in INDEXES:
        op.drop_index(name, table_name="catalog_hotels")
    if bind.dialect.name == "postgresql":
        op.execute("ALTER TABLE catalog_hotels DROP CONSTRAINT IF EXISTS fk_catalog_hotels_duplicate_of")
        op.execute("ALTER TABLE catalog_hotels DROP CONSTRAINT IF EXISTS catalog_hotels_duplicate_of_fkey")
    for name, _, _ in reversed(COLUMNS):
        op.drop_column("catalog_hotels", name)
