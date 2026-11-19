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
RAW="https://raw.githubusercontent.com/mehdikazemi9287-byte/karentravel.ir/${REF:-$BR}"
TGZ="https://codeload.github.com/mehdikazemi9287-byte/karentravel.ir/tar.gz/refs/heads/$BR"
PATCH=0002-ADR-023-inner-pages-refinement-on-production.patch
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
SERVICES=$(cd "$ROOT" && docker compose config --services 2>/dev/null || true)
for s in web frontend; do
  if printf '%s\n' "$SERVICES" | grep -qx "$s"; then SVC=$s; break; fi
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

step "3) code: inner-pages refinement on production base (ADR-023)"
CODE=0
if grep -q 'approved-inner-2026-11.css' components/marketplace/ApprovedFigmaHome.tsx 2>/dev/null; then
  echo "already applied — skip"
else
  git apply --check "$TMP/$PATCH"
  git -c user.name="KarenSeir Deploy" -c user.email="deploy@karentravel.ir" am "$TMP/$PATCH"
  CODE=1
fi
P3=0003-ADR-023-journey-pages-consistency.patch
if grep -q 'JourneyShell pages (47 routes)' components/marketplace/approved-inner-2026-11.css 2>/dev/null; then
  echo "0003 already applied — skip"
else
  curl -fsSL --retry 3 -m 120 -o "$TMP/$P3" "$RAW/deploy/patches/$P3"
  git apply --check "$TMP/$P3"
  git -c user.name="KarenSeir Deploy" -c user.email="deploy@karentravel.ir" am "$TMP/$P3"
  CODE=1
fi

P4=0004-stitch-search-results.patch
if grep -q "search-results-2026-11.css" components/operational/UnifiedSearchView.tsx 2>/dev/null; then
  echo "0004 already applied — skip"
else
  curl -fsSL --retry 3 -m 120 -o "$TMP/$P4" "$RAW/deploy/patches/$P4"
  git apply --check "$TMP/$P4"
  git -c user.name="KarenSeir Deploy" -c user.email="deploy@karentravel.ir" am "$TMP/$P4"
  CODE=1
fi

P5=0005-stitch-catalog-detail-checkout-dashboard.patch
if grep -q "stitch-pages-2026-11.css" components/catalog/CatalogViews.tsx 2>/dev/null; then
  echo "0005 already applied — skip"
else
  curl -fsSL --retry 3 -m 120 -o "$TMP/$P5" "$RAW/deploy/patches/$P5"
  git apply --check "$TMP/$P5"
  git -c user.name="KarenSeir Deploy" -c user.email="deploy@karentravel.ir" am "$TMP/$P5"
  CODE=1
fi

P6=0006-stitch-login-manage-confirmation.patch
if grep -q "Login / OTP (Stitch" components/marketplace/stitch-pages-2026-11.css 2>/dev/null; then
  echo "0006 already applied — skip"
else
  curl -fsSL --retry 3 -m 120 -o "$TMP/$P6" "$RAW/deploy/patches/$P6"
  git apply --check "$TMP/$P6"
  git -c user.name="KarenSeir Deploy" -c user.email="deploy@karentravel.ir" am "$TMP/$P6"
  CODE=1
fi

P7=0007-stitch-hotel-results-layout.patch
if grep -q "Hotel results layout = Stitch Desktop/05" components/marketplace/stitch-pages-2026-11.css 2>/dev/null; then
  echo "0007 already applied — skip"
else
  curl -fsSL --retry 3 -m 120 -o "$TMP/$P7" "$RAW/deploy/patches/$P7"
  git apply --check "$TMP/$P7"
  git -c user.name="KarenSeir Deploy" -c user.email="deploy@karentravel.ir" am "$TMP/$P7"
  CODE=1
fi

P8=0008-fix-hotel-fallback-width.patch
if grep -q "results-content>:has(form)" components/operational/search-results-2026-11.css 2>/dev/null; then
  echo "0008 already applied — skip"
else
  curl -fsSL --retry 3 -m 120 -o "$TMP/$P8" "$RAW/deploy/patches/$P8"
  git apply --check "$TMP/$P8"
  git -c user.name="KarenSeir Deploy" -c user.email="deploy@karentravel.ir" am "$TMP/$P8"
  CODE=1
fi

P9=0009-audit-fixes-jalali-header-relevance.patch
if [ -f components/forms/JalaliDateInput.tsx ]; then
  echo "0009 already applied — skip"
else
  curl -fsSL --retry 3 -m 120 -o "$TMP/$P9" "$RAW/deploy/patches/$P9"
  git apply --check "$TMP/$P9"
  git -c user.name="KarenSeir Deploy" -c user.email="deploy@karentravel.ir" am "$TMP/$P9"
  CODE=1
fi

P10=0010-flight-results-stitch-card.patch
if grep -q "fr-row" components/operational/search-results-2026-11.css 2>/dev/null; then
  echo "0010 already applied — skip"
else
  curl -fsSL --retry 3 -m 120 -o "$TMP/$P10" "$RAW/deploy/patches/$P10"
  git apply --check "$TMP/$P10"
  git -c user.name="KarenSeir Deploy" -c user.email="deploy@karentravel.ir" am "$TMP/$P10"
  CODE=1
fi

BACKEND=0
P11=0011-vandapay-payment-gateway.patch
if grep -q "class VandaPayAdapter" backend/app/providers.py 2>/dev/null; then echo "0011 already applied — skip"; else
  curl -fsSL --retry 3 -m 120 -o "$TMP/$P11" "$RAW/deploy/patches/$P11"; git apply --check "$TMP/$P11"
  git -c user.name="KarenSeir Deploy" -c user.email="deploy@karentravel.ir" am "$TMP/$P11"; CODE=1; BACKEND=1; fi
P12=0012-stitch-round6-tours-experiences.patch
if grep -q "supplier/experience-portal" backend/app/main.py 2>/dev/null; then echo "0012 already applied — skip"; else
  curl -fsSL --retry 3 -m 120 -o "$TMP/$P12" "$RAW/deploy/patches/$P12"
  git -c user.name="KarenSeir Deploy" -c user.email="deploy@karentravel.ir" am "$TMP/$P12"; CODE=1; BACKEND=1; fi

step "4) design gallery + docs (everything from Stitch/Figma round 1–4)"
# Not served from Next public/: production CSP (script-src 'self', X-Frame-Options DENY) blocks the
# Tailwind CDN and the gallery iframes. Public preview stays on GitHub Pages; the server keeps the full set in docs/.
mkdir -p docs/design docs/adr deploy tools/design
rm -rf docs/design/stitch-redesign-2026-11
cp -r "$SRC/docs/design/stitch-redesign-2026-11" docs/design/
cp "$SRC"/docs/adr/ADR-02[23]-*.md docs/adr/ 2>/dev/null || true
cp "$SRC"/deploy/REDESIGN_2026-11_DEPLOY.md "$SRC"/deploy/redesign-2026-11-rollback.sh deploy/; cp /root/rd.sh deploy/redesign-2026-11-deploy.sh 2>/dev/null || true
cp "$SRC"/tools/design/*.py tools/design/ 2>/dev/null || true
git add docs/design/stitch-redesign-2026-11 docs/adr deploy tools/design
git -c user.name="KarenSeir Deploy" -c user.email="deploy@karentravel.ir" commit -qm "design: Stitch redesign 2026-11 gallery + docs (rounds 1-4)" || echo "nothing new to commit"
echo "design files on server: $(find docs/design/stitch-redesign-2026-11 -type f | wc -l)"

if [ "$CODE" = 0 ]; then echo; echo "No runtime code changed — no rebuild/restart (production untouched). HEAD: $(git rev-parse --short HEAD)  log: $LOG"; echo "RESULT: DOCS DEPLOYED, CODE SKIPPED"; rm -rf "$TMP"; exit 0; fi
step "5) build + restart frontend only ($SVC)"
cd "$ROOT"
export GIT_COMMIT=$(git -C "$APP" rev-parse --short HEAD) BUILD_TIMESTAMP=$(date -u +%FT%TZ)
docker compose build "$SVC"
docker compose up -d --no-deps "$SVC"
sleep 20

if [ "${BACKEND:-0}" = 1 ] || [ "${FORCE_BACKEND:-0}" = 1 ]; then
  step "5b) build + restart backend (api, worker) — no DB migration in 0011/0012"
  TS=$(date +%Y%m%d-%H%M%S)
  for s in api worker; do IMG=$(docker compose images -q "$s" 2>/dev/null | head -1); [ -n "$IMG" ] && docker tag "$IMG" "karenseir-$s:pre-$TS" && echo "backup image karenseir-$s:pre-$TS"; done
  docker compose build api
  docker compose up -d --no-deps api worker
  for i in $(seq 1 30); do st=$(docker compose ps api --format '{{.Status}}'); case "$st" in *healthy*) [ "${st#*unhealthy}" = "$st" ] && break;; esac; sleep 3; done
  echo "api: $(docker compose ps api --format '{{.Status}}')  worker: $(docker compose ps worker --format '{{.Status}}')"
  echo "backend rollback: docker tag karenseir-api:pre-$TS <api image> && docker compose up -d --no-deps api worker"
fi

step "6) verify"
ok=1
chk(){ local u=$1 want=$2; local c; c=$(curl -s -o /dev/null -w '%{http_code}' "$u" || echo 000); echo "$c  $u"; [ "$c" = "$want" ] || ok=0; }
chk https://karentravel.ir/ 200
chk https://karentravel.ir/hotels 200
chk https://karentravel.ir/services 200
chk https://karentravel.ir/api/health 200
n=$(curl -s https://karentravel.ir/services | grep -c 'ks-inner' || true); echo "ks-inner on /services: $n (want ≥1)"; [ "$n" -ge 1 ] || ok=0
h=$(curl -s https://karentravel.ir/ | grep -c 'ks-inner' || true); echo "ks-inner on / (homepage): $h (want 0)"; [ "$h" = 0 ] || ok=0
docker compose ps "$SVC"
echo; echo "HEAD now: $(git -C "$APP" rev-parse --short HEAD)   log: $LOG"
if [ $ok = 1 ]; then echo "RESULT: DEPLOY OK"; else echo "RESULT: CHECK FAILED — review above; rollback: bash $APP/deploy/redesign-2026-11-rollback.sh"; fi
rm -rf "$TMP"
