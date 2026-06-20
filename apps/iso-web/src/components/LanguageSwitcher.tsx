import { useTranslation } from 'react-i18next';

export function LanguageSwitcher() {
  const { i18n, t } = useTranslation();
  return (
    <span aria-label={t('app.language')}>
      <button type="button" className="btn" onClick={() => { i18n.changeLanguage('en'); localStorage.setItem('iso-ui-lang', 'en'); }}>
        EN
      </button>
      <button type="button" className="btn" onClick={() => { i18n.changeLanguage('he'); localStorage.setItem('iso-ui-lang', 'he'); }}>
        HE
      </button>
    </span>
  );
}
