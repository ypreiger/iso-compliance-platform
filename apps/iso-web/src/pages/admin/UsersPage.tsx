import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useAuth } from '../../auth';
import { api, UserRow } from '../../api';

const ROLES = ['admin', 'consultant', 'supervisor'];

export function UsersPage() {
  const { t } = useTranslation();
  const { token } = useAuth();
  const [users, setUsers] = useState<UserRow[]>([]);
  const [email, setEmail] = useState('');
  const [name, setName] = useState('');
  const [role, setRole] = useState('consultant');

  const load = () => { if (token) api.users.list(token).then((r) => setUsers(r.users)); };
  useEffect(() => { load(); }, [token]);

  return (
    <section>
      <h1>{t('app.users')}</h1>
      <input placeholder={t('admin.email')} value={email} onChange={(e) => setEmail(e.target.value)} />
      <input placeholder={t('admin.name')} value={name} onChange={(e) => setName(e.target.value)} />
      <select value={role} onChange={(e) => setRole(e.target.value)}>
        {ROLES.map((r) => <option key={r} value={r}>{r}</option>)}
      </select>
      <button type="button" className="btn" onClick={() => token && api.users.create(token, { email, name, roles: [role] }).then(() => { setEmail(''); load(); })}>
        {t('admin.inviteUser')}
      </button>
      <table>
        <thead><tr><th>{t('admin.email')}</th><th>{t('admin.name')}</th><th>{t('admin.roles')}</th></tr></thead>
        <tbody>{users.map((u) => <tr key={u.id}><td>{u.email}</td><td>{u.name}</td><td>{u.roles?.join(', ')}</td></tr>)}</tbody>
      </table>
    </section>
  );
}
