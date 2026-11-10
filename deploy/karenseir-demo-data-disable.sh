#!/usr/bin/env bash
# KarenSeir — switch OFF the demo seed data on production without deleting anything (security review M-7).
#   * users whose email ends in .test      -> users.disabled_at = <run time>
#   * demo tenants aftab-bank, faraz-industries -> tenants.disabled_at = <run time>
#     (a demo tenant that also holds a non-.test account is NOT disabled; it is listed for the owner instead)
#   * never touches the real tenants karenseir-public / karenseir-consumer, whatever their emails look like
# A disabled account cannot get an OTP, log in, refresh, or use a token it already has (needs migration 20261109_73).
# Reversible: every row gets the same timestamp, and the undo command printed at the end clears exactly those rows.
# Run from the Mac:
#   check only:  ssh karen@188.121.123.218 'bash -s -- --check' < ~/Downloads/karenseir-demo-data-disable.sh
#   apply:       ssh karen@188.121.123.218 'bash -s' < ~/Downloads/karenseir-demo-data-disable.sh
#   undo:        ssh karen@188.121.123.218 'bash -s -- --undo 2026-11-10T08:00:00+00:00' < ~/Downloads/karenseir-demo-data-disable.sh
main() {
set -euo pipefail
local check=0 undo=""
while [ $# -gt 0 ]; do
  case "$1" in
    --check) check=1;;
    --undo) shift; undo="${1:-}";;
    *) echo "ABORT: unknown option $1"; exit 1;;
  esac
  shift
done

ROOT=${KARENSEIR_ROOT:-/opt/karenseir}
TS=$(date -u +%Y%m%d-%H%M%S)
STAMP=$(date -u +%Y-%m-%dT%H:%M:%S+00:00)
DEMO_TENANTS="'aftab-bank','faraz-industries'"
REAL_TENANTS="'karenseir-public','karenseir-consumer'"
cd "$ROOT"
PSQL=(docker compose exec -T db psql -U karenseir -d karenseir -At -v ON_ERROR_STOP=1)
q() { "${PSQL[@]}" -c "$1"; }

echo "== 1/4 preflight"
for t in users tenants; do
  [ "$(q "select count(*) from information_schema.columns where table_name='$t' and column_name='disabled_at';")" = 1 ] \
    || { echo "ABORT: $t.disabled_at is missing — deploy the release with migration 20261109_73 first (nothing changed)"; exit 2; }
done

if [ -n "$undo" ]; then
  case "$undo" in [0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T[0-9][0-9]:[0-9][0-9]:[0-9][0-9]+00:00) ;; *) echo "ABORT: --undo needs the exact stamp printed by the apply run"; exit 1;; esac
  echo "rows with this stamp: users=$(q "select count(*) from users where disabled_at='$undo';") tenants=$(q "select count(*) from tenants where disabled_at='$undo';")"
  if [ "$check" = 1 ]; then echo "UNDO-CHECK-OK (nothing changed)"; return 0; fi
  q "begin; update users set disabled_at=null where disabled_at='$undo'; update tenants set disabled_at=null where disabled_at='$undo'; commit;" >/dev/null
  echo "UNDONE: accounts and tenants disabled at $undo are active again."
  return 0
fi

echo "== 2/4 what would change"
USERS_SQL="from users u join tenants t on t.id=u.tenant_id where u.email ilike '%.test' and t.slug not in ($REAL_TENANTS) and u.disabled_at is null"
# a demo tenant is only disabled when every account in it is a .test demo account
TENANTS_SQL="from tenants t where t.slug in ($DEMO_TENANTS) and t.disabled_at is null and not exists (select 1 from users u where u.tenant_id=t.id and u.email not ilike '%.test')"
echo "demo users (.test) to disable:            $(q "select count(*) $USERS_SQL;")"
q "select '  '||t.slug||': '||count(*) $USERS_SQL group by t.slug order by t.slug;"
echo "demo tenants to disable:                  $(q "select count(*) $TENANTS_SQL;") ($(q "select coalesce(string_agg(slug, ', '),'none') $TENANTS_SQL;"))"
kept=$(q "select coalesce(string_agg(t.slug||' ('||(select count(*) from users u where u.tenant_id=t.id and u.email not ilike '%.test')||' non-.test accounts)', ', '),'') from tenants t where t.slug in ($DEMO_TENANTS) and t.disabled_at is null and exists (select 1 from users u where u.tenant_id=t.id and u.email not ilike '%.test');")
if [ -n "$kept" ]; then echo "KEPT ACTIVE (has real-looking accounts, review by hand): $kept"; fi
echo "skipped .test emails in real tenants:     $(q "select count(*) from users u join tenants t on t.id=u.tenant_id where u.email ilike '%.test' and t.slug in ($REAL_TENANTS);") (never touched)"
echo "already disabled: users=$(q "select count(*) from users where disabled_at is not null;") tenants=$(q "select count(*) from tenants where disabled_at is not null;")"
if [ "$check" = 1 ]; then echo "DEMO-DISABLE-CHECK-OK (nothing changed)"; return 0; fi

echo "== 3/4 database backup + list of affected rows"
"$ROOT/backup.sh"
mkdir -p "$ROOT/backups"
LIST="$ROOT/backups/demo-disable-$TS.txt"
{ echo "# stamp $STAMP"; q "select 'user '||u.id||' '||t.slug||' '||u.email $USERS_SQL order by u.id;"; q "select 'tenant '||t.id||' '||t.slug $TENANTS_SQL order by t.id;"; } > "$LIST"

echo "== 4/4 disable (one transaction)"
q "begin; update users set disabled_at='$STAMP' where id in (select u.id $USERS_SQL); update tenants set disabled_at='$STAMP' where id in (select t.id $TENANTS_SQL); commit;" >/dev/null
echo "DISABLED: users=$(q "select count(*) from users where disabled_at='$STAMP';") tenants=$(q "select count(*) from tenants where disabled_at='$STAMP';") (list: $LIST)"
echo "undo:  ssh karen@188.121.123.218 'bash -s -- --undo $STAMP' < ~/Downloads/karenseir-demo-data-disable.sh"
echo "undo (on the server): cd $ROOT && docker compose exec -T db psql -U karenseir -d karenseir -c \"update users set disabled_at=null where disabled_at='$STAMP'; update tenants set disabled_at=null where disabled_at='$STAMP';\""
}
main "$@" </dev/null
