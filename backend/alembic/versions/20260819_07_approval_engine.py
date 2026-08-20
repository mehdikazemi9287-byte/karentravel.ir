"""Add configurable multi-step approval engine and organization dimensions.

Revision ID: 20260819_07
Revises: 20260819_06
"""
import sqlalchemy as sa
from alembic import op
from app.operations import ApprovalInstanceStep, ApprovalTemplate, ApprovalTemplateStep, CostCenter, Department, EmployeeAssignment

revision = "20260819_07"
down_revision = "20260819_06"
branch_labels = None
depends_on = None


def _add(table, column):
    bind = op.get_bind()
    if column.name not in {item["name"] for item in sa.inspect(bind).get_columns(table)}:
        op.add_column(table, column)


def upgrade() -> None:
    bind = op.get_bind()
    for model in (Department, CostCenter, EmployeeAssignment, ApprovalTemplate, ApprovalTemplateStep, ApprovalInstanceStep):
        model.__table__.create(bind=bind, checkfirst=True)
    _add("approval_workflows", sa.Column("template_id", sa.String(36), nullable=True))
    _add("approval_workflows", sa.Column("current_step_order", sa.Integer(), nullable=False, server_default="1"))
    _add("approval_workflows", sa.Column("rejection_reason", sa.String(500), nullable=True))
    _add("approval_workflows", sa.Column("escalation_count", sa.Integer(), nullable=False, server_default="0"))
    if bind.dialect.name == "postgresql":
        fks = sa.inspect(bind).get_foreign_keys("approval_workflows")
        if not any(item.get("constrained_columns") == ["template_id"] for item in fks):
            op.create_foreign_key("fk_approval_workflow_template", "approval_workflows", "approval_templates", ["template_id"], ["id"])
        for table in ("departments", "cost_centers", "employee_assignments", "approval_templates", "approval_template_steps", "approval_instance_steps"):
            op.execute(sa.text(f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY'))
            op.execute(sa.text(f'ALTER TABLE "{table}" FORCE ROW LEVEL SECURITY'))
            op.execute(sa.text(f'DROP POLICY IF EXISTS karenseir_tenant_isolation ON "{table}"'))
            op.execute(sa.text(f'CREATE POLICY karenseir_tenant_isolation ON "{table}" USING (tenant_id = NULLIF(current_setting(\'app.tenant_id\', true), \'\')::integer) WITH CHECK (tenant_id = NULLIF(current_setting(\'app.tenant_id\', true), \'\')::integer)'))


def downgrade() -> None:
    pass
