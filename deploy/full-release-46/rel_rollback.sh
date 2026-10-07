#!/bin/bash
# Roll the full release back to the previous containers and alembic 38. Rows added by the importers stay as non-public reference/draft rows.
set -uo pipefail; source ~/ks-checkline-work/rel_env.sh
docker rm -f karenseir-api-next >/dev/null 2>&1 || true
if docker inspect $PREVWEB >/dev/null 2>&1; then docker rm -f karenseir-frontend-1 >/dev/null 2>&1 || true; docker rename $PREVWEB karenseir-frontend-1; docker update --restart unless-stopped karenseir-frontend-1 >/dev/null; docker start karenseir-frontend-1 >/dev/null; fi
if docker inspect $PREVAPI >/dev/null 2>&1; then docker rm -f karenseir-api-1 >/dev/null 2>&1 || true; fi
if [ "$(sql -c 'select version_num from alembic_version')" != "20261007_38" ]; then
  sql -c "update catalog_hotels set status='draft' where source='checkline' and status<>'draft'" || true   # as before the release: no CheckLine hotel was public
  owner alembic downgrade 20261007_38 2>&1 | grep -E "Running|Error" | cut -c1-120
fi
if docker inspect $PREVAPI >/dev/null 2>&1; then docker rename $PREVAPI karenseir-api-1; docker update --restart unless-stopped karenseir-api-1 >/dev/null; docker start karenseir-api-1 >/dev/null; fi
for i in $(seq 1 40); do [ "$(curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:8000/health)" = 200 ] && break; sleep 2; done
echo "ROLLED BACK: api=$(docker inspect karenseir-api-1 --format '{{.Config.Image}}') web=$(docker inspect karenseir-frontend-1 --format '{{.Config.Image}}') db=$(sql -c 'select version_num from alembic_version') api_health=$(curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:8000/health) web=$(curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:3000/)"
