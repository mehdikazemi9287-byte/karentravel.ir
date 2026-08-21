'use client';

import { createContext, useContext, useEffect, useMemo, useState } from 'react';
import { AuthSession, KarenSeirApi } from './karenseir-client';

type AuthContextValue = {
  api: KarenSeirApi;
  session: AuthSession | null;
  devLogin(email: string): Promise<AuthSession>;
  requestOtp(tenant: string, identifier: string): ReturnType<KarenSeirApi['requestOtp']>;
  verifyOtp(tenant: string, challenge: string, code: string): Promise<AuthSession>;
  logout(): Promise<void>;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const api = useMemo(() => new KarenSeirApi(), []);
  const [session, setSession] = useState<AuthSession | null>(null);
  useEffect(()=>{const handle=window.setTimeout(()=>setSession(api.getSession()),0);return()=>window.clearTimeout(handle)},[api]);
  const value = useMemo<AuthContextValue>(() => ({
    api, session,
    async devLogin(email) { const next = await api.devLogin(email); setSession(next); return next; },
    requestOtp(tenant, identifier) { return api.requestOtp(tenant, identifier); },
    async verifyOtp(tenant, challenge, code) { const next = await api.verifyOtp(tenant, challenge, code); setSession(next); return next; },
    async logout() { await api.logout(); setSession(null); },
  }), [api, session]);
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const value = useContext(AuthContext);
  if (!value) throw new Error('AuthProvider is required');
  return value;
}
