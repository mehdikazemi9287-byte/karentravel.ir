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
    inspector = sa.inspect(bind)
    columns = {column["name"] for column in inspector.get_columns("visa_applications")}
    if "tour_reservation_id" not in columns:
        return
    if bind.dialect.name == "sqlite":
        op.execute(sa.text("DROP INDEX IF EXISTS ix_visa_applications_tour_reservation_id"))
        with op.batch_alter_table("visa_applications") as batch:
            batch.drop_column("tour_reservation_id")
    else:
        # The FK/index may have been created either by this migration's own
        # upgrade() (named "fk_visa_applications_tour_reservation") or, on a
        # fresh install, by migration 20260821_14's table.create() from the
        # ORM model -- which already carried this column and used SQLAlchemy's
        # default auto-generated constraint name instead. Look the real name
        # up rather than assuming one, so downgrade works on both paths.
        indexes = {idx["name"] for idx in inspector.get_indexes("visa_applications")}
        if "ix_visa_applications_tour_reservation_id" in indexes:
            op.drop_index("ix_visa_applications_tour_reservation_id", table_name="visa_applications")
        for fk in inspector.get_foreign_keys("visa_applications"):
            if fk.get("constrained_columns") == ["tour_reservation_id"] and fk.get("name"):
                op.drop_constraint(fk["name"], "visa_applications", type_="foreignkey")
        op.drop_column("visa_applications", "tour_reservation_id")
