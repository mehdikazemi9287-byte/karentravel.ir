"""Reference tour slug (for /tours/[slug]) and a room-type image URL. Additive."""
import sqlalchemy as sa
from alembic import op

revision = "20261014_45"
down_revision = "20261013_44"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if "slug" not in {c["name"] for c in sa.inspect(bind).get_columns("catalog_tours")}:
        op.add_column("catalog_tours", sa.Column("slug", sa.String(200), nullable=True))
        op.create_index("ux_catalog_tours_slug", "catalog_tours", ["slug"], unique=True)
    if "image_url" not in {c["name"] for c in sa.inspect(bind).get_columns("catalog_hotel_room_types")}:
        op.add_column("catalog_hotel_room_types", sa.Column("image_url", sa.String(500), nullable=True))


def downgrade() -> None:
    # Revision 39 builds catalog_tours from the live model, so on a chain that starts at 38 the slug column and its
    # unique constraint already exist under the names the model gives them; drop whichever form is present.
    bind = op.get_bind()
    if "image_url" in {c["name"] for c in sa.inspect(bind).get_columns("catalog_hotel_room_types")}:
        op.drop_column("catalog_hotel_room_types", "image_url")
    if "slug" in {c["name"] for c in sa.inspect(bind).get_columns("catalog_tours")}:
        if bind.dialect.name == "postgresql":
            op.execute("DROP INDEX IF EXISTS ux_catalog_tours_slug")
            op.execute("ALTER TABLE catalog_tours DROP CONSTRAINT IF EXISTS catalog_tours_slug_key")
        elif "ux_catalog_tours_slug" in {i["name"] for i in sa.inspect(bind).get_indexes("catalog_tours")}:
            op.drop_index("ux_catalog_tours_slug", table_name="catalog_tours")
        op.drop_column("catalog_tours", "slug")
