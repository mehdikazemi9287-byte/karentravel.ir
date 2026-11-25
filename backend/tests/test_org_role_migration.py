"""Migration 20261124_78 (legacy organization roles -> customer + organization grants): upgrade, idempotent re-run, exact downgrade.
Runs the revision's own upgrade()/downgrade() on a throw-away SQLite database (PostgreSQL RLS path: see the PR QA notes)."""
import importlib.util
import json
from pathlib import Path

import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations

from app.database import Base

MIGRATION = Path(__file__).resolve().parents[1] / 'alembic' / 'versions' / '20261124_78_org_roles_to_grants.py'


def _load():
    spec = importlib.util.spec_from_file_location('mig78', MIGRATION)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


def _run(engine, fn):
    with engine.begin() as conn:
        with Operations.context(MigrationContext.configure(conn)):
            fn()


def _state(engine):
    with engine.connect() as conn:
        users = dict(conn.execute(sa.text('SELECT email, role FROM users ORDER BY email')).all())
        grants = {(e, o): json.loads(p) for e, o, p in conn.execute(sa.text(
            'SELECT u.email, g.organization_id, g.permissions_json FROM enterprise_grants g JOIN users u ON u.id = g.user_id')).all()}
    return users, grants


def test_upgrade_idempotent_and_downgrade_restores(tmp_path):
    mig = _load()
    assert mig.down_revision == '20261112_77' and mig.revision == '20261124_78'
    engine = sa.create_engine(f'sqlite:///{tmp_path}/mig.db')
    Base.metadata.create_all(engine)
    with engine.begin() as c:
        c.execute(sa.text('DROP TABLE org_role_migration_backups'))
        now = '2026-11-24 00:00:00'
        for tid in (1, 2):
            c.execute(sa.text("INSERT INTO tenants (id, slug, name, primary_color) VALUES (:i, :s, :s, '#000000')"), {'i': tid, 's': f't{tid}'})
        users = [(1, 1, 'mgr', 'manager'), (2, 1, 'welfare', 'welfare_manager'), (3, 1, 'admin', 'organization_admin'), (4, 1, 'emp', 'employee'),
                 (5, 1, 'lonely', 'manager'), (6, 1, 'cust', 'customer'), (7, 1, 'ops', 'backoffice_expert'), (8, 2, 'admin2', 'organization_admin'),
                 (9, 1, 'emp-no-org', 'employee')]
        for uid, tid, email, role in users:
            c.execute(sa.text('INSERT INTO users (id, tenant_id, email, name, role) VALUES (:i, :t, :e, :e, :r)'), {'i': uid, 't': tid, 'e': email, 'r': role})
        for oid, tid in (('A', 1), ('B', 1), ('X', 2)):
            c.execute(sa.text("INSERT INTO organizations (id, tenant_id, name, status, created_at, updated_at) VALUES (:o, :t, :o, 'active', :n, :n)"), {'o': oid, 't': tid, 'n': now})
        for n, (uid, tid, oid) in enumerate([(1, 1, 'A'), (1, 1, 'B'), (2, 1, 'A'), (3, 1, 'A'), (4, 1, 'A'), (6, 1, 'A'), (8, 2, 'X')]):
            c.execute(sa.text('INSERT INTO employee_assignments (id, tenant_id, user_id, organization_id, created_at, updated_at) VALUES (:i, :t, :u, :o, :n, :n)'),
                      {'i': f'ea{n}', 't': tid, 'u': uid, 'o': oid, 'n': now})
        c.execute(sa.text("INSERT INTO enterprise_grants (id, tenant_id, organization_id, user_id, permissions_json, created_at, updated_at) VALUES ('g1', 1, 'B', 1, :p, :n, :n)"),
                  {'p': json.dumps(['policy.manage']), 'n': now})
    before = _state(engine)

    _run(engine, mig.upgrade)
    users, grants = _state(engine)
    assert users == {'mgr': 'customer', 'welfare': 'customer', 'admin': 'customer', 'emp': 'customer', 'emp-no-org': 'customer',
                     'lonely': 'manager',            # no membership: left for an admin to resolve
                     'cust': 'customer', 'ops': 'backoffice_expert', 'admin2': 'customer'}
    assert grants[('mgr', 'A')] == ['requests.approve', 'requests.read_all']
    assert grants[('mgr', 'B')] == ['policy.manage', 'requests.approve', 'requests.read_all']    # union with the existing grant
    assert grants[('welfare', 'A')] == ['benefits.manage', 'requests.approve', 'requests.read_all']
    assert grants[('admin', 'A')] == mig.ALL and grants[('admin2', 'X')] == mig.ALL                # each in its own tenant/org only
    assert ('admin', 'B') not in grants and ('emp', 'A') not in grants and ('cust', 'A') not in grants

    _run(engine, mig.upgrade)                                                                    # second run changes nothing
    assert _state(engine) == (users, grants)

    _run(engine, mig.downgrade)
    assert _state(engine) == before
    assert 'org_role_migration_backups' not in sa.inspect(engine).get_table_names()
