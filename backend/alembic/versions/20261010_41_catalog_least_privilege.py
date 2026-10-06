"""Least privilege for the API database role on master-catalog tables.

Production's default privileges hand karenseir_api full DML on every new table, so the role could DELETE
catalog rows although no code path does. This states the exact need and removes the rest:
  read-only reference ........ SELECT
  admin-edited parents ....... SELECT, INSERT, UPDATE          (never DELETE: hotels/tours/mappings are hidden or linked, not removed)
  replace-on-save children ... SELECT, INSERT, UPDATE, DELETE  (images, room types, itinerary days, tour hotels)
  supplier quotes ............ SELECT, INSERT
Importers and migrations run as the owner role and are unaffected. No-op when the role does not exist.
Downgrade restores the previous broad grant.
"""
import sqlalchemy as sa
from alembic import op

revision = "20261010_41"
down_revision = "20261009_40"
branch_labels = None
depends_on = None

READ_ONLY = ("catalog_places", "catalog_airlines", "catalog_airports", "catalog_rail_operators", "catalog_rail_stations", "catalog_venues", "catalog_tour_departures")
PARENTS = ("catalog_hotels", "catalog_hotel_matches", "catalog_hotel_provider_mappings", "catalog_hotel_room_mappings", "catalog_hotel_rate_plan_mappings", "catalog_tours")
CHILDREN = ("catalog_hotel_images", "catalog_hotel_room_types", "catalog_tour_itinerary_days", "catalog_tour_hotels")
QUOTES = ("hotel_offer_snapshots",)
GRANTS = {**{t: "SELECT" for t in READ_ONLY}, **{t: "SELECT, INSERT, UPDATE" for t in PARENTS}, **{t: "SELECT, INSERT, UPDATE, DELETE" for t in CHILDREN}, **{t: "SELECT, INSERT" for t in QUOTES}}


def _as_role(statements):
    body = " ".join(f"EXECUTE '{s}';" for s in statements)
    op.execute(sa.text(f"DO $$ BEGIN IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'karenseir_api') THEN {body} END IF; END $$;"))


def upgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    _as_role([s for table, privileges in GRANTS.items() for s in (f"REVOKE ALL ON {table} FROM karenseir_api", f"GRANT {privileges} ON {table} TO karenseir_api")])


def downgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    _as_role([f"GRANT SELECT, INSERT, UPDATE, DELETE ON {table} TO karenseir_api" for table in GRANTS])
