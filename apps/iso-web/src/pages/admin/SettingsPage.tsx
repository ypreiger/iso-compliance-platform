import { useTranslation } from 'react-i18next';

export function SettingsPage() {
  const { t } = useTranslation();
  return (
    <section>
      <h1>{t('app.settings')}</h1>
      <ul>
        <li>Admin bootstrap: yaakov.preiger@think-21.com, yaakovpreiger@gmail.com, valeria.preiger@gmail.com</li>
        <li>LLM aliases: iso-mapper, iso-report, iso-embed</li>
        <li>Authentication: Google Workspace SAML (SAML_IDP_* / SAML_SP_* on iso-api)</li>
      </ul>
    </section>
  );
}
