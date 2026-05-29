import { BarChart3, ShieldCheck, Sparkles } from "lucide-react";
import { Link } from "react-router-dom";

import { AppBackground } from "@/components/AppBackground";

const FEATURES = [
  {
    icon: Sparkles,
    title: "Web + URL research",
    description: "Search topics and read your links in one run.",
  },
  {
    icon: ShieldCheck,
    title: "Citation verification",
    description: "Every insight is checked against its sources.",
  },
  {
    icon: BarChart3,
    title: "Structured reports",
    description: "Metrics, risks, and opportunities with citations.",
  },
] as const;

export function AuthLayout({
  title,
  subtitle,
  children,
  footer,
}: {
  title: string;
  subtitle: string;
  children: React.ReactNode;
  footer?: React.ReactNode;
}) {
  return (
    <div className="relative min-h-screen lg:grid lg:grid-cols-2">
      <div className="relative hidden overflow-hidden bg-gradient-to-br from-primary via-primary to-indigo-700 p-10 text-primary-foreground lg:flex lg:flex-col lg:justify-between">
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_20%_20%,rgba(255,255,255,0.12),transparent_45%)]" />
        <div className="absolute -right-20 top-1/3 h-72 w-72 rounded-full bg-white/10 blur-3xl" />
        <div className="absolute -left-16 bottom-0 h-64 w-64 rounded-full bg-indigo-300/20 blur-3xl" />
        <div className="relative">
          <Link to="/" className="inline-flex items-center gap-2 text-lg font-semibold tracking-tight">
            <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-white/15 ring-1 ring-white/20">
              <Sparkles className="h-4 w-4" />
            </span>
            Market Research Assistant
          </Link>
          <p className="mt-6 max-w-md text-balance text-sm leading-relaxed text-primary-foreground/85">
            Turn competitors, topics, and source URLs into cited market intelligence — with
            automated fact-checking built in.
          </p>
        </div>
        <ul className="relative space-y-4">
          {FEATURES.map(({ icon: Icon, title: featureTitle, description }) => (
            <li key={featureTitle} className="flex gap-3">
              <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-white/10 ring-1 ring-white/15">
                <Icon className="h-4 w-4" />
              </span>
              <div>
                <p className="text-sm font-medium">{featureTitle}</p>
                <p className="text-xs leading-relaxed text-primary-foreground/75">{description}</p>
              </div>
            </li>
          ))}
        </ul>
      </div>

      <div className="relative flex min-h-screen flex-col justify-center px-4 py-10 sm:px-8">
        <AppBackground />
        <div className="relative mx-auto w-full max-w-md space-y-8">
          <div className="space-y-2 lg:hidden">
            <Link to="/" className="inline-flex items-center gap-2 font-semibold tracking-tight">
              <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary/10 text-primary">
                <Sparkles className="h-4 w-4" />
              </span>
              MRA
            </Link>
          </div>

          <div className="space-y-1">
            <h1 className="text-2xl font-bold tracking-tight">{title}</h1>
            <p className="text-sm text-muted-foreground">{subtitle}</p>
          </div>

          <div className="rounded-xl border bg-card/90 p-6 shadow-sm ring-1 ring-border/60 backdrop-blur-sm">
            {children}
          </div>

          {footer ? (
            <div className="text-center text-sm text-muted-foreground">{footer}</div>
          ) : null}
        </div>
      </div>
    </div>
  );
}
