import { Navigate, Outlet, useLocation } from "react-router-dom";

import { AppLoadingScreen } from "@/components/AppLoadingScreen";
import { useAuth } from "@/hooks/useAuth";

/** Redirect to login when /auth/me returns 401 (dev bypass still works server-side). */
export function ProtectedRoute() {
  const { user, isLoading } = useAuth();
  const location = useLocation();

  if (isLoading) {
    return <AppLoadingScreen message="Checking session…" />;
  }

  if (!user) {
    return <Navigate to="/login" state={{ from: location.pathname }} replace />;
  }

  return <Outlet />;
}

export function AdminRoute() {
  const { user, isLoading, isAdmin } = useAuth();
  const location = useLocation();

  if (isLoading) {
    return <AppLoadingScreen message="Checking session…" />;
  }

  if (!user) {
    return <Navigate to="/login" state={{ from: location.pathname }} replace />;
  }

  if (!isAdmin) {
    return <Navigate to="/" replace />;
  }

  return <Outlet />;
}
