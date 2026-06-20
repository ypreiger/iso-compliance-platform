import i18n from 'i18next';
import { initReactI18next } from 'react-i18next';
import en from './en.json';
import he from './he.json';

export function applyDocumentDirection(lng: string) {
  const dir = lng === 'he' ? 'rtl' : 'ltr';
  document.documentElement.lang = lng;
  document.documentElement.dir = dir;
}

i18n.use(initReactI18next).init({
  resources: { en: { translation: en }, he: { translation: he } },
  lng: localStorage.getItem('iso-ui-lang') || 'en',
  fallbackLng: 'en',
  interpolation: { escapeValue: false },
});

applyDocumentDirection(i18n.language);
i18n.on('languageChanged', applyDocumentDirection);

export default i18n;
