"""Additive operational foundation for tenant-safe booking, finance and trip events.

Revision ID: 20260817_01
Revises: None
"""
from alembic import op

from app.database import Base
from app import main  # noqa: F401 - register metadata

revision = "20260817_01"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # checkfirst keeps this baseline safe for the existing pilot database while
    # still supporting a clean-database upgrade.
    Base.metadata.create_all(bind=op.get_bind(), checkfirst=True)


def downgrade() -> None:
    # The baseline is intentionally non-destructive. Production rollback uses
    # application rollback plus database restore; existing pilot data is never
    # dropped automatically.
    pass
