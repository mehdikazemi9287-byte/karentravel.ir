#!/bin/sh
set -eu

: "${BACKUP_FILE:?set BACKUP_FILE to a verified custom-format dump}"
: "${RESTORE_DATABASE:?set RESTORE_DATABASE to an isolated restore-test database}"
: "${POSTGRES_USER:?set POSTGRES_USER}"

case "$RESTORE_DATABASE" in
  karenseir|postgres|template0|template1) echo "refusing restore into production/system database" >&2; exit 2 ;;
esac

test -f "$BACKUP_FILE"
if command -v sha256sum >/dev/null 2>&1; then
  sha256sum --check "$BACKUP_FILE.sha256"
elif command -v shasum >/dev/null 2>&1; then
  expected=$(awk '{print $1}' "$BACKUP_FILE.sha256")
  actual=$(shasum -a 256 "$BACKUP_FILE" | awk '{print $1}')
  test "$actual" = "$expected"
else
  echo "SHA-256 utility is required" >&2
  exit 3
fi
createdb --username="$POSTGRES_USER" "$RESTORE_DATABASE"
pg_restore --exit-on-error --no-owner --username="$POSTGRES_USER" --dbname="$RESTORE_DATABASE" "$BACKUP_FILE"
psql --username="$POSTGRES_USER" --dbname="$RESTORE_DATABASE" --set=ON_ERROR_STOP=1 --command='SELECT version_num FROM alembic_version;'
printf '%s\n' "restore verification completed in isolated database: $RESTORE_DATABASE"
