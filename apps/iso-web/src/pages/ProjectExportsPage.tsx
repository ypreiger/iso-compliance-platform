import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useParams } from 'react-router-dom';
import { useAuth } from '../auth';
import { api } from '../api';

export function ProjectExportsPage() {
  const { t } = useTranslation();
  const { id } = useParams();
  const { token } = useAuth();
  const [approved, setApproved] = useState(false);
  const [msg, setMsg] = useState('');

  useEffect(() => {
    if (token && id) api.projects.get(token, id).then((p) => setApproved(!!(p as { mapping_approved?: boolean }).mapping_approved));
  }, [token, id]);

  return (
    <section>
      <h1>{t('exports.title')}</h1>
      {!approved && <div className="alert-warn">{t('exports.requiresApproval')}</div>}
      <button type="button" className="btn" disabled={!approved} onClick={() => token && id && api.exports.create(token, id, 'xlsx').then((r) => setMsg(JSON.stringify(r))).catch((e: Error) => setMsg(e.message))}>{t('exports.excel')}</button>
      <button type="button" className="btn" disabled={!approved} onClick={() => token && id && api.exports.create(token, id, 'docx').then((r) => setMsg(JSON.stringify(r))).catch((e: Error) => setMsg(e.message))}>{t('exports.docx')}</button>
      {msg && <pre>{msg}</pre>}
    </section>
  );
}
