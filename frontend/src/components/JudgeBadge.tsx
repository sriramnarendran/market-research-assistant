import { useState } from "react";
import { CheckCircle2, HelpCircle, Loader2, XCircle } from "lucide-react";

import type { JudgeVerdict } from "@/api/types";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

const VERDICT_META = {
  verified: {
    label: "Verified",
    variant: "success" as const,
    icon: CheckCircle2,
    defaultTitle: "Supported by cited sources",
  },
  unsupported: {
    label: "Unsupported",
    variant: "warning" as const,
    icon: HelpCircle,
    defaultTitle: "Weak or missing support in sources",
  },
  contradicted: {
    label: "Contradicted",
    variant: "destructive" as const,
    icon: XCircle,
    defaultTitle: "Conflicts with cited sources",
  },
} as const;

function ClickableJudgeBadge({
  label,
  variant,
  icon: Icon,
  rationale,
  defaultTitle,
}: {
  label: string;
  variant: "success" | "warning" | "destructive" | "secondary";
  icon: typeof CheckCircle2;
  rationale?: string | null;
  defaultTitle: string;
}) {
  const [showRationale, setShowRationale] = useState(false);
  const canToggle = Boolean(rationale?.trim());

  return (
    <div className="inline-flex flex-col items-start gap-1">
      <button
        type="button"
        onClick={() => canToggle && setShowRationale((v) => !v)}
        className={cn(
          "rounded-full focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2",
          canToggle ? "cursor-pointer" : "cursor-default",
        )}
        title={
          canToggle
            ? showRationale
              ? "Hide judge note"
              : "Show judge note"
            : defaultTitle
        }
        aria-expanded={showRationale}
      >
        <Badge variant={variant} className="pointer-events-none gap-1">
          <Icon className="h-3 w-3" />
          {label}
        </Badge>
      </button>
      {showRationale && rationale && (
        <p className="max-w-md text-xs text-muted-foreground">
          <span className="font-medium">Judge:</span> {rationale}
        </p>
      )}
    </div>
  );
}

function isJudgeIncomplete(rationale?: string | null): boolean {
  const lower = rationale?.toLowerCase() ?? "";
  return (
    lower.includes("judge skipped") ||
    lower.includes("could not be completed") ||
    lower.includes("judge error")
  );
}

export function JudgeBadge({
  verdict,
  rationale,
  pending = false,
}: {
  verdict?: JudgeVerdict | null;
  rationale?: string | null;
  /** Show spinner while judge has not finished this insight. */
  pending?: boolean;
}) {
  if (pending && !verdict && !isJudgeIncomplete(rationale)) {
    return (
      <Badge variant="secondary" className="gap-1">
        <Loader2 className="h-3 w-3 animate-spin" aria-hidden />
        Checking
      </Badge>
    );
  }

  if (!verdict) {
    if (isJudgeIncomplete(rationale)) {
      return (
        <ClickableJudgeBadge
          label="Not checked"
          variant="secondary"
          icon={HelpCircle}
          rationale={rationale}
          defaultTitle="Verification was skipped or could not be completed"
        />
      );
    }
    return null;
  }

  const meta = VERDICT_META[verdict];
  return (
    <ClickableJudgeBadge
      label={meta.label}
      variant={meta.variant}
      icon={meta.icon}
      rationale={rationale}
      defaultTitle={meta.defaultTitle}
    />
  );
}
