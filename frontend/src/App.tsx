import { Routes, Route, Navigate } from 'react-router-dom'
import { Layout } from './components/Layout'
import { ProjectsPage } from './pages/ProjectsPage'
import { ProjectDetailPage } from './pages/ProjectDetailPage'
import { NichesPage } from './pages/NichesPage'
import { OAuthCallbackPage } from './pages/OAuthCallbackPage'
import { OAuthYouTubeChannelSelectPage } from './pages/OAuthYouTubeChannelSelectPage'

function App() {
  return (
    <Layout>
      <Routes>
        <Route path="/" element={<Navigate to="/projects" replace />} />
        <Route path="/projects" element={<ProjectsPage />} />
        <Route path="/projects/:projectId" element={<ProjectDetailPage />} />
        <Route path="/niches" element={<NichesPage />} />
        <Route path="/oauth/callback" element={<OAuthCallbackPage />} />
        <Route path="/oauth/youtube-channel-select" element={<OAuthYouTubeChannelSelectPage />} />
      </Routes>
    </Layout>
  )
}

export default App
