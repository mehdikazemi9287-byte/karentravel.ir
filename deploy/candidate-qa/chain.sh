#!/bin/bash
# Migration chain audit on a throwaway restore of the production dump (never touches production).
set -uo pipefail
W=~/ks-checkline-work; PG=ks-catalog-scratch-pg; IMG=karenseir-current-api:visible-slice19-enterprise-link
PW=$(docker inspect $PG --format '{{range .Config.Env}}{{println .}}{{end}}' | sed -n 's/^POSTGRES_PASSWORD=//p')
psql() { docker exec -i $PG psql -U postgres -v ON_ERROR_STOP=1 -At "$@"; }
run() { docker run --rm --network container:$PG -u $(id -u):$(id -g) -e HOME=/tmp -e PYTHONDONTWRITEBYTECODE=1 -e DATABASE_URL="postgresql+psycopg://postgres:$PW@127.0.0.1:5432/ks_chain" -v $W/run:/work -w /work $IMG "$@"; }
FP="select md5(string_agg(table_name||column_name||data_type||is_nullable, ',' order by table_name, ordinal_position)) from information_schema.columns where table_schema='public'"
rm -rf $W/run; mkdir -p $W/run; rsync -a --exclude __pycache__ --exclude '*.db' --exclude media $W/src/backend/ $W/run/
psql -c "DROP DATABASE IF EXISTS ks_chain" >/dev/null; psql -c "CREATE DATABASE ks_chain" >/dev/null
for r in karenseir karenseir_api karenseir_worker; do [ "$(psql -c "select count(*) from pg_roles where rolname='$r'")" = 0 ] && psql -c "CREATE ROLE $r NOLOGIN" >/dev/null && echo "$r" >> $W/tmp_roles; done
docker exec -i $PG pg_restore -U postgres -d ks_chain --no-owner < ~/backups/checkline-20261006/prod-karenseir.dump 2>&1 | tail -3
echo "start: $(psql -d ks_chain -c 'select version_num from alembic_version') tables=$(psql -d ks_chain -c "select count(*) from pg_tables where schemaname='public'") bookings=$(psql -d ks_chain -c 'select count(*) from bookings') users=$(psql -d ks_chain -c 'select count(*) from users')"
B=$(psql -d ks_chain -c "$FP")
run alembic upgrade head 2>&1 | grep -E "Running|Error|error" | cut -c1-150
echo "after up: $(psql -d ks_chain -c 'select version_num from alembic_version') bookings=$(psql -d ks_chain -c 'select count(*) from bookings') users=$(psql -d ks_chain -c 'select count(*) from users') catalog_hotels=$(psql -d ks_chain -c 'select count(*) from catalog_hotels')"
psql -d ks_chain -c "select 'api_grants', has_table_privilege('karenseir_api','catalog_hotels','SELECT'), has_table_privilege('karenseir_api','catalog_hotels','UPDATE'), has_table_privilege('karenseir_api','catalog_hotels','DELETE')"
run alembic downgrade 20260928_34 2>&1 | grep -cE "Running downgrade"
A=$(psql -d ks_chain -c "$FP"); echo "after down: $(psql -d ks_chain -c 'select version_num from alembic_version') schema_identical=$([ "$A" = "$B" ] && echo YES || echo NO) bookings=$(psql -d ks_chain -c 'select count(*) from bookings')"
run alembic upgrade head 2>&1 | grep -c Running
psql -c "DROP DATABASE ks_chain" >/dev/null
if [ -f $W/tmp_roles ]; then for r in $(cat $W/tmp_roles); do psql -c "DROP ROLE $r" >/dev/null 2>&1; done; rm -f $W/tmp_roles; fi
