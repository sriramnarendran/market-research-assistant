import type { RunStatus } from "@/api/types";

export function statusLabel(status: RunStatus): string {
  const labels: Record<RunStatus, string> = {
    queued: "Waiting to start",
    fetching: "Fetching URLs",
    extracting: "Reading sources",
    researching: "Searching the web",
    synthesizing: "Writing report",
    judging: "Checking citations",
    done: "Complete",
    done_with_warnings: "Complete — review flags",
    failed_fetch: "Failed at fetch",
    failed_agent: "Failed at research",
    failed_synth: "Failed at synthesis",
    failed_budget: "Stopped — budget limit",
    failed_unknown: "Failed",
  };
  return labels[status] ?? status;
}

export function statusDescription(
  status: RunStatus,
  failureReason?: string | null,
): string {
  if (failureReason && status.startsWith("failed_")) {
    return failureReason;
  }
  const descriptions: Partial<Record<RunStatus, string>> = {
    queued: "Your run is in line and will start shortly.",
    fetching: "Downloading and cleaning the URLs you provided. Sources appear below as they're fetched.",
    extracting: "Pulling facts out of each source.",
    researching: "Searching the web for your topics. New sources appear below as they're found.",
    synthesizing: "Turning facts into a structured market brief.",
    judging: "An independent model is verifying each insight — the report below updates live.",
    done: "Your report is ready below.",
    done_with_warnings: "Report is ready, but some insights need a closer look.",
    failed_budget: "The run hit the token budget cap. Partial results may be available.",
  };
  return descriptions[status] ?? "";
}

export function statusVariant(
  status: RunStatus,
): "default" | "secondary" | "destructive" | "success" | "warning" {
  if (status === "done") return "success";
  if (status === "done_with_warnings") return "warning";
  if (status.startsWith("failed_")) return "destructive";
  if (status === "queued") return "secondary";
  return "secondary";
}

export function isInProgress(status: RunStatus): boolean {
  return ![
    "done",
    "done_with_warnings",
    "failed_fetch",
    "failed_agent",
    "failed_synth",
    "failed_budget",
    "failed_unknown",
  ].includes(status);
}

export function runDisplayTitle(run: {
  topics: string[];
  urls: string[];
  report?: { headline?: string } | null;
}): string {
  if (run.report?.headline) return run.report.headline;
  return runInputTitle(run);
}

/** Page chrome title — never repeats the report headline (that lives in ReportViewer). */
export function runPageTitle(run: { topics: string[]; urls: string[] }): string {
  return runInputTitle(run);
}

function runInputTitle(run: { topics: string[]; urls: string[] }): string {
  if (run.topics.length > 0) {
    const preview = run.topics.slice(0, 2).join(", ");
    return run.topics.length > 2 ? `${preview} +${run.topics.length - 2} more` : preview;
  }
  if (run.urls.length > 0) {
    return `${run.urls.length} URL${run.urls.length === 1 ? "" : "s"}`;
  }
  return "Research run";
}

export function formatRelativeTime(iso: string): string {
  const date = new Date(iso);
  const diffMs = Date.now() - date.getTime();
  const diffMin = Math.floor(diffMs / 60_000);
  if (diffMin < 1) return "Just now";
  if (diffMin < 60) return `${diffMin}m ago`;
  const diffHr = Math.floor(diffMin / 60);
  if (diffHr < 24) return `${diffHr}h ago`;
  const diffDay = Math.floor(diffHr / 24);
  if (diffDay < 7) return `${diffDay}d ago`;
  return date.toLocaleDateString();
}
