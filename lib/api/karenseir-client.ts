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

export type RequestOptions = { signal?: AbortSignal; timeoutMs?: number };

export class KarenSeirApi {
  private session: AuthSession | null = null;
  private sessionEpoch = 0;
  private readonly reads = new Map<string, Promise<unknown>>();
  private refreshFlight: { token: string; epoch: number; promise: Promise<void> } | null = null;
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
  setSession(session: AuthSession) { this.sessionEpoch++; this.reads.clear(); this.session = session; if(typeof window!=='undefined')sessionStorage.setItem('karenseir-auth-session',JSON.stringify(session)); }

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
    this.sessionEpoch++; this.reads.clear(); this.session = null;if(typeof window!=='undefined')sessionStorage.removeItem('karenseir-auth-session');
  }

  async get<T>(path: string, options: RequestOptions = {}) { return this.request<T>(path, options); }
  async publicGet<T>(path: string, options: RequestOptions = {}) { return this.request<T>(path, options, false); }
  async publicPost<T>(path: string, body: unknown, options: RequestOptions = {}) { return this.request<T>(path, { ...options, method: 'POST', body: JSON.stringify(body) }, false); }
  async post<T>(path: string, body: unknown, idempotencyKey?: string, options: RequestOptions = {}) {
    return this.request<T>(path, { ...options, method: 'POST', headers: idempotencyKey ? { 'Idempotency-Key': idempotencyKey } : undefined, body: JSON.stringify(body) });
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

  private async refresh(epoch: number) {
    const session = this.session;
    if (!session || epoch !== this.sessionEpoch) throw new ApiError(401, 'نشست تغییر کرده است.');
    if (this.refreshFlight?.epoch === epoch && this.refreshFlight.token === session.refresh_token) return this.refreshFlight.promise;
    const flight = { token: session.refresh_token, epoch, promise: Promise.resolve() };
    flight.promise = (async () => {
      const next = await this.request<AuthSession>('/auth/refresh', { method: 'POST', body: JSON.stringify({ refresh_token: session.refresh_token, device_id: this.deviceId }) }, false, false);
      if (epoch !== this.sessionEpoch || this.session?.refresh_token !== session.refresh_token) throw new ApiError(401, 'نشست تغییر کرده است.');
      this.session = { ...session, ...next };
      if (typeof window !== 'undefined') sessionStorage.setItem('karenseir-auth-session', JSON.stringify(this.session));
    })().finally(() => { if (this.refreshFlight === flight) this.refreshFlight = null; });
    this.refreshFlight = flight;
    return flight.promise;
  }

  private async request<T>(path: string, init: RequestInit & RequestOptions = {}, authenticated = true, retry = true, isMultipart = false): Promise<T> {
    const method = (init.method || 'GET').toUpperCase();
    const write = method !== 'GET';
    if (write) this.reads.clear();
    const epoch = this.sessionEpoch;
    const timeoutMs = init.timeoutMs ?? 30000;
    if (!Number.isFinite(timeoutMs) || timeoutMs <= 0) throw new RangeError('Invalid request deadline');
    const key = !write && !init.body && !init.signal && typeof window !== 'undefined'
      ? JSON.stringify([path, authenticated, epoch, authenticated ? this.session?.access_token : null, Array.from(new Headers(init.headers).entries()), timeoutMs]) : null;
    const prior = key ? this.reads.get(key) : undefined;
    if (prior) return structuredClone(await prior) as T;
    const controller = new AbortController();
    const cancel = () => controller.abort(init.signal?.reason);
    if (init.signal?.aborted) cancel(); else init.signal?.addEventListener('abort', cancel, { once: true });
    const timer = setTimeout(() => controller.abort(new DOMException('Request timed out', 'TimeoutError')), timeoutMs);
    let onAbort = () => {};
    const aborted = new Promise<never>((_, reject) => {
      onAbort = () => reject(controller.signal.reason);
      if (controller.signal.aborted) onAbort(); else controller.signal.addEventListener('abort', onAbort, { once: true });
    });
    const task = Promise.race([aborted, Promise.resolve().then(() => this.send<T>(path, init, authenticated, retry, isMultipart, controller.signal, epoch))]);
    const registered = key !== null && this.reads.size < 256;
    if (registered) this.reads.set(key, task);
    try { return structuredClone(await task); }
    finally {
      clearTimeout(timer);
      controller.signal.removeEventListener('abort', onAbort);
      init.signal?.removeEventListener('abort', cancel);
      if (registered && this.reads.get(key!) === task) this.reads.delete(key!);
      if (write) this.reads.clear();
    }
  }

  private async send<T>(path: string, init: RequestInit & RequestOptions, authenticated: boolean, retry: boolean, isMultipart: boolean, signal: AbortSignal, epoch: number): Promise<T> {
    signal.throwIfAborted();
    if (authenticated && epoch !== this.sessionEpoch) throw new ApiError(401, 'نشست تغییر کرده است.');
    const headers = new Headers(init.headers);
    if (!isMultipart) headers.set('Content-Type', 'application/json');
    headers.set('X-Correlation-ID', newId());
    const token = this.session?.access_token;
    if (authenticated) {
      if (!token) throw new ApiError(401, 'برای ادامه وارد شوید.');
      headers.set('Authorization', `Bearer ${token}`);
    }
    const { timeoutMs: _timeout, ...fetchOptions } = init;
    const response = await fetch(`${this.baseUrl}${path}`, { ...fetchOptions, headers, signal, cache: 'no-store' });
    signal.throwIfAborted();
    if (authenticated && epoch !== this.sessionEpoch) throw new ApiError(401, 'نشست تغییر کرده است.');
    if (response.status === 401 && authenticated && retry && this.session?.refresh_token) {
      // A late 401 for the old access token must not rotate the replacement again.
      if (this.session.access_token === token) await this.refresh(epoch);
      signal.throwIfAborted();
      return this.send<T>(path, init, true, false, isMultipart, signal, epoch);
    }
    if (!response.ok) {
      let message = 'ارتباط با سرویس انجام نشد.';
      let detail: unknown;
      try { detail = (await response.json()).detail; message = typeof detail === 'string' ? detail : message; } catch { /* non-JSON upstream */ }
      signal.throwIfAborted();
      throw new ApiError(response.status, message, detail);
    }
    if (response.status === 204) return undefined as T;
    const data = await response.json() as T;
    signal.throwIfAborted();
    if (authenticated && epoch !== this.sessionEpoch) throw new ApiError(401, 'نشست تغییر کرده است.');
    return data;
  }
}
