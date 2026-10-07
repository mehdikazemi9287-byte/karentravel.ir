#!/bin/bash
# Full release of the QA'd candidate: migrations 39..46, additive imports, API container, frontend container. Worker and DB containers are not touched.
set -euo pipefail; source ~/ks-checkline-work/rel_env.sh
fail() { echo "GATE FAILED: $1"; bash $W/rel_rollback.sh; exit 1; }
[ -s $B/prod-karenseir-pre46.dump ] && (cd $B && sha256sum -c SHA256SUMS >/dev/null) || { echo "no verified backup"; exit 1; }
[ "$(sql -c 'select version_num from alembic_version')" = "20261007_38" ] || { echo "production is not at 38"; exit 1; }
[ "$(docker inspect karenseir-api-1 --format '{{.Config.Image}}')" = "karenseir-current-api:catalog-backend-352684d" ] || { echo "unexpected API image"; exit 1; }
[ "$(docker inspect karenseir-frontend-1 --format '{{.Config.Image}}')" = "karenseir-current-web:visible-slice18-saved-selection" ] || { echo "unexpected web image"; exit 1; }
docker image inspect $NEWAPI $NEWWEB >/dev/null; ! docker inspect $PREVAPI $PREVWEB >/dev/null 2>&1 || { echo "previous containers already exist"; exit 1; }
WK_BEFORE=$(docker inspect karenseir-worker-1 --format '{{.Id}} {{.State.StartedAt}}'); DB_BEFORE=$(docker inspect karenseir-db-1 --format '{{.Id}} {{.State.StartedAt}}')
python3 $W/prodsmoke.py $B/smoke-api-before.json >/dev/null
# 0. last dump immediately before the first write
docker exec karenseir-db-1 pg_dump -U karenseir -d karenseir -Fc > $B/prod-karenseir-final.dump; docker exec -i karenseir-db-1 pg_restore -l < $B/prod-karenseir-final.dump | grep -c "TABLE DATA" | sed 's/^/final_dump_table_entries=/'; (cd $B && sha256sum prod-karenseir-final.dump >> SHA256SUMS); chmod 600 $B/*
RB=$(sql -c "$ROWS")
# 1. migrations (owner role; the running API keeps serving, changes are additive)
owner alembic upgrade head 2>&1 | grep -E "Running upgrade|Error|Traceback" | sed -E 's/.*Running upgrade ([0-9_]+ -> [0-9_]+).*/\1/' | tr '\n' ';'; echo
[ "$(sql -c 'select version_num from alembic_version')" = "20261015_46" ] || fail "migration did not reach 46"
[ "$(curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:8000/health)" = 200 ] || fail "running API unhealthy after migration"
# 2. data
imports owner 2>&1 | tee $B/imports.log | cut -c1-330
grep -q "^bundle final {'inserted': 0, 'updated': 0" $B/imports.log || fail "bundle import is not idempotent"
[ "$(sql -c "$ROWS")" = "$RB" ] || fail "existing rows changed"
sql -c "$SUMMARY" | tee $B/summary-after.txt
[ "$(grep -E '^(price-like columns|city/country mismatch|published without city|published duplicates|dup slugs|tour dup slugs) ' $B/summary-after.txt | awk -F' [|] ' '{s+=$2} END {print s}')" = 0 ] || fail "data integrity"
[ "$(sql -c "select count(*) from pg_class c join pg_namespace n on n.oid=c.relnamespace where n.nspname='public' and c.relkind='r' and c.relname<>'alembic_version' and not has_table_privilege('karenseir_api', c.oid, 'SELECT')")" = 0 ] || fail "API role cannot read a table"
# 3. trial start of the new API image in production mode with the exact production env (no published port)
docker inspect karenseir-api-1 --format '{{json .Config.Env}}' | python3 -c "
import json,sys
skip=('PATH','LANG','GPG_KEY','PYTHON_VERSION','PYTHON_SHA256','PYTHONDONTWRITEBYTECODE','PYTHONUNBUFFERED','GIT_COMMIT','BUILD_TIMESTAMP')
env=[e for e in json.load(sys.stdin) if e.split('=',1)[0] not in skip]
assert not any('\n' in e for e in env)
open('$B/api.env','w').write('\n'.join(env)+'\n')"; chmod 600 $B/api.env
docker rm -f karenseir-api-next >/dev/null 2>&1 || true
docker run -d --name karenseir-api-next --network $NET --env-file $B/api.env $NEWAPI >/dev/null
ok=0; for i in $(seq 1 30); do [ "$(docker inspect karenseir-api-next --format '{{.State.Health.Status}}')" = healthy ] && ok=1 && break; [ "$(docker inspect karenseir-api-next --format '{{.State.Running}}')" = true ] || break; sleep 3; done
[ $ok = 1 ] || { docker logs karenseir-api-next 2>&1 | tail -8 | cut -c1-200; fail "new API image does not start healthy in production mode"; }
docker rm -f karenseir-api-next >/dev/null
# 4. swap the API container (same name, network, port, media volume, restart policy)
VOL=$(docker inspect karenseir-api-1 --format '{{range .Mounts}}{{if eq .Destination "/app/media"}}{{.Name}}{{end}}{{end}}')
docker stop karenseir-api-1 >/dev/null; docker update --restart no karenseir-api-1 >/dev/null; docker rename karenseir-api-1 $PREVAPI
docker run -d --name karenseir-api-1 --network $NET -p 8000:8000 -v $VOL:/app/media --restart unless-stopped --env-file $B/api.env $NEWAPI >/dev/null
ok=0; for i in $(seq 1 40); do [ "$(curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:8000/health)" = 200 ] && ok=1 && break; sleep 2; done
[ $ok = 1 ] || fail "new API not healthy after swap"
python3 $W/prodsmoke.py $B/smoke-api-after.json $B/smoke-api-before.json > $B/smoke-api.log 2>&1 || { tail -12 $B/smoke-api.log | cut -c1-200; fail "API smoke differs from before"; }
tail -2 $B/smoke-api.log | cut -c1-200
# 5. swap the frontend container (same name, network, port, restart policy)
docker stop karenseir-frontend-1 >/dev/null; docker update --restart no karenseir-frontend-1 >/dev/null; docker rename karenseir-frontend-1 $PREVWEB
docker run -d --name karenseir-frontend-1 --network $NET -p 3000:3000 --restart unless-stopped $NEWWEB >/dev/null
ok=0; for i in $(seq 1 40); do [ "$(curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:3000/)" = 200 ] && [ "$(curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1/)" = 200 ] && ok=1 && break; sleep 2; done
[ $ok = 1 ] || fail "new frontend not serving after swap"
[ "$(docker inspect karenseir-worker-1 --format '{{.Id}} {{.State.StartedAt}}')" = "$WK_BEFORE" ] && [ "$(docker inspect karenseir-db-1 --format '{{.Id}} {{.State.StartedAt}}')" = "$DB_BEFORE" ] || fail "worker or db container changed"
echo "DEPLOYED api=$(docker inspect karenseir-api-1 --format '{{.Config.Image}}') web=$(docker inspect karenseir-frontend-1 --format '{{.Config.Image}}') db=$(sql -c 'select version_num from alembic_version') api_health=$(docker inspect karenseir-api-1 --format '{{.State.Health.Status}}') worker=$(docker inspect karenseir-worker-1 --format '{{.State.Health.Status}}')"
