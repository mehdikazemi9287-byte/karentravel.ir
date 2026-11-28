"""users.password_hash: optional fixed password for staff login (owner request 1405-09-08, while SMS OTP is blocked).

Additive and nullable: every existing account keeps NULL, which means "no password login" (OTP only, as before).
Set only from the server console with scripts/set_staff_password.py (pbkdf2 via app.security.hash_password).
users already has RLS and grants; adding a column changes neither. Nothing is deleted; downgrade is refused.
"""
from alembic import op
import sqlalchemy as sa

revision = "20261128_82"
down_revision = "20261128_81"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    existing = {c["name"] for c in sa.inspect(bind).get_columns("users")}
    if "password_hash" not in existing:
        op.add_column("users", sa.Column("password_hash", sa.String(200), nullable=True))


def downgrade():
    raise RuntimeError("Staff password hashes are retained")
