"""Remove near-duplicate insights across report sections after synthesis."""

from __future__ import annotations

import re
from difflib import SequenceMatcher

from app.ai.diff import claim_hash
from app.ai.schemas import CompetitiveStrategicSynthesis, CompetitorActivity, Insight, InsightSection, Report, Theme

_SIMILARITY_THRESHOLD = 0.68
_SUBSTRING_RATIO = 0.55


def _normalize(statement: str) -> str:
    return re.sub(r"\s+", " ", statement.lower().strip())


def _similar(a: str, b: str) -> bool:
    if claim_hash(a) == claim_hash(b):
        return True
    na, nb = _normalize(a), _normalize(b)
    if na == nb:
        return True
    shorter, longer = (na, nb) if len(na) <= len(nb) else (nb, na)
    if shorter in longer and len(shorter) / max(len(longer), 1) >= _SUBSTRING_RATIO:
        return True
    return SequenceMatcher(None, na, nb).ratio() >= _SIMILARITY_THRESHOLD


def _mentions_company(statement: str, name: str) -> bool:
    return name.lower() in _normalize(statement)


def _is_cross_company(statement: str, company_names: list[str]) -> bool:
    hits = sum(1 for name in company_names if _mentions_company(statement, name))
    return hits >= 2


class _DedupeState:
    def __init__(self) -> None:
        self._kept: list[str] = []

    def accept(self, statement: str) -> bool:
        for kept in self._kept:
            if _similar(statement, kept):
                return False
        self._kept.append(statement)
        return True

    def filter(self, insights: list[Insight]) -> list[Insight]:
        return [ins for ins in insights if self.accept(ins.statement)]


def dedupe_report(report: Report) -> Report:
    """Drop repeated insights, keeping the first occurrence in priority order.

    ``key_findings`` keeps the model's top headlines; ``competitors`` and
    ``themes`` add detail without restating them.
    """
    state = _DedupeState()
    company_names = [c.competitor for c in report.competitors]

    key_findings = state.filter(report.key_findings)

    market_trends: InsightSection | None = None
    if report.market_trends is not None:
        kept = state.filter(report.market_trends.insights)
        if kept:
            market_trends = InsightSection(summary=report.market_trends.summary, insights=kept)

    consumer_behavior: InsightSection | None = None
    if report.consumer_behavior is not None:
        kept = state.filter(report.consumer_behavior.insights)
        if kept:
            consumer_behavior = InsightSection(
                summary=report.consumer_behavior.summary, insights=kept
            )

    competitors: list[CompetitorActivity] = []
    for c in report.competitors:
        kept = state.filter(c.insights)
        if kept:
            competitors.append(CompetitorActivity(competitor=c.competitor, insights=kept))

    themes: list[Theme] = []
    for theme in report.themes:
        kept = state.filter(theme.insights)
        if kept:
            themes.append(Theme(title=theme.title, summary=theme.summary, insights=kept))

    opportunities = state.filter(report.opportunities)
    risks = state.filter(report.risks)

    synthesis = report.competitive_strategic_synthesis
    competitive_strategic_synthesis: CompetitiveStrategicSynthesis | None = None
    if synthesis is not None:
        dynamics = [
            ins
            for ins in state.filter(synthesis.dynamics)
            if company_names and _is_cross_company(ins.statement, company_names)
        ]
        implications = state.filter(synthesis.implications)
        if dynamics:
            competitive_strategic_synthesis = CompetitiveStrategicSynthesis(
                summary=synthesis.summary,
                dynamics=dynamics,
                implications=implications,
            )

    return report.model_copy(
        update={
            "competitors": competitors,
            "themes": themes,
            "key_findings": key_findings,
            "market_trends": market_trends,
            "consumer_behavior": consumer_behavior,
            "opportunities": opportunities,
            "risks": risks,
            "competitive_strategic_synthesis": competitive_strategic_synthesis,
        }
    )
