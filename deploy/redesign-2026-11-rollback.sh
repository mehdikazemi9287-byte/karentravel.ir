#!/usr/bin/env bash
# Rollback of the Nov 2026 redesign deploy: restores pre-redesign code HEAD and rebuilds the frontend.
set -euo pipefail
ROOT=/opt/karenseir; APP=$ROOT/app
git config --global --add safe.directory "$APP" 2>/dev/null || true
PRE=$(cat "$ROOT/pre-redesign-HEAD.txt"); [ -n "$PRE" ] || { echo "no pre-redesign HEAD recorded"; exit 2; }
SVC=web; (cd "$ROOT" && docker compose config --services | grep -qx web) || SVC=frontend
echo "rolling back $APP to $PRE (service $SVC)"
git -C "$APP" reset --hard "$PRE"
cd "$ROOT" && docker compose build "$SVC" && docker compose up -d --no-deps "$SVC"
sleep 15; curl -s -o /dev/null -w '%{http_code} https://karentravel.ir/\n' https://karentravel.ir/
echo "Faster alternative: retag the backup image listed by: docker images | grep pre-redesign"
