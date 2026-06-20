const API_BASE = import.meta.env.VITE_API_URL || '/api';

export type User = { id: string; email: string; roles: string[] };

function headers(token?: string): HeadersInit {
  const h: HeadersInit = { 'Content-Type': 'application/json' };
  if (token) h['Authorization'] = `Bearer ${token}`;
  return h;
}

async function req<T>(path: string, token?: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, { ...init, headers: { ...headers(token), ...init?.headers } });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || res.statusText);
  }
  return res.json();
}

export const api = {
  authConfig: () => req<{ google_enabled: boolean; dev_mode: boolean }>('/auth/config'),
  devLogin: (email: string) =>
    req<{ access_token: string; user: User }>('/auth/dev-login', undefined, {
      method: 'POST',
      body: JSON.stringify({ email, name: email.split('@')[0] }),
    }),
  googleCallback: (code: string, token?: string) =>
    req<{ access_token: string; user: User }>('/auth/google/callback', token, {
      method: 'POST',
      body: JSON.stringify({ code }),
    }),
  me: (token: string) => req<User>('/auth/me', token),
  projects: {
    list: (t: string) => req<{ projects: Record<string, unknown>[] }>('/v1/projects', t),
    create: (t: string, body: object) =>
      req('/v1/projects', t, { method: 'POST', body: JSON.stringify(body) }),
    get: (t: string, id: string) => req(`/v1/projects/${id}`, t),
    context: (t: string, id: string, context: object) =>
      req(`/v1/projects/${id}/context`, t, { method: 'PUT', body: JSON.stringify({ context }) }),
  },
  findings: {
    list: (t: string, pid: string) => req<{ findings: { id: string; finding_text: string }[] }>(`/v1/projects/${pid}/findings`, t),
    add: (t: string, pid: string, text: string) =>
      req(`/v1/projects/${pid}/findings`, t, {
        method: 'POST',
        body: JSON.stringify({ finding_text: text }),
      }),
    bulk: (t: string, pid: string, findings: string[]) =>
      req(`/v1/projects/${pid}/findings/bulk`, t, {
        method: 'POST',
        body: JSON.stringify({ findings }),
      }),
  },
  mapping: {
    list: (t: string, pid: string) => req<{ items: { finding: { id: string; finding_text: string }; mappings: { id: string; clause_id: string; clause_title: string; relevance_pct: number; severity: string }[] }[] }>(`/v1/projects/${pid}/mapping`, t),
    runAuto: (t: string, pid: string) =>
      req(`/v1/projects/${pid}/mapping/run-auto`, t, { method: 'POST' }),
    approve: (t: string, pid: string) =>
      req(`/v1/projects/${pid}/mapping/approve`, t, { method: 'POST' }),
    add: (t: string, pid: string, body: object) =>
      req(`/v1/projects/${pid}/mapping`, t, { method: 'POST', body: JSON.stringify(body) }),
    delete: (t: string, pid: string, mid: string) =>
      req(`/v1/projects/${pid}/mapping/${mid}`, t, { method: 'DELETE' }),
  },
  coverage: {
    list: (t: string, pid: string) => req<{ coverage: { standard: string; clause_id: string; status: string }[] }>(`/v1/projects/${pid}/coverage`, t),
    set: (t: string, pid: string, body: object) =>
      req(`/v1/projects/${pid}/coverage`, t, { method: 'PUT', body: JSON.stringify(body) }),
  },
  exports: {
    create: (t: string, pid: string, format: string) =>
      req(`/v1/projects/${pid}/exports`, t, {
        method: 'POST',
        body: JSON.stringify({ format, locale: 'he' }),
      }),
  },
  iso: {
    standards: (t: string) => req<{ standards: string[] }>('/v1/iso/standards', t),
    clauses: (t: string, standard: string, language: string, q = '') =>
      req<{ clauses: Clause[] }>(
        `/v1/iso/clauses?standard=${standard}&language=${language}&q=${encodeURIComponent(q)}`,
        t,
      ),
    bilingual: (t: string, standard: string, clauseId: string) =>
      req<{ locales: Record<string, { title: string; text: string; direction: string }> }>(
        `/v1/iso/clauses/${clauseId}/bilingual?standard=${standard}`,
        t,
      ),
  },
  users: {
    list: (t: string) => req<{ users: UserRow[] }>('/admin/users', t),
    create: (t: string, body: object) =>
      req('/admin/users', t, { method: 'POST', body: JSON.stringify(body) }),
  },
  corpus: {
    list: (t: string, type: string) => req(`/admin/corpus/${type}`, t),
    register: (t: string, type: string, body: object) =>
      req(`/admin/corpus/${type}`, t, { method: 'POST', body: JSON.stringify(body) }),
  },
  instructions: {
    list: (t: string) => req('/admin/instructions', t),
    get: (t: string, stage: string) => req(`/admin/instructions/${stage}`, t),
    publish: (t: string, body: object) =>
      req('/admin/instructions', t, { method: 'POST', body: JSON.stringify(body) }),
  },
};

export type Clause = {
  clause_id: string;
  title: string;
  text: string;
  language: string;
  direction: string;
};

export type UserRow = User & { name: string; is_active: boolean; roles: string[] };

export function googleLoginUrl(clientRedirect: string): string {
  const params = new URLSearchParams({
    client_id: import.meta.env.VITE_GOOGLE_CLIENT_ID || '',
    redirect_uri: clientRedirect,
    response_type: 'code',
    scope: 'openid email profile',
    access_type: 'online',
    prompt: 'select_account',
  });
  return `https://accounts.google.com/o/oauth2/v2/auth?${params}`;
}
