import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useAuth } from '../../auth';
import { api, UserRow } from '../../api';

const ROLES = ['viewer', 'consultant', 'supervisor', 'admin'];

const ROLE_COLOR: Record<string, string> = {
  admin: '#c62828',
  supervisor: '#1565c0',
  consultant: '#2e7d32',
  viewer: '#6c757d',
};

export function UsersPage() {
  const { t } = useTranslation();
  const { token } = useAuth();
  const [users, setUsers] = useState<UserRow[]>([]);
  const [email, setEmail] = useState('');
  const [name, setName] = useState('');
  const [role, setRole] = useState('consultant');
  const [err, setErr] = useState('');
  const [msg, setMsg] = useState('');

  const load = () => {
    if (token) api.users.list(token).then((r) => setUsers(r.users));
  };
  useEffect(() => { load(); }, [token]);

  const invite = () => {
    if (!token || !email) return;
    setErr(''); setMsg('');
    api.users.create(token, { email, name, roles: [role] })
      .then(() => { setEmail(''); setName(''); setMsg(`Invited ${email}`); load(); })
      .catch((e: Error) => setErr(e.message));
  };

  const changeRole = (user: UserRow, newRole: string) => {
    if (!token) return;
    setErr('');
    api.users.updateRole(token, user.id, [newRole])
      .then(() => load())
      .catch((e: Error) => setErr(e.message));
  };

  const toggleActive = (user: UserRow) => {
    if (!token) return;
    setErr('');
    api.users.deactivate(token, user.id)
      .then(() => load())
      .catch((e: Error) => setErr(e.message));
  };

  return (
    <section>
      <h1 style={{ marginBottom: '1rem' }}>{t('app.users')}</h1>

      {err && <div className="alert" style={{ marginBottom: '1rem' }}>{err}</div>}
      {msg && <div className="alert alert-ok" style={{ marginBottom: '1rem' }}>{msg}</div>}

      {/* Invite form */}
      <div style={{ background: '#f8f9fa', border: '1px solid #dee2e6', borderRadius: 10, padding: '1.25rem', marginBottom: '1.5rem', display: 'flex', flexWrap: 'wrap', gap: '0.75rem', alignItems: 'flex-end' }}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
          <label style={{ fontSize: 12, fontWeight: 600, color: '#495057' }}>{t('admin.email')}</label>
          <input
            style={{ padding: '8px 12px', border: '2px solid #dee2e6', borderRadius: 8, fontSize: 14, minWidth: 220 }}
            placeholder="user@example.com"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && invite()}
          />
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
          <label style={{ fontSize: 12, fontWeight: 600, color: '#495057' }}>{t('admin.name')}</label>
          <input
            style={{ padding: '8px 12px', border: '2px solid #dee2e6', borderRadius: 8, fontSize: 14, minWidth: 160 }}
            placeholder="Full name"
            value={name}
            onChange={(e) => setName(e.target.value)}
          />
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
          <label style={{ fontSize: 12, fontWeight: 600, color: '#495057' }}>{t('admin.roles')}</label>
          <select
            style={{ padding: '8px 12px', border: '2px solid #dee2e6', borderRadius: 8, fontSize: 14 }}
            value={role}
            onChange={(e) => setRole(e.target.value)}
          >
            {ROLES.map((r) => <option key={r} value={r}>{r}</option>)}
          </select>
        </div>
        <button type="button" className="btn" onClick={invite}>{t('admin.inviteUser')}</button>
      </div>

      {/* Users table */}
      <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 14 }}>
        <thead>
          <tr style={{ background: '#f8f9fa' }}>
            <th style={{ padding: '10px 14px', textAlign: 'start', borderBottom: '2px solid #dee2e6', fontWeight: 700 }}>{t('admin.email')}</th>
            <th style={{ padding: '10px 14px', textAlign: 'start', borderBottom: '2px solid #dee2e6', fontWeight: 700 }}>{t('admin.name')}</th>
            <th style={{ padding: '10px 14px', textAlign: 'start', borderBottom: '2px solid #dee2e6', fontWeight: 700 }}>{t('admin.roles')}</th>
            <th style={{ padding: '10px 14px', textAlign: 'start', borderBottom: '2px solid #dee2e6', fontWeight: 700 }}>Status</th>
            <th style={{ padding: '10px 14px', textAlign: 'start', borderBottom: '2px solid #dee2e6', fontWeight: 700 }}>Actions</th>
          </tr>
        </thead>
        <tbody>
          {users.map((u) => {
            const currentRole = u.roles?.[0] ?? 'viewer';
            return (
              <tr key={u.id} style={{ borderBottom: '1px solid #f0f0f0', opacity: u.is_active === false ? 0.5 : 1 }}>
                <td style={{ padding: '10px 14px' }}>{u.email}</td>
                <td style={{ padding: '10px 14px' }}>{u.name}</td>
                <td style={{ padding: '10px 14px' }}>
                  <select
                    value={currentRole}
                    onChange={(e) => changeRole(u, e.target.value)}
                    style={{
                      padding: '4px 8px',
                      borderRadius: 6,
                      border: `2px solid ${ROLE_COLOR[currentRole] || '#dee2e6'}`,
                      color: ROLE_COLOR[currentRole] || '#212529',
                      fontWeight: 600,
                      fontSize: 13,
                      background: 'white',
                      cursor: 'pointer',
                    }}
                  >
                    {ROLES.map((r) => <option key={r} value={r}>{r}</option>)}
                  </select>
                </td>
                <td style={{ padding: '10px 14px' }}>
                  <span style={{
                    padding: '2px 8px', borderRadius: 10, fontSize: 12, fontWeight: 700,
                    background: u.is_active === false ? '#f8d7da' : '#d4edda',
                    color: u.is_active === false ? '#721c24' : '#155724',
                  }}>
                    {u.is_active === false ? 'inactive' : 'active'}
                  </span>
                </td>
                <td style={{ padding: '10px 14px' }}>
                  {u.is_active !== false && (
                    <button
                      type="button"
                      onClick={() => toggleActive(u)}
                      style={{ padding: '3px 10px', fontSize: 12, border: '1px solid #dee2e6', borderRadius: 6, background: '#f8f9fa', cursor: 'pointer' }}
                    >
                      Deactivate
                    </button>
                  )}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </section>
  );
}
