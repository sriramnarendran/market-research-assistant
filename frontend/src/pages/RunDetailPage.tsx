import { useMutation } from "@tanstack/react-query";
import {
  AlertTriangle,
  ChevronDown,
  Download,
  Loader2,
  RotateCcw,
} from "lucide-react";
import { useNavigate, useParams } from "react-router-dom";
import { toast } from "sonner";

import { api, ApiError } from "@/api/client";
import { TERMINAL_STATUSES } from "@/api/types";
import { PageHeader } from "@/components/PageHeader";
import { ReportViewer } from "@/components/ReportViewer";
import { RunSourcesFeed } from "@/components/RunSourcesFeed";
import { RunStatusBadge } from "@/components/RunStatusBadge";
import { RunStepper } from "@/components/RunStepper";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useRunPolling } from "@/hooks/useRunPolling";
import { useRunSourcesPolling } from "@/hooks/useRunSourcesPolling";
import {
  isInProgress,
  runPageTitle,
  statusDescription,
} from "@/lib/runStatus";
import { judgeProgress } from "@/lib/judgeProgress";

function RunDetailSkeleton() {
  return (
    <div className="space-y-6">
      <div className="flex justify-between gap-4">
        <div className="space-y-2">
          <Skeleton className="h-4 w-32" />
          <Skeleton className="h-8 w-64" />
          <Skeleton className="h-4 w-48" />
        </div>
        <Skeleton className="h-9 w-28" />
      </div>
      <Skeleton className="h-40 w-full" />
      <Skeleton className="h-64 w-full" />
    </div>
  );
}

export function RunDetailPage() {
  const navigate = useNavigate();
  const { runId } = useParams<{ runId: string }>();
  const { data: run, isLoading, error } = useRunPolling(runId);
  const inProgressLater = run ? isInProgress(run.status) : false;
  const { data: sources = [], isLoading: sourcesLoading } = useRunSourcesPolling(
    runId,
    inProgressLater,
    run?.created_at,
  );

  const rerun = useMutation({
    mutationFn: () =>
      api.createRun({
        topics: run!.topics,
        urls: run!.urls,
        prior_run_id: run!.id,
      }),
    onSuccess: (resp) => {
      toast.success("New run started — we'll highlight what changed");
      navigate(`/runs/${resp.id}`);
    },
    onError: (e) => {
      toast.error("Could not start re-run", {
        description: e instanceof ApiError ? e.message : String(e),
      });
    },
  });

  const exportPdf = useMutation({
    mutationFn: () => api.exportRunPdf(run!.id),
    onSuccess: () => toast.success("Report downloaded"),
    onError: (e) => {
      toast.error("Export failed", {
        description: e instanceof ApiError ? e.message : String(e),
      });
    },
  });

  if (isLoading) {
    return <RunDetailSkeleton />;
  }
  if (error || !run) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Run not found</CardTitle>
          <CardDescription>
            This run may have been deleted or you don't have access.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <Button variant="outline" onClick={() => navigate("/runs")}>
            Back to all runs
          </Button>
        </CardContent>
      </Card>
    );
  }

  const isTerminal = TERMINAL_STATUSES.has(run.status);
  const isFailure = run.status.startsWith("failed_");
  const inProgress = isInProgress(run.status);
  const isJudging = run.status === "judging";
  const hasReport = Boolean(run.report);
  const showPipelineCard = inProgress && !hasReport;
  const verification =
    hasReport && isJudging && run.report ? judgeProgress(run.report) : null;
  const isBudgetFailure =
    run.status === "failed_budget" ||
    (run.failure_reason?.toLowerCase().includes("budget") ?? false);
  const canRerun =
    isTerminal && (run.topics.length > 0 || run.urls.length > 0);
  const pageTitle = runPageTitle(run);
  const statusHelp = statusDescription(run.status, run.failure_reason);

  return (
    <div className="space-y-8">
      <PageHeader
        crumbs={[
          { label: "Runs", to: "/runs" },
          { label: run.report ? "Report" : pageTitle },
        ]}
        title={pageTitle}
        description={statusHelp || undefined}
        actions={
          <>
            <RunStatusBadge status={run.status} />
            {run.report && isTerminal && (
              <Button
                variant="outline"
                size="sm"
                disabled={exportPdf.isPending}
                onClick={() => exportPdf.mutate()}
              >
                {exportPdf.isPending ? (
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                ) : (
                  <Download className="mr-2 h-4 w-4" />
                )}
                Download PDF
              </Button>
            )}
            {canRerun && (
              <Button
                variant="outline"
                size="sm"
                disabled={rerun.isPending}
                title="Run again with the same inputs and compare changes"
                onClick={() => rerun.mutate()}
              >
                {rerun.isPending ? (
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                ) : (
                  <RotateCcw className="mr-2 h-4 w-4" />
                )}
                Run again
              </Button>
            )}
          </>
        }
      />

      {isBudgetFailure && (
        <Card className="border-amber-500/40 bg-amber-500/5">
          <CardHeader className="pb-2">
            <CardTitle className="flex items-center gap-2 text-base text-amber-800">
              <AlertTriangle className="h-4 w-4" />
              Stopped early — token budget reached
            </CardTitle>
            <CardDescription>
              Partial results may still be useful. Try fewer topics or URLs on
              the next run.
            </CardDescription>
          </CardHeader>
        </Card>
      )}

      {isFailure && (
        <Card className="border-destructive/40 bg-destructive/5">
          <CardHeader>
            <CardTitle className="text-destructive">Something went wrong</CardTitle>
            <CardDescription>{run.failure_reason}</CardDescription>
          </CardHeader>
          <CardContent>
            <Button variant="outline" onClick={() => navigate("/")}>
              Start a new run
            </Button>
          </CardContent>
        </Card>
      )}

      {showPipelineCard && (
        <Card className="overflow-hidden border-primary/20 bg-gradient-to-br from-primary/[0.04] via-card to-card">
          <CardHeader className="pb-3">
            <CardTitle className="flex items-center gap-2 text-base">
              <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary/10">
                <Loader2 className="h-4 w-4 animate-spin text-primary" />
              </span>
              Generating your report
            </CardTitle>
            <CardDescription>
              Usually takes a few minutes. Sources appear below as they&apos;re collected — this
              page updates automatically.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-6">
            <RunStepper status={run.status} failureReason={run.failure_reason} />
            <RunSourcesFeed
              sources={sources}
              fetchFailures={run.url_fetch_failures ?? []}
              isLoading={sourcesLoading}
            />
          </CardContent>
        </Card>
      )}

      {isJudging && hasReport && (
        <Card className="border-primary/20 bg-primary/[0.03]">
          <CardHeader className="pb-2">
            <CardTitle className="flex items-center gap-2 text-base">
              <Loader2 className="h-4 w-4 animate-spin text-primary" />
              Verifying citations
            </CardTitle>
            <CardDescription>
              Your report is ready to read below. Judge badges update as each insight is checked
              {verification && verification.total > 0
                ? ` (${verification.resolved}/${verification.total} done).`
                : "."}
            </CardDescription>
          </CardHeader>
          <CardContent>
            <RunStepper status={run.status} failureReason={run.failure_reason} />
          </CardContent>
        </Card>
      )}

      {run.report ? (
        <ReportViewer report={run.report} judgeInProgress={isJudging} />
      ) : (
        !isFailure &&
        !inProgress && (
          <Card>
            <CardContent className="py-8 text-center text-sm text-muted-foreground">
              No report was produced for this run.
            </CardContent>
          </Card>
        )
      )}

      {isTerminal && run.report && (
        <details className="group overflow-hidden rounded-xl border bg-muted/20 ring-1 ring-border/60">
          <summary className="flex cursor-pointer list-none items-center justify-between gap-2 px-4 py-3.5 text-sm font-medium transition-colors hover:bg-muted/40 [&::-webkit-details-marker]:hidden">
            <span>How this run was built</span>
            <ChevronDown className="h-4 w-4 shrink-0 text-muted-foreground transition-transform group-open:rotate-180" />
          </summary>
          <div className="space-y-4 border-t px-4 py-4">
            <RunStepper status={run.status} failureReason={run.failure_reason} />
            {(run.topics.length > 0 || run.urls.length > 0) && (
              <div className="space-y-3 text-sm">
                {run.topics.length > 0 && (
                  <div>
                    <div className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
                      Topics searched
                    </div>
                    <div className="mt-2 flex flex-wrap gap-2">
                      {run.topics.map((t) => (
                        <span
                          key={t}
                          className="rounded-full border bg-background px-2.5 py-0.5 text-xs"
                        >
                          {t}
                        </span>
                      ))}
                    </div>
                  </div>
                )}
                {run.urls.length > 0 && (
                  <div>
                    <div className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
                      URLs analyzed
                    </div>
                    <ul className="mt-2 space-y-1">
                      {run.urls.map((u) => (
                        <li key={u} className="break-all">
                          <a
                            href={u}
                            target="_blank"
                            rel="noreferrer"
                            className="text-primary hover:underline"
                          >
                            {u}
                          </a>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            )}
          </div>
        </details>
      )}

      {!isTerminal && (run.topics.length > 0 || run.urls.length > 0) && (
        <Card className="border-dashed">
          <CardHeader className="pb-2">
            <CardTitle className="text-base">Your inputs</CardTitle>
            <CardDescription>Topics and URLs for this run</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3 text-sm">
            {run.topics.length > 0 && (
              <div className="flex flex-wrap gap-2">
                {run.topics.map((t) => (
                  <span
                    key={t}
                    className="rounded-full border bg-secondary/60 px-2.5 py-0.5 text-xs"
                  >
                    {t}
                  </span>
                ))}
              </div>
            )}
            {run.urls.length > 0 && (
              <ul className="space-y-1.5 rounded-lg bg-muted/30 p-3">
                {run.urls.map((u) => (
                  <li key={u} className="break-all text-muted-foreground">
                    <a href={u} target="_blank" rel="noreferrer" className="hover:text-primary hover:underline">
                      {u}
                    </a>
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>
      )}
    </div>
  );
}
