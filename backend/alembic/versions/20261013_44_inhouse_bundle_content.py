"""Source facts (details_json) on places/hotels/tours, reference content pages and the legacy route map.

Additive. No price/availability column. API role: read-only on the two new tables.
"""
import sqlalchemy as sa
from alembic import op

from app.catalog import CONTENT_TABLES

revision = "20261013_44"
down_revision = "20261012_43"
branch_labels = None
depends_on = None
TARGETS = ("catalog_places", "catalog_hotels", "catalog_tours")


def upgrade() -> None:
    bind = op.get_bind()
    for table in TARGETS:
        if "details_json" not in {c["name"] for c in sa.inspect(bind).get_columns(table)}:
            op.add_column(table, sa.Column("details_json", sa.Text(), nullable=True))
    for table in CONTENT_TABLES:
        table.create(bind=bind, checkfirst=True)
        if bind.dialect.name == "postgresql":
            op.execute(sa.text("DO $$ BEGIN IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'karenseir_api') THEN "
                               f"EXECUTE 'REVOKE ALL ON {table.name} FROM karenseir_api'; EXECUTE 'GRANT SELECT ON {table.name} TO karenseir_api'; END IF; END $$;"))


def downgrade() -> None:
    bind = op.get_bind()
    for table in reversed(CONTENT_TABLES):
        table.drop(bind=bind, checkfirst=True)
    for table in reversed(TARGETS):
        op.drop_column(table, "details_json")
