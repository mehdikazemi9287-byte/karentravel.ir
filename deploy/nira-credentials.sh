#!/usr/bin/env bash
# Add Niira (NRS) airline credentials to /opt/karenseir/.env — append only, never deletes anything.
# The owner runs this in the server console and types each airline's web-service user and password himself.
# Passwords are read hidden (read -s), written only to the server's .env, never echoed or logged.
# Later lines in .env override earlier ones, so a typo is fixed by running again (nothing is removed).
# Usage:  bash /opt/karenseir/app/deploy/nira-credentials.sh            (all airlines below)
#         bash /opt/karenseir/app/deploy/nira-credentials.sh HH J1      (only these)
set -u
ENV=/opt/karenseir/.env
cd /opt/karenseir || exit 1
ALL="HH J1 DZD FP Y9 PA ISP VR"
declare -A FA=([HH]="تابان Taban" [J1]="معراج Meraj" [DZD]="یزد Yazd" [FP]="فلای‌پرشیا FlyPersia" [Y9]="کیش‌ایر KishAir" [PA]="پارس‌ایر ParsAir" [ISP]="جی‌اسکای JSky" [VR]="وارش Varesh")
LIST="${*:-$ALL}"
cp --update=none "$ENV" "$ENV.backup-$(date +%Y%m%d-%H%M%S)-nira" 2>/dev/null || cp -n "$ENV" "$ENV.backup-$(date +%Y%m%d-%H%M%S)-nira"
added=""
for C in $LIST; do
  echo
  echo "== $C  ${FA[$C]:-}   (Enter on an empty line = skip this airline)"
  read -rp "  WS USER (e.g. THR383.WS): " U
  [ -z "$U" ] && { echo "  skipped"; continue; }
  read -rsp "  PASSWORD (hidden): " P; echo
  [ -z "$P" ] && { echo "  skipped (no password)"; unset P; continue; }
  case "$P$U" in *\'*) echo "  this value contains a single quote (') — not supported here, skipped; tell Claude"; unset P; continue;; esac
  # Single quotes: docker compose env_file keeps the value literal (no $ interpolation, no ' #' comment).
  printf "\n# Niira %s (%s)\nNIRA_%s_USER='%s'\nNIRA_%s_PASS='%s'\n" "$C" "$(date -Iseconds)" "$C" "$U" "$C" "$P" >> "$ENV"
  unset P
  added="$added $C"
  echo "  saved"
done
# Enabled airlines = every airline that now has a user+pass in .env
EN=$(for C in $ALL; do grep -q "^NIRA_${C}_PASS=." "$ENV" && grep -q "^NIRA_${C}_USER=." "$ENV" && printf '%s,' "$C"; done)
EN=${EN%,}
printf '# Niira enabled airlines (%s)\nNIRA_MODE=live\nNIRA_AIRLINES=%s\n' "$(date -Iseconds)" "$EN" >> "$ENV"
echo; echo "enabled: $EN"
docker compose up -d api worker >/dev/null 2>&1; sleep 30
docker compose exec -T api python - <<'PY'
from datetime import date, timedelta
from app.nira_nrs import nira_mode, requested_airlines, airline_config, NiraClient
m, _ = nira_mode(); day = date.today() + timedelta(days=1)
for c in requested_airlines():
    cfg, reason, missing = airline_config(c, m)
    if not cfg:
        print(c, "NOT READY:", reason, missing); continue
    try:
        a = NiraClient(m, cfg).availability_fare("THR", "MHD", day)
        print(c, "OK  THR-MHD", day, "flights:", len(a.flights))
    except Exception as e:
        print(c, "ERROR:", getattr(e, "code", type(e).__name__))
PY
