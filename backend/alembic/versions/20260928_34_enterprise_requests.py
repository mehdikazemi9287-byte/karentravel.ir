"""Add tenant-isolated enterprise request, policy, approval audit and RFQ tables."""
import sqlalchemy as sa
from alembic import op

from app.enterprise_models import EnterpriseGrant, EnterprisePolicy, EnterpriseRequest, EnterpriseRequestEvent, EnterpriseInvitation, EnterpriseQuote, BenefitCampaign

revision = "20260928_34"
down_revision = "20260922_33"
branch_labels = None
depends_on = None
POLICY = "karenseir_tenant_isolation"
NEW_TABLES = tuple(model.__table__ for model in (EnterpriseGrant, EnterprisePolicy, EnterpriseRequest, EnterpriseRequestEvent, EnterpriseInvitation, EnterpriseQuote, BenefitCampaign))


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
            op.execute(sa.text(
                "DO $$ BEGIN IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'karenseir_api') THEN "
                f"EXECUTE 'GRANT SELECT, INSERT, UPDATE, DELETE ON {table.name} TO karenseir_api'; END IF; END $$;"))


def downgrade() -> None:
    bind = op.get_bind()
    for table in reversed(NEW_TABLES):
        table.drop(bind=bind, checkfirst=True)
