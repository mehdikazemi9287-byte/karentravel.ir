#!/usr/bin/env bash
# KarenSeir — roll back karenseir-https.sh: restore /etc/nginx exactly as it was before the first HTTPS run,
# restore the six HTTPS-related .env keys, rebuild web, restart api/web, verify the HTTP site.
#
#   passwordless sudo:  ssh karen@188.121.123.218 'bash -s' < ~/Downloads/karenseir-https-rollback.sh
#   sudo with password: scp ~/Downloads/karenseir-https-rollback.sh karen@188.121.123.218:/tmp/ && ssh -t karen@188.121.123.218 'bash /tmp/karenseir-https-rollback.sh'
#   a specific backup:  ... 'bash -s -- /opt/karenseir/backups/https-YYYYMMDD-HHMMSS' < ...
#   preview only:       ... 'bash -s -- --check' < ...
#
# Default backup = the newest https-* backup taken BEFORE the script had ever changed nginx (PRIOR_MANAGED empty),
# i.e. the original state even after several HTTPS reruns. Left in place on purpose: the certificate in
# /etc/letsencrypt (harmless, lets a later rerun skip issuance), certbot, and a ufw 443 rule if one was added.
# HSTS: browsers that saw the header keep using https for max-age seconds; with a large max-age a rollback
# to HTTP breaks those visitors, so it is refused unless CONFIRM_HSTS_ROLLBACK=1.
set -euo pipefail

DOMAIN=karentravel.ir
EXPECTED_IP=${EXPECTED_IP:-188.121.123.218}
APP_DIR=${APP_DIR:-/opt/karenseir}
MANAGED_NAME=karentravel-https.conf
ENV_KEYS="CORS_ORIGINS NEXT_PUBLIC_SITE_URL NEXT_PUBLIC_API_URL PUBLIC_WEB_URL ALLOW_HTTP_PREVIEW ALLOW_HTTP_ORIGIN_PREVIEW"
TS=$(date -u +%Y%m%d-%H%M%S)
CHECK_ONLY=0; BK=""
for a in "$@"; do case "$a" in --check) CHECK_ONLY=1;; *) BK=$a;; esac; done
RUN_TTY="scp ~/Downloads/karenseir-https-rollback.sh karen@$EXPECTED_IP:/tmp/ && ssh -t karen@$EXPECTED_IP 'bash /tmp/karenseir-https-rollback.sh'"
trap 'rc=$?; printf "\nROLLBACK-FAILED at line %s (exit %s)\n" "$LINENO" "$rc" >&2; exit $rc' ERR
say() { printf '%s\n' "$*"; }
ok()  { printf '  ok   %s\n' "$*"; }
die() { printf '\nROLLBACK-FAILED: %s\n' "$*" >&2; exit 1; }

INTERACTIVE=0; [ -t 0 ] && [ -t 1 ] && INTERACTIVE=1
if [ "$(id -u)" -eq 0 ]; then SUDO=""
elif sudo -n true 2>/dev/null; then SUDO="sudo -n"
elif [ "$INTERACTIVE" = 1 ]; then sudo -v || exit 1; SUDO="sudo"; ( while kill -0 $$ 2>/dev/null; do sudo -n true 2>/dev/null; sleep 50; done ) &
else echo "ABORT: sudo needs a password and there is no terminal. Run:  $RUN_TTY"; exit 2; fi
exec </dev/null
S() { if [ -z "$SUDO" ]; then "$@"; else $SUDO "$@"; fi; }
WORK=$(mktemp -d); trap 'rm -rf "$WORK"' EXIT
exec 9>"/tmp/karenseir-https.lock"; flock -n 9 || { echo "a karenseir-https run is active"; exit 1; }
cd "$APP_DIR"

say "== 0/4 choose backup"
if [ -z "$BK" ]; then
  for d in $(ls -1d "$APP_DIR"/backups/https-2* 2>/dev/null | sort -r); do
    [ -f "$d/STATE" ] && grep -qx 'PRIOR_MANAGED=' "$d/STATE" && { BK=$d; break; }
  done
fi
[ -n "$BK" ] && [ -f "$BK/etc-nginx.tgz" ] && [ -f "$BK/env.bak" ] || die "no usable backup (need etc-nginx.tgz + env.bak); pass one: bash -s -- $APP_DIR/backups/https-…"
ok "backup $BK"
S tar -tzf "$BK/etc-nginx.tgz" >/dev/null || die "backup tar unreadable"
bget() { awk -F= -v k="$1" '$1==k{print substr($0,index($0,"=")+1); found=1; exit} END{if(!found) print "<absent>"}' "$BK/env.bak"; }
cget() { awk -F= -v k="$1" '$1==k{print substr($0,index($0,"=")+1); found=1; exit} END{if(!found) print "<absent>"}' .env; }
ENV_DIFF=0
for k in $ENV_KEYS; do b=$(bget "$k"); c=$(cget "$k"); [ "$b" = "$c" ] || { ENV_DIFF=1; say "       .env $k: '$c' → '$b'"; }; done
[ "$ENV_DIFF" = 0 ] && ok ".env keys already equal to the backup"
hsts=0
for f in /etc/nginx/sites-available/$MANAGED_NAME /etc/nginx/conf.d/$MANAGED_NAME; do
  [ -f "$f" ] && hsts=$(sed -n 's/.*Strict-Transport-Security "max-age=\([0-9]*\)".*/\1/p' "$f" | head -1); [ -n "$hsts" ] || hsts=0
  [ "$hsts" != 0 ] && break
done
say "       current HSTS max-age: $hsts"
if [ "$hsts" -gt 86400 ] && [ "${CONFIRM_HSTS_ROLLBACK:-0}" != 1 ]; then
  die "HSTS max-age=$hsts is live: visitors' browsers will refuse plain HTTP for that long. Lower it first (rerun karenseir-https.sh with HSTS_MAX_AGE=0 and wait the old max-age) or pass CONFIRM_HSTS_ROLLBACK=1"
fi
[ "$CHECK_ONLY" = 1 ] && { say "ROLLBACK-CHECK-OK (nothing changed)"; exit 0; }

say "== 1/4 nginx → state of $(basename "$BK")"
RB="$APP_DIR/backups/https-rollback-$TS"; mkdir -p "$RB"; chmod 700 "$RB"
S tar -czf "$RB/etc-nginx-before-rollback.tgz" -C / etc/nginx; cp -p .env "$RB/env-before-rollback"; chmod 600 "$RB/env-before-rollback"
S mv /etc/nginx "/etc/nginx.rollback-$TS"
if ! S tar -xzf "$BK/etc-nginx.tgz" -C / || ! S nginx -t >"$WORK/nt" 2>&1; then
  cat "$WORK/nt" >&2 || true
  S rm -rf /etc/nginx; S mv "/etc/nginx.rollback-$TS" /etc/nginx
  die "restored nginx config fails nginx -t — current config put back unchanged"
fi
S rm -rf "/etc/nginx.rollback-$TS"
S systemctl reload nginx; ok "nginx restored and reloaded (pre-rollback copy: $RB)"

say "== 2/4 .env"
if [ "$ENV_DIFF" = 1 ]; then
  cp -p .env "$WORK/env"
  for k in $ENV_KEYS; do
    b=$(bget "$k")
    if [ "$b" = "<absent>" ]; then awk -F= -v k="$k" '$1!=k' "$WORK/env" >"$WORK/e2"
    else awk -F= -v k="$k" -v v="$b" 'BEGIN{d=0} $1==k{ if(!d){print k"="v; d=1}; next } {print} END{ if(!d) print k"="v }' "$WORK/env" >"$WORK/e2"; fi
    cat "$WORK/e2" >"$WORK/env"
  done
  cat "$WORK/env" >.env; ok ".env keys restored"
  say "== 3/4 rebuild web + restart api/web"
  docker compose build web </dev/null >/tmp/karenseir-https-rollback-build.log 2>&1 || { tail -30 /tmp/karenseir-https-rollback-build.log; die "web build failed"; }
  docker compose up -d api web </dev/null >/dev/null
  for i in $(seq 1 40); do
    docker compose exec -T api python -c "import urllib.request;urllib.request.urlopen('http://127.0.0.1:8000/health',timeout=3)" </dev/null >/dev/null 2>&1 && break
    [ "$i" = 40 ] && { docker compose logs --tail 30 api </dev/null; die "api not healthy"; }; sleep 5
  done; ok "api healthy"
else say "== 3/4 nothing to rebuild"; fi

say "== 4/4 verify"
sleep 3
c=$(curl -sS -m 15 --resolve "$DOMAIN:80:127.0.0.1" -o /dev/null -w '%{http_code}' "http://$DOMAIN/" || true)
h=$(curl -sS -m 15 --resolve "$DOMAIN:80:127.0.0.1" -o /dev/null -w '%{http_code}' "http://$DOMAIN/api/health" || true)
say "       http://$DOMAIN/ → $c ; /api/health → $h"
[ "$c" = 200 ] && [ "$h" = 200 ] || die "site not healthy after rollback (pre-rollback copy in $RB)"
say "ROLLBACK-OK restored $(basename "$BK") $(date -u +%FT%TZ)  (certificate kept in /etc/letsencrypt; reapply with karenseir-https.sh)"
