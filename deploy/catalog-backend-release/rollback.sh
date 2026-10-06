#!/bin/bash
# Roll the catalog backend release back to d2ba674 / alembic 34. Removes ONLY data created by this release (catalog_* tables did not exist before).
set -euo pipefail; source ~/ks-checkline-work/relenv.sh
echo "rollback: stopping new API"; docker rm -f karenseir-api-next >/dev/null 2>&1 || true
if docker inspect $PREV >/dev/null 2>&1; then docker rm -f karenseir-api-1 >/dev/null 2>&1 || true; fi
if [ "$(sql -c 'select version_num from alembic_version')" != "20260928_34" ]; then
  sql -c "delete from catalog_hotels where source in ('checkline','karenseir') or latitude is null or longitude is null" 2>/dev/null || true   # release-owned rows only; lets downgrade 37 proceed
  owner $NEW alembic downgrade 20260928_34 2>&1 | grep -E "Running|Error" | cut -c1-120
fi
echo "db=$(sql -c 'select version_num from alembic_version')"
if docker inspect $PREV >/dev/null 2>&1; then docker rename $PREV karenseir-api-1; docker update --restart unless-stopped karenseir-api-1 >/dev/null; docker start karenseir-api-1 >/dev/null; fi
for i in $(seq 1 30); do [ "$(curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:8000/health)" = 200 ] && break; sleep 2; done
echo "rollback done: api=$(docker inspect karenseir-api-1 --format '{{.Config.Image}}') health=$(curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:8000/health)"
