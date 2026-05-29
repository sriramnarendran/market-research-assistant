"""Records per-LLM-call telemetry into `usage_events` and the application log.

Pydantic AI exposes token usage via `result.usage()` (a `Usage` object). We
extract `request_tokens` / `response_tokens` and persist a row per call so we
can drive the admin dashboard's cost + token aggregations.

Cost estimation is intentionally approximate — exact pricing changes often
and we surface a hint in the README that this is a "best effort" figure.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.models import ModelInfo, info_for
from app.db.models import UsageEvent

log = logging.getLogger(__name__)


# Approximate USD per 1K tokens, used to populate `usage_events.cost_usd`.
# Edit these as Azure pricing changes; the rest of the code treats them as
# advisory and never gates behaviour on the result.
_COST_PER_1K = {
    # (provider, model_or_deployment) -> (input_cost, output_cost)
    ("azure_openai", "gpt-5-mini"): (Decimal("0.00025"), Decimal("0.002")),
    ("azure_openai", "gpt-5"): (Decimal("0.00125"), Decimal("0.010")),
    ("azure_openai", "gpt-4o-mini"): (Decimal("0.00015"), Decimal("0.0006")),
    ("azure_openai", "gpt-4o"): (Decimal("0.0025"), Decimal("0.010")),
    ("test", "test"): (Decimal("0"), Decimal("0")),
}


@dataclass(slots=True)
class CallRecord:
    """Normalized fields extracted from a Pydantic AI `Usage` object."""

    input_tokens: int
    output_tokens: int
    duration_ms: int


def normalize_usage(usage: Any, duration_ms: int = 0) -> CallRecord:
    """Pull token counts out of Pydantic AI's `Usage` regardless of minor
    API churn (it has had both `request_tokens` and `input_tokens` names).
    """
    input_tokens = (
        getattr(usage, "input_tokens", None)
        or getattr(usage, "request_tokens", None)
        or 0
    )
    output_tokens = (
        getattr(usage, "output_tokens", None)
        or getattr(usage, "response_tokens", None)
        or 0
    )
    return CallRecord(
        input_tokens=int(input_tokens or 0),
        output_tokens=int(output_tokens or 0),
        duration_ms=duration_ms,
    )


def estimate_cost_usd(info: ModelInfo, input_tokens: int, output_tokens: int) -> Decimal:
    rates = _COST_PER_1K.get((info.provider, info.model))
    if rates is None:
        return Decimal("0")
    in_rate, out_rate = rates
    return (
        (Decimal(input_tokens) * in_rate + Decimal(output_tokens) * out_rate) / Decimal(1000)
    ).quantize(Decimal("0.000001"))


async def record_usage(
    session: AsyncSession,
    *,
    run_id: UUID | None,
    phase: str,
    usage: Any,
    duration_ms: int = 0,
) -> CallRecord:
    """Insert a `usage_events` row and emit a structured log line.

    Returns the normalized counts so callers can update an in-memory budget.
    """
    info = info_for(phase)
    counts = normalize_usage(usage, duration_ms=duration_ms)
    cost = estimate_cost_usd(info, counts.input_tokens, counts.output_tokens)

    event = UsageEvent(
        run_id=run_id,
        provider=info.provider,
        model=info.model,
        phase=phase,
        input_tokens=counts.input_tokens,
        output_tokens=counts.output_tokens,
        cost_usd=cost,
        duration_ms=counts.duration_ms,
    )
    session.add(event)
    await session.flush()

    log.info(
        "llm_call",
        extra={
            "run_id": str(run_id) if run_id else None,
            "phase": phase,
            "provider": info.provider,
            "model": info.model,
            "input_tokens": counts.input_tokens,
            "output_tokens": counts.output_tokens,
            "cost_usd": str(cost),
            "duration_ms": counts.duration_ms,
        },
    )
    return counts
