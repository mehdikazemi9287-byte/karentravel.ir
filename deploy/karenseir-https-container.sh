#!/usr/bin/env bash
# KarenSeir — enable HTTPS for karentravel.ir on the CURRENT production layout (nginx in a container):
#   /opt/karenseir                 compose project (server-owned docker-compose.yml + override, .env, backup.sh)
#   /opt/karenseir/nginx/default.conf   single-file bind mount → /etc/nginx/conf.d/default.conf:ro in service "nginx"
#   /opt/karenseir/certs           → nginx /etc/nginx/certs:ro  and  certbot /etc/letsencrypt   (root-owned)
#   volume certbot-www             → nginx + certbot /var/www/certbot  (ACME webroot)
#   service certbot (profile ssl)  certbot/certbot image, only run on demand
# (deploy/karenseir-https.sh is the older variant for HOST nginx; it refuses this server.)
#
# From the Mac:
#   preflight, changes nothing:  ssh karen@188.121.123.218 'bash -s -- --check' < ~/Downloads/karenseir-https-container.sh
#   apply:                       ssh karen@188.121.123.218 'bash -s' < ~/Downloads/karenseir-https-container.sh
#   rollback:                    ssh karen@188.121.123.218 'bash -s' < ~/Downloads/karenseir-https-container-rollback.sh
# Options (environment, before bash:  ssh ... 'HSTS_MAX_AGE=31536000 bash -s' < ...):
#   HSTS_MAX_AGE=300   start short; rerun later with 31536000 (a rerun only regenerates nginx + reuses the certificate)
#   WITH_WWW=auto      auto = include www.karentravel.ir only if its A record points to this server; 1 = require; 0 = apex only
#   EMAIL=             Let's Encrypt account e-mail (optional; otherwise --register-unsafely-without-email)
#   CERT_FULLCHAIN= CERT_KEY=   purchased certificate files on the server (no Let's Encrypt, no auto-renewal)
#   ASSUME_443_OPEN=0  1 = continue although this server cannot reach its own public IP on 443 (hairpin; check from the Mac first)
#
# Stages: 0 preflight (read-only) → 1 backup + web image tag → 2 certificate (ACME self-test, dry-run, issue) →
#   A nginx: 443 server (copy of the port-80 server) next to unchanged HTTP → B .env/compose + web rebuild + restart →
#   C nginx: HTTP→HTTPS redirect, www→apex → renewal cron → verification → HTTPS-OK
# Any failure after the first change and before stage C is verified restores default.conf (in place), .env, the compose
# overlay and the previous web image (AUTO-RESTORE-OK). Certificates already obtained stay (harmless).
# Exit codes: 1 failure, 2 preflight abort, 3 Let's Encrypt/certbot unavailable (fallbacks printed), 4 HTTPS not reachable.
#
# The whole body is functions; only the last line runs main, so with 'bash -s' bash has read everything first.
set -Eeuo pipefail

usage() { sed -n '2,24p' "${BASH_SOURCE[0]}" 2>/dev/null || true; }

config() {
  DOMAIN=${DOMAIN:-karentravel.ir}
  WWW=www.$DOMAIN
  EXPECTED_IP=${EXPECTED_IP:-188.121.123.218}
  ROOT=${ROOT:-/opt/karenseir}
  CONF=$ROOT/nginx/default.conf
  PRE=$ROOT/nginx/default.conf.pre-https     # not mounted into the container (only default.conf is)
  OVERLAY=docker-compose.https.yml
  HSTS_MAX_AGE=${HSTS_MAX_AGE:-300}
  WITH_WWW=${WITH_WWW:-auto}
  EMAIL=${EMAIL:-}
  CERT_FULLCHAIN=${CERT_FULLCHAIN:-}
  CERT_KEY=${CERT_KEY:-}
  ASSUME_443_OPEN=${ASSUME_443_OPEN:-0}
  PULL_TIMEOUT=${PULL_TIMEOUT:-180}
  KT_SLEEP=${KT_SLEEP:-5}
  TS=$(date -u +%Y%m%d-%H%M%S)
  BK=$ROOT/backups/https-$TS
  CHECK_ONLY=0
  for a in "$@"; do case "$a" in --check) CHECK_ONLY=1;; -h|--help) usage; exit 0;; *) echo "unknown argument: $a"; exit 2;; esac; done
  ROLLBACK_CMD="ssh karen@$EXPECTED_IP 'bash -s' < ~/Downloads/karenseir-https-container-rollback.sh"
  CRON_MARK="# karenseir-https-container: certbot renew"
  CHANGED=0 AUTO_RESTORE=1 NGINX_TOUCHED=0 IMG_TOUCHED=0 UP_TOUCHED=0
  WEB_REF="" WEB_PRE_TAG="" WORK="" LOCK="" LOCK_HELD=0
  FAILS=() WARNS=()
}

say()  { printf '%s\n' "$*"; }
ok()   { printf '  ok   %s\n' "$*"; }
warn() { printf '  WARN %s\n' "$*"; WARNS+=("$*"); }
fail() { printf '  FAIL %s\n' "$*"; FAILS+=("$*"); }
die()  { printf '\nHTTPS-FAILED: %s\n' "$*" >&2; exit 1; }
die_rc() { local rc=$1; shift; printf '\nHTTPS-FAILED: %s\n' "$*" >&2; exit "$rc"; }
dc()   { docker compose "$@" </dev/null; }

# ---------------------------------------------------------------- error handling / auto-restore
on_err() {
  local rc=$1 line=$2
  [ "$BASHPID" = "$$" ] || exit "$rc"
  printf '\nHTTPS-FAILED at line %s (exit %s)\n' "$line" "$rc" >&2
  exit "$rc"
}
on_exit() {
  local rc=$?
  [ "$BASHPID" = "$$" ] || return 0
  set +e; trap - ERR
  if [ "$rc" != 0 ] && [ "$CHANGED" = 1 ]; then
    if [ "$AUTO_RESTORE" = 1 ]; then auto_restore
    else printf '\nHTTPS stays live (redirect + HSTS were already active; not auto-restored).\nBackup: %s\nRollback: %s\n' "$BK" "$ROLLBACK_CMD" >&2; fi
  elif [ "$rc" != 0 ]; then printf 'Nothing was changed on the server.\n' >&2; fi
  [ -z "$WORK" ] || rm -rf "$WORK"
  [ "$LOCK_HELD" != 1 ] || rm -rf "$LOCK"
}
restore_file() { # $1 backup copy  $2 live file — in place (keeps the inode; required for the single-file bind mount)
  [ -f "$1" ] || return 0
  cmp -s "$1" "$2" && return 0
  cat "$1" >"$2"
}
auto_restore() {
  local st=0
  printf '\n-- auto-restore from %s\n' "$BK" >&2
  if [ "$NGINX_TOUCHED" = 1 ]; then
    if restore_file "$BK/default.conf" "$CONF" && dc exec -T nginx nginx -t >/dev/null 2>&1 && dc exec -T nginx nginx -s reload >/dev/null 2>&1
    then printf '   default.conf restored in place, nginx -t ok, reloaded\n' >&2
    else st=1; printf '   default.conf could NOT be restored/reloaded (copy: %s/default.conf)\n' "$BK" >&2; fi
  fi
  cmp -s "$BK/env" .env || printf '   .env restored\n' >&2
  if ! restore_file "$BK/env" .env; then st=1; printf '   .env could NOT be restored (copy: %s/env)\n' "$BK" >&2; fi
  for f in docker-compose.yml docker-compose.override.yml; do restore_file "$BK/$f" "$f" || { st=1; printf '   %s could NOT be restored\n' "$f" >&2; }; done
  if [ -z "$PRIOR_MANAGED" ] && [ -f "$PRE" ]; then mv "$PRE" "$BK/default.conf.pre-https.failed-run" || st=1; fi
  if [ -f "$BK/$OVERLAY" ]; then restore_file "$BK/$OVERLAY" "$OVERLAY" || st=1
  elif [ -f "$OVERLAY" ]; then mv "$OVERLAY" "$BK/$OVERLAY.failed-run" || st=1; fi
  if [ "$IMG_TOUCHED" = 1 ] || [ "$UP_TOUCHED" = 1 ]; then
    if [ -n "$WEB_PRE_TAG" ] && docker tag "$WEB_PRE_TAG" "$WEB_REF" >/dev/null 2>&1; then printf '   web image %s ← %s\n' "$WEB_REF" "$WEB_PRE_TAG" >&2
    else st=1; printf '   previous web image unknown — web keeps the new build\n' >&2; fi
  fi
  if [ "$UP_TOUCHED" = 1 ]; then
    # shellcheck disable=SC2086
    if dc up -d --no-build --no-deps $APP_SERVICES >/dev/null 2>&1; then printf '   %s restarted with the previous .env/image\n' "$APP_SERVICES" >&2
    else st=1; printf '   docker compose up -d --no-build %s failed\n' "$APP_SERVICES" >&2; fi
  fi
  local i c=""
  for i in 1 2 3 4 5 6 7 8 9 10 11 12; do
    req "http://$DOMAIN/"; c=$RC; [ "$c" = 200 ] && break; sleep "$KT_SLEEP"
  done
  [ "$c" = 200 ] || { st=1; printf '   http://%s/ answers %s after restore\n' "$DOMAIN" "$c" >&2; }
  if [ "$st" = 0 ]; then printf 'AUTO-RESTORE-OK: back to the state before this run (backup kept: %s)\n' "$BK" >&2
  else printf 'AUTO-RESTORE-INCOMPLETE: run the rollback: %s\n' "$ROLLBACK_CMD" >&2; fi
}
lock_acquire() { # mkdir is atomic; per-user lock (this script never needs sudo)
  LOCK="$HOME/.karenseir-https-container.lock"
  local old
  if ! mkdir -m 0700 "$LOCK" 2>/dev/null; then
    old=$(cat "$LOCK/pid" 2>/dev/null || true)
    if [ -n "$old" ] && ps -p "$old" >/dev/null 2>&1; then echo "another run is active (pid $old, lock $LOCK)"; exit 1; fi
    rm -rf "$LOCK"; mkdir -m 0700 "$LOCK" 2>/dev/null || { echo "cannot take lock $LOCK"; exit 1; }
  fi
  LOCK_HELD=1; echo "$$" >"$LOCK/pid"
}

# ---------------------------------------------------------------- small helpers
envget() { # FILE KEY → value without surrounding quotes
  awk -F= -v k="$2" '$1==k{v=substr($0,index($0,"=")+1); gsub(/^["'\'']|["'\'']$/,"",v); print v; exit}' "$1"
}
envhas() { grep -q "^$2=" "$1"; }
envset() { # FILE KEY VALUE — replace the first, drop duplicates, append if absent; written in place
  awk -F= -v k="$2" -v v="$3" 'BEGIN{d=0} $1==k{ if(!d){print k"="v; d=1}; next } {print} END{ if(!d) print k"="v }' "$1" >"$1.tmp.$$"
  cat "$1.tmp.$$" >"$1"; rm -f "$1.tmp.$$"
}
# req [-p] URL [curl args] — -p: no --resolve (public DNS / explicit host). Sets RC RV RL; body $WORK/b, headers $WORK/h
req() {
  local pub=0 url out res=()
  [ "$1" = -p ] && { pub=1; shift; }
  url=$1; shift
  [ "$pub" = 1 ] || res=(--resolve "$DOMAIN:80:127.0.0.1" --resolve "$DOMAIN:443:127.0.0.1" --resolve "$WWW:80:127.0.0.1" --resolve "$WWW:443:127.0.0.1")
  : >"$WORK/b"; : >"$WORK/h"
  out=$(curl -sS -m 20 "${res[@]}" "$@" -o "$WORK/b" -D "$WORK/h" -w '%{http_code} %{http_version} %{redirect_url}' "$url" 2>/dev/null) || true
  RC=000 RV=0 RL=""
  read -r RC RV RL <<<"$out" || true
  RC=${RC:-000}
}
hcount() { grep -ci "^$1:" "$WORK/h" || true; }
a_records() { getent ahostsv4 "$1" 2>/dev/null | awk '{print $1}' | sort -u | tr '\n' ' ' | sed 's/ $//' || true; }
aaaa_records() { getent ahostsv6 "$1" 2>/dev/null | awk '$1 !~ /^::ffff:/{print $1}' | sort -u | tr '\n' ' ' | sed 's/ $//' || true; }
# helper containers use the image of the running nginx (alpine, root, already on the server → no pull)
helper() { docker run --rm --network none "$@"; }
cert_pem() { helper -v "$ROOT/certs:/kt-c:ro" --entrypoint cat "$NGINX_IMG" "/kt-c/$1" 2>/dev/null; }
certbot_run() { dc --profile ssl run --rm --no-deps -T --entrypoint certbot certbot "$@"; }

print_fallbacks() {
  local vol_path
  vol_path=$(docker volume inspect -f '{{.Mountpoint}}' "${WEBROOT_VOL:-certbot-www}" 2>/dev/null || echo "<docker volume inspect -f '{{.Mountpoint}}' ${WEBROOT_VOL:-<project>_certbot-www}>")
  cat <<EOF

Let's Encrypt via the certbot container is not possible right now. Nothing user-facing was changed. Options:
  1) Purchased certificate (Talahost or any CA; DV for $DOMAIN${INCLUDE_WWW:+ + $WWW}): copy fullchain + key to the server, rerun:
       ssh karen@$EXPECTED_IP 'CERT_FULLCHAIN=/home/karen/ssl/fullchain.pem CERT_KEY=/home/karen/ssl/privkey.pem bash -s' < ~/Downloads/karenseir-https-container.sh
  2) certbot on the host (apt, or pip through the same mirror the builds use), writing into the SAME directories the
     containers use, then rerun this script (it finds the valid certificate and skips issuance):
       sudo apt-get install -y certbot      # or: sudo pip install certbot -i <mirror>
       sudo certbot certonly --webroot -w $vol_path --config-dir $ROOT/certs \\
            --cert-name $DOMAIN -d $DOMAIN${INCLUDE_WWW:+ -d $WWW} --agree-tos -n --register-unsafely-without-email
     Renewal then needs a host cron with the same --config-dir (the container cron this script installs needs the image).
  3) Load the certbot image from another machine:  docker save certbot/certbot | ssh karen@$EXPECTED_IP docker load
  4) Only outbound HTTPS blocked: rerun with a proxy:  ssh ... 'HTTPS_PROXY=http://<proxy>:<port> bash -s' < ...
EOF
}

# ---------------------------------------------------------------- nginx config parser / generator (python3, stdlib only)
write_py() {
cat >"$WORK/ngx.py" <<'PY'
import json, re, sys
SEC = [("X-Content-Type-Options", "nosniff"), ("X-Frame-Options", "DENY"),
       ("Referrer-Policy", "strict-origin-when-cross-origin"),
       ("Permissions-Policy", '"camera=(), microphone=(self), geolocation=(self)"')]
HIDE = [h for h, _ in SEC] + ["Strict-Transport-Security"]
MARK = "# managed-by: karenseir-https-container.sh"

def tokenize(s):
    toks, i, n = [], 0, len(s)
    while i < n:
        c = s[i]
        if c.isspace(): i += 1; continue
        if c == "#":
            j = s.find("\n", i); i = n if j < 0 else j; continue
        if c in "{};": toks.append((c, i, i + 1)); i += 1; continue
        j = i
        while j < n and not s[j].isspace() and s[j] not in "{};":
            if s[j] in "\"'":
                q = s[j]; j += 1
                while j < n and s[j] != q:
                    j += 2 if s[j] == "\\" else 1
                j += 1
            elif s[j] == "\\": j += 2
            else: j += 1
        toks.append(("w", i, j)); i = j
    return toks

def parse(s):
    root = {"name": "", "raw": [], "args": [], "children": [], "start": 0, "open": None, "end": len(s)}
    stack, cur = [root], []
    for t, a, b in tokenize(s):
        if t == "w": cur.append((s[a:b], a, b))
        elif t == ";":
            if cur:
                stack[-1]["children"].append({"name": cur[0][0], "raw": [w[0] for w in cur], "args": [w[0].strip("\"'") for w in cur[1:]],
                                              "start": cur[0][1], "end": b, "open": None, "children": []})
            cur = []
        elif t == "{":
            node = {"name": cur[0][0] if cur else "", "raw": [w[0] for w in cur], "args": [w[0].strip("\"'") for w in cur[1:]],
                    "start": cur[0][1] if cur else a, "open": a, "end": None, "children": []}
            stack[-1]["children"].append(node); stack.append(node); cur = []
        else:
            if len(stack) == 1: sys.exit("PARSE: unbalanced '}' at offset %d" % a)
            stack[-1]["end"] = b; stack.pop(); cur = []
    if len(stack) != 1 or cur: sys.exit("PARSE: unbalanced braces / missing ';'")
    return root

def blocks(n):
    for c in n["children"]:
        if c["open"] is not None:
            yield c; yield from blocks(c)
def direct(n, name): return [c for c in n["children"] if c["open"] is None and c["name"] == name]
def port(listen, p):
    return bool(listen["args"]) and re.fullmatch(r"(?:\[[0-9a-fA-F:]*\]:|(?:\d+\.){3}\d+:|\*:)?" + p, listen["args"][0]) is not None
def servers(root): return [c for c in root["children"] if c["name"] == "server" and c["open"] is not None]
def is_acme(c): return c["name"] == "location" and any("/.well-known/acme-challenge" in a for a in c["args"])
def line_span(s, a, b):
    ls = s.rfind("\n", 0, a) + 1
    a2 = ls if s[ls:a].strip() == "" else a
    le = s.find("\n", b); le = len(s) if le < 0 else le
    b2 = min(le + 1, len(s)) if s[b:le].strip() == "" else b
    return a2, b2
def indent_of(s, node):
    ls = s.rfind("\n", 0, node["start"]) + 1
    return re.match(r"[ \t]*", s[ls:node["start"]]).group(0)

def base_server(s, root):
    s80 = [S for S in servers(root) if any(port(l, "80") for l in direct(S, "listen"))]
    s443 = [S for S in servers(root) if any(port(l, "443") for l in direct(S, "listen"))]
    return s80, s443

def inspect(path):
    s = open(path, encoding="utf-8").read(); root = parse(s)
    s80, s443 = base_server(s, root)
    first = s.split("\n", 1)[0]
    m = re.search(r"mode=(\w+)", first) if first.startswith(MARK) else None
    info = {"servers80": len(s80), "servers443": len(s443), "managed": m.group(1) if m else "",
            "upstreams": sorted({u["args"][0] for u in root["children"] if u["name"] == "upstream" and u["open"] is not None and u["args"]})}
    if len(s80) == 1:
        S = s80[0]
        info["acme"] = any(is_acme(c) for c in S["children"])
        info["proxy"] = sorted({d["args"][0] for B in [S] + list(blocks(S)) for d in direct(B, "proxy_pass") if d["args"]})
        info["ipv6"] = any(l["args"] and l["args"][0].startswith("[") for l in direct(S, "listen"))
        info["server_name"] = [a for d in direct(S, "server_name") for a in d["args"]]
        info["server_headers"] = sorted({d["args"][0] for d in direct(S, "add_header") if d["args"]})
        info["addheader_blocks"] = sum(1 for B in blocks(S) if direct(B, "add_header"))
        info["return_at_server"] = bool(direct(S, "return"))
    print(json.dumps(info))

def header_values(S):
    vals = dict(SEC)
    for d in direct(S, "add_header"):
        for h, _ in SEC:
            if d["args"] and d["args"][0].lower() == h.lower() and len(d["raw"]) > 2: vals[h] = d["raw"][2]
    return vals

def header_edits(s, S, hsts):
    """nginx is the single source of the security headers: hide upstream copies, add them at server level (always),
    and repeat them in every block that has its own add_header (such a block does not inherit the server ones)."""
    vals, edits = header_values(S), []
    ind = indent_of(s, S["children"][0]) if S["children"] else "    "
    have = {d["args"][0].lower() for d in direct(S, "add_header") if d["args"]}
    lines = ["%s# karenseir-https: nginx is the only source of these headers; upstream copies are hidden" % ind]
    lines += ["%sproxy_hide_header %s;" % (ind, h) for h in HIDE]
    lines += ["%sadd_header %s %s always;" % (ind, h, vals[h]) for h, _ in SEC if h.lower() not in have]
    if hsts is not None: lines.append('%sadd_header Strict-Transport-Security "max-age=%s" always;' % (ind, hsts))
    edits.append((S["open"] + 1, S["open"] + 1, "\n" + "\n".join(lines) + "\n"))
    for B in [S] + list(blocks(S)):
        for d in direct(B, "add_header"):
            if d["args"] and d["args"][0].lower() == "strict-transport-security":
                a, b = line_span(s, d["start"], d["end"]); edits.append((a, b, ""))
    for B in blocks(S):
        ah = [d for d in direct(B, "add_header") if d["args"] and d["args"][0].lower() != "strict-transport-security"]
        hide = direct(B, "proxy_hide_header")
        bi = (indent_of(s, B["children"][0]) if B["children"] else indent_of(s, B) + "    ")
        ins = []
        if ah:
            names = {d["args"][0].lower() for d in ah}
            ins += ["%sadd_header %s %s always;" % (bi, h, vals[h]) for h, _ in SEC if h.lower() not in names]
            if hsts is not None: ins.append('%sadd_header Strict-Transport-Security "max-age=%s" always;' % (bi, hsts))
        if hide:
            hn = {d["args"][0].lower() for d in hide}
            ins += ["%sproxy_hide_header %s;" % (bi, h) for h in HIDE if h.lower() not in hn]
        if ins:
            edits.append((B["open"] + 1, B["open"] + 1, "  # karenseir-https: own add_header here = no inheritance, so repeated\n" + "\n".join(ins) + "\n"))
    return edits

def apply(s, a0, b0, edits):
    out = s[a0:b0]
    for a, b, t in sorted(edits, key=lambda e: (e[0], e[1]), reverse=True):
        out = out[:a - a0] + t + out[b - a0:]
    return out

def ssl_head(ind, names, ipv6, h2, cert, key):
    l = ["server {"]
    if h2 == "on": l += [ind + "listen 443 ssl;"] + ([ind + "listen [::]:443 ssl;"] if ipv6 else []) + [ind + "http2 on;"]
    else: l += [ind + "listen 443 ssl http2;"] + ([ind + "listen [::]:443 ssl http2;"] if ipv6 else [])
    l += [ind + "server_name %s;" % " ".join(names),
          ind + "ssl_certificate %s;" % cert, ind + "ssl_certificate_key %s;" % key,
          ind + "ssl_protocols TLSv1.2 TLSv1.3;", ind + "ssl_prefer_server_ciphers off;",
          ind + "ssl_session_cache shared:KTSSL:10m;", ind + "ssl_session_timeout 1d;", ind + "ssl_session_tickets off;"]
    return "\n".join(l)

def gen(mode, path, out, domain, www, hsts, h2, cert, key):
    s = open(path, encoding="utf-8").read(); root = parse(s)
    if s.startswith(MARK): sys.exit("GEN: base config is already managed; use the pre-https copy")
    s80, s443 = base_server(s, root)
    if len(s80) != 1 or s443: sys.exit("GEN: need exactly one active port-80 server and no active 443 server (found %d/%d)" % (len(s80), len(s443)))
    S = s80[0]
    acme = [c for c in S["children"] if is_acme(c)]
    if not acme: sys.exit("GEN: the port-80 server has no /.well-known/acme-challenge/ location")
    ind = indent_of(s, S["children"][0]) if S["children"] else "    "
    listens = direct(S, "listen"); ipv6 = any(l["args"] and l["args"][0].startswith("[") for l in listens)
    names_tls = [domain] + ([www] if www else [])
    blocks_out = []
    # --- port 80
    if mode == "tls":
        blocks_out.append(s[S["start"]:S["end"]])   # stage A: the HTTP server stays byte-identical
    else:
        vals = header_values(S)
        sn = direct(S, "server_name")
        l = ["server {"] + [ind + s[x["start"]:x["end"]] for x in listens]
        l.append(ind + (s[sn[0]["start"]:sn[0]["end"]] if sn else "server_name _;"))
        l.append(ind + "# karenseir-https: HTTP only answers ACME; everything else (domain, www, IP) → https://%s" % domain)
        l += [ind + "add_header %s %s always;" % (h, vals[h]) for h, _ in SEC]
        l.append(ind + s[acme[0]["start"]:acme[0]["end"]])
        l += [ind + "location / {", ind + "    return 301 https://%s$request_uri;" % domain, ind + "}", "}"]
        blocks_out.append("\n".join(l))
    # --- 443 apex (+www before the redirect stage): exact copy of the port-80 server body
    e443 = header_edits(s, S, hsts)
    for x in listens: e443.append(line_span(s, x["start"], x["end"]) + ("",))
    for x in direct(S, "server_name"): e443.append(line_span(s, x["start"], x["end"]) + ("",))
    body = apply(s, S["open"] + 1, S["end"], e443)
    blocks_out.append("# karenseir-https: HTTPS — same locations as the HTTP server above%s\n" % (" (copied from it)" if mode == "tls" else " had before the redirect")
                      + ssl_head(ind, names_tls if mode == "tls" else [domain], ipv6, h2, cert, key) + body)
    if mode == "final" and www:
        vals = header_values(S)
        l = [ssl_head(ind, [www], ipv6, h2, cert, key)]
        l += [ind + "add_header %s %s always;" % (h, vals[h]) for h, _ in SEC]
        l.append(ind + 'add_header Strict-Transport-Security "max-age=%s" always;' % hsts)
        l += [ind + "return 301 https://%s$request_uri;" % domain, "}"]
        blocks_out.append("\n".join(l))
    head = ("%s mode=%s domain=%s www=%d hsts=%s\n# Generated from default.conf.pre-https (the original). A rerun regenerates this file from that copy,\n"
            "# so make lasting edits there. Rollback: deploy/karenseir-https-container-rollback.sh\n") % (MARK, mode, domain, 1 if www else 0, hsts)
    text = head + s[:S["start"]] + "\n\n".join(blocks_out) + s[S["end"]:]
    parse(text)
    open(out, "w", encoding="utf-8").write(text)

if __name__ == "__main__":
    if sys.argv[1] == "inspect": inspect(sys.argv[2])
    elif sys.argv[1] == "gen":
        a = sys.argv[2:]
        gen(a[0], a[1], a[2], a[3], a[4] if a[4] not in ("", "0") else "", a[5], a[6], a[7], a[8])
PY
cat >"$WORK/plan.py" <<'PY'
# compose plan: which .env keys / overlay entries make the resolved config use the HTTPS values
import json, re, sys
dom, cors, res_p, raw_p, ip, envnew, envlive = sys.argv[1:8]
res = json.load(open(res_p))["services"]; raw = json.load(open(raw_p))["services"]
import os
def readenv(p):
    d = {}
    for l in open(p, encoding="utf-8"):
        m = re.match(r"\s*([A-Za-z_][A-Za-z0-9_]*)=(.*)$", l.rstrip("\n"))
        if m: d.setdefault(m.group(1), m.group(2).strip().strip("\"'"))
    return d
NEW = readenv(envnew); LIVE = os.path.realpath(envlive)
def env_file_keys(svc):
    """keys an env_file: .env (the project .env) gives this service — compose reads the LIVE file, so the planned
    value is taken from the candidate file instead"""
    ef = (raw.get(svc) or {}).get("env_file") or []
    if isinstance(ef, (str, dict)): ef = [ef]
    paths = [os.path.realpath(e["path"] if isinstance(e, dict) else e) for e in ef]
    return LIVE in paths
D = "https://" + dom
WANT = [("web", "args", "NEXT_PUBLIC_API_URL", D + "/api", "set"), ("web", "args", "NEXT_PUBLIC_SITE_URL", D, "set"),
        ("web", "args", "ALLOW_HTTP_PREVIEW", "0", "not1"),
        ("web", "env", "NEXT_PUBLIC_API_URL", D + "/api", "ifpresent"), ("web", "env", "NEXT_PUBLIC_SITE_URL", D, "ifpresent"),
        ("web", "env", "ALLOW_HTTP_PREVIEW", "0", "not1")]
for svc in ("api", "worker"):
    pol = "set" if svc == "api" else "ifpresent"
    WANT += [(svc, "env", "CORS_ORIGINS", cors, pol), (svc, "env", "PUBLIC_WEB_URL", D, pol),
             (svc, "env", "ZARINPAL_CALLBACK_URL", D + "/api/payments/zarinpal/callback", pol),
             (svc, "env", "ALLOW_HTTP_ORIGIN_PREVIEW", "0", "not1"),
             (svc, "env", "PUBLIC_SITE_URL", D, "ifpresent"), (svc, "env", "PUBLIC_ORIGIN", D, "ifpresent")]
def kv(x):
    if isinstance(x, list): return dict((i.split("=", 1) + [None])[:2] for i in x)
    return dict(x or {})
def get(d, svc, sec):
    s = d.get(svc) or {}
    if sec == "args":
        b = s.get("build"); return kv(b.get("args")) if isinstance(b, dict) else {}
    return kv(s.get("environment"))
REF = re.compile(r"^\$\{([A-Za-z_][A-Za-z0-9_]*)(?:(?::?-|:?\?)[^}]*)?\}(.*)$|^\$([A-Za-z_][A-Za-z0-9_]*)(.*)$")
envs, out = {}, []
def ref(svc, sec, key):
    rv = get(raw, svc, sec).get(key); rv = None if rv is None else str(rv)
    return rv, REF.match(rv or "")
def current(svc, sec, key):
    r = get(res, svc, sec)
    if sec == "env" and key not in get(raw, svc, sec) and env_file_keys(svc):
        return (key in NEW), NEW.get(key, "")
    return (key in r), ("" if r.get(key) is None else str(r.get(key)))
for svc, sec, key, val, pol in WANT:   # variables that already feed a correct value are locked to it
    if svc not in res or pol == "not1": continue
    r = get(res, svc, sec)
    if key in r and str(r.get(key)) == val:
        rv, m = ref(svc, sec, key)
        if m:
            var = m.group(1) or m.group(3); suffix = m.group(2) if m.group(1) else m.group(4)
            if "$" not in suffix and val.endswith(suffix): envs.setdefault(var, val[:len(val) - len(suffix)] if suffix else val)
for svc, sec, key, val, pol in WANT:
    if svc not in res: continue
    present, cur = current(svc, sec, key)
    if pol == "ifpresent" and not present: continue
    if sec == "env" and key not in get(raw, svc, sec) and env_file_keys(svc):
        v = "0" if pol == "not1" else val
        if pol == "not1" and cur != "1": continue
        if cur == v: out.append("OK\t%s env %s=%s (env_file .env)" % (svc, key, cur)); continue
        out.append("ENV\t%s\t%s\t(%s env_file .env: '%s')" % (key, v, svc, cur)); envs[key] = v; continue
    if pol == "not1":
        if cur != "1": continue
    elif present and cur == val:
        out.append("OK\t%s %s %s=%s" % (svc, sec, key, cur)); continue
    rv, m = ref(svc, sec, key)
    if m:
        var = m.group(1) or m.group(3); suffix = m.group(2) if m.group(1) else m.group(4)
        if "$" not in suffix and val.endswith(suffix):
            v = val[:len(val) - len(suffix)] if suffix else val
            if envs.get(var, v) != v:
                out.append("BAD\t%s is used for different values (%s / %s): pin via overlay" % (var, envs[var], v))
                out.append("OVL\t%s\t%s\t%s\t%s" % (svc, sec, key, val)); continue
            if var not in envs: out.append("ENV\t%s\t%s\t(%s %s %s: '%s' via ${%s})" % (var, v, svc, sec, key, cur, var))
            envs[var] = v; continue
    out.append("OVL\t%s\t%s\t%s\t%s\t(%s: '%s')" % (svc, sec, key, val, "absent" if rv is None else "literal", cur))
ipkeys = []
for svc in ("web", "api", "worker"):
    for sec in ("args", "env"):
        for k in get(res, svc, sec):
            if ("%s\t%s\t%s\t" % (svc, sec, k)) in "\n".join(o[4:] for o in out if o.startswith("OVL")): continue
            v = current(svc, sec, k)[1]
            if v and ip in str(v): ipkeys.append("%s.%s.%s" % (svc, sec, k))
if ipkeys: out.append("IP\t" + " ".join(sorted(ipkeys)))
print("\n".join(out))
PY
cat >"$WORK/overlay.py" <<'PY'
# write the managed compose overlay (JSON is valid YAML); merges with an existing managed overlay
import json, os, sys
path, lines_p, hosts = sys.argv[1], sys.argv[2], sys.argv[3]
doc = {"services": {}}
if os.path.exists(path):
    body = "".join(l for l in open(path) if not l.lstrip().startswith("#"))
    if body.strip(): doc = json.loads(body)
for line in open(lines_p):
    p = line.rstrip("\n").split("\t")
    if len(p) < 5 or p[0] != "OVL": continue
    _, svc, sec, key, val = p[:5]
    s = doc["services"].setdefault(svc, {})
    if sec == "args": s.setdefault("build", {}).setdefault("args", {})[key] = val
    else: s.setdefault("environment", {})[key] = val
if hosts:
    eh = doc["services"].setdefault("web", {}).setdefault("extra_hosts", [])
    for h in hosts.split(","):
        if h and h + ":host-gateway" not in eh: eh.append(h + ":host-gateway")
with open(path + ".tmp", "w") as f:
    f.write("# managed-by: karenseir-https-container.sh — HTTPS values that the server-owned compose files hard-code.\n")
    f.write("# Loaded through COMPOSE_FILE in .env. Rollback removes it.\n")
    json.dump(doc, f, indent=2); f.write("\n")
os.replace(path + ".tmp", path)
PY
}
ngx_inspect() { python3 "$WORK/ngx.py" inspect "$1"; }
jget() { python3 -c 'import json,sys; v=json.load(open(sys.argv[1]));
for k in sys.argv[2].split("."): v=v.get(k) if isinstance(v,dict) else None
print(v if not isinstance(v,(list,dict,bool)) else json.dumps(v))' "$1" "$2"; }
compose_json() { # ENVFILE OUT [--no-interpolate]
  local envf=$1 out=$2; shift 2
  docker compose --env-file "$envf" --profile ssl config --format json "$@" </dev/null >"$out" 2>"$out.err"   # --profile: include certbot
}
gen_conf() { # MODE OUT
  python3 "$WORK/ngx.py" gen "$1" "$BASE_CONF" "$2" "$DOMAIN" "${INCLUDE_WWW:+$WWW}" "$HSTS_MAX_AGE" "$H2" "$CERT_FILE" "$KEY_FILE"
}
validate_conf() { # FILE — nginx -t in a throwaway container: same image, same network (upstream names resolve), real certs
  docker run --rm --network "$NGX_NET" -v "$1:/etc/nginx/conf.d/default.conf:ro" -v "$ROOT/certs:/etc/nginx/certs:ro" \
    --entrypoint nginx "$NGINX_IMG" -t >"$WORK/vt.log" 2>&1
}
install_conf() { # FILE — validate, write in place (same inode), check the container sees it, nginx -t, reload
  local f=$1 ino0 ino1 h_host h_cont
  validate_conf "$f" || { tail -5 "$WORK/vt.log" >&2; die "generated nginx config fails nginx -t (live config untouched)"; }
  ok "generated config passes nginx -t (throwaway container on $NGX_NET)"
  ino0=$(stat -c %i "$CONF")
  NGINX_TOUCHED=1
  cat "$f" >"$CONF"
  ino1=$(stat -c %i "$CONF")
  [ "$ino0" = "$ino1" ] || die "default.conf inode changed ($ino0 → $ino1); the container would keep the old file"
  h_host=$(md5sum <"$CONF" | cut -d' ' -f1); h_cont=$(dc exec -T nginx cat /etc/nginx/conf.d/default.conf | md5sum | cut -d' ' -f1)
  [ "$h_host" = "$h_cont" ] || die "the nginx container does not see the new default.conf (bind mount stale)"
  dc exec -T nginx nginx -t >"$WORK/nt.log" 2>&1 || { tail -5 "$WORK/nt.log" >&2; die "nginx -t inside the container failed"; }
  dc exec -T nginx nginx -s reload >/dev/null
  sleep 1
  ok "default.conf written in place (inode $ino1), container sees it, reloaded"
}
# web container can fetch https://DOMAIN/api/health (server-side fetches use NEXT_PUBLIC_API_URL)?
web_reaches_https() {
  local js="fetch('https://$DOMAIN/api/health',{signal:AbortSignal.timeout(8000)}).then(r=>process.exit(r.ok?0:1),()=>process.exit(1))"
  if [ "${1:-}" = hostgw ]; then docker run --rm --add-host "$DOMAIN:host-gateway" --entrypoint node "$WEB_IMG_ID" -e "$js" </dev/null >/dev/null 2>&1
  else dc exec -T web node -e "$js" >/dev/null 2>&1; fi
}

# ================================================================ 0 PREFLIGHT (read-only)
preflight() {
  say "== 0 preflight (read-only) $(date -u +%FT%TZ) on $(hostname 2>/dev/null || echo ?) as $(id -un)"
  cd "$ROOT" 2>/dev/null || { echo "ABORT: $ROOT not found"; exit 2; }
  local c
  for c in docker curl python3 getent awk openssl md5sum stat timeout crontab; do command -v "$c" >/dev/null || fail "missing command: $c"; done
  [ ${#FAILS[@]} -eq 0 ] || { say "PREFLIGHT-ABORT"; exit 2; }
  docker info >/dev/null 2>&1 && ok "docker usable by $(id -un) (no sudo needed)" || fail "docker not usable by $(id -un)"
  docker compose version >/dev/null 2>&1 && ok "docker compose $(docker compose version --short 2>/dev/null)" || fail "docker compose missing"
  for c in docker-compose.yml .env "$CONF"; do [ -f "$c" ] && [ -w "$c" ] || fail "$c missing or not writable by $(id -un)"; done
  [ -f docker-compose.override.yml ] && ok "docker-compose.override.yml present" || say "       (no docker-compose.override.yml)"
  mkdir -p "$ROOT/backups" 2>/dev/null && [ -w "$ROOT/backups" ] || fail "$ROOT/backups not writable"
  [ -w "$ROOT" ] || fail "$ROOT not writable by $(id -un) (overlay file)"
  [ -w "$ROOT/nginx" ] || fail "$ROOT/nginx not writable by $(id -un) (default.conf.pre-https copy)"
  case "$HSTS_MAX_AGE" in ''|*[!0-9]*) fail "HSTS_MAX_AGE must be a number";; esac
  case "$WITH_WWW" in auto|0|1) ;; *) fail "WITH_WWW must be auto, 0 or 1";; esac
  [ ${#FAILS[@]} -eq 0 ] || { pf_abort; }

  # -- compose model
  compose_json .env "$WORK/res.json" || { cat "$WORK/res.json.err"; fail "docker compose config failed"; pf_abort; }
  compose_json .env "$WORK/raw.json" --no-interpolate || { cat "$WORK/raw.json.err"; fail "docker compose config --no-interpolate failed"; pf_abort; }
  APP_SERVICES=""
  for c in web api worker; do [ "$(jget "$WORK/res.json" "services.$c")" = None ] || APP_SERVICES="$APP_SERVICES $c"; done
  APP_SERVICES=${APP_SERVICES# }
  [[ " $APP_SERVICES " == *" web "* && " $APP_SERVICES " == *" api "* ]] && ok "app services: $APP_SERVICES" || fail "services web/api not in compose ($APP_SERVICES)"
  CERTBOT_IMAGE=$(jget "$WORK/res.json" services.certbot.image)
  [ "$CERTBOT_IMAGE" != None ] && ok "certbot service (image $CERTBOT_IMAGE, profiles $(jget "$WORK/res.json" services.certbot.profiles))" || fail "no certbot service in compose"
  python3 - "$WORK/res.json" "$ROOT" >"$WORK/cbv" <<'PY' || fail "certbot volumes: $(cat "$WORK/cbv")"
import json, sys
s = json.load(open(sys.argv[1]))["services"]; root = sys.argv[2].rstrip("/")
def vols(n): return {v.get("target"): v for v in s.get(n, {}).get("volumes", []) if isinstance(v, dict)}
cb, ng = vols("certbot"), vols("nginx")
bad = []
le = cb.get("/etc/letsencrypt"); www = cb.get("/var/www/certbot")
if not le or le.get("source", "").rstrip("/") != root + "/certs": bad.append("certbot /etc/letsencrypt is not %s/certs" % root)
if not www: bad.append("certbot has no /var/www/certbot")
nw = ng.get("/var/www/certbot")
if www and nw and www.get("source") != nw.get("source"): bad.append("certbot and nginx use different /var/www/certbot sources")
print("; ".join(bad) or "ok"); sys.exit(1 if bad else 0)
PY
  [ "$(cat "$WORK/cbv")" = ok ] && ok "certbot writes $ROOT/certs + the shared ACME webroot volume"

  # -- nginx container
  NGX_CID=$(dc ps -q nginx 2>/dev/null | head -1 || true)
  if [ -z "$NGX_CID" ] || [ "$(docker inspect -f '{{.State.Running}}' "$NGX_CID" 2>/dev/null)" != true ]; then fail "nginx container not running"; pf_abort; fi
  NGINX_IMG=$(docker inspect -f '{{.Image}}' "$NGX_CID")
  ok "nginx container $(docker inspect -f '{{.Name}}' "$NGX_CID" | tr -d /) running ($(docker inspect -f '{{.Config.Image}}' "$NGX_CID"))"
  local ports; ports=$(docker port "$NGX_CID" 2>/dev/null || true)
  grep -q '^80/tcp -> ' <<<"$ports" && ok "port 80 published" || fail "port 80 not published by nginx"
  grep -q '^443/tcp -> ' <<<"$ports" && ok "port 443 published" || fail "port 443 not published by nginx (add \"443:443\" to compose)"
  local mounts; mounts=$(docker inspect -f '{{range .Mounts}}{{.Type}}|{{.Source}}|{{.Destination}}|{{.Name}}{{"\n"}}{{end}}' "$NGX_CID")
  grep -q "^bind|$CONF|/etc/nginx/conf.d/default.conf|" <<<"$mounts" && ok "default.conf is a single-file bind mount → write in place" || fail "nginx does not mount $CONF at /etc/nginx/conf.d/default.conf"
  grep -q "^bind|$ROOT/certs|/etc/nginx/certs|" <<<"$mounts" && ok "certs mounted at /etc/nginx/certs" || fail "nginx does not mount $ROOT/certs at /etc/nginx/certs"
  WEBROOT_VOL=$(awk -F'|' '$3=="/var/www/certbot"{print ($1=="volume")?$4:$2}' <<<"$mounts")
  [ -n "$WEBROOT_VOL" ] && ok "ACME webroot $WEBROOT_VOL" || fail "nginx has no /var/www/certbot mount"
  NGX_NET=$(docker inspect -f '{{range $k, $v := .NetworkSettings.Networks}}{{println $k}}{{end}}' "$NGX_CID" | awk 'NF' | awk '/edge$/{e=$0} NR==1{f=$0} END{print (e!="")?e:f}')
  [ -n "$NGX_NET" ] && ok "nginx network $NGX_NET" || fail "nginx network unknown"
  NGX_V=$(dc exec -T nginx nginx -v 2>&1 | sed -n 's/.*nginx\/\([0-9.]*\).*/\1/p')
  if [ "$(printf '%s\n%s\n' "${NGX_V:-0}" 1.25.1 | sort -V | head -1)" = 1.25.1 ]; then H2=on; else H2=listen; fi
  ok "nginx $NGX_V (http2: $H2)"
  dc exec -T nginx nginx -t >"$WORK/nt0" 2>&1 && ok "current nginx -t passes" || fail "current config fails nginx -t: $(tail -2 "$WORK/nt0" | tr '\n' ' ')"

  # -- default.conf structure
  ngx_inspect "$CONF" >"$WORK/cur.json" || { fail "default.conf does not parse"; pf_abort; }
  PRIOR_MANAGED=$(jget "$WORK/cur.json" managed); [ "$PRIOR_MANAGED" = None ] && PRIOR_MANAGED=""
  if [ -n "$PRIOR_MANAGED" ]; then
    BASE_CONF=$PRE
    [ -f "$PRE" ] || { fail "default.conf is managed (mode=$PRIOR_MANAGED) but $PRE is missing"; pf_abort; }
    ok "rerun: current config managed (mode=$PRIOR_MANAGED); regenerating from $(basename "$PRE")"
  else BASE_CONF=$CONF; fi
  ngx_inspect "$BASE_CONF" >"$WORK/base.json" || { fail "$BASE_CONF does not parse"; pf_abort; }
  local n80 n443 ups prox
  n80=$(jget "$WORK/base.json" servers80); n443=$(jget "$WORK/base.json" servers443)
  [ "$n80" = 1 ] && ok "one active port-80 server block" || fail "expected exactly one active 'listen 80' server, found $n80"
  [ "$n443" = 0 ] && ok "no active 443 server yet (the commented karenseir.ir example is ignored)" || fail "base config already has $n443 active 443 server(s) — review by hand"
  [ "$n80" = 1 ] || pf_abort
  [ "$(jget "$WORK/base.json" acme)" = true ] && ok "ACME location /.well-known/acme-challenge/ present" || fail "port-80 server has no ACME location"
  [ "$(jget "$WORK/base.json" return_at_server)" = false ] || fail "port-80 server has a server-level return (already redirecting?)"
  ups=$(jget "$WORK/base.json" upstreams); prox=$(jget "$WORK/base.json" proxy)
  grep -q '"web"' <<<"$ups" && grep -q '"api"' <<<"$ups" && ok "upstreams $ups" || fail "upstream blocks web/api not found ($ups)"
  grep -q 'http://web' <<<"$prox" && grep -q 'http://api' <<<"$prox" && ok "proxy_pass targets $prox" || fail "proxy_pass http://web / http://api not found ($prox)"
  say "       server_name $(jget "$WORK/base.json" server_name), server-level headers $(jget "$WORK/base.json" server_headers), locations with own add_header: $(jget "$WORK/base.json" addheader_blocks)"

  # -- DNS
  local a aw aaaa
  a=$(a_records "$DOMAIN"); aaaa=$(aaaa_records "$DOMAIN")
  [ "$a" = "$EXPECTED_IP" ] && ok "DNS A $DOMAIN → $a" || fail "DNS A $DOMAIN → '$a' (expected only $EXPECTED_IP)"
  [ -z "$aaaa" ] || fail "DNS AAAA $DOMAIN → $aaaa (Let's Encrypt prefers IPv6; remove it at Talahost)"
  aw=$(a_records "$WWW")
  INCLUDE_WWW=""
  case "$WITH_WWW" in
    1) [ "$aw" = "$EXPECTED_IP" ] && INCLUDE_WWW=1 || fail "WITH_WWW=1 but $WWW → '$aw'";;
    auto) if [ "$aw" = "$EXPECTED_IP" ] && [ -z "$(aaaa_records "$WWW")" ]; then INCLUDE_WWW=1; else say "       $WWW → '${aw:-none}': www is left out (WITH_WWW=auto)"; fi;;
  esac
  [ -z "$INCLUDE_WWW" ] || ok "DNS A $WWW → $aw (included)"
  hostname -I 2>/dev/null | grep -qw "$EXPECTED_IP" && say "       $EXPECTED_IP is on a local interface" || say "       $EXPECTED_IP not on a local interface (cloud NAT) — fine"

  # -- certificate source
  CERT_MODE=letsencrypt CERT_VALID=0
  if [ -n "$CERT_FULLCHAIN$CERT_KEY" ]; then
    CERT_MODE=manual
    case "$CERT_FULLCHAIN" in /*) ;; *) fail "CERT_FULLCHAIN must be an absolute path";; esac
    case "$CERT_KEY" in /*) ;; *) fail "CERT_KEY must be an absolute path";; esac
    CERT_FILE=/etc/nginx/certs/manual/$DOMAIN/fullchain.pem; KEY_FILE=/etc/nginx/certs/manual/$DOMAIN/privkey.pem
    if [ -r "$CERT_FULLCHAIN" ] && [ -r "$CERT_KEY" ]; then
      local cp kp san
      cp=$(openssl x509 -in "$CERT_FULLCHAIN" -noout -pubkey 2>/dev/null | openssl sha256 || true)
      kp=$(openssl pkey -in "$CERT_KEY" -pubout 2>/dev/null | openssl sha256 || true)
      [ -n "$cp" ] && [ "$cp" = "$kp" ] && ok "manual certificate matches its key" || fail "CERT_FULLCHAIN and CERT_KEY do not match"
      openssl x509 -in "$CERT_FULLCHAIN" -noout -checkend 604800 >/dev/null 2>&1 || fail "manual certificate expires within 7 days"
      san=$(openssl x509 -in "$CERT_FULLCHAIN" -noout -ext subjectAltName 2>/dev/null || true)
      for c in "$DOMAIN" ${INCLUDE_WWW:+"$WWW"}; do grep -qE "DNS:($c|\*\.$DOMAIN)(,|$)" <<<"$san" || fail "manual certificate does not cover $c"; done
    else fail "CERT_FULLCHAIN/CERT_KEY not readable"; fi
  else
    CERT_FILE=/etc/nginx/certs/live/$DOMAIN/fullchain.pem; KEY_FILE=/etc/nginx/certs/live/$DOMAIN/privkey.pem
    if cert_pem "live/$DOMAIN/fullchain.pem" >"$WORK/cur.pem" && [ -s "$WORK/cur.pem" ]; then
      local san2 miss=0
      san2=$(openssl x509 -in "$WORK/cur.pem" -noout -ext subjectAltName 2>/dev/null || true)
      for c in "$DOMAIN" ${INCLUDE_WWW:+"$WWW"}; do grep -qE "DNS:$c(,|$)" <<<"$san2" || miss=1; done
      if [ "$miss" = 0 ] && openssl x509 -in "$WORK/cur.pem" -noout -checkend 2592000 >/dev/null 2>&1; then
        CERT_VALID=1; ok "existing certificate valid >30 days for the names ($(openssl x509 -in "$WORK/cur.pem" -noout -enddate)) — issuance skipped"
      else say "       existing certificate needs renewal/expansion ($(openssl x509 -in "$WORK/cur.pem" -noout -enddate 2>/dev/null))"; fi
    else say "       no certificate in $ROOT/certs/live/$DOMAIN yet"; fi
    if [ "$CERT_VALID" = 0 ]; then
      req -p https://acme-v02.api.letsencrypt.org/directory
      if [ "$RC" = 200 ] && grep -q newOrder "$WORK/b"; then ok "Let's Encrypt API reachable"
      else say "  FAIL Let's Encrypt API unreachable from this server (http=$RC)"; print_fallbacks; exit 3; fi
      if docker image inspect "$CERTBOT_IMAGE" >/dev/null 2>&1; then CERTBOT_PRESENT=1; ok "image $CERTBOT_IMAGE present"
      else CERTBOT_PRESENT=0; say "       image $CERTBOT_IMAGE not present — apply will try 'docker pull' (timeout ${PULL_TIMEOUT}s)"; fi
    fi
  fi

  # -- web image / env plan
  local wcid; wcid=$(dc ps -q web 2>/dev/null | head -1 || true)
  [ -n "$wcid" ] && WEB_IMG_ID=$(docker inspect -f '{{.Image}}' "$wcid") && WEB_REF=$(docker inspect -f '{{.Config.Image}}' "$wcid") \
    && ok "web runs $WEB_REF (${WEB_IMG_ID:7:12})" || fail "web container not running"
  say "       .env now: $(for k in PUBLIC_ORIGIN CORS_ORIGINS PUBLIC_WEB_URL ZARINPAL_CALLBACK_URL NEXT_PUBLIC_SITE_URL NEXT_PUBLIC_API_URL ALLOW_HTTP_PREVIEW ALLOW_HTTP_ORIGIN_PREVIEW COMPOSE_FILE; do envhas .env "$k" && printf '%s=%s  ' "$k" "$(envget .env "$k")"; done)"
  env_plan || true
  local avail; avail=$(df -Pm /var/lib/docker 2>/dev/null | awk 'NR==2{print $4}' || true); [ -n "$avail" ] || avail=$(df -Pm "$ROOT" | awk 'NR==2{print $4}')
  [ "${avail:-0}" -ge 2048 ] && ok "disk free ${avail}MB" || fail "less than 2GB free for the web rebuild (${avail:-?}MB)"
  crontab -l 2>/dev/null | grep -qF "$CRON_MARK" && say "       renewal cron already installed" || true

  [ ${#FAILS[@]} -eq 0 ] || pf_abort
  say "PREFLIGHT-OK (domain $DOMAIN${INCLUDE_WWW:+ + $WWW}, cert $CERT_MODE$([ "$CERT_VALID" = 1 ] && echo ' reuse'), hsts $HSTS_MAX_AGE)"
}
pf_abort() {
  say ""; say "PREFLIGHT-ABORT (${#FAILS[@]} problem(s)); nothing was changed:"; local f; for f in "${FAILS[@]}"; do say "  - $f"; done; exit 2
}

# env plan on a temporary copy of .env: the direct .env keys, then whatever the compose files reference.
# Leaves $WORK/env.new and $WORK/plan (OVL lines = overlay entries). Read-only for the server.
env_plan() {
  local d="https://$DOMAIN" cur_cors new_cors o k round
  cp -p .env "$WORK/env.new"
  new_cors="$d"; [ -z "$INCLUDE_WWW" ] || new_cors="$new_cors,https://$WWW"
  cur_cors=$(envget .env CORS_ORIGINS || true)
  IFS=',' read -ra _o <<<"${cur_cors:-}"
  for o in "${_o[@]}"; do o=${o// /}; case "$o" in https://*) [[ ",$new_cors," == *",$o,"* ]] || new_cors="$new_cors,$o";; esac; done
  NEW_CORS=$new_cors
  for k in PUBLIC_ORIGIN PUBLIC_WEB_URL PUBLIC_SITE_URL NEXT_PUBLIC_SITE_URL; do envhas "$WORK/env.new" "$k" && envset "$WORK/env.new" "$k" "$d"; done
  envhas "$WORK/env.new" NEXT_PUBLIC_API_URL && envset "$WORK/env.new" NEXT_PUBLIC_API_URL "$d/api"
  envhas "$WORK/env.new" ZARINPAL_CALLBACK_URL && envset "$WORK/env.new" ZARINPAL_CALLBACK_URL "$d/api/payments/zarinpal/callback"
  envhas "$WORK/env.new" CORS_ORIGINS && envset "$WORK/env.new" CORS_ORIGINS "$new_cors"
  for k in ALLOW_HTTP_PREVIEW ALLOW_HTTP_ORIGIN_PREVIEW; do [ "$(envget "$WORK/env.new" "$k")" != 1 ] || envset "$WORK/env.new" "$k" 0; done
  : >"$WORK/plan"
  for round in 1 2 3; do
    compose_json "$WORK/env.new" "$WORK/pres.json" || { cat "$WORK/pres.json.err"; fail "compose config with the new .env failed"; return 1; }
    compose_json "$WORK/env.new" "$WORK/praw.json" --no-interpolate || { fail "compose config --no-interpolate failed"; return 1; }
    python3 "$WORK/plan.py" "$DOMAIN" "$new_cors" "$WORK/pres.json" "$WORK/praw.json" "$EXPECTED_IP" "$WORK/env.new" .env >"$WORK/plan"
    grep -q '^ENV' "$WORK/plan" || break
    while IFS=$'\t' read -r _ k v _; do envset "$WORK/env.new" "$k" "$v"; done < <(grep '^ENV' "$WORK/plan")
    [ "$round" != 3 ] || { fail "compose env plan does not converge"; return 1; }
  done
  say "       env plan (.env changes):"
  while IFS= read -r k; do
    [ -n "$k" ] || continue
    [ "$(envget .env "$k")" = "$(envget "$WORK/env.new" "$k")" ] || say "         .env $k: '$(envget .env "$k")' → '$(envget "$WORK/env.new" "$k")'"
  done < <(sed -n 's/^\([A-Za-z_][A-Za-z0-9_]*\)=.*/\1/p' "$WORK/env.new" | sort -u)
  if grep -q '^OVL' "$WORK/plan"; then say "       values the compose files hard-code (→ overlay $OVERLAY via COMPOSE_FILE):"; grep '^OVL' "$WORK/plan" | sed 's/^OVL\t/         /;s/\t/ /g'; fi
  if grep -q '^BAD' "$WORK/plan"; then grep '^BAD' "$WORK/plan" | sed 's/^BAD\t/       WARN /'; fi
  if grep -q '^IP' "$WORK/plan"; then say "       still containing $EXPECTED_IP after the plan (not touched): $(grep '^IP' "$WORK/plan" | cut -f2)"; fi
  return 0
}

# ================================================================ apply
backup() {
  say "== 1 backup → $BK"
  mkdir -p "$BK"; chmod 700 "$BK"
  cp -p "$CONF" "$BK/default.conf"; cp -p .env "$BK/env"
  local f; for f in docker-compose.yml docker-compose.override.yml "$OVERLAY"; do [ ! -f "$f" ] || cp -p "$f" "$BK/$f"; done
  [ ! -f "$PRE" ] || cp -p "$PRE" "$BK/default.conf.pre-https"
  { echo "TS=$TS"; echo "PRIOR_MANAGED=$PRIOR_MANAGED"; echo "OVERLAY_EXISTED=$([ -f "$OVERLAY" ] && echo 1 || echo 0)"; echo "DOMAIN=$DOMAIN"; } >"$BK/STATE"
  CHANGED=1
  ok "default.conf, .env, compose files copied"
  local repo; repo=$WEB_REF; case "${repo##*/}" in *:*) repo=${repo%:*};; esac
  case "$WEB_REF" in ""|sha256:*|*@*) warn "web image reference '$WEB_REF' cannot be re-tagged — restore would keep the new build";;
    *) WEB_PRE_TAG="$repo:pre-https-$TS"
       docker tag "$WEB_IMG_ID" "$WEB_PRE_TAG"
       { echo "WEB_IMAGE_REF=$WEB_REF"; echo "WEB_IMAGE_PRE=$WEB_IMG_ID"; echo "WEB_IMAGE_TAG=$WEB_PRE_TAG"; } >>"$BK/STATE"
       ok "running web image kept as $WEB_PRE_TAG (api/worker are only restarted, not rebuilt)";;
  esac
}

ensure_certbot_image() {
  [ "$CERT_MODE" = letsencrypt ] && [ "$CERT_VALID" = 0 ] && [ "${CERTBOT_PRESENT:-1}" = 0 ] || return 0
  say "  pulling $CERTBOT_IMAGE (timeout ${PULL_TIMEOUT}s)…"
  if timeout "$PULL_TIMEOUT" docker pull -q "$CERTBOT_IMAGE" </dev/null >"$WORK/pull.log" 2>&1; then ok "pulled $CERTBOT_IMAGE"
  else tail -3 "$WORK/pull.log"; say "  FAIL cannot pull $CERTBOT_IMAGE (Docker Hub blocked?)"; print_fallbacks; exit 3; fi
}

certificate() {
  say "== 2 certificate"
  if [ "$CERT_MODE" = manual ]; then
    helper -v "$ROOT/certs:/kt-c" -v "$CERT_FULLCHAIN:/kt-in/fullchain.pem:ro" -v "$CERT_KEY:/kt-in/privkey.pem:ro" --entrypoint sh "$NGINX_IMG" \
      -c "mkdir -p /kt-c/manual/$DOMAIN && cp /kt-in/fullchain.pem /kt-c/manual/$DOMAIN/fullchain.pem && cp /kt-in/privkey.pem /kt-c/manual/$DOMAIN/privkey.pem && chmod 600 /kt-c/manual/$DOMAIN/privkey.pem"
    ok "manual certificate copied to $ROOT/certs/manual/$DOMAIN (renew it yourself: $(openssl x509 -in "$CERT_FULLCHAIN" -noout -enddate))"
    return 0
  fi
  [ "$CERT_VALID" = 0 ] || { ok "reusing the valid certificate"; return 0; }
  local tok="kt-selftest-$TS-$RANDOM" got n
  # shellcheck disable=SC2016  # $1 is expanded by sh inside the helper container
  helper -v "$WEBROOT_VOL:/kt-w" --entrypoint sh "$NGINX_IMG" -c 'mkdir -p /kt-w/.well-known/acme-challenge && printf %s "$1" >"/kt-w/.well-known/acme-challenge/$1"' sh "$tok"
  for n in "$DOMAIN" ${INCLUDE_WWW:+"$WWW"}; do
    req "http://$n/.well-known/acme-challenge/$tok"; got=$(head -c 200 "$WORK/b")
    if [ "$got" != "$tok" ]; then
      # shellcheck disable=SC2016
      helper -v "$WEBROOT_VOL:/kt-w" --entrypoint sh "$NGINX_IMG" -c 'rm -f "/kt-w/.well-known/acme-challenge/$1"' sh "$tok" || true
      die "ACME self-test: http://$n/.well-known/acme-challenge/ does not serve the webroot volume (got $RC '${got:0:60}')"
    fi
  done
  req -p "http://$DOMAIN/.well-known/acme-challenge/$tok"; got=$(head -c 200 "$WORK/b")
  # shellcheck disable=SC2016
  helper -v "$WEBROOT_VOL:/kt-w" --entrypoint sh "$NGINX_IMG" -c 'rm -f "/kt-w/.well-known/acme-challenge/$1"' sh "$tok" || true
  [ "$got" = "$tok" ] && ok "ACME self-test passed (local + via public DNS)" || warn "ACME token not reachable via the public IP from inside (hairpin NAT?); Let's Encrypt checks from outside"
  local args=(certonly --webroot -w /var/www/certbot --cert-name "$DOMAIN" -d "$DOMAIN") acct
  [ -z "$INCLUDE_WWW" ] || args+=(-d "$WWW")
  if [ -n "$EMAIL" ]; then acct=(-m "$EMAIL"); else acct=(--register-unsafely-without-email); fi
  args+=(--agree-tos -n "${acct[@]}" --keep-until-expiring --expand)
  say "  certbot dry-run (staging)…"
  if ! certbot_run "${args[@]}" --dry-run >"$WORK/cb-dry.log" 2>&1; then
    tail -15 "$WORK/cb-dry.log"; print_fallbacks
    die "Let's Encrypt dry-run failed (nginx/.env untouched)"
  fi
  ok "dry-run passed"
  certbot_run "${args[@]}" >"$WORK/cb.log" 2>&1 || { tail -15 "$WORK/cb.log"; die "certbot issuance failed after a successful dry-run"; }
  cert_pem "live/$DOMAIN/fullchain.pem" >"$WORK/new.pem" || die "certificate not readable after issuance"
  ok "certificate issued: $(openssl x509 -in "$WORK/new.pem" -noout -enddate)"
}

stage_a() {
  say "== A nginx: HTTPS on 443 (copy of the port-80 server), HTTP unchanged"
  if [ -z "$PRIOR_MANAGED" ]; then cat "$CONF" >"$PRE.tmp"; mv "$PRE.tmp" "$PRE"; ok "original saved as $(basename "$PRE") (not mounted)"; fi
  BASE_CONF=$PRE
  FIRST_MODE=tls; [ "$PRIOR_MANAGED" != final ] || FIRST_MODE=final
  gen_conf "$FIRST_MODE" "$WORK/a.conf"
  install_conf "$WORK/a.conf"
  req "https://$DOMAIN/"; [ "$RC" = 200 ] || die_rc 4 "https://$DOMAIN/ (local, certificate verified) returns $RC"
  ok "https://$DOMAIN/ → 200 locally (HTTP/$RV, certificate verified by curl)"
  if [ "$FIRST_MODE" = tls ]; then req "http://$DOMAIN/"; [ "$RC" = 200 ] || die "http://$DOMAIN/ returns $RC after stage A"; fi
  req -p "https://$DOMAIN/"
  if [ "$RC" = 200 ]; then ok "https://$DOMAIN/ reachable via public DNS/IP"
  elif [ "$ASSUME_443_OPEN" = 1 ]; then warn "https via the public IP failed from inside ($RC); continuing because ASSUME_443_OPEN=1"
  else
    say "  this server cannot reach https://$DOMAIN via $EXPECTED_IP (code $RC)."
    say "  From the Mac:  nc -vz -w5 $EXPECTED_IP 443   — if it connects, only hairpin NAT is missing: rerun with ASSUME_443_OPEN=1."
    say "  If it times out, open TCP 443 in the ArvanCloud security group and rerun."
    die_rc 4 "HTTPS not reachable via the public IP (stopping before .env/redirect)"
  fi
}

stage_b() {
  say "== B .env / compose → https://$DOMAIN, web rebuild, restart $APP_SERVICES"
  local hosts="" args_before args_after
  if web_reaches_https; then ok "web container reaches https://$DOMAIN/api (server-side fetches)"
  elif web_reaches_https hostgw; then hosts=$DOMAIN; ok "web container needs $DOMAIN → host-gateway (no hairpin NAT); added via overlay extra_hosts"
  else die "the web container cannot reach https://$DOMAIN/api (neither directly nor via host-gateway); NEXT_PUBLIC_API_URL cannot switch"; fi
  env_plan || die "env plan failed"
  grep -q '^BAD' "$WORK/plan" && warn "$(grep '^BAD' "$WORK/plan" | cut -f2 | tr '\n' ' ')"
  python3 -c 'import json,sys; s=json.load(open(sys.argv[1]))["services"]["web"]; b=s.get("build"); print(json.dumps(b.get("args") if isinstance(b,dict) else {}, sort_keys=True))' "$WORK/res.json" >"$WORK/args0"
  if grep -q '^OVL' "$WORK/plan" || [ -n "$hosts" ]; then
    python3 "$WORK/overlay.py" "$OVERLAY" "$WORK/plan" "$hosts"
    local cf; cf=$(envget "$WORK/env.new" COMPOSE_FILE || true)
    if [ -z "$cf" ]; then cf=docker-compose.yml; [ ! -f docker-compose.override.yml ] || cf="$cf:docker-compose.override.yml"; fi
    [[ ":$cf:" == *":$OVERLAY:"* ]] || cf="$cf:$OVERLAY"
    envset "$WORK/env.new" COMPOSE_FILE "$cf"
    ok "overlay $OVERLAY written; COMPOSE_FILE=$cf"
  fi
  cat "$WORK/env.new" >.env
  local k
  while read -r k; do
    if ! envhas "$BK/env" "$k" || [ "$(envget "$BK/env" "$k")" != "$(envget .env "$k")" ]; then echo "ENVSET=$k" >>"$BK/STATE"; fi
  done < <(sed -n 's/^\([A-Za-z_][A-Za-z0-9_]*\)=.*/\1/p' .env | sort -u)
  dc config -q || die "docker compose config fails with the new .env/overlay"
  compose_json .env "$WORK/res2.json"; compose_json .env "$WORK/raw2.json" --no-interpolate
  python3 "$WORK/plan.py" "$DOMAIN" "$NEW_CORS" "$WORK/res2.json" "$WORK/raw2.json" "$EXPECTED_IP" .env .env >"$WORK/plan2"
  if grep -qE '^(ENV|OVL)' "$WORK/plan2"; then grep -E '^(ENV|OVL)' "$WORK/plan2"; die "compose does not resolve the HTTPS values"; fi
  ok "compose resolves: $(grep '^OK' "$WORK/plan2" | cut -f2 | tr '\n' ';' | sed 's/;$//')"
  python3 -c 'import json,sys; s=json.load(open(sys.argv[1]))["services"]["web"]; b=s.get("build"); print(json.dumps(b.get("args") if isinstance(b,dict) else {}, sort_keys=True))' "$WORK/res2.json" >"$WORK/args1"
  args_before=$(cat "$WORK/args0"); args_after=$(cat "$WORK/args1")
  if [ "$args_before" != "$args_after" ]; then
    say "  building web (several minutes; log /tmp/karenseir-https-build.log)…"
    IMG_TOUCHED=1
    dc build web >/tmp/karenseir-https-build.log 2>&1 || { tail -30 /tmp/karenseir-https-build.log; die "web build failed (running containers untouched)"; }
    ok "web built"
  else ok "web build args unchanged — no rebuild"; fi
  UP_TOUCHED=1
  # shellcheck disable=SC2086
  dc up -d --no-build --no-deps $APP_SERVICES >"$WORK/up.log" 2>&1 || { cat "$WORK/up.log"; die "docker compose up -d $APP_SERVICES failed"; }
  local i h
  for i in $(seq 1 36); do
    req "https://$DOMAIN/api/health"; h=$RC; req "https://$DOMAIN/"
    [ "$h" = 200 ] && [ "$RC" = 200 ] && break
    [ "$i" = 36 ] && { dc logs --tail 30 api || true; die "api/web not healthy after restart (api $h, web $RC)"; }
    sleep "$KT_SLEEP"
  done
  ok "api + web healthy over https"
  local wcid; wcid=$(dc ps -q web | head -1); echo "WEB_IMAGE_POST=$(docker inspect -f '{{.Image}}' "$wcid")" >>"$BK/STATE"
}

stage_c() {
  say "== C nginx: HTTP→HTTPS redirect${INCLUDE_WWW:+, www→apex}, HSTS max-age=$HSTS_MAX_AGE"
  gen_conf final "$WORK/c.conf"
  install_conf "$WORK/c.conf"
  req "http://$DOMAIN/tours?x=1"; [ "$RC $RL" = "301 https://$DOMAIN/tours?x=1" ] || die "redirect check: '$RC $RL'"
  req "https://$DOMAIN/"; [ "$RC" = 200 ] || die "https://$DOMAIN/ returns $RC after stage C"
  AUTO_RESTORE=0
  ok "redirect live — from here on failures are reported, not auto-restored"
}

renewal() {
  say "== renewal"
  if [ "$CERT_MODE" = manual ]; then warn "manual certificate: no automatic renewal ($(openssl x509 -in "$CERT_FULLCHAIN" -noout -enddate))"; return 0; fi
  local line="17 3 * * * cd $ROOT && docker compose --profile ssl run --rm --no-deps -T --entrypoint certbot certbot renew --webroot -w /var/www/certbot -q >>$HOME/karenseir-certbot-renew.log 2>&1 && docker compose exec -T nginx nginx -s reload >/dev/null 2>&1 $CRON_MARK"
  if crontab -l 2>/dev/null | grep -qF "$CRON_MARK"; then ok "renewal cron already present"
  else { crontab -l 2>/dev/null || true; echo "$line"; } | crontab - && ok "cron (daily 03:17) installed for $(id -un): certbot renew + nginx reload"; fi
  if docker image inspect "$CERTBOT_IMAGE" >/dev/null 2>&1; then
    if certbot_run renew --dry-run --cert-name "$DOMAIN" >"$WORK/renew.log" 2>&1; then ok "certbot renew --dry-run passed"
    else tail -8 "$WORK/renew.log"; warn "certbot renew --dry-run failed — renewal needs attention before expiry"; fi
  else warn "image $CERTBOT_IMAGE not on the server (certificate came from elsewhere): the renewal cron will fail; see fallback 2"; fi
}

verify() {
  say "== verification"
  FAILS=()
  local p n h asset
  req "https://$DOMAIN/"; [ "$RC $RV" = "200 2" ] && ok "https://$DOMAIN/ 200 over HTTP/2" || fail "home: '$RC HTTP/$RV' (want 200 HTTP/2)"
  cp "$WORK/b" "$WORK/home.html"
  check_headers "home" 1
  grep -i '^content-security-policy:' "$WORK/h" | grep -q "$EXPECTED_IP" && fail "CSP still contains $EXPECTED_IP" || ok "CSP has no $EXPECTED_IP"
  [ "$(hcount content-security-policy)" = 1 ] || fail "home: CSP sent $(hcount content-security-policy) times"
  grep -i '^strict-transport-security:' "$WORK/h" | grep -q "max-age=$HSTS_MAX_AGE" || fail "HSTS max-age is not $HSTS_MAX_AGE"
  req "http://$DOMAIN/tours?x=1"; [ "$RC $RL" = "301 https://$DOMAIN/tours?x=1" ] && ok "http → https keeps path/query" || fail "http redirect: '$RC $RL'"
  check_headers "http redirect" 0
  req -p "http://127.0.0.1/" -H "Host: $EXPECTED_IP"; [ "$RC $RL" = "301 https://$DOMAIN/" ] && ok "http://$EXPECTED_IP → https://$DOMAIN/" || fail "IP redirect: '$RC $RL'"
  if [ -n "$INCLUDE_WWW" ]; then
    req "https://$WWW/x"; [ "$RC $RL" = "301 https://$DOMAIN/x" ] && ok "https://$WWW → apex" || fail "www redirect: '$RC $RL'"
    check_headers "www redirect" 1
  fi
  req "https://$DOMAIN/api/health"; [ "$RC" = 200 ] && ok "/api/health 200 $(head -c 60 "$WORK/b")" || fail "/api/health → $RC"
  check_headers "/api/health" 1
  req "https://$DOMAIN/kt-https-check-404-$TS"; [ "$RC" = 404 ] && ok "404 page answers 404" || fail "404 check → $RC"
  check_headers "404" 1
  asset=$(grep -o '/_next/static/[^"'\'' ]*\.\(js\|css\)' "$WORK/home.html" | head -1 || true)
  if [ -n "$asset" ]; then
    req "https://$DOMAIN$asset"; [ "$RC" = 200 ] && ok "static asset $asset 200" || fail "static asset $asset → $RC"
    check_headers "_next/static" 1
  else fail "no /_next/static asset found in the home page"; fi
  req "https://$DOMAIN/robots.txt"; grep -qi "^sitemap: https://$DOMAIN/sitemap.xml" "$WORK/b" && ok "robots.txt sitemap on https://$DOMAIN" || fail "robots.txt sitemap line not on https://$DOMAIN"
  req "https://$DOMAIN/sitemap.xml" -m 90
  n=$({ grep -o "<loc>https://$DOMAIN" "$WORK/b" || true; } | wc -l); h=$(grep -c "$EXPECTED_IP" "$WORK/b" || true)
  [ "$n" -gt 0 ] && [ "$h" = 0 ] && ok "sitemap: $n URLs on https://$DOMAIN, none on the IP" || fail "sitemap: https URLs=$n, IP mentions=$h"
  req "https://$DOMAIN/api/health" -H "Origin: https://$DOMAIN"
  p=$(tr -d '\r' <"$WORK/h" | awk -F': ' 'tolower($1)=="access-control-allow-origin"{print $2}')
  [ "$p" = "https://$DOMAIN" ] && ok "CORS allows https://$DOMAIN" || fail "CORS allow-origin for https://$DOMAIN: '$p'"
  echo "RESULT_FAILS=${#FAILS[@]}" >>"$BK/STATE"
  say ""
  if [ ${#FAILS[@]} -gt 0 ]; then
    say "HTTPS-FAILED: ${#FAILS[@]} check(s) failed (HTTPS stays live; nothing auto-restored):"; for p in "${FAILS[@]}"; do say "  - $p"; done
    say "Rollback: $ROLLBACK_CMD"; exit 1
  fi
  for p in "${WARNS[@]}"; do say "WARN: $p"; done
  cat <<EOF
Next:
  - from the Mac:  curl -sI https://$DOMAIN/ | head -5   and open https://$DOMAIN in a browser
  - after ~1 week without problems raise HSTS:  ssh karen@$EXPECTED_IP 'HSTS_MAX_AGE=31536000 bash -s' < ~/Downloads/karenseir-https-container.sh
  - Zarinpal: register https://$DOMAIN/api/payments/zarinpal/callback in the merchant panel before enabling payments
HTTPS-OK https://$DOMAIN hsts=$HSTS_MAX_AGE backup=$BK $(date -u +%FT%TZ)
EOF
}
check_headers() { # $1 label  $2 = 1 if HSTS expected
  local h n
  for h in x-content-type-options x-frame-options referrer-policy permissions-policy; do
    n=$(hcount "$h"); [ "$n" = 1 ] || fail "$1: $h sent $n times (want 1)"
  done
  n=$(hcount strict-transport-security); [ "$n" = "$2" ] || fail "$1: Strict-Transport-Security sent $n times (want $2)"
}

main() {
  config "$@"
  trap 'on_err $? $LINENO' ERR
  trap on_exit EXIT
  exec </dev/null   # bash has parsed the whole script; nothing below may read stdin ('bash -s')
  WORK=$(mktemp -d)
  write_py
  lock_acquire
  preflight
  [ "$CHECK_ONLY" = 0 ] || { say "(--check: nothing was changed)"; exit 0; }
  ensure_certbot_image
  backup
  certificate
  stage_a
  stage_b
  stage_c
  renewal
  verify
}

# KARENSEIR_HTTPS_LIB=1 only defines the functions (tests); the real entry point is this last line.
[ "${KARENSEIR_HTTPS_LIB:-0}" = 1 ] || main "$@" </dev/null
