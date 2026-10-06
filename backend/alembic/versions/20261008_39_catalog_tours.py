"""Reference tour catalog (title + recorded dates). Not a product: no price, capacity, supplier or tenant column.

Sellable tours stay in the tenant-scoped tour_products/tour_departures tables owned by suppliers.
"""
from alembic import op
import sqlalchemy as sa

from app.catalog import TOUR_TABLES

revision = "20261008_39"
down_revision = "20261007_38"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    for table in TOUR_TABLES:
        table.create(bind=bind, checkfirst=True)
        if bind.dialect.name == "postgresql":
            op.execute(sa.text("DO $$ BEGIN IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'karenseir_api') THEN "
                               f"EXECUTE 'REVOKE ALL ON {table.name} FROM karenseir_api'; EXECUTE 'GRANT SELECT ON {table.name} TO karenseir_api'; END IF; END $$;"))


def downgrade() -> None:
    bind = op.get_bind()
    for table in reversed(TOUR_TABLES):
        table.drop(bind=bind, checkfirst=True)
