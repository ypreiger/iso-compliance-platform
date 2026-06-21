import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useAuth } from '../../auth';
import { api, type CorpusFile } from '../../api';

function ValidationBadge({ v }: { v?: CorpusFile['validation'] }) {
  if (!v) return <span className="badge badge-grey">—</span>;
  const ok = v.passed;
  const label = ok
    ? `✓ ${Math.round(v.rag_hit_rate * 100)}% RAG`
    : `⚠ ${Math.round(v.rag_hit_rate * 100)}% RAG`;
  return (
    <span
      className={`badge ${ok ? 'badge-ok' : 'badge-warn'}`}
      title={`RAG hit ${Math.round(v.rag_hit_rate * 100)}%  phrase ${Math.round(v.phrase_hit_rate * 100)}%  clauses ${v.total_clauses}`}
    >
      {label}
    </span>
  );
}

function humanSize(bytes: number) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

export function DocumentsPage() {
  const { t } = useTranslation();
  const { token } = useAuth();
  const [files, setFiles] = useState<CorpusFile[]>([]);
  const [msg, setMsg] = useState('');
  const [err, setErr] = useState('');

  const load = () => {
    if (!token) return;
    api.documents.list(token).then((r) => setFiles(r.files)).catch((e: Error) => setErr(e.message));
  };

  useEffect(() => { load(); }, [token]);

  const del = (id: string, name: string) => {
    if (!token) return;
    if (!window.confirm(`Delete stored file "${name}"?`)) return;
    api.documents.delete(token, id).then(load).catch((e: Error) => setErr(e.message));
  };

  const download = (id: string, filename: string) => {
    const url = api.documents.downloadUrl(id);
    const a = document.createElement('a');
    a.href = url;
    a.setAttribute('download', filename);
    // Need auth header — open in new tab with bearer (modern browsers strip auth header on navigations)
    fetch(url, { headers: { Authorization: `Bearer ${token}` } })
      .then((res) => {
        if (!res.ok) throw new Error(res.statusText);
        return res.blob();
      })
      .then((blob) => {
        const objUrl = URL.createObjectURL(blob);
        a.href = objUrl;
        a.click();
        URL.revokeObjectURL(objUrl);
      })
      .catch((e: Error) => setErr(e.message));
  };

  return (
    <section className="corpus-admin">
      <h1>{t('admin.documentsTab')}</h1>
      <p>{t('admin.documentsHelp')}</p>
      {err && <div className="alert">{err}</div>}
      {msg && <div className="alert alert-ok">{msg}</div>}

      {files.length === 0 ? (
        <p className="empty-hint">{t('admin.noDocuments')}</p>
      ) : (
        <table className="doc-table">
          <thead>
            <tr>
              <th>{t('admin.fileName')}</th>
              <th>{t('iso.standard')}</th>
              <th>{t('iso.language')}</th>
              <th>{t('admin.edition')}</th>
              <th>{t('admin.parseMethod')}</th>
              <th>{t('admin.clauses')}</th>
              <th>{t('admin.validation')}</th>
              <th>{t('admin.fileSize')}</th>
              <th>{t('admin.uploadedAt')}</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {files.map((f) => (
              <tr key={f.id}>
                <td>
                  <button
                    className="link-btn"
                    onClick={() => download(f.id, f.filename)}
                    title="Download original file"
                  >
                    ⬇ {f.filename}
                  </button>
                </td>
                <td>{(f.standards || []).join(', ')}</td>
                <td>{f.language?.toUpperCase()}</td>
                <td>{f.edition}</td>
                <td>
                  <span className={`badge ${f.parse_method === 'llm' ? 'badge-ok' : 'badge-grey'}`}>
                    {f.parse_method || '—'}
                  </span>
                </td>
                <td>{f.clauses_imported ?? '—'}</td>
                <td><ValidationBadge v={f.validation} /></td>
                <td>{humanSize(f.size_bytes)}</td>
                <td>{new Date(f.created_at).toLocaleDateString()}</td>
                <td>
                  <button
                    className="btn btn-sm btn-danger"
                    onClick={() => del(f.id, f.filename)}
                  >
                    {t('admin.deleteFile')}
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}
