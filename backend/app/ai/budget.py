"""Per-run token budget.

A simple thread-safe counter passed through the pipeline as a Pydantic AI
`deps` field. Every LLM call site:
  1. Calls `budget.guard()` before invoking the agent (raises if exceeded).
  2. Calls `budget.record(input_tokens, output_tokens)` after the call.

Exceeding the budget terminates the current phase. The pipeline orchestrator
catches `TokenBudgetExceeded` and transitions the run to `failed_budget`.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field


class TokenBudgetExceeded(Exception):
    """Raised when the cumulative token budget for a run is exhausted."""


@dataclass(slots=True)
class TokenBudget:
    """Tracks cumulative input + output tokens across one run.

    `judge_reserve` tokens are held back from extract/research/synth so the
    judge phase can usually run. Judge calls use `guard(for_judge=True)` to
    spend against the full limit.
    """

    limit: int
    judge_reserve: int = 0
    used: int = 0
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def _effective_cap(self, *, for_judge: bool) -> int:
        if for_judge:
            return self.limit
        return max(0, self.limit - self.judge_reserve)

    def remaining(self, *, for_judge: bool = False) -> int:
        with self._lock:
            return max(0, self._effective_cap(for_judge=for_judge) - self.used)

    def exceeded(self, *, for_judge: bool = False) -> bool:
        with self._lock:
            return self.used >= self._effective_cap(for_judge=for_judge)

    def guard(self, *, for_judge: bool = False) -> None:
        """Raise if the phase-specific budget cap is exhausted."""
        with self._lock:
            cap = self._effective_cap(for_judge=for_judge)
            if self.used >= cap:
                raise TokenBudgetExceeded(
                    f"run token budget cap {cap} exceeded (used {self.used}, "
                    f"total limit {self.limit})"
                )

    def record(self, input_tokens: int, output_tokens: int) -> None:
        """Add to the running total. Safe to call from concurrent agent runs."""
        delta = max(0, input_tokens) + max(0, output_tokens)
        with self._lock:
            self.used += delta
