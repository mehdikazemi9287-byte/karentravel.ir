"""Launch V1 item 8.3 (owner decision 2026-11-24): everyone is a customer; organization authority comes from membership.

DATA MIGRATION - the owner must approve it before it is deployed (deploy runs `alembic upgrade head`).

For every account whose global role is a legacy organization role (employee, manager, welfare_manager, organization_admin):
1. In each organization the account is already a member of (employee_assignments, same tenant), the grant the role stood
   for is added to enterprise_grants (union with any existing grant; nothing is removed):
     employee -> none, manager -> requests.read_all + requests.approve,
     welfare_manager -> + benefits.manage, organization_admin -> all organization permissions (app/org_access.py).
2. The previous role and each previous grant (or "none") are stored in org_role_migration_backups.
3. users.role is set to `customer`.
Accounts with manager / welfare_manager / organization_admin but NO membership are left unchanged (there is no organization
to carry their authority to); they are counted in the log so an admin can add the membership and re-run. `employee` has the
same permissions as `customer`, so it is converted even without a membership.
Staff roles (backoffice_expert, finance_operator, tenant_admin, platform_admin, agency_partner, supplier) are not touched.

Idempotent: an account that already has a backup row is skipped, so a second run changes nothing.
Downgrade restores every backed-up account's role and grants exactly as they were before (grant edits made after the
upgrade on those rows are overwritten), then drops the backup table.

Revision ID: 20261124_78
Revises: 20261112_77
"""
import json
import logging
import uuid
from datetime import datetime, timezone

import sqlalchemy as sa
from alembic import op

revision = "20261124_78"
down_revision = "20261112_77"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")
TABLE = "org_role_migration_backups"
ALL = ["benefits.manage", "policy.manage", "requests.approve", "requests.on_behalf", "requests.read_all", "rfq.manage", "roles.manage"]
# Frozen copy of app/org_access.py::LEGACY_ORG_ROLE_GRANTS at the time of this revision (a migration must not follow later code edits).
LEGACY = {
    "employee": [],
    "manager": ["requests.approve", "requests.read_all"],
    "welfare_manager": ["benefits.manage", "requests.approve", "requests.read_all"],
    "organization_admin": ALL,
}


def _tenant_scope(bind, tenant_id: int) -> None:
    """Users, memberships and grants are FORCE ROW LEVEL SECURITY tables on PostgreSQL: act inside one tenant at a time."""
    if bind.dialect.name == "postgresql":
        bind.execute(sa.text("SELECT set_config('app.tenant_id', :t, true)"), {"t": str(tenant_id)})


def _create_backup_table(bind) -> None:
    from app.database import Base
    import app.enterprise_models  # noqa: F401  registers the table on Base.metadata

    Base.metadata.tables[TABLE].create(bind, checkfirst=True)
    if bind.dialect.name != "postgresql":
        return
    predicate = "tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::integer"
    op.execute(sa.text(f'ALTER TABLE "{TABLE}" ENABLE ROW LEVEL SECURITY'))
    op.execute(sa.text(f'ALTER TABLE "{TABLE}" FORCE ROW LEVEL SECURITY'))
    op.execute(sa.text(f'DROP POLICY IF EXISTS karenseir_tenant_isolation ON "{TABLE}"'))
    op.execute(sa.text(f'CREATE POLICY karenseir_tenant_isolation ON "{TABLE}" USING ({predicate}) WITH CHECK ({predicate})'))
    if bind.scalar(sa.text("SELECT count(*) FROM pg_roles WHERE rolname='karenseir_api'")):
        # The API never writes this table; read-only for support.
        op.execute(sa.text(f'GRANT SELECT ON "{TABLE}" TO karenseir_api'))
        op.execute(sa.text(f'REVOKE INSERT, UPDATE, DELETE ON "{TABLE}" FROM karenseir_api'))


def upgrade() -> None:
    bind = op.get_bind()
    _create_backup_table(bind)
    now = datetime.now(timezone.utc)
    converted = skipped_no_org = already = 0
    for (tenant_id,) in bind.execute(sa.text("SELECT id FROM tenants ORDER BY id")).all():
        _tenant_scope(bind, tenant_id)
        users = bind.execute(sa.text("SELECT id, role FROM users WHERE tenant_id = :t AND role IN ('employee', 'manager', 'welfare_manager', 'organization_admin') ORDER BY id"),
                             {"t": tenant_id}).all()
        for user_id, role in users:
            if bind.scalar(sa.text(f'SELECT 1 FROM "{TABLE}" WHERE tenant_id = :t AND user_id = :u'), {"t": tenant_id, "u": user_id}):
                already += 1
                continue
            orgs = [row[0] for row in bind.execute(sa.text(
                "SELECT organization_id FROM employee_assignments WHERE tenant_id = :t AND user_id = :u ORDER BY organization_id"),
                {"t": tenant_id, "u": user_id}).all()]
            wanted = set(LEGACY[role])
            if wanted and not orgs:
                skipped_no_org += 1
                continue
            previous: dict[str, list[str] | None] = {}
            for org_id in orgs:
                grant = bind.execute(sa.text(
                    "SELECT id, permissions_json FROM enterprise_grants WHERE tenant_id = :t AND organization_id = :o AND user_id = :u"),
                    {"t": tenant_id, "o": org_id, "u": user_id}).first()
                old = json.loads(grant[1]) if grant else None
                previous[org_id] = old
                if not wanted:
                    continue
                merged = json.dumps(sorted(set(old or []) | wanted))
                if grant:
                    bind.execute(sa.text("UPDATE enterprise_grants SET permissions_json = :p, updated_at = :now WHERE id = :id AND tenant_id = :t"),
                                 {"p": merged, "now": now, "id": grant[0], "t": tenant_id})
                else:
                    bind.execute(sa.text("INSERT INTO enterprise_grants (id, tenant_id, organization_id, user_id, permissions_json, created_at, updated_at) "
                                         "VALUES (:id, :t, :o, :u, :p, :now, :now)"),
                                 {"id": str(uuid.uuid4()), "t": tenant_id, "o": org_id, "u": user_id, "p": merged, "now": now})
            bind.execute(sa.text(f'INSERT INTO "{TABLE}" (id, tenant_id, user_id, previous_role, previous_grants_json, created_at, updated_at) '
                                 "VALUES (:id, :t, :u, :r, :g, :now, :now)"),
                         {"id": str(uuid.uuid4()), "t": tenant_id, "u": user_id, "r": role, "g": json.dumps(previous, sort_keys=True), "now": now})
            bind.execute(sa.text("UPDATE users SET role = 'customer' WHERE id = :u AND tenant_id = :t"), {"u": user_id, "t": tenant_id})
            converted += 1
    log.info("org roles -> grants: converted=%s skipped_without_membership=%s already_migrated=%s", converted, skipped_no_org, already)


def downgrade() -> None:
    bind = op.get_bind()
    if TABLE in set(sa.inspect(bind).get_table_names()):
        now = datetime.now(timezone.utc)
        for (tenant_id,) in bind.execute(sa.text("SELECT id FROM tenants ORDER BY id")).all():
            _tenant_scope(bind, tenant_id)
            rows = bind.execute(sa.text(f'SELECT user_id, previous_role, previous_grants_json FROM "{TABLE}" WHERE tenant_id = :t'), {"t": tenant_id}).all()
            for user_id, previous_role, previous_json in rows:
                for org_id, old in json.loads(previous_json or "{}").items():
                    params = {"t": tenant_id, "o": org_id, "u": user_id}
                    if old is None:
                        bind.execute(sa.text("DELETE FROM enterprise_grants WHERE tenant_id = :t AND organization_id = :o AND user_id = :u"), params)
                    else:
                        bind.execute(sa.text("UPDATE enterprise_grants SET permissions_json = :p, updated_at = :now WHERE tenant_id = :t AND organization_id = :o AND user_id = :u"),
                                     {**params, "p": json.dumps(old), "now": now})
                bind.execute(sa.text("UPDATE users SET role = :r WHERE id = :u AND tenant_id = :t"), {"r": previous_role, "u": user_id, "t": tenant_id})
        op.drop_table(TABLE)
