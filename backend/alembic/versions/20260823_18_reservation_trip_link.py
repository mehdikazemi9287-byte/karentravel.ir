"""Link reservations to trips so the post-booking journey can produce real Trip/Timeline data.

Revision ID: 20260823_18
Revises: 20260822_17
"""
import sqlalchemy as sa
from alembic import op

revision = "20260823_18"
down_revision = "20260822_17"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {column["name"] for column in inspector.get_columns("reservations")}
    if "trip_id" not in columns:
        if bind.dialect.name == "sqlite":
            with op.batch_alter_table("reservations") as batch:
                batch.add_column(sa.Column("trip_id", sa.String(length=36), nullable=True))
                batch.create_foreign_key("fk_reservations_trip_id_trips", "trips", ["trip_id"], ["id"])
                batch.create_index("ix_reservations_trip_id", ["trip_id"])
        else:
            op.add_column("reservations", sa.Column("trip_id", sa.String(length=36), nullable=True))
            op.create_foreign_key("fk_reservations_trip_id_trips", "reservations", "trips", ["trip_id"], ["id"])
            op.create_index("ix_reservations_trip_id", "reservations", ["trip_id"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {column["name"] for column in inspector.get_columns("reservations")}
    if "trip_id" not in columns:
        return
    if bind.dialect.name == "sqlite":
        with op.batch_alter_table("reservations") as batch:
            batch.drop_index("ix_reservations_trip_id")
            batch.drop_constraint("fk_reservations_trip_id_trips", type_="foreignkey")
            batch.drop_column("trip_id")
    else:
        fk_name = None
        for fk in inspector.get_foreign_keys("reservations"):
            if fk.get("constrained_columns") == ["trip_id"]:
                fk_name = fk.get("name")
                break
        op.drop_index("ix_reservations_trip_id", table_name="reservations")
        if fk_name:
            op.drop_constraint(fk_name, "reservations", type_="foreignkey")
        op.drop_column("reservations", "trip_id")
