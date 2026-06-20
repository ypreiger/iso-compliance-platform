import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useAuth } from '../../auth';
import { api } from '../../api';

function CorpusPage({ type, titleKey }: { type: string; titleKey: string }) {
  const { t } = useTranslation();
  const { token } = useAuth();
  const [docs, setDocs] = useState<Record<string, unknown>[]>([]);
  const [chunks, setChunks] = useState(0);
  const [name, setName] = useState('');

  const load = () => {
    if (!token) return;
    api.corpus.list(token, type).then((r) => {
      const row = r as { documents: Record<string, unknown>[]; indexed_chunks: number };
      setDocs(row.documents || []);
      setChunks(row.indexed_chunks || 0);
    });
  };
  useEffect(() => { load(); }, [token, type]);

  return (
    <section>
      <h1>{t(titleKey)}</h1>
      <p>Indexed chunks: {chunks}</p>
      <input value={name} onChange={(e) => setName(e.target.value)} />
      <button type="button" className="btn" onClick={() => token && api.corpus.register(token, type, { doc_type: type, name, standards: ['ISO9001'] }).then(load)}>{t('app.add')}</button>
      <table>
        <thead><tr><th>Name</th><th>Status</th></tr></thead>
        <tbody>{docs.map((d) => <tr key={String(d.id)}><td>{String(d.name)}</td><td>{String(d.status)}</td></tr>)}</tbody>
      </table>
    </section>
  );
}

export const KnowledgeIsoPage = () => <CorpusPage type="iso" titleKey="admin.isoCorpus" />;
export const KnowledgeSamplesPage = () => <CorpusPage type="samples" titleKey="admin.samples" />;
export const KnowledgeTemplatesPage = () => <CorpusPage type="templates" titleKey="admin.templates" />;
