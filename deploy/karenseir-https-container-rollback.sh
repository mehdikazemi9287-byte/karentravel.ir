#!/usr/bin/env bash
# KarenSeir — roll back deploy/karenseir-https-container.sh (container nginx layout in /opt/karenseir).
#   preview:            ssh karen@188.121.123.218 'bash -s -- --check' < ~/Downloads/karenseir-https-container-rollback.sh
#   rollback (latest):  ssh karen@188.121.123.218 'bash -s' < ~/Downloads/karenseir-https-container-rollback.sh
#   a given backup:     ssh karen@188.121.123.218 'bash -s -- /opt/karenseir/backups/https-YYYYMMDD-HHMMSS' < ...
# Default backup = the newest https-* backup taken while default.conf was still the original (PRIOR_MANAGED empty),
# i.e. the pre-HTTPS state even after several reruns.
# Restores: nginx/default.conf (written IN PLACE — single-file bind mount), .env, docker-compose.yml/override,
# removes the managed overlay, re-tags the previous web image (no rebuild), up -d --no-build web api worker,
# nginx -t + reload, removes the renewal cron line, verifies HTTP. Certificates in /opt/karenseir/certs stay.
# HSTS: browsers that saw it keep using https for max-age seconds (start value 300 → wait 5 minutes). If the live
# config has max-age > 86400 the rollback is refused unless FORCE=1.
set -Eeuo pipefail

config() {
  DOMAIN=${DOMAIN:-karentravel.ir}
  EXPECTED_IP=${EXPECTED_IP:-188.121.123.218}
  ROOT=${ROOT:-/opt/karenseir}
  CONF=$ROOT/nginx/default.conf
  OVERLAY=docker-compose.https.yml
  CRON_MARK="# karenseir-https-container: certbot renew"
  FORCE=${FORCE:-0}
  KT_SLEEP=${KT_SLEEP:-5}
  TS=$(date -u +%Y%m%d-%H%M%S)
  CHECK_ONLY=0 BK=""
  for a in "$@"; do case "$a" in --check) CHECK_ONLY=1;; -*) echo "unknown option $a"; exit 2;; *) BK=$a;; esac; done
  WORK="" LOCK="" LOCK_HELD=0
}
say()  { printf '%s\n' "$*"; }
ok()   { printf '  ok   %s\n' "$*"; }
warn() { printf '  WARN %s\n' "$*"; }
die()  { printf '\nROLLBACK-FAILED: %s\n' "$*" >&2; exit 1; }
dc()   { docker compose "$@" </dev/null; }
on_err() { [ "$BASHPID" = "$$" ] || exit "$1"; printf '\nROLLBACK-FAILED at line %s (exit %s)\n' "$2" "$1" >&2; exit "$1"; }
on_exit() {
  [ "$BASHPID" = "$$" ] || return 0
  set +e; trap - ERR
  [ -z "$WORK" ] || rm -rf "$WORK"
  [ "$LOCK_HELD" != 1 ] || rm -rf "$LOCK"
}
lock_acquire() { # same lock as the apply script
  LOCK="$HOME/.karenseir-https-container.lock"
  local old
  if ! mkdir -m 0700 "$LOCK" 2>/dev/null; then
    old=$(cat "$LOCK/pid" 2>/dev/null || true)
    if [ -n "$old" ] && ps -p "$old" >/dev/null 2>&1; then echo "a karenseir-https-container run is active (pid $old)"; exit 1; fi
    rm -rf "$LOCK"; mkdir -m 0700 "$LOCK" 2>/dev/null || { echo "cannot take lock $LOCK"; exit 1; }
  fi
  LOCK_HELD=1; echo "$$" >"$LOCK/pid"
}
sget() { sed -n "s/^$1=//p" "$BK/STATE" 2>/dev/null | tail -1; }
restore_file() { [ -f "$1" ] || return 0; cmp -s "$1" "$2" && return 0; cat "$1" >"$2"; }
http_code() { curl -sS -m 15 --resolve "$DOMAIN:80:127.0.0.1" -o /dev/null -w '%{http_code}' "$1" 2>/dev/null || true; }

plan() {
  say "== 0 plan (read-only)"
  cd "$ROOT" 2>/dev/null || die "$ROOT not found"
  local d
  if [ -z "$BK" ]; then
    for d in $(find "$ROOT/backups" -maxdepth 1 -type d -name 'https-2*' 2>/dev/null | sort -r); do
      if [ -f "$d/STATE" ] && grep -qx 'PRIOR_MANAGED=' "$d/STATE"; then BK=$d; break; fi
    done
  fi
  { [ -n "$BK" ] && [ -f "$BK/default.conf" ] && [ -f "$BK/env" ] && [ -f "$BK/STATE" ]; } || die "no usable backup (need default.conf, env, STATE); pass one: bash -s -- $ROOT/backups/https-…"
  ok "backup $BK"
  head -1 "$BK/default.conf" | grep -q '^# managed-by: karenseir-https-container.sh' && warn "the backup's default.conf is itself a managed one (rerun backup) — prefer the oldest backup"
  local f live
  for f in default.conf env docker-compose.yml docker-compose.override.yml; do
    case $f in default.conf) live=$CONF;; env) live=.env;; *) live=$f;; esac
    if [ -f "$BK/$f" ]; then cmp -s "$BK/$f" "$live" && say "       $f: unchanged" || say "       $f: will be restored"; fi
  done
  OVL_ACTION=keep
  if [ "$(sget OVERLAY_EXISTED)" = 1 ] && [ -f "$BK/$OVERLAY" ]; then OVL_ACTION=restore; elif [ -f "$OVERLAY" ]; then OVL_ACTION=remove; fi
  say "       overlay $OVERLAY: $OVL_ACTION"
  # HSTS currently served
  HSTS=$(sed -n 's/.*Strict-Transport-Security "max-age=\([0-9]*\)".*/\1/p' "$CONF" | sort -n | tail -1)
  HSTS=${HSTS:-0}
  say "       current HSTS max-age in default.conf: $HSTS"
  if [ "$HSTS" -gt 86400 ] && [ "$FORCE" != 1 ]; then
    die "HSTS max-age=$HSTS is live: browsers that saw it refuse plain HTTP for that long. Lower it first (rerun the apply script with HSTS_MAX_AGE=0, wait the old max-age) or pass FORCE=1"
  fi
  # web image plan
  IMG_REF=$(sget WEB_IMAGE_REF); IMG_TAG=$(sget WEB_IMAGE_TAG); IMG_PRE=$(sget WEB_IMAGE_PRE)
  local cid cur posts
  cid=$(dc ps -q web 2>/dev/null | head -1 || true); cur=""; [ -z "$cid" ] || cur=$(docker inspect -f '{{.Image}}' "$cid" 2>/dev/null || true)
  posts=$(cat "$ROOT"/backups/https-2*/STATE 2>/dev/null | sed -n 's/^WEB_IMAGE_POST=//p' | sort -u || true)
  WEB_PLAN=none
  if [ -n "$IMG_PRE" ] && [ "$cur" = "$IMG_PRE" ]; then ok "web already runs the pre-HTTPS image"
  elif [ -n "$IMG_TAG" ] && docker image inspect "$IMG_TAG" >/dev/null 2>&1; then
    if [ -n "$cur" ] && grep -qxF "$cur" <<<"$posts"; then WEB_PLAN=retag; ok "web: $IMG_REF ← $IMG_TAG (no rebuild)"
    else WEB_PLAN=rebuild; warn "running web image was not built by the HTTPS script (a release since?) — web will be REBUILT with the restored settings instead of downgrading to $IMG_TAG"; fi
  else WEB_PLAN=rebuild; warn "previous web image ${IMG_TAG:-<not recorded>} not available — web will be rebuilt"; fi
  APP_SERVICES=""
  for d in web api worker; do dc config --services 2>/dev/null | grep -qx "$d" && APP_SERVICES="$APP_SERVICES $d"; done
  APP_SERVICES=${APP_SERVICES# }
  crontab -l 2>/dev/null | grep -qF "$CRON_MARK" && say "       renewal cron line will be removed" || true
}

apply() {
  RB="$ROOT/backups/https-rollback-$TS"; mkdir -p "$RB"; chmod 700 "$RB"
  cp -p "$CONF" "$RB/default.conf"; cp -p .env "$RB/env"
  local f; for f in docker-compose.yml docker-compose.override.yml "$OVERLAY"; do [ ! -f "$f" ] || cp -p "$f" "$RB/$f"; done
  say "== 1 nginx (pre-rollback copy: $RB)"
  docker run --rm --network "$(docker inspect -f '{{range $k, $v := .NetworkSettings.Networks}}{{println $k}}{{end}}' "$(dc ps -q nginx | head -1)" | awk 'NF' | head -1)" \
    -v "$BK/default.conf:/etc/nginx/conf.d/default.conf:ro" -v "$ROOT/certs:/etc/nginx/certs:ro" --entrypoint nginx \
    "$(docker inspect -f '{{.Image}}' "$(dc ps -q nginx | head -1)")" -t >"$WORK/vt" 2>&1 || { cat "$WORK/vt"; die "backup default.conf fails nginx -t — nothing changed"; }
  local ino; ino=$(stat -c %i "$CONF")
  restore_file "$BK/default.conf" "$CONF"
  [ "$(stat -c %i "$CONF")" = "$ino" ] || die "default.conf inode changed"
  if ! dc exec -T nginx nginx -t >"$WORK/nt" 2>&1; then cat "$RB/default.conf" >"$CONF"; cat "$WORK/nt"; die "nginx -t failed in the container — previous config put back"; fi
  dc exec -T nginx nginx -s reload >/dev/null; ok "default.conf restored in place, reloaded"
  say "== 2 .env / compose files"
  restore_file "$BK/env" .env
  for f in docker-compose.yml docker-compose.override.yml; do restore_file "$BK/$f" "$f"; done
  [ ! -f "$ROOT/nginx/default.conf.pre-https" ] || mv "$ROOT/nginx/default.conf.pre-https" "$RB/default.conf.pre-https"
  case "$OVL_ACTION" in restore) restore_file "$BK/$OVERLAY" "$OVERLAY";; remove) mv "$OVERLAY" "$RB/$OVERLAY.removed";; esac
  dc config -q || die "docker compose config fails after restore (copies in $RB)"
  ok ".env and compose files restored"
  say "== 3 web image ($WEB_PLAN) + restart $APP_SERVICES"
  case "$WEB_PLAN" in
    retag) docker tag "$IMG_TAG" "$IMG_REF"; ok "$IMG_REF ← $IMG_TAG";;
    rebuild) dc build web >/tmp/karenseir-https-rollback-build.log 2>&1 || { tail -30 /tmp/karenseir-https-rollback-build.log; die "web build failed"; };;
  esac
  # shellcheck disable=SC2086
  dc up -d --no-build --no-deps $APP_SERVICES >/dev/null
  if crontab -l 2>/dev/null | grep -qF "$CRON_MARK"; then
    { crontab -l 2>/dev/null | grep -vF "$CRON_MARK" || true; } | crontab -; ok "renewal cron line removed"
  fi
}

verify() {
  say "== 4 verify"
  local c h
  for _ in $(seq 1 36); do c=$(http_code "http://$DOMAIN/"); h=$(http_code "http://$DOMAIN/api/health"); [ "$c$h" = 200200 ] && break; sleep "$KT_SLEEP"; done
  say "       http://$DOMAIN/ → $c ; /api/health → $h"
  [ "$c$h" = 200200 ] || die "site not healthy after rollback (pre-rollback copies in $RB)"
  [ "$HSTS" = 0 ] || say "NOTE: browsers that already got HSTS force https for up to ${HSTS}s; the restored config has no 443 server, so those visitors see a connection error until then (wait ${HSTS}s / clear HSTS for the site)."
  say "ROLLBACK-OK restored $(basename "$BK") $(date -u +%FT%TZ)  (certificates kept in $ROOT/certs; reapply with karenseir-https-container.sh)"
}

main() {
  config "$@"
  trap 'on_err $? $LINENO' ERR
  trap on_exit EXIT
  exec </dev/null
  WORK=$(mktemp -d)
  lock_acquire
  plan
  [ "$CHECK_ONLY" = 0 ] || { say "ROLLBACK-CHECK-OK (nothing changed)"; exit 0; }
  apply
  verify
}

[ "${KARENSEIR_HTTPS_LIB:-0}" = 1 ] || main "$@" </dev/null
