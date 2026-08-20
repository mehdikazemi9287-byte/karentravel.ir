#!/bin/sh
set -eu

required='JWT_SECRET POSTGRES_PASSWORD CORS_ORIGINS REDIS_URL WORKER_DATABASE_URL'
for name in $required; do
  eval "value=\${$name:-}"
  eval "file=\${${name}_FILE:-}"
  if test -n "$value" && test -n "$file"; then
    echo "$name and ${name}_FILE cannot both be configured" >&2
    exit 1
  fi
  if test -n "$file"; then
    test -f "$file" && test ! -L "$file" || { echo "invalid secret file: ${name}_FILE" >&2; exit 1; }
    test -z "$(find "$file" -perm -077 -print)" || { echo "unsafe secret file permissions: ${name}_FILE" >&2; exit 1; }
    value="$(sed -n '1p' "$file")"
  fi
  test -n "$value" || { echo "missing required secret/config: $name" >&2; exit 1; }
  case "$value" in replace-with-*|*your-domain.example*) echo "placeholder value rejected: $name" >&2; exit 1 ;; esac
  case "$name" in
    JWT_SECRET) jwt_secret_value="$value" ;;
    CORS_ORIGINS) cors_origins_value="$value" ;;
  esac
done

case "$cors_origins_value" in https://*) ;; *) echo 'CORS_ORIGINS must use HTTPS' >&2; exit 1 ;; esac
test "${#jwt_secret_value}" -ge 32 || { echo 'JWT_SECRET must be at least 32 characters' >&2; exit 1; }
printf '%s\n' 'production preflight passed'
