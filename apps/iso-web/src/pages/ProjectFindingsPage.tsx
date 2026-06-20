import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useParams } from 'react-router-dom';
import { useAuth } from '../auth';
import { api } from '../api';

export function ProjectFindingsPage() {
  const { t } = useTranslation();
  const { id } = useParams();
  const { token } = useAuth();
  const [findings, setFindings] = useState<{ id: string; finding_text: string }[]>([]);
  const [text, setText] = useState('');
  const [bulk, setBulk] = useState('');

  const load = () => {
    if (token && id) {
      api.findings.list(token, id).then((r) => setFindings(r.findings));
    }
  };
  useEffect(() => { load(); }, [token, id]);

  return (
    <section>
      <h1>{t('findings.title')}</h1>
      <textarea value={text} onChange={(e) => setText(e.target.value)} placeholder={t('findings.add')} />
      <button type="button" className="btn" onClick={() => token && id && api.findings.add(token, id, text).then(() => { setText(''); load(); })}>{t('app.add')}</button>
      <textarea value={bulk} onChange={(e) => setBulk(e.target.value)} placeholder={t('findings.paste')} rows={6} />
      <button type="button" className="btn" onClick={() => token && id && api.findings.bulk(token, id, bulk.split('\n')).then(() => { setBulk(''); load(); })}>{t('app.add')}</button>
      <ul>{findings.map((f) => <li key={f.id}>{f.finding_text}</li>)}</ul>
    </section>
  );
}
