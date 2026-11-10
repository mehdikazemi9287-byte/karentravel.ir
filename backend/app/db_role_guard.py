"""Read-only check that the API connects with the restricted database role (KT-05).

The API must not run as a superuser, a BYPASSRLS role or the owner of the application
tables (an owner can switch row-level security off). Migrations use a separate owner
connection (the `migrate` compose service); the outbox worker has its own role.
Run as a release preflight with `python -m app.db_role_guard`.
"""
from __future__ import annotations

from sqlalchemy import text


def restricted_role_problems(connection) -> list[str]:
    if connection.dialect.name != "postgresql":
        return []
    row = connection.execute(text("SELECT current_user, rolsuper, rolbypassrls FROM pg_roles WHERE rolname = current_user")).one()
    problems = []
    if row.rolsuper:
        problems.append("superuser")
    if row.rolbypassrls:
        problems.append("bypassrls")
    owned = connection.scalar(text("SELECT count(*) FROM pg_tables WHERE schemaname = 'public' AND tableowner = current_user"))
    if owned:
        problems.append(f"owns {owned} tables")
    return problems


def assert_restricted_api_role(connection) -> None:
    problems = restricted_role_problems(connection)
    if problems:
        raise RuntimeError(
            "API database role is not restricted (" + ", ".join(problems) + "); "
            "connect the API as karenseir_api (deploy/provision-api-role.sql) and run migrations with the owner role only"
        )


if __name__ == "__main__":
    from .database import engine

    with engine.connect() as connection:
        assert_restricted_api_role(connection)
    print("API database role is restricted (NOSUPERUSER, NOBYPASSRLS, owns no tables)")
