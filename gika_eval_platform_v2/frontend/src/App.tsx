import { NavLink, Routes, Route, Navigate } from "react-router-dom";
import DashboardPage from "./pages/DashboardPage";
import DatasetsPage from "./pages/DatasetsPage";
import NewRunPage from "./pages/NewRunPage";
import ComparePage from "./pages/ComparePage";
import RunDetailPage from "./pages/RunDetailPage";

export default function App() {
  return (
    <div className="app-layout">
      <aside className="sidebar">
        <div className="sidebar-brand">
          GIKA Eval
          <small>Evaluation Platform</small>
        </div>
        <nav>
          <NavLink to="/analytics">Analytics</NavLink>
          <NavLink to="/datasets">Datasets</NavLink>
          <NavLink to="/new-run">New Run</NavLink>
          <NavLink to="/compare">Compare</NavLink>
        </nav>
      </aside>
      <main className="main-content">
        <Routes>
          <Route path="/" element={<Navigate to="/analytics" replace />} />
          <Route path="/analytics" element={<DashboardPage />} />
          <Route path="/analytics/:runId" element={<RunDetailPage />} />
          <Route path="/datasets" element={<DatasetsPage />} />
          <Route path="/new-run" element={<NewRunPage />} />
          <Route path="/compare" element={<ComparePage />} />
        </Routes>
      </main>
    </div>
  );
}
