"""Canonical AI-layer data shapes.

These Pydantic models are used as Pydantic AI `output_type`s, as the
serialised report shape stored on `runs.report`, and as the typed contract
between pipeline phases.

Naming convention: domain types live here; HTTP request/response models
live in `app/api/schemas.py` and reference these types.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

# -----------------------------------------------------------------------------
# Enumerations as Literal types (Pydantic AI generates JSON schemas from these)
# -----------------------------------------------------------------------------

Confidence = Literal["high", "medium", "low"]
JudgeVerdictLiteral = Literal["verified", "unsupported", "contradicted"]
DiffTag = Literal["new", "unchanged", "removed"]
ResearchStopReason = Literal[
    "model_complete",
    "iteration_cap",
    "budget_exceeded",
    "consecutive_empty",
    "tool_error",
]

# -----------------------------------------------------------------------------
# Extraction output
# -----------------------------------------------------------------------------


class Fact(BaseModel):
    """A single claim extracted from one source.

    `source_id` is stamped by an output_validator (the LLM never sees the real
    UUID) — see `app/ai/agents/extract.py`.
    """

    model_config = ConfigDict(extra="forbid")

    claim: str = Field(
        ...,
        min_length=4,
        max_length=600,
        description="A concise factual claim, paraphrased from the source.",
    )
    evidence: str = Field(
        ...,
        min_length=4,
        max_length=1200,
        description="A direct quote or near-quote from the source backing the claim.",
    )
    confidence: Confidence = Field(
        ...,
        description="How directly the source supports the claim.",
    )
    source_id: UUID | None = Field(
        default=None,
        description="Stamped by the extraction output_validator; must not be set by the LLM.",
    )


# -----------------------------------------------------------------------------
# Research agent output (topic path)
# -----------------------------------------------------------------------------


class SearchResult(BaseModel):
    """One result returned by the `search` tool to the research agent."""

    model_config = ConfigDict(extra="forbid")

    url: str
    title: str
    snippet: str
    score: float = Field(..., ge=0.0, le=1.0)


class CollectedSource(BaseModel):
    """A search result that passed the relevance filter and was persisted as a source."""

    model_config = ConfigDict(extra="forbid")

    source_id: UUID
    url: str
    title: str
    snippet: str
    score: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Tavily relevance score when collected via search.",
    )
    topic_match: str = Field(
        ..., description="Which user-supplied topic this result is relevant to."
    )


class ResearchOutput(BaseModel):
    """The research agent's final structured output (set when the model is done)."""

    model_config = ConfigDict(extra="forbid")

    summary: str = Field(
        ...,
        max_length=1500,
        description="One- or two-sentence summary of what was learned across topics.",
    )
    topics_covered: list[str] = Field(default_factory=list)
    iterations_used: int = Field(..., ge=0, le=8)
    stop_reason: ResearchStopReason


# -----------------------------------------------------------------------------
# Judge output
# -----------------------------------------------------------------------------


class JudgeVerdict(BaseModel):
    """The judge model's verdict on a single insight."""

    model_config = ConfigDict(extra="forbid")

    verdict: JudgeVerdictLiteral
    rationale: str = Field(..., min_length=4, max_length=400)

    @field_validator("verdict", mode="before")
    @classmethod
    def _normalize_verdict(cls, v: object) -> object:
        if isinstance(v, str):
            return v.strip().lower()
        return v

    @field_validator("rationale", mode="before")
    @classmethod
    def _normalize_rationale(cls, v: object) -> str:
        """Coerce model output so minor length/format issues don't fail the run.

        Long rationales (common when the model pastes a quote) are truncated.
        Empty or ultra-short rationales get a safe fallback.
        """
        text = v.strip() if isinstance(v, str) else (str(v).strip() if v is not None else "")
        if len(text) < 4:
            return "No supporting excerpt found."
        if len(text) > 400:
            return text[:397] + "…"
        return text


# -----------------------------------------------------------------------------
# Synthesis output
# -----------------------------------------------------------------------------


class Insight(BaseModel):
    """A single insight inside a theme, competitor grouping, or brief section."""

    model_config = ConfigDict(extra="forbid")

    statement: str = Field(..., min_length=8, max_length=800)
    citations: list[UUID] = Field(
        default_factory=list,
        description="source_ids that support this insight. Empty for removed diff ghosts.",
    )
    judge_verdict: JudgeVerdictLiteral | None = Field(default=None)
    judge_rationale: str | None = Field(default=None)
    diff_tag: DiffTag | None = Field(default=None)


class KeyMetric(BaseModel):
    """A pulled-out quantitative fact suitable for a stat-card display.

    Examples (label / value / context):
      - "Founding partners" / "14" / "Members of the Project Glasswing coalition"
      - "High-severity vulnerabilities found" / "thousands" / "Across major OS and browsers"
      - "Oldest bug uncovered" / "27 years" / "OpenBSD crash bug undetected by automated tests"

    `value` is a string so the model can use ranges ("12-15"), qualifiers
    ("thousands", "$4.2B+"), or units ("27 years") without us having to model
    every numeric type. Always cite the source(s) the figure came from.
    """

    model_config = ConfigDict(extra="forbid")

    label: str = Field(..., min_length=2, max_length=80)
    value: str = Field(..., min_length=1, max_length=40)
    context: str = Field(..., min_length=4, max_length=240)
    citations: list[UUID] = Field(..., min_length=1)


class Theme(BaseModel):
    """A thematic grouping of insights across sources."""

    model_config = ConfigDict(extra="forbid")

    title: str = Field(..., min_length=2, max_length=160)
    summary: str = Field(..., max_length=600)
    insights: list[Insight] = Field(..., min_length=1)


class CompetitorActivity(BaseModel):
    """Recent activity attributable to a specific competitor."""

    model_config = ConfigDict(extra="forbid")

    competitor: str = Field(..., min_length=1, max_length=120)
    insights: list[Insight] = Field(..., min_length=1)


class InsightSection(BaseModel):
    """Narrative section with cited insight bullets (e.g. market trends)."""

    model_config = ConfigDict(extra="forbid")

    summary: str = Field(
        ...,
        min_length=20,
        max_length=900,
        description="2–4 sentence overview grounded in cited facts below.",
    )
    insights: list[Insight] = Field(
        ...,
        min_length=1,
        max_length=6,
        description="Distinct cited facts for this section.",
    )


class CompetitiveStrategicSynthesis(BaseModel):
    """Cross-competitor synthesis — how players relate, not just what each did."""

    model_config = ConfigDict(extra="forbid")

    summary: str = Field(
        ...,
        min_length=20,
        max_length=1800,
        description=(
            "4–8 sentence narrative comparing competitive moves and positioning "
            "using only input facts."
        ),
    )
    dynamics: list[Insight] = Field(
        ...,
        min_length=1,
        max_length=6,
        description="Cited insights on competitive interactions and contrasts.",
    )
    implications: list[Insight] = Field(
        default_factory=list,
        max_length=5,
        description=(
            "Cited factual strategic signals from sources — not reader advice."
        ),
    )


class Report(BaseModel):
    """Top-level synthesised report — a structured market-intelligence brief.

    Stored as JSONB on `runs.report`. Older reports may be missing the brief
    fields (`headline`, `executive_summary`, etc.); they all default so old
    rows still deserialize.
    """

    model_config = ConfigDict(extra="forbid")

    # Brief — the top of the report, designed to be the first thing an analyst reads.
    headline: str = Field(
        default="",
        max_length=240,
        description="Single-sentence top-line takeaway across all sources.",
    )
    executive_summary: str = Field(
        default="",
        max_length=1500,
        description="3-6 sentence narrative the user reads first.",
    )
    key_metrics: list[KeyMetric] = Field(
        default_factory=list,
        description="0-6 pulled-out quantitative facts.",
    )
    key_findings: list[Insight] = Field(
        default_factory=list,
        description="4-6 most important insights, cross-cutting the themes.",
    )
    market_trends: InsightSection | None = Field(
        default=None,
        description="Industry and macro market shifts supported by facts.",
    )
    consumer_behavior: InsightSection | None = Field(
        default=None,
        description="Demand, adoption, and buyer-behavior signals from facts.",
    )
    opportunities: list[Insight] = Field(
        default_factory=list,
        description="Strategic openings / what this enables.",
    )
    risks: list[Insight] = Field(
        default_factory=list,
        description="Threats, blockers, missing capabilities, contradictions in evidence.",
    )
    competitive_strategic_synthesis: CompetitiveStrategicSynthesis | None = Field(
        default=None,
        description=(
            "Cross-competitor strategic synthesis when facts support comparison."
        ),
    )

    # Detail — full thematic and per-competitor breakdown.
    themes: list[Theme] = Field(default_factory=list)
    competitors: list[CompetitorActivity] = Field(default_factory=list)

    # Forward look.
    outlook: str | None = Field(
        default=None,
        max_length=600,
        description="Optional 1-2 sentence forward-looking statement / what to watch.",
    )

    # Change detection — claims present in prior run but absent from this one.
    removed_insights: list[Insight] = Field(
        default_factory=list,
        description="Ghost insights from the prior run (diff_tag=removed).",
    )

    # Metadata stamped by the synth output_validator.
    topics: list[str] = Field(default_factory=list)
    source_count: int = Field(..., ge=0)
    generated_at: datetime
