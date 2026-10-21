import { NavLink, Route, Routes } from "react-router-dom";
import BackendStatus from "./components/BackendStatus.jsx";
import Analysis from "./pages/Analysis.jsx";
import Dashboard from "./pages/Dashboard.jsx";
import History from "./pages/History.jsx";
import QkdLab from "./pages/QkdLab.jsx";
import SecuritySimulator from "./pages/SecuritySimulator.jsx";
import Transfer from "./pages/Transfer.jsx";

export const PAGES = [
  { path: "/", label: "Dashboard", element: <Dashboard /> },
  { path: "/qkd-lab", label: "QKD Laboratory", element: <QkdLab /> },
  { path: "/security", label: "Security Simulator", element: <SecuritySimulator /> },
  { path: "/transfer", label: "Transaction Transfer", element: <Transfer /> },
  { path: "/analysis", label: "Experimental Analysis", element: <Analysis /> },
  { path: "/history", label: "History & Security Logs", element: <History /> },
];

export default function App() {
  return (
    <div className="min-h-screen bg-page text-ink">
      <header className="border-b border-line bg-surface">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-2 px-4 py-3 sm:px-6">
          <div>
            <h1 className="text-lg font-bold tracking-tight">Q-Secure Banking Network</h1>
            <p className="text-xs text-ink-2">
              Educational BB84 + AES-256-GCM simulation · fictional banks · no real transfers · not production security
            </p>
          </div>
          <BackendStatus />
        </div>
        <nav className="mx-auto flex max-w-7xl gap-1 overflow-x-auto px-4 sm:px-6" aria-label="Main">
          {PAGES.map((page) => (
            <NavLink
              key={page.path}
              to={page.path}
              end
              className={({ isActive }) =>
                `-mb-px whitespace-nowrap border-b-2 px-3 py-2 text-sm font-medium ${
                  isActive ? "border-accent text-ink" : "border-transparent text-ink-2 hover:text-ink"
                }`
              }
            >
              {page.label}
            </NavLink>
          ))}
        </nav>
      </header>
      <main className="mx-auto max-w-7xl px-4 py-6 sm:px-6">
        <Routes>
          {PAGES.map((page) => <Route key={page.path} path={page.path} element={page.element} />)}
          <Route path="*" element={<p className="text-ink-2">Page not found.</p>} />
        </Routes>
      </main>
    </div>
  );
}
