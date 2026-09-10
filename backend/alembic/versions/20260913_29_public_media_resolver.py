"""Narrowly-scoped SECURITY DEFINER lookup for public supplier media.

An anonymous /media/public/{id} request has no tenant claim, so it cannot read
supplier_assets under RLS. This function -- owned by the existing NOLOGIN
BYPASSRLS role, same pattern as find_login_identity -- returns the storage key
for an asset ONLY when it is explicitly visibility='public' AND status='active'.
Private, deleted, or replaced-away assets return no row (=> 404). It exposes no
listing and no private data.

Revision ID: 20260913_29
Revises: 20260913_28
"""
import sqlalchemy as sa
from alembic import op

revision = "20260913_29"
down_revision = "20260913_28"
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
    op.execute(sa.text("GRANT SELECT ON supplier_assets TO karenseir_identity_resolver"))
    op.execute(sa.text("""
        CREATE OR REPLACE FUNCTION public.find_public_media_asset(p_asset_id text)
        RETURNS TABLE(tenant_id integer, storage_key text, content_type text)
        LANGUAGE sql
        SECURITY DEFINER
        SET search_path = public
        AS $func$
            SELECT tenant_id, storage_key, content_type
            FROM supplier_assets
            WHERE id = p_asset_id AND visibility = 'public' AND status = 'active';
        $func$;
    """))
    op.execute(sa.text("ALTER FUNCTION public.find_public_media_asset(text) OWNER TO karenseir_identity_resolver"))
    op.execute(sa.text("REVOKE ALL ON FUNCTION public.find_public_media_asset(text) FROM PUBLIC"))
    op.execute(sa.text("""
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'karenseir_api') THEN
                EXECUTE 'GRANT EXECUTE ON FUNCTION public.find_public_media_asset(text) TO karenseir_api';
            END IF;
        END $$;
    """))


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    op.execute(sa.text("DROP FUNCTION IF EXISTS public.find_public_media_asset(text)"))
