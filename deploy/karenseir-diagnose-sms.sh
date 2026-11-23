#!/usr/bin/env bash
# KarenSeir — READ-ONLY diagnostic for login SMS (Kavenegar Verify/Lookup).
#
# Run ON THE SERVER (ArvanCloud web console or ssh), from the compose project:
#   cd /opt/karenseir && bash app/deploy/karenseir-diagnose-sms.sh
#   (or: bash /path/to/karenseir-diagnose-sms.sh   — it cd's to /opt/karenseir itself)
#
# What it does — and does NOT do:
#   * changes nothing: no .env edit, no restart, no rebuild, no DB write;
#   * sends NO SMS: the only Kavenegar call is account/info.json (credit/expiry lookup);
#   * never prints a secret: env values are shown as length + last 2 characters only,
#     phone numbers in logs are cut to their last 4 digits, the API key is never echoed.
# Options (env): ROOT=/opt/karenseir  SERVICE=api  SINCE=48h  LINES=40
set -uo pipefail

ROOT="${ROOT:-/opt/karenseir}"
SERVICE="${SERVICE:-api}"
SINCE="${SINCE:-48h}"
LINES="${LINES:-40}"
case "$SINCE" in *[!0-9a-z]*|"") echo "invalid SINCE"; exit 1;; esac
case "$LINES" in *[!0-9]*|"") echo "invalid LINES"; exit 1;; esac

cd "$ROOT" 2>/dev/null || { echo "ABORT: $ROOT not found"; exit 1; }
say() { printf '\n== %s ==\n' "$*"; }

say "1. deployed version"
[ -f DEPLOYED ] && sed -n '1,5p' DEPLOYED || echo "(no $ROOT/DEPLOYED file)"
docker compose ps --format '{{.Name}}\t{{.Status}}' 2>/dev/null | grep -E "(^|[-_])($SERVICE|worker)([-_]|$)" || echo "(could not list $SERVICE container)"

say "2. SMS/OTP variable NAMES in $ROOT/.env (values not read)"
if [ -r .env ]; then
  grep -oE '^(KAVENEGAR_[A-Z0-9_]*|KARENSEIR_SMS_PROVIDER|SMS_[A-Z0-9_]*|OTP_[A-Z0-9_]*|NOTIFICATION_PROVIDER_MODE)=' .env | tr -d '=' | sort -u | sed 's/^/  .env: /'
  [ "${PIPESTATUS[0]}" = "0" ] || echo "  (none found in .env)"
else
  echo "  (.env not readable by this user)"
fi

say "3. inside the running $SERVICE container: names, masked values, selected adapter"
docker compose exec -T "$SERVICE" python - <<'PY' 2>&1 || echo "  (exec into $SERVICE failed — is the container running?)"
import os, re
pat = re.compile(r"^(KAVENEGAR_|KARENSEIR_SMS|SMS_|OTP_|NOTIFICATION_PROVIDER|PROVIDER_RESILIENCE)")
names = sorted(n for n in os.environ if pat.match(n))
def mask(v):
    return f"len={len(v)}" + (f" ..{v[-2:]}" if len(v) > 6 else "")
if not names:
    print("  NO KAVENEGAR/SMS/OTP variables reach this container.")
    print("  -> the compose file does not pass them to the service (needs env_file: .env or environment: entries).")
for n in names:
    print(f"  {n}: {mask(os.environ[n])}")
# Non-secret settings, shown in clear so the mode is unambiguous.
for n in ("KARENSEIR_SMS_PROVIDER", "OTP_PROVIDER_MODE", "NOTIFICATION_PROVIDER_MODE", "KAVENEGAR_OTP_TEMPLATE"):
    v = os.environ.get(n)
    print(f"  [setting] {n} = {v!r}" if v is not None else f"  [setting] {n} is NOT set")
try:
    from app.providers import ADAPTERS
    otp = ADAPTERS["otp"]
    inner = getattr(otp, "adapter", otp)
    h = otp.health()
    print(f"  selected OTP adapter: {type(inner).__name__} mode={getattr(inner, 'mode', '?')} health={h.status}")
    if type(inner).__name__ != "KavenegarSmsOtpProvider":
        print("  -> login codes are NOT sent via Kavenegar (KARENSEIR_SMS_PROVIDER must equal 'kavenegar' exactly).")
except Exception as exc:  # noqa: BLE001
    print(f"  could not load app.providers: {type(exc).__name__}")
PY

say "4. Kavenegar account/info.json from inside $SERVICE (no SMS is sent)"
docker compose exec -T "$SERVICE" python - <<'PY' 2>&1 || echo "  (exec into $SERVICE failed)"
import json, os, time
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen
try:
    from app.config import read_secret
    key = (read_secret("KAVENEGAR_API_KEY") or "").strip()
except Exception as exc:  # noqa: BLE001
    print(f"  could not read KAVENEGAR_API_KEY(_FILE): {type(exc).__name__}")
    key = (os.environ.get("KAVENEGAR_API_KEY") or "").strip()
if not key:
    print("  KAVENEGAR_API_KEY is empty in this container -> nothing to check.")
    print("  (an empty key also explains an 'unknown method' (404) answer: the URL becomes /v1//account/info.json)")
    raise SystemExit(0)
HINTS = {200: "OK", 401: "account disabled", 403: "API key invalid", 404: "unknown method / wrong URL",
         405: "wrong HTTP method", 407: "blocked by account security (allowed-IP list) settings",
         418: "insufficient credit", 426: "method needs an upgraded plan", 451: "too many calls from this IP"}
url = f"https://api.kavenegar.com/v1/{quote(key, safe='')}/account/info.json"
req = Request(url, data=b"", method="POST", headers={"Accept": "application/json", "Content-Type": "application/x-www-form-urlencoded"})
http_status, body = None, None
try:
    with urlopen(req, timeout=10) as resp:  # noqa: S310 - fixed Kavenegar host
        http_status, raw = resp.status, resp.read()
except HTTPError as exc:
    http_status, raw = exc.code, exc.read()
except URLError as exc:
    reason = str(getattr(exc, "reason", exc)).replace(key, "***")
    print(f"  NETWORK: cannot reach api.kavenegar.com ({reason[:120]})")
    raise SystemExit(0)
except Exception as exc:  # noqa: BLE001
    print(f"  NETWORK: {type(exc).__name__}")
    raise SystemExit(0)
try:
    body = json.loads(raw.decode("utf-8"))
except Exception:  # noqa: BLE001
    body = None
ret = (body or {}).get("return") or {} if isinstance(body, dict) else {}
status = ret.get("status")
print(f"  HTTP status: {http_status}")
print(f"  return.status: {status} ({HINTS.get(status, 'see Kavenegar status table')})")
entries = (body or {}).get("entries") if isinstance(body, dict) else None
if status == 200 and isinstance(entries, dict):
    credit = entries.get("remaincredit")
    exp = entries.get("expiredate")
    exp_txt = time.strftime("%Y-%m-%d", time.gmtime(int(exp))) if str(exp or "").isdigit() else exp
    print(f"  remaincredit: {credit}")
    print(f"  expiredate:   {exp_txt}")
    print(f"  account type: {entries.get('type')}")
PY

say "5. recent $SERVICE log lines about OTP/SMS/Kavenegar (last $LINES, since $SINCE; phones -> last 4 digits)"
docker compose logs --no-color --since "$SINCE" "$SERVICE" 2>/dev/null \
  | grep -iE 'otp|kavenegar|sms|register/request' \
  | sed -E \
      -e 's#/v1/[^/ ]+/#/v1/***/#g' \
      -e 's/(\+?98|0098|0)?9[0-9]{5}([0-9]{4})/***\2/g' \
  | tail -n "$LINES"
[ "${PIPESTATUS[1]}" = "0" ] || echo "  (no matching log lines)"

say "summary"
cat <<'TXT'
  * section 3 must show KARENSEIR_SMS_PROVIDER = 'kavenegar', a template name, and
    "selected OTP adapter: KavenegarSmsOtpProvider". If not, the code is never sent.
  * section 4 return.status 200 + credit > 0 means the key works from this server.
  * otp_throttled / sms_daily_cap_reached in logs = local limits, not a Kavenegar fault.
  * Live delivery is proven only when a requested login code actually arrives on a phone.
This script changed nothing and sent no SMS.
TXT
