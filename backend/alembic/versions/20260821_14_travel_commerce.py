"""Add tenant-scoped travel commerce domains.

Revision ID: 20260821_14
Revises: 20260820_13
"""
import sqlalchemy as sa
from alembic import op
from app.operations import (
    CruiseSailing,
    TourDeparture,
    TourProduct,
    TourReservation,
    VacationProperty,
    VacationReservation,
    VacationUnit,
    VisaApplicant,
    VisaApplication,
    VisaDocument,
    VisaProduct,
    VisaTimelineEvent,
)

revision = "20260821_14"
down_revision = "20260820_13"
branch_labels = None
depends_on = None
POLICY = "karenseir_tenant_isolation"
TABLES = (
    VacationProperty.__table__, VacationUnit.__table__, VacationReservation.__table__,
    TourProduct.__table__, TourDeparture.__table__, TourReservation.__table__,
    CruiseSailing.__table__, VisaProduct.__table__, VisaApplication.__table__,
    VisaApplicant.__table__, VisaDocument.__table__, VisaTimelineEvent.__table__,
)


def upgrade() -> None:
    bind = op.get_bind()
    for table in TABLES:
        table.create(bind=bind, checkfirst=True)
    if bind.dialect.name == "postgresql":
        quote = bind.dialect.identifier_preparer.quote
        for table in TABLES:
            target = quote(table.name)
            op.execute(sa.text(f"ALTER TABLE {target} ENABLE ROW LEVEL SECURITY"))
            op.execute(sa.text(f"ALTER TABLE {target} FORCE ROW LEVEL SECURITY"))
            exists = bind.execute(sa.text("SELECT 1 FROM pg_policies WHERE schemaname = current_schema() AND tablename = :table AND policyname = :policy"), {"table": table.name, "policy": POLICY}).scalar()
            if not exists:
                op.execute(sa.text(f"CREATE POLICY {POLICY} ON {target} USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::integer) WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::integer)"))


def downgrade() -> None:
    bind = op.get_bind()
    for table in reversed(TABLES):
        table.drop(bind=bind, checkfirst=True)
