#!/usr/bin/env bash
# KarenSeir — enable HTTPS for karentravel.ir + www on the production server where nginx runs as a CONTAINER
# (karenseir-nginx-1, conf /opt/karenseir/nginx/default.conf, certs /opt/karenseir/certs → /etc/nginx/certs,
#  ACME webroot volume karenseir_certbot-www → /var/www/certbot). Run as root in /root.
# Phases:  1 backup → 2 certbot (apt) + Let's Encrypt via webroot → 3 copy certs → 4 add TLS server block (no redirect)
#          → 5 nginx -t + reload + local TLS check → 6 HTTP→HTTPS redirect for the domain only (IP stays HTTP)
#          → 7 .env: https origins + PUBLIC_WEB_URL, restart api → 8 renewal hook.  Any failure in 4-6 restores nginx conf.
# Rollback: bash /opt/karenseir/app/deploy/https-container-rollback.sh <backup-dir>
set -Eeuo pipefail
ROOT=/opt/karenseir; CONF=$ROOT/nginx/default.conf; CERTS=$ROOT/certs; NGX=karenseir-nginx-1
D=karentravel.ir; W=www.karentravel.ir; IP=188.121.123.218
TS=$(date +%Y%m%d-%H%M%S); BK=$ROOT/backups/https-$TS; LOG=$ROOT/https-$TS.log
exec > >(tee -a "$LOG") 2>&1
step(){ echo; echo "=== $* ==="; }
restore(){ echo "!! restoring nginx conf from $BK"; cp "$BK/default.conf" "$CONF"; docker exec $NGX nginx -t && docker exec $NGX nginx -s reload; }
CHANGED_NGINX=0
trap 'rc=$?; if [ $rc -ne 0 ] && [ $CHANGED_NGINX = 1 ]; then restore; fi; echo "RESULT: HTTPS-FAILED (rc=$rc) — log $LOG"' ERR

step "0) preflight"
for h in $D $W; do r=$(getent hosts $h | awk '{print $1}' | head -1); echo "$h -> $r"; [ "$r" = "$IP" ] || { echo "BLOCKED: $h does not resolve to $IP"; exit 2; }; done
docker exec $NGX nginx -t
WEBROOT=$(docker inspect -f '{{range .Mounts}}{{if eq .Destination "/var/www/certbot"}}{{.Source}}{{end}}{{end}}' $NGX)
[ -d "$WEBROOT" ] || { echo "BLOCKED: no /var/www/certbot mount"; exit 2; }
echo "webroot: $WEBROOT"
grep -q "acme-challenge" "$CONF" || { echo "BLOCKED: no acme-challenge location in $CONF"; exit 2; }

step "1) backup"
mkdir -p "$BK"; cp "$CONF" "$BK/default.conf"; cp "$ROOT/.env" "$BK/env.bak"; cp -a "$CERTS" "$BK/certs" 2>/dev/null || true
echo "backup: $BK"

step "2) certificate (Let's Encrypt, webroot)"
command -v certbot >/dev/null || { DEBIAN_FRONTEND=noninteractive apt-get install -y certbot >/dev/null; }
echo "probe" > "$WEBROOT/.well-known-probe" 2>/dev/null || true
mkdir -p "$WEBROOT/.well-known/acme-challenge"; echo ok > "$WEBROOT/.well-known/acme-challenge/probe"
c=$(curl -s -m 10 -o /dev/null -w '%{http_code}' -H "Host: $D" http://127.0.0.1/.well-known/acme-challenge/probe || true); echo "local ACME probe: $c"
rm -f "$WEBROOT/.well-known/acme-challenge/probe" "$WEBROOT/.well-known-probe"
[ "$c" = 200 ] || { echo "BLOCKED: ACME path not served locally"; exit 2; }
if [ ! -s /etc/letsencrypt/live/$D/fullchain.pem ]; then
  certbot certonly --webroot -w "$WEBROOT" -d $D -d $W --agree-tos --register-unsafely-without-email --non-interactive --keep-until-expiring
fi
openssl x509 -in /etc/letsencrypt/live/$D/fullchain.pem -noout -subject -enddate

step "3) install certs for the nginx container"
mkdir -p "$CERTS/live/$D"
cp -L /etc/letsencrypt/live/$D/fullchain.pem "$CERTS/live/$D/fullchain.pem"
cp -L /etc/letsencrypt/live/$D/privkey.pem "$CERTS/live/$D/privkey.pem"
chmod 600 "$CERTS/live/$D/privkey.pem"
docker exec $NGX test -s /etc/nginx/certs/live/$D/fullchain.pem && echo "visible in container"

step "4) TLS server block (copy of the active :80 server, same locations)"
CHANGED_NGINX=1
python3 - "$CONF" "$D" "$W" <<'PY'
import re,sys
p,d,w=sys.argv[1:]; s=open(p).read()
if 'managed-by: https-container.sh' in s: print('TLS block already present'); sys.exit(0)
def blocks(t):
    out=[]; i=0
    for m in re.finditer(r'(?m)^[ \t]*server[ \t]*\{',t):
        if m.start()<i: continue
        depth=0; j=m.end()-1
        while j<len(t):
            if t[j]=='{': depth+=1
            elif t[j]=='}':
                depth-=1
                if depth==0: break
            j+=1
        out.append((m.start(),j+1)); i=j+1
    return out
act=None
for a,b in blocks(s):
    body=s[a:b]
    if re.search(r'(?m)^[ \t]*listen[ \t]+80\b',body): act=body; break
assert act, 'no active listen 80 server'
tls=re.sub(r'(?m)^([ \t]*)listen[ \t]+80[^;]*;',r'\1listen 443 ssl http2;',act,count=1)
tls=re.sub(r'(?m)^([ \t]*)listen[ \t]+\[::\]:80[^;]*;',r'\1listen [::]:443 ssl;',tls)
tls=re.sub(r'(?m)^([ \t]*)server_name[^;]*;',r'\1server_name %s %s;\n\1ssl_certificate     /etc/nginx/certs/live/%s/fullchain.pem;\n\1ssl_certificate_key /etc/nginx/certs/live/%s/privkey.pem;\n\1ssl_protocols TLSv1.2 TLSv1.3;\n\1ssl_session_cache shared:SSL:10m;'%(d,w,d,d),tls,count=1)
s=s.rstrip()+'\n\n# managed-by: https-container.sh (TLS)\n'+tls+'\n'
open(p,'w').write(s); print('TLS block appended')
PY
docker exec $NGX nginx -t
docker exec $NGX nginx -s reload; sleep 2

step "5) local TLS check"
for u in / /hotels /api/health; do echo "$(curl -s -m 15 -o /dev/null -w '%{http_code}' --resolve $D:443:127.0.0.1 https://$D$u) https://$D$u"; done
c=$(curl -s -m 15 -o /dev/null -w '%{http_code}' --resolve $D:443:127.0.0.1 https://$D/); [ "$c" = 200 ] || { echo "TLS homepage not 200"; false; }

step "6) redirect http://karentravel.ir → https (IP access unchanged)"
python3 - "$CONF" "$D" "$W" <<'PY'
import sys
p,d,w=sys.argv[1:]; s=open(p).read()
if 'managed-by: https-container.sh (redirect)' in s: print('redirect already present'); sys.exit(0)
s=s.rstrip()+f'''

# managed-by: https-container.sh (redirect)
server {{
    listen 80;
    server_name {d} {w};
    location /.well-known/acme-challenge/ {{ root /var/www/certbot; }}
    location / {{ return 301 https://{d}$request_uri; }}
}}
'''
open(p,'w').write(s); print('redirect block appended')
PY
docker exec $NGX nginx -t
docker exec $NGX nginx -s reload; sleep 2
echo "http domain: $(curl -s -m 10 -o /dev/null -w '%{http_code} -> %{redirect_url}' -H "Host: $D" http://127.0.0.1/hotels)"
echo "http IP:     $(curl -s -m 10 -o /dev/null -w '%{http_code}' http://127.0.0.1/)"
CHANGED_NGINX=0

step "7) app origins (.env) + restart api"
cd $ROOT
python3 - .env <<'PY'
import re,sys
p=sys.argv[1]; s=open(p).read()
def setv(k,v):
    global s
    if re.search(rf'(?m)^{k}=',s): s=re.sub(rf'(?m)^{k}=.*$',f'{k}={v}',s)
    else: s=s.rstrip('\n')+f'\n{k}={v}\n'
cur=re.search(r'(?m)^CORS_ORIGINS=(.*)$',s); items=[x.strip() for x in (cur.group(1) if cur else '').split(',') if x.strip()]
for o in ['https://karentravel.ir','https://www.karentravel.ir']:
    if o not in items: items.append(o)
setv('CORS_ORIGINS',','.join(items))
setv('PUBLIC_WEB_URL','https://karentravel.ir')
open(p,'w').write(s); print('CORS_ORIGINS=',','.join(items)); print('PUBLIC_WEB_URL=https://karentravel.ir')
PY
docker compose up -d --no-deps api; sleep 15; docker compose ps api
echo "api via TLS: $(curl -s -m 15 -o /dev/null -w '%{http_code}' --resolve $D:443:127.0.0.1 https://$D/api/health)"

step "8) auto-renewal hook"
mkdir -p /etc/letsencrypt/renewal-hooks/deploy
cat > /etc/letsencrypt/renewal-hooks/deploy/karenseir-nginx.sh <<HOOK
#!/bin/sh
cp -L /etc/letsencrypt/live/$D/fullchain.pem $CERTS/live/$D/fullchain.pem
cp -L /etc/letsencrypt/live/$D/privkey.pem $CERTS/live/$D/privkey.pem
docker exec $NGX nginx -s reload
HOOK
chmod +x /etc/letsencrypt/renewal-hooks/deploy/karenseir-nginx.sh
systemctl list-timers 2>/dev/null | grep -i certbot || echo "(certbot timer not listed — renew via cron)"
grep -q "certbot renew" /etc/crontab || echo "17 3 * * * root certbot renew -q" >> /etc/crontab
trap - ERR
echo; echo "RESULT: HTTPS-OK — backup $BK, log $LOG"
