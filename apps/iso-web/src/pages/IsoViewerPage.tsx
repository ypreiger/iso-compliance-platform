import { useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useAuth } from '../auth';
import { api, Clause } from '../api';

export function IsoViewerPage() {
  const { t, i18n } = useTranslation();
  const { token } = useAuth();
  const [standards, setStandards] = useState<string[]>(['ISO9001']);
  const [standard, setStandard] = useState('ISO9001');
  const [lang, setLang] = useState<'en' | 'he'>(() =>
    (i18n.language?.startsWith('he') ? 'he' : 'en'));
  const [q, setQ] = useState('');
  const [clauses, setClauses] = useState<Clause[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);

  useEffect(() => {
    if (!token) return;
    api.iso.standards(token).then((r) => {
      if (r.standards.length) {
        setStandards(r.standards);
        setStandard((s) => (r.standards.includes(s) ? s : r.standards[0]));
      }
    });
  }, [token]);

  useEffect(() => {
    const uiLang = i18n.language?.startsWith('he') ? 'he' : 'en';
    setLang(uiLang);
  }, [i18n.language]);

  useEffect(() => {
    if (!token) return;
    api.iso.clauses(token, standard, lang, q).then((r) => {
      setClauses(r.clauses);
      setSelectedId(r.clauses[0]?.clause_id ?? null);
    });
  }, [token, standard, lang, q]);

  const selected = useMemo(
    () => clauses.find((c) => c.clause_id === selectedId) ?? null,
    [clauses, selectedId],
  );

  return (
    <section className="iso-viewer">
      <header className="iso-toolbar">
        <h1>{t('iso.title')}</h1>
        <div className="iso-controls">
          <label>
            {t('iso.standard')}
            <select value={standard} onChange={(e) => setStandard(e.target.value)}>
              {standards.map((s) => <option key={s} value={s}>{s}</option>)}
            </select>
          </label>
          <label>
            {t('iso.language')}
            <select value={lang} onChange={(e) => setLang(e.target.value as 'en' | 'he')}>
              <option value="en">{t('iso.english')}</option>
              <option value="he">{t('iso.hebrew')}</option>
            </select>
          </label>
          <label>
            {t('iso.search')}
            <input value={q} onChange={(e) => setQ(e.target.value)} placeholder={t('iso.searchPlaceholder')} />
          </label>
        </div>
      </header>
      <div className="iso-layout">
        <aside className="iso-clause-list">
          <ul>
            {clauses.map((c) => (
              <li key={c.clause_id}>
                <button
                  type="button"
                  className={`iso-clause-btn${c.clause_id === selectedId ? ' active' : ''}`}
                  onClick={() => setSelectedId(c.clause_id)}
                >
                  <span className="iso-clause-id">{c.clause_id}</span>
                  <span className="iso-clause-title">{c.title}</span>
                  {c.fallback && <span className="iso-fallback-badge">{t('iso.fallbackEn')}</span>}
                </button>
              </li>
            ))}
          </ul>
          {!clauses.length && <p className="iso-empty">{t('iso.empty')}</p>}
        </aside>
        <article className={`iso-content ${lang === 'he' ? 'iso-rtl' : 'iso-ltr'}`}>
          {selected ? (
            <>
              <h2>
                <span className="iso-clause-id">{selected.clause_id}</span>
                {" "}{selected.title}
              </h2>
              {selected.fallback && (
                <p className="iso-fallback-note">{t('iso.fallbackNote')}</p>
              )}
              {selected.text.split('\n\n').map((para) => (
                <p key={para.slice(0, 24)}>{para}</p>
              ))}
            </>
          ) : (
            <p className="iso-empty">{t('iso.pickClause')}</p>
          )}
        </article>
      </div>
    </section>
  );
}
