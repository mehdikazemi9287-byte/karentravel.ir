#!/usr/bin/env bash
# KarenSeir — deploy of the Nov 2026 redesign (ADR-022) to /opt/karenseir
# Brings: (1) inner-pages redesign code patch, (2) the full Stitch design gallery
# (desktop/mobile/app/tablet + assets + docs) served at /design-2026-11/index.html
# Frontend-only: no API, DB or migration change. Idempotent; safe to re-run.
# Rollback: bash deploy/redesign-2026-11-rollback.sh   (or see REDESIGN_2026-11_DEPLOY.md)
set -euo pipefail

ROOT=/opt/karenseir
APP=$ROOT/app
BR=design/stitch-redesign-2026-11
RAW="https://raw.githubusercontent.com/mehdikazemi9287-byte/karentravel.ir/$BR"
TGZ="https://codeload.github.com/mehdikazemi9287-byte/karentravel.ir/tar.gz/refs/heads/$BR"
PATCH=0001-feat-ui-inner-pages-redesign-Plum-Coral-Cream-Shell-.patch
TS=$(date +%Y%m%d-%H%M%S)
LOG=$ROOT/deploy-redesign-2026-11-$TS.log
exec > >(tee -a "$LOG") 2>&1
step(){ echo; echo "=== $* ==="; }

step "0) preflight"
cd "$APP"
git config --global --get-all safe.directory | grep -qx "$APP" || git config --global --add safe.directory "$APP"
ST=$(git status --porcelain --untracked-files=no)
if [ -n "$ST" ]; then
  # These edits are already inside the running image (COPY . .), so keep them: snapshot as a commit, never discard.
  echo "uncommitted live edits found — snapshotting (nothing discarded):"; git status --short --untracked-files=no
  git -c user.name="KarenSeir Deploy" -c user.email="deploy@karentravel.ir" commit -qam "server: snapshot of uncommitted live edits before redesign-2026-11 deploy"
fi
SVC=""
for s in web frontend; do
  if (cd "$ROOT" && docker compose config --services 2>/dev/null | grep -qx "$s"); then SVC=$s; break; fi
done
[ -n "$SVC" ] || { echo "BLOCKED: no web/frontend service in $ROOT compose"; (cd "$ROOT" && docker compose config --services); exit 2; }
echo "frontend service: $SVC"

step "1) backup current state"
if [ ! -s "$ROOT/pre-redesign-HEAD.txt" ]; then H=$(git rev-parse HEAD); echo "$H" > "$ROOT/pre-redesign-HEAD.txt"; fi
echo "pre-redesign HEAD: $(cat "$ROOT/pre-redesign-HEAD.txt")   current HEAD: $(git rev-parse HEAD)"
docker ps --format '{{.Names}} {{.Image}}' > "$ROOT/pre-redesign-images-$TS.txt"
IMG=$(docker compose -f "$ROOT/docker-compose.yml" images -q "$SVC" 2>/dev/null | head -1 || true)
if [ -n "$IMG" ]; then docker tag "$IMG" "karenseir-web:pre-redesign-$TS" && echo "image backup: karenseir-web:pre-redesign-$TS"; fi

step "2) fetch from GitHub ($BR)"
TMP=$(mktemp -d)
curl -fsSL --retry 3 -m 120 -o "$TMP/$PATCH" "$RAW/deploy/patches/$PATCH"
curl -fSL --retry 3 --connect-timeout 20 -m 900 -o "$TMP/src.tgz" "$RAW/deploy/bundles/redesign-2026-11.tar.gz"
mkdir -p "$TMP/src" && tar -xzf "$TMP/src.tgz" -C "$TMP/src"
SRC="$TMP/src"
[ -d "$SRC/docs/design/stitch-redesign-2026-11" ] || { echo "BLOCKED: gallery not in tarball"; exit 3; }

step "3) code: inner-pages redesign patch (ADR-022)"
if grep -q 'redesign-2026-11.css' app/layout.tsx 2>/dev/null; then
  echo "already applied — skip"
else
  git apply --check "$TMP/$PATCH"
  git -c user.name="KarenSeir Deploy" -c user.email="deploy@karentravel.ir" am "$TMP/$PATCH"
fi

step "4) design gallery + docs (everything from Stitch/Figma round 1–4)"
rm -rf public/design-2026-11
cp -r "$SRC/docs/design/stitch-redesign-2026-11" public/design-2026-11
mkdir -p docs/design docs/adr deploy tools/design
rm -rf docs/design/stitch-redesign-2026-11
cp -r "$SRC/docs/design/stitch-redesign-2026-11" docs/design/
cp "$SRC"/docs/adr/ADR-022-*.md docs/adr/ 2>/dev/null || true
cp "$SRC"/deploy/REDESIGN_2026-11_DEPLOY.md "$SRC"/deploy/redesign-2026-11-rollback.sh deploy/; cp /root/rd.sh deploy/redesign-2026-11-deploy.sh 2>/dev/null || true
cp "$SRC"/tools/design/*.py tools/design/ 2>/dev/null || true
git add public/design-2026-11 docs/design/stitch-redesign-2026-11 docs/adr deploy tools/design
git -c user.name="KarenSeir Deploy" -c user.email="deploy@karentravel.ir" commit -qm "design: Stitch redesign 2026-11 gallery + docs (rounds 1-4)" || echo "nothing new to commit"
echo "gallery files: $(find public/design-2026-11 -type f | wc -l)"

step "5) build + restart frontend only ($SVC)"
cd "$ROOT"
export GIT_COMMIT=$(git -C "$APP" rev-parse --short HEAD) BUILD_TIMESTAMP=$(date -u +%FT%TZ)
docker compose build "$SVC"
docker compose up -d --no-deps "$SVC"
sleep 20

step "6) verify"
ok=1
chk(){ local u=$1 want=$2; local c; c=$(curl -s -o /dev/null -w '%{http_code}' "$u" || echo 000); echo "$c  $u"; [ "$c" = "$want" ] || ok=0; }
chk https://karentravel.ir/ 200
chk https://karentravel.ir/hotels 200
chk https://karentravel.ir/design-2026-11/index.html 200
chk https://karentravel.ir/design-2026-11/tablet/04-credit-finance.html 200
n=$(curl -s https://karentravel.ir/hotels | grep -c 'ks-inner' || true); echo "ks-inner on /hotels: $n (want ≥1)"; [ "$n" -ge 1 ] || ok=0
docker compose ps "$SVC"
echo; echo "HEAD now: $(git -C "$APP" rev-parse --short HEAD)   log: $LOG"
if [ $ok = 1 ]; then echo "RESULT: DEPLOY OK"; else echo "RESULT: CHECK FAILED — review above; rollback: bash $APP/deploy/redesign-2026-11-rollback.sh"; fi
rm -rf "$TMP"
