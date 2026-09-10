"""Backfill SupplierMembership rows for suppliers that predate the explicit
supplier-portal ownership boundary (migration 20260913_27).

Without a membership row, _supplier_scope() returns nothing and the owning user
is locked out of every /supplier/* route. New onboarding self-heals (it inserts
the membership); this script repairs suppliers created before that.

Mapping rule (deterministic, conservative):
  * A supplier with >=1 existing membership is left untouched.
  * A supplier with 0 memberships is assigned role="owner" to the *single*
    role="supplier" user in its tenant.
  * Tenants with 0 or >1 supplier-role users are reported, never guessed.

Dry-run by default. Pass --apply (or APPLY=1) to commit. Safe to re-run.
"""
from __future__ import annotations

import os
import sys

from sqlalchemy import func, select

from app.database import set_tenant_context
from app.main import SessionLocal, Tenant, User
from app.operations import Supplier, SupplierMembership


def main() -> int:
    apply = "--apply" in sys.argv or os.getenv("APPLY") == "1"
    created = skipped = ambiguous = 0
    with SessionLocal() as db:
        for tenant in db.scalars(select(Tenant).order_by(Tenant.id)).all():
            set_tenant_context(db, tenant.id)
            supplier_users = db.scalars(
                select(User).where(User.tenant_id == tenant.id, User.role == "supplier")
            ).all()
            suppliers = db.scalars(select(Supplier).where(Supplier.tenant_id == tenant.id)).all()
            if not suppliers:
                continue
            for sup in suppliers:
                has = db.scalar(
                    select(func.count()).select_from(SupplierMembership).where(
                        SupplierMembership.tenant_id == tenant.id,
                        SupplierMembership.supplier_id == sup.id,
                    )
                )
                if has:
                    skipped += 1
                    continue
                if len(supplier_users) != 1:
                    ambiguous += 1
                    print(f"  MANUAL  tenant={tenant.slug} supplier={sup.id} "
                          f"({sup.display_name!r}) — {len(supplier_users)} supplier-role users")
                    continue
                owner = supplier_users[0]
                print(f"  ASSIGN  tenant={tenant.slug} supplier={sup.id} "
                      f"({sup.display_name!r}) -> user={owner.id} ({owner.email})")
                if apply:
                    db.add(SupplierMembership(
                        tenant_id=tenant.id, user_id=owner.id, supplier_id=sup.id, role="owner"))
                created += 1
        if apply:
            db.commit()
    mode = "APPLIED" if apply else "DRY-RUN (pass --apply to commit)"
    print(f"\n{mode}: {created} membership(s) to create, {skipped} already owned, "
          f"{ambiguous} need manual assignment")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
