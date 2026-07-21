import {
  BriefcaseBusiness,
  ChartNoAxesCombined,
  ClipboardList,
  FileClock,
  Menu,
  Moon,
  PlayCircle,
  Sun,
  UserRoundCog,
  X,
} from "lucide-react";
import { useEffect, useState, type ReactNode } from "react";
import { NavLink } from "react-router-dom";
import { ActiveRunBanner } from "./ActiveRunBanner";

const links = [
  { to: "/", label: "Dashboard", icon: ChartNoAxesCombined, end: true },
  { to: "/jobs", label: "Jobs", icon: BriefcaseBusiness },
  { to: "/history", label: "Analysis History", icon: FileClock },
  { to: "/applications", label: "Applications", icon: ClipboardList },
  { to: "/profile", label: "Candidate Profile", icon: UserRoundCog },
  { to: "/controls", label: "Run Controls", icon: PlayCircle },
];

export function AppShell({ children }: { children: ReactNode }) {
  const [menuOpen, setMenuOpen] = useState(false);
  const [dark, setDark] = useState(document.documentElement.dataset.theme === "dark");

  useEffect(() => {
    document.documentElement.dataset.theme = dark ? "dark" : "light";
  }, [dark]);

  return (
    <div className="app-shell">
      <aside className={`sidebar ${menuOpen ? "is-open" : ""}`}>
        <div className="brand">
          <span className="brand-mark">J</span>
          <div>
            <strong>Jobbot</strong>
            <span>Local career workspace</span>
          </div>
          <button className="icon-button mobile-only" onClick={() => setMenuOpen(false)} aria-label="Close navigation">
            <X size={19} />
          </button>
        </div>
        <nav aria-label="Primary navigation">
          {links.map(({ to, label, icon: Icon, end }) => (
            <NavLink
              key={to}
              to={to}
              end={end}
              onClick={() => setMenuOpen(false)}
              className={({ isActive }) => (isActive ? "nav-link active" : "nav-link")}
            >
              <Icon size={18} aria-hidden="true" />
              <span>{label}</span>
            </NavLink>
          ))}
        </nav>
        <div className="sidebar-footer">
          <span className="local-indicator"><i /> Local only</span>
          <p>Gemini credentials stay on this machine.</p>
        </div>
      </aside>
      {menuOpen && <button className="sidebar-scrim" aria-label="Close navigation" onClick={() => setMenuOpen(false)} />}
      <div className="app-main">
        <header className="topbar">
          <button className="icon-button menu-button" onClick={() => setMenuOpen(true)} aria-label="Open navigation">
            <Menu size={20} />
          </button>
          <div className="topbar-title">
            <strong>Career intelligence</strong>
            <span>Scrape · evaluate · apply</span>
          </div>
          <button className="theme-toggle" onClick={() => setDark((value) => !value)} aria-label={`Switch to ${dark ? "light" : "dark"} theme`}>
            {dark ? <Sun size={17} /> : <Moon size={17} />}
            <span>{dark ? "Light" : "Dark"}</span>
          </button>
        </header>
        <ActiveRunBanner />
        <main className="page-content">{children}</main>
      </div>
    </div>
  );
}
