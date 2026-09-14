"""Add users.mobile_e164: canonical E.164 Iranian mobile number for real
SMS/OTP delivery (Kavenegar integration). Additive and backward-compatible:
nullable, so no existing account's authentication is broken -- email-based
OTP lookup keeps working unchanged for every account that has no mobile
on file yet. Unique only among non-null values (standard SQL null
semantics), matching the existing users.email uniqueness convention.

Revision ID: 20260915_32
Revises: 20260913_31
"""
import sqlalchemy as sa
from alembic import op

revision = "20260915_32"
down_revision = "20260913_31"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    existing = {item["name"] for item in sa.inspect(bind).get_columns("users")}
    if "mobile_e164" not in existing:
        op.add_column("users", sa.Column("mobile_e164", sa.String(length=16), nullable=True))
    indexes = {ix["name"] for ix in sa.inspect(bind).get_indexes("users")}
    if "ix_users_mobile_e164" not in indexes:
        op.create_index("ix_users_mobile_e164", "users", ["mobile_e164"], unique=True)

    # Backfill: ONLY when an existing identifier is itself already an
    # unambiguous, valid Iranian mobile number (e.g. a seeded account whose
    # `email` field happens to hold a phone-shaped string). Never derived
    # or guessed from an email address otherwise -- for this dataset
    # (seeded *.test email addresses) this is expected to backfill zero
    # rows, which is the correct, honest outcome, not a bug.
    from app.kavenegar_adapter import normalize_iranian_mobile
    rows = bind.execute(sa.text("SELECT id, email FROM users WHERE mobile_e164 IS NULL")).fetchall()
    for row in rows:
        receptor = normalize_iranian_mobile(row.email or "")
        if receptor is None:
            continue
        candidate = f"+{receptor}"
        clash = bind.execute(sa.text("SELECT 1 FROM users WHERE mobile_e164 = :m"), {"m": candidate}).scalar()
        if clash:
            continue  # never create a duplicate; both rows stay untouched/NULL
        bind.execute(sa.text("UPDATE users SET mobile_e164 = :m WHERE id = :id"), {"m": candidate, "id": row.id})


def downgrade() -> None:
    bind = op.get_bind()
    indexes = {ix["name"] for ix in sa.inspect(bind).get_indexes("users")}
    if "ix_users_mobile_e164" in indexes:
        op.drop_index("ix_users_mobile_e164", table_name="users")
    existing = {item["name"] for item in sa.inspect(bind).get_columns("users")}
    if "mobile_e164" in existing:
        op.drop_column("users", "mobile_e164")
