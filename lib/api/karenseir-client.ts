// crypto.randomUUID() only exists in secure contexts (HTTPS or localhost); on a
// plain-HTTP origin it is undefined and throws. These IDs are correlation/device/
// idempotency identifiers, not secrets, so a non-cryptographic fallback is safe.
export function newId(): string {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') return crypto.randomUUID();
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0;
    return (c === 'x' ? r : (r & 0x3) | 0x8).toString(16);
  });
}

export type AuthSession = {
  access_token: string;
  refresh_token: string;
  /** 'cookie' (AUTH_COOKIE_MODE on the API): the real tokens live in httpOnly cookies the page cannot read;
   *  access_token is then only a non-secret placeholder carrying the public claims (iss/sub) for UI keys. */
  token_type: 'bearer' | 'cookie';
  user?: { name: string; role: string; tenant: string };
};

type CookieSessionBody = { token_type: 'cookie'; subject?: { iss?: string; sub?: string; tenant?: number }; user?: AuthSession['user'] };

const CSRF_COOKIE = 'karenseir_csrf';

/** Turn an API login/refresh body into the stored session. In cookie mode nothing secret is kept in JS storage. */
function toSession(body: AuthSession | CookieSessionBody): AuthSession {
  if (body.token_type !== 'cookie' || 'access_token' in body) return body as AuthSession;
  const subject = (body as CookieSessionBody).subject;
  const claims = JSON.stringify({ iss: subject?.iss, sub: subject?.sub, tenant: subject?.tenant });
  const b64 = typeof btoa === 'function' ? btoa(unescape(encodeURIComponent(claims))) : '';
  return { access_token: `cookie.${b64}.`, refresh_token: 'cookie', token_type: 'cookie', user: body.user };
}

function readCookie(name: string): string | null {
  if (typeof document === 'undefined') return null;
  const hit = document.cookie.split('; ').find(c => c.startsWith(`${name}=`));
  return hit ? decodeURIComponent(hit.slice(name.length + 1)) : null;
}

export class ApiError extends Error {
  constructor(public readonly status: number, message: string, public readonly detail?: unknown) { super(message); }
}

/** Thrown by verifyOtp when the account has authenticator-app two-step login: finish with verifyMfa(ticket, ...). */
export class MfaRequiredError extends Error {
  constructor(public readonly ticket: string, public readonly tenantSlug: string) { super('mfa_required'); }
}

/** In the browser, call a path-mounted API on the page's own origin (the same nginx serves /api for the IP and for karentravel.ir);
 *  an absolute build-time URL on another host would be a cross-origin call that CORS blocks. Server-side keeps the configured URL. */
export function resolveApiBase(configured: string): string {
  const base = configured.replace(/\/$/, '');
  if (typeof window === 'undefined' || !/^https?:\/\//.test(base)) return base;
  try {
    const u = new URL(base);
    // Only a path-mounted API ("…/api" behind our nginx) exists on every host; a bare API origin (dev :8000) is kept.
    if (u.origin === window.location.origin || u.pathname === '/' || u.pathname === '') return base;
    return window.location.origin + u.pathname.replace(/\/$/, '');
  } catch { return base; }
}

export class KarenSeirApi {
  private session: AuthSession | null = null;
  private refreshPending: Promise<void> | null = null;
  private readonly baseUrl: string;
  readonly deviceId: string;

  constructor(baseUrl = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000') {
    this.baseUrl = resolveApiBase(baseUrl);
    this.deviceId = typeof window === 'undefined' ? 'server-render' : (sessionStorage.getItem('karenseir-device-id') ?? newId());
    if (typeof window !== 'undefined') {
      sessionStorage.setItem('karenseir-device-id', this.deviceId);
      try { const stored=sessionStorage.getItem('karenseir-auth-session');if(stored)this.session=JSON.parse(stored) as AuthSession; } catch { sessionStorage.removeItem('karenseir-auth-session'); }
    }
  }

  get authenticated() { return this.session !== null; }
  getSession() { return this.session; }
  setSession(session: AuthSession) { this.session = session; if(typeof window!=='undefined')sessionStorage.setItem('karenseir-auth-session',JSON.stringify(session)); }

  async requestOtp(tenant_slug: string, identifier: string) {
    return this.request<{ status: string; challenge_id: string; expires_in: number }>('/auth/otp/request', { method: 'POST', body: JSON.stringify({ tenant_slug, identifier }) }, false);
  }

  async register(mobile: string, name?: string) {
    return this.request<{ status: string; challenge_id: string; expires_in: number; tenant_slug: string }>('/auth/register/request', { method: 'POST', body: JSON.stringify({ mobile, name }) }, false);
  }

  async verifyOtp(tenant_slug: string, challenge_id: string, code: string) {
    const body = await this.request<AuthSession & { mfa_required?: boolean; mfa_ticket?: string }>('/auth/otp/verify', { method: 'POST', body: JSON.stringify({ tenant_slug, challenge_id, code, device_id: this.deviceId }) }, false);
    if (body.mfa_required && body.mfa_ticket) throw new MfaRequiredError(body.mfa_ticket, tenant_slug);
    const session = toSession(body);
    this.setSession(session);
    return session;
  }

  async verifyMfa(tenant_slug: string, mfa_ticket: string, factor: { code?: string; recovery_code?: string }) {
    const session = toSession(await this.request<AuthSession>('/auth/2fa/verify', { method: 'POST', body: JSON.stringify({ tenant_slug, mfa_ticket, ...factor, device_id: this.deviceId }) }, false));
    this.setSession(session);
    return session;
  }

  async devLogin(email: string) {
    const session = toSession(await this.request<AuthSession>('/auth/dev-login', { method: 'POST', body: JSON.stringify({ email }) }, false));
    this.setSession(session);
    return session;
  }

  async logout() {
    const previous = this.session;
    this.session = null;
    if(typeof window!=='undefined')for(const key of ['karenseir-auth-session','karenseir-assistant-conversation-id','karenseir-assistant-messages','karenseir-assistant-resume-pending'])sessionStorage.removeItem(key);
    if (!previous) return;
    // Clear this browser immediately; navigation or a failed network request must not restore it.
    // Keepalive attempts server revocation with the captured credentials; never refresh after logout.
    const cookieMode = previous.token_type === 'cookie';
    const headers: Record<string, string> = cookieMode ? { 'X-CSRF-Token': readCookie(CSRF_COOKIE) ?? '' } : { Authorization: `Bearer ${previous.access_token}` };
    try { await this.request<void>('/auth/logout', { method:'POST', keepalive:true, credentials:'same-origin', headers, body:JSON.stringify(cookieMode ? {} : {refresh_token:previous.refresh_token}) }, false, false); }
    catch { /* Local sign-out is complete. No claim of server revocation when unreachable. */ }
  }

  async getText(path: string) { return this.request<string>(path, {}, true, true, false, true); }
  async get<T>(path: string) { return this.request<T>(path); }
  async publicGet<T>(path: string) { return this.request<T>(path, {}, false); }
  async publicPost<T>(path: string, body: unknown) { return this.request<T>(path, { method: 'POST', body: JSON.stringify(body) }, false); }
  async post<T>(path: string, body: unknown, idempotencyKey?: string) {
    return this.request<T>(path, { method: 'POST', headers: idempotencyKey ? { 'Idempotency-Key': idempotencyKey } : undefined, body: JSON.stringify(body) });
  }
  async put<T>(path: string, body: unknown) {
    return this.request<T>(path, { method: 'PUT', body: JSON.stringify(body) });
  }
  // Phase 6 (Assistant): the token is attached WHEN a session exists, but a
  // missing session never throws -- unlike `post`, which requires one. This
  // is the one shape Assistant's own contract needs: anonymous callers must
  // keep working, and an already-logged-in caller's identity should still
  // be forwarded on every call without the caller having to ask for it.
  async postOptionalAuth<T>(path: string, body: unknown) {
    return this.request<T>(path, { method: 'POST', body: JSON.stringify(body) }, 'optional');
  }
  async postAudio<T>(path: string, blob: Blob, filename: string) {
    const form = new FormData();
    form.append('audio', blob, filename);
    return this.request<T>(path, { method: 'POST', body: form }, true, true, true);
  }
  async postForm<T>(path: string, form: FormData) {
    return this.request<T>(path, { method: 'POST', body: form }, true, true, true);
  }
  async putForm<T>(path: string, form: FormData) {
    return this.request<T>(path, { method: 'PUT', body: form }, true, true, true);
  }
  /** Binary responses (document previews) with the same auth/refresh handling. */
  async getBlob(path: string) { return this.request<Blob>(path, {}, true, true, false, false, true); }
  async postBlob(path: string, body: unknown) { return this.request<Blob>(path, { method: 'POST', body: JSON.stringify(body) }, true, true, false, false, true); }
  get apiBase() { return this.baseUrl; }
  async delete<T>(path: string, body: unknown) {
    return this.request<T>(path, { method: 'DELETE', body: JSON.stringify(body) });
  }

  private async refresh() {
    if (this.refreshPending) return this.refreshPending;
    const current = this.session;
    if (!current) throw new ApiError(401, 'نشست معتبر نیست.');
    const pending = (async () => {
      const cookieMode = current.token_type === 'cookie';
      const body = cookieMode ? { device_id: this.deviceId } : { refresh_token: current.refresh_token, device_id: this.deviceId };
      const next = await this.request<AuthSession>('/auth/refresh', { method: 'POST', headers: cookieMode ? { 'X-CSRF-Token': readCookie(CSRF_COOKIE) ?? '' } : undefined, body: JSON.stringify(body) }, false, false);
      if (this.session?.refresh_token !== current.refresh_token) throw new ApiError(401, 'نشست تغییر کرده است؛ دوباره وارد شوید.');
      this.setSession(cookieMode ? { ...current, ...toSession(next), user: current.user ?? next.user } : { ...current, ...next });
    })();
    this.refreshPending = pending;
    try { await pending; } finally { if (this.refreshPending === pending) this.refreshPending = null; }
  }

  private async request<T>(path: string, init: RequestInit = {}, authenticated: boolean | 'optional' = true, retry = true, isMultipart = false, asText = false, asBlob = false): Promise<T> {
    const headers = new Headers(init.headers);
    if (!isMultipart) headers.set('Content-Type', 'application/json');
    headers.set('X-Correlation-ID', newId());
    if (authenticated === true && !this.session) throw new ApiError(401, 'برای ادامه وارد شوید.');
    const cookieMode = this.session?.token_type === 'cookie';
    const sentToken = this.session?.access_token;
    if ((authenticated === true || authenticated === 'optional') && this.session) {
      if (cookieMode) {
        // httpOnly cookies travel by themselves; state-changing calls carry the double-submit CSRF token.
        const method = (init.method ?? 'GET').toUpperCase();
        if (!['GET', 'HEAD', 'OPTIONS'].includes(method)) headers.set('X-CSRF-Token', readCookie(CSRF_COOKIE) ?? '');
      } else headers.set('Authorization', `Bearer ${this.session.access_token}`);
    }
    const response = await fetch(`${this.baseUrl}${path}`, { credentials: 'same-origin', ...init, headers });
    if (response.status === 401 && authenticated === true && retry && this.session?.refresh_token) {
      // A delayed 401 may belong to the token another request already refreshed.
      if (cookieMode || sentToken === this.session.access_token) await this.refresh();
      return this.request<T>(path, init, true, false, isMultipart, asText, asBlob);
    }
    if (!response.ok) {
      let message = 'ارتباط با سرویس انجام نشد.';
      let detail: unknown;
      try { detail = (await response.json()).detail; message = typeof detail === 'string' ? detail : message; } catch { /* non-JSON upstream */ }
      throw new ApiError(response.status, message, detail);
    }
    if (response.status === 204) return undefined as T;
    return (asBlob ? response.blob() : asText ? response.text() : response.json()) as Promise<T>;
  }
}
