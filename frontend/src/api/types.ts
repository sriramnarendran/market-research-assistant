/** Wire types — kept in lock-step with backend app/api/schemas.py. */

export type RunStatus =
  | "queued"
  | "fetching"
  | "extracting"
  | "researching"
  | "synthesizing"
  | "judging"
  | "done"
  | "done_with_warnings"
  | "failed_fetch"
  | "failed_agent"
  | "failed_synth"
  | "failed_budget"
  | "failed_unknown";

export const TERMINAL_STATUSES: ReadonlySet<RunStatus> = new Set<RunStatus>([
  "done",
  "done_with_warnings",
  "failed_fetch",
  "failed_agent",
  "failed_synth",
  "failed_budget",
  "failed_unknown",
]);

export type JudgeVerdict = "verified" | "unsupported" | "contradicted";
export type DiffTag = "new" | "unchanged" | "removed";

export interface Insight {
  statement: string;
  citations: string[]; // UUIDs
  judge_verdict?: JudgeVerdict | null;
  judge_rationale?: string | null;
  diff_tag?: DiffTag | null;
}

export interface KeyMetric {
  label: string;
  value: string;
  context: string;
  citations: string[];
}

export interface Theme {
  title: string;
  summary: string;
  insights: Insight[];
}

export interface CompetitorActivity {
  competitor: string;
  insights: Insight[];
}

/** Cross-competitor synthesis grounded in cited facts. */
export interface CompetitiveStrategicSynthesis {
  summary: string;
  dynamics: Insight[];
  implications?: Insight[];
}

/** Narrative section with cited insight bullets. */
export interface InsightSection {
  summary: string;
  insights: Insight[];
}

export interface Report {
  /** Brief sections — populated on new runs; may be empty on older reports. */
  headline?: string;
  executive_summary?: string;
  key_metrics?: KeyMetric[];
  key_findings?: Insight[];
  market_trends?: InsightSection | null;
  consumer_behavior?: InsightSection | null;
  opportunities?: Insight[];
  risks?: Insight[];
  competitive_strategic_synthesis?: CompetitiveStrategicSynthesis | null;
  outlook?: string | null;
  /** Claims present in prior run but absent now. */
  removed_insights?: Insight[];

  /** Detail sections. */
  themes: Theme[];
  competitors: CompetitorActivity[];
  topics: string[];
  source_count: number;
  generated_at: string;
}

export interface RunSummary {
  id: string;
  status: RunStatus;
  topics: string[];
  urls: string[];
  created_at: string;
  completed_at?: string | null;
  failure_reason?: string | null;
  has_report: boolean;
}

export interface UrlFetchFailure {
  url: string;
  error: string;
}

export interface RunDetail {
  id: string;
  status: RunStatus;
  topics: string[];
  urls: string[];
  created_at: string;
  completed_at?: string | null;
  failure_reason?: string | null;
  url_fetch_failures?: UrlFetchFailure[];
  report?: Report | null;
}

export interface SourceSummary {
  id: string;
  url: string;
  origin: "url_path" | "tavily";
  title?: string | null;
  topic_match?: string | null;
  bytes: number;
  fetched_at: string;
}

export interface SourceDetail {
  id: string;
  run_id: string;
  url: string;
  origin: "url_path" | "tavily";
  title?: string | null;
  topic_match?: string | null;
  fetched_text: string;
  bytes: number;
  fetched_at: string;
}

export interface RunCreateRequest {
  topics: string[];
  urls: string[];
  prior_run_id?: string | null;
}

export interface RunCreateResponse {
  id: string;
  status: RunStatus;
}

export interface SignupRequest {
  email: string;
  password: string;
}

export interface LoginRequest {
  email: string;
  password: string;
}

export interface UserResponse {
  id: string;
  email: string;
  role: "user" | "admin";
}

export interface AdminOverview {
  total_users: number;
  active_users_7d: number;
  total_runs: number;
  runs_today: number;
  completed_runs: number;
  in_progress_runs: number;
  failed_runs: number;
  reports_generated: number;
  total_sources: number;
  url_sources: number;
  search_sources: number;
  sources_today: number;
}

export interface UsageDayRow {
  day: string;
  provider: string;
  phase: string;
  input_tokens: number;
  output_tokens: number;
  cost_usd: number;
}

export interface RunMetrics {
  total_runs: number;
  success_rate: number;
  p50_duration_sec: number | null;
  p95_duration_sec: number | null;
  failure_breakdown: Record<string, number>;
}

export interface UserUsageSummary {
  user_id: string;
  email: string;
  total_runs: number;
  input_tokens: number;
  output_tokens: number;
  cost_usd: number;
}

export interface AppErrorRow {
  id: string;
  created_at: string;
  payload: Record<string, unknown>;
}
