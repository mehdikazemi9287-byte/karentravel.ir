"""Set the fixed login password of one staff account, from the server console only.

Owner request 1405-09-08 (docs/product/approvals.md): while SMS OTP delivery is blocked, staff sign in at
/login -> «ورود با رمز». There is deliberately no web endpoint for setting a password; this script is the only way.

Run inside the api container (see docs/ops/STAFF_PASSWORD_LOGIN.md):
    cd /opt/karenseir && docker compose exec api python -m scripts.set_staff_password --list
    cd /opt/karenseir && docker compose exec api python -m scripts.set_staff_password --tenant <slug> --mobile 09xxxxxxxxx

* The password is asked twice with getpass (hidden); it is never an argument, never printed and never logged.
* Only staff roles (backoffice_expert, finance_operator, tenant_admin, platform_admin) may get a password;
  customers and organization roles are refused. A disabled account is refused.
* Every change writes an authentication audit row (action "password.set"). Nothing is deleted.
"""
from __future__ import annotations

import argparse
import getpass
import json
import sys
from typing import Callable, Optional, Sequence

from sqlalchemy import select

from app import operations as operational_models
from app.database import set_tenant_context
from app.main import STAFF_PASSWORD_ROLES, SessionLocal, Tenant, User, _account_disabled, _find_login_user
from app.security import hash_password


def _mask(value: Optional[str]) -> str:
    if not value:
        return "-"
    if "@" in value:
        name, _, domain = value.partition("@")
        return (name[:2] + "***@" + domain) if name else "***@" + domain
    return value[:5] + "****" + value[-3:] if len(value) > 8 else "****"


def list_staff(out=print) -> int:
    """Read-only: staff accounts that may get a password, with masked contact and whether one is set."""
    with SessionLocal() as db:
        for tenant in db.scalars(select(Tenant).order_by(Tenant.id)).all():
            set_tenant_context(db, tenant.id)
            rows = db.scalars(select(User).where(User.tenant_id == tenant.id, User.role.in_(sorted(STAFF_PASSWORD_ROLES))).order_by(User.id)).all()
            for user in rows:
                state = "disabled" if _account_disabled(db, user) else "active"
                has = "yes" if user.password_hash else "no"
                out(f"tenant={tenant.slug}  user_id={user.id}  role={user.role}  mobile={_mask(user.mobile_e164)}  email={_mask(user.email)}  {state}  password_set={has}")
    return 0


def set_password(tenant_slug: str, identifier: str, *, prompt: Callable[[str], str] = getpass.getpass, out=print) -> int:
    with SessionLocal() as db:
        tenant = db.scalar(select(Tenant).where(Tenant.slug == tenant_slug))
        if tenant is None:
            out("خطا: این tenant پیدا نشد. با --list فهرست حساب‌های کارکنان را ببینید.")
            return 2
        set_tenant_context(db, tenant.id)
        user = _find_login_user(db, tenant.id, identifier)
        if user is None:
            out("خطا: حسابی با این شماره/ایمیل در این tenant پیدا نشد.")
            return 2
        if user.role not in STAFF_PASSWORD_ROLES:
            out(f"خطا: نقش این حساب ({user.role}) کارکنان/مدیر نیست؛ فقط حساب‌های کارکنان رمز می‌گیرند.")
            return 3
        if _account_disabled(db, user):
            out("خطا: این حساب یا tenant آن غیرفعال است.")
            return 3
        first = prompt("رمز جدید (حداقل ۱۰ کاراکتر؛ دیده نمی‌شود): ")
        second = prompt("تکرار رمز: ")
        if first != second:
            out("خطا: دو رمز یکسان نیستند؛ چیزی تغییر نکرد.")
            return 4
        try:
            encoded = hash_password(first)
        except ValueError:
            out("خطا: رمز باید حداقل ۱۰ کاراکتر باشد؛ چیزی تغییر نکرد.")
            return 4
        replaced = bool(user.password_hash)
        user.password_hash = encoded
        db.add(operational_models.AuthenticationAudit(tenant_id=tenant.id, user_id=user.id, action="password.set",
                                                       detail_json=json.dumps({"via": "server_console", "replaced": replaced})))
        db.commit()
        out(f"انجام شد: رمز حساب user_id={user.id} (نقش {user.role}، tenant {tenant.slug}) {'عوض' if replaced else 'تنظیم'} شد.")
        return 0


def main(argv: Optional[Sequence[str]] = None, *, prompt: Callable[[str], str] = getpass.getpass, require_tty: bool = True, out=print) -> int:
    parser = argparse.ArgumentParser(description="Set a staff account's login password (server console only).")
    parser.add_argument("--list", action="store_true", help="list staff accounts (masked), read-only")
    parser.add_argument("--tenant", help="tenant slug")
    who = parser.add_mutually_exclusive_group()
    who.add_argument("--mobile", help="account mobile, e.g. 09xxxxxxxxx")
    who.add_argument("--email", help="account email")
    args = parser.parse_args(argv)
    if args.list:
        return list_staff(out=out)
    if not args.tenant or not (args.mobile or args.email):
        parser.error("--tenant and one of --mobile/--email are required (or --list)")
    if require_tty and not sys.stdin.isatty():
        out("خطا: این دستور باید در کنسول تعاملی اجرا شود (docker compose exec بدون -T)، تا رمز مخفی پرسیده شود.")
        return 5
    return set_password(args.tenant, args.mobile or args.email, prompt=prompt, out=out)


if __name__ == "__main__":
    raise SystemExit(main())
