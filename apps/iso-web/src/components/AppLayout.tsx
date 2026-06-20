import { Link, Outlet, useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { useAuth } from '../auth';
import { LanguageSwitcher } from './LanguageSwitcher';

export function AppLayout() {
  const { t } = useTranslation();
  const { user, logout, isAdmin } = useAuth();
  const nav = useNavigate();

  return (
    <div className="layout">
      <nav className="sidebar">
        <strong>{t('app.title')}</strong>
        <Link to="/projects">{t('app.projects')}</Link>
        <Link to="/iso">{t('app.isoViewer')}</Link>
        {isAdmin && (
          <>
            <Link to="/admin/knowledge/iso">{t('admin.isoCorpus')}</Link>
            <Link to="/admin/knowledge/samples">{t('admin.samples')}</Link>
            <Link to="/admin/knowledge/templates">{t('admin.templates')}</Link>
            <Link to="/admin/instructions">{t('app.instructions')}</Link>
            <Link to="/admin/users">{t('app.users')}</Link>
            <Link to="/admin/settings">{t('app.settings')}</Link>
          </>
        )}
      </nav>
      <div className="main">
        <div className="topbar">
          <LanguageSwitcher />
          <span>{user?.email}</span>
          <button type="button" className="btn" onClick={() => { logout(); nav('/login'); }}>
            {t('app.logout')}
          </button>
        </div>
        <Outlet />
      </div>
    </div>
  );
}
