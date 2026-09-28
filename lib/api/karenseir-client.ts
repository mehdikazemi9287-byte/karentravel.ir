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
  token_type: 'bearer';
  user?: { name: string; role: string; tenant: string };
};

export class ApiError extends Error {
  constructor(public readonly status: number, message: string, public readonly detail?: unknown) { super(message); }
}

export class KarenSeirApi {
  private session: AuthSession | null = null;
  private refreshPending: Promise<void> | null = null;
  private readonly baseUrl: string;
  readonly deviceId: string;

  constructor(baseUrl = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000') {
    this.baseUrl = baseUrl.replace(/\/$/, '');
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
    const session = await this.request<AuthSession>('/auth/otp/verify', { method: 'POST', body: JSON.stringify({ tenant_slug, challenge_id, code, device_id: this.deviceId }) }, false);
    this.setSession(session);
    return session;
  }

  async devLogin(email: string) {
    const session = await this.request<AuthSession>('/auth/dev-login', { method: 'POST', body: JSON.stringify({ email }) }, false);
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
    try { await this.request<void>('/auth/logout', { method:'POST', keepalive:true, headers:{Authorization:`Bearer ${previous.access_token}`}, body:JSON.stringify({refresh_token:previous.refresh_token}) }, false, false); }
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
  get apiBase() { return this.baseUrl; }
  async delete<T>(path: string, body: unknown) {
    return this.request<T>(path, { method: 'DELETE', body: JSON.stringify(body) });
  }

  private async refresh() {
    if (this.refreshPending) return this.refreshPending;
    const current = this.session;
    if (!current) throw new ApiError(401, 'نشست معتبر نیست.');
    const pending = (async () => {
      const next = await this.request<AuthSession>('/auth/refresh', { method: 'POST', body: JSON.stringify({ refresh_token: current.refresh_token, device_id: this.deviceId }) }, false, false);
      if (this.session?.refresh_token !== current.refresh_token) throw new ApiError(401, 'نشست تغییر کرده است؛ دوباره وارد شوید.');
      this.setSession({ ...current, ...next });
    })();
    this.refreshPending = pending;
    try { await pending; } finally { if (this.refreshPending === pending) this.refreshPending = null; }
  }

  private async request<T>(path: string, init: RequestInit = {}, authenticated: boolean | 'optional' = true, retry = true, isMultipart = false, asText = false): Promise<T> {
    const headers = new Headers(init.headers);
    if (!isMultipart) headers.set('Content-Type', 'application/json');
    headers.set('X-Correlation-ID', newId());
    if (authenticated === true) {
      if (!this.session) throw new ApiError(401, 'برای ادامه وارد شوید.');
      headers.set('Authorization', `Bearer ${this.session.access_token}`);
    } else if (authenticated === 'optional' && this.session) {
      headers.set('Authorization', `Bearer ${this.session.access_token}`);
    }
    const response = await fetch(`${this.baseUrl}${path}`, { ...init, headers });
    if (response.status === 401 && authenticated === true && retry && this.session?.refresh_token) {
      // A delayed 401 may belong to the token another request already refreshed.
      if (headers.get('Authorization') === `Bearer ${this.session.access_token}`) await this.refresh();
      return this.request<T>(path, init, true, false, isMultipart, asText);
    }
    if (!response.ok) {
      let message = 'ارتباط با سرویس انجام نشد.';
      let detail: unknown;
      try { detail = (await response.json()).detail; message = typeof detail === 'string' ? detail : message; } catch { /* non-JSON upstream */ }
      throw new ApiError(response.status, message, detail);
    }
    if (response.status === 204) return undefined as T;
    return (asText ? response.text() : response.json()) as Promise<T>;
  }
}
