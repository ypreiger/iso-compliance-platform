type Props = {
  en?: { title: string; text: string };
  he?: { title: string; text: string };
};

export function BilingualIsoPanel({ en, he }: Props) {
  return (
    <div className="bilingual">
      <div className="card iso-ltr">
        <h4>English (LTR)</h4>
        <strong>{en?.title}</strong>
        <p>{en?.text}</p>
      </div>
      <div className="card iso-rtl">
        <h4>עברית (RTL)</h4>
        <strong>{he?.title}</strong>
        <p>{he?.text}</p>
      </div>
    </div>
  );
}
