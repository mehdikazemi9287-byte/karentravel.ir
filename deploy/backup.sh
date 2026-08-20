#!/bin/sh
set -eu

: "${BACKUP_DIR:?set BACKUP_DIR to an explicit protected directory}"
: "${POSTGRES_USER:?set POSTGRES_USER}"
: "${POSTGRES_DB:?set POSTGRES_DB}"

case "$BACKUP_DIR" in
  /|"") echo "unsafe BACKUP_DIR" >&2; exit 2 ;;
esac

umask 077
mkdir -p "$BACKUP_DIR"
stamp=$(date -u +%Y%m%dT%H%M%SZ)
target="$BACKUP_DIR/karenseir-$stamp.dump"
pg_dump --format=custom --no-owner --file="$target" --username="$POSTGRES_USER" "$POSTGRES_DB"
pg_restore --list "$target" >/dev/null
if command -v sha256sum >/dev/null 2>&1; then
  sha256sum "$target" > "$target.sha256"
elif command -v shasum >/dev/null 2>&1; then
  shasum -a 256 "$target" > "$target.sha256"
else
  echo "SHA-256 utility is required" >&2
  exit 3
fi
printf '%s\n' "$target"
