"""Add security, finance and notification operation extensions.

Revision ID: 20260818_02
Revises: 20260817_01
"""

import sqlalchemy as sa
from alembic import op

from app.operations import (
    Agency,
    InstallmentPlan,
    NotificationPreference,
    PricingRule,
    RefreshTokenSession,
    RolePermission,
    SettlementRecord,
    UserProfile,
)

revision = "20260818_02"
down_revision = "20260817_01"
branch_labels = None
depends_on = None


def _add_column_if_missing(table_name: str, column: sa.Column) -> None:
    bind = op.get_bind()
    columns = {item["name"] for item in sa.inspect(bind).get_columns(table_name)}
    if column.name not in columns:
        op.add_column(table_name, column)


def upgrade() -> None:
    bind = op.get_bind()
    for table in (
        UserProfile.__table__,
        RolePermission.__table__,
        RefreshTokenSession.__table__,
        Agency.__table__,
        InstallmentPlan.__table__,
        PricingRule.__table__,
        SettlementRecord.__table__,
        NotificationPreference.__table__,
    ):
        table.create(bind=bind, checkfirst=True)

    _add_column_if_missing("outbox_events", sa.Column("correlation_id", sa.String(length=64), nullable=True))
    _add_column_if_missing("outbox_events", sa.Column("idempotency_key", sa.String(length=120), nullable=True))
    _add_column_if_missing("outbox_events", sa.Column("dead_lettered_at", sa.DateTime(timezone=True), nullable=True))
    indexes = {item["name"] for item in sa.inspect(bind).get_indexes("outbox_events")}
    if "ix_outbox_events_correlation_id" not in indexes:
        op.create_index("ix_outbox_events_correlation_id", "outbox_events", ["correlation_id"], unique=False)


def downgrade() -> None:
    # Intentionally non-destructive. Rollback uses the previous application
    # image and a verified database backup; operational history is preserved.
    pass
