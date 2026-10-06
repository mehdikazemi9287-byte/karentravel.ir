"""Structured trip change events, reference tour model, room/rate-plan mappings, offer snapshots.

Additive. trip_events gains nullable change columns (category, actor, old/new value, acknowledgement).
catalog_tours gains descriptive columns; itinerary days and tour hotels are reference content.
tour_products.catalog_tour_id optionally links a supplier's sellable product to a reference tour.
No price/capacity column is added to any catalog table; hotel_offer_snapshots only ever holds real supplier quotes.
"""
import sqlalchemy as sa
from alembic import op

from app.catalog import PROVIDER_DETAIL_TABLES, TOUR_CONTENT_TABLES

revision = "20261009_40"
down_revision = "20261008_39"
branch_labels = None
depends_on = None

TRIP = (("change_category", sa.String(32)), ("actor_user_id", sa.Integer()), ("old_value_json", sa.Text()), ("new_value_json", sa.Text()), ("affected_reference", sa.String(120)),
        ("acknowledged_at", sa.DateTime(timezone=True)), ("acknowledged_by_user_id", sa.Integer()))
TOUR = (("description", sa.Text()), ("origin_place_id", sa.String(80)), ("destination_place_id", sa.String(80)), ("duration_nights", sa.Integer()), ("duration_days", sa.Integer()), ("transport_mode", sa.String(16)),
        ("board", sa.String(8)), ("guide_included", sa.Boolean()), ("transfer_included", sa.Boolean()), ("documents_required", sa.Text()), ("cancellation_policy_text", sa.Text()))


def _add(table, columns):
    have = {c["name"] for c in sa.inspect(op.get_bind()).get_columns(table)}
    for name, type_ in columns:
        if name not in have:
            op.add_column(table, sa.Column(name, type_, nullable=True))


def _grant(sql):
    op.execute(sa.text("DO $$ BEGIN IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'karenseir_api') THEN EXECUTE '" + sql + "'; END IF; END $$;"))


def upgrade() -> None:
    bind = op.get_bind()
    _add("trip_events", TRIP)
    if "ix_trip_events_change_category" not in {i["name"] for i in sa.inspect(bind).get_indexes("trip_events")}:
        op.create_index("ix_trip_events_change_category", "trip_events", ["change_category"])
    _add("catalog_tours", TOUR)
    _add("tour_products", (("catalog_tour_id", sa.String(40)),))
    for table in (*TOUR_CONTENT_TABLES, *PROVIDER_DETAIL_TABLES):
        table.create(bind=bind, checkfirst=True)
        if bind.dialect.name == "postgresql":
            _grant(f"GRANT SELECT, INSERT, UPDATE ON {table.name} TO karenseir_api")
            _grant(f"GRANT USAGE, SELECT ON SEQUENCE {table.name}_id_seq TO karenseir_api")
    if bind.dialect.name == "postgresql":
        for table in TOUR_CONTENT_TABLES:
            _grant(f"GRANT DELETE ON {table.name} TO karenseir_api")
        _grant("GRANT INSERT, UPDATE ON catalog_tours TO karenseir_api")


def downgrade() -> None:
    bind = op.get_bind()
    for table in reversed((*TOUR_CONTENT_TABLES, *PROVIDER_DETAIL_TABLES)):
        table.drop(bind=bind, checkfirst=True)
    op.drop_column("tour_products", "catalog_tour_id")
    for name, _ in reversed(TOUR):
        op.drop_column("catalog_tours", name)
    op.drop_index("ix_trip_events_change_category", table_name="trip_events")
    for name, _ in reversed(TRIP):
        op.drop_column("trip_events", name)
