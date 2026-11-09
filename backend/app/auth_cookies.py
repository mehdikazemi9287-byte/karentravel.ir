"""httpOnly cookie session transport with double-submit CSRF (security review M-3).

Feature flag: AUTH_COOKIE_MODE=1 (default off -> behaviour is exactly the
Bearer-only API it was before). When on:

* Login responses (/auth/otp/verify, /auth/2fa/verify, /auth/dev-login) and a
  cookie-driven /auth/refresh set three cookies and DROP the tokens from the
  JSON body, so script running in the page (XSS) cannot read them:
    karenseir_at    access JWT       HttpOnly, SameSite=Lax, Max-Age 15 min
    karenseir_rt    refresh token    HttpOnly, SameSite=Lax, Max-Age 30 days
    karenseir_csrf  random value     readable by JS, SameSite=Lax
  The body becomes {"token_type": "cookie", "user": ..., "subject": {iss, sub, tenant}}.
* A request without an Authorization header but with karenseir_at gets the
  header injected from the cookie; /auth/refresh and /auth/logout get the
  refresh token injected into their JSON body from karenseir_rt.
* Any cookie-authenticated POST/PUT/PATCH/DELETE must send header
  X-CSRF-Token equal to the karenseir_csrf cookie, otherwise 403.
* Authorization: Bearer clients keep working unchanged (no cookie use, no CSRF
  needed). A login request with header "X-Auth-Transport: bearer" still gets
  the tokens in the body; a refresh that sends refresh_token in its body gets
  a bearer response too.
* /auth/logout always clears the cookies.

Secure flag: AUTH_COOKIE_SECURE=auto (default) sets Secure only when the
request arrived over HTTPS (scheme or X-Forwarded-Proto), so the flag also
works on the current plain-HTTP site; set AUTH_COOKIE_SECURE=1 after HTTPS
(H-3). AUTH_COOKIE_PATH (default "/") scopes the cookies.

Switching on (after HTTPS): set AUTH_COOKIE_MODE=1 and AUTH_COOKIE_SECURE=1 in
the api environment and restart api. Logged-in browsers keep their current
Bearer session until it ends; the next login uses cookies. Switch off by
removing the flag (cookie sessions then fall back to "please log in again").
"""
from __future__ import annotations

import hmac
import json
import os
import secrets
from http.cookies import SimpleCookie
from typing import Optional

import jwt

AT, RT, CSRF = "karenseir_at", "karenseir_rt", "karenseir_csrf"
LOGIN_SUFFIXES = ("/auth/otp/verify", "/auth/2fa/verify", "/auth/dev-login")
REFRESH_SUFFIX, LOGOUT_SUFFIX = "/auth/refresh", "/auth/logout"
UNSAFE = {"POST", "PUT", "PATCH", "DELETE"}
SYNTHETIC_PREFIX = "Bearer cookie."  # placeholder the browser client keeps instead of a real token


def enabled() -> bool:
    return os.getenv("AUTH_COOKIE_MODE", "0").strip().lower() in {"1", "true", "yes", "on"}


def _secure(scope, headers: dict) -> bool:
    mode = os.getenv("AUTH_COOKIE_SECURE", "auto").strip().lower()
    if mode in {"1", "true", "yes", "on"}:
        return True
    if mode in {"0", "false", "no", "off"}:
        return False
    return scope.get("scheme") == "https" or headers.get("x-forwarded-proto", "").split(",")[0].strip() == "https"


def _cookie(name: str, value: str, *, max_age: int, http_only: bool, secure: bool) -> bytes:
    path = os.getenv("AUTH_COOKIE_PATH", "/") or "/"
    parts = [f"{name}={value}", f"Path={path}", f"Max-Age={max_age}", "SameSite=Lax"]
    if http_only:
        parts.append("HttpOnly")
    if secure:
        parts.append("Secure")
    return "; ".join(parts).encode("latin-1")


def _set_session_cookies(access: str, refresh: str, csrf: str, secure: bool) -> list[tuple[bytes, bytes]]:
    return [(b"set-cookie", _cookie(AT, access, max_age=15 * 60, http_only=True, secure=secure)),
            (b"set-cookie", _cookie(RT, refresh, max_age=30 * 24 * 3600, http_only=True, secure=secure)),
            (b"set-cookie", _cookie(CSRF, csrf, max_age=30 * 24 * 3600, http_only=False, secure=secure))]


def _clear_cookies(secure: bool) -> list[tuple[bytes, bytes]]:
    return [(b"set-cookie", _cookie(name, "", max_age=0, http_only=name != CSRF, secure=secure)) for name in (AT, RT, CSRF)]


def _parse_cookies(raw: str) -> dict[str, str]:
    jar = SimpleCookie()
    try:
        jar.load(raw)
    except Exception:  # malformed cookie header: treat as no cookies
        return {}
    return {k: v.value for k, v in jar.items()}


def _subject(access_token: str) -> dict:
    try:
        claims = jwt.decode(access_token, options={"verify_signature": False})
    except jwt.PyJWTError:
        return {}
    return {k: claims.get(k) for k in ("iss", "sub", "tenant")}


async def _read_body(receive) -> bytes:
    body, more = b"", True
    while more:
        message = await receive()
        if message["type"] != "http.request":
            return body
        body += message.get("body", b"")
        more = message.get("more_body", False)
    return body


async def _json_error(send, status: int, detail: str) -> None:
    payload = json.dumps({"detail": detail}, ensure_ascii=False).encode("utf-8")
    await send({"type": "http.response.start", "status": status, "headers": [(b"content-type", b"application/json"), (b"content-length", str(len(payload)).encode())]})
    await send({"type": "http.response.body", "body": payload})


class AuthCookieMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or not enabled():
            return await self.app(scope, receive, send)
        raw_headers = list(scope.get("headers") or [])
        headers = {k.decode("latin-1").lower(): v.decode("latin-1") for k, v in raw_headers}
        cookies = _parse_cookies(headers.get("cookie", ""))
        path, method = scope.get("path", ""), scope.get("method", "GET").upper()
        secure = _secure(scope, headers)
        is_login = path.endswith(LOGIN_SUFFIXES)
        is_refresh, is_logout = path.endswith(REFRESH_SUFFIX), path.endswith(LOGOUT_SUFFIX)

        authorization: Optional[str] = headers.get("authorization")
        if authorization and authorization.startswith(SYNTHETIC_PREFIX):
            authorization = None
            raw_headers = [(k, v) for k, v in raw_headers if k.lower() != b"authorization"]
        used_cookie = False
        if not authorization and cookies.get(AT) and not is_login:
            raw_headers.append((b"authorization", f"Bearer {cookies[AT]}".encode("latin-1")))
            used_cookie = True

        body_override: Optional[bytes] = None
        if (is_refresh or is_logout) and cookies.get(RT) and method == "POST":
            body = await _read_body(receive)
            try:
                data = json.loads(body or b"{}")
            except ValueError:
                data = None
            if isinstance(data, dict) and not data.get("refresh_token"):
                data["refresh_token"] = cookies[RT]
                body = json.dumps(data).encode("utf-8")
                used_cookie = True
                raw_headers = [(k, v) for k, v in raw_headers if k.lower() not in (b"content-length", b"content-type")]
                raw_headers += [(b"content-type", b"application/json"), (b"content-length", str(len(body)).encode())]
            body_override = body

        if used_cookie and method in UNSAFE:
            sent, expected = headers.get("x-csrf-token", ""), cookies.get(CSRF, "")
            if not sent or not expected or not hmac.compare_digest(sent, expected):
                return await _json_error(send, 403, "درخواست از صفحهٔ معتبر ارسال نشده است؛ صفحه را تازه کنید و دوباره تلاش کنید")

        new_scope = dict(scope)
        new_scope["headers"] = raw_headers
        downstream_receive = receive
        if body_override is not None:
            delivered = False

            async def downstream_receive():  # noqa: F811  replay the (possibly rewritten) body once
                nonlocal delivered
                if not delivered:
                    delivered = True
                    return {"type": "http.request", "body": body_override, "more_body": False}
                return await receive()

        wants_bearer = headers.get("x-auth-transport", "").strip().lower() == "bearer"
        rewrite = (is_login and not wants_bearer) or (is_refresh and used_cookie)
        if not rewrite and not is_logout:
            return await self.app(new_scope, downstream_receive, send)

        start: dict = {}
        chunks: list[bytes] = []

        async def capture(message):
            if message["type"] == "http.response.start":
                start.update(message)
                return
            if message["type"] == "http.response.body":
                chunks.append(message.get("body", b""))
                if message.get("more_body", False):
                    return
                await _finish()

        async def _finish():
            status = start.get("status", 500)
            out_headers = [(k, v) for k, v in start.get("headers", []) if k.lower() != b"content-length"]
            body = b"".join(chunks)
            if is_logout:
                out_headers += _clear_cookies(secure)
            elif status == 200:
                try:
                    data = json.loads(body)
                except ValueError:
                    data = None
                if isinstance(data, dict) and data.get("access_token") and data.get("refresh_token"):
                    csrf = secrets.token_urlsafe(32)
                    out_headers += _set_session_cookies(data["access_token"], data["refresh_token"], csrf, secure)
                    slim = {"token_type": "cookie", "subject": _subject(data["access_token"])}
                    if "user" in data:
                        slim["user"] = data["user"]
                    body = json.dumps(slim, ensure_ascii=False).encode("utf-8")
            elif status == 401 and is_refresh:
                out_headers += _clear_cookies(secure)
            out_headers.append((b"content-length", str(len(body)).encode()))
            await send({**start, "headers": out_headers})
            await send({"type": "http.response.body", "body": body})

        return await self.app(new_scope, downstream_receive, capture)
