"""Organization authority comes from membership, not from the global role (Launch V1 item 8.3, owner decision 2026-11-24).

Every person's global role (users.role) is `customer` unless they are staff of the company itself (operations, finance,
admin, agency, supplier). What a person may do inside an organization comes only from that organization:
`employee_assignments` (membership) + `enterprise_grants` (permissions in that organization). Every check here is scoped
by tenant and organization; a grant in organization A says nothing about organization B.

Transition: accounts that still carry a legacy organization role (employee / manager / welfare_manager / organization_admin)
keep working. Inside an organization they are members of, the legacy role counts as the grant set below, which is exactly
what migration 20261124_78 writes into `enterprise_grants` before it sets their role to `customer`. Outside their
organizations a legacy role gives nothing organizational.
"""
from __future__ import annotations

import json
from typing import Iterable, Optional

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from . import enterprise_models as e
from . import operations as m
from .security import role_has_permission

ORG_PERMISSIONS = frozenset({"requests.read_all", "requests.on_behalf", "requests.approve", "policy.manage", "roles.manage", "rfq.manage", "benefits.manage"})

# Legacy global organization role -> the organization grants it stands for (used by guards and by migration 20261124_78).
LEGACY_ORG_ROLE_GRANTS: dict[str, frozenset[str]] = {
    "employee": frozenset(),
    "manager": frozenset({"requests.read_all", "requests.approve"}),
    "welfare_manager": frozenset({"requests.read_all", "requests.approve", "benefits.manage"}),
    "organization_admin": ORG_PERMISSIONS,
}
LEGACY_ORG_ROLES = tuple(LEGACY_ORG_ROLE_GRANTS)

# Page/endpoint groups (mirrored in lib/panel-context.ts).
RECORDS = frozenset({"requests.read_all", "policy.manage", "roles.manage"})       # organization-wide records
STRUCTURE_MANAGE = frozenset({"roles.manage"})                                       # departments / cost centers / approval templates
PASSENGERS = frozenset({"roles.manage", "requests.read_all", "requests.on_behalf"})  # saved passengers of the organization


def is_tenant_staff(user) -> bool:
    """Staff of the company itself who manage every organization of their tenant (not an organization role)."""
    return role_has_permission(user.role, "tenant:manage")


def organization(db: Session, user, org_id: str, *, active: bool = False) -> Optional[m.Organization]:
    q = select(m.Organization).where(m.Organization.tenant_id == user.tenant_id, m.Organization.id == org_id)
    if active:
        q = q.where(m.Organization.status == "active")
    return db.scalar(q)


def is_member(db: Session, user, org_id: str) -> bool:
    return db.scalar(select(m.EmployeeAssignment.id).where(
        m.EmployeeAssignment.tenant_id == user.tenant_id, m.EmployeeAssignment.user_id == user.id,
        m.EmployeeAssignment.organization_id == org_id)) is not None


def granted(db: Session, user, org_id: str) -> set[str]:
    """Permissions of a member in one organization: the stored grant plus (transition) what a legacy organization role stands for."""
    row = db.scalar(select(e.EnterpriseGrant).where(
        e.EnterpriseGrant.tenant_id == user.tenant_id, e.EnterpriseGrant.organization_id == org_id, e.EnterpriseGrant.user_id == user.id))
    stored = set(json.loads(row.permissions_json)) & ORG_PERMISSIONS if row else set()
    return stored | set(LEGACY_ORG_ROLE_GRANTS.get(user.role, ()))


def member_permissions(db: Session, user, org_id: str) -> Optional[set[str]]:
    """None when the user is not a member of this organization (in their tenant); else their organization permissions."""
    if not is_member(db, user, org_id):
        return None
    return granted(db, user, org_id)


def has_org_permission(db: Session, user, org_id: str, any_of: Iterable[str]) -> bool:
    perms = member_permissions(db, user, org_id)
    return bool(perms and perms & set(any_of))


def require_org(db: Session, user, org_id: str, any_of: Iterable[str], *, staff: bool = True, lock: bool = False) -> m.Organization:
    """The organization (tenant-scoped) when the user may act on it: tenant staff (if `staff`), or a member holding one of `any_of`.
    An organization outside the user's tenant, or one they have nothing to do with, is a 404 so its existence is not revealed."""
    q = select(m.Organization).where(m.Organization.tenant_id == user.tenant_id, m.Organization.id == org_id)
    org = db.scalar(q.with_for_update() if lock else q)
    if org is None:
        raise HTTPException(404, "سازمان وجود ندارد")
    if staff and is_tenant_staff(user):
        return org
    perms = member_permissions(db, user, org_id)
    if perms is None:
        raise HTTPException(404, "سازمان وجود ندارد")
    if not perms & set(any_of):
        raise HTTPException(403, "مجوز سازمانی این عملیات را ندارید")
    return org


def org_ids_with(db: Session, user, any_of: Iterable[str]) -> list[str]:
    """Organizations of the user's tenant in which the user is a member holding one of `any_of`."""
    wanted = set(any_of)
    ids = db.scalars(select(m.EmployeeAssignment.organization_id).where(
        m.EmployeeAssignment.tenant_id == user.tenant_id, m.EmployeeAssignment.user_id == user.id)).all()
    return [org_id for org_id in ids if granted(db, user, org_id) & wanted]
