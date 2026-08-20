"""Add tenant-safe OTP challenges and session security metadata.

Revision ID: 20260819_04
Revises: 20260819_03
"""
import sqlalchemy as sa
from alembic import op

from app.operations import AuthenticationAudit, AuthenticationState, OTPChallenge

revision = "20260819_04"
down_revision = "20260819_03"
branch_labels = None
depends_on = None


def _add_column_if_missing(table_name: str, column: sa.Column) -> None:
    bind = op.get_bind()
    if column.name not in {item["name"] for item in sa.inspect(bind).get_columns(table_name)}:
        op.add_column(table_name, column)


def upgrade() -> None:
    bind = op.get_bind()
    OTPChallenge.__table__.create(bind=bind, checkfirst=True)
    AuthenticationState.__table__.create(bind=bind, checkfirst=True)
    AuthenticationAudit.__table__.create(bind=bind, checkfirst=True)
    for column in (
        sa.Column("family_id", sa.String(36), nullable=True),
        sa.Column("device_hash", sa.String(64), nullable=True),
        sa.Column("ip_hash", sa.String(64), nullable=True),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoke_reason", sa.String(48), nullable=True),
    ):
        _add_column_if_missing("refresh_token_sessions", column)
    op.execute(sa.text("UPDATE refresh_token_sessions SET family_id = id WHERE family_id IS NULL"))
    if bind.dialect.name == "postgresql":
        op.alter_column("refresh_token_sessions", "family_id", nullable=False)
    indexes = {item["name"] for item in sa.inspect(bind).get_indexes("refresh_token_sessions")}
    if "ix_refresh_token_sessions_family_id" not in indexes:
        op.create_index("ix_refresh_token_sessions_family_id", "refresh_token_sessions", ["family_id"])
    if bind.dialect.name == "postgresql":
        for table in ("otp_challenges", "authentication_states", "authentication_audits"):
            op.execute(sa.text(f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY'))
            op.execute(sa.text(f'ALTER TABLE "{table}" FORCE ROW LEVEL SECURITY'))
            op.execute(sa.text(f'DROP POLICY IF EXISTS karenseir_tenant_isolation ON "{table}"'))
            op.execute(sa.text(
                f'CREATE POLICY karenseir_tenant_isolation ON "{table}" '
                "USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::integer) "
                "WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::integer)"
            ))


def downgrade() -> None:
    # Security history is intentionally retained; application rollback is non-destructive.
    pass
