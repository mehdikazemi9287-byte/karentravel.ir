#!/bin/sh
set -eu

: "${PUBLIC_WEB_URL:?set PUBLIC_WEB_URL to the authorized HTTPS frontend URL}"
: "${PUBLIC_API_URL:?set PUBLIC_API_URL to the authorized HTTPS API URL}"

case "$PUBLIC_WEB_URL $PUBLIC_API_URL" in
  *your-domain.example*|*localhost*|*127.0.0.1*) echo 'placeholder/local addresses are not public production' >&2; exit 1 ;;
esac
case "$PUBLIC_WEB_URL $PUBLIC_API_URL" in
  https://*' https://'*) ;;
  *) echo 'both public endpoints must use HTTPS' >&2; exit 1 ;;
esac

curl --fail --silent --show-error --proto '=https' --tlsv1.2 "$PUBLIC_WEB_URL/" >/dev/null
ready="$(curl --fail --silent --show-error --proto '=https' --tlsv1.2 "$PUBLIC_API_URL/ready")"
metrics="$(curl --fail --silent --show-error --proto '=https' --tlsv1.2 "$PUBLIC_API_URL/metrics")"
printf '%s' "$ready" | grep -q '"status":"ready"'
printf '%s' "$ready" | grep -q '"rate_limiter":"distributed"'
printf '%s' "$metrics" | grep -q 'karenseir_http_requests_total'

printf '%s\n' 'public production DNS/TLS/readiness/metrics validation passed'
