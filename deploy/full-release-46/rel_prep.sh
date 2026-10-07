#!/bin/bash
# Full release, step 1: build both images from the QA'd commit, take and verify the final backup, rehearse the whole migration + import sequence on the restored backup.
set -euo pipefail; W=~/ks-checkline-work; TS=$(date -u +%Y%m%dT%H%MZ); mkdir -p ~/backups/release-full-$TS; echo ~/backups/release-full-$TS > $W/release46_backup_dir; chmod 700 ~/backups/release-full-$TS
source $W/rel_env.sh; PG=ks-catalog-scratch-pg; PW=$(docker inspect $PG --format '{{range .Config.Env}}{{println .}}{{end}}' | sed -n 's/^POSTGRES_PASSWORD=//p')
[ -z "$(git -C $W/src status --short)" ] || { echo "worktree not clean"; exit 1; }
echo "commit=$SHA prod_api=$(docker inspect karenseir-api-1 --format '{{.Config.Image}}') prod_web=$(docker inspect karenseir-frontend-1 --format '{{.Config.Image}}') prod_db=$(sql -c 'select version_num from alembic_version')"
rm -rf $W/apictx; mkdir -p $W/apictx; git -C $W/src archive HEAD backend | tar -x -C $W/apictx --strip-components=1; rm -rf $W/apictx/tests; mkdir -p $W/apictx/catalog_data; cp $W/osm/*.json.gz $W/apictx/catalog_data/
docker build -q -t $NEWAPI --build-arg GIT_COMMIT=$SHA --build-arg BUILD_TIMESTAMP=$(date -u +%FT%TZ) $W/apictx | tail -1
rm -rf $W/webctx; mkdir -p $W/webctx; git -C $W/src archive HEAD | tar -x -C $W/webctx
docker build -q -t $NEWWEB --build-arg NEXT_PUBLIC_API_URL=http://95.38.184.209:8000 --build-arg NEXT_PUBLIC_SITE_URL=http://95.38.184.209 --build-arg ALLOW_HTTP_PREVIEW=1 --build-arg GIT_COMMIT=$SHA --build-arg BUILD_TIMESTAMP=$(date -u +%FT%TZ) $W/webctx | tail -1
docker image inspect $NEWAPI $NEWWEB --format '{{index .RepoTags 0}} {{.Id}}' | cut -c1-90
# ---- backup + verification by full restore
docker exec karenseir-db-1 pg_dump -U karenseir -d karenseir -Fc > $B/prod-karenseir-pre46.dump; (cd $B && sha256sum prod-karenseir-pre46.dump > SHA256SUMS); ls -la $B/prod-karenseir-pre46.dump | awk '{print "backup bytes="$5}'
for c in karenseir-api-1 karenseir-frontend-1 karenseir-worker-1; do docker inspect $c > $B/$c.inspect.json; done; chmod 600 $B/*
psql() { docker exec -i $PG psql -U postgres -v ON_ERROR_STOP=1 -At -F ' | ' "$@"; }
psql -c "DROP DATABASE IF EXISTS ks_rel_verify" >/dev/null; psql -c "CREATE DATABASE ks_rel_verify" >/dev/null
for r in karenseir karenseir_api karenseir_worker; do [ "$(psql -c "select count(*) from pg_roles where rolname='$r'")" = 0 ] && psql -c "CREATE ROLE $r NOLOGIN" >/dev/null && echo "$r" >> $W/tmp_roles; done
docker exec -i $PG pg_restore -U postgres -d ks_rel_verify --no-owner --exit-on-error < $B/prod-karenseir-pre46.dump && echo "restore exit=0"
COUNT="select string_agg(c::text, ',' order by t) from (select table_name t, (xpath('/row/c/text()', query_to_xml(format('select count(*) c from %I', table_name), false, true, '')))[1]::text::bigint c from information_schema.tables where table_schema='public' and table_type='BASE TABLE') x"
P=$(sql -c "$COUNT" | md5sum | cut -c1-12); R=$(psql -d ks_rel_verify -c "$COUNT" | md5sum | cut -c1-12); echo "per-table row counts prod=$P restored=$R tables=$(psql -d ks_rel_verify -c "select count(*) from information_schema.tables where table_schema='public' and table_type='BASE TABLE'") $([ $P = $R ] && echo BACKUP_VERIFIED || echo BACKUP_MISMATCH)"
# ---- rehearsal on the restored backup
run() { docker run --rm --network container:$PG -e DATABASE_URL="postgresql+psycopg://postgres:$PW@127.0.0.1:5432/ks_rel_verify" -e ENVIRONMENT=development -v $W/zip:/bundle:ro -v $W/ref:/ref:ro -v $STAGED:/staged:ro $NEWAPI "$@"; }
BEFORE=$(psql -d ks_rel_verify -c "$ROWS"); run alembic upgrade head 2>&1 | grep -cE "Running upgrade" | sed 's/^/migrations applied=/'
imports run
echo "untouched rows before/after: $BEFORE -> $(psql -d ks_rel_verify -c "$ROWS") alembic=$(psql -d ks_rel_verify -c 'select version_num from alembic_version')"
psql -d ks_rel_verify -c "$SUMMARY"
psql -c "DROP DATABASE ks_rel_verify" >/dev/null; if [ -f $W/tmp_roles ]; then for r in $(cat $W/tmp_roles); do psql -c "DROP ROLE IF EXISTS $r" >/dev/null 2>&1; done; rm -f $W/tmp_roles; fi
echo "prep done; production untouched: api=$(docker inspect karenseir-api-1 --format '{{.Config.Image}}') db=$(sql -c 'select version_num from alembic_version')"
