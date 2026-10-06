"""Admin ownership (updated_by, updated_at) on reference tables, so a panel edit is never overwritten by an importer. Additive.

The API role gains UPDATE (not INSERT, not DELETE) on these tables: the panel edits descriptive fields of existing records only.
"""
import sqlalchemy as sa
from alembic import op

revision = "20261015_46"
down_revision = "20261014_45"
branch_labels = None
depends_on = None

TABLES = ("catalog_places", "catalog_airlines", "catalog_airports", "catalog_venues", "catalog_content")


def _as_role(statements):
    if op.get_bind().dialect.name != "postgresql":
        return
    body = " ".join(f"EXECUTE '{s}';" for s in statements)
    op.execute(sa.text(f"DO $$ BEGIN IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'karenseir_api') THEN {body} END IF; END $$;"))


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    for table in TABLES:
        have = {c["name"] for c in inspector.get_columns(table)}
        if "updated_at" not in have: op.add_column(table, sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True))
        if "updated_by" not in have: op.add_column(table, sa.Column("updated_by", sa.Integer(), nullable=True))
    _as_role([f"GRANT UPDATE ON {table} TO karenseir_api" for table in TABLES])


def downgrade() -> None:
    _as_role([f"REVOKE UPDATE ON {table} FROM karenseir_api" for table in TABLES])
    inspector = sa.inspect(op.get_bind())
    for table in TABLES:
        have = {c["name"] for c in inspector.get_columns(table)}
        if "updated_by" in have: op.drop_column(table, "updated_by")
        if "updated_at" in have: op.drop_column(table, "updated_at")
