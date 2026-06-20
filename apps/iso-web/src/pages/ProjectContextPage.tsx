import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useParams } from 'react-router-dom';
import { useAuth } from '../auth';
import { api } from '../api';

export function ProjectContextPage() {
  const { t } = useTranslation();
  const { id } = useParams();
  const { token } = useAuth();
  const [industry, setIndustry] = useState('');
  const [sites, setSites] = useState('1');
  const [processes, setProcesses] = useState('');

  useEffect(() => {
    if (!token || !id) return;
    api.projects.get(token, id).then((p) => {
      const row = p as { context?: Record<string, unknown> };
      const ctx = row.context || {};
      setIndustry(String(ctx.industry || ''));
      setSites(String(ctx.sites || 1));
      setProcesses(String(ctx.processes || ''));
    });
  }, [token, id]);

  return (
    <section>
      <h1>{t('context.title')}</h1>
      <label>{t('context.industry')}</label>
      <input value={industry} onChange={(e) => setIndustry(e.target.value)} />
      <label>{t('context.sites')}</label>
      <input value={sites} onChange={(e) => setSites(e.target.value)} />
      <label>{t('context.processes')}</label>
      <textarea value={processes} onChange={(e) => setProcesses(e.target.value)} rows={4} />
      <button type="button" className="btn" onClick={() => token && id && api.projects.context(token, id, { industry, sites: Number(sites), processes })}>
        {t('app.save')}
      </button>
    </section>
  );
}
