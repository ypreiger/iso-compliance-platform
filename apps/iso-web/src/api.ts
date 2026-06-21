const API_BASE = import.meta.env.VITE_API_URL || '/api';

export type User = {
  id: string;
  email: string;
  roles: string[];
  can_access_projects?: boolean;
};

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

export type AuthConfig = {
  saml_enabled: boolean;
  google_enabled: boolean;
  google_client_id: string;
  dev_mode: boolean;
};

export const api = {
  authConfig: () => req<AuthConfig>('/auth/config'),
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
  googleIdToken: (credential: string) =>
    req<{ access_token: string; user: User }>('/auth/google/id-token', undefined, {
      method: 'POST',
      body: JSON.stringify({ credential }),
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
    updateRole: (t: string, userId: string, roles: string[]) =>
      req<UserRow>(`/admin/users/${userId}`, t, {
        method: 'PATCH',
        body: JSON.stringify({ roles }),
      }),
    deactivate: (t: string, userId: string) =>
      req(`/admin/users/${userId}`, t, {
        method: 'PATCH',
        body: JSON.stringify({ is_active: false }),
      }),
  },
  corpus: {
    list: (t: string, type: string) => req(`/admin/corpus/${type}`, t),
    register: (t: string, type: string, body: object) =>
      req(`/admin/corpus/${type}`, t, { method: 'POST', body: JSON.stringify(body) }),
    uploadIso: (t: string, form: FormData) =>
      fetch(`${API_BASE}/admin/corpus/iso/upload`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${t}` },
        body: form,
      }).then(async (res) => {
        if (!res.ok) {
          const err = await res.json().catch(() => ({ detail: res.statusText }));
          throw new Error(err.detail || res.statusText);
        }
        return res.json() as Promise<UploadResult>;
      }),
    translateIso: (t: string, body: {
      standard: string;
      edition?: string;
      source_language?: string;
      target_language?: string;
    }) =>
      req<{ translated_clauses: number; source_language: string; target_language: string }>(
        '/admin/corpus/iso/translate', t, { method: 'POST', body: JSON.stringify(body) }),
    deleteStandard: (t: string, body: { standard: string; languages?: string[] }) =>
      req<{ standard: string; clauses_removed: number; languages: string[] }>(
        '/admin/corpus/iso/delete-standard', t, { method: 'POST', body: JSON.stringify(body) }),
  },
  documents: {
    list: (t: string) => req<{ files: CorpusFile[] }>('/admin/corpus/files', t),
    downloadUrl: (fileId: string) => `${API_BASE}/admin/corpus/files/${fileId}`,
    delete: (t: string, fileId: string) =>
      req('/admin/corpus/files/' + fileId, t, { method: 'DELETE' }),
  },
  instructions: {
    list: (t: string) => req('/admin/instructions', t),
    get: (t: string, stage: string) => req(`/admin/instructions/${stage}`, t),
    publish: (t: string, body: object) =>
      req('/admin/instructions', t, { method: 'POST', body: JSON.stringify(body) }),
  },
};

export type ValidationResult = {
  standard: string;
  language: string;
  total_clauses: number;
  sampled: number;
  rag_hit_rate: number;
  phrase_hit_rate: number;
  passed: boolean;
};

export type UploadResult = {
  clauses_imported: number;
  rag_chunks: number;
  parse_method?: string;
  language?: string;
  clauses_en?: number;
  clauses_he?: number;
  warnings?: string[];
  validation?: ValidationResult;
  file_id?: string;
};

export type CorpusFile = {
  id: string;
  corpus_id: string;
  filename: string;
  content_type: string;
  size_bytes: number;
  created_at: string;
  standards: string[];
  language: string;
  edition: string;
  parse_method: string;
  clauses_imported?: number;
  validation?: ValidationResult;
};

export type Clause = {
  clause_id: string;
  title: string;
  text: string;
  language: string;
  direction: string;
  fallback?: boolean;
  edition?: string;
};

export type UserRow = User & { name: string; is_active: boolean; roles: string[] };

export function samlLoginHref(): string {
  return `${API_BASE}/auth/saml/login`;
}

export function googleLoginHref(): string {
  return `${API_BASE}/auth/google/login`;
}
