"""Add global master/catalog tables (places, hotels, airlines, airports, rail, venues).

Reference data only: no tenant_id, no price/offer/availability columns. The API role
gets SELECT; rows are written by scripts/catalog/import_catalog.py under the owner role.
"""
import sqlalchemy as sa
from alembic import op

from app.catalog import CATALOG_TABLES

revision = "20261003_36"
down_revision = "20260929_35"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    for table in CATALOG_TABLES:
        table.create(bind=bind, checkfirst=True)
        if bind.dialect.name == "postgresql":
            op.execute(sa.text(
                "DO $$ BEGIN IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'karenseir_api') THEN "
                f"EXECUTE 'GRANT SELECT ON {table.name} TO karenseir_api'; END IF; END $$;"))


def downgrade() -> None:
    bind = op.get_bind()
    for table in reversed(CATALOG_TABLES):
        table.drop(bind=bind, checkfirst=True)
