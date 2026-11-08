#!/usr/bin/env bash
# KarenSeir — enable HTTPS for karentravel.ir (+ www) on the production server (host nginx + Let's Encrypt).
#
# Run the read-only audit first:   ssh karen@188.121.123.218 'bash -s' < ~/Downloads/karenseir-server-audit.sh
# Preflight only (changes nothing): ssh karen@188.121.123.218 'bash -s -- --check' < ~/Downloads/karenseir-https.sh
# Apply:
#   - karen has passwordless sudo:  ssh karen@188.121.123.218 'bash -s' < ~/Downloads/karenseir-https.sh
#   - sudo asks for a password:     scp ~/Downloads/karenseir-https.sh karen@188.121.123.218:/tmp/ && ssh -t karen@188.121.123.218 'bash /tmp/karenseir-https.sh'
#     (with 'bash -s' there is no terminal for the sudo prompt; the script detects that and stops with this command instead of hanging)
# Rollback: same two forms with karenseir-https-rollback.sh
#
# Options (environment variables, put them before bash:  ssh ... 'HSTS_MAX_AGE=31536000 bash -s' < ...):
#   HSTS_MAX_AGE=300        HSTS max-age in seconds (start short; rerun later with 31536000 to raise — nothing else changes)
#   WITH_WWW=1              also serve/redirect www.karentravel.ir (needs its DNS A record → this server); 0 = apex only
#   CERTBOT_EMAIL=          Let's Encrypt account e-mail for expiry notices (optional)
#   CERT_FULLCHAIN= CERT_KEY=   use a purchased certificate (e.g. Talahost) instead of Let's Encrypt; no auto-renewal
#   IGNORE_NGINX_EXTRAS=0   1 = drop extra nginx locations/directives found in the current site config (review the list first!)
#   ASSUME_443_OPEN=0       1 = continue although this server cannot reach its own public 443 (only after checking from the Mac)
#
# Steps: 0 read-only preflight (abort on anything unexpected) → 1 backup → 2 certbot/ufw → 3 nginx HTTP + ACME webroot →
#        4 certificate → 5 nginx TLS (no redirect yet) + reachability → 6 .env + rebuild web + restart api/web →
#        7 nginx final (HTTP→HTTPS redirect, HTTP/2, short HSTS) → 8 renewal check → 9 verification → HTTPS-OK
# Idempotent: reruns reuse the valid certificate, rewrite the same managed nginx file and skip the web rebuild when .env is unchanged.
set -euo pipefail

DOMAIN=karentravel.ir
WWW=www.$DOMAIN
EXPECTED_IP=${EXPECTED_IP:-188.121.123.218}
APP_DIR=${APP_DIR:-/opt/karenseir}
HSTS_MAX_AGE=${HSTS_MAX_AGE:-300}
WITH_WWW=${WITH_WWW:-1}
CERTBOT_EMAIL=${CERTBOT_EMAIL:-}
CERT_FULLCHAIN=${CERT_FULLCHAIN:-}
CERT_KEY=${CERT_KEY:-}
IGNORE_NGINX_EXTRAS=${IGNORE_NGINX_EXTRAS:-0}
ASSUME_443_OPEN=${ASSUME_443_OPEN:-0}
WEBROOT=/var/www/letsencrypt
MANAGED_NAME=karentravel-https.conf
MARKER="managed-by: karenseir-https.sh"
TS=$(date -u +%Y%m%d-%H%M%S)
BK="$APP_DIR/backups/https-$TS"
CHECK_ONLY=0; [ "${1:-}" = "--check" ] && CHECK_ONLY=1
SSH_CMD="ssh karen@$EXPECTED_IP"
RUN_TTY="scp ~/Downloads/karenseir-https.sh karen@$EXPECTED_IP:/tmp/ && ssh -t karen@$EXPECTED_IP 'bash /tmp/karenseir-https.sh'"
ROLLBACK_CMD="$SSH_CMD 'bash -s' < ~/Downloads/karenseir-https-rollback.sh   (password sudo: scp it to /tmp and ssh -t karen@$EXPECTED_IP 'bash /tmp/karenseir-https-rollback.sh')"
CHANGED=0
FAILS=()
WARNS=()

say()  { printf '%s\n' "$*"; }
ok()   { printf '  ok   %s\n' "$*"; }
warn() { printf '  WARN %s\n' "$*"; WARNS+=("$*"); }
fail() { printf '  FAIL %s\n' "$*"; FAILS+=("$*"); }
die()  {
  printf '\nHTTPS-FAILED: %s\n' "$*" >&2
  if [ "$CHANGED" = 1 ]; then printf 'Backups: %s\nRollback: %s\n' "$BK" "$ROLLBACK_CMD" >&2
  else printf 'Nothing was changed on the server.\n' >&2; fi
  exit 1
}
trap 'rc=$?; printf "\nHTTPS-FAILED at line %s (exit %s)\n" "$LINENO" "$rc" >&2; [ "$CHANGED" = 1 ] && printf "Backups: %s\nRollback: %s\n" "$BK" "$ROLLBACK_CMD" >&2; exit $rc' ERR

print_fallbacks() {
  cat <<EOF

Let's Encrypt cannot be used from this server right now. Nothing was changed. Options:
  1) Certificate bought from Talahost (or any CA reseller, DV for $DOMAIN + $WWW): put the files on the server and rerun:
       ssh karen@$EXPECTED_IP 'CERT_FULLCHAIN=/home/karen/ssl/fullchain.pem CERT_KEY=/home/karen/ssl/privkey.pem bash -s' < ~/Downloads/karenseir-https.sh
     (fullchain = certificate + intermediate bundle; renew it yourself before expiry — the script prints the date)
  2) Issue a Let's Encrypt certificate elsewhere with a DNS-01 challenge (e.g. acme.sh/certbot --manual --preferred-challenges dns
     on the Mac, TXT record _acme-challenge.$DOMAIN in the Talahost DNS panel), copy the files to the server, then use option 1.
  3) ArvanCloud CDN SSL: move the domain's nameservers to ArvanCloud, enable CDN proxy + free edge certificate.
     This changes DNS (A records then show Arvan edge IPs), so this script's DNS check will refuse it — a separate plan is needed.
  4) If only outbound HTTPS is blocked (validation from Let's Encrypt to port 80 still works), rerun with an outbound proxy:
       ssh karen@$EXPECTED_IP 'HTTPS_PROXY=http://<proxy>:<port> bash -s' < ~/Downloads/karenseir-https.sh
EOF
}

# ---------------------------------------------------------------- sudo (detect, never hang)
INTERACTIVE=0; [ -t 0 ] && [ -t 1 ] && INTERACTIVE=1
if [ "$(id -u)" -eq 0 ]; then SUDO=""
elif sudo -n true 2>/dev/null; then SUDO="sudo -n"
elif [ "$INTERACTIVE" = 1 ]; then
  say "sudo needs a password (asked once):"; sudo -v || { echo "sudo refused"; exit 1; }; SUDO="sudo"
  ( while kill -0 $$ 2>/dev/null; do sudo -n true 2>/dev/null; sleep 50; done ) &
else
  SUDO=NONE
fi
exec </dev/null   # nothing below may read the script from stdin ('bash -s')
sudo_ok() { [ "$SUDO" != NONE ]; }
S() { case "$SUDO" in ""|NONE) "$@";; *) $SUDO "$@";; esac; }

WORK=$(mktemp -d); trap 'rm -rf "$WORK"' EXIT
exec 9>"/tmp/karenseir-https.lock"; flock -n 9 || { echo "another karenseir-https run is active"; exit 1; }

# ================================================================ 0 PREFLIGHT (read-only)
say "== 0/9 preflight (read-only) $(date -u +%FT%TZ)"
cd "$APP_DIR" 2>/dev/null || { echo "ABORT: $APP_DIR not found"; exit 1; }
if sudo_ok; then ok "sudo available (${SUDO:-root})"; else fail "sudo needs a password and there is no terminal. Run:  $RUN_TTY"; fi
for c in curl python3 docker getent awk openssl flock ss; do command -v "$c" >/dev/null || fail "missing command: $c"; done
. /etc/os-release 2>/dev/null || true; [ "${ID:-}" = ubuntu ] && ok "OS $PRETTY_NAME" || warn "OS is not Ubuntu (${PRETTY_NAME:-?})"
docker compose version >/dev/null 2>&1 && ok "docker compose $(docker compose version --short 2>/dev/null)" || fail "docker compose not usable by $(id -un)"
[ -f .env ] && [ -w .env ] && ok ".env present and writable" || fail "$APP_DIR/.env missing or not writable by $(id -un)"
case "$HSTS_MAX_AGE" in ''|*[!0-9]*) fail "HSTS_MAX_AGE must be a number";; esac
NAMES=("$DOMAIN"); [ "$WITH_WWW" = 1 ] && NAMES+=("$WWW")

# -- certificate source
CERT_MODE=letsencrypt
if [ -n "$CERT_FULLCHAIN$CERT_KEY" ]; then
  CERT_MODE=manual
  S test -r "$CERT_FULLCHAIN" || fail "CERT_FULLCHAIN not readable: $CERT_FULLCHAIN"
  S test -r "$CERT_KEY" || fail "CERT_KEY not readable: $CERT_KEY"
  if [ ${#FAILS[@]} -eq 0 ]; then
    c_pub=$(S openssl x509 -in "$CERT_FULLCHAIN" -noout -pubkey 2>/dev/null | openssl sha256 || true)
    k_pub=$(S openssl pkey -in "$CERT_KEY" -pubout 2>/dev/null | openssl sha256 || true)
    [ -n "$c_pub" ] && [ "$c_pub" = "$k_pub" ] && ok "manual certificate matches key" || fail "manual certificate and key do not match"
    S openssl x509 -in "$CERT_FULLCHAIN" -noout -checkend 604800 >/dev/null || fail "manual certificate expires within 7 days"
    san=$(S openssl x509 -in "$CERT_FULLCHAIN" -noout -ext subjectAltName 2>/dev/null || true)
    for n in "${NAMES[@]}"; do grep -q "DNS:$n\b" <<<"$san" || { [ "$n" = "$WWW" ] && grep -qF "DNS:*.$DOMAIN" <<<"$san"; } || fail "manual certificate does not cover $n"; done
    ok "manual certificate: $(S openssl x509 -in "$CERT_FULLCHAIN" -noout -enddate)"
  fi
  CERT_DIR=/etc/nginx/ssl-karentravel; CERT_FILE=$CERT_DIR/fullchain.pem; KEY_FILE=$CERT_DIR/privkey.pem
else
  CERT_FILE=/etc/letsencrypt/live/$DOMAIN/fullchain.pem; KEY_FILE=/etc/letsencrypt/live/$DOMAIN/privkey.pem
  code=$(curl -sS -m 15 -o "$WORK/acme.json" -w '%{http_code}' https://acme-v02.api.letsencrypt.org/directory 2>"$WORK/acme.err" || true)
  if [ "$code" = 200 ] && grep -q newOrder "$WORK/acme.json"; then ok "Let's Encrypt API reachable"
  else say "  FAIL Let's Encrypt API unreachable (http=$code $(head -c 200 "$WORK/acme.err"))"; print_fallbacks; exit 3; fi
fi

# -- public IP + DNS
pub=$(curl -sS -m 8 https://api.ipify.org 2>/dev/null || curl -sS -m 8 https://ifconfig.me 2>/dev/null || true)
if [ -n "$pub" ]; then [ "$pub" = "$EXPECTED_IP" ] && ok "public IP $pub" || fail "public IP is $pub, expected $EXPECTED_IP"
elif ip -4 addr 2>/dev/null | grep -q " $EXPECTED_IP/"; then ok "public IP $EXPECTED_IP (local interface)"
else warn "public IP could not be determined (ipify/ifconfig.me unreachable); trusting EXPECTED_IP=$EXPECTED_IP"; fi
for n in "${NAMES[@]}"; do
  a=$(getent ahostsv4 "$n" 2>/dev/null | awk '{print $1}' | sort -u | tr '\n' ' ' || true)
  [ "${a% }" = "$EXPECTED_IP" ] && ok "DNS A $n → $EXPECTED_IP" || fail "DNS A $n → '${a% }' (expected only $EXPECTED_IP)$( [ "$n" = "$WWW" ] && echo "; fix the www record at Talahost or rerun with WITH_WWW=0")"
  aaaa=$(getent ahostsv6 "$n" 2>/dev/null | awk '$1 !~ /^::ffff:/{print $1}' | sort -u | tr '\n' ' ' || true)
  if [ -n "$aaaa" ] && ! ip -6 addr 2>/dev/null | grep -qF "${aaaa%% *}"; then fail "DNS AAAA $n → $aaaa is not this server (Let's Encrypt would validate over IPv6); remove it at Talahost"; fi
  if command -v dig >/dev/null; then g=$(dig +short +time=3 +tries=1 A "$n" @8.8.8.8 2>/dev/null | tr '\n' ' ' || true); [ -n "$g" ] && say "       (8.8.8.8 sees $n → ${g% })"; fi
done

# -- nginx type: host vs container
cont80=$(docker ps --format '{{.Names}} {{.Ports}}' 2>/dev/null </dev/null | grep -E '(0\.0\.0\.0|\[::\]|:::):(80|443)->' || true)
[ -z "$cont80" ] || fail "a container publishes port 80/443 ($cont80) — container nginx is not supported by this script"
if command -v nginx >/dev/null && systemctl is-active --quiet nginx; then ok "host nginx active ($(nginx -v 2>&1 | sed 's/.*\///'))"; else fail "host nginx not installed/active"; fi
if sudo_ok; then
  listeners=$(S ss -tlnpH 2>/dev/null || true)
  l80=$(awk '$4 ~ /:80$/' <<<"$listeners"); l443=$(awk '$4 ~ /:443$/' <<<"$listeners")
  [ -n "$l80" ] && ! grep -vq nginx <<<"$l80" && ok "port 80 → nginx" || fail "port 80 listener is not (only) nginx: $(tr '\n' ' ' <<<"$l80")"
  if [ -z "$l443" ]; then ok "port 443 free"; elif ! grep -vq nginx <<<"$l443"; then ok "port 443 → nginx (rerun)"; else fail "port 443 used by something else: $(tr '\n' ' ' <<<"$l443")"; fi
  UFW=$(S ufw status 2>/dev/null | head -1 || true)
  case "$UFW" in *inactive*|"") ok "ufw ${UFW:-not installed}";; *active*) S ufw status | grep -E '^(443|443/tcp|Nginx Full|Nginx HTTPS)\s+ALLOW' >/dev/null && ok "ufw allows 443" || say "  note ufw active without 443 rule → step 2 adds 'ufw allow 443/tcp'";; esac
  S nginx -t >/dev/null 2>"$WORK/nt0" && ok "current nginx -t passes" || fail "current nginx config already fails nginx -t: $(tail -2 "$WORK/nt0" | tr '\n' ' ')"
  S nginx -T >"$WORK/nginx-T.txt" 2>/dev/null || true
fi

# -- parse the current nginx site config
cat >"$WORK/parse.py" <<'PY'
import re, sys
from urllib.parse import urlsplit
text = open(sys.argv[1], encoding="utf-8", errors="replace").read()
marker, ip = sys.argv[2], sys.argv[3]
files, cur = {}, None
for line in text.splitlines():
    m = re.match(r"# configuration file (.+):$", line)
    if m: cur = m.group(1); files[cur] = []; continue
    if cur: files[cur].append(line)
def tokens(lines):
    s = "\n".join(re.sub(r"(^|\s)#.*$", "", l) for l in lines)
    return re.findall(r'"[^"]*"|\'[^\']*\'|[{};]|[^\s{};]+', s)
def parse(toks):
    root = {"name": "root", "args": [], "dirs": [], "blocks": []}; stack = [root]; words = []
    for t in toks:
        if t == ";":
            if words: stack[-1]["dirs"].append(words)
            words = []
        elif t == "{":
            b = {"name": words[0] if words else "", "args": words[1:], "dirs": [], "blocks": []}
            stack[-1]["blocks"].append(b); stack.append(b); words = []
        elif t == "}":
            if len(stack) > 1: stack.pop()
            words = []
        else: words.append(t.strip("\"'"))
    return root
def walk(b, name):
    for c in b["blocks"]:
        if c["name"] == name: yield c
        yield from walk(c, name)
out, servers = {}, []
inc_sites = any(re.search(r"include\s+/etc/nginx/sites-enabled/", l) for l in files.get("/etc/nginx/nginx.conf", []))
upstreams = set()
for f, lines in files.items():
    tree = parse(tokens(lines))
    for u in walk(tree, "upstream"): upstreams.update(u["args"])
    managed = ""
    if lines and marker in lines[0]:
        m = re.search(r"mode=(\w+)", lines[0]); managed = m.group(1) if m else "unknown"
    for s in walk(tree, "server"):
        servers.append((f, s, managed))
app, other, stock = [], [], []
web, api, extras, cmb, ipv6, names, managed_mode = set(), {}, [], set(), False, set(), ""
SKIP_LOC = {"/.well-known/acme-challenge/", "^~ /.well-known/acme-challenge/", "/.well-known/", "^~ /.well-known/"}
API_LOC = {"/api/", "/api", "^~ /api/"}
OK_SRV = {"listen", "server_name", "return", "root", "index", "client_max_body_size", "add_header", "access_log", "error_log",
          "ssl_certificate", "ssl_certificate_key", "ssl_protocols", "ssl_ciphers", "ssl_prefer_server_ciphers", "ssl_session_cache",
          "ssl_session_timeout", "ssl_session_tickets", "ssl_dhparam", "http2", "charset", "server_tokens", "limit_req", "proxy_hide_header",
          "gzip", "gzip_vary", "gzip_min_length", "gzip_types", "gzip_proxied", "gzip_comp_level", "proxy_set_header", "proxy_http_version",
          "proxy_connect_timeout", "proxy_read_timeout", "proxy_send_timeout", "proxy_buffering", "try_files"}
OK_LOC = OK_SRV | {"proxy_pass", "default_type", "alias"}
def has_proxy(b): return any(d[0] == "proxy_pass" for d in b["dirs"]) or any(has_proxy(c) for c in b["blocks"])
for f, s, managed in servers:
    sd = {d[0]: d[1:] for d in s["dirs"]}
    listens = [" ".join(d[1:]) for d in s["dirs"] if d[0] == "listen"]
    sn = [n for d in s["dirs"] if d[0] == "server_name" for n in d[1:]]
    if has_proxy(s) or managed:
        app.append(f); names.update(sn); managed_mode = managed or managed_mode
        ipv6 = ipv6 or any("[::]" in l for l in listens)
        if "client_max_body_size" in sd: cmb.add(sd["client_max_body_size"][0])
        for d in s["dirs"]:
            if d[0] == "include" and not d[1].endswith("proxy_params"): extras.append(f"{f}: server include {d[1]}")
            elif d[0] not in OK_SRV and d[0] != "include": extras.append(f"{f}: server directive {' '.join(d)}")
        for loc in s["blocks"]:
            if loc["name"] != "location": extras.append(f"{f}: block {loc['name']}"); continue
            arg = " ".join(loc["args"])
            if arg in SKIP_LOC: continue
            pp = [d[1] for d in loc["dirs"] if d[0] == "proxy_pass"]
            for d in loc["dirs"]:
                if d[0] == "include" and not d[1].endswith("proxy_params"): extras.append(f"{f}: location {arg}: include {d[1]}")
                elif d[0] not in OK_LOC and d[0] != "include": extras.append(f"{f}: location {arg}: {' '.join(d)}")
            if loc["blocks"]: extras.append(f"{f}: nested block in location {arg}")
            if arg == "/":
                web.update(pp)
            elif arg in API_LOC:
                for p in pp: api[p] = arg
            else: extras.append(f"{f}: location {arg}" + (f" -> {pp[0]}" if pp else ""))
    else:
        if set(sn) <= {"_", "localhost", ""} and not any("ssl" in l for l in listens): stock.append(f)
        else: other.append(f"{f} ({' '.join(sn) or 'no server_name'}; listen {', '.join(listens)})")
def host_ok(u):
    h = urlsplit(u).hostname or ""
    if h in upstreams: return "upstream-block"
    if h in ("127.0.0.1", "localhost", "::1", ip) or re.fullmatch(r"[0-9.]+", h): return "ok"
    return "hostname"
out["INCLUDES_SITES_ENABLED"] = "1" if inc_sites else "0"
out["APP_FILES"] = " ".join(sorted(set(app)))
out["STOCK_FILES"] = " ".join(sorted(set(stock) - set(app)))
out["OTHER_SERVERS"] = " | ".join(other)
out["MANAGED_MODE"] = managed_mode
out["SERVER_NAMES"] = " ".join(sorted(names))
out["HAS_IPV6"] = "1" if ipv6 else "0"
out["CLIENT_MAX_BODY"] = sorted(cmb)[-1] if cmb else "16m"
out["WEB_UPSTREAM"] = " ".join(sorted(web))
out["API_UPSTREAM"] = " ".join(sorted(api))
out["API_LOC"] = " ".join(sorted(set(api.values())))
out["EXTRAS"] = " || ".join(extras)
bad = [u for u in list(web) + list(api) if host_ok(u) != "ok"]
out["UPSTREAM_PROBLEM"] = " ".join(f"{u}({host_ok(u)})" for u in bad)
if len(web) == 1:
    w = next(iter(web)); p = urlsplit(w); out["WEB_HEALTH"] = f"{p.scheme}://{p.netloc}/"
if len(api) == 1:
    a, loc = next(iter(api.items())); p = urlsplit(a); base = f"{p.scheme}://{p.netloc}"
    rest = "/api/health"[len(loc.replace("^~ ", "")):]
    out["API_HEALTH"] = (base + p.path.rstrip("/") + "/" + rest.lstrip("/")) if p.path else base + "/api/health"
for k, v in out.items(): print(f"{k}={v}")
PY
declare -A NG
if [ -s "$WORK/nginx-T.txt" ]; then
  while IFS='=' read -r k v; do NG[$k]=$v; done < <(python3 "$WORK/parse.py" "$WORK/nginx-T.txt" "$MARKER" "$EXPECTED_IP")
  say "       nginx app files: ${NG[APP_FILES]:-none}; server_name: ${NG[SERVER_NAMES]:-?}; managed mode: ${NG[MANAGED_MODE]:-no}"
  [ -n "${NG[APP_FILES]}" ] || fail "no nginx server block with proxy_pass found"
  [ "${NG[INCLUDES_SITES_ENABLED]}" = 1 ] || [ -d /etc/nginx/conf.d ] || fail "neither sites-enabled nor conf.d is included by nginx.conf"
  [ -z "${NG[OTHER_SERVERS]}" ] || fail "nginx serves other sites too (${NG[OTHER_SERVERS]}) — not expected on this server"
  [ -n "${NG[STOCK_FILES]}" ] && say "       stock default site(s) to disable: ${NG[STOCK_FILES]}"
  if [ -n "${NG[WEB_UPSTREAM]}" ] && [ "${NG[WEB_UPSTREAM]}" = "${NG[WEB_UPSTREAM]%% *}" ]; then ok "web upstream ${NG[WEB_UPSTREAM]}"; else fail "web upstream (location /) not unique: '${NG[WEB_UPSTREAM]}'"; fi
  if [ -n "${NG[API_UPSTREAM]}" ] && [ "${NG[API_UPSTREAM]}" = "${NG[API_UPSTREAM]%% *}" ]; then ok "api upstream ${NG[API_LOC]} → ${NG[API_UPSTREAM]}"; else fail "api upstream (location /api/) not unique: '${NG[API_UPSTREAM]}'"; fi
  [ -z "${NG[UPSTREAM_PROBLEM]}" ] || fail "upstream not a loopback/IP address: ${NG[UPSTREAM_PROBLEM]}"
  if [ -n "${NG[EXTRAS]}" ]; then
    say "       extra nginx config the managed file would NOT carry over:"; tr '|' '\n' <<<"${NG[EXTRAS]}" | sed '/^$/d;s/^ */         - /'
    [ "$IGNORE_NGINX_EXTRAS" = 1 ] && warn "extras dropped on purpose (IGNORE_NGINX_EXTRAS=1)" || fail "unexpected nginx config (see list) — send this output; or rerun with IGNORE_NGINX_EXTRAS=1 after review"
  fi
  if [ -n "${NG[WEB_HEALTH]:-}" ]; then c=$(curl -s -o /dev/null -m 10 -w '%{http_code}' "${NG[WEB_HEALTH]}" || true); [ "$c" = 200 ] && ok "web upstream answers 200" || fail "web upstream ${NG[WEB_HEALTH]} → $c"; fi
  if [ -n "${NG[API_HEALTH]:-}" ]; then c=$(curl -s -o /dev/null -m 10 -w '%{http_code}' "${NG[API_HEALTH]}" || true); [ "$c" = 200 ] && ok "api upstream health 200 (${NG[API_HEALTH]})" || fail "api health ${NG[API_HEALTH]} → $c"; fi
elif sudo_ok; then fail "could not read 'nginx -T'"; fi

# -- certbot + existing certificate
if [ "$CERT_MODE" = letsencrypt ]; then
  if command -v certbot >/dev/null; then ok "certbot $(certbot --version 2>&1 | awk '{print $2}')"; else say "  note certbot not installed → step 2 installs it (apt)"; fi
fi
CERT_VALID=0
if sudo_ok && S test -f "$CERT_FILE"; then
  san=$(S openssl x509 -in "$CERT_FILE" -noout -ext subjectAltName 2>/dev/null || true); cover=1
  for n in "${NAMES[@]}"; do grep -q "DNS:$n\b" <<<"$san" || cover=0; done
  if [ "$cover" = 1 ] && S openssl x509 -in "$CERT_FILE" -noout -checkend 2592000 >/dev/null; then CERT_VALID=1; ok "existing certificate valid >30d for ${NAMES[*]}"; else say "  note existing certificate missing names or expiring → will (re)issue"; fi
fi

# -- compose wiring + current flags (non-secret values only)
declare -A CC
if docker compose config --format json </dev/null >"$WORK/cc.json" 2>"$WORK/cc.err"; then
  python3 - "$WORK/cc.json" >"$WORK/cc.txt" <<'PY'
import json, sys
c = json.load(open(sys.argv[1])); s = c.get("services", {})
def kv(x):
    if isinstance(x, list): return dict((i.split("=", 1) + [""])[:2] for i in x)
    return {k: ("" if v is None else str(v)) for k, v in (x or {}).items()}
w, a = s.get("web", {}), s.get("api", {})
b = w.get("build") or {}
b = b if isinstance(b, dict) else {"context": b}
args, wenv, aenv = kv(b.get("args")), kv(w.get("environment")), kv(a.get("environment"))
print("HAS_WEB=" + ("1" if w else "0")); print("HAS_API=" + ("1" if a else "0"))
print("WEB_CONTEXT=" + str(b.get("context", "")))
for k in ("NEXT_PUBLIC_SITE_URL", "NEXT_PUBLIC_API_URL", "ALLOW_HTTP_PREVIEW"):
    print(f"ARG_{k}=" + args.get(k, "<not-a-build-arg>"))
for k in ("CORS_ORIGINS", "ALLOW_HTTP_ORIGIN_PREVIEW", "ENVIRONMENT", "PUBLIC_WEB_URL"):
    print(f"API_{k}=" + aenv.get(k, "<unset>"))
PY
  while IFS='=' read -r k v; do CC[$k]=$v; done <"$WORK/cc.txt"
  [ "${CC[HAS_WEB]}" = 1 ] && [ "${CC[HAS_API]}" = 1 ] && ok "compose services web + api" || fail "compose has no web/api service"
  for k in NEXT_PUBLIC_SITE_URL NEXT_PUBLIC_API_URL ALLOW_HTTP_PREVIEW; do say "       web build arg $k=${CC[ARG_$k]}"; done
  for k in CORS_ORIGINS ALLOW_HTTP_ORIGIN_PREVIEW ENVIRONMENT PUBLIC_WEB_URL; do say "       api env $k=${CC[API_$k]}"; done
  [ "${CC[ARG_NEXT_PUBLIC_SITE_URL]}" != "<not-a-build-arg>" ] || fail "web build does not take NEXT_PUBLIC_SITE_URL as a build arg — .env change would not reach the bundle"
  [ "${CC[ARG_ALLOW_HTTP_PREVIEW]}" != "<not-a-build-arg>" ] || warn "web build has no ALLOW_HTTP_PREVIEW arg (Dockerfile default '' = HTTPS mode)"
  [ "${CC[API_CORS_ORIGINS]}" != "<unset>" ] || fail "api service gets no CORS_ORIGINS"
  ctx=${CC[WEB_CONTEXT]}
  if [ -f "$ctx/next.config.mjs" ]; then
    grep -q Strict-Transport-Security "$ctx/next.config.mjs" && say "  note deployed next.config.mjs still sets HSTS; nginx hides upstream HSTS (proxy_hide_header), so only nginx's short HSTS reaches browsers"
  else warn "web build context $ctx/next.config.mjs not found"; fi
else fail "docker compose config failed: $(tail -1 "$WORK/cc.err")"; fi
envget() { awk -F= -v k="$1" '$1==k{v=substr($0,index($0,"=")+1); gsub(/^["'\'']|["'\'']$/,"",v); print v; exit}' .env; }
for k in ENVIRONMENT CORS_ORIGINS NEXT_PUBLIC_SITE_URL NEXT_PUBLIC_API_URL PUBLIC_WEB_URL ALLOW_HTTP_PREVIEW ALLOW_HTTP_ORIGIN_PREVIEW; do say "       .env $k=$(envget $k)"; done
case "$(envget NEXT_PUBLIC_API_URL)" in /*|http://*/*[!/]*|https://*/*[!/]*) ok "NEXT_PUBLIC_API_URL is path-mounted";; *) fail "NEXT_PUBLIC_API_URL='$(envget NEXT_PUBLIC_API_URL)' is not a path-mounted URL (…/api); browsers on https would call it cross-origin";; esac
ip_keys=$(awk -F= -v ip="$EXPECTED_IP" '/^[A-Z0-9_]+=/ && index($0, ip){print $1}' .env | tr '\n' ' ')
[ -n "$ip_keys" ] && say "       .env keys whose value contains the IP: $ip_keys"
avail=$(df -Pm /var/lib/docker 2>/dev/null | awk 'NR==2{print $4}' || true); [ "${avail:-0}" -gt 2048 ] && ok "disk free ${avail}MB" || fail "less than 2GB free for the web rebuild (${avail:-?}MB)"

if [ ${#FAILS[@]} -gt 0 ]; then
  say ""; say "PREFLIGHT-ABORT (${#FAILS[@]} problem(s)); nothing was changed:"; for f in "${FAILS[@]}"; do say "  - $f"; done; exit 2
fi
say "PREFLIGHT-OK"; [ "$CHECK_ONLY" = 1 ] && exit 0

# ---------------------------------------------------------------- helpers for the change phase
NGINX_V=$(nginx -v 2>&1 | sed 's/.*nginx\///;s/ .*//')
ver_ge() { [ "$(printf '%s\n%s\n' "$2" "$1" | sort -V | head -1)" = "$2" ]; }
if ver_ge "$NGINX_V" 1.25.1; then L443="listen 443 ssl;"; L443v6="listen [::]:443 ssl;"; H2="http2 on;"; else L443="listen 443 ssl http2;"; L443v6="listen [::]:443 ssl http2;"; H2=""; fi
[ "${NG[HAS_IPV6]}" = 1 ] || L443v6=""
V6_80=""; [ "${NG[HAS_IPV6]}" = 1 ] && V6_80="listen [::]:80"
WEB_UP=${NG[WEB_UPSTREAM]}; API_UP=${NG[API_UPSTREAM]}; API_LOC=${NG[API_LOC]}
CMB=${NG[CLIENT_MAX_BODY]}
if [ "${NG[INCLUDES_SITES_ENABLED]}" = 1 ]; then TARGET=/etc/nginx/sites-available/$MANAGED_NAME; LINK=/etc/nginx/sites-enabled/$MANAGED_NAME
else TARGET=/etc/nginx/conf.d/$MANAGED_NAME; LINK=""; fi
SERVER_NAMES_80="$DOMAIN"; [ "$WITH_WWW" = 1 ] && SERVER_NAMES_80="$DOMAIN $WWW"

proxy_block() { # $1 upstream
  cat <<EOF
        proxy_pass $1;
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_set_header X-Request-ID \$request_id;
        proxy_connect_timeout 5s;
        proxy_read_timeout 60s;
EOF
}
render() { # $1 = precert | tls | final
  local mode=$1 acme="    location ^~ /.well-known/acme-challenge/ { root $WEBROOT; default_type text/plain; }"
  cat <<EOF
# $MARKER (mode=$mode, $(date -u +%FT%TZ), hsts=$HSTS_MAX_AGE) — do not edit by hand; rerun the script.
# Repo reference: deploy/nginx.karentravel-https.conf. Security headers other than HSTS come from the app
# (next.config.mjs, FastAPI _security_headers); nginx adds only HSTS so every header is sent exactly once.
limit_req_zone \$binary_remote_addr zone=kt_https_api:10m rate=20r/s;

# Bare IP / unknown hosts: pages go to the brand domain (in final mode).
server {
    listen 80 default_server;
    ${V6_80:+$V6_80 default_server;}
    server_name _;
    client_max_body_size $CMB;
$acme
EOF
  if [ "$mode" != final ] || envget NEXT_PUBLIC_API_URL | grep -F "$EXPECTED_IP" >/dev/null; then
    printf '    # kept while NEXT_PUBLIC_API_URL (server-side fetches) still uses the IP\n    location %s {\n%s\n    }\n' "$API_LOC" "$(proxy_block "$API_UP")"
  fi
  cat <<EOF
    location / {
EOF
  if [ "$mode" = final ]; then echo "        return 301 https://$DOMAIN\$request_uri;"; else proxy_block "$WEB_UP"; fi
  cat <<EOF
    }
}

server {
    listen 80;
    ${V6_80:+$V6_80;}
    server_name $SERVER_NAMES_80;
    client_max_body_size $CMB;
$acme
EOF
  if [ "$mode" = final ]; then
    echo "    location / { return 301 https://$DOMAIN\$request_uri; }"
  else
    printf '    location %s {\n%s\n    }\n    location / {\n%s\n    }\n' "$API_LOC" "$(proxy_block "$API_UP")" "$(proxy_block "$WEB_UP")"
  fi
  echo "}"
  [ "$mode" = precert ] && return 0
  local tls="    ssl_certificate $CERT_FILE;
    ssl_certificate_key $KEY_FILE;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_session_cache shared:kt_ssl:10m;
    ssl_session_timeout 1d;
    ssl_session_tickets off;"
  if [ "$WITH_WWW" = 1 ]; then
    cat <<EOF

server {
    $L443
    ${L443v6}
    ${H2}
    server_name $WWW;
$tls
    return 301 https://$DOMAIN\$request_uri;
}
EOF
  fi
  cat <<EOF

server {
    $L443
    ${L443v6}
    ${H2}
    server_name $DOMAIN;
$tls
    proxy_hide_header Strict-Transport-Security;
EOF
  [ "$mode" = final ] && echo "    add_header Strict-Transport-Security \"max-age=$HSTS_MAX_AGE\" always;"
  cat <<EOF
    client_max_body_size $CMB;
    gzip on;
    gzip_vary on;
    gzip_proxied any;
    gzip_min_length 1024;
    gzip_types application/json application/javascript application/xml text/css text/plain text/xml image/svg+xml;
$acme
    location $API_LOC {
        limit_req zone=kt_https_api burst=40 nodelay;
$(proxy_block "$API_UP")
    }
    location / {
$(proxy_block "$WEB_UP")
    }
}
EOF
}
apply_nginx() { # $1 mode — write, test, reload; restore previous file on failure
  local mode=$1
  render "$mode" >"$WORK/site.conf"
  S test -f "$TARGET" && S cp -p "$TARGET" "$WORK/prev.conf" || : >"$WORK/prev.conf"
  S install -m 0644 "$WORK/site.conf" "$TARGET"
  [ -n "$LINK" ] && S ln -sfn "$TARGET" "$LINK"
  if ! S nginx -t >"$WORK/nt" 2>&1; then
    cat "$WORK/nt" >&2
    if [ -s "$WORK/prev.conf" ]; then S install -m 0644 "$WORK/prev.conf" "$TARGET"; else S rm -f "$TARGET" ${LINK:+"$LINK"}; restore_disabled; fi
    S nginx -t >/dev/null 2>&1 && S systemctl reload nginx
    die "nginx -t failed for mode=$mode (previous config restored)"
  fi
  S systemctl reload nginx; sleep 2; ok "nginx mode=$mode active ($TARGET)"
}
restore_disabled() { [ -f "$BK/STATE" ] || return 0; while read -r src; do [ -n "$src" ] && S mv "$BK/disabled/$(basename "$src")" "$src"; done < <(sed -n 's/^DISABLED=//p' "$BK/STATE"); }
CURL=(curl -sS -m 20 --resolve "$DOMAIN:80:127.0.0.1" --resolve "$DOMAIN:443:127.0.0.1" --resolve "$WWW:80:127.0.0.1" --resolve "$WWW:443:127.0.0.1")
envset() { # KEY VALUE — replace first, drop duplicates, append if absent
  awk -F= -v k="$1" -v v="$2" 'BEGIN{d=0} $1==k{ if(!d){print k"="v; d=1}; next } {print} END{ if(!d) print k"="v }' .env >"$WORK/env.new"
  cat "$WORK/env.new" >.env
}

# ================================================================ 1 backup
say "== 1/9 backup → $BK"
mkdir -p "$BK/disabled"; chmod 700 "$BK"
S tar -czf "$BK/etc-nginx.tgz" -C / etc/nginx; S chown "$(id -u):$(id -g)" "$BK/etc-nginx.tgz"
cp -p .env "$BK/env.bak"; chmod 600 "$BK/env.bak"
{ echo "TS=$TS"; echo "TARGET=$TARGET"; echo "LINK=$LINK"; echo "PRIOR_MANAGED=${NG[MANAGED_MODE]}"; } >"$BK/STATE"
CHANGED=1; ok "nginx tar + .env copy saved"

# ================================================================ 2 certbot / ufw
say "== 2/9 tools + firewall"
if [ "$CERT_MODE" = letsencrypt ] && ! command -v certbot >/dev/null; then
  S env DEBIAN_FRONTEND=noninteractive apt-get update -qq >/dev/null 2>&1 || true
  S env DEBIAN_FRONTEND=noninteractive apt-get install -y -qq certbot >"$WORK/apt.log" 2>&1 || { tail -5 "$WORK/apt.log"; die "apt-get install certbot failed"; }
  ok "certbot installed ($(certbot --version 2>&1))"
fi
case "${UFW:-}" in *inactive*|"") ;; *active*) S ufw status | grep -E '^(443|443/tcp|Nginx Full|Nginx HTTPS)\s+ALLOW' >/dev/null || { S ufw allow 443/tcp >/dev/null; echo "UFW_ADDED=443/tcp" >>"$BK/STATE"; ok "ufw allow 443/tcp"; };; esac
S mkdir -p "$WEBROOT/.well-known/acme-challenge"

# ================================================================ 3 nginx: managed HTTP config + ACME webroot
say "== 3/9 nginx managed config"
for f in ${NG[APP_FILES]} ${NG[STOCK_FILES]}; do
  [ "$f" = "$TARGET" ] || [ "$f" = "$LINK" ] && continue
  [ "$(S readlink -f "$f")" = "$TARGET" ] && continue
  S mv "$f" "$BK/disabled/$(basename "$f")"; echo "DISABLED=$f" >>"$BK/STATE"; ok "disabled $f (kept in $BK/disabled)"
done
FIRST_MODE=precert
if [ "$CERT_VALID" = 1 ] || [ "$CERT_MODE" = manual ]; then FIRST_MODE=tls; [ "${NG[MANAGED_MODE]}" = final ] && FIRST_MODE=final; fi
if [ "$CERT_MODE" = manual ]; then
  S mkdir -p "$CERT_DIR"; S chmod 700 "$CERT_DIR"
  S install -m 0644 "$CERT_FULLCHAIN" "$CERT_FILE"; S install -m 0600 "$CERT_KEY" "$KEY_FILE"; ok "manual certificate installed in $CERT_DIR"
fi
apply_nginx "$FIRST_MODE"
tok="kt-selftest-$TS"; echo "$tok" | S tee "$WEBROOT/.well-known/acme-challenge/$tok" >/dev/null
for n in "${NAMES[@]}"; do
  got=$("${CURL[@]}" "http://$n/.well-known/acme-challenge/$tok" 2>/dev/null || true)
  [ "$got" = "$tok" ] || { S rm -f "$WEBROOT/.well-known/acme-challenge/$tok"; die "ACME webroot not served for http://$n (got '${got:0:80}')"; }
done
pubgot=$(curl -sS -m 10 "http://$DOMAIN/.well-known/acme-challenge/$tok" 2>/dev/null || true)
S rm -f "$WEBROOT/.well-known/acme-challenge/$tok"
[ "$pubgot" = "$tok" ] && ok "ACME webroot served (local + via public IP)" || warn "ACME webroot not reachable via the public IP from inside (hairpin); Let's Encrypt validates from outside"
c=$("${CURL[@]}" -o /dev/null -w '%{http_code}' "http://$DOMAIN/" || true); [ "$c" = 200 ] || [ "$FIRST_MODE" = final ] || die "site over HTTP returns $c after nginx switch"

# ================================================================ 4 certificate
say "== 4/9 certificate"
if [ "$CERT_MODE" = manual ]; then ok "manual certificate (renew it yourself): $(S openssl x509 -in "$CERT_FILE" -noout -enddate)"
elif [ "$CERT_VALID" = 1 ]; then ok "reusing valid certificate"
else
  dargs=(); for n in "${NAMES[@]}"; do dargs+=(-d "$n"); done
  if [ -n "$CERTBOT_EMAIL" ]; then acct=(-m "$CERTBOT_EMAIL"); else acct=(--register-unsafely-without-email); fi
  CB=(certbot certonly --webroot -w "$WEBROOT" --cert-name "$DOMAIN" "${dargs[@]}" --agree-tos -n "${acct[@]}" --keep-until-expiring --expand)
  say "  certbot dry-run (staging, no rate limit)…"
  if ! S "${CB[@]}" --dry-run >"$WORK/cb-dry.log" 2>&1; then
    tail -15 "$WORK/cb-dry.log"
    S rm -f "$TARGET" ${LINK:+"$LINK"}; restore_disabled; S nginx -t >/dev/null 2>&1 && S systemctl reload nginx
    print_fallbacks
    die "Let's Encrypt validation failed (dry-run). Original nginx config restored; .env untouched"
  fi
  S "${CB[@]}" --deploy-hook "systemctl reload nginx" >"$WORK/cb.log" 2>&1 || { tail -15 "$WORK/cb.log"; die "certbot issuance failed after a successful dry-run"; }
  ok "certificate issued: $(S openssl x509 -in "$CERT_FILE" -noout -enddate)"
fi

# ================================================================ 5 nginx TLS (no redirect yet) + reachability
say "== 5/9 TLS on 443"
[ "$FIRST_MODE" = final ] || apply_nginx tls
c=$("${CURL[@]}" -o /dev/null -w '%{http_code}' "https://$DOMAIN/" || true); [ "$c" = 200 ] || die "https://$DOMAIN/ (local) returns $c"
ok "https://$DOMAIN/ answers 200 locally (certificate verified by curl)"
c=$(curl -sS -m 10 -o /dev/null -w '%{http_code}' "https://$DOMAIN/" 2>/dev/null || true)
if [ "$c" = 200 ]; then ok "https://$DOMAIN/ reachable via public IP $EXPECTED_IP"
elif [ "$ASSUME_443_OPEN" = 1 ]; then warn "443 not reachable from inside via public IP (code $c); continuing because ASSUME_443_OPEN=1"
else
  say ""; say "STOP before the redirect: this server cannot reach https://$DOMAIN via its public IP (code $c)."
  say "HTTPS is live alongside HTTP; nothing user-facing changed. Check from the Mac:  curl -sI https://$DOMAIN/"
  say "If that shows HTTP/2 200 (only hairpin is blocked), rerun with:  ssh karen@$EXPECTED_IP 'ASSUME_443_OPEN=1 bash -s' < ~/Downloads/karenseir-https.sh"
  say "If it times out, open TCP 443 in the ArvanCloud panel (security group / firewall) and rerun."
  exit 4
fi

# ================================================================ 6 .env + rebuild web + restart api/web
say "== 6/9 .env + web rebuild"
cur_cors=$(envget CORS_ORIGINS); new_cors="https://$DOMAIN"; [ "$WITH_WWW" = 1 ] && new_cors="$new_cors,https://$WWW"
IFS=',' read -ra _o <<<"$cur_cors"; for o in "${_o[@]}"; do o=${o// /}; case "$o" in https://*) [[ ",$new_cors," == *",$o,"* ]] || new_cors="$new_cors,$o";; esac; done
envset CORS_ORIGINS "$new_cors"
envset NEXT_PUBLIC_SITE_URL "https://$DOMAIN"
envset ALLOW_HTTP_PREVIEW 0
envset ALLOW_HTTP_ORIGIN_PREVIEW 0
pw=$(envget PUBLIC_WEB_URL); [ -n "$pw" ] && [ "$pw" != "https://$DOMAIN" ] && envset PUBLIC_WEB_URL "https://$DOMAIN"
api_url=$(envget NEXT_PUBLIC_API_URL)
case "$api_url" in
  http://"$EXPECTED_IP"/*|http://"$DOMAIN"/*)
    path="/${api_url#http://*/}"; path=${path%/}
    if docker compose exec -T web node -e "fetch('https://$DOMAIN$path/health',{signal:AbortSignal.timeout(8000)}).then(r=>process.exit(r.ok?0:1),()=>process.exit(1))" </dev/null 2>/dev/null; then
      envset NEXT_PUBLIC_API_URL "https://$DOMAIN$path"; ok "NEXT_PUBLIC_API_URL → https://$DOMAIN$path (web container reaches it)"
    else warn "NEXT_PUBLIC_API_URL kept ($api_url): web container cannot reach https://$DOMAIN$path; the IP keeps serving $API_LOC over HTTP for server-side calls"; fi;;
  *) ok "NEXT_PUBLIC_API_URL unchanged ($api_url)";;
esac
ENV_KEYS="CORS_ORIGINS NEXT_PUBLIC_SITE_URL NEXT_PUBLIC_API_URL PUBLIC_WEB_URL ALLOW_HTTP_PREVIEW ALLOW_HTTP_ORIGIN_PREVIEW"
if cmp -s .env "$BK/env.bak"; then ENV_CHANGED=0; ok ".env already up to date"
else
  ENV_CHANGED=1; echo "ENV_CHANGED=1" >>"$BK/STATE"
  for k in $ENV_KEYS; do o=$(cd "$BK" && awk -F= -v k="$k" '$1==k{print substr($0,index($0,"=")+1); exit}' env.bak); n=$(envget "$k"); [ "$o" = "$n" ] || ok ".env $k: '$o' → '$n'"; done
fi
docker compose config --format json </dev/null >"$WORK/cc.json"; python3 - "$WORK/cc.json" "$DOMAIN" "$new_cors" >"$WORK/ccchk" <<'PY' || { cat "$WORK/ccchk"; cp -p "$BK/env.bak" .env; die "compose does not pick up the new values (.env restored)"; }
import json, sys
c = json.load(open(sys.argv[1])); s = c["services"]; dom, cors = sys.argv[2], sys.argv[3]
def kv(x):
    if isinstance(x, list): return dict((i.split("=", 1) + [""])[:2] for i in x)
    return {k: ("" if v is None else str(v)) for k, v in (x or {}).items()}
b = s["web"].get("build") or {}; args = kv(b.get("args") if isinstance(b, dict) else {}); env = kv(s["api"].get("environment"))
bad = []
if args.get("NEXT_PUBLIC_SITE_URL") != "https://" + dom: bad.append("web arg NEXT_PUBLIC_SITE_URL=" + str(args.get("NEXT_PUBLIC_SITE_URL")))
if args.get("ALLOW_HTTP_PREVIEW", "") == "1": bad.append("web arg ALLOW_HTTP_PREVIEW=1")
if env.get("CORS_ORIGINS") != cors: bad.append("api CORS_ORIGINS=" + str(env.get("CORS_ORIGINS")))
if env.get("ALLOW_HTTP_ORIGIN_PREVIEW", "") == "1": bad.append("api ALLOW_HTTP_ORIGIN_PREVIEW=1 (hard-coded in compose?)")
print("\n".join(bad)); sys.exit(1 if bad else 0)
PY
ok "compose resolves the new values"
live_ok=0
if [ "$ENV_CHANGED" = 0 ]; then
  "${CURL[@]}" -o "$WORK/sm0" "https://$DOMAIN/sitemap.xml" 2>/dev/null || true; "${CURL[@]}" -o /dev/null -D "$WORK/h0" "https://$DOMAIN/" 2>/dev/null || true
  grep "<loc>https://$DOMAIN" "$WORK/sm0" >/dev/null 2>&1 && grep -i 'upgrade-insecure-requests' "$WORK/h0" >/dev/null 2>&1 && live_ok=1
fi
if [ "$live_ok" = 1 ]; then ok "running web already built with HTTPS settings — rebuild skipped"
else
  say "  building web (a few minutes, log /tmp/karenseir-https-build.log)…"
  docker compose build web </dev/null >/tmp/karenseir-https-build.log 2>&1 || { tail -30 /tmp/karenseir-https-build.log; die "web build failed (running containers untouched)"; }
fi
docker compose up -d api web </dev/null >"$WORK/up.log" 2>&1 || { cat "$WORK/up.log"; die "docker compose up -d api web failed"; }
for i in $(seq 1 40); do
  docker compose exec -T api python -c "import urllib.request;urllib.request.urlopen('http://127.0.0.1:8000/health',timeout=3)" </dev/null >/dev/null 2>&1 && break
  [ "$i" = 40 ] && { docker compose logs --tail 40 api </dev/null; die "api not healthy after restart (CORS/production config check?)"; }
  sleep 5
done; ok "api healthy"
for i in $(seq 1 30); do c=$(curl -s -o /dev/null -m 5 -w '%{http_code}' "${NG[WEB_HEALTH]}" || true); [ "$c" = 200 ] && break; [ "$i" = 30 ] && die "web not answering after restart ($c)"; sleep 4; done; ok "web answering"

# ================================================================ 7 nginx final: redirect + HTTP/2 + HSTS
say "== 7/9 nginx final (HTTP→HTTPS, HSTS max-age=$HSTS_MAX_AGE)"
apply_nginx final

# ================================================================ 8 renewal
say "== 8/9 renewal"
if [ "$CERT_MODE" = letsencrypt ]; then
  if S certbot renew --dry-run --cert-name "$DOMAIN" >"$WORK/renew.log" 2>&1; then ok "certbot renew --dry-run passed"; else tail -8 "$WORK/renew.log"; warn "certbot renew --dry-run failed (certificate valid until $(S openssl x509 -in "$CERT_FILE" -noout -enddate | cut -d= -f2))"; fi
  S grep -q 'reload nginx' "/etc/letsencrypt/renewal/$DOMAIN.conf" 2>/dev/null && ok "renewal reloads nginx (deploy hook)" || { printf '#!/bin/sh\nsystemctl reload nginx\n' >"$WORK/hook"; S install -m 0755 -D "$WORK/hook" /etc/letsencrypt/renewal-hooks/deploy/reload-nginx.sh; ok "added deploy hook reload-nginx.sh"; }
  if systemctl is-active --quiet certbot.timer || systemctl is-active --quiet snap.certbot.renew.timer || [ -f /etc/cron.d/certbot ]; then ok "automatic renewal scheduled"; else warn "no certbot timer/cron found — renewal is not automatic"; fi
else warn "manual certificate: no automatic renewal; expires $(S openssl x509 -in "$CERT_FILE" -noout -enddate | cut -d= -f2)"; fi

# ================================================================ 9 verification
say "== 9/9 verification"
FAILS=()
c=$("${CURL[@]}" -o /dev/null -w '%{http_code} %{http_version}' "https://$DOMAIN/" || true); [ "$c" = "200 2" ] && ok "https://$DOMAIN/ 200 over HTTP/2" || fail "home: '$c' (want '200 2')"
c=$("${CURL[@]}" -o /dev/null -w '%{http_code} %{redirect_url}' "http://$DOMAIN/tours?x=1" || true); [ "$c" = "301 https://$DOMAIN/tours?x=1" ] && ok "http → https redirect keeps path/query" || fail "http redirect: '$c'"
c=$(curl -sS -m 10 -o /dev/null -H "Host: $EXPECTED_IP" -w '%{http_code} %{redirect_url}' "http://127.0.0.1/" || true); [ "$c" = "301 https://$DOMAIN/" ] && ok "http://$EXPECTED_IP → https://$DOMAIN" || fail "IP redirect: '$c'"
if [ "$WITH_WWW" = 1 ]; then c=$("${CURL[@]}" -o /dev/null -w '%{http_code} %{redirect_url}' "https://$WWW/" || true); [ "$c" = "301 https://$DOMAIN/" ] && ok "https://$WWW → apex" || fail "www redirect: '$c'"; fi
c=$("${CURL[@]}" -o "$WORK/health" -w '%{http_code}' "https://$DOMAIN/api/health" || true); [ "$c" = 200 ] && ok "/api/health 200 $(head -c 80 "$WORK/health")" || fail "/api/health → $c"
c=$("${CURL[@]}" -o /dev/null -D - -H "Origin: https://$DOMAIN" "https://$DOMAIN/api/health" | tr -d '\r' | awk -F': ' 'tolower($1)=="access-control-allow-origin"{print $2}' || true); [ "$c" = "https://$DOMAIN" ] && ok "CORS allows https://$DOMAIN" || fail "CORS allow-origin for https://$DOMAIN: '$c'"
"${CURL[@]}" "https://$DOMAIN/sitemap.xml" >"$WORK/sitemap" || true
n_https=$({ grep -o "<loc>https://$DOMAIN" "$WORK/sitemap" || true; } | wc -l); n_ip=$(grep -c "$EXPECTED_IP" "$WORK/sitemap" || true)
[ "$n_https" -gt 0 ] && [ "$n_ip" = 0 ] && ok "sitemap: $n_https URLs on https://$DOMAIN, none on the IP" || fail "sitemap: https URLs=$n_https, IP mentions=$n_ip"
"${CURL[@]}" -o "$WORK/robots" "https://$DOMAIN/robots.txt" || true
grep -i "^sitemap: https://$DOMAIN/sitemap.xml" "$WORK/robots" >/dev/null && ok "robots.txt sitemap on https://$DOMAIN" || fail "robots.txt sitemap line not on https://$DOMAIN"
"${CURL[@]}" -o "$WORK/home" "https://$DOMAIN/" || true
if grep -F "$EXPECTED_IP" "$WORK/home" >/dev/null; then fail "home page HTML still contains $EXPECTED_IP (canonical/og)"; else ok "home page HTML has no IP references"; fi
hdr_check() { # $1 path  $2.. header:1 (exactly once) | header:max1 (at most once)
  local p=$1 spec h want n; shift; "${CURL[@]}" -o /dev/null -D "$WORK/h" "https://$DOMAIN$p" >/dev/null || true
  for spec in "$@"; do h=${spec%%:*}; want=${spec#*:}; n=$(grep -ci "^$h:" "$WORK/h" || true)
    if [ "$want" = 1 ] && [ "$n" != 1 ]; then fail "$p: $h sent $n times (want 1)"; elif [ "$want" = max1 ] && [ "$n" -gt 1 ]; then fail "$p: $h sent $n times"; fi; done
}
hdr_check / strict-transport-security:1 x-content-type-options:1 content-security-policy:1 x-frame-options:max1 referrer-policy:max1 permissions-policy:max1
grep -i '^strict-transport-security:' "$WORK/h" | grep -q "max-age=$HSTS_MAX_AGE" || fail "HSTS max-age is not $HSTS_MAX_AGE"
grep -i '^content-security-policy:' "$WORK/h" | grep -q 'upgrade-insecure-requests' || fail "CSP lacks upgrade-insecure-requests (web still built with ALLOW_HTTP_PREVIEW=1?)"
hdr_check /api/health strict-transport-security:1 x-content-type-options:1 x-frame-options:max1 referrer-policy:max1 permissions-policy:max1
[ ${#FAILS[@]} -eq 0 ] && ok "security headers: exactly one of each (HSTS from nginx, the rest from the app)"
cert=$(echo | openssl s_client -connect 127.0.0.1:443 -servername "$DOMAIN" 2>/dev/null | openssl x509 -noout -issuer -enddate 2>/dev/null | tr '\n' ' ' || true)
say "       certificate: $cert"
echo "RESULT_FAILS=${#FAILS[@]}" >>"$BK/STATE"

say ""
if [ ${#FAILS[@]} -gt 0 ]; then
  say "HTTPS-FAILED: ${#FAILS[@]} check(s) failed:"; for f in "${FAILS[@]}"; do say "  - $f"; done
  say "HTTPS itself is live. Backups: $BK"; say "Rollback: $ROLLBACK_CMD"; exit 1
fi
for w in "${WARNS[@]}"; do say "WARN: $w"; done
cat <<EOF
Next:
  - check from the Mac:  curl -sI https://$DOMAIN/ | head -5   and open https://$DOMAIN in a browser
  - after ~1 week without problems raise HSTS (nothing else changes):
      ssh karen@$EXPECTED_IP 'HSTS_MAX_AGE=31536000 bash -s' < ~/Downloads/karenseir-https.sh
  - future releases keep the HTTPS values: they live in $APP_DIR/.env
HTTPS-OK https://$DOMAIN hsts=$HSTS_MAX_AGE backup=$BK $(date -u +%FT%TZ)
EOF
