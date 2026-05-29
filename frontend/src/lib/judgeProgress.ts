import type { Insight, Report } from "@/api/types";

function isInsightResolved(ins: Insight): boolean {
  if (ins.judge_verdict) return true;
  const lower = ins.judge_rationale?.toLowerCase() ?? "";
  return (
    lower.includes("judge skipped") ||
    lower.includes("could not be completed") ||
    lower.includes("judge error")
  );
}

/** Count insights awaiting or completed judge verification. */
export function judgeProgress(report: Report): {
  total: number;
  resolved: number;
  pending: number;
} {
  const insights = collectInsights(report);
  const resolved = insights.filter(isInsightResolved).length;
  return {
    total: insights.length,
    resolved,
    pending: insights.length - resolved,
  };
}

function collectInsights(report: Report): Insight[] {
  const out: Insight[] = [];
  out.push(...(report.key_findings ?? []));
  for (const section of [report.market_trends, report.consumer_behavior]) {
    if (section) out.push(...section.insights);
  }
  out.push(...(report.opportunities ?? []));
  out.push(...(report.risks ?? []));
  const syn = report.competitive_strategic_synthesis;
  if (syn) {
    out.push(...syn.dynamics);
    out.push(...(syn.implications ?? []));
  }
  for (const theme of report.themes) out.push(...theme.insights);
  for (const comp of report.competitors) out.push(...comp.insights);
  return out;
}
