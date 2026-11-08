import { useEffect } from "react";
import { BrowserRouter, Navigate, Route, Routes, useLocation } from "react-router-dom";
import { ErrorBoundary } from "./components/ErrorBoundary";
import { Sidebar } from "./components/Sidebar/Sidebar";
import { NoticeToast } from "./components/ui/NoticeToast";
import { useBridge } from "./hooks/useBridge";
import { GitContext } from "./pages/GitContext";
import { IgnoreManager } from "./pages/IgnoreManager";
import { Logs } from "./pages/Logs";
import { Overview } from "./pages/Overview";
import { Sessions } from "./pages/Sessions";
import { Settings } from "./pages/Settings";

function ScrollToTop() {
  const location = useLocation();
  useEffect(() => {
    window.scrollTo(0, 0);
  }, [location.pathname]);
  return null;
}

function Shell() {
  useBridge();

  return (
    <div className="min-h-screen lg:pl-[264px]">
      <a
        href="#main"
        className="focus-ring sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-4 focus:z-[70] focus:rounded-lg focus:bg-duck-400 focus:px-3 focus:py-2 focus:text-xs focus:font-semibold focus:text-ink-950"
      >
        Skip to content
      </a>
      <Sidebar />
      <main id="main" className="mx-auto w-full max-w-[1500px] px-4 py-6 sm:px-6 lg:px-8 lg:py-9">
        <ScrollToTop />
        <Routes>
          <Route path="/" element={<Overview />} />
          <Route path="/sessions" element={<Sessions />} />
          <Route path="/git" element={<GitContext />} />
          <Route path="/ignore" element={<IgnoreManager />} />
          <Route path="/settings" element={<Settings />} />
          <Route path="/logs" element={<Logs />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </main>
      <NoticeToast />
    </div>
  );
}

export default function App() {
  return (
    <ErrorBoundary>
      <BrowserRouter>
        <Shell />
      </BrowserRouter>
    </ErrorBoundary>
  );
}
