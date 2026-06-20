import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { api, googleLoginUrl } from '../api';
import { useAuth } from '../auth';
import { LanguageSwitcher } from '../components/LanguageSwitcher';

export function LoginPage() {
  const { t } = useTranslation();
  const { loginDev, loginToken, token } = useAuth();
  const nav = useNavigate();
  const [params] = useSearchParams();
  const [email, setEmail] = useState('yaakovpreiger@gmail.com');
  const [err, setErr] = useState('');
  const [cfg, setCfg] = useState({ google_enabled: false, dev_mode: true });

  useEffect(() => { if (token) nav('/projects'); }, [token, nav]);

  useEffect(() => {
    api.authConfig().then(setCfg).catch(() => undefined);
    const code = params.get('code');
    if (code) {
      api.googleCallback(code).then((r) => {
        loginToken(r.access_token, r.user);
        nav('/projects');
      }).catch((e: Error) => setErr(e.message));
    }
  }, [params, loginToken, nav]);

  const redirectUri = `${window.location.origin}/login`;

  return (
    <div className="main" style={{ maxWidth: 480, margin: '2rem auto' }}>
      <h1>{t('login.title')}</h1>
      <LanguageSwitcher />
      {err && <div className="alert">{err}</div>}
      {cfg.google_enabled && (
        <button type="button" className="btn" onClick={() => { window.location.href = googleLoginUrl(redirectUri); }}>
          {t('login.google')}
        </button>
      )}
      {cfg.dev_mode && (
        <div style={{ marginTop: 24 }}>
          <label>{t('login.email')}</label>
          <input value={email} onChange={(e) => setEmail(e.target.value)} />
          <button type="button" className="btn" onClick={() => loginDev(email).then(() => nav('/projects')).catch((e: Error) => setErr(e.message))}>
            {t('login.dev')}
          </button>
        </div>
      )}
    </div>
  );
}
