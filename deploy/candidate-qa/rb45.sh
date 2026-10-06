#!/bin/bash
# Re-check after fixes: 38 -> 45 -> 38 schema identity, 45 -> 34, bundle import then reference re-import (nothing erased).
set -uo pipefail
W=~/ks-checkline-work; PG=ks-catalog-scratch-pg; PW=$(docker inspect $PG --format '{{range .Config.Env}}{{println .}}{{end}}' | sed -n 's/^POSTGRES_PASSWORD=//p')
NEW=karenseir-current-api:cand45-$(git -C $W/src rev-parse --short HEAD)
psql() { docker exec -i $PG psql -U postgres -v ON_ERROR_STOP=1 -At "$@"; }
FP="select md5(string_agg(table_name||column_name||data_type||is_nullable, ',' order by table_name, ordinal_position)) from information_schema.columns where table_schema='public'"
CON="select md5(string_agg(conrelid::regclass::text||conname||contype::text, ',' order by conrelid::regclass::text, conname)) from pg_constraint where connamespace='public'::regnamespace"
rm -rf $W/apictx; mkdir -p $W/apictx; rsync -a --exclude __pycache__ --exclude '*.db' --exclude media --exclude tests $W/src/backend/ $W/apictx/; mkdir -p $W/apictx/catalog_data; cp $W/osm/*.json.gz $W/apictx/catalog_data/
docker build -q -t $NEW $W/apictx | tail -1
psql -c "DROP DATABASE IF EXISTS ks_a45_rb" >/dev/null; psql -c "CREATE DATABASE ks_a45_rb" >/dev/null; docker exec -i $PG pg_restore -U postgres -d ks_a45_rb --no-owner < $W/audit45/prod.dump 2>&1 | tail -1
run() { docker run --rm --network container:$PG -e DATABASE_URL="postgresql+psycopg://postgres:$PW@127.0.0.1:5432/ks_a45_rb" -e ENVIRONMENT=development -v $W/zip:/bundle:ro $NEW "$@"; }
B=$(psql -d ks_a45_rb -c "$FP"); C=$(psql -d ks_a45_rb -c "$CON"); H=$(psql -d ks_a45_rb -c "select count(*) from catalog_hotels")
run alembic upgrade head 2>&1 | grep -c "Running upgrade"
run python scripts/catalog/import_checkline_bundle.py /bundle >/dev/null
run python scripts/catalog/import_catalog.py | python3 -c "import json,sys;d=json.load(sys.stdin);print('reference re-import after bundle', {k:(v['inserted'],v['updated'],v['removed']) for k,v in d.items() if isinstance(v,dict)})"
psql -d ks_a45_rb -c "select 'places with description kept', count(*) from catalog_places where description is not null and details_json is not null"
run alembic downgrade 20261007_38 2>&1 | grep -E "Running downgrade|Error|refused" | sed -E 's/.*Running downgrade ([0-9_]+ -> [0-9_]+).*/\1/' | tr '\n' ';'; echo
echo "at 38: alembic=$(psql -d ks_a45_rb -c 'select version_num from alembic_version') columns_identical=$([ "$(psql -d ks_a45_rb -c "$FP")" = "$B" ] && echo YES || echo NO) constraints_identical=$([ "$(psql -d ks_a45_rb -c "$CON")" = "$C" ] && echo YES || echo NO) hotels=$(psql -d ks_a45_rb -c 'select count(*) from catalog_hotels') (was $H) users=$(psql -d ks_a45_rb -c 'select count(*) from users')"
run alembic upgrade head 2>&1 | grep -c "Running upgrade"
psql -c "DROP DATABASE ks_a45_rb" >/dev/null
if [ -f $W/tmp_roles ]; then for r in $(cat $W/tmp_roles); do psql -c "DROP ROLE IF EXISTS $r" >/dev/null 2>&1; done; rm -f $W/tmp_roles; fi
rm -f $W/audit45/prod.dump; echo cleaned
