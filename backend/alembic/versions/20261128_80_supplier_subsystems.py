"""Supplier web-service connection: provider_key, connection_mode (dedicated|shared), external_ref (subsystem code). Additive, nullable."""
from alembic import op
import sqlalchemy as sa

revision = "20261128_80"
down_revision = "20261128_79"
branch_labels = None
depends_on = None

COLUMNS = (("provider_key", 40), ("connection_mode", 16), ("external_ref", 40))


def upgrade():
    bind = op.get_bind()
    name = "suppliers"
    existing = {c["name"] for c in sa.inspect(bind).get_columns(name)}
    for column, size in COLUMNS:
        if column not in existing:
            op.add_column(name, sa.Column(column, sa.String(size), nullable=True))
    if "ix_suppliers_provider_key" not in {i["name"] for i in sa.inspect(bind).get_indexes(name)}:
        op.create_index("ix_suppliers_provider_key", name, ["provider_key"])
    if bind.dialect.name != "postgresql":
        return
    op.execute(sa.text(f'ALTER TABLE "{name}" ENABLE ROW LEVEL SECURITY'))
    op.execute(sa.text(f'ALTER TABLE "{name}" FORCE ROW LEVEL SECURITY'))
    predicate = "tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::integer"
    op.execute(sa.text(f'DROP POLICY IF EXISTS karenseir_tenant_isolation ON "{name}"'))
    op.execute(sa.text(f'CREATE POLICY karenseir_tenant_isolation ON "{name}" USING ({predicate}) WITH CHECK ({predicate})'))
    if bind.scalar(sa.text("SELECT count(*) FROM pg_roles WHERE rolname='karenseir_api'")):
        op.execute(sa.text(f'GRANT SELECT, INSERT, UPDATE ON "{name}" TO karenseir_api'))


def downgrade():
    raise RuntimeError("Supplier connection columns are retained")
