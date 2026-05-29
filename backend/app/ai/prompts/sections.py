"""Report section specs and research coverage — shared by research and synthesis."""

from __future__ import annotations

from app.ai.recency import recency_context_block
from app.guardrails.wrapping import wrap_topics

RESEARCH_SYSTEM_COVERAGE = """\
What to collect (feeds the report sections downstream)
------------------------------------------------------
Your searches supply facts for a structured market-intelligence report with \
sections: headline, executive_summary, key_metrics, key_findings, market_trends, \
consumer_behavior, themes, competitors, competitive_strategic_synthesis, \
opportunities, risks, outlook.

**You choose the analysis dimensions dynamically** — there is no fixed checklist. \
Before your first `search`, infer what dimensions matter for the user's \
keywords and what a Product/GTM reader would need to compare them.

Planning analysis dimensions (do this first)
----------------------------------------------
From the user keywords in <topic> tags, decide what to investigate:

  - **Entity type:** Is each keyword a company, product, industry segment, \
    technology, regulation, or something else? Dimensions should match \
    (e.g. public companies → earnings/investor news; products → releases; \
    sectors → adoption/regulation).
  - **Report coverage:** What would populate key_findings, key_metrics, \
    market_trends, consumer_behavior, competitors[], and themes[]? Plan \
    dimensions that yield concrete, recent, citable facts — not generic background.
  - **Multi-keyword runs:** When 2+ keywords appear, include dimensions that \
    support **comparison** (each company's moves in parallel categories) as \
    well as **cross-cutting themes** that span them.
  - **Recency:** Favor dimensions that surface **current** news (launches, \
    filings, announcements) over historical retrospectives.

Aim for **4–6 tailored dimensions** per run (fewer if keywords are narrow, \
more if broad). Examples of dimension *types* (pick what fits — do not copy \
this list blindly):
  - product/feature launches, pricing/packaging, partnerships/M&A, \
    earnings/metrics, strategy/positioning, regulatory/legal, customer/GTM wins, \
    developer ecosystem, geographic expansion, competitive benchmarks, \
    **market/industry trends**, **consumer demand and adoption signals**.

When the user supplied **two or more** keywords, **each keyword MUST receive at \
least one successful search** that collects sources before you finish. **Balance \
collection evenly** — each keyword may contribute at most \
``ceil(MAX_EXTRACT_SOURCES / topic_count)`` sources; once a keyword hits that \
quota, search other keywords instead.

Query construction (mandatory)
------------------------------
Every `search` query MUST:
  - Include **at least one exact user keyword** from the <topic> tags.
  - Add **entity intelligence** the search engine needs: official names, common \
    aliases, parent companies, ticker symbols, and `site:` filters for official \
    blogs or newsrooms when that helps find primary sources.
  - Target **one dimension you planned** for that keyword (name it in `rationale`).
  - Add **recency** — current calendar year and/or "latest", "news".

In each `search` call's `rationale`, briefly state:
  1. Which keyword and planned dimension you are targeting.
  2. Which report section(s) this should feed (e.g. key_metrics, competitors).

Good examples (user topics: meta, google — after planning dimensions):
  - "Meta AI agents enterprise adoption 2026 site:about.meta.com"
  - "Alphabet GOOGL Google Gemini cloud AI announcement 2026"
  - "Meta vs Google enterprise AI positioning latest news 2026"

Bad examples:
  - "tech industry trends 2026" (no user keyword or entity names)
  - "google" alone (no planned dimension, no recency modifier, no aliases)
  - Reusing the same dimension when that angle already returned strong results

Stop when your planned dimensions have useful coverage for each keyword, or \
you hit the iteration cap — then produce final output.
"""

SYNTH_SECTION_DEFINITIONS = """\
Report sections — purpose, requirements, and fill order
-------------------------------------------------------
Organize input `Fact` objects into these sections. Each section has a distinct \
job; do not reuse the same fact in multiple insight bullets (see No repetition).

**Fill order:** key_findings → market_trends → consumer_behavior → \
competitors[] → themes[] → competitive_strategic_synthesis (if applicable). \
Optional sections only when facts support them. **Use every distinct \
high-confidence fact at least once** across the report — do not leave facts unused.

### headline (required when any facts exist)
- **Purpose:** Single scan line for executives.
- **Format:** One sentence, ≤ 240 characters.
- **Content:** The newest, highest-signal development **among user keywords** in \
  <topic> tags. Never lead with companies outside those keywords (e.g. KPMG, \
  Anthropic, OpenAI, Deloitte) unless they are user topics.

### executive_summary (required when any facts exist)
- **Purpose:** Short narrative before detail sections.
- **Format:** 3–6 sentences, ≤ 1500 characters; prose only (no bullets).
- **Content:** Who did what and what changed across all sources. **Address every \
  user keyword** in <topic> tags — if a keyword has no supporting facts, state \
  that explicitly (e.g. "No recent sources covered Amazon."). Lead with the \
  most recent facts. No recommendations.

### key_metrics (required when ≥2 quantified facts exist; 2–6 items)
- **Purpose:** Stat cards for quantitative facts — the scannable numbers block.
- **Format:** Each item: `label`, `value`, `context`, `citations`.
- **Content:** Pull counts, percentages, dollar amounts, growth multiples, and \
  dated milestones from input facts into stat cards **before** reusing the same \
  figures in insight bullets. **Prioritize metrics about user keywords** in \
  <topic> tags. Required when the facts contain ≥2 distinct quantified values. \
  Never invent figures.

### key_findings (required, 4–6 items when enough distinct facts exist)
- **Purpose:** Top headlines an analyst reads first.
- **Format:** One cited `Insight` per item; one sentence each (8–800 chars).
- **Content:** The **highest-signal unique** developments — each bullet a \
  different fact. **At least half must be about user keywords** in <topic> tags. \
  Peripheral companies (consultancies, partners, labs) may appear at most once \
  here; put their context in themes[] instead. Prefer recent, high-confidence \
  facts. If fewer than 4 unique facts exist, output fewer; do not pad or repeat.

### market_trends (optional; omit if unsupported)
- **Purpose:** Industry-wide shifts, macro drivers, technology adoption, \
  regulation, or supply/demand dynamics **as described in sources** — not \
  single-company product news.
- **Format:** `summary` (2–4 sentences) + `insights[]` with 2–6 cited bullets.
- **Content:** Cross-industry or sector patterns (e.g. "AI memory demand surge", \
  "enterprise SaaS consolidation"). Must **not** duplicate `key_findings` \
  bullets — use facts with a market-wide angle or omit.

### consumer_behavior (optional; omit if unsupported)
- **Purpose:** Buyer, user, or demand-side signals from sources: adoption rates, \
  purchasing patterns, segment preferences, churn, usage growth, pricing \
  sensitivity — factual only.
- **Format:** `summary` (2–4 sentences) + `insights[]` with 2–6 cited bullets.
- **Content:** How customers or markets are behaving per sources. Must **not** \
  duplicate `key_findings` or `market_trends` bullets.

### competitive_strategic_synthesis (optional; null if unsupported)
- **When:** Two or more companies appear in facts/topics AND you can write \
  3+ cross-company dynamics without repeating key_findings.
- **summary:** 3–6 sentences comparing what each company did — facts only, \
  no new claims.
- **dynamics (3–5 items):** Each insight MUST name **two or more companies** \
  in one sentence and contrast their moves with citations. No single-company \
  bullets here.
- **implications (0–4 items):** Optional; same rules as opportunities.

### opportunities (optional, 0–5 items)
- **Purpose:** Market openings **as described in sources**.
- **Content:** Factual observations only — not "you should" advice. Empty if \
  sources do not describe openings.

### risks (optional, 0–5 items)
- **Purpose:** Threats or negative shifts **as described in sources**.
- **Content:** Factual observations only — not warnings to the reader. Empty \
  if unsupported.

### themes[] (required, 3–6 when enough cross-cutting facts exist)
- **Purpose:** Industry patterns that cut across companies or topics.
- **Format:** Each theme: `title`, 1–2 sentence `summary`, ≥ 1 cited insight.
- **Content:** Cross-cutting trends (e.g. "agentic search", "VR platform \
  split"). Insights must **not** duplicate `key_findings` or `competitors[]` \
  bullets — use a different angle or omit the theme.

### competitors[] (required when facts name specific companies)
- **Purpose:** Per-company activity log **for user keywords only**.
- **Format:** `competitor` = **exact user keyword string** from <topic> tags \
  (e.g. "google", not "Alphabet"); `insights[]` = cited one-sentence facts.
- **Content:** **ONLY user keywords** as row names — never Anthropic, KPMG, \
  OpenAI, Deloitte, Graebel, etc. Include one row per user keyword when facts \
  support that entity. Product launches, pricing, partnerships, funding, GTM, \
  metrics, positioning — **only facts not already in key_findings, market_trends, \
  or consumer_behavior**. Include **2–5 substantive insights per company** when \
  facts allow — never copyright/trademark/contact boilerplate. Prefer facts where \
  the company is the **subject** of the move (not merely mentioned as a partner \
  on another company's site). If a keyword only appears as a partner/customer in \
  another keyword's sources, note that gap in executive_summary and keep the \
  competitors[] row minimal (1–2 bullets max). \
  If a keyword has zero facts, omit its row (and note the gap in \
  executive_summary).

### outlook (optional, ≤ 600 chars or null)
- **Purpose:** Forward-looking statements from sources.
- **Content:** Only what sources themselves say about future plans. No model \
  speculation.

### Citations (all insight sections)
Every `Insight` and `KeyMetric` MUST cite ≥ 1 `source_id` from input facts. \
Never invent UUIDs.

No repetition (mandatory)
-------------------------
Each factual claim → **at most one** `Insight.statement` in the entire report. \
Later sections must add **new** facts, not paraphrase earlier bullets.
"""


def build_synth_user_note(*, topics: list[str]) -> str:
    """Run-specific synthesis instructions (topic runs vs URL-only runs)."""
    if topics:
        return (
            "Follow the section definitions in your system prompt. "
            "User keywords above are the ONLY allowed competitors[] row names — "
            "never Anthropic, KPMG, OpenAI, Deloitte, etc. "
            "Headline and most key_findings must be about user keywords. "
            "User keywords MUST each appear in executive_summary and in "
            "competitors[] when facts exist for that entity. "
            "Fill key_metrics (2–6 stat cards) when facts contain quantified values. "
            "Fill key_findings first (unique headlines), then market_trends and "
            "consumer_behavior from cross-cutting facts, then competitors[] with "
            "remaining company facts, then non-duplicative themes[]. Use every "
            "distinct high-confidence fact at least once. "
            "Never surface copyright/trademark/contact boilerplate as insights. "
            "competitive_strategic_synthesis.dynamics requires two+ company names per bullet."
        )
    return (
        "URL-ONLY RUN — facts come from user-supplied URLs; TOPICS above are empty. "
        "Ignore system-prompt rules that require user keywords in headline, "
        "key_findings, or competitors[]. Instead:\n"
        "- Spread facts across ALL supported sections — do not pack everything into "
        "key_findings and themes alone.\n"
        "- market_trends: REQUIRED when facts describe sector-wide adoption, macro "
        "patterns, geographic/demographic diffusion, or industry shifts (e.g. national "
        "AI usage rates, metro vs rural gaps). Use facts with a market-wide angle "
        "not already used in key_findings (1–6 insight bullets).\n"
        "- consumer_behavior: REQUIRED when facts describe user/workforce adoption, "
        "usage by segment, demographic drivers, or demand-side signals (1–6 bullets).\n"
        "- competitors[]: REQUIRED when facts name companies as subjects — one row "
        "per primary company (e.g. Microsoft, Apple, EY). Use the company name as "
        "the `competitor` string. Put company-specific facts not already in "
        "key_findings, market_trends, or consumer_behavior here (2–5 bullets each "
        "when facts allow).\n"
        "- competitive_strategic_synthesis: REQUIRED when two or more companies "
        "appear as subjects — compare their moves in dynamics[] (each bullet names "
        "two+ companies).\n"
        "- opportunities / risks / outlook: fill when sources describe market "
        "openings, threats, or stated future plans (including product roadmaps).\n"
        "- executive_summary: summarize what the URLs covered — do NOT say that "
        "no keywords were provided.\n"
        "- Fill key_metrics when facts contain quantified values. Use every distinct "
        "high-confidence fact at least once. Never surface copyright/trademark/"
        "contact boilerplate as insights."
    )


def build_research_user_prompt(topics: list[str]) -> str:
    """User message for the research agent: keywords + dynamic coverage plan."""
    topic_block = wrap_topics(topics)
    n = len(topics)
    balance_note = (
        "Plan dimensions that support comparing all keywords. You MUST collect "
        "sources for each keyword — allocate at least one search per keyword "
        "before finishing."
        if n >= 2
        else "Plan dimensions tailored to this keyword's entity type and what "
        "the report sections need."
    )
    return (
        recency_context_block().rstrip()
        + "\n\nUSER KEYWORDS (every search query must include at least one):\n"
        + topic_block
        + "\n\n"
        + balance_note
        + "\n\nBefore searching: infer 4–6 analysis dimensions appropriate for "
        "these keywords and the downstream report (see system prompt). Then use "
        "`search` to cover those dimensions with recent sources. In each "
        "`rationale`, name the dimension and target report section. Stop when "
        "planned coverage is sufficient or you hit the iteration cap."
    )
