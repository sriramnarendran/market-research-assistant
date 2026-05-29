import { Route, Routes } from "react-router-dom";

import { AppLayout } from "@/components/AppLayout";
import { AdminRoute, ProtectedRoute } from "@/components/ProtectedRoute";
import { AdminPage } from "@/pages/AdminPage";
import { CreateRunPage } from "@/pages/CreateRunPage";
import { LoginPage } from "@/pages/LoginPage";
import { RunDetailPage } from "@/pages/RunDetailPage";
import { RunListPage } from "@/pages/RunListPage";
export function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route element={<ProtectedRoute />}>
        <Route element={<AppLayout />}>
          <Route path="/" element={<CreateRunPage />} />
          <Route path="/runs" element={<RunListPage />} />
          <Route path="/runs/:runId" element={<RunDetailPage />} />
        </Route>
      </Route>
      <Route element={<AdminRoute />}>
        <Route element={<AppLayout />}>
          <Route path="/admin" element={<AdminPage />} />
        </Route>
      </Route>
    </Routes>
  );
}
