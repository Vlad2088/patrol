// Каркас: роутинг, auth-контекст, layout со сайдбаром
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";

import "./styles.css";
import { authStore } from "./api/client";
import { AuthCtx, type AuthUser } from "./auth";
import LoginPage from "./pages/LoginPage";
import DashboardPage from "./pages/DashboardPage";
import ObjectsPage from "./pages/ObjectsPage";
import RoutesPage from "./pages/RoutesPage";
import ShiftsPage from "./pages/ShiftsPage";
import GuardsPage from "./pages/GuardsPage";
import PatrolsPage from "./pages/PatrolsPage";
import ReportsPage from "./pages/ReportsPage";
import AuditPage from "./pages/AuditPage";
import Layout from "./components/Layout";

const queryClient = new QueryClient({
  defaultOptions: { queries: { retry: 1, staleTime: 30_000 } },
});

function readUser(): AuthUser | null {
  const raw = localStorage.getItem("patrol_user");
  if (!raw || !authStore.access) return null;
  try {
    return JSON.parse(raw);
  } catch {
    return null;
  }
}

function Shell() {
  const user = readUser();
  const logout = () => {
    authStore.clear();
    window.location.href = "/login";
  };
  return (
    <AuthCtx.Provider value={{ user, logout }}>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/" element={user ? <Layout /> : <Navigate to="/login" replace />}>
          <Route index element={<DashboardPage />} />
          <Route path="objects" element={<ObjectsPage />} />
          <Route path="routes" element={<RoutesPage />} />
          <Route path="shifts" element={<ShiftsPage />} />
          <Route path="guards" element={<GuardsPage />} />
          <Route path="patrols" element={<PatrolsPage />} />
          <Route path="reports" element={<ReportsPage />} />
          <Route path="audit" element={<AuditPage />} />
        </Route>
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </AuthCtx.Provider>
  );
}

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Shell />
      </BrowserRouter>
    </QueryClientProvider>
  </StrictMode>
);
