#!/usr/bin/env bash
# KarenSeir — roll back karenseir-https.sh: restore /etc/nginx exactly as it was before the first HTTPS run,
# restore the six HTTPS-related .env keys, put the previous web image back (no rebuild), restart api/web, verify HTTP.
#
#   passwordless sudo:  ssh karen@188.121.123.218 'bash -s' < ~/Downloads/karenseir-https-rollback.sh
#   sudo with password: scp ~/Downloads/karenseir-https-rollback.sh karen@188.121.123.218:/tmp/ && ssh -t karen@188.121.123.218 'bash /tmp/karenseir-https-rollback.sh'
#   a specific backup:  ... 'bash -s -- /opt/karenseir/backups/https-YYYYMMDD-HHMMSS' < ...
#   preview only:       ... 'bash -s -- --check' < ...
#
# Default backup = the newest https-* backup taken BEFORE the script had ever changed nginx (PRIOR_MANAGED empty),
# i.e. the original state even after several HTTPS reruns. Left in place on purpose: the certificate in
# /etc/letsencrypt (harmless, lets a later rerun skip issuance), certbot, and a ufw 443 rule if one was added.
# Web image: the backup records the image that was running before HTTPS (tag <image>:pre-https-<ts>). It is re-tagged
# as the compose image and started with --no-build — but only while the running web image is one karenseir-https.sh
# built (a later normal release would otherwise be downgraded); in every other case web is rebuilt from the current
# checkout with the restored .env, with a warning.
# HSTS: browsers that saw the header keep using https for max-age seconds; with a large max-age a rollback
# to HTTP breaks those visitors, so it is refused unless CONFIRM_HSTS_ROLLBACK=1.
#
# The whole body is functions and only the last line runs main, so with 'bash -s' bash has parsed everything first.
set -Eeuo pipefail

config() {
  DOMAIN=karentravel.ir
  EXPECTED_IP=${EXPECTED_IP:-188.121.123.218}
  APP_DIR=${APP_DIR:-/opt/karenseir}
  MANAGED_NAME=karentravel-https.conf
  ENV_KEYS="CORS_ORIGINS NEXT_PUBLIC_SITE_URL NEXT_PUBLIC_API_URL PUBLIC_WEB_URL ALLOW_HTTP_PREVIEW ALLOW_HTTP_ORIGIN_PREVIEW"
  TS=$(date -u +%Y%m%d-%H%M%S)
  CHECK_ONLY=0; BK=""
  for a in "$@"; do case "$a" in --check) CHECK_ONLY=1;; *) BK=$a;; esac; done
  RUN_TTY="scp ~/Downloads/karenseir-https-rollback.sh karen@$EXPECTED_IP:/tmp/ && ssh -t karen@$EXPECTED_IP 'bash /tmp/karenseir-https-rollback.sh'"
  WORK=""; LOCK=/run/karenseir-https.lock; LOCK_HELD=0; SUDO=""
}
say() { printf '%s\n' "$*"; }
ok()  { printf '  ok   %s\n' "$*"; }
warn() { printf '  WARN %s\n' "$*"; }
die() { printf '\nROLLBACK-FAILED: %s\n' "$*" >&2; exit 1; }
on_err() { [ "$BASHPID" = "$$" ] || exit "$1"; printf '\nROLLBACK-FAILED at line %s (exit %s)\n' "$2" "$1" >&2; exit "$1"; }
on_exit() {
  [ "$BASHPID" = "$$" ] || return 0
  set +e; trap - ERR
  [ -z "$WORK" ] || rm -rf "$WORK"
  [ "$LOCK_HELD" != 1 ] || S rm -rf "$LOCK"
}
S() { if [ -z "$SUDO" ]; then "$@"; else $SUDO "$@"; fi; }

setup_sudo() {
  INTERACTIVE=0; [ -t 0 ] && [ -t 1 ] && INTERACTIVE=1
  if [ "$(id -u)" -eq 0 ]; then SUDO=""
  elif sudo -n true 2>/dev/null; then SUDO="sudo -n"
  elif [ "$INTERACTIVE" = 1 ]; then sudo -v || exit 1; SUDO="sudo"; ( while kill -0 $$ 2>/dev/null; do sudo -n true 2>/dev/null || true; sleep 50; done ) &
  else echo "ABORT: sudo needs a password and there is no terminal. Run:  $RUN_TTY"; exit 2; fi
}
lock_acquire() { # same root-owned lock as karenseir-https.sh; mkdir is atomic and does not follow symlinks
  local old
  if ! S mkdir -m 0700 "$LOCK" 2>/dev/null; then
    old=$(S cat "$LOCK/pid" 2>/dev/null || true)
    if [ -n "$old" ] && ps -p "$old" >/dev/null 2>&1; then echo "a karenseir-https run is active (pid $old)"; exit 1; fi
    S rm -rf "$LOCK"; S mkdir -m 0700 "$LOCK" 2>/dev/null || { echo "cannot take lock $LOCK"; exit 1; }
  fi
  LOCK_HELD=1; echo "$$" | S tee "$LOCK/pid" >/dev/null
}
bget() { awk -F= -v k="$1" '$1==k{print substr($0,index($0,"=")+1); found=1; exit} END{if(!found) print "<absent>"}' "$BK/env.bak"; }
cget() { awk -F= -v k="$1" '$1==k{print substr($0,index($0,"=")+1); found=1; exit} END{if(!found) print "<absent>"}' .env; }
sget() { sed -n "s/^$1=//p" "$BK/STATE" 2>/dev/null | tail -1; }

choose_backup() {
  say "== 0/4 choose backup"
  if [ -z "$BK" ]; then
    for d in $(ls -1d "$APP_DIR"/backups/https-2* 2>/dev/null | sort -r); do
      if [ -f "$d/STATE" ] && grep -qx 'PRIOR_MANAGED=' "$d/STATE"; then BK=$d; break; fi
    done
  fi
  { [ -n "$BK" ] && [ -f "$BK/etc-nginx.tgz" ] && [ -f "$BK/env.bak" ]; } || die "no usable backup (need etc-nginx.tgz + env.bak); pass one: bash -s -- $APP_DIR/backups/https-…"
  ok "backup $BK"
  S tar -tzf "$BK/etc-nginx.tgz" >/dev/null || die "backup tar unreadable"
  ENV_DIFF=0
  for k in $ENV_KEYS; do b=$(bget "$k"); c=$(cget "$k"); [ "$b" = "$c" ] || { ENV_DIFF=1; say "       .env $k: '$c' → '$b'"; }; done
  [ "$ENV_DIFF" = 1 ] || ok ".env keys already equal to the backup"

  # web image plan: retag (no build) | rebuild | none
  IMG_REF=$(sget WEB_IMAGE_REF); IMG_TAG=$(sget WEB_IMAGE_TAG); IMG_PRE=$(sget WEB_IMAGE_PRE)
  cid=$(docker compose ps -q web 2>/dev/null | head -1 || true)
  CUR_IMG=""; [ -z "$cid" ] || CUR_IMG=$(docker inspect -f '{{.Image}}' "$cid" 2>/dev/null || true)
  posts=$(cat "$APP_DIR"/backups/https-2*/STATE 2>/dev/null | sed -n 's/^WEB_IMAGE_POST=//p' | sort -u || true)
  WEB_PLAN=none
  if [ -n "$IMG_PRE" ] && [ "$CUR_IMG" = "$IMG_PRE" ]; then
    WEB_PLAN=none; ok "web already runs the pre-HTTPS image"
  elif [ -n "$IMG_TAG" ] && [ -n "$IMG_REF" ] && docker image inspect "$IMG_TAG" >/dev/null 2>&1; then
    if [ -n "$CUR_IMG" ] && grep -qxF "$CUR_IMG" <<<"$posts"; then WEB_PLAN=retag; ok "web: previous image $IMG_TAG will be restored (no rebuild)"
    else WEB_PLAN=rebuild; warn "running web image was not built by karenseir-https.sh (a release since?) — web will be REBUILT from the current checkout instead of restoring $IMG_TAG"; fi
  elif [ "$ENV_DIFF" = 1 ]; then
    WEB_PLAN=rebuild; warn "previous web image tag ${IMG_TAG:-<not recorded>} not available — falling back to a web rebuild"
  fi

  hsts=0
  for f in /etc/nginx/sites-available/$MANAGED_NAME /etc/nginx/conf.d/$MANAGED_NAME; do
    [ ! -f "$f" ] || hsts=$(sed -n 's/.*Strict-Transport-Security "max-age=\([0-9]*\)".*/\1/p' "$f" | head -1); [ -n "$hsts" ] || hsts=0
    [ "$hsts" = 0 ] || break
  done
  say "       current HSTS max-age: $hsts"
  if [ "$hsts" -gt 86400 ] && [ "${CONFIRM_HSTS_ROLLBACK:-0}" != 1 ]; then
    die "HSTS max-age=$hsts is live: visitors' browsers will refuse plain HTTP for that long. Lower it first (rerun karenseir-https.sh with HSTS_MAX_AGE=0 and wait the old max-age) or pass CONFIRM_HSTS_ROLLBACK=1"
  fi
}

restore_nginx() {
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
}

restore_env_and_web() {
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
  else ok ".env unchanged"; fi
  say "== 3/4 web image + restart api/web (plan: $WEB_PLAN)"
  case "$WEB_PLAN" in
    retag)
      docker tag "$IMG_TAG" "$IMG_REF"; ok "$IMG_REF ← $IMG_TAG"
      docker compose up -d --no-build --force-recreate web </dev/null >/dev/null;;
    rebuild)
      docker compose build web </dev/null >/tmp/karenseir-https-rollback-build.log 2>&1 || { tail -30 /tmp/karenseir-https-rollback-build.log; die "web build failed"; }
      docker compose up -d --no-build web </dev/null >/dev/null;;
  esac
  if [ "$ENV_DIFF" = 1 ] || [ "$WEB_PLAN" != none ]; then
    docker compose up -d --no-build api </dev/null >/dev/null
    for i in $(seq 1 40); do
      if docker compose exec -T api python -c "import urllib.request;urllib.request.urlopen('http://127.0.0.1:8000/health',timeout=3)" </dev/null >/dev/null 2>&1; then break; fi
      [ "$i" != 40 ] || { docker compose logs --tail 30 api </dev/null; die "api not healthy"; }; sleep 5
    done; ok "api healthy"
  else ok "nothing to restart"; fi
}

verify() {
  say "== 4/4 verify"
  local c h i
  for i in $(seq 1 20); do
    c=$(curl -sS -m 15 --resolve "$DOMAIN:80:127.0.0.1" -o /dev/null -w '%{http_code}' "http://$DOMAIN/" || true)
    [ "$c" != 200 ] || break; sleep 3
  done
  h=$(curl -sS -m 15 --resolve "$DOMAIN:80:127.0.0.1" -o /dev/null -w '%{http_code}' "http://$DOMAIN/api/health" || true)
  say "       http://$DOMAIN/ → $c ; /api/health → $h"
  { [ "$c" = 200 ] && [ "$h" = 200 ]; } || die "site not healthy after rollback (pre-rollback copy in $RB)"
  say "ROLLBACK-OK restored $(basename "$BK") $(date -u +%FT%TZ)  (certificate kept in /etc/letsencrypt; reapply with karenseir-https.sh)"
}

main() {
  config "$@"
  trap 'on_err $? $LINENO' ERR
  trap on_exit EXIT
  setup_sudo
  exec </dev/null   # the whole script is parsed already; nothing below may read stdin ('bash -s')
  WORK=$(mktemp -d)
  lock_acquire
  cd "$APP_DIR" 2>/dev/null || die "$APP_DIR not found"
  choose_backup
  [ "$CHECK_ONLY" = 0 ] || { say "ROLLBACK-CHECK-OK (nothing changed)"; exit 0; }
  restore_nginx
  restore_env_and_web
  verify
}

[ "${KARENSEIR_HTTPS_LIB:-0}" = 1 ] || main "$@"
