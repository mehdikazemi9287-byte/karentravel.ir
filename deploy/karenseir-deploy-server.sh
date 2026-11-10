#!/usr/bin/env bash
# KarenSeir — release origin/production (GitHub) to 188.121.123.218, server layout:
#   /opt/karenseir            compose project (server-owned docker-compose.yml + override, .env, backup.sh)
#   /opt/karenseir/app        git checkout (no remote; server-only commit 8ca27bd = pip mirror + catalog_data placeholder)
# Run from the Mac:   ssh karen@188.121.123.218 'bash -s' < ~/Downloads/karenseir-deploy.sh
# Check only:         ssh karen@188.121.123.218 'bash -s -- --check' < ~/Downloads/karenseir-deploy.sh
# Server-side edits:  add --discard-server-edits to save uncommitted edits in app/ to backups/*.patch and continue
# Builds web/api/worker; checks the API DB role (KT-05); runs alembic upgrade head via the one-off `migrate` service and aborts (rolling back code + images) if it fails.
# On a failed health check it rolls back by itself (previous branch + previous images; the DB is untouched by this release).
set -euo pipefail

ROOT=/opt/karenseir
APP=$ROOT/app
REPO=https://github.com/mehdikazemi9287-byte/karentravel.ir
SERVER_ONLY=8ca27bd
SERVICES="web api worker"
TS=$(date +%Y%m%d-%H%M%S)

say() { printf '%s\n' "$*"; }
die() { say "ABORT: $*"; exit 1; }

health() {
  local i=0
  until curl -fsS -m 5 -o /dev/null -H 'Host: karentravel.ir' http://127.0.0.1/ \
     && curl -fsS -m 5 -H 'Host: karentravel.ir' http://127.0.0.1/api/health >/dev/null; do
    i=$((i+1)); [ "$i" -ge 36 ] && return 1
    sleep 5
  done
}

rollback() {
  say "== ROLLBACK: back to $PREV_BRANCH ($PREV) and previous images"
  cd "$APP" && git checkout --quiet "$PREV_BRANCH"
  for s in $SERVICES; do docker tag "karenseir-$s:pre-$TS" "karenseir-$s:latest"; done
  cd "$ROOT" && docker compose up -d --no-build $SERVICES
  if health; then say "ROLLBACK-OK: site is back on $PREV"; else say "ROLLBACK-INCOMPLETE: check 'docker compose ps' and logs"; fi
}

main() {
  local check=0 discard=0
  for a in "$@"; do case "$a" in --check) check=1;; --discard-server-edits) discard=1;; esac; done

  say "== 1/6 preflight"
  cd "$APP"
  if [ -n "$(git status --porcelain --untracked-files=no)" ]; then
    git status --short --untracked-files=no
    if [ "$discard" = 1 ] && [ "$check" = 0 ]; then
      mkdir -p "$ROOT/backups"; PATCH="$ROOT/backups/server-edits-$TS.patch"
      git diff > "$PATCH" && test -s "$PATCH" || die "could not save the server edits"
      git checkout -- . && say "server edits saved to $PATCH and removed from the work tree"
    elif [ "$discard" = 1 ]; then
      say "check: these server edits would be saved to backups/server-edits-<time>.patch and removed"
    else
      die "tracked files changed in $APP (re-run with --discard-server-edits to save them to backups/ as a patch and continue)"
    fi
  fi
  PREV=$(git rev-parse --short HEAD); PREV_BRANCH=$(git rev-parse --abbrev-ref HEAD)
  git cat-file -e "$SERVER_ONLY^{commit}" || die "server-only commit $SERVER_ONLY not found"
  git fetch --quiet "$REPO" production:refs/remotes/github/production
  NEW=$(git rev-parse --short github/production)
  say "running: $PREV_BRANCH @ $PREV   ->   production @ $NEW (+ server-only $SERVER_ONLY)"
  for s in $SERVICES; do docker image inspect "karenseir-$s:latest" >/dev/null || die "image karenseir-$s:latest not found"; done
  [ "$(df -Pm "$ROOT" | awk 'NR==2{print $4}')" -ge 3000 ] || die "less than 3 GB free on $ROOT"
  curl -fsS -m 5 -o /dev/null -H 'Host: karentravel.ir' http://127.0.0.1/ || die "site is not healthy before the release"
  # KT-05: migrations need the one-off owner service `migrate`; the API itself must use the restricted role.
  (cd "$ROOT" && docker compose config --services | grep -qx migrate) || die "one-time step missing: add the 'migrate' service and point the api DATABASE_URL at karenseir_api (docs/audit/fix-2026-11-10.md, KT-05)"
  if [ "$check" = 1 ]; then say "DEPLOY-CHECK-OK (nothing changed)"; return 0; fi

  say "== 2/6 database backup"
  "$ROOT/backup.sh"

  say "== 3/6 keep current images for rollback (tag pre-$TS)"
  for s in $SERVICES; do docker tag "karenseir-$s:latest" "karenseir-$s:pre-$TS"; done

  say "== 4/6 new branch release-$TS = production + server-only commit"
  git checkout --quiet -b "release-$TS" github/production
  git cherry-pick "$SERVER_ONLY" >/dev/null || { git cherry-pick --abort; git checkout --quiet "$PREV_BRANCH"; git branch -D "release-$TS"; die "server-only commit does not apply on production (nothing deployed)"; }
  say "code: $(git log --oneline -1)"

  say "== 5/6 build and restart $SERVICES"
  cd "$ROOT"
  if ! docker compose build $SERVICES; then
    say "build failed — the running containers were not touched"
    cd "$APP" && git checkout --quiet "$PREV_BRANCH" && git branch -D "release-$TS" >/dev/null
    for s in $SERVICES; do docker tag "karenseir-$s:pre-$TS" "karenseir-$s:latest"; done
    die "build failed; code back on $PREV_BRANCH"
  fi
  if ! docker compose run --rm --no-deps -T api python -m app.db_role_guard; then
    say "API ROLE CHECK FAILED — the running containers were not touched"
    cd "$APP" && git checkout --quiet "$PREV_BRANCH" && git branch -D "release-$TS" >/dev/null
    for s in $SERVICES; do docker tag "karenseir-$s:pre-$TS" "karenseir-$s:latest"; done
    die "the api service still connects as a privileged/owner role; finish the KT-05 one-time step first"
  fi
  PREV_HEAD=$(docker compose run --rm -T migrate alembic current 2>/dev/null | awk 'NF{print $1}' | tail -1)
  say "migration head before: ${PREV_HEAD:-unknown}"
  if ! docker compose run --rm -T migrate alembic upgrade head; then
    say "MIGRATION FAILED — rolling back code and images (the database backup from step 2 is kept)"
    cd "$APP" && git checkout --quiet "$PREV_BRANCH" && git branch -D "release-$TS" >/dev/null
    for s in $SERVICES; do docker tag "karenseir-$s:pre-$TS" "karenseir-$s:latest"; done
    cd "$ROOT" && docker compose up -d --no-build $SERVICES
    die "alembic upgrade failed; previous release restored. If the DB was partly migrated, restore the latest dump in $ROOT/backups."
  fi
  say "migration head after: $(docker compose run --rm -T migrate alembic current 2>/dev/null | awk 'NF{print $1}' | tail -1)"
  docker compose up -d $SERVICES

  say "== 6/6 health"
  if ! health; then say "HEALTH FAILED"; rollback; exit 1; fi
  curl -fsS -m 5 -H 'Host: karentravel.ir' http://127.0.0.1/ | grep -q 'کارن تراول' && say "brand: کارن تراول OK" || say "WARN: new brand not found in the home page"
  docker compose ps --format '{{.Name}}\t{{.Status}}'
  say "DEPLOY-OK: production $NEW on branch release-$TS (previous $PREV_BRANCH @ $PREV, images tagged pre-$TS)"
  say "manual rollback: cd $APP && git checkout $PREV_BRANCH && for s in $SERVICES; do docker tag karenseir-\$s:pre-$TS karenseir-\$s:latest; done && cd $ROOT && docker compose up -d --no-build $SERVICES"
}

main "$@" </dev/null
