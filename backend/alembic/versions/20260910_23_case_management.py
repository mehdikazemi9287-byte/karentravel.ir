"""Add Trip Operations case-management fields to support cases."""
from alembic import op
import sqlalchemy as sa

revision = "20260910_23"
down_revision = "20260909_22"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    existing = {item["name"] for item in sa.inspect(bind).get_columns("support_cases")}
    additions = [
        ("case_type", sa.String(length=48), "OTHER"),
        ("severity", sa.String(length=16), "MEDIUM"),
        ("sla_due_at", sa.DateTime(timezone=True), None),
        ("resolution_type", sa.String(length=32), None),
        ("resolution_notes", sa.Text(), None),
        ("resolved_by_user_id", sa.Integer(), None),
        ("resolved_at", sa.DateTime(timezone=True), None),
        ("audit_trail_json", sa.Text(), "[]"),
    ]
    for name, column_type, default in additions:
        if name in existing:
            continue
        kwargs = {"nullable": True}
        if default is not None:
            kwargs["server_default"] = default
        op.add_column("support_cases", sa.Column(name, column_type, **kwargs))
    inspector = sa.inspect(bind)
    fks = {fk.get("name") for fk in inspector.get_foreign_keys("support_cases")}
    if "fk_support_cases_resolved_by_user_id" not in fks:
        op.create_foreign_key("fk_support_cases_resolved_by_user_id", "support_cases", "users", ["resolved_by_user_id"], ["id"])


def downgrade() -> None:
    # Preserve case-management audit history; rollback uses the previous image.
    pass
