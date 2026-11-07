import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { Layout } from "./components/Layout";
import { ToastProvider } from "./components/ui";
import "./index.css";
import { SessionProvider, useSession } from "./lib/session";
import Analytics from "./pages/Analytics";
import Auditor from "./pages/Auditor";
import History from "./pages/History";
import Knowledge from "./pages/Knowledge";
import Landing from "./pages/Landing";
import Overview from "./pages/Overview";
import Review from "./pages/Review";
import Settings from "./pages/Settings";
import SubmissionPage from "./pages/Submission";
import Visual from "./pages/Visual";

function RequireWorkspace({ children }: { children: React.ReactNode }) {
  const { session } = useSession();
  return session ? <>{children}</> : <Navigate to="/" replace />;
}

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <SessionProvider>
      <ToastProvider>
        <BrowserRouter>
          <Routes>
            <Route path="/" element={<Landing />} />
            <Route path="/app" element={<RequireWorkspace><Layout /></RequireWorkspace>}>
              <Route index element={<Navigate to="overview" replace />} />
              <Route path="overview" element={<Overview />} />
              <Route path="auditor" element={<Auditor />} />
              <Route path="review" element={<Review />} />
              <Route path="submissions/:id" element={<SubmissionPage />} />
              <Route path="knowledge" element={<Knowledge />} />
              <Route path="visual" element={<Visual />} />
              <Route path="analytics" element={<Analytics />} />
              <Route path="history" element={<History />} />
              <Route path="settings" element={<Settings />} />
            </Route>
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </BrowserRouter>
      </ToastProvider>
    </SessionProvider>
  </React.StrictMode>,
);
