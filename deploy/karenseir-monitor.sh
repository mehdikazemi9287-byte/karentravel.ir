#!/usr/bin/env bash
# KarenSeir / Karen Travel — minute-by-minute production watch (installed by karenseir-deploy-server.sh
# as /etc/cron.d/karenseir-monitor). Read-only except one safe self-heal: nginx reload when the site
# fails through nginx but the containers answer directly (stale upstream IPs after a container recreate).
#
# Checks: public pages through nginx (HTTP + HTTPS/SNI), API health, container health, alembic head
# unchanged between deploys, and core table row counts never DROP between two runs (data moved/deleted).
# Output: /opt/karenseir/monitor/status.json (latest), monitor.log (history, trimmed), alerts.log (problems only).
set -uo pipefail
ROOT=/opt/karenseir; OUT=$ROOT/monitor; mkdir -p "$OUT"
LOG=$OUT/monitor.log; ALERTS=$OUT/alerts.log; STATE=$OUT/counts.prev
NOW=$(date -u +%FT%TZ); PROBLEMS=()
[ -f "$OUT/deploying" ] && [ $(( $(date +%s) - $(stat -c %Y "$OUT/deploying") )) -lt 1800 ] && { echo "$NOW skip (deploy running)" >> "$LOG"; exit 0; }
alert(){ PROBLEMS+=("$1"); echo "$NOW ALERT $1" >> "$ALERTS"; }

code(){ curl -s -o /dev/null -m 15 -w '%{http_code}' "$@" 2>/dev/null || echo 000; }
for p in / /flights /hotels /trains /tours /login /blog; do
  c=$(code -H 'Host: karentravel.ir' "http://127.0.0.1$p"); [ "$c" = 200 ] || [ "$c" = 301 ] || [ "$c" = 308 ] || alert "http $p -> $c"
done
c=$(code -k --resolve karentravel.ir:443:127.0.0.1 https://karentravel.ir/); [ "$c" = 200 ] || alert "https / -> $c"
c=$(code -H 'Host: karentravel.ir' http://127.0.0.1/api/health); [ "$c" = 200 ] || alert "api health -> $c"
HOME_HTML=$(curl -s -m 15 -H 'Host: karentravel.ir' http://127.0.0.1/ 2>/dev/null); case "$HOME_HTML" in *'کارن تراول'*) ;; *) alert "brand text missing on homepage";; esac

# containers
for n in karenseir-web-1 karenseir-api-1 karenseir-worker-1 karenseir-db-1 karenseir-redis-1 karenseir-nginx-1; do
  s=$(docker inspect -f '{{.State.Status}}/{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}' "$n" 2>/dev/null || echo missing)
  case "$s" in running/healthy|running/none) ;; *) alert "container $n $s";; esac
done

# self-heal: site fails via nginx but web answers directly -> nginx has stale upstreams
if printf '%s\n' "${PROBLEMS[@]:-}" | grep -q '^http / \|^https /'; then
  WEBIP=$(docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' karenseir-web-1 2>/dev/null | head -c 40)
  if [ -n "$WEBIP" ] && [ "$(code "http://$WEBIP:3000/")" = 200 ]; then
    docker exec karenseir-nginx-1 nginx -s reload >/dev/null 2>&1 && echo "$NOW HEAL nginx reloaded (web direct OK at $WEBIP)" >> "$ALERTS"
  fi
fi

# data integrity: migration head and core row counts (counts may grow; a drop is an alert)
U=$(docker exec karenseir-db-1 printenv POSTGRES_USER 2>/dev/null); D=$(docker exec karenseir-db-1 printenv POSTGRES_DB 2>/dev/null)
q(){ docker exec karenseir-db-1 psql -U "$U" -d "$D" -tAc "$1" 2>/dev/null | tr -d '[:space:]'; }
HEAD=$(q "select version_num from alembic_version")
COUNTS=""
for t in users tenants reservations payment_intents bookings support_cases catalog_hotels; do
  ex=$(q "select to_regclass('public.$t') is not null")
  [ "$ex" = t ] && COUNTS="$COUNTS $t=$(q "select count(*) from $t")"
done
if [ -s "$STATE" ]; then
  read -r PHEAD PCOUNTS < "$STATE"
  [ -n "$HEAD" ] && [ "$HEAD" != "$PHEAD" ] && [ ! -f "$OUT/deploying" ] && echo "$NOW INFO migration head $PHEAD -> $HEAD" >> "$ALERTS"
  for kv in $PCOUNTS; do k=${kv%%=*}; pv=${kv#*=}; nv=$(printf '%s\n' $COUNTS | sed -n "s/^$k=//p"); [ -n "$nv" ] && [ "$nv" -lt "$pv" ] 2>/dev/null && alert "rows dropped in $k: $pv -> $nv"; done
fi
[ -n "$HEAD" ] && echo "$HEAD$COUNTS" > "$STATE"

STATUS=ok; [ ${#PROBLEMS[@]} -gt 0 ] && STATUS=problem
printf '{"time":"%s","status":"%s","migration_head":"%s","counts":"%s","problems":%s}\n' "$NOW" "$STATUS" "$HEAD" "${COUNTS# }" \
  "$( [ ${#PROBLEMS[@]} -gt 0 ] && printf '"%s",' "${PROBLEMS[@]}" | sed 's/,$//;s/^/[/;s/$/]/' || echo '[]')" > "$OUT/status.json"
echo "$NOW $STATUS ${PROBLEMS[*]:-}" >> "$LOG"
tail -n 20000 "$LOG" > "$LOG.tmp" && mv "$LOG.tmp" "$LOG"
