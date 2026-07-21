import { Navigate, Route, Routes } from "react-router-dom";
import { AppShell } from "./components/AppShell";
import { ApplicationsPage } from "./pages/ApplicationsPage";
import { CandidateProfilePage } from "./pages/CandidateProfilePage";
import { ControlsPage } from "./pages/ControlsPage";
import { DashboardPage } from "./pages/DashboardPage";
import { HistoryPage } from "./pages/HistoryPage";
import { JobsPage } from "./pages/JobsPage";

export default function App() {
  return (
    <AppShell>
      <Routes>
        <Route path="/" element={<DashboardPage />} />
        <Route path="/jobs" element={<JobsPage />} />
        <Route path="/history" element={<HistoryPage />} />
        <Route path="/applications" element={<ApplicationsPage />} />
        <Route path="/profile" element={<CandidateProfilePage />} />
        <Route path="/controls" element={<ControlsPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </AppShell>
  );
}
