#!/usr/bin/env bash
# KarenSeir — which PostgreSQL role does the API connect as? (security review H-4)
# Row-level security (tenant isolation) is ignored for a SUPERUSER or a BYPASSRLS role, so the API must use the
# non-superuser, NOBYPASSRLS role karenseir_api.
#   default / --check : read-only report (API role, rolsuper, rolbypassrls, karenseir_api state, RLS table count)
#   --apply           : create or update karenseir_api (NOSUPERUSER NOBYPASSRLS) with the grants of
#                       deploy/provision-api-role.sql and a fresh random password, then PRINT the DATABASE_URL change.
#                       It never edits .env / docker-compose.yml and never restarts anything: the owner switches over.
# Run from the Mac:
#   ssh karen@188.121.123.218 'bash -s -- --check' < ~/Downloads/karenseir-db-role-check.sh
#   ssh karen@188.121.123.218 'bash -s -- --apply' < ~/Downloads/karenseir-db-role-check.sh
main() {
set -euo pipefail
local apply=0
for a in "$@"; do case "$a" in --check) apply=0;; --apply) apply=1;; *) echo "ABORT: unknown option $a"; exit 1;; esac; done

ROOT=${KARENSEIR_ROOT:-/opt/karenseir}
APP=$ROOT/app
TS=$(date -u +%Y%m%d-%H%M%S)
cd "$ROOT"
PSQL=(docker compose exec -T db psql -U karenseir -d karenseir -At -v ON_ERROR_STOP=1)
q() { "${PSQL[@]}" -c "$1"; }

echo "== 1/3 role the running API connects as (asked through the API's own DATABASE_URL; no password printed)"
api_role=$(docker compose exec -T api python -c "from sqlalchemy import text; from app.database import engine
with engine.connect() as c: print('|'.join(str(v) for v in c.execute(text('select current_user, r.rolsuper, r.rolbypassrls from pg_roles r where r.rolname = current_user')).one()))" 2>/dev/null | tail -1) || true
if [ -z "$api_role" ]; then echo "ABORT: could not ask the api container (is it running? docker compose ps)"; exit 2; fi
IFS='|' read -r role super bypass <<< "$api_role"
echo "api connects as: $role   rolsuper=$super   rolbypassrls=$bypass"
if [ "$super" = True ] || [ "$bypass" = True ]; then
  echo "RESULT: H-4 OPEN — tenant isolation (RLS) is NOT enforced for API queries"
else
  echo "RESULT: OK — API role is subject to RLS"
fi

echo "== 2/3 database state"
existing=$(q "select rolname||'|'||rolsuper||'|'||rolbypassrls||'|'||rolcanlogin from pg_roles where rolname='karenseir_api';")
echo "karenseir_api: ${existing:-does not exist}   (name|super|bypassrls|login)"
echo "worker role:   $(q "select coalesce(string_agg(rolname||'|'||rolsuper||'|'||rolbypassrls, ', '),'none') from pg_roles where rolname='karenseir_worker';")"
echo "tables with tenant_id: $(q "select count(distinct c.table_name) from information_schema.columns c where c.table_schema='public' and c.column_name='tenant_id';")   with RLS+FORCE: $(q "select count(*) from pg_class k join pg_namespace n on n.oid=k.relnamespace where n.nspname='public' and k.relkind='r' and k.relrowsecurity and k.relforcerowsecurity;")"
if [ "$apply" = 0 ]; then echo "DB-ROLE-CHECK-OK (read-only, nothing changed)"; return 0; fi

if [ "$role" = karenseir_api ] && [ "$super" != True ] && [ "$bypass" != True ]; then
  echo "nothing to do: the API already uses karenseir_api without superuser/bypass"; return 0
fi
[ -f "$APP/deploy/provision-api-role.sql" ] || { echo "ABORT: $APP/deploy/provision-api-role.sql not found (deploy a release that has it)"; exit 2; }

echo "== 3/3 create/update karenseir_api (NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS) + grants"
"$ROOT/backup.sh"
pw=$(openssl rand -hex 24)
docker compose exec -T db psql -U karenseir -d karenseir -q -v ON_ERROR_STOP=1 -v "api_password=$pw" -f - < "$APP/deploy/provision-api-role.sql" >/dev/null
echo "role now: $(q "select rolname||' super='||rolsuper||' bypassrls='||rolbypassrls||' login='||rolcanlogin from pg_roles where rolname='karenseir_api';")"
URL_FILE="$ROOT/karenseir_api.database_url"
( umask 077; printf 'postgresql+psycopg://karenseir_api:%s@db:5432/karenseir\n' "$pw" > "$URL_FILE" )
echo
echo "NOTHING ELSE WAS CHANGED. To switch the API over (owner, by hand):"
echo "  1. new value (secret, file mode 600):  cat $URL_FILE"
echo "     masked: postgresql+psycopg://karenseir_api:****@db:5432/karenseir"
echo "  2. in $ROOT/docker-compose.yml, service api -> environment -> DATABASE_URL: replace"
echo "       postgresql+psycopg://karenseir:\${POSTGRES_PASSWORD}@db:5432/karenseir"
echo "     with the value from step 1 (keep the worker's WORKER_DATABASE_URL as it is)."
echo "  3. migrations need the owner role, not karenseir_api: add to $ROOT/.env"
echo "       MIGRATION_DATABASE_URL=postgresql+psycopg://karenseir:<POSTGRES_PASSWORD>@db:5432/karenseir"
echo "     (karenseir-deploy-server.sh uses it for 'alembic upgrade head' when present)"
echo "  4. cd $ROOT && docker compose up -d api && curl -fsS -H 'Host: karentravel.ir' http://127.0.0.1/api/health"
echo "  5. re-run this script with --check: expect 'RESULT: OK'"
echo "undo: put the old DATABASE_URL line back in docker-compose.yml and 'docker compose up -d api'."
if [ -z "$existing" ]; then echo "      the role was created now ($TS); to remove it: docker compose exec -T db psql -U karenseir -d karenseir -c 'DROP OWNED BY karenseir_api; DROP ROLE karenseir_api;'"; fi
}
main "$@" </dev/null
