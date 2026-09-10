"""Notification foundation: versioned templates + channel-independent events.

Adds notification_templates and notification_events (both tenant-isolated), and
two nullable columns to notification_delivery_attempts (scheduled_at, failed_at).
Purely additive; the existing trip-event notification path is untouched.

Must be applied by a role that owns notification_delivery_attempts (the DB
superuser) because of the ALTER TABLE -- same operational note as 20260822_17.

Revision ID: 20260913_30
Revises: 20260913_29
"""
import sqlalchemy as sa
from alembic import op

from app.operations import NotificationEvent, NotificationTemplate

revision = "20260913_30"
down_revision = "20260913_29"
branch_labels = None
depends_on = None
POLICY = "karenseir_tenant_isolation"
NEW_TABLES = (NotificationTemplate.__table__, NotificationEvent.__table__)


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
            exists = bind.execute(sa.text(
                "SELECT 1 FROM pg_policies WHERE schemaname = current_schema() "
                "AND tablename = :t AND policyname = :p"), {"t": table.name, "p": POLICY}).scalar()
            if not exists:
                op.execute(sa.text(
                    f"CREATE POLICY {POLICY} ON {target} "
                    "USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::integer) "
                    "WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::integer)"))
            # this migration runs as the superuser; make sure the app runtime role
            # still has DML on the tables it just created.
            op.execute(sa.text(
                "DO $$ BEGIN IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'karenseir_api') THEN "
                f"EXECUTE 'GRANT SELECT, INSERT, UPDATE, DELETE ON {table.name} TO karenseir_api'; END IF; END $$;"))

    cols = {c["name"] for c in sa.inspect(bind).get_columns("notification_delivery_attempts")}
    to_add = [c for c in ("scheduled_at", "failed_at") if c not in cols]
    if to_add:
        if bind.dialect.name == "sqlite":
            with op.batch_alter_table("notification_delivery_attempts") as batch:
                for c in to_add:
                    batch.add_column(sa.Column(c, sa.DateTime(timezone=True), nullable=True))
        else:
            for c in to_add:
                op.add_column("notification_delivery_attempts", sa.Column(c, sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    cols = {c["name"] for c in sa.inspect(bind).get_columns("notification_delivery_attempts")}
    for c in ("failed_at", "scheduled_at"):
        if c in cols:
            op.drop_column("notification_delivery_attempts", c)
    for table in reversed(NEW_TABLES):
        table.drop(bind=bind, checkfirst=True)
