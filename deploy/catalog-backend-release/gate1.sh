#!/bin/bash
# Compatibility gate, part 1: fresh backup, API image, two throwaway copies of production, old+new API on loopback.
set -euo pipefail
W=~/ks-checkline-work; PG=ks-catalog-scratch-pg; B=~/backups/release-catalog-backend-$(date -u +%Y%m%dT%H%MZ); mkdir -p $B; echo $B > $W/release_backup_dir
NEW=karenseir-current-api:catalog-backend-$(git -C $W/src rev-parse --short HEAD); OLD=karenseir-current-api:visible-slice18-saved-selection; echo $NEW > $W/release_image
PW=$(docker inspect $PG --format '{{range .Config.Env}}{{println .}}{{end}}' | sed -n 's/^POSTGRES_PASSWORD=//p')
psql() { docker exec -i $PG psql -U postgres -v ON_ERROR_STOP=1 -At "$@"; }
# 1. fresh production backup (read-only) + deployment state
docker exec karenseir-db-1 pg_dump -U karenseir -d karenseir -Fc > $B/prod-karenseir.dump
docker exec -i karenseir-db-1 pg_restore -l < $B/prod-karenseir.dump | grep -c "TABLE DATA" | sed 's/^/backup_table_data_entries=/'
docker exec karenseir-db-1 pg_dumpall -U karenseir --roles-only | grep -v PASSWORD > $B/roles-no-passwords.sql || true
for c in karenseir-api-1 karenseir-frontend-1 karenseir-worker-1 karenseir-db-1; do docker inspect $c > $B/inspect-$c.json; done; chmod 600 $B/*
docker ps --format '{{.Names}} {{.Image}} {{.ID}}' | grep -E 'karenseir-(api|frontend|worker|db)-1' > $B/containers.txt
docker exec karenseir-db-1 psql -U karenseir -d karenseir -Atc "select version_num from alembic_version" > $B/alembic_version.txt
(cd $B && sha256sum prod-karenseir.dump containers.txt alembic_version.txt > SHA256SUMS); ls -la $B | awk '{print $5,$9}' | tail -n +2 | tr '\n' ' '; echo
# 2. image from the candidate backend only (no frontend file is part of this context)
rm -rf $W/apictx; mkdir -p $W/apictx; rsync -a --exclude __pycache__ --exclude '*.db' --exclude media --exclude tests $W/src/backend/ $W/apictx/; mkdir -p $W/apictx/catalog_data; cp $W/osm/*.json.gz $W/apictx/catalog_data/
docker build -q -t $NEW --build-arg GIT_COMMIT=$(git -C $W/src rev-parse --short HEAD) --build-arg BUILD_TIMESTAMP=$(date -u +%FT%TZ) $W/apictx | tail -1
# 3. two copies of production
for r in karenseir karenseir_api karenseir_worker; do [ "$(psql -c "select count(*) from pg_roles where rolname='$r'")" = 0 ] && psql -c "CREATE ROLE $r NOLOGIN" >/dev/null && echo "$r" >> $W/tmp_roles; done
for db in ks_gate_old ks_gate_new; do psql -c "DROP DATABASE IF EXISTS $db" >/dev/null; psql -c "CREATE DATABASE $db" >/dev/null; docker exec -i $PG pg_restore -U postgres -d $db --no-owner < $B/prod-karenseir.dump 2>&1 | tail -2; done
# 4. old and new API, development mode for dev-login, loopback only, isolated redis db numbers, no SMS provider key
SEARCH=$(docker inspect karenseir-api-1 --format '{{range .Config.Env}}{{println .}}{{end}}' | grep '^SEARCH_INTERNAL_TOKEN=')
start() { docker rm -f $1 >/dev/null 2>&1 || true; docker run -d --name $1 --network host -e ENVIRONMENT=development -e "$SEARCH" -e SEARCH_SERVICE_URL=http://127.0.0.1:8090 -e REDIS_URL=redis://127.0.0.1:16380/$5 \
  -e DATABASE_URL="postgresql+psycopg://postgres:$PW@127.0.0.1:55439/$3" -e CORS_ORIGINS=http://127.0.0.1:3398 -e JWT_SECRET=gate-only-secret-not-production-0123456789 -e MEDIA_STORAGE_ROOT=/tmp/media \
  $2 sh -c "alembic upgrade head && exec uvicorn app.main:app --host 127.0.0.1 --port $4 --no-access-log" >/dev/null; }
start ks-gate-api-old $OLD ks_gate_old 18134 11; start ks-gate-api-new $NEW ks_gate_new 18138 12; sleep 12
for p in 18134 18138; do curl -s -o /dev/null -w "api_$p=%{http_code} " http://127.0.0.1:$p/health; done; echo
echo "old=$(psql -d ks_gate_old -c 'select version_num from alembic_version') new=$(psql -d ks_gate_new -c 'select version_num from alembic_version')"
docker logs ks-gate-api-new 2>&1 | grep -E "Running upgrade|Error|Traceback" | cut -c1-110
