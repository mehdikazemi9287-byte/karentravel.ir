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
    op.drop_column("catalog_hotel_room_types", "image_url")
    op.drop_index("ux_catalog_tours_slug", table_name="catalog_tours")
    op.drop_column("catalog_tours", "slug")
