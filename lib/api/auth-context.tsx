'use client';

import { createContext, useContext, useEffect, useMemo, useState } from 'react';
import { AuthSession, KarenSeirApi } from './karenseir-client';

type AuthContextValue = {
  api: KarenSeirApi;
  session: AuthSession | null;
  /** false until the stored session has been read (one tick after mount); show no «وارد شوید» and start no search before it. */
  ready: boolean;
  devLogin(email: string): Promise<AuthSession>;
  requestOtp(tenant: string, identifier: string): ReturnType<KarenSeirApi['requestOtp']>;
  register(mobile: string, name?: string): ReturnType<KarenSeirApi['register']>;
  verifyOtp(tenant: string, challenge: string, code: string): Promise<AuthSession>;
  verifyMfa(tenant: string, ticket: string, factor: { code?: string; recovery_code?: string }): Promise<AuthSession>;
  passwordLogin(tenant: string, identifier: string, password: string): Promise<AuthSession>;
  logout(): Promise<void>;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const api = useMemo(() => new KarenSeirApi(), []);
  const [session, setSession] = useState<AuthSession | null>(null);
  const [ready, setReady] = useState(false);
  useEffect(()=>{const handle=window.setTimeout(()=>{setSession(api.getSession());setReady(true)},0);return()=>window.clearTimeout(handle)},[api]);
  const value = useMemo<AuthContextValue>(() => ({
    api, session, ready,
    async devLogin(email) { const next = await api.devLogin(email); setSession(next); return next; },
    requestOtp(tenant, identifier) { return api.requestOtp(tenant, identifier); },
    register(mobile, name) { return api.register(mobile, name); },
    async verifyOtp(tenant, challenge, code) { const next = await api.verifyOtp(tenant, challenge, code); setSession(next); return next; },
    async verifyMfa(tenant, ticket, factor) { const next = await api.verifyMfa(tenant, ticket, factor); setSession(next); return next; },
    async passwordLogin(tenant, identifier, password) { const next = await api.passwordLogin(tenant, identifier, password); setSession(next); return next; },
    async logout() { const pending=api.logout(); setSession(null); await pending; },
  }), [api, session, ready]);
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const value = useContext(AuthContext);
  if (!value) throw new Error('AuthProvider is required');
  return value;
}
