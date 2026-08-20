#!/bin/sh
set -eu

: "${BACKUP_FILE:?set BACKUP_FILE to a verified custom-format dump}"
: "${RESTORE_DATABASE:?set RESTORE_DATABASE to an isolated restore-test database}"
: "${POSTGRES_USER:?set POSTGRES_USER}"

case "$RESTORE_DATABASE" in
  karenseir|postgres|template0|template1) echo "refusing restore into production/system database" >&2; exit 2 ;;
esac

test -f "$BACKUP_FILE"
sha256sum --check "$BACKUP_FILE.sha256"
createdb --username="$POSTGRES_USER" "$RESTORE_DATABASE"
pg_restore --exit-on-error --no-owner --username="$POSTGRES_USER" --dbname="$RESTORE_DATABASE" "$BACKUP_FILE"
psql --username="$POSTGRES_USER" --dbname="$RESTORE_DATABASE" --set=ON_ERROR_STOP=1 --command='SELECT version_num FROM alembic_version;'
printf '%s\n' "restore verification completed in isolated database: $RESTORE_DATABASE"
