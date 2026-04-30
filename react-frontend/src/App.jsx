import { Routes, Route } from 'react-router-dom';
import Layout from './components/Layout';
import HomePage from './pages/HomePage';
import ScanProgressPage from './pages/ScanProgressPage';
import AnalysisPage from './pages/AnalysisPage';
import FileDetailPage from './pages/FileDetailPage';
import DashboardPage from './pages/DashboardPage';
import AboutPage from './pages/AboutPage';

function App() {
  return (
    <Layout>
      <Routes>
        <Route path="/" element={<HomePage />} />
        <Route path="/scan/:scanId" element={<ScanProgressPage />} />
        <Route path="/analysis/:scanId" element={<AnalysisPage />} />
        <Route path="/file/:fileId" element={<FileDetailPage />} />
        <Route path="/dashboard" element={<DashboardPage />} />
        <Route path="/about" element={<AboutPage />} />
      </Routes>
    </Layout>
  );
}

export default App;
