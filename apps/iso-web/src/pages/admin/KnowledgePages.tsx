import { useEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useAuth } from '../../auth';
import { api, type UploadResult } from '../../api';

const API_BASE = import.meta.env.VITE_API_URL || '/api';

function downloadFile(token: string, fileId: string, filename: string) {
  fetch(`${API_BASE}/admin/corpus/files/${fileId}`, {
    headers: { Authorization: `Bearer ${token}` },
  })
    .then((res) => {
      if (!res.ok) throw new Error(res.statusText);
      return res.blob();
    })
    .then((blob) => {
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = filename;
      a.click();
      URL.revokeObjectURL(url);
    })
    .catch(console.error);
}

const STANDARDS = ['ISO9001', 'ISO14001', 'ISO45001', 'ISO13485'];

function ValidationSummary({ v }: { v?: UploadResult['validation'] }) {
  if (!v) return null;
  const ok = v.passed;
  return (
    <div className={`validation-summary ${ok ? 'val-ok' : 'val-warn'}`}>
      <strong>{ok ? '✓ Validation passed' : '⚠ Validation issues'}</strong>
      {' · '}RAG coverage: {Math.round(v.rag_hit_rate * 100)}%
      {' · '}Phrase match: {Math.round(v.phrase_hit_rate * 100)}%
      {' · '}{v.total_clauses} clauses indexed
    </div>
  );
}

function CorpusPage({ type, titleKey }: { type: string; titleKey: string }) {
  const { t } = useTranslation();
  const { token } = useAuth();
  const fileRef = useRef<HTMLInputElement>(null);
  const [docs, setDocs] = useState<Record<string, unknown>[]>([]);
  const [clauseCounts, setClauseCounts] = useState<Record<string, unknown>[]>([]);
  const [chunks, setChunks] = useState(0);
  const [standard, setStandard] = useState('ISO9001');
  const [language, setLanguage] = useState<'en' | 'he' | 'both'>('en');
  const [edition, setEdition] = useState('2015');
  const [replaceExisting, setReplaceExisting] = useState(true);
  const [translateDir, setTranslateDir] = useState<'en-he' | 'he-en'>('en-he');
  const [uploading, setUploading] = useState(false);
  const [lastUpload, setLastUpload] = useState<UploadResult | null>(null);
  const [msg, setMsg] = useState('');
  const [err, setErr] = useState('');

  const load = () => {
    if (!token) return;
    api.corpus.list(token, type).then((r) => {
      const row = r as {
        documents: Record<string, unknown>[];
        indexed_chunks: number;
        clause_counts?: Record<string, unknown>[];
      };
      setDocs(row.documents || []);
      setChunks(row.indexed_chunks || 0);
      setClauseCounts(row.clause_counts || []);
    });
  };
  useEffect(() => { load(); }, [token, type]);

  const upload = () => {
    if (!token || !fileRef.current?.files?.[0]) return;
    setErr('');
    setMsg('');
    setLastUpload(null);
    setUploading(true);
    const form = new FormData();
    form.append('file', fileRef.current.files[0]);
    form.append('standard', standard);
    form.append('language', language);
    form.append('edition', edition);
    form.append('replace_previous', replaceExisting ? 'true' : 'false');
    setMsg(t('admin.uploading'));
    api.corpus.uploadIso(token, form)
      .then((r) => {
        setLastUpload(r);
        const base =
          r.language === 'both' && r.clauses_en != null
            ? t('admin.uploadDoneBoth', { en: r.clauses_en, he: r.clauses_he, chunks: r.rag_chunks })
            : t('admin.uploadDone', { count: r.clauses_imported ?? 0, chunks: r.rag_chunks ?? 0 });
        const method = r.parse_method ? ` [${r.parse_method}]` : '';
        const warn = r.warnings?.length ? ` (${r.warnings.length} warnings)` : '';
        setMsg(base + method + warn);
        load();
      })
      .catch((e: Error) => setErr(e.message))
      .finally(() => setUploading(false));
  };

  const translate = () => {
    if (!token) return;
    setErr('');
    const [source_language, target_language] =
      translateDir === 'en-he' ? (['en', 'he'] as const) : (['he', 'en'] as const);
    api.corpus.translateIso(token, { standard, edition, source_language, target_language })
      .then((r) => {
        setMsg(
          t('admin.translateDoneDir', {
            count: r.translated_clauses,
            from: source_language.toUpperCase(),
            to: target_language.toUpperCase(),
          }),
        );
        load();
      })
      .catch((e: Error) => setErr(e.message));
  };

  const deleteStandard = () => {
    if (!token) return;
    if (!window.confirm(t('admin.deleteStandardConfirm', { standard }))) return;
    setErr('');
    api.corpus.deleteStandard(token, { standard })
      .then((r) => {
        setMsg(t('admin.deleteStandardDone', { standard: r.standard, count: r.clauses_removed }));
        setLastUpload(null);
        load();
      })
      .catch((e: Error) => setErr(e.message));
  };

  if (type !== 'iso') {
    return (
      <section>
        <h1>{t(titleKey)}</h1>
        <p>Indexed chunks: {chunks}</p>
      </section>
    );
  }

  return (
    <section className="corpus-admin">
      <h1>{t(titleKey)}</h1>
      <p>{t('admin.isoUploadHelp')}</p>
      {err && <div className="alert">{err}</div>}
      {msg && <div className="alert alert-ok">{msg}</div>}
      {lastUpload && <ValidationSummary v={lastUpload.validation} />}

      <div className="corpus-upload-form">
        <label>
          {t('iso.standard')}
          <select value={standard} onChange={(e) => setStandard(e.target.value)}>
            {STANDARDS.map((s) => <option key={s} value={s}>{s}</option>)}
          </select>
        </label>
        <label>
          {t('iso.language')}
          <select value={language} onChange={(e) => setLanguage(e.target.value as 'en' | 'he' | 'both')}>
            <option value="en">{t('iso.english')}</option>
            <option value="he">{t('iso.hebrew')}</option>
            <option value="both">{t('admin.bilingualBundle')}</option>
          </select>
        </label>
        <label>
          {t('admin.edition')}
          <input value={edition} onChange={(e) => setEdition(e.target.value)} />
        </label>
        <label>
          {t('admin.isoFile')}
          <input
            ref={fileRef}
            type="file"
            accept={
              language === 'both'
                ? '.json'
                : '.pdf,.doc,.docx,.json,application/pdf,application/msword,application/vnd.openxmlformats-officedocument.wordprocessingml.document'
            }
          />
        </label>
        <label className="checkbox-row">
          <input
            type="checkbox"
            checked={replaceExisting}
            onChange={(e) => setReplaceExisting(e.target.checked)}
          />
          {t('admin.replaceExisting')}
        </label>
        <p className="form-hint">
          {replaceExisting ? t('admin.replaceExistingHelp') : t('admin.mergeExistingHelp')}
        </p>
        <label>
          {t('admin.translateDirection')}
          <select value={translateDir} onChange={(e) => setTranslateDir(e.target.value as 'en-he' | 'he-en')}>
            <option value="en-he">{t('admin.translateEnHe')}</option>
            <option value="he-en">{t('admin.translateHeEn')}</option>
          </select>
        </label>
        <div className="button-row">
          <button type="button" className="btn" onClick={upload} disabled={uploading}>
            {uploading ? t('admin.uploading') : t('admin.uploadIso')}
          </button>
          <button type="button" className="btn" onClick={translate}>{t('admin.translateRun')}</button>
          <button type="button" className="btn btn-danger" onClick={deleteStandard}>
            {t('admin.deleteStandard')}
          </button>
        </div>
      </div>

      <h2>{t('admin.clauseInventory')}</h2>
      <table>
        <thead>
          <tr>
            <th>{t('iso.standard')}</th>
            <th>{t('iso.language')}</th>
            <th>{t('admin.clauses')}</th>
            <th>{t('admin.edition')}</th>
          </tr>
        </thead>
        <tbody>
          {clauseCounts.map((row) => (
            <tr key={`${row.standard}-${row.language}`}>
              <td>{String(row.standard)}</td>
              <td>{String(row.language)}</td>
              <td>{String(row.c)}</td>
              <td>{String(row.edition || '')}</td>
            </tr>
          ))}
        </tbody>
      </table>

      <h2>{t('admin.uploadHistory')}</h2>
      <p style={{ fontSize: 13, color: '#6c757d', marginBottom: '0.75rem' }}>
        RAG chunks indexed: <strong>{chunks}</strong> · Original files stored and downloadable below
      </p>
      <table>
        <thead>
          <tr>
            <th>File</th>
            <th>Standard</th>
            <th>Lang</th>
            <th>Edition</th>
            <th>Status</th>
            <th>Download</th>
          </tr>
        </thead>
        <tbody>
          {docs.map((d) => {
            const meta = (d.metadata as Record<string, unknown>) || {};
            const fileId = meta.file_id as string | undefined;
            const filename = String(d.name);
            return (
              <tr key={String(d.id)}>
                <td>{filename}</td>
                <td>{(d.standards as string[] | undefined)?.join(', ') || '—'}</td>
                <td>{String(d.language)}</td>
                <td>{String(d.edition)}</td>
                <td>
                  <span style={{
                    padding: '2px 7px', borderRadius: 8, fontSize: 11, fontWeight: 700,
                    background: d.status === 'ready' ? '#d4edda' : d.status === 'failed' ? '#f8d7da' : '#fff3cd',
                    color: d.status === 'ready' ? '#155724' : d.status === 'failed' ? '#721c24' : '#856404',
                  }}>
                    {String(d.status)}
                  </span>
                </td>
                <td>
                  {fileId && token ? (
                    <button
                      type="button"
                      className="link-btn"
                      style={{ fontSize: 13 }}
                      onClick={() => downloadFile(token, fileId, filename)}
                    >
                      ⬇ {filename.split('.').pop()?.toUpperCase()}
                    </button>
                  ) : (
                    <span style={{ color: '#aaa', fontSize: 12 }}>—</span>
                  )}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </section>
  );
}

export const KnowledgeIsoPage = () => <CorpusPage type="iso" titleKey="admin.isoCorpus" />;
export const KnowledgeSamplesPage = () => <CorpusPage type="samples" titleKey="admin.samples" />;
export const KnowledgeTemplatesPage = () => <CorpusPage type="templates" titleKey="admin.templates" />;
