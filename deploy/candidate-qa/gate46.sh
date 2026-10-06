#!/bin/bash
# Migration 38 -> 46 audit and API compatibility gate on throwaway restores of a fresh, read-only production dump.
# Nothing here writes to production.
set -uo pipefail
W=~/ks-checkline-work; PG=ks-catalog-scratch-pg; A=$W/audit45; mkdir -p $A
OLD=$(docker inspect karenseir-api-1 --format '{{.Config.Image}}'); NEW=karenseir-current-api:cand46-$(git -C $W/src rev-parse --short HEAD)
PW=$(docker inspect $PG --format '{{range .Config.Env}}{{println .}}{{end}}' | sed -n 's/^POSTGRES_PASSWORD=//p')
psql() { docker exec -i $PG psql -U postgres -v ON_ERROR_STOP=1 -At "$@"; }
FP="select md5(string_agg(table_name||column_name||data_type||is_nullable, ',' order by table_name, ordinal_position)) from information_schema.columns where table_schema='public'"
ROWS="select (select count(*) from users)||'/'||(select count(*) from bookings)||'/'||(select count(*) from tenants)||'/'||(select count(*) from catalog_hotels)||'/'||(select count(*) from catalog_hotels where source='checkline')||'/'||(select count(*) from catalog_hotels where status='published')||'/'||(select count(*) from catalog_places)||'/'||(select count(*) from catalog_venues)||'/'||(select count(*) from audit_events)"
docker exec karenseir-db-1 pg_dump -U karenseir -d karenseir -Fc > $A/prod.dump; echo "prod dump bytes=$(stat -c %s $A/prod.dump) prod_alembic=$(docker exec karenseir-db-1 psql -U karenseir -d karenseir -Atc 'select version_num from alembic_version')"
rm -rf $W/apictx; mkdir -p $W/apictx; rsync -a --exclude __pycache__ --exclude '*.db' --exclude media --exclude tests $W/src/backend/ $W/apictx/; mkdir -p $W/apictx/catalog_data; cp $W/osm/*.json.gz $W/apictx/catalog_data/ 2>/dev/null; ls $W/apictx/catalog_data | wc -l
docker build -q -t $NEW --build-arg GIT_COMMIT=$(git -C $W/src rev-parse --short HEAD) $W/apictx | tail -1
for r in karenseir karenseir_api karenseir_worker; do [ "$(psql -c "select count(*) from pg_roles where rolname='$r'")" = 0 ] && psql -c "CREATE ROLE $r NOLOGIN" >/dev/null && echo "$r" >> $W/tmp_roles; done
for db in ks_gate_old ks_gate_new ks_a45_rb; do psql -c "DROP DATABASE IF EXISTS $db" >/dev/null; psql -c "CREATE DATABASE $db" >/dev/null; docker exec -i $PG pg_restore -U postgres -d $db --no-owner < $A/prod.dump 2>&1 | grep -v "already exists" | tail -1; done
run() { local db=$1; shift; docker run --rm --network container:$PG -e DATABASE_URL="postgresql+psycopg://postgres:$PW@127.0.0.1:5432/$db" -e ENVIRONMENT=development -v $W/zip:/bundle:ro -v $W/ref:/ref:ro $NEW "$@"; }
CON="select md5(string_agg(conrelid::regclass::text||conname||contype::text, ',' order by conrelid::regclass::text, conname)) from pg_constraint where connamespace='public'::regnamespace"; GR="select md5(string_agg(table_name||privilege_type, ',' order by table_name, privilege_type)) from information_schema.role_table_grants where grantee='karenseir_api'"
B38=$(psql -d ks_a45_rb -c "$FP"); C38=$(psql -d ks_a45_rb -c "$CON"); G38=$(psql -d ks_a45_rb -c "$GR"); echo "rows@38 users/bookings/tenants/hotels/checkline/published/places/venues/audit = $(psql -d ks_gate_new -c "$ROWS")"
echo "== chain"; run ks_gate_new alembic history 2>/dev/null | grep -E "^2026(1006|1007|1008|1009|101)" | awk '{print $1,$2,$3}' | tr '\n' ';'; echo
echo "== upgrade 38->46"; run ks_gate_new alembic upgrade head 2>&1 | grep -E "Running upgrade|Error|Traceback" | sed -E 's/.*Running upgrade ([0-9_]+ -> [0-9_]+).*/\1/' | tr '\n' ';'; echo
echo "rows@45 = $(psql -d ks_gate_new -c "$ROWS") alembic=$(psql -d ks_gate_new -c 'select version_num from alembic_version')"
echo "== importers on the migrated copy (production mode: no --publish)"
for i in 1 2; do run ks_gate_new python scripts/catalog/import_checkline_bundle.py /bundle | python3 -c "import json,sys;d=json.load(sys.stdin);h=d['hotels'];print('bundle run',{k:h[k] for k in ('inserted','updated','unchanged','published','kept_draft')},'tours ins/upd',d['tours']['inserted'],d['tours']['updated'],'places',d['places'])"; done
run ks_gate_new python scripts/catalog/import_catalog.py | python3 -c "import json,sys;d=json.load(sys.stdin);print('osm reimport',{k:(v['inserted'],v['updated'],v['removed']) for k,v in d.items() if isinstance(v,dict)})"
for i in 1 2; do run ks_gate_new python scripts/catalog/import_airports_reference.py /ref/airports.csv | cut -c1-140; run ks_gate_new python scripts/catalog/import_airlines_reference.py /ref/airlines-wikidata.json | cut -c1-140; done
run ks_gate_new python scripts/catalog/import_checkline_bundle.py /bundle | python3 -c "import json,sys;d=json.load(sys.stdin);h=d['hotels'];print('bundle run 3 (after reference)',{k:h[k] for k in ('inserted','updated','unchanged','published')})"
echo "rows after imports = $(psql -d ks_gate_new -c "$ROWS")"
psql -d ks_gate_new -F ' | ' -c "select 'checkline status', status, count(*) from catalog_hotels where source='checkline' group by 2; select 'public tours', count(*) from catalog_tours where status='published'; select 'osm untouched', count(*) from catalog_hotels where source='openstreetmap' and updated_by is null; select 'price-like columns', count(*) from information_schema.columns where table_name like 'catalog_%' and column_name ~ 'price|amount|capacity|inventory'; select 'api grants hotels/places/tours', has_table_privilege('karenseir_api','catalog_hotels','DELETE'), has_table_privilege('karenseir_api','catalog_places','UPDATE'), has_table_privilege('karenseir_api','catalog_tours','DELETE')"
echo "== rollback copy: 38 -> 46 -> 38"; run ks_a45_rb alembic upgrade head 2>&1 | grep -c "Running upgrade"; R45=$(psql -d ks_a45_rb -c "$ROWS"); run ks_a45_rb alembic downgrade 20261007_38 2>&1 | grep -E "Running downgrade|Error|refused" | wc -l
echo "schema identical to 38: $([ "$(psql -d ks_a45_rb -c "$FP")" = "$B38" ] && echo YES || echo NO) constraints: $([ "$(psql -d ks_a45_rb -c "$CON")" = "$C38" ] && echo YES || echo NO) api-role grants: $([ "$(psql -d ks_a45_rb -c "$GR")" = "$G38" ] && echo YES || echo NO) alembic=$(psql -d ks_a45_rb -c 'select version_num from alembic_version') rows=$(psql -d ks_a45_rb -c "$ROWS") (at45: $R45)"
echo "== API contract: current production image vs candidate image, same data"
SEARCH=$(docker inspect karenseir-api-1 --format '{{range .Config.Env}}{{println .}}{{end}}' | grep '^SEARCH_INTERNAL_TOKEN=')
psql -c "DROP DATABASE ks_gate_new" >/dev/null; psql -c "CREATE DATABASE ks_gate_new" >/dev/null; docker exec -i $PG pg_restore -U postgres -d ks_gate_new --no-owner < $A/prod.dump 2>&1 | grep -v "already exists" | tail -1
for n in 11 12; do docker exec karenseir-closure-qa-redis redis-cli -n $n flushdb >/dev/null; done
start() { docker rm -f $1 >/dev/null 2>&1; docker run -d --name $1 --network host -e ENVIRONMENT=development -e "$SEARCH" -e SEARCH_SERVICE_URL=http://127.0.0.1:8090 -e REDIS_URL=redis://127.0.0.1:16380/$5 -e DATABASE_URL="postgresql+psycopg://postgres:$PW@127.0.0.1:55439/$3" -e CORS_ORIGINS=http://127.0.0.1:3398 -e JWT_SECRET=gate-only-secret-not-production-0123456789 -e MEDIA_STORAGE_ROOT=/tmp/media $2 sh -c "alembic upgrade head && exec uvicorn app.main:app --host 127.0.0.1 --port $4 --no-access-log" >/dev/null; }
start ks-gate-api-old $OLD ks_gate_old 18134 11; start ks-gate-api-new $NEW ks_gate_new 18138 12; sleep 14
for p in 18134 18138; do curl -s -o /dev/null -w "api_$p=%{http_code} " http://127.0.0.1:$p/health; done; echo "old=$(psql -d ks_gate_old -c 'select version_num from alembic_version') new=$(psql -d ks_gate_new -c 'select version_num from alembic_version')"
python3 $W/gate2.py 2>&1 | tail -7
for n in 11 12; do docker exec karenseir-closure-qa-redis redis-cli -n $n flushdb >/dev/null; done
python3 $W/gate2b.py 2>&1 | tail -4
bash $W/gate3.sh 2>&1 | tail -8
docker rm -f ks-gate-api-old ks-gate-api-new ks-gate-web >/dev/null 2>&1
for db in ks_gate_old ks_gate_new ks_a45_rb; do psql -c "DROP DATABASE IF EXISTS $db" >/dev/null; done
if [ -f $W/tmp_roles ]; then for r in $(cat $W/tmp_roles); do psql -c "DROP ROLE IF EXISTS $r" >/dev/null 2>&1; done; rm -f $W/tmp_roles; fi
for n in 11 12; do docker exec karenseir-closure-qa-redis redis-cli -n $n flushdb >/dev/null; done
rm -f $A/prod.dump; echo "cleanup done; production api=$(docker inspect karenseir-api-1 --format '{{.Config.Image}}') db=$(docker exec karenseir-db-1 psql -U karenseir -d karenseir -Atc 'select version_num from alembic_version')"
