"""Link visa applications to tenant-owned tour reservations.

Revision ID: 20260821_15
Revises: 20260821_14
"""
import sqlalchemy as sa
from alembic import op

revision = "20260821_15"
down_revision = "20260821_14"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {column["name"] for column in inspector.get_columns("visa_applications")}
    if "tour_reservation_id" not in columns:
        if bind.dialect.name == "sqlite":
            with op.batch_alter_table("visa_applications") as batch:
                batch.add_column(sa.Column("tour_reservation_id", sa.String(length=36), nullable=True))
                batch.create_foreign_key("fk_visa_applications_tour_reservation", "tour_reservations", ["tour_reservation_id"], ["id"])
                batch.create_index("ix_visa_applications_tour_reservation_id", ["tour_reservation_id"])
        else:
            op.add_column("visa_applications", sa.Column("tour_reservation_id", sa.String(length=36), nullable=True))
            op.create_foreign_key("fk_visa_applications_tour_reservation", "visa_applications", "tour_reservations", ["tour_reservation_id"], ["id"])
            op.create_index("ix_visa_applications_tour_reservation_id", "visa_applications", ["tour_reservation_id"])


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        op.execute(sa.text("DROP INDEX IF EXISTS ix_visa_applications_tour_reservation_id"))
        with op.batch_alter_table("visa_applications") as batch:
            batch.drop_column("tour_reservation_id")
    else:
        op.drop_index("ix_visa_applications_tour_reservation_id", table_name="visa_applications")
        op.drop_constraint("fk_visa_applications_tour_reservation", "visa_applications", type_="foreignkey")
        op.drop_column("visa_applications", "tour_reservation_id")
