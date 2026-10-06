#!/bin/bash
# Candidate: migrate to head, prove the API works under the least-privilege role and that direct DELETE is denied.
set -uo pipefail
W=~/ks-checkline-work; PG=ks-catalog-scratch-pg; IMG=karenseir-current-api:visible-slice19-enterprise-link
PW=$(docker inspect $PG --format '{{range .Config.Env}}{{println .}}{{end}}' | sed -n 's/^POSTGRES_PASSWORD=//p')
psql() { docker exec -i $PG psql -U postgres -d ks_cand37 -v ON_ERROR_STOP=1 -At "$@"; }
run() { docker run --rm --network container:$PG -u $(id -u):$(id -g) -e HOME=/tmp -e PYTHONDONTWRITEBYTECODE=1 -e DATABASE_URL="postgresql+psycopg://postgres:$PW@127.0.0.1:5432/ks_cand37" -v $W/run:/work -v ~/karenseir-current/artifacts/checkline-pretransfer-20261006:/staged:ro -w /work $IMG "$@"; }
rm -rf $W/run; mkdir -p $W/run; rsync -a --exclude __pycache__ --exclude '*.db' --exclude media $W/src/backend/ $W/run/
docker rm -f ks-cand37-api >/dev/null 2>&1
run alembic upgrade head 2>&1 | grep -E "Running|Error" | cut -c1-90
run python scripts/catalog/import_checkline_tours.py /staged | cut -c1-120
# simulate production: the API role exists and default privileges gave it everything
docker exec -i $PG psql -U postgres -At <<SQL >/dev/null
DO \$\$ BEGIN IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='karenseir_api') THEN CREATE ROLE karenseir_api LOGIN PASSWORD 'scratch-only-lp'; ELSE ALTER ROLE karenseir_api LOGIN PASSWORD 'scratch-only-lp'; END IF; END \$\$;
SQL
psql -c "GRANT USAGE ON SCHEMA public TO karenseir_api; GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO karenseir_api; GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO karenseir_api" >/dev/null
echo "before 41: delete on catalog_hotels=$(psql -c "select has_table_privilege('karenseir_api','catalog_hotels','DELETE')") update on catalog_places=$(psql -c "select has_table_privilege('karenseir_api','catalog_places','UPDATE')")"
run alembic downgrade 20261009_40 2>&1 | grep -cE "Running downgrade"; run alembic upgrade head 2>&1 | grep -E "Running" | cut -c1-90
psql -F ' ' -c "select 'after 41:', string_agg(t||'='||concat_ws('', case when has_table_privilege('karenseir_api',t,'SELECT') then 'r' end, case when has_table_privilege('karenseir_api',t,'INSERT') then 'a' end, case when has_table_privilege('karenseir_api',t,'UPDATE') then 'w' end, case when has_table_privilege('karenseir_api',t,'DELETE') then 'd' end), ' ' order by t) from unnest(array['catalog_hotels','catalog_places','catalog_airports','catalog_hotel_images','catalog_hotel_room_types','catalog_hotel_matches','catalog_hotel_provider_mappings','catalog_tours','catalog_tour_departures','catalog_tour_itinerary_days','hotel_offer_snapshots','users','trip_events']) t"
# API as the restricted role
docker run -d --name ks-cand37-api --network host -u $(id -u):$(id -g) -e HOME=/tmp -e PYTHONDONTWRITEBYTECODE=1 -e ENVIRONMENT=development -e MEDIA_STORAGE_ROOT=/media \
  -e DATABASE_URL="postgresql+psycopg://karenseir_api:scratch-only-lp@127.0.0.1:55439/ks_cand37" -e CORS_ORIGINS=http://127.0.0.1:3396,http://localhost:3396 -e PUBLIC_WEB_URL=http://127.0.0.1:3396 \
  -v $W/run:/work -v $W/media:/media -w /work $IMG uvicorn app.main:app --host 127.0.0.1 --port 18137 --no-access-log >/dev/null
sleep 7; curl -s -o /dev/null -w "api_as_restricted_role=%{http_code}\n" http://127.0.0.1:18137/catalog/summary; docker logs ks-cand37-api 2>&1 | grep -iE "error|denied|Traceback" | head -5
python3 $W/sample_hotel.py 2>&1 | grep -E "^save|^reopen|^anon" | cut -c1-140
TRIP=$(psql -c "insert into trips (id, tenant_id, user_id, title, destination, status, created_at, updated_at) select gen_random_uuid()::text, tenant_id, id, 'سفر شیراز (نمونهٔ آزمون)', 'شیراز', 'planned', now(), now() from users where email='employee@aftab.test' returning id" | head -1); echo "$TRIP" > $W/trip_id
python3 $W/tripflow.py $TRIP
echo "direct statements as the API role:"
for sqlx in "delete from catalog_hotels where id='cl-7788'" "update catalog_places set name_fa='x' where id='ir'" "delete from catalog_tours" "delete from catalog_hotel_provider_mappings" "update catalog_tour_departures set starts_on=now()"; do
  out=$(docker exec -e PGPASSWORD=scratch-only-lp $PG psql -h 127.0.0.1 -U karenseir_api -d ks_cand37 -At -c "$sqlx" 2>&1 | head -1); echo "  $sqlx -> ${out:0:70}"; done
docker logs ks-cand37-api 2>&1 | grep -ciE "permission denied" | sed 's/^/permission_denied_in_api_log=/'
