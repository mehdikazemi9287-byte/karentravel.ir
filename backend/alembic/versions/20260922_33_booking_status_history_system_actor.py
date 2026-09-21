"""Allow NULL actor_id on booking_status_history for system/webhook-driven transitions.

Webhook-driven reservation transitions have no authenticated human actor
(the previous code used a sentinel actor_id=0, which violated the FK to
users.id since no such user exists). This matches the existing pattern on
visa_timeline_events.actor_id, which is already nullable for the same reason.
"""
from alembic import op
import sqlalchemy as sa

revision = "20260922_33"
down_revision = "20260915_32"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("booking_status_history", "actor_id", existing_type=sa.Integer(), nullable=True)


def downgrade() -> None:
    op.alter_column("booking_status_history", "actor_id", existing_type=sa.Integer(), nullable=False)
