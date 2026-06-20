import { Navigate, Route, Routes } from 'react-router-dom';
import { AuthProvider, useAuth } from './auth';
import { AppLayout } from './components/AppLayout';
import { LoginPage } from './pages/LoginPage';
import { ProjectsPage } from './pages/ProjectsPage';
import { ProjectContextPage } from './pages/ProjectContextPage';
import { ProjectFindingsPage } from './pages/ProjectFindingsPage';
import { ProjectMappingPage } from './pages/ProjectMappingPage';
import { ProjectCoveragePage } from './pages/ProjectCoveragePage';
import { ProjectExportsPage } from './pages/ProjectExportsPage';
import { IsoViewerPage } from './pages/IsoViewerPage';
import { KnowledgeIsoPage, KnowledgeSamplesPage, KnowledgeTemplatesPage } from './pages/admin/KnowledgePages';
import { InstructionsPage } from './pages/admin/InstructionsPage';
import { UsersPage } from './pages/admin/UsersPage';
import { SettingsPage } from './pages/admin/SettingsPage';
import './styles.css';

function RequireAuth() {
  const { token } = useAuth();
  if (!token) return <Navigate to="/login" replace />;
  return <AppLayout />;
}

export default function App() {
  return (
    <AuthProvider>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/auth/callback" element={<LoginPage />} />
        <Route element={<RequireAuth />}>
          <Route path="/" element={<Navigate to="/projects" replace />} />
          <Route path="/projects" element={<ProjectsPage />} />
          <Route path="/projects/:id/context" element={<ProjectContextPage />} />
          <Route path="/projects/:id/findings" element={<ProjectFindingsPage />} />
          <Route path="/projects/:id/mapping" element={<ProjectMappingPage />} />
          <Route path="/projects/:id/coverage" element={<ProjectCoveragePage />} />
          <Route path="/projects/:id/exports" element={<ProjectExportsPage />} />
          <Route path="/iso" element={<IsoViewerPage />} />
          <Route path="/admin/knowledge/iso" element={<KnowledgeIsoPage />} />
          <Route path="/admin/knowledge/samples" element={<KnowledgeSamplesPage />} />
          <Route path="/admin/knowledge/templates" element={<KnowledgeTemplatesPage />} />
          <Route path="/admin/instructions" element={<InstructionsPage />} />
          <Route path="/admin/users" element={<UsersPage />} />
          <Route path="/admin/settings" element={<SettingsPage />} />
        </Route>
      </Routes>
    </AuthProvider>
  );
}
