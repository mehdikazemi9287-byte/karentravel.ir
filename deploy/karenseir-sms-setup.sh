#!/usr/bin/env bash
# KarenSeir — connect login SMS (Kavenegar Verify/Lookup) on the production server.
# Run ON THE MAC (not on the server):   bash ~/Downloads/karenseir-sms-setup.sh
# Optional: TEMPLATE=karenotp bash ~/Downloads/karenseir-sms-setup.sh
#   default TEMPLATE=karentest ("تست فنی" template: SMS reaches only the Kavenegar account owner's number)
#
# The API key is asked here with hidden input and sent to the server over ssh stdin; it is never
# printed, never put on a command line, and never stored on the Mac.
# On the server: backs up .env, sets KARENSEIR_SMS_PROVIDER / KAVENEGAR_OTP_TEMPLATE / KAVENEGAR_API_KEY,
# checks the api service really receives them, recreates api + worker, waits for health.
# Anything unexpected → .env is restored from the backup.
set -euo pipefail

HOST="${HOST:-karen@188.121.123.218}"
TEMPLATE="${TEMPLATE:-karentest}"
case "$TEMPLATE" in ""|*[!A-Za-z0-9_-]*) echo "invalid TEMPLATE"; exit 1;; esac

printf 'Kavenegar API key (hidden): '
IFS= read -rs KEY; echo
case "$KEY" in ""|*[!A-Za-z0-9+/=_-]*) echo "ABORT: the key looks empty or has unexpected characters"; exit 1;; esac

remote_body() {
cat <<'REMOTE'
main() {
set -euo pipefail
cd /opt/karenseir
TS=$(date +%Y%m%d-%H%M%S)
BK=".env.bak-sms-$TS"
cp -p .env "$BK"
restore() { cat "$BK" > .env; echo "RESTORED .env from $BK"; }
setkv() {  # setkv NAME VALUE  — replace or append; the value is never echoed
  local tmp; tmp=$(mktemp); grep -v "^$1=" .env > "$tmp" || true
  printf '%s=%s\n' "$1" "$2" >> "$tmp"; cat "$tmp" > .env; rm -f "$tmp"
}
setkv KARENSEIR_SMS_PROVIDER kavenegar
setkv KAVENEGAR_OTP_TEMPLATE "$TEMPLATE"
setkv KAVENEGAR_API_KEY "$KEY"
unset KEY
chmod 600 .env
# Does the api service actually receive the three variables? (count only — the key is never printed)
cfg=$(docker compose config 2>/dev/null) || { echo "ABORT: docker compose config failed"; restore; exit 1; }
n=$(printf '%s\n' "$cfg" | awk '/^  api:$/{f=1;next} /^  [a-z][a-z0-9_-]*:$/{f=0} f' | grep -cE 'KARENSEIR_SMS_PROVIDER|KAVENEGAR_OTP_TEMPLATE|KAVENEGAR_API_KEY' || true)
unset cfg
if [ "${n:-0}" -lt 3 ]; then
  echo "ABORT: the api service does not receive these variables (found ${n:-0} of 3)."
  echo "       docker-compose.yml needs env_file: .env for api (or the three names under environment:). Nothing was restarted."
  restore; exit 2
fi
echo "env OK for api (${n}/3). Recreating api + worker..."
docker compose up -d --no-build api worker
i=0
until curl -fsS -m 5 -H 'Host: karentravel.ir' http://127.0.0.1/api/health >/dev/null; do
  i=$((i+1))
  if [ "$i" -ge 30 ]; then echo "HEALTH FAILED — restoring .env and restarting"; restore; docker compose up -d --no-build api worker; exit 3; fi
  sleep 4
done
echo "inside api: provider=$(docker compose exec -T api printenv KARENSEIR_SMS_PROVIDER) template=$(docker compose exec -T api printenv KAVENEGAR_OTP_TEMPLATE)"
echo "SMS-SETUP-OK (backup /opt/karenseir/$BK). Now request a login code on the site with the Kavenegar account owner's number."
}
main </dev/null
REMOTE
}

# Line 1 of stdin = the key (read by the remote shell), the rest = the script for bash -s.
{ printf '%s\n' "$KEY"; remote_body; } | ssh "$HOST" "IFS= read -r KEY && export KEY && TEMPLATE='$TEMPLATE' exec bash -s"
