"""Change detection via normalized claim hashing."""

from __future__ import annotations

import hashlib
import re
from collections.abc import Callable
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.schemas import CompetitiveStrategicSynthesis, CompetitorActivity, Insight, Report, Theme
from app.db.models import RunFact

_NORMALIZE_RE = re.compile(r"[^a-z0-9 ]+")
_STOPWORDS = frozenset(
    "a an and the of to in on at for is are was were be been being have has had do does did but or so as if".split()
)


def claim_hash(claim: str) -> str:
    """Normalised SHA256 of a claim statement."""
    normalized = _NORMALIZE_RE.sub(" ", claim.lower())
    tokens = [t for t in normalized.split() if t and t not in _STOPWORDS]
    return hashlib.sha256(" ".join(tokens).encode("utf-8")).hexdigest()


async def load_prior_hashes(session: AsyncSession, prior_run_id: UUID) -> dict[str, str]:
    """Map claim_hash -> claim text from the prior run's persisted facts."""
    rows = (
        await session.execute(
            select(RunFact.claim_hash, RunFact.claim).where(
                RunFact.run_id == prior_run_id,
                RunFact.diff_tag != "removed",
            )
        )
    ).all()
    return {h: c for h, c in rows}


def _iter_insights(report: Report) -> list[Insight]:
    out: list[Insight] = []
    for theme in report.themes:
        out.extend(theme.insights)
    for ca in report.competitors:
        out.extend(ca.insights)
    out.extend(report.key_findings)
    out.extend(report.opportunities)
    out.extend(report.risks)
    if report.competitive_strategic_synthesis is not None:
        syn = report.competitive_strategic_synthesis
        out.extend(syn.dynamics)
        out.extend(syn.implications)
    return out


def _current_hashes(report: Report) -> set[str]:
    return {claim_hash(ins.statement) for ins in _iter_insights(report)}


def _tag_insight(ins: Insight, prior_hashes: set[str]) -> Insight:
    h = claim_hash(ins.statement)
    tag = "unchanged" if h in prior_hashes else "new"
    return ins.model_copy(update={"diff_tag": tag})


def _tag_insights(insights: list[Insight], prior_hashes: set[str]) -> list[Insight]:
    return [_tag_insight(ins, prior_hashes) for ins in insights]


def _tag_theme(theme: Theme, prior_hashes: set[str]) -> Theme:
    return theme.model_copy(
        update={"insights": _tag_insights(theme.insights, prior_hashes)}
    )


def _tag_competitor(ca: CompetitorActivity, prior_hashes: set[str]) -> CompetitorActivity:
    return ca.model_copy(
        update={"insights": _tag_insights(ca.insights, prior_hashes)}
    )


def apply_change_detection(
    report: Report,
    prior_hash_to_claim: dict[str, str],
) -> Report:
    """Tag insights new/unchanged and add removed ghost insights."""
    prior_hashes = set(prior_hash_to_claim.keys())
    current_hashes = _current_hashes(report)
    removed_hashes = prior_hashes - current_hashes
    removed_insights = [
        Insight(
            statement=prior_hash_to_claim[h],
            citations=[],
            diff_tag="removed",
        )
        for h in sorted(removed_hashes)
    ]

    synthesis_update: CompetitiveStrategicSynthesis | None = None
    if report.competitive_strategic_synthesis is not None:
        syn = report.competitive_strategic_synthesis
        synthesis_update = syn.model_copy(
            update={
                "dynamics": _tag_insights(syn.dynamics, prior_hashes),
                "implications": _tag_insights(syn.implications, prior_hashes),
            }
        )

    return report.model_copy(
        update={
            "themes": [_tag_theme(t, prior_hashes) for t in report.themes],
            "competitors": [_tag_competitor(c, prior_hashes) for c in report.competitors],
            "key_findings": _tag_insights(report.key_findings, prior_hashes),
            "opportunities": _tag_insights(report.opportunities, prior_hashes),
            "risks": _tag_insights(report.risks, prior_hashes),
            "competitive_strategic_synthesis": synthesis_update,
            "removed_insights": removed_insights,
        }
    )
