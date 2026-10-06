#!/bin/bash
# Backend-only release: migrations 35..38, master catalog + CheckLine drafts, API container swap. Frontend, worker and DB containers are not touched.
set -euo pipefail; source ~/ks-checkline-work/relenv.sh
STAGED=~/karenseir-current/artifacts/checkline-pretransfer-20261006
fail() { echo "GATE FAILED: $1"; [ "${SWAPPED:-0}" = 1 ] || [ "${MIGRATED:-0}" = 1 ] && bash $W/rollback.sh; exit 1; }
FE_BEFORE=$(docker inspect karenseir-frontend-1 --format '{{.Id}} {{.Image}} {{.State.StartedAt}}'); WK_BEFORE=$(docker inspect karenseir-worker-1 --format '{{.Id}} {{.State.StartedAt}}'); echo "$FE_BEFORE" > $B/frontend-before.txt
[ "$(sql -c 'select version_num from alembic_version')" = "20260928_34" ] || fail "production is not at 34"
[ "$(docker inspect karenseir-api-1 --format '{{.Config.Image}}')" = "karenseir-current-api:visible-slice18-saved-selection" ] || fail "unexpected API image"
# 0. final backup immediately before the first write
docker exec karenseir-db-1 pg_dump -U karenseir -d karenseir -Fc > $B/prod-karenseir-final.dump; docker exec -i karenseir-db-1 pg_restore -l < $B/prod-karenseir-final.dump | grep -c "TABLE DATA" | sed 's/^/final_backup_table_entries=/'
RC="select (select count(*) from users), (select count(*) from bookings), (select count(*) from tenants)"; RC_BEFORE=$(sql -c "$RC")
(cd $B && sha256sum prod-karenseir-final.dump >> SHA256SUMS); sql -c "select 'before', (select count(*) from users), (select count(*) from bookings), (select count(*) from tenants), (select count(*) from audit_events)" | tee $B/rowcounts-before.txt
# 1. migrations (owner role; running API keeps serving, changes are additive)
MIGRATED=1; owner $NEW alembic upgrade head 2>&1 | grep -E "Running upgrade|Error|Traceback" | cut -c1-100
[ "$(sql -c 'select version_num from alembic_version')" = "20261007_38" ] || fail "migration did not reach 38"
[ "$(curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:8000/health)" = 200 ] || fail "running API unhealthy after migration"
# 2. data: master catalog (baked /app/catalog_data), then CheckLine drafts
owner $NEW python scripts/catalog/import_catalog.py | python3 -c "import json,sys; d=json.load(sys.stdin); print('catalog', {k:(v['inserted'],v['removed']) for k,v in d.items() if isinstance(v,dict)})"
owner -v $STAGED:/staged:ro $NEW python scripts/catalog/import_checkline.py /staged | cut -c1-330
owner -v $STAGED:/staged:ro $NEW python scripts/catalog/import_checkline.py /staged | python3 -c "import json,sys; d=json.load(sys.stdin); print('checkline rerun', d['inserted'], d['updated'], d['unchanged'])"
C=$(sql -c "select (select count(*) from catalog_hotels), (select count(*) from catalog_hotels where source='checkline'), (select count(*) from catalog_hotels where source='checkline' and status<>'draft'), (select count(*) from catalog_hotels where source='checkline' and (latitude is not null or image_url is not null or amenities_json<>'[]' or description is not null)), (select count(*) - count(distinct id) from catalog_hotels)")
echo "counts total|checkline|checkline_not_draft|fabricated|dup_ids = $C"; [ "$C" = "19974 | 706 | 0 | 0 | 0" ] || fail "data integrity counts unexpected"
[ "$(sql -c "$RC")" = "$RC_BEFORE" ] || fail "existing table row counts changed"
# 3. trial start of the new image in production mode with the exact production env (no published port)
docker inspect karenseir-api-1 --format '{{json .Config.Env}}' | python3 -c "
import json,sys
skip=('PATH','LANG','GPG_KEY','PYTHON_VERSION','PYTHON_SHA256','PYTHONDONTWRITEBYTECODE','PYTHONUNBUFFERED')
env=[e for e in json.load(sys.stdin) if e.split('=',1)[0] not in skip]
assert not any('\n' in e for e in env)
open('$B/api.env','w').write('\n'.join(env)+'\n')"; chmod 600 $B/api.env
docker rm -f karenseir-api-next >/dev/null 2>&1 || true
docker run -d --name karenseir-api-next --network $NET --env-file $B/api.env $NEW >/dev/null
ok=0; for i in $(seq 1 30); do [ "$(docker inspect karenseir-api-next --format '{{.State.Health.Status}}')" = healthy ] && ok=1 && break; [ "$(docker inspect karenseir-api-next --format '{{.State.Running}}')" = true ] || break; sleep 3; done
[ $ok = 1 ] || { docker logs karenseir-api-next 2>&1 | tail -8 | cut -c1-200; docker rm -f karenseir-api-next >/dev/null; fail "new image does not start healthy in production mode"; }
docker rm -f karenseir-api-next >/dev/null
# 4. swap the API container (same name, network, port, media volume, restart policy)
VOL=$(docker inspect karenseir-api-1 --format '{{range .Mounts}}{{if eq .Destination "/app/media"}}{{.Name}}{{end}}{{end}}')
docker stop karenseir-api-1 >/dev/null; docker update --restart no karenseir-api-1 >/dev/null; docker rename karenseir-api-1 $PREV; SWAPPED=1
docker run -d --name karenseir-api-1 --network $NET -p 8000:8000 -v $VOL:/app/media --restart unless-stopped --env-file $B/api.env $NEW >/dev/null
ok=0; for i in $(seq 1 40); do [ "$(curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:8000/health)" = 200 ] && ok=1 && break; sleep 2; done
[ $ok = 1 ] || fail "new API not healthy after swap"
# 5. immediate gates
[ "$(docker inspect karenseir-frontend-1 --format '{{.Id}} {{.Image}} {{.State.StartedAt}}')" = "$FE_BEFORE" ] || fail "frontend container changed"
[ "$(docker inspect karenseir-worker-1 --format '{{.Id}} {{.State.StartedAt}}')" = "$WK_BEFORE" ] || fail "worker container changed"
python3 $W/prodsmoke.py $B/smoke-api-after.json $B/smoke-api-before.json || fail "API smoke differs from before"
echo "DEPLOYED api=$(docker inspect karenseir-api-1 --format '{{.Config.Image}}') db=$(sql -c 'select version_num from alembic_version') health=$(docker inspect karenseir-api-1 --format '{{.State.Health.Status}}')"
