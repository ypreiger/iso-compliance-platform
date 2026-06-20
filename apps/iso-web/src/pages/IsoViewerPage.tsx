import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useAuth } from '../auth';
import { api, Clause } from '../api';
import { BilingualIsoPanel } from '../components/BilingualIsoPanel';

export function IsoViewerPage() {
  const { t } = useTranslation();
  const { token } = useAuth();
  const [standard, setStandard] = useState('ISO9001');
  const [lang, setLang] = useState<'en' | 'he'>('en');
  const [q, setQ] = useState('');
  const [clauses, setClauses] = useState<Clause[]>([]);
  const [selected, setSelected] = useState<Clause | null>(null);
  const [bilingual, setBilingual] = useState<{ en?: { title: string; text: string }; he?: { title: string; text: string } }>({});

  useEffect(() => {
    if (token) api.iso.clauses(token, standard, lang, q).then((r) => setClauses(r.clauses));
  }, [token, standard, lang, q]);

  const pick = (c: Clause) => {
    setSelected(c);
    if (token) api.iso.bilingual(token, standard, c.clause_id).then((r) => setBilingual({ en: r.locales.en, he: r.locales.he }));
  };

  return (
    <section>
      <h1>{t('iso.title')}</h1>
      <select value={standard} onChange={(e) => setStandard(e.target.value)}>
        {['ISO9001', 'ISO14001', 'ISO45001', 'ISO13485'].map((s) => <option key={s} value={s}>{s}</option>)}
      </select>
      <select value={lang} onChange={(e) => setLang(e.target.value as 'en' | 'he')}>
        <option value="en">{t('iso.english')}</option>
        <option value="he">{t('iso.hebrew')}</option>
      </select>
      <input value={q} onChange={(e) => setQ(e.target.value)} placeholder={t('iso.search')} />
      <ul>{clauses.map((c) => (
        <li key={`${c.clause_id}-${c.language}`}>
          <button type="button" className="btn" onClick={() => pick(c)}>{c.clause_id} — {c.title}</button>
        </li>
      ))}</ul>
      {selected && (
        <>
          <h2>{t('iso.bilingual')}: {selected.clause_id}</h2>
          <div className={lang === 'he' ? 'iso-rtl' : 'iso-ltr'}>
            <strong>{selected.title}</strong>
            <p>{selected.text}</p>
          </div>
          <BilingualIsoPanel {...bilingual} />
        </>
      )}
    </section>
  );
}
