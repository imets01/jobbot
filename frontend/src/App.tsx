import { Navigate, Route, Routes } from "react-router-dom";
import { AppShell } from "./components/AppShell";
import { ApplicationsPage } from "./pages/ApplicationsPage";
import { CandidateProfilePage } from "./pages/CandidateProfilePage";
import { DashboardPage } from "./pages/DashboardPage";
import { HistoryPage } from "./pages/HistoryPage";
import { JobsPage } from "./pages/JobsPage";
import { SearchPage } from "./pages/SearchPage";

export default function App() {
  return (
    <AppShell>
      <Routes>
        <Route path="/" element={<SearchPage />} />
        <Route path="/dashboard" element={<DashboardPage />} />
        <Route path="/jobs" element={<JobsPage />} />
        <Route path="/history" element={<HistoryPage />} />
        <Route path="/applications" element={<ApplicationsPage />} />
        <Route path="/profile" element={<CandidateProfilePage />} />
        <Route path="/controls" element={<Navigate to="/" replace />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </AppShell>
  );
}
