import { useMemo, useState } from "react";
import {
  AlertTriangle,
  BarChart3,
  Building2,
  Compass,
  FileText,
  Lightbulb,
  Sparkles,
  Telescope,
  Swords,
  TrendingUp,
  Users,
} from "lucide-react";

import type { Insight, InsightSection, KeyMetric, Report } from "@/api/types";
import type { DiffTag, JudgeVerdict } from "@/api/types";
import { JudgeBadge } from "@/components/JudgeBadge";
import { SourceChip } from "@/components/SourceChip";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

type IndexFn = (id: string) => number;

const SECTION_META = {
  findings: { icon: Lightbulb, tint: "text-amber-600", bg: "bg-amber-500/10" },
  marketTrends: { icon: TrendingUp, tint: "text-teal-600", bg: "bg-teal-500/10" },
  consumerBehavior: { icon: Users, tint: "text-rose-600", bg: "bg-rose-500/10" },
  metrics: { icon: BarChart3, tint: "text-sky-600", bg: "bg-sky-500/10" },
  synthesis: { icon: Swords, tint: "text-violet-600", bg: "bg-violet-500/10" },
  opportunities: { icon: Compass, tint: "text-emerald-600", bg: "bg-emerald-500/10" },
  risks: { icon: AlertTriangle, tint: "text-orange-600", bg: "bg-orange-500/10" },
  themes: { icon: FileText, tint: "text-slate-600", bg: "bg-slate-500/10" },
  competitors: { icon: Building2, tint: "text-indigo-600", bg: "bg-indigo-500/10" },
  outlook: { icon: Telescope, tint: "text-primary", bg: "bg-primary/10" },
} as const;

export function ReportViewer({
  report,
  judgeInProgress = false,
}: {
  report: Report;
  judgeInProgress?: boolean;
}) {
  const sourceIndex = useMemo(() => buildSourceIndex(report), [report]);
  const indexOf = (id: string) => sourceIndex.get(id) ?? 0;
  const toc = useMemo(() => buildToc(report), [report]);
  const [activeSection, setActiveSection] = useState<string | null>(null);

  return (
    <article className="overflow-hidden rounded-xl border bg-card">
      <header className="border-b px-5 py-6 sm:px-8 sm:py-7">
        <div className="flex flex-col gap-5 lg:flex-row lg:items-start lg:justify-between lg:gap-8">
          <div className="min-w-0 flex-1 space-y-4">
            <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted-foreground">
              <span className="inline-flex items-center gap-1.5 font-medium text-foreground">
                <Sparkles className="h-3.5 w-3.5 text-primary" />
                Intelligence brief
              </span>
              <span aria-hidden className="hidden sm:inline">
                ·
              </span>
              <time dateTime={report.generated_at}>
                {new Date(report.generated_at).toLocaleDateString(undefined, {
                  dateStyle: "medium",
                })}{" "}
                {new Date(report.generated_at).toLocaleTimeString(undefined, {
                  timeStyle: "short",
                })}
              </time>
            </div>

            <h2 className="text-pretty text-xl font-semibold leading-snug tracking-tight text-foreground sm:text-2xl">
              {report.headline || "Market research report"}
            </h2>

            {report.executive_summary && !summaryMatchesHeadline(report) && (
              <div className="rounded-lg border-l-[3px] border-primary/40 bg-muted/40 px-4 py-3">
                <p className="mb-1 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
                  Summary
                </p>
                <p className="text-sm leading-relaxed text-foreground/80">{report.executive_summary}</p>
              </div>
            )}
          </div>

          <dl className="grid shrink-0 grid-cols-3 gap-2 sm:gap-3 lg:w-56 lg:grid-cols-1">
            <MetaStat label="Sources" value={report.source_count} />
            <MetaStat label="Themes" value={report.themes.length} />
            <MetaStat label="Competitors" value={report.competitors.length} />
          </dl>
        </div>
      </header>

      {toc.length > 1 && (
        <div className="sticky top-0 z-10 border-b bg-background/95 backdrop-blur-sm">
          <nav
            className="flex gap-1 overflow-x-auto px-4 py-2 sm:px-6 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden"
            aria-label="Report sections"
          >
            {toc.map((item) => (
              <a
                key={item.id}
                href={`#${item.id}`}
                onClick={() => setActiveSection(item.id)}
                className={cn(
                  "shrink-0 rounded-md px-3 py-1.5 text-xs font-medium transition-colors",
                  activeSection === item.id
                    ? "bg-primary text-primary-foreground"
                    : "text-muted-foreground hover:bg-muted hover:text-foreground",
                )}
              >
                {item.label}
              </a>
            ))}
          </nav>
        </div>
      )}

      <p className="border-b bg-muted/30 px-4 py-2 text-[11px] leading-relaxed text-muted-foreground sm:px-6">
        {judgeInProgress ? (
          <>
            Report ready — citation checks are updating live.{" "}
            <strong className="font-medium text-foreground">Checking</strong> badges resolve as
            verification completes.
          </>
        ) : (
          <>
            Tip: click <strong className="font-medium text-foreground">[n]</strong> for sources,
            verdict badges for judge notes.
          </>
        )}
      </p>

      <main className="space-y-8 px-4 py-6 sm:space-y-10 sm:px-6 sm:py-8">
        {(report.key_metrics?.length ?? 0) > 0 && (
          <ReportSection
            id="metrics"
            title="Key metrics"
            description={`${report.key_metrics!.length} headline metrics from your sources`}
            styleKey="metrics"
          >
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3">
              {report.key_metrics!.map((m, i) => (
                <MetricCard key={i} metric={m} indexOf={indexOf} paletteIndex={i} rank={i + 1} />
              ))}
            </div>
          </ReportSection>
        )}

        {(report.key_findings?.length ?? 0) > 0 && (
          <ReportSection
            id="findings"
            title="Key findings"
            description={`${report.key_findings!.length} top insights from this run`}
            styleKey="findings"
          >
            <InsightList insights={report.key_findings!} indexOf={indexOf} numbered judgeInProgress={judgeInProgress} />
          </ReportSection>
        )}

        {report.market_trends && (
          <InsightSectionBlock
            id="market-trends"
            section={report.market_trends}
            title="Market trends"
            description="Industry and macro shifts from your sources"
            styleKey="marketTrends"
            indexOf={indexOf}
            judgeInProgress={judgeInProgress}
          />
        )}

        {report.consumer_behavior && (
          <InsightSectionBlock
            id="consumer-behavior"
            section={report.consumer_behavior}
            title="Consumer behavior"
            description="Demand and adoption signals from your sources"
            styleKey="consumerBehavior"
            indexOf={indexOf}
            judgeInProgress={judgeInProgress}
          />
        )}

        {report.competitive_strategic_synthesis && (
          <ReportSection
            id="synthesis"
            title="Competitive synthesis"
            description={`${synthesisInsightCount(report.competitive_strategic_synthesis)} competitive insights`}
            styleKey="synthesis"
          >
            <p className="mb-6 rounded-xl bg-violet-500/5 px-4 py-3 text-sm leading-relaxed text-foreground/90 ring-1 ring-violet-500/10">
              {report.competitive_strategic_synthesis.summary}
            </p>
            <div className="space-y-6">
              {(report.competitive_strategic_synthesis.dynamics?.length ?? 0) > 0 && (
                <SubHeading title="Competitive dynamics" count={report.competitive_strategic_synthesis.dynamics.length}>
                  <InsightList
                    insights={report.competitive_strategic_synthesis.dynamics}
                    indexOf={indexOf}
                    numbered
                    judgeInProgress={judgeInProgress}
                  />
                </SubHeading>
              )}
              {(report.competitive_strategic_synthesis.implications?.length ?? 0) > 0 && (
                <SubHeading
                  title="Strategic signals"
                  count={report.competitive_strategic_synthesis.implications!.length}
                >
                  <InsightList
                    insights={report.competitive_strategic_synthesis.implications!}
                    indexOf={indexOf}
                    numbered
                    judgeInProgress={judgeInProgress}
                  />
                </SubHeading>
              )}
            </div>
          </ReportSection>
        )}

        {((report.opportunities?.length ?? 0) > 0 || (report.risks?.length ?? 0) > 0) && (
          <div id="signals" className="grid grid-cols-1 gap-8 lg:grid-cols-2 lg:gap-6">
            {(report.opportunities?.length ?? 0) > 0 && (
              <ReportSection
                title="Opportunities"
                description={`${report.opportunities!.length} opportunities identified`}
                styleKey="opportunities"
              >
                <InsightList insights={report.opportunities!} indexOf={indexOf} numbered judgeInProgress={judgeInProgress} />
              </ReportSection>
            )}
            {(report.risks?.length ?? 0) > 0 && (
              <ReportSection
                title="Risks"
                description={`${report.risks!.length} risks identified`}
                styleKey="risks"
              >
                <InsightList insights={report.risks!} indexOf={indexOf} numbered judgeInProgress={judgeInProgress} />
              </ReportSection>
            )}
          </div>
        )}

        {report.themes.length > 0 && (
          <ReportSection
            id="themes"
            title="Themes"
            description={`${report.themes.length} themes · ${countGroupedInsights(report.themes)} insights`}
            styleKey="themes"
          >
            <div className="space-y-6">
              {report.themes.map((theme, idx) => (
                <SubHeading
                  key={`${theme.title}-${idx}`}
                  title={theme.title}
                  subtitle={theme.summary}
                  count={theme.insights.length}
                >
                  <InsightList insights={theme.insights} indexOf={indexOf} numbered judgeInProgress={judgeInProgress} />
                </SubHeading>
              ))}
            </div>
          </ReportSection>
        )}

        {report.competitors.length > 0 && (
          <ReportSection
            id="competitors"
            title="Competitor activity"
            description={`${report.competitors.length} competitors · ${countGroupedInsights(report.competitors)} insights`}
            styleKey="competitors"
          >
            <div className="space-y-6">
              {report.competitors.map((ca, idx) => (
                <SubHeading key={`${ca.competitor}-${idx}`} title={ca.competitor} count={ca.insights.length}>
                  <InsightList insights={ca.insights} indexOf={indexOf} numbered judgeInProgress={judgeInProgress} />
                </SubHeading>
              ))}
            </div>
          </ReportSection>
        )}

        {(report.removed_insights?.length ?? 0) > 0 && (
          <ReportSection
            id="removed"
            title="Removed since last run"
            description={`${report.removed_insights!.length} insights removed`}
            styleKey="themes"
          >
            <div className="space-y-2">
              {report.removed_insights!.map((ins, j) => (
                <div
                  key={j}
                  className="flex flex-wrap items-start gap-2 rounded-xl bg-muted/30 px-4 py-3 ring-1 ring-border/40"
                >
                  <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-background text-xs font-semibold text-muted-foreground ring-1 ring-border/60">
                    {j + 1}
                  </span>
                  <DiffBadge tag="removed" />
                  <p className="flex-1 text-sm text-muted-foreground line-through">{ins.statement}</p>
                </div>
              ))}
            </div>
          </ReportSection>
        )}

        {report.outlook && (
          <ReportSection id="outlook" title="Outlook" description="What to watch next" styleKey="outlook">
            <p className="rounded-xl bg-muted/30 px-4 py-4 text-sm leading-relaxed ring-1 ring-border/40">
              {report.outlook}
            </p>
          </ReportSection>
        )}
      </main>
    </article>
  );
}

function countGroupedInsights(items: { insights: Insight[] }[]): number {
  return items.reduce((total, item) => total + item.insights.length, 0);
}

function synthesisInsightCount(synth: NonNullable<Report["competitive_strategic_synthesis"]>): number {
  return (synth.dynamics?.length ?? 0) + (synth.implications?.length ?? 0);
}

function normalizeText(text: string): string {
  return text
    .toLowerCase()
    .replace(/[^\w\s]/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

function summaryMatchesHeadline(report: Report): boolean {
  const headline = normalizeText(report.headline || "");
  const summary = normalizeText(report.executive_summary || "");
  if (!headline || !summary) return false;
  if (headline === summary) return true;

  const shorter = headline.length <= summary.length ? headline : summary;
  const longer = headline.length <= summary.length ? summary : headline;
  if (longer.includes(shorter) && shorter.length / longer.length >= 0.65) return true;

  const headlineWords = new Set(headline.split(" ").filter((w) => w.length > 3));
  const summaryWords = summary.split(" ").filter((w) => w.length > 3);
  if (headlineWords.size === 0 || summaryWords.length === 0) return false;
  const overlap = summaryWords.filter((w) => headlineWords.has(w)).length;
  return overlap / Math.max(headlineWords.size, summaryWords.length) >= 0.75;
}

function MetaStat({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-lg border bg-muted/20 px-3 py-2.5 text-center lg:flex lg:items-center lg:justify-between lg:text-left">
      <dt className="text-[10px] font-medium uppercase tracking-wider text-muted-foreground">{label}</dt>
      <dd className="mt-0.5 text-lg font-semibold tabular-nums text-foreground lg:mt-0">{value}</dd>
    </div>
  );
}

function buildSourceIndex(report: Report): Map<string, number> {
  const map = new Map<string, number>();
  let n = 1;
  const add = (ids: string[]) => {
    for (const id of ids) {
      if (!map.has(id)) map.set(id, n++);
    }
  };
  for (const m of report.key_metrics ?? []) add(m.citations);
  const synth = report.competitive_strategic_synthesis;
  if (synth) {
    for (const i of synth.dynamics) add(i.citations);
    for (const i of synth.implications ?? []) add(i.citations);
  }
  for (const i of report.key_findings ?? []) add(i.citations);
  for (const section of [report.market_trends, report.consumer_behavior]) {
    if (section) for (const i of section.insights) add(i.citations);
  }
  for (const i of report.opportunities ?? []) add(i.citations);
  for (const i of report.risks ?? []) add(i.citations);
  for (const t of report.themes) for (const i of t.insights) add(i.citations);
  for (const c of report.competitors) for (const i of c.insights) add(i.citations);
  return map;
}

function buildToc(report: Report): { id: string; label: string }[] {
  const items: { id: string; label: string }[] = [];
  if ((report.key_metrics?.length ?? 0) > 0) items.push({ id: "metrics", label: "Metrics" });
  if ((report.key_findings?.length ?? 0) > 0) items.push({ id: "findings", label: "Findings" });
  if (report.market_trends) items.push({ id: "market-trends", label: "Trends" });
  if (report.consumer_behavior) items.push({ id: "consumer-behavior", label: "Consumers" });
  if (report.competitive_strategic_synthesis) items.push({ id: "synthesis", label: "Synthesis" });
  if ((report.opportunities?.length ?? 0) > 0 || (report.risks?.length ?? 0) > 0) {
    items.push({ id: "signals", label: "Signals" });
  }
  if (report.themes.length > 0) items.push({ id: "themes", label: "Themes" });
  if (report.competitors.length > 0) items.push({ id: "competitors", label: "Competitors" });
  if (report.outlook) items.push({ id: "outlook", label: "Outlook" });
  return items;
}

function InsightSectionBlock({
  id,
  section,
  title,
  description,
  styleKey,
  indexOf,
  judgeInProgress,
}: {
  id: string;
  section: InsightSection;
  title: string;
  description: string;
  styleKey: keyof typeof SECTION_META;
  indexOf: IndexFn;
  judgeInProgress: boolean;
}) {
  return (
    <ReportSection
      id={id}
      title={title}
      description={`${description} · ${section.insights.length} insights`}
      styleKey={styleKey}
    >
      <p className="mb-4 rounded-xl bg-muted/30 px-4 py-3 text-sm leading-relaxed text-foreground/90 ring-1 ring-border/40">
        {section.summary}
      </p>
      <InsightList
        insights={section.insights}
        indexOf={indexOf}
        numbered
        judgeInProgress={judgeInProgress}
      />
    </ReportSection>
  );
}

function ReportSection({
  id,
  title,
  description,
  styleKey,
  children,
}: {
  id?: string;
  title: string;
  description?: string;
  styleKey: keyof typeof SECTION_META;
  children: React.ReactNode;
}) {
  const meta = SECTION_META[styleKey];
  const Icon = meta.icon;

  return (
    <section id={id} className="scroll-mt-20">
      <div className="mb-4 flex items-center gap-3 border-b pb-3">
        <span
          className={cn(
            "flex h-9 w-9 shrink-0 items-center justify-center rounded-lg",
            meta.bg,
            meta.tint,
          )}
        >
          <Icon className="h-4 w-4" />
        </span>
        <div className="min-w-0 flex-1">
          <h3 className="font-semibold text-foreground">{title}</h3>
          {description && <p className="mt-0.5 text-xs text-muted-foreground">{description}</p>}
        </div>
      </div>
      {children}
    </section>
  );
}

function SubHeading({
  title,
  subtitle,
  count,
  children,
}: {
  title: string;
  subtitle?: string;
  count?: number;
  children: React.ReactNode;
}) {
  return (
    <div className="space-y-3">
      <div className="flex items-baseline justify-between gap-3">
        <h4 className="text-sm font-semibold text-foreground">{title}</h4>
        {count !== undefined && (
          <span className="shrink-0 text-xs tabular-nums text-muted-foreground">{count} items</span>
        )}
      </div>
      {subtitle && <p className="-mt-1 text-xs leading-relaxed text-muted-foreground">{subtitle}</p>}
      <div className="space-y-2">{children}</div>
    </div>
  );
}

const METRIC_PALETTES = [
  {
    card: "from-sky-500/10 to-cyan-500/5 ring-sky-500/15",
    label: "text-sky-700",
    value: "text-sky-950",
    context: "text-sky-900/60",
    rank: "bg-sky-500/15 text-sky-800 ring-sky-500/20",
  },
  {
    card: "from-violet-500/10 to-purple-500/5 ring-violet-500/15",
    label: "text-violet-700",
    value: "text-violet-950",
    context: "text-violet-900/60",
    rank: "bg-violet-500/15 text-violet-800 ring-violet-500/20",
  },
  {
    card: "from-emerald-500/10 to-teal-500/5 ring-emerald-500/15",
    label: "text-emerald-700",
    value: "text-emerald-950",
    context: "text-emerald-900/60",
    rank: "bg-emerald-500/15 text-emerald-800 ring-emerald-500/20",
  },
  {
    card: "from-amber-500/10 to-orange-500/5 ring-amber-500/15",
    label: "text-amber-800",
    value: "text-amber-950",
    context: "text-amber-900/60",
    rank: "bg-amber-500/15 text-amber-900 ring-amber-500/20",
  },
  {
    card: "from-rose-500/10 to-pink-500/5 ring-rose-500/15",
    label: "text-rose-700",
    value: "text-rose-950",
    context: "text-rose-900/60",
    rank: "bg-rose-500/15 text-rose-800 ring-rose-500/20",
  },
  {
    card: "from-indigo-500/10 to-blue-500/5 ring-indigo-500/15",
    label: "text-indigo-700",
    value: "text-indigo-950",
    context: "text-indigo-900/60",
    rank: "bg-indigo-500/15 text-indigo-800 ring-indigo-500/20",
  },
] as const;

function MetricCard({
  metric,
  indexOf,
  paletteIndex,
  rank,
}: {
  metric: KeyMetric;
  indexOf: IndexFn;
  paletteIndex: number;
  rank: number;
}) {
  const palette = METRIC_PALETTES[paletteIndex % METRIC_PALETTES.length];

  return (
    <div
      className={cn(
        "flex min-h-[10rem] flex-col rounded-2xl bg-gradient-to-br p-5 ring-1 transition-shadow hover:shadow-md",
        palette.card,
      )}
    >
      <div className="flex items-center gap-2.5">
        <span
          className={cn(
            "flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-xs font-semibold ring-1",
            palette.rank,
          )}
        >
          {rank}
        </span>
        <p className={cn("text-[11px] font-semibold uppercase tracking-wider", palette.label)}>{metric.label}</p>
      </div>
      <p className={cn("mt-3 text-3xl font-bold tracking-tight", palette.value)}>{metric.value}</p>
      <p className={cn("mt-2 flex-1 text-xs leading-relaxed", palette.context)}>{metric.context}</p>
      {metric.citations.length > 0 && (
        <div className="mt-4 flex flex-wrap justify-end gap-1 border-t border-black/[0.04] pt-3">
          {metric.citations.map((cid) => (
            <SourceChip key={cid} sourceId={cid} index={indexOf(cid)} highlightText={metric.context} />
          ))}
        </div>
      )}
    </div>
  );
}

function InsightList({
  insights,
  indexOf,
  numbered = false,
  judgeInProgress = false,
}: {
  insights: Insight[];
  indexOf: IndexFn;
  numbered?: boolean;
  judgeInProgress?: boolean;
}) {
  return (
    <div className="space-y-3">
      {insights.map((ins, j) => (
        <InsightCard
          key={j}
          insight={ins}
          indexOf={indexOf}
          rank={numbered ? j + 1 : undefined}
          judgeInProgress={judgeInProgress}
        />
      ))}
    </div>
  );
}

function insightAccent(verdict?: JudgeVerdict | null) {
  switch (verdict) {
    case "verified":
      return "border-l-[3px] border-l-emerald-400";
    case "unsupported":
      return "border-l-[3px] border-l-amber-400";
    case "contradicted":
      return "border-l-[3px] border-l-red-400";
    default:
      return "";
  }
}

function InsightCard({
  insight,
  indexOf,
  rank,
  judgeInProgress = false,
}: {
  insight: Insight;
  indexOf: IndexFn;
  rank?: number;
  judgeInProgress?: boolean;
}) {
  return (
    <div
      className={cn(
        "rounded-lg border bg-background p-3.5 sm:p-4",
        insightAccent(insight.judge_verdict),
      )}
    >
      <div className="flex flex-wrap items-start gap-x-3 gap-y-2">
        {rank !== undefined && (
          <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-foreground/[0.06] text-xs font-semibold text-foreground ring-1 ring-border/50">
            {rank}
          </span>
        )}
        <p className="min-w-[12rem] flex-1 text-sm leading-relaxed text-foreground/90">{insight.statement}</p>
        <div className="flex flex-wrap items-center gap-1.5">
          <DiffBadge tag={insight.diff_tag} />
          <JudgeBadge
            verdict={insight.judge_verdict}
            rationale={insight.judge_rationale}
            pending={judgeInProgress}
          />
        </div>
      </div>
      {insight.citations.length > 0 && (
        <div className="mt-3 flex flex-wrap justify-end gap-1 border-t border-border/40 pt-3">
          {insight.citations.map((cid) => (
            <SourceChip key={cid} sourceId={cid} index={indexOf(cid)} highlightText={insight.statement} />
          ))}
        </div>
      )}
    </div>
  );
}

function DiffBadge({ tag }: { tag?: DiffTag | null }) {
  if (!tag || tag === "unchanged") return null;
  if (tag === "new") {
    return <Badge className="bg-emerald-600 hover:bg-emerald-600">NEW</Badge>;
  }
  return <Badge variant="secondary">REMOVED</Badge>;
}
