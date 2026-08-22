"""Add a narrowly-scoped SECURITY DEFINER identity-lookup function so
cross-tenant identity resolution (dev-login today; any future login path
that must find a user before a tenant is known) never needs a role with
broad RLS bypass. The function is owned by a NOLOGIN role that exists only
to own it -- nobody can connect as that role, and it exposes exactly one
narrow, non-sensitive query (id/tenant_id/name/role by email), nothing else.

Revision ID: 20260822_17
Revises: 20260822_16
"""
import sqlalchemy as sa
from alembic import op

revision = "20260822_17"
down_revision = "20260822_16"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    op.execute(sa.text("""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'karenseir_identity_resolver') THEN
                CREATE ROLE karenseir_identity_resolver NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE BYPASSRLS;
            END IF;
        END $$;
    """))
    # BYPASSRLS only bypasses row-security policies; it grants no table access on its
    # own. This role still needs an explicit, minimal SELECT grant on the one table
    # the function reads -- nothing else.
    op.execute(sa.text("GRANT SELECT ON users TO karenseir_identity_resolver"))
    op.execute(sa.text("""
        CREATE OR REPLACE FUNCTION public.find_login_identity(p_email text)
        RETURNS TABLE(user_id integer, tenant_id integer, user_name text, user_role text)
        LANGUAGE sql
        SECURITY DEFINER
        SET search_path = public
        AS $func$
            SELECT id, tenant_id, name, role FROM users WHERE email = p_email;
        $func$;
    """))
    op.execute(sa.text("ALTER FUNCTION public.find_login_identity(text) OWNER TO karenseir_identity_resolver"))
    op.execute(sa.text("REVOKE ALL ON FUNCTION public.find_login_identity(text) FROM PUBLIC"))
    # EXECUTE is granted to the API role separately by deploy/provision-api-role.sql,
    # matching the established convention that role grants live outside migrations.


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    op.execute(sa.text("DROP FUNCTION IF EXISTS public.find_login_identity(text)"))
