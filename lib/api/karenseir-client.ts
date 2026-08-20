export type AuthSession = {
  access_token: string;
  refresh_token: string;
  token_type: 'bearer';
  user?: { name: string; role: string; tenant: string };
};

export class ApiError extends Error {
  constructor(public readonly status: number, message: string) { super(message); }
}

export class KarenSeirApi {
  private session: AuthSession | null = null;
  private readonly baseUrl: string;
  readonly deviceId: string;

  constructor(baseUrl = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000') {
    this.baseUrl = baseUrl.replace(/\/$/, '');
    this.deviceId = typeof window === 'undefined' ? 'server-render' : (sessionStorage.getItem('karenseir-device-id') ?? crypto.randomUUID());
    if (typeof window !== 'undefined') sessionStorage.setItem('karenseir-device-id', this.deviceId);
  }

  get authenticated() { return this.session !== null; }
  setSession(session: AuthSession) { this.session = session; }

  async requestOtp(tenant_slug: string, identifier: string) {
    return this.request<{ status: string; challenge_id: string; expires_in: number }>('/auth/otp/request', { method: 'POST', body: JSON.stringify({ tenant_slug, identifier }) }, false);
  }

  async verifyOtp(tenant_slug: string, challenge_id: string, code: string) {
    const session = await this.request<AuthSession>('/auth/otp/verify', { method: 'POST', body: JSON.stringify({ tenant_slug, challenge_id, code, device_id: this.deviceId }) }, false);
    this.session = session;
    return session;
  }

  async devLogin(email: string) {
    const session = await this.request<AuthSession>('/auth/dev-login', { method: 'POST', body: JSON.stringify({ email }) }, false);
    this.session = session;
    return session;
  }

  async logout() {
    if (!this.session) return;
    await this.request<void>('/auth/logout', { method: 'POST', body: JSON.stringify({ refresh_token: this.session.refresh_token }) });
    this.session = null;
  }

  async get<T>(path: string) { return this.request<T>(path); }
  async post<T>(path: string, body: unknown, idempotencyKey?: string) {
    return this.request<T>(path, { method: 'POST', headers: idempotencyKey ? { 'Idempotency-Key': idempotencyKey } : undefined, body: JSON.stringify(body) });
  }
  async put<T>(path: string, body: unknown) {
    return this.request<T>(path, { method: 'PUT', body: JSON.stringify(body) });
  }

  private async refresh() {
    if (!this.session) throw new ApiError(401, 'نشست معتبر نیست.');
    const next = await this.request<AuthSession>('/auth/refresh', { method: 'POST', body: JSON.stringify({ refresh_token: this.session.refresh_token, device_id: this.deviceId }) }, false, false);
    this.session = { ...this.session, ...next };
  }

  private async request<T>(path: string, init: RequestInit = {}, authenticated = true, retry = true): Promise<T> {
    const headers = new Headers(init.headers);
    headers.set('Content-Type', 'application/json');
    headers.set('X-Correlation-ID', crypto.randomUUID());
    if (authenticated) {
      if (!this.session) throw new ApiError(401, 'برای ادامه وارد شوید.');
      headers.set('Authorization', `Bearer ${this.session.access_token}`);
    }
    const response = await fetch(`${this.baseUrl}${path}`, { ...init, headers });
    if (response.status === 401 && authenticated && retry && this.session?.refresh_token) {
      await this.refresh();
      return this.request<T>(path, init, true, false);
    }
    if (!response.ok) {
      let message = 'ارتباط با سرویس انجام نشد.';
      try { message = (await response.json()).detail ?? message; } catch { /* non-JSON upstream */ }
      throw new ApiError(response.status, message);
    }
    if (response.status === 204) return undefined as T;
    return response.json() as Promise<T>;
  }
}
