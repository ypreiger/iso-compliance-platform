import React, { createContext, useContext, useEffect, useMemo, useState } from 'react';
import { api, User } from './api';

type AuthCtx = {
  token: string | null;
  user: User | null;
  loginDev: (email: string) => Promise<void>;
  loginToken: (token: string, user: User) => void;
  logout: () => void;
  isAdmin: boolean;
  canAccessProjects: boolean;
};

const Ctx = createContext<AuthCtx | null>(null);
const KEY = 'iso-auth-token';

const PROJECT_ROLES = new Set(['admin', 'consultant', 'supervisor']);

export function hasProjectAccess(user: User | null | undefined): boolean {
  if (!user) return false;
  if (typeof user.can_access_projects === 'boolean') return user.can_access_projects;
  return user.roles.some((r) => PROJECT_ROLES.has(r));
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [token, setToken] = useState<string | null>(() => localStorage.getItem(KEY));
  const [user, setUser] = useState<User | null>(null);

  useEffect(() => {
    if (!token) return;
    api.me(token).then(setUser).catch(() => {
      localStorage.removeItem(KEY);
      setToken(null);
    });
  }, [token]);

  const value = useMemo<AuthCtx>(
    () => ({
      token,
      user,
      loginDev: async (email: string) => {
        const r = await api.devLogin(email);
        localStorage.setItem(KEY, r.access_token);
        setToken(r.access_token);
        setUser(r.user);
      },
      loginToken: (t, u) => {
        localStorage.setItem(KEY, t);
        setToken(t);
        setUser(u);
      },
      logout: () => {
        localStorage.removeItem(KEY);
        setToken(null);
        setUser(null);
      },
      isAdmin: !!user?.roles.includes('admin'),
      canAccessProjects: hasProjectAccess(user),
    }),
    [token, user],
  );

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useAuth() {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error('AuthProvider missing');
  return ctx;
}
