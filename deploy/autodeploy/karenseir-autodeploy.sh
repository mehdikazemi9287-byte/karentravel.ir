#!/usr/bin/env bash
# KarenSeir auto-deploy poller — merge to main on GitHub => deploy to production (owner decision 1405-09-07).
# Runs every 10 minutes from karenseir-autodeploy.timer. One-way only: GitHub main -> server. It is NOT a command
# channel and runs nothing except the already-verified /root/deploy.sh.
# Never deletes anything. A failed commit is recorded and never retried. Stops if disk is low or history diverged.
set -u
ROOT=/opt/karenseir
APP=$ROOT/app
STATE=$ROOT/autodeploy
mkdir -p "$STATE"
LOG="$STATE/status.log"
say() { echo "$(date -u +%FT%TZ) $*" | tee -a "$LOG"; }
exec 9>"$STATE/lock"; flock -n 9 || exit 0
[ -e "$ROOT/monitor/deploying" ] && { say "skip: a deploy is already running"; exit 0; }
[ -e "$STATE/PAUSE" ] && { say "skip: paused (remove nothing; rename $STATE/PAUSE to resume)"; exit 0; }

git -C "$APP" fetch -q origin main || { say "skip: git fetch failed"; exit 0; }
NEW=$(git -C "$APP" rev-parse origin/main)
CUR=$(awk '{print $1}' "$ROOT/DEPLOYED" 2>/dev/null)
[ -z "$CUR" ] && { say "stop: $ROOT/DEPLOYED missing"; exit 0; }
case "$NEW" in "$CUR"*) exit 0;; esac
SHORT=${NEW:0:7}
grep -q "^$NEW " "$STATE/failed" 2>/dev/null && exit 0
if ! git -C "$APP" merge-base --is-ancestor "$CUR" "$NEW" 2>/dev/null; then
  say "stop: deployed $CUR is not an ancestor of main $SHORT — needs a person"; echo "$NEW diverged" >> "$STATE/failed"; exit 0
fi
FREE_GB=$(df -BG --output=avail / | tail -1 | tr -dc 0-9)
if [ "${FREE_GB:-0}" -lt 8 ]; then say "stop: only ${FREE_GB}G free on / — not deploying $SHORT"; exit 0; fi

say "deploy start: $CUR -> $SHORT"
if bash /root/deploy.sh --check >>"$LOG" 2>&1 && bash /root/deploy.sh >>"$LOG" 2>&1; then
  say "deploy ok: $SHORT"
else
  echo "$NEW failed $(date -u +%FT%TZ)" >> "$STATE/failed"
  say "deploy FAILED: $SHORT (recorded; will not retry this commit — the deploy script rolls back on failure)"
fi
