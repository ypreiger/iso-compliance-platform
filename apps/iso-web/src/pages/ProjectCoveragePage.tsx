import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useParams } from 'react-router-dom';
import { useAuth } from '../auth';
import { api } from '../api';

export function ProjectCoveragePage() {
  const { t } = useTranslation();
  const { id } = useParams();
  const { token } = useAuth();
  const [rows, setRows] = useState<{ standard: string; clause_id: string; status: string }[]>([]);
  const [clauseId, setClauseId] = useState('4.1');
  const [status, setStatus] = useState('not_checked');

  useEffect(() => {
    if (token && id) api.coverage.list(token, id).then((r) => setRows(r.coverage));
  }, [token, id]);

  return (
    <section>
      <h1>{t('coverage.title')}</h1>
      <ul>{rows.map((r) => <li key={r.clause_id}>{r.standard} {r.clause_id}: {r.status}</li>)}</ul>
      <input value={clauseId} onChange={(e) => setClauseId(e.target.value)} />
      <select value={status} onChange={(e) => setStatus(e.target.value)}>
        <option value="not_checked">{t('coverage.notChecked')}</option>
        <option value="na">{t('coverage.na')}</option>
        <option value="compliant">{t('coverage.compliant')}</option>
        <option value="nc">{t('coverage.nc')}</option>
      </select>
      <button type="button" className="btn" onClick={() => token && id && api.coverage.set(token, id, { standard: 'ISO9001', clause_id: clauseId, status }).then(() => api.coverage.list(token, id).then((r) => setRows(r.coverage)))}>
        {t('app.save')}
      </button>
    </section>
  );
}
