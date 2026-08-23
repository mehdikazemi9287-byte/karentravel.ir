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
    if (!this.session) return;
    await this.request<void>('/auth/logout', { method: 'POST', body: JSON.stringify({ refresh_token: this.session.refresh_token }) });
    this.session = null;if(typeof window!=='undefined')sessionStorage.removeItem('karenseir-auth-session');
  }

  async get<T>(path: string) { return this.request<T>(path); }
  async publicGet<T>(path: string) { return this.request<T>(path, {}, false); }
  async post<T>(path: string, body: unknown, idempotencyKey?: string) {
    return this.request<T>(path, { method: 'POST', headers: idempotencyKey ? { 'Idempotency-Key': idempotencyKey } : undefined, body: JSON.stringify(body) });
  }
  async put<T>(path: string, body: unknown) {
    return this.request<T>(path, { method: 'PUT', body: JSON.stringify(body) });
  }
  async postAudio<T>(path: string, blob: Blob, filename: string) {
    const form = new FormData();
    form.append('audio', blob, filename);
    return this.request<T>(path, { method: 'POST', body: form }, true, true, true);
  }
  async delete<T>(path: string, body: unknown) {
    return this.request<T>(path, { method: 'DELETE', body: JSON.stringify(body) });
  }

  private async refresh() {
    if (!this.session) throw new ApiError(401, 'نشست معتبر نیست.');
    const next = await this.request<AuthSession>('/auth/refresh', { method: 'POST', body: JSON.stringify({ refresh_token: this.session.refresh_token, device_id: this.deviceId }) }, false, false);
    this.setSession({ ...this.session, ...next });
  }

  private async request<T>(path: string, init: RequestInit = {}, authenticated = true, retry = true, isMultipart = false): Promise<T> {
    const headers = new Headers(init.headers);
    if (!isMultipart) headers.set('Content-Type', 'application/json');
    headers.set('X-Correlation-ID', newId());
    if (authenticated) {
      if (!this.session) throw new ApiError(401, 'برای ادامه وارد شوید.');
      headers.set('Authorization', `Bearer ${this.session.access_token}`);
    }
    const response = await fetch(`${this.baseUrl}${path}`, { ...init, headers });
    if (response.status === 401 && authenticated && retry && this.session?.refresh_token) {
      await this.refresh();
      return this.request<T>(path, init, true, false, isMultipart);
    }
    if (!response.ok) {
      let message = 'ارتباط با سرویس انجام نشد.';
      let detail: unknown;
      try { detail = (await response.json()).detail; message = typeof detail === 'string' ? detail : message; } catch { /* non-JSON upstream */ }
      throw new ApiError(response.status, message, detail);
    }
    if (response.status === 204) return undefined as T;
    return response.json() as Promise<T>;
  }
}
