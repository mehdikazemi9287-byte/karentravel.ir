#!/bin/sh
# One-shot production release of origin/production (run ON the server, from the repo checkout).
# Safe order: refuse a dirty worktree -> DB backup -> build -> alembic upgrade (in a one-off container) -> up -> health.
# Usage:  APP_DIR=/path/to/karentravel.ir sh deploy/release-production.sh
# Optional: COMPOSE="docker compose -f docker-compose.yml -f docker-compose.production-secrets.yml" (default: docker compose --env-file .env)
set -eu
APP_DIR="${APP_DIR:-$(pwd)}"
COMPOSE="${COMPOSE:-docker compose --env-file .env}"
cd "$APP_DIR"

if [ -n "$(git status --porcelain --untracked-files=no)" ]; then
  echo "ABORT: tracked files changed on the server; commit or stash them first:" >&2
  git status --short --untracked-files=no >&2
  exit 1
fi
PREV="$(git rev-parse HEAD)"
git fetch --quiet origin production
git checkout --quiet production
git merge --ff-only --quiet origin/production
NEW="$(git rev-parse HEAD)"
echo "release: $PREV -> $NEW"

mkdir -p backups
DUMP="backups/karenseir-before-$(date +%Y%m%d-%H%M%S)-${NEW%"${NEW#???????}"}.dump"
$COMPOSE exec -T db pg_dump -U karenseir -Fc karenseir > "$DUMP"
test -s "$DUMP" || { echo "ABORT: empty database backup" >&2; exit 1; }
echo "backup: $DUMP"

$COMPOSE build api worker web
$COMPOSE run --rm api alembic upgrade head
$COMPOSE up -d
$COMPOSE ps

i=0
until curl -fsS -m 5 http://127.0.0.1:8000/health >/dev/null && curl -fsS -m 5 -o /dev/null http://127.0.0.1:3000/; do
  i=$((i+1)); [ "$i" -ge 30 ] && { echo "HEALTH FAILED. Rollback: git checkout $PREV && $COMPOSE up -d --build ; restore DB: $COMPOSE exec -T db pg_restore --clean --if-exists -U karenseir -d karenseir < $DUMP" >&2; exit 1; }
  sleep 5
done
$COMPOSE run --rm api alembic current
echo "OK: production is at $NEW (previous $PREV, backup $DUMP)"
