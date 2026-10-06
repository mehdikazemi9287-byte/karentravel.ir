"""Hotel content for the master catalog: policies, publication status, licensed images, room types.

Additive. Unknown coordinates become NULL-able (no centroid substitution). Existing rows keep
status='published'. The API role gains write access to hotel content only, used by the audited
admin endpoints (app/catalog_admin.py). No price/offer/availability column is introduced.
Idempotent: revision 36 builds tables from the live model, so on a fresh database the columns
may already exist; each step checks first.
"""
import sqlalchemy as sa
from alembic import op

from app.catalog import HOTEL_CONTENT_TABLES

revision = "20261006_37"
down_revision = "20261003_36"
branch_labels = None
depends_on = None

COLUMNS = (
    ("rules_text", sa.Text(), None), ("children_policy", sa.String(16), None), ("pets_policy", sa.String(16), None), ("smoking_policy", sa.String(16), None),
    ("stars_status", sa.String(24), None), ("status", sa.String(16), "published"), ("updated_at", sa.DateTime(timezone=True), None), ("updated_by", sa.Integer(), None),
)


def _grant(sql: str) -> None:
    op.execute(sa.text("DO $$ BEGIN IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'karenseir_api') THEN EXECUTE '" + sql + "'; END IF; END $$;"))


def upgrade() -> None:
    bind = op.get_bind()
    have = {c["name"] for c in sa.inspect(bind).get_columns("catalog_hotels")}
    with op.batch_alter_table("catalog_hotels") as batch:
        batch.alter_column("latitude", existing_type=sa.Float(), nullable=True)
        batch.alter_column("longitude", existing_type=sa.Float(), nullable=True)
        for name, type_, default in COLUMNS:
            if name not in have:
                batch.add_column(sa.Column(name, type_, nullable=default is None, server_default=default))
    indexes = {i["name"] for i in sa.inspect(bind).get_indexes("catalog_hotels")}
    if "ix_catalog_hotels_status" not in indexes:
        op.create_index("ix_catalog_hotels_status", "catalog_hotels", ["status"])
    for table in HOTEL_CONTENT_TABLES:
        table.create(bind=bind, checkfirst=True)
    if bind.dialect.name == "postgresql":
        _grant("GRANT INSERT, UPDATE ON catalog_hotels TO karenseir_api")
        for table in HOTEL_CONTENT_TABLES:
            _grant(f"GRANT SELECT, INSERT, UPDATE, DELETE ON {table.name} TO karenseir_api")
            _grant(f"GRANT USAGE, SELECT ON SEQUENCE {table.name}_id_seq TO karenseir_api")


def downgrade() -> None:
    bind = op.get_bind()
    if bind.execute(sa.text("SELECT count(*) FROM catalog_hotels WHERE latitude IS NULL OR longitude IS NULL OR source IN ('checkline','karenseir')")).scalar():
        raise RuntimeError("Downgrade refused: catalog_hotels holds CheckLine/admin hotels or rows without coordinates. Export and remove them explicitly first.")
    if bind.dialect.name == "postgresql":
        _grant("REVOKE INSERT, UPDATE ON catalog_hotels FROM karenseir_api")
    for table in reversed(HOTEL_CONTENT_TABLES):
        table.drop(bind=bind, checkfirst=True)
    op.drop_index("ix_catalog_hotels_status", table_name="catalog_hotels")
    with op.batch_alter_table("catalog_hotels") as batch:
        for name, _, _ in reversed(COLUMNS):
            batch.drop_column(name)
        batch.alter_column("latitude", existing_type=sa.Float(), nullable=False)
        batch.alter_column("longitude", existing_type=sa.Float(), nullable=False)
