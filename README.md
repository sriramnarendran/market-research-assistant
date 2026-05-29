# Market Research Intelligence Assistant

A web application that ingests competitor names / topics and source URLs, runs a hybrid AI pipeline (deterministic for URLs, agentic for topics), and produces a structured market-intelligence report with per-insight source citations, an independent LLM-as-judge verdict, PDF export, and change detection on re-runs. **All pipeline LLM phases use GPT-5** served through Azure OpenAI (`gpt-5` deployments).

---

## Problem statement

Market and competitive research is slow, fragmented, and hard to trust: analysts juggle search results, ad-hoc notes, and uncited LLM summaries. This app automates the loop — ingest topics and URLs, extract grounded facts, synthesise a structured brief, and independently verify each insight against its cited sources.

## Solution approach

1. **Hybrid pipeline** — user URLs are fetched and extracted deterministically; topics trigger an agentic Tavily research loop.
2. **Structured synthesis** — a Pydantic AI synth agent outputs a typed `Report` (headline, executive summary, themes, competitors, metrics).
3. **Independent judge** — a separate Azure OpenAI GPT-5 deployment scores each insight (`verified` / `unsupported` / `contradicted`).
4. **Change detection** — re-runs with `prior_run_id` hash claims and tag insights as NEW / unchanged / removed.
5. **Export** — completed reports download as PDF via WeasyPrint.

See [docs/design.md](docs/design.md) and [docs/prompts.md](docs/prompts.md) for architecture and prompt strategy.

## AI agents

All agents are built with [Pydantic AI](https://ai.pydantic.dev/) — structured JSON output, optional tools. They run on **GPT-5** via Azure OpenAI`.

| Agent | When it runs | Input → output |
|-------|----------------|----------------|
| **Extract** | After each URL or research source is fetched | One source’s text → list of grounded `Fact` objects (`claim`, `evidence`, `confidence`, `source_id`) |
| **Research** | When the user supplies topics (one parallel task per keyword) | Topics + Tavily `search` tool loop → persisted sources; agent decides query angles until coverage caps or iteration limit |
| **Synth** | Once all facts are merged | All `Fact`s + topics → structured `Report` (headline, metrics, findings, themes, competitors, optional sections) |
| **Judge** | After synthesis (separate GPT-5 deployment) | One insight + cited source excerpts → `verified` / `unsupported` / `contradicted` + rationale |

**Not LLM agents:** URL fetch (httpx + trafilatura + SSRF checks), article hydration for Tavily hits, balanced source selection, dedupe, and claim-hash change detection run as deterministic Python in the pipeline orchestrator.

Flow: **fetch → extract → [research → hydrate → extract] → synth → judge → PDF**.

## Tech stack

| Layer | Technology |
|-------|------------|
| Frontend | React 18, Vite, TypeScript, Tailwind |
| Backend | Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2, Alembic |
| AI | Pydantic AI agents; **GPT-5** via Azure OpenAI (main + judge deployments) |
| Search | Tavily |
| Fetch / extract | httpx, trafilatura |
| PDF | Jinja2 + WeasyPrint |
| Auth | Argon2id + JWT (httpOnly cookies) |
| Observability | structlog, Postgres event tables |
| Local DB | Postgres 16 (docker-compose) — optional; can point at Supabase locally |
| Production DB | [Supabase](https://supabase.com) (managed Postgres) |
| Hosting | Azure Static Web Apps (frontend) + Container Apps (backend container) |

## Local build & run

### Prerequisites

- Python 3.12+, Node.js 20+, pnpm, Docker Desktop, [uv](https://docs.astral.sh/uv/)

### Environment

Copy `backend/.env.example` → `backend/.env` and set Azure OpenAI + Tavily keys. Use `LLM_MODE=test` to run without external LLM calls.

For **Supabase** instead of local Docker Postgres: create a project at [supabase.com](https://supabase.com), copy the **Session pooler** URI (port 5432) for Azure, or direct URI for local dev. See comments in `.env.example`.

**WeasyPrint (PDF export)** requires system libraries locally:

```bash
# macOS (Apple Silicon or Intel Homebrew)
brew install pango gdk-pixbuf libffi
```

The backend auto-configures Homebrew library paths on macOS. Restart `uvicorn` after installing.

### Start

```bash
# Postgres (local) — skip if DATABASE_URL points at Supabase
docker compose -f infra/docker-compose.yml up -d

# Backend
cd backend && uv sync --all-extras
uv run alembic upgrade head    # applies schema to Supabase or local Postgres
uv run python -m app.db.seed   # optional demo users
uv run uvicorn app.main:app --reload --port 8000

# Frontend (new terminal)
cd frontend && pnpm install && pnpm dev
```

Open http://localhost:5173.

**Dev auth bypass:** with `AUTH_DEV_BYPASS=true`, unauthenticated requests use the seeded dev user.



## AI tools, models, and libraries

- [Pydantic AI](https://ai.pydantic.dev/) — agent framework with structured output and tool use
- **GPT-5 (Azure OpenAI)** — extract, research, coverage queries, synth (`AZURE_OPENAI_MAIN_DEPLOYMENT`); judge (`AZURE_OPENAI_JUDGE_DEPLOYMENT`). Defaults in `.env.example`: `gpt-5-mini`; point `MAIN` at `gpt-5` for the full model.
- [Tavily](https://tavily.com/) — web search in the research agent
- [Trafilatura](https://trafilatura.readthedocs.io/) — article extraction
- [WeasyPrint](https://weasyprint.org/) — PDF report export
- [tiktoken](https://github.com/openai/tiktoken) — fetch-path token cap

Prompt rationale and examples: [docs/prompts.md](docs/prompts.md).

## Design decisions & trade-offs

Architecture detail lives in [docs/design.md](docs/design.md). Below is the decision log for the full project — what we chose, why, and what we gave up.

### Pipeline & orchestration

| Decision | Rationale | Trade-off |
|----------|-----------|-----------|
| **Hybrid URL + topic paths** | User URLs are high-trust when provided; topics need open-web search via Tavily | Two ingestion paths, duplicate extract/hydrate logic, harder to reason about coverage |
| **URL leg runs before research** | Deterministic fetch/extract gives fast value; topic research fills gaps | URL sources consume extract budget first; research gets remaining per-topic slots |
| **In-process `BackgroundTasks` worker** | Zero extra infra for take-home; simple local dev | Runs lost on process restart; no horizontal worker scale or retry queue |
| **Postgres `run_events` state machine** | Every transition is queryable for debugging without a log stack | Not real-time; clients poll for status |
| **Soft-fail research, hard-fail empty facts** | Partial Tavily failure should not kill a URL-only run | A topic can finish with zero sources and still reach synth if URLs produced facts |
| **Per-run token budget + judge reserve** | Prevents extract/synth from starving the judge phase | Long reports may skip late judge calls when budget is tight |
| **Separate DB session per parallel task** | SQLAlchemy `AsyncSession` is not safe across asyncio tasks | More connections; each task commits its own usage rows |

### Fetch & content extraction

| Decision | Rationale | Trade-off |
|----------|-----------|-----------|
| **httpx + trafilatura (not Tavily Extract as primary)** | Full control over SSRF, size caps, retries; trafilatura is strong on news/blog HTML | JS-heavy SPAs and paywalls often fail; no built-in search fallback on fetch |
| **Tavily for search only** | Search ranking and snippets are Tavily’s strength; article body comes from our fetcher | Extra hydrate step after Tavily; snippet-only persist if full fetch fails |
| **500 KB stream cap + 80k token truncate** | Bounds cost and latency before LLM extract | Long PDFs/reports are truncated; tail facts may be lost |
| **Browser-like User-Agent + retry on 429/5xx** | Many publishers block obvious bots | Still blocked by aggressive anti-bot; not a general scraper |
| **Parallel URL fetch with per-URL commit** | UI can show sources as they land; failures are isolated | Many small transactions vs one bulk commit |

### Research & topic coverage

| Decision | Rationale | Trade-off |
|----------|-----------|-----------|
| **Parallel research per topic (`asyncio`, `RESEARCH_CONCURRENCY`)** | Each keyword gets its own Tavily loop and DB session; avoids one agent favoring the first topic | Increased LLM cost for 3 topics; shared URL dedupe via `SharedResearchState` |
| **LLM-generated coverage queries (`coverage_queries.py`)** | Model supplies aliases, tickers, `site:` filters — no hardcoded vendor maps | Extra LLM call per uncovered topic; fallback templates if generation fails |
| **Trust targeted Tavily queries for filtering** | If the query targets one keyword, accept results on score — LLM already shaped the search | Low-score or off-topic hits can slip through on dedicated searches |
| **Per-topic source cap (`ceil(MAX_EXTRACT_SOURCES / N)`)** | Stops one keyword from consuming the entire extract budget | A hot topic may hit its cap while another is still sparse |
| **Coverage guarantee before/after agent** | Deterministic gap-fill ensures at least one source row per topic when Tavily can find one | Many Tavily calls on failure; pipeline continues even if a topic stays uncovered |

### Synthesis & report structure

| Decision | Rationale | Trade-off |
|----------|-----------|-----------|
| **Single synth agent → typed `Report` (Pydantic AI)** | One structured pass; schema enforces sections and citations | Large fact sets → long context; one failure mode for the whole report |
| **Citation `@output_validator` + `ModelRetry`** | Fabricated `source_id`s are caught before persist | Extra LLM round-trips on bad citations |
| **URL-only runs: fill all fact-supported sections** | URLs often carry rich adoption/company news; shouldn’t collapse into key_findings only | More prompt complexity; model may still under-fill optional sections |
| **Post-synth dedupe (`dedupe.py`)** | Stops the same claim appearing in key_findings, themes, and competitors | Aggressive similarity threshold can drop valid angles; sections need ≥1 unique bullet |
| **`topic_scope.py` reorders when topics exist** | Headline and findings lead with user keywords | Non-topic companies demoted even if they dominate the sources |
| **Boilerplate fact filter (`fact_filter.py`)** | Drops copyright/trademark/contact junk from extract | Heuristic; may rarely drop borderline legal context |

### Judge & verification

| Decision | Rationale | Trade-off |
|----------|-----------|-----------|
| **Judge on separate Azure OpenAI deployment** | Statistical independence from synth/extract when deployments differ | Same deployment = weak independence; doubles Azure model surface |
| **Per-insight judge (not whole-report)** | Granular badges; incremental PDF/UI updates | N × LLM calls; dominant cost on long reports |
| **`done_with_warnings` only on `contradicted`** | `unsupported` is advisory; don’t flag the whole run | Users may miss unsupported bullets if they don’t read badges |
| **Never drop judged insights** | Transparency — show disagreement rather than hide | PDF/UI can feel noisy when many flags appear |

### Data, auth & deployment

| Decision | Rationale | Trade-off |
|----------|-----------|-----------|
| **Azure Static Web Apps + Container Apps** | Simple split: static frontend, containerised API | Two deploy paths; CORS/cookie wiring between SWA and backend |
| **WeasyPrint PDF (server-side)** | Full CSS control; no headless browser in CI/prod | Native deps (Pango, GDK); macOS dev needs Homebrew libraries |
| **Postgres event tables for observability** | Queryable audit trail without Datadog/etc. | Retention job required; not live dashboards |

### AI framework & prompts

| Decision | Rationale | Trade-off |
|----------|-----------|-----------|
| **Pydantic AI for all agents** | Typed `output_type`, tool loop, `@output_validator`, provider swap in `models.py` | Framework coupling; upgrade churn |
| **Prompts as Python constants** | Grep/refactor friendly; part of import graph | Not editable by non-devs without redeploy |
| **`<topic>` / `<source>` XML wrapping** | Prompt-injection defence for user content | Escaping overhead; models must treat tags as delimiters |
| **Strict grounding rules in every phase** | Reduce hallucination in extract/synth/judge | Models refuse or thin-out when sources are sparse |
| **Research agent plans dimensions dynamically** | No fixed checklist — adapts to company vs product vs sector | Less predictable Tavily spend; quality varies by model |

### Frontend & UX

| Decision | Rationale | Trade-off |
|----------|-----------|-----------|
| **Poll run status (no WebSockets)** | Matches BackgroundTasks worker; simple TanStack Query | Higher latency to see phase changes; more API load |
| **Incremental judge snapshots** | Report JSON updates per insight during judge phase | Many DB writes; large JSON patches over the wire |
| **Source feed with `topic_match` badges** | Shows which keyword each Tavily hit supports | Clutter when tags missing or wrong |

### Principles we consistently prioritized

1. **Grounding over fluency** — citations, validators, and judge over polished but uncited prose.
2. **Simplicity over scale** — in-process worker, claim hashing, single-region deploy for the take-home scope.
3. **Transparency over auto-hiding** — flagged insights stay in the report; failures surface in `run_events`.
4. **Bounded cost** — token budgets, extract caps, concurrency semaphores, and Tavily day windows.

See [docs/prompts.md](docs/prompts.md) for prompt-level rationale and examples.

## AI usage citations

This project was built with assistance from **Cursor** (AI pair-programming IDE) and **Claude / GPT** models via Cursor Agent. AI was used for:

- Scaffolding FastAPI routes, SQLAlchemy models, and Alembic migrations
- Drafting Pydantic AI agent definitions and prompt templates (reviewed against grounding requirements)
- Frontend shadcn/ui components, TanStack Query wiring, and UX polish
- Test fixtures and documentation structure

All AI-generated code was reviewed, run against tests, and adjusted for this codebase’s conventions. Prompt strategy and model choices are documented in [docs/prompts.md](docs/prompts.md).

## Known limitations & production upgrades

- **Worker queue** — replace `BackgroundTasks` with Redis + arq or Azure Service Bus for durable jobs.
- **Managed Identity** — swap API keys for Azure AD auth to OpenAI.
- **Supabase networking** — enable network restrictions / private link for production.
- **Semantic diff** — embedding-based claim matching instead of SHA256 hashes.
- **Real-time status** — WebSockets or SSE instead of polling.
- **PDF on macOS dev** — requires Homebrew WeasyPrint libraries; Docker image includes them for production.

## Project layout

```
backend/    FastAPI + Pydantic AI pipeline + PDF export
frontend/   React + Vite
infra/      docker-compose (local)
docs/       design.md, prompts.md
.github/    CI/CD workflows
```

## License

Take-home assignment submission.
