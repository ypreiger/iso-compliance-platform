import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import { useAuth } from '../auth';
import { api } from '../api';

export function ProjectsPage() {
  const { t } = useTranslation();
  const { token } = useAuth();
  const [projects, setProjects] = useState<Record<string, unknown>[]>([]);
  const [name, setName] = useState('');

  const load = () => { if (token) api.projects.list(token).then((r) => setProjects(r.projects)); };
  useEffect(() => { load(); }, [token]);

  return (
    <section>
      <h1>{t('projects.title')}</h1>
      <input placeholder={t('projects.name')} value={name} onChange={(e) => setName(e.target.value)} />
      <button type="button" className="btn" onClick={() => token && api.projects.create(token, { name, standards: ['ISO9001'] }).then(() => { setName(''); load(); })}>
        {t('projects.new')}
      </button>
      <table>
        <thead><tr><th>{t('projects.name')}</th><th>{t('projects.status')}</th><th>Actions</th></tr></thead>
        <tbody>
          {projects.map((p) => (
            <tr key={String(p.id)}>
              <td>{String(p.name)}</td>
              <td>{String(p.status)}</td>
              <td>
                <Link to={`/projects/${p.id}/context`}>Context</Link> ·
                <Link to={`/projects/${p.id}/findings`}> Findings</Link> ·
                <Link to={`/projects/${p.id}/mapping`}> Mapping</Link> ·
                <Link to={`/projects/${p.id}/coverage`}> Coverage</Link> ·
                <Link to={`/projects/${p.id}/exports`}> Exports</Link>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}
