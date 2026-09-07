"""Add leisure domain: Place, ExperienceProduct, LeisureSession,
LeisureTicketType, and extend the existing (previously unused) tickets table
with admission-QR fields.

Revision ID: 20260908_21
Revises: 20260827_20
"""
import sqlalchemy as sa
from alembic import op
from app.operations import ExperienceProduct, LeisureSession, LeisureTicketType, Place

revision = "20260908_21"
down_revision = "20260827_20"
branch_labels = None
depends_on = None
POLICY = "karenseir_tenant_isolation"
NEW_TABLES = (Place.__table__, ExperienceProduct.__table__, LeisureSession.__table__, LeisureTicketType.__table__)


def upgrade() -> None:
    bind = op.get_bind()
    for table in NEW_TABLES:
        table.create(bind=bind, checkfirst=True)
    if bind.dialect.name == "postgresql":
        quote = bind.dialect.identifier_preparer.quote
        for table in NEW_TABLES:
            target = quote(table.name)
            op.execute(sa.text(f"ALTER TABLE {target} ENABLE ROW LEVEL SECURITY"))
            op.execute(sa.text(f"ALTER TABLE {target} FORCE ROW LEVEL SECURITY"))
            exists = bind.execute(sa.text("SELECT 1 FROM pg_policies WHERE schemaname = current_schema() AND tablename = :table AND policyname = :policy"), {"table": table.name, "policy": POLICY}).scalar()
            if not exists:
                op.execute(sa.text(f"CREATE POLICY {POLICY} ON {target} USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::integer) WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::integer)"))
    inspector = sa.inspect(bind)
    columns = {column["name"] for column in inspector.get_columns("tickets")}
    if "qr_token" not in columns:
        if bind.dialect.name == "sqlite":
            with op.batch_alter_table("tickets") as batch:
                batch.add_column(sa.Column("qr_token", sa.String(length=64), nullable=True))
                batch.add_column(sa.Column("leisure_session_id", sa.String(length=36), nullable=True))
                batch.add_column(sa.Column("redeemed_at", sa.DateTime(timezone=True), nullable=True))
                batch.add_column(sa.Column("redeemed_by", sa.Integer(), nullable=True))
                batch.create_unique_constraint("uq_tickets_qr_token", ["qr_token"])
                batch.create_foreign_key("fk_tickets_leisure_session", "leisure_sessions", ["leisure_session_id"], ["id"])
                batch.create_foreign_key("fk_tickets_redeemed_by", "users", ["redeemed_by"], ["id"])
                batch.create_index("ix_tickets_qr_token", ["qr_token"])
                batch.create_index("ix_tickets_leisure_session_id", ["leisure_session_id"])
        else:
            op.add_column("tickets", sa.Column("qr_token", sa.String(length=64), nullable=True))
            op.add_column("tickets", sa.Column("leisure_session_id", sa.String(length=36), nullable=True))
            op.add_column("tickets", sa.Column("redeemed_at", sa.DateTime(timezone=True), nullable=True))
            op.add_column("tickets", sa.Column("redeemed_by", sa.Integer(), nullable=True))
            op.create_unique_constraint("uq_tickets_qr_token", "tickets", ["qr_token"])
            op.create_foreign_key("fk_tickets_leisure_session", "tickets", "leisure_sessions", ["leisure_session_id"], ["id"])
            op.create_foreign_key("fk_tickets_redeemed_by", "tickets", "users", ["redeemed_by"], ["id"])
            op.create_index("ix_tickets_qr_token", "tickets", ["qr_token"])
            op.create_index("ix_tickets_leisure_session_id", "tickets", ["leisure_session_id"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {column["name"] for column in inspector.get_columns("tickets")}
    if "qr_token" in columns:
        if bind.dialect.name == "sqlite":
            with op.batch_alter_table("tickets") as batch:
                batch.drop_column("qr_token")
                batch.drop_column("leisure_session_id")
                batch.drop_column("redeemed_at")
                batch.drop_column("redeemed_by")
        else:
            op.drop_constraint("fk_tickets_leisure_session", "tickets", type_="foreignkey")
            op.drop_constraint("fk_tickets_redeemed_by", "tickets", type_="foreignkey")
            op.drop_index("ix_tickets_qr_token", table_name="tickets")
            op.drop_index("ix_tickets_leisure_session_id", table_name="tickets")
            op.drop_column("tickets", "qr_token")
            op.drop_column("tickets", "leisure_session_id")
            op.drop_column("tickets", "redeemed_at")
            op.drop_column("tickets", "redeemed_by")
    for table in reversed(NEW_TABLES):
        table.drop(bind=bind, checkfirst=True)
