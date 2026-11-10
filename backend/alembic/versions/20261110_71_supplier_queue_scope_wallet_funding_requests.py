"""booking_items.supplier_id/fulfillment_mode for SQL-side supplier queue scope (KT-04);
wallet_funding_requests for maker-checker wallet top-ups (KT-07). Additive only.

Revision ID: 20261110_71
Revises: 20261109_70
"""
import json

from alembic import op
import sqlalchemy as sa

revision = "20261110_71"
down_revision = "20261109_70"
branch_labels = None
depends_on = None


def _scope(snapshot_json):
    try:
        snap = json.loads(snapshot_json or "{}")
    except (TypeError, ValueError):
        return None, None
    if not isinstance(snap, dict):
        return None, None
    supplier, mode = snap.get("supplier_id"), snap.get("fulfillment_mode")
    return (str(supplier)[:36] if supplier else None), (str(mode)[:32] if mode else None)


def upgrade() -> None:
    from app.database import Base
    import app.operations  # noqa: F401  registers wallet_funding_requests on Base.metadata

    bind = op.get_bind()
    columns = {c["name"] for c in sa.inspect(bind).get_columns("booking_items")}
    if "supplier_id" not in columns:
        op.add_column("booking_items", sa.Column("supplier_id", sa.String(36), nullable=True))
    if "fulfillment_mode" not in columns:
        op.add_column("booking_items", sa.Column("fulfillment_mode", sa.String(32), nullable=True))
    if "ix_booking_items_supplier_id" not in {i["name"] for i in sa.inspect(bind).get_indexes("booking_items")}:
        op.create_index("ix_booking_items_supplier_id", "booking_items", ["supplier_id"])

    # Backfill per tenant: booking_items is tenant-isolated (FORCE RLS on PostgreSQL), so the
    # tenant context is set before each tenant's rows are read and updated.
    tenant_ids = [row[0] for row in bind.execute(sa.text("SELECT id FROM tenants ORDER BY id"))]
    for tenant_id in tenant_ids:
        if bind.dialect.name == "postgresql":
            bind.execute(sa.text("SELECT set_config('app.tenant_id', :t, true)"), {"t": str(tenant_id)})
        rows = bind.execute(sa.text("SELECT id, snapshot_json FROM booking_items WHERE tenant_id = :t AND supplier_id IS NULL AND fulfillment_mode IS NULL"), {"t": tenant_id}).all()
        for item_id, snapshot_json in rows:
            supplier_id, mode = _scope(snapshot_json)
            if supplier_id or mode:
                bind.execute(sa.text("UPDATE booking_items SET supplier_id = :s, fulfillment_mode = :m WHERE id = :i AND tenant_id = :t"), {"s": supplier_id, "m": mode, "i": item_id, "t": tenant_id})
    if bind.dialect.name == "postgresql":
        bind.execute(sa.text("SELECT set_config('app.tenant_id', '', true)"))

    Base.metadata.tables["wallet_funding_requests"].create(bind, checkfirst=True)
    if bind.dialect.name != "postgresql":
        return
    predicate = "tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::integer"
    name = "wallet_funding_requests"
    op.execute(sa.text(f'ALTER TABLE "{name}" ENABLE ROW LEVEL SECURITY'))
    op.execute(sa.text(f'ALTER TABLE "{name}" FORCE ROW LEVEL SECURITY'))
    op.execute(sa.text(f'DROP POLICY IF EXISTS karenseir_tenant_isolation ON "{name}"'))
    op.execute(sa.text(f'CREATE POLICY karenseir_tenant_isolation ON "{name}" USING ({predicate}) WITH CHECK ({predicate})'))
    if bind.scalar(sa.text("SELECT count(*) FROM pg_roles WHERE rolname='karenseir_api'")):
        op.execute(sa.text(f'GRANT SELECT, INSERT, UPDATE ON "{name}" TO karenseir_api'))


def downgrade() -> None:
    raise RuntimeError("wallet funding requests are financial evidence; restore from backup instead of downgrading")
