import { useQuery } from "@tanstack/react-query";
import { ChevronRight, FileText, Loader2, Plus } from "lucide-react";
import { useMemo, useState } from "react";
import { Link } from "react-router-dom";

import { api } from "@/api/client";
import type { RunSummary } from "@/api/types";
import { PageHeader } from "@/components/PageHeader";
import { RunStatusBadge } from "@/components/RunStatusBadge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { formatRelativeTime, isInProgress, runDisplayTitle } from "@/lib/runStatus";
import { cn } from "@/lib/utils";

type Filter = "all" | "active" | "done";

function RunListSkeleton() {
  return (
    <div className="space-y-3">
      {Array.from({ length: 4 }).map((_, i) => (
        <Skeleton key={i} className="h-28 w-full rounded-xl" />
      ))}
    </div>
  );
}

export function RunListPage() {
  const [filter, setFilter] = useState<Filter>("all");
  const { data, isLoading, error } = useQuery({
    queryKey: ["runs"],
    queryFn: () => api.listRuns(),
  });

  const activeCount = data?.filter((r) => isInProgress(r.status)).length ?? 0;
  const doneCount = data?.filter((r) => r.has_report).length ?? 0;

  const filtered = useMemo(() => {
    if (!data) return [];
    if (filter === "active") return data.filter((r) => isInProgress(r.status));
    if (filter === "done") return data.filter((r) => r.has_report);
    return data;
  }, [data, filter]);

  const description = data
    ? activeCount > 0
      ? `${activeCount} in progress · ${data.length} total · ${doneCount} with reports`
      : `${data.length} run${data.length === 1 ? "" : "s"} · ${doneCount} with reports`
    : "Past and in-progress market research runs.";

  return (
    <div className="mx-auto max-w-4xl space-y-8">
      <PageHeader
        title="Research history"
        description={description}
        actions={
          <Button asChild>
            <Link to="/">
              <Plus className="h-4 w-4" />
              New research
            </Link>
          </Button>
        }
      />

      {data && data.length > 0 && (
        <div className="flex flex-wrap gap-2">
          <FilterChip
            label="All"
            count={data.length}
            active={filter === "all"}
            onClick={() => setFilter("all")}
          />
          {activeCount > 0 && (
            <FilterChip
              label="In progress"
              count={activeCount}
              active={filter === "active"}
              onClick={() => setFilter("active")}
            />
          )}
          <FilterChip
            label="With report"
            count={doneCount}
            active={filter === "done"}
            onClick={() => setFilter("done")}
          />
        </div>
      )}

      {isLoading && <RunListSkeleton />}
      {error && (
        <div className="rounded-xl border border-destructive/30 bg-destructive/5 px-4 py-3 text-sm text-destructive">
          Couldn&apos;t load runs: {String(error)}
        </div>
      )}

      {data && data.length === 0 && (
        <Card className="border-dashed">
          <CardHeader>
            <CardTitle>No research yet</CardTitle>
            <CardDescription>
              Start by adding competitors, topics, or URLs you want analyzed. You&apos;ll get a
              cited report in a few minutes.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <Button asChild>
              <Link to="/">
                <Plus className="h-4 w-4" />
                Start your first research
              </Link>
            </Button>
          </CardContent>
        </Card>
      )}

      {data && data.length > 0 && filtered.length === 0 && (
        <p className="rounded-xl border border-dashed bg-muted/20 px-4 py-8 text-center text-sm text-muted-foreground">
          No runs match this filter.
        </p>
      )}

      {filtered.length > 0 && (
        <div className="space-y-3">
          {filtered.map((r) => (
            <RunRow key={r.id} run={r} />
          ))}
        </div>
      )}
    </div>
  );
}

function FilterChip({
  label,
  count,
  active,
  onClick,
}: {
  label: string;
  count: number;
  active: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-sm font-medium transition-colors",
        active
          ? "border-primary/30 bg-primary/10 text-primary"
          : "bg-card text-muted-foreground hover:bg-accent hover:text-foreground",
      )}
    >
      {label}
      <span
        className={cn(
          "rounded-full px-1.5 py-0.5 text-[10px] tabular-nums",
          active ? "bg-primary/15" : "bg-muted",
        )}
      >
        {count}
      </span>
    </button>
  );
}

function RunRow({ run }: { run: RunSummary }) {
  const title = runDisplayTitle(run);
  const progressing = isInProgress(run.status);

  return (
    <Link to={`/runs/${run.id}`} className="group block">
      <Card className="transition-all hover:border-primary/30 hover:shadow-sm">
        <CardContent className="flex items-center gap-4 p-4 sm:p-5">
          <div
            className={cn(
              "flex h-11 w-11 shrink-0 items-center justify-center rounded-xl ring-1",
              run.has_report
                ? "bg-emerald-500/10 text-emerald-700 ring-emerald-500/20"
                : progressing
                  ? "bg-primary/10 text-primary ring-primary/20"
                  : "bg-muted text-muted-foreground ring-border",
            )}
          >
            {progressing ? (
              <Loader2 className="h-5 w-5 animate-spin" />
            ) : (
              <FileText className="h-5 w-5" />
            )}
          </div>
          <div className="min-w-0 flex-1 space-y-1.5">
            <div className="flex flex-wrap items-center gap-2">
              <span className="truncate font-medium group-hover:text-primary">{title}</span>
              <RunStatusBadge status={run.status} />
            </div>
            <div className="flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-muted-foreground">
              <span>{formatRelativeTime(run.created_at)}</span>
              {run.topics.length > 0 && (
                <>
                  <span>·</span>
                  <span>
                    {run.topics.slice(0, 2).join(", ")}
                    {run.topics.length > 2 && ` +${run.topics.length - 2}`}
                  </span>
                </>
              )}
              {run.urls.length > 0 && (
                <>
                  <span>·</span>
                  <span>
                    {run.urls.length} URL{run.urls.length === 1 ? "" : "s"}
                  </span>
                </>
              )}
              {run.has_report && (
                <>
                  <span>·</span>
                  <span className="font-medium text-emerald-700">Report ready</span>
                </>
              )}
            </div>
          </div>
          <ChevronRight className="h-5 w-5 shrink-0 text-muted-foreground transition-transform group-hover:translate-x-0.5 group-hover:text-primary" />
        </CardContent>
      </Card>
    </Link>
  );
}
