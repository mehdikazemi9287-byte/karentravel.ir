#!/usr/bin/env bash
# KarenSeir — free a mobile number held by a DEMO seed account (*.test email) so its owner can register
# as a real customer. Only touches users whose email ends in .test. Reversible: prints the undo SQL.
# Run from the Mac:
#   ssh karen@188.121.123.218 'MOBILE=+989191258009 bash -s' < ~/Downloads/karenseir-free-demo-mobile.sh
main() {
set -euo pipefail
case "${MOBILE:-}" in +989[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]) ;; *) echo "ABORT: set MOBILE=+989xxxxxxxxx"; exit 1;; esac
cd /opt/karenseir
PSQL=(docker compose exec -T db psql -U karenseir -d karenseir -At -v ON_ERROR_STOP=1)
held=$("${PSQL[@]}" -c "select u.id||'|'||t.slug||'|'||u.email from users u join tenants t on t.id=u.tenant_id where u.mobile_e164='$MOBILE';")
[ -n "$held" ] || { echo "nothing to do: no account holds this number"; exit 0; }
echo "held by: $held"
case "$held" in *.test) ;; *) echo "ABORT: holder is not a demo (*.test) account — not touching a real account"; exit 2;; esac
uid=${held%%|*}
"${PSQL[@]}" -c "update users set mobile_e164=null where id=$uid and email like '%.test' and mobile_e164='$MOBILE';" >/dev/null
echo "FREED: demo user $uid no longer holds the number."
echo "undo:  docker compose exec -T db psql -U karenseir -d karenseir -c \"update users set mobile_e164='$MOBILE' where id=$uid;\""
}
main </dev/null
