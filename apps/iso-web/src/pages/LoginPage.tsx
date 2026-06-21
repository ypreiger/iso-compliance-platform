import { useEffect, useState } from 'react';
import { GoogleOAuthProvider, GoogleLogin } from '@react-oauth/google';
import { useTranslation } from 'react-i18next';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { api, AuthConfig, samlLoginHref } from '../api';
import { useAuth } from '../auth';
import { LanguageSwitcher } from '../components/LanguageSwitcher';

export function LoginPage() {
  const { t } = useTranslation();
  const { loginDev, loginToken, token } = useAuth();
  const nav = useNavigate();
  const [params] = useSearchParams();
  const [email, setEmail] = useState('yaakovpreiger@gmail.com');
  const [err, setErr] = useState('');
  const [cfgErr, setCfgErr] = useState('');
  const [cfg, setCfg] = useState<AuthConfig | null>(null);

  useEffect(() => {
    if (token) nav('/iso', { replace: true });
  }, [token, nav]);

  useEffect(() => {
    api.authConfig()
      .then((next) => {
        setCfg(next);
        setCfgErr('');
      })
      .catch(() => setCfgErr('Unable to load auth configuration from API'));
  }, []);

  useEffect(() => {
    const accessToken = params.get('access_token');
    if (accessToken && !token) {
      api.me(accessToken)
        .then((user) => {
          loginToken(accessToken, user);
          nav('/iso', { replace: true });
        })
        .catch((e: Error) => setErr(e.message));
      return;
    }
    const code = params.get('code');
    if (!code || token) return;
    api.googleCallback(code)
      .then((r) => {
        loginToken(r.access_token, r.user);
        nav('/iso', { replace: true });
      })
      .catch((e: Error) => setErr(e.message));
  }, [params, loginToken, nav, token]);

  const googleReady = cfg !== null && cfg.google_enabled && !!cfg.google_client_id;

  const loginCard = (
    <div className="login-card">
      <LanguageSwitcher />
      <h1>{t('login.title')}</h1>
      <p className="login-sub">{t('login.subtitle')}</p>
      {err && <div className="alert">{err}</div>}
      {cfgErr && <div className="alert">{cfgErr}</div>}
      {googleReady ? (
        <div className="google-signin-wrap">
          <GoogleLogin
            onSuccess={(res) => {
              if (!res.credential) {
                setErr('Google sign-in failed');
                return;
              }
              api.googleIdToken(res.credential)
                .then((r) => {
                  loginToken(r.access_token, r.user);
                  nav('/iso', { replace: true });
                })
                .catch((e: Error) => setErr(e.message));
            }}
            onError={() => setErr('Google sign-in failed')}
            useOneTap={false}
            theme="outline"
            size="large"
            text="signin_with"
            shape="rectangular"
          />
        </div>
      ) : cfg !== null ? (
        <div className="alert alert-warn">{t('login.googleUnavailable')}</div>
      ) : (
        <div className="alert alert-warn">Loading authentication configuration...</div>
      )}
      {!googleReady && cfg && cfg.saml_enabled && (
        <p className="login-alt">
          <button type="button" className="link-btn" onClick={() => { window.location.href = samlLoginHref(); }}>
            {t('login.workspaceSso')}
          </button>
        </p>
      )}
      {cfg && cfg.dev_mode && (
        <div className="login-dev">
          <label>{t('login.email')}</label>
          <input value={email} onChange={(e) => setEmail(e.target.value)} />
          <button
            type="button"
            className="btn"
            onClick={() => loginDev(email).then(() => nav('/iso', { replace: true })).catch((e: Error) => setErr(e.message))}
          >
            {t('login.dev')}
          </button>
        </div>
      )}
    </div>
  );

  return (
    <div className="login-page">
      {googleReady ? (
        <GoogleOAuthProvider clientId={cfg.google_client_id}>{loginCard}</GoogleOAuthProvider>
      ) : (
        loginCard
      )}
    </div>
  );
}
