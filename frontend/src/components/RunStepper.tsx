import { Check, AlertTriangle, CircleDashed, Loader2, X } from "lucide-react";

import type { RunStatus } from "@/api/types";
import { cn } from "@/lib/utils";

interface Step {
  key: RunStatus | "queued";
  label: string;
  hint: string;
}

const STEPS: Step[] = [
  { key: "queued", label: "Queued", hint: "Waiting to start" },
  { key: "fetching", label: "Fetch", hint: "Download your URLs" },
  { key: "extracting", label: "Extract", hint: "Pull facts from sources" },
  { key: "researching", label: "Research", hint: "Search the web for topics" },
  { key: "synthesizing", label: "Synthesize", hint: "Build the report" },
  { key: "judging", label: "Verify", hint: "Check citations" },
];

const STEP_ORDER: Record<string, number> = Object.fromEntries(
  STEPS.map((s, i) => [s.key, i]),
);

const FAILED_PREFIX = "failed_";

function statusIndex(status: RunStatus): number {
  if (status === "done" || status === "done_with_warnings") return STEPS.length;
  if (status.startsWith(FAILED_PREFIX)) {
    const map: Record<string, RunStatus> = {
      failed_fetch: "fetching",
      failed_agent: "researching",
      failed_synth: "synthesizing",
      failed_budget: "judging",
      failed_unknown: "queued",
    };
    return STEP_ORDER[map[status] ?? "queued"] ?? 0;
  }
  return STEP_ORDER[status] ?? 0;
}

export function RunStepper({
  status,
  failureReason,
}: {
  status: RunStatus;
  failureReason?: string | null;
}) {
  const active = statusIndex(status);
  const failed = status.startsWith(FAILED_PREFIX);
  const done = status === "done" || status === "done_with_warnings";
  const warnings = status === "done_with_warnings";
  const currentStep = done ? null : STEPS[Math.min(active, STEPS.length - 1)];
  const progressPct = done ? 100 : Math.round((active / STEPS.length) * 100);

  return (
    <div className="space-y-5">
      {!done && !failed && (
        <div className="space-y-2">
          <div className="flex items-center justify-between text-xs text-muted-foreground">
            <span>
              {currentStep ? (
                <>
                  <span className="font-medium text-foreground">Now:</span> {currentStep.hint}
                </>
              ) : (
                "Starting…"
              )}
            </span>
            <span className="tabular-nums">{progressPct}%</span>
          </div>
          <div className="h-1.5 overflow-hidden rounded-full bg-muted">
            <div
              className="h-full rounded-full bg-primary transition-all duration-500 ease-out"
              style={{ width: `${Math.max(progressPct, 8)}%` }}
            />
          </div>
        </div>
      )}

      <ol className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-6 lg:gap-3">
        {STEPS.map((step, idx) => {
          const isPast = idx < active;
          const isCurrent = idx === active && !done && !failed;
          const isFailedAt = idx === active && failed;
          return (
            <li
              key={step.key}
              title={step.hint}
              className={cn(
                "relative flex flex-col items-start rounded-xl border p-3 text-sm transition-all duration-300",
                isPast && "border-emerald-500/25 bg-emerald-500/5",
                isCurrent && "border-primary bg-primary/5 shadow-sm ring-2 ring-primary/15",
                isFailedAt && "border-destructive/40 bg-destructive/5",
                !isPast && !isCurrent && !isFailedAt && "border-border/80 bg-muted/20 opacity-80",
              )}
            >
              <div className="flex items-center gap-2">
                {isPast && <Check className="h-4 w-4 shrink-0 text-emerald-600" />}
                {isCurrent && (
                  <Loader2 className="h-4 w-4 shrink-0 animate-spin text-primary" />
                )}
                {isFailedAt && <X className="h-4 w-4 shrink-0 text-destructive" />}
                {!isPast && !isCurrent && !isFailedAt && (
                  <CircleDashed className="h-4 w-4 shrink-0 text-muted-foreground" />
                )}
                <span className="font-medium">{step.label}</span>
              </div>
              <p className="mt-1.5 line-clamp-2 text-xs leading-snug text-muted-foreground">
                {step.hint}
              </p>
              {isFailedAt && failureReason && (
                <p className="mt-1 line-clamp-3 text-xs text-destructive">{failureReason}</p>
              )}
            </li>
          );
        })}
      </ol>

      {warnings && (
        <div className="flex items-start gap-2 rounded-xl border border-amber-500/30 bg-amber-500/5 p-3 text-sm text-amber-950">
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-amber-600" />
          <p>
            Some insights were flagged as unsupported or contradicted. Look for amber and red
            badges in the report.
          </p>
        </div>
      )}
    </div>
  );
}
