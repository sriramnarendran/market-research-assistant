import {
  History,
  LayoutDashboard,
  LogOut,
  Sparkles,
} from "lucide-react";
import { Link, Outlet, useLocation } from "react-router-dom";

import { AppBackground } from "@/components/AppBackground";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/hooks/useAuth";
import { cn } from "@/lib/utils";

const NAV = [
  { to: "/", label: "Research", icon: Sparkles, exact: true },
  { to: "/runs", label: "History", icon: History, exact: false },
] as const;

function userInitial(email: string): string {
  return (email[0] ?? "?").toUpperCase();
}

export function AppLayout() {
  const location = useLocation();
  const { user, isAdmin, logout } = useAuth();

  return (
    <div className="relative min-h-screen">
      <AppBackground />
      <header className="sticky top-0 z-40 border-b border-border/60 bg-background/70 backdrop-blur-xl">
        <div className="container flex h-14 items-center justify-between gap-4">
          <Link
            to="/"
            className="group flex items-center gap-2.5 font-semibold tracking-tight transition-opacity hover:opacity-90"
          >
            <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary text-primary-foreground shadow-sm">
              <Sparkles className="h-4 w-4" />
            </span>
            <span className="hidden sm:inline">Market Research Assistant</span>
            <span className="sm:hidden">MRA</span>
          </Link>

          <nav className="flex flex-1 items-center justify-end gap-1 sm:gap-2">
            {NAV.map((item) => {
              const active = item.exact
                ? location.pathname === item.to
                : location.pathname.startsWith(item.to);
              const Icon = item.icon;
              return (
                <Link
                  key={item.to}
                  to={item.to}
                  className={cn(
                    "inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-sm font-medium transition-colors",
                    active
                      ? "bg-primary/10 text-primary"
                      : "text-muted-foreground hover:bg-accent hover:text-foreground",
                  )}
                >
                  <Icon className="h-4 w-4" />
                  <span className="hidden sm:inline">{item.label}</span>
                </Link>
              );
            })}

            {isAdmin && (
              <Link
                to="/admin"
                className={cn(
                  "inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-sm font-medium transition-colors",
                  location.pathname.startsWith("/admin")
                    ? "bg-primary/10 text-primary"
                    : "text-muted-foreground hover:bg-accent hover:text-foreground",
                )}
              >
                <LayoutDashboard className="h-4 w-4" />
                <span className="hidden sm:inline">Admin</span>
              </Link>
            )}

            {user && (
              <div className="ml-1 hidden items-center gap-2 border-l pl-3 sm:flex">
                <span
                  className="flex h-8 w-8 items-center justify-center rounded-full bg-secondary text-xs font-semibold text-secondary-foreground"
                  title={user.email}
                >
                  {userInitial(user.email)}
                </span>
                <span className="max-w-[140px] truncate text-xs text-muted-foreground">
                  {user.email}
                </span>
              </div>
            )}

            <Button
              variant="ghost"
              size="sm"
              className="ml-1 text-muted-foreground"
              onClick={() => void logout()}
            >
              <LogOut className="h-4 w-4 sm:mr-1.5" />
              <span className="hidden sm:inline">Logout</span>
            </Button>
          </nav>
        </div>
      </header>

      <main className="container py-8 sm:py-10">
        <Outlet />
      </main>
    </div>
  );
}
