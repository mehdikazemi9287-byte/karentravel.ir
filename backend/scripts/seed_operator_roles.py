"""Idempotent, tenant-scoped bootstrap of operator-role users.

The corporate tenants seed only employee / welfare_manager / supplier /
organization_admin, so the agency, backoffice, finance and tenant-admin portals
have no user to reach them. This creates exactly one operator user per
(tenant, role) for the corporate tenants, with a deterministic, non-guessable
email. Users in this system have no password column -- they authenticate via OTP
-- so this provisions identity + RBAC only; operational sign-in still depends on
the (externally-blocked) OTP provider.

Safe to re-run. Never touches existing users. Skips the public-catalog tenant.
Its stdout is the audit record for this one-off bootstrap.
"""
from __future__ import annotations

import os
import sys

from sqlalchemy import select

from app.database import set_tenant_context
from app.main import SessionLocal, Tenant, User

OPERATOR_ROLES = ("agency_partner", "backoffice_expert", "finance_operator", "tenant_admin")
SKIP_TENANT_SLUGS = {"karenseir-public"}
EMAIL_TMPL = "ops.{role}@{slug}.operators.karenseir"


def main() -> int:
    apply = "--apply" in sys.argv or os.getenv("APPLY") == "1"
    created = skipped = 0
    with SessionLocal() as db:
        for tenant in db.scalars(select(Tenant).order_by(Tenant.id)).all():
            if tenant.slug in SKIP_TENANT_SLUGS:
                continue
            set_tenant_context(db, tenant.id)
            for role in OPERATOR_ROLES:
                if db.scalar(select(User.id).where(User.tenant_id == tenant.id, User.role == role).limit(1)):
                    skipped += 1
                    continue
                email = EMAIL_TMPL.format(role=role, slug=tenant.slug)
                if db.scalar(select(User.id).where(User.tenant_id == tenant.id, User.email == email)):
                    skipped += 1
                    continue
                print(f"  CREATE tenant={tenant.slug} role={role} email={email}")
                created += 1
                if apply:
                    # flush per row while THIS tenant's RLS context is active
                    db.add(User(tenant_id=tenant.id, email=email, name=f"اپراتور {role}", role=role))
                    db.flush()
        if apply:
            db.commit()
    print(f"\n{'APPLIED' if apply else 'DRY-RUN (pass --apply)'}: {created} to create, {skipped} already present")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
