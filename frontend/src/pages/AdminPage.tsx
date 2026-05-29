import { useQuery } from "@tanstack/react-query";
import type { LucideIcon } from "lucide-react";
import {
  Activity,
  BarChart3,
  CheckCircle2,
  DollarSign,
  FileText,
  Globe,
  Link2,
  Loader2,
  Search,
  Users,
  XCircle,
} from "lucide-react";
import { useMemo } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { api } from "@/api/client";
import { PageHeader } from "@/components/PageHeader";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";

const REFRESH_MS = 30_000;

export function AdminPage() {
  const queryOpts = {
    refetchInterval: REFRESH_MS,
    refetchIntervalInBackground: true,
    refetchOnWindowFocus: true,
    staleTime: 0,
  } as const;

  const overview = useQuery({
    queryKey: ["admin", "overview"],
    queryFn: api.admin.overview,
    ...queryOpts,
  });
  const usage = useQuery({
    queryKey: ["admin", "usage"],
    queryFn: api.admin.usage,
    ...queryOpts,
  });

  const lastUpdated = useMemo(
    () => Math.max(overview.dataUpdatedAt, usage.dataUpdatedAt),
    [overview.dataUpdatedAt, usage.dataUpdatedAt],
  );

  const usageByDay = useMemo(
    () => aggregateUsageByDay(usage.data ?? []),
    [usage.data],
  );

  const totalCost90d = useMemo(
    () => usageByDay.reduce((sum, row) => sum + row.cost_usd, 0),
    [usageByDay],
  );

  const loading = overview.isLoading || usage.isLoading;
  const o = overview.data;

  const summary = o
    ? [
        `${formatCount(o.runs_today)} run${o.runs_today === 1 ? "" : "s"} today`,
        `${formatCount(o.sources_today)} source${o.sources_today === 1 ? "" : "s"} fetched today`,
        `${formatUsd(totalCost90d)} LLM spend (90d)`,
      ].join(" · ")
    : "Platform activity, sources collected, and LLM usage.";

  if (loading) {
    return <AdminPageSkeleton />;
  }

  return (
    <div className="space-y-8">
      <PageHeader
        title="Admin dashboard"
        description={summary}
        actions={<LiveStatusBadge updatedAt={lastUpdated} />}
      />

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <HeroMetric
          label="Runs today"
          value={o?.runs_today ?? 0}
          icon={Activity}
          accent="sky"
        />
        <HeroMetric
          label="Sources today"
          value={o?.sources_today ?? 0}
          icon={Globe}
          accent="emerald"
        />
        <HeroMetric
          label="Reports generated"
          value={o?.reports_generated ?? 0}
          icon={FileText}
          accent="violet"
        />
        <HeroMetric
          label="Active users (7d)"
          value={o?.active_users_7d ?? 0}
          icon={Users}
          accent="amber"
        />
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <MetricSection
          title="Run pipeline"
          description="All-time run outcomes and throughput"
          icon={BarChart3}
        >
          <div className="grid gap-3 sm:grid-cols-2">
            <MetricTile label="Total runs" value={o?.total_runs ?? 0} icon={BarChart3} />
            <MetricTile label="Completed" value={o?.completed_runs ?? 0} icon={CheckCircle2} tone="success" />
            <MetricTile label="In progress" value={o?.in_progress_runs ?? 0} icon={Loader2} tone="info" />
            <MetricTile label="Failed" value={o?.failed_runs ?? 0} icon={XCircle} tone="danger" />
          </div>
        </MetricSection>

        <MetricSection
          title="Sources collected"
          description="URLs fetched and pages found via search"
          icon={Globe}
        >
          <div className="grid gap-3 sm:grid-cols-2">
            <MetricTile label="Total sources" value={o?.total_sources ?? 0} icon={Globe} />
            <MetricTile label="From your URLs" value={o?.url_sources ?? 0} icon={Link2} />
            <MetricTile label="From web search" value={o?.search_sources ?? 0} icon={Search} />
            <MetricTile
              label="Registered users"
              value={o?.total_users ?? 0}
              icon={Users}
              hint="Logged in or created a run"
            />
          </div>
        </MetricSection>
      </div>

      <Card>
        <CardHeader>
          <div className="flex items-center gap-3">
            <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-primary/10 text-primary">
              <DollarSign className="h-4 w-4" />
            </div>
            <div>
              <CardTitle className="text-base">LLM usage</CardTitle>
              <CardDescription>Daily token volume and estimated cost (last 90 days)</CardDescription>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          {usageByDay.length === 0 ? (
            <div className="flex h-48 items-center justify-center rounded-xl border border-dashed bg-muted/20 text-sm text-muted-foreground">
              No usage recorded yet. Costs appear after research runs complete.
            </div>
          ) : (
            <div className="grid gap-6 lg:grid-cols-2">
              <ChartPanel title="Tokens per day" subtitle="Input + output across all phases">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={usageByDay} margin={{ top: 4, right: 8, left: 0, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" className="stroke-border/60" vertical={false} />
                    <XAxis
                      dataKey="day"
                      tick={{ fontSize: 11 }}
                      tickFormatter={(v: string) => formatChartDay(v)}
                      axisLine={false}
                      tickLine={false}
                    />
                    <YAxis
                      tick={{ fontSize: 11 }}
                      tickFormatter={(v: number) => formatCompact(v)}
                      axisLine={false}
                      tickLine={false}
                      width={48}
                    />
                    <Tooltip content={<UsageTooltip mode="tokens" />} />
                    <Line
                      type="monotone"
                      dataKey="tokens"
                      stroke="hsl(var(--primary))"
                      strokeWidth={2}
                      dot={false}
                      activeDot={{ r: 4 }}
                    />
                  </LineChart>
                </ResponsiveContainer>
              </ChartPanel>

              <ChartPanel title="Cost per day" subtitle="Sum of usage_events.cost_usd">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={usageByDay} margin={{ top: 4, right: 8, left: 0, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" className="stroke-border/60" vertical={false} />
                    <XAxis
                      dataKey="day"
                      tick={{ fontSize: 11 }}
                      tickFormatter={(v: string) => formatChartDay(v)}
                      axisLine={false}
                      tickLine={false}
                    />
                    <YAxis
                      tick={{ fontSize: 11 }}
                      tickFormatter={(v: number) => `$${formatCompact(v)}`}
                      axisLine={false}
                      tickLine={false}
                      width={48}
                    />
                    <Tooltip content={<UsageTooltip mode="cost" />} />
                    <Bar
                      dataKey="cost_usd"
                      fill="hsl(var(--primary))"
                      radius={[4, 4, 0, 0]}
                      maxBarSize={32}
                    />
                  </BarChart>
                </ResponsiveContainer>
              </ChartPanel>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

function AdminPageSkeleton() {
  return (
    <div className="space-y-8">
      <div className="space-y-3">
        <Skeleton className="h-9 w-56" />
        <Skeleton className="h-4 w-full max-w-xl" />
      </div>
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {Array.from({ length: 4 }).map((_, i) => (
          <Skeleton key={i} className="h-28 w-full rounded-xl" />
        ))}
      </div>
      <div className="grid gap-6 lg:grid-cols-2">
        <Skeleton className="h-64 w-full rounded-xl" />
        <Skeleton className="h-64 w-full rounded-xl" />
      </div>
      <Skeleton className="h-80 w-full rounded-xl" />
    </div>
  );
}

function LiveStatusBadge({ updatedAt }: { updatedAt: number }) {
  if (updatedAt <= 0) return null;
  return (
    <span className="inline-flex items-center gap-2 rounded-full border bg-muted/40 px-3 py-1.5 text-xs text-muted-foreground">
      <span className="relative flex h-2 w-2">
        <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-60" />
        <span className="relative inline-flex h-2 w-2 rounded-full bg-emerald-500" />
      </span>
      Updated {new Date(updatedAt).toLocaleTimeString()} · every {REFRESH_MS / 1000}s
    </span>
  );
}

type Accent = "sky" | "emerald" | "violet" | "amber";

const HERO_ACCENTS: Record<Accent, { card: string; icon: string }> = {
  sky: {
    card: "from-sky-500/10 via-card to-card ring-sky-500/15",
    icon: "bg-sky-500/15 text-sky-700",
  },
  emerald: {
    card: "from-emerald-500/10 via-card to-card ring-emerald-500/15",
    icon: "bg-emerald-500/15 text-emerald-700",
  },
  violet: {
    card: "from-violet-500/10 via-card to-card ring-violet-500/15",
    icon: "bg-violet-500/15 text-violet-700",
  },
  amber: {
    card: "from-amber-500/10 via-card to-card ring-amber-500/15",
    icon: "bg-amber-500/15 text-amber-800",
  },
};

function HeroMetric({
  label,
  value,
  icon: Icon,
  accent,
}: {
  label: string;
  value: number;
  icon: LucideIcon;
  accent: Accent;
}) {
  const styles = HERO_ACCENTS[accent];
  return (
    <div
      className={cn(
        "relative overflow-hidden rounded-xl bg-gradient-to-br p-5 ring-1 transition-shadow hover:shadow-sm",
        styles.card,
      )}
    >
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">{label}</p>
          <p className="mt-2 text-3xl font-bold tabular-nums tracking-tight">{formatCount(value)}</p>
        </div>
        <div className={cn("flex h-10 w-10 shrink-0 items-center justify-center rounded-lg", styles.icon)}>
          <Icon className="h-5 w-5" />
        </div>
      </div>
    </div>
  );
}

function MetricSection({
  title,
  description,
  icon: Icon,
  children,
}: {
  title: string;
  description: string;
  icon: LucideIcon;
  children: React.ReactNode;
}) {
  return (
    <Card>
      <CardHeader className="pb-4">
        <div className="flex items-center gap-3">
          <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-primary/10 text-primary">
            <Icon className="h-4 w-4" />
          </div>
          <div>
            <CardTitle className="text-base">{title}</CardTitle>
            <CardDescription>{description}</CardDescription>
          </div>
        </div>
      </CardHeader>
      <CardContent>{children}</CardContent>
    </Card>
  );
}

type TileTone = "default" | "success" | "info" | "danger";

const TILE_TONES: Record<TileTone, string> = {
  default: "bg-muted/60 text-muted-foreground",
  success: "bg-emerald-500/10 text-emerald-700",
  info: "bg-sky-500/10 text-sky-700",
  danger: "bg-destructive/10 text-destructive",
};

function MetricTile({
  label,
  value,
  icon: Icon,
  tone = "default",
  hint,
}: {
  label: string;
  value: number;
  icon: LucideIcon;
  tone?: TileTone;
  hint?: string;
}) {
  return (
    <div className="flex items-start gap-3 rounded-xl border bg-card/50 p-3.5 transition-colors hover:bg-accent/30">
      <div className={cn("flex h-9 w-9 shrink-0 items-center justify-center rounded-lg", TILE_TONES[tone])}>
        <Icon className={cn("h-4 w-4", tone === "info" && value > 0 && "animate-spin")} />
      </div>
      <div className="min-w-0">
        <p className="text-xs text-muted-foreground">{label}</p>
        <p className="text-xl font-semibold tabular-nums">{formatCount(value)}</p>
        {hint && <p className="mt-0.5 text-[11px] leading-snug text-muted-foreground">{hint}</p>}
      </div>
    </div>
  );
}

function ChartPanel({
  title,
  subtitle,
  children,
}: {
  title: string;
  subtitle: string;
  children: React.ReactNode;
}) {
  return (
    <div className="space-y-3">
      <div>
        <p className="text-sm font-medium">{title}</p>
        <p className="text-xs text-muted-foreground">{subtitle}</p>
      </div>
      <div className="h-56">{children}</div>
    </div>
  );
}

function UsageTooltip({
  active,
  payload,
  label,
  mode,
}: {
  active?: boolean;
  payload?: { value: number }[];
  label?: string;
  mode: "tokens" | "cost";
}) {
  if (!active || !payload?.length || !label) return null;
  const value = payload[0]?.value ?? 0;
  return (
    <div className="rounded-lg border bg-popover px-3 py-2 text-xs shadow-md">
      <p className="font-medium text-foreground">{formatChartDay(label, true)}</p>
      <p className="mt-1 text-muted-foreground">
        {mode === "cost" ? formatUsd(value) : `${formatCount(value)} tokens`}
      </p>
    </div>
  );
}

function aggregateUsageByDay(
  rows: { day: string; input_tokens: number; output_tokens: number; cost_usd: number }[],
) {
  const byDay = new Map<string, { day: string; tokens: number; cost_usd: number }>();
  for (const r of rows) {
    const cur = byDay.get(r.day) ?? { day: r.day, tokens: 0, cost_usd: 0 };
    cur.tokens += r.input_tokens + r.output_tokens;
    cur.cost_usd += r.cost_usd;
    byDay.set(r.day, cur);
  }
  return [...byDay.values()].sort((a, b) => a.day.localeCompare(b.day));
}

function formatCount(n: number): string {
  return n.toLocaleString();
}

function formatCompact(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}k`;
  return String(Math.round(n * 100) / 100);
}

function formatUsd(n: number): string {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: n >= 1 ? 2 : 4,
    maximumFractionDigits: n >= 1 ? 2 : 4,
  }).format(n);
}

function formatChartDay(iso: string, long = false): string {
  const d = new Date(`${iso}T12:00:00`);
  return d.toLocaleDateString(undefined, long
    ? { weekday: "short", month: "short", day: "numeric" }
    : { month: "short", day: "numeric" });
}
