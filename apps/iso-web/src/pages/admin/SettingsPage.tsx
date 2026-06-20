import { useTranslation } from 'react-i18next';

export function SettingsPage() {
  const { t } = useTranslation();
  return (
    <section>
      <h1>{t('app.settings')}</h1>
      <ul>
        <li>Admin bootstrap: yaakovpreiger@gmail.com, valeria.preiger@gmail.com</li>
        <li>LLM aliases: iso-mapper, iso-report, iso-embed</li>
        <li>Google OAuth: GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET on iso-api</li>
      </ul>
    </section>
  );
}
