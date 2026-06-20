import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useParams } from 'react-router-dom';
import { useAuth } from '../auth';
import { api } from '../api';
import { BilingualIsoPanel } from '../components/BilingualIsoPanel';

type MapItem = {
  finding: { id: string; finding_text: string };
  mappings: { id: string; clause_id: string; clause_title: string; relevance_pct: number; severity: string }[];
};

export function ProjectMappingPage() {
  const { t } = useTranslation();
  const { id } = useParams();
  const { token } = useAuth();
  const [items, setItems] = useState<MapItem[]>([]);
  const [selected, setSelected] = useState<MapItem | null>(null);
  const [bilingual, setBilingual] = useState<{ en?: { title: string; text: string }; he?: { title: string; text: string } }>({});
  const [clauseId, setClauseId] = useState('4.1');

  const load = () => {
    if (token && id) {
      api.mapping.list(token, id).then((r) => {
        const list = r.items;
        setItems(list);
        if (!selected && list.length) setSelected(list[0]);
      });
    }
  };
  useEffect(() => { load(); }, [token, id]);

  useEffect(() => {
    if (!token || !selected?.mappings[0]) return;
    api.iso.bilingual(token, 'ISO9001', selected.mappings[0].clause_id).then((r) => {
      setBilingual({ en: r.locales.en, he: r.locales.he });
    });
  }, [token, selected]);

  return (
    <section>
      <h1>{t('mapping.title')}</h1>
      <button type="button" className="btn" onClick={() => token && id && api.mapping.runAuto(token, id).then(load)}>{t('mapping.runAuto')}</button>
      <button type="button" className="btn" onClick={() => token && id && api.mapping.approve(token, id).then(load)}>{t('mapping.approveAll')}</button>
      <div className="grid3" style={{ marginTop: 16 }}>
        <div className="card">
          <h3>{t('mapping.findings')}</h3>
          <ul>{items.map((it) => (
            <li key={it.finding.id}>
              <button type="button" className="btn" onClick={() => setSelected(it)}>{it.finding.finding_text.slice(0, 60)}</button>
            </li>
          ))}</ul>
        </div>
        <div className="card">
          <h3>Pairs</h3>
          {selected?.mappings.map((m) => (
            <div key={m.id}>
              {m.clause_id} — {m.relevance_pct}% / {m.severity}
              <button type="button" className="btn" onClick={() => token && id && api.mapping.delete(token, id, m.id).then(load)}>×</button>
            </div>
          ))}
          <input value={clauseId} onChange={(e) => setClauseId(e.target.value)} placeholder={t('mapping.addPair')} />
          <button type="button" className="btn" onClick={() => selected && token && id && api.mapping.add(token, id, {
            finding_id: selected.finding.id, standard: 'ISO9001', clause_id: clauseId, clause_title: clauseId, relevance_pct: 75, severity: 'minor',
          }).then(load)}>{t('app.add')}</button>
        </div>
        <div className="card">
          <h3>{t('mapping.clausePreview')}</h3>
          <BilingualIsoPanel {...bilingual} />
        </div>
      </div>
    </section>
  );
}
