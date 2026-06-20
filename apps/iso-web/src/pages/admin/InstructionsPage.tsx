import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useAuth } from '../../auth';
import { api } from '../../api';

const STAGES = [
  'context_summarize', 'finding_normalize', 'iso_map_and_score', 'clause_coverage',
  'corrective_action_draft', 'ofi_instruction_draft', 'report_narrative',
];

export function InstructionsPage() {
  const { t } = useTranslation();
  const { token } = useAuth();
  const [stage, setStage] = useState(STAGES[0]);
  const [body, setBody] = useState('');

  useEffect(() => {
    if (!token) return;
    api.instructions.get(token, stage).then((r) => setBody(String((r as { body?: string }).body || ''))).catch(() => setBody(''));
  }, [token, stage]);

  return (
    <section>
      <h1>{t('app.instructions')}</h1>
      <select value={stage} onChange={(e) => setStage(e.target.value)}>
        {STAGES.map((s) => <option key={s} value={s}>{s}</option>)}
      </select>
      <textarea value={body} onChange={(e) => setBody(e.target.value)} rows={12} />
      <button type="button" className="btn" onClick={() => token && api.instructions.publish(token, { stage, body, locale: 'en' })}>Publish</button>
    </section>
  );
}
