#!/usr/bin/env bash
# Compares rendered HTML of key pages: pre-redesign backup image vs the live web container.
set -u
IMG=${1:-karenseir-web:pre-redesign-20261116-190552}
docker inspect -f '{{range .Config.Env}}{{println .}}{{end}}' karenseir-web-1 | grep -v '^$' > /tmp/web.env
N=$(docker inspect -f '{{range $k,$v := .NetworkSettings.Networks}}{{$k}}{{end}}' karenseir-web-1)
docker rm -f kw-old >/dev/null 2>&1
docker run -d --rm --name kw-old --network "$N" --env-file /tmp/web.env "$IMG" >/dev/null
sleep 25
O=$(docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' kw-old)
W=$(docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' karenseir-web-1)
txt(){ sed 's/<script[^>]*>[^<]*<\/script>//g; s/<[^>]*>/ /g' "$1" | tr -s ' \n' | md5sum | cut -c1-8; }
cls(){ grep -o 'class="[^"]*"' "$1" | md5sum | cut -c1-8; }
for p in / /hotels /flights /services; do
  curl -s -m 20 "http://$O:3000$p" > /tmp/o.html; curl -s -m 20 "http://$W:3000$p" > /tmp/n.html
  printf '%-10s text:%s/%s  classes:%s/%s\n' "$p" "$(txt /tmp/o.html)" "$(txt /tmp/n.html)" "$(cls /tmp/o.html)" "$(cls /tmp/n.html)"
done
diff <(grep -o 'class="[^"]*"' /tmp/o.html) <(grep -o 'class="[^"]*"' /tmp/n.html) | head -5
docker rm -f kw-old >/dev/null
