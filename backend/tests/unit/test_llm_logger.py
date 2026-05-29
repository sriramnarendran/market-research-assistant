"""LLM transcript logger tests.

Drives a real `agent.run()` against TestModel and verifies a complete
JSONL line lands in the configured log file with the full message graph.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import BaseModel
from pydantic_ai import Agent
from pydantic_ai.models.test import TestModel

from app.core.llm_logger import log_llm_call, setup_llm_logger


class _Out(BaseModel):
    answer: str


def _reinstall_logger() -> None:
    # The logger module caches its install state; reset for test isolation.
    from app.core import llm_logger as mod

    logger = logging.getLogger("app.llm_requests")
    for h in list(logger.handlers):
        logger.removeHandler(h)
        try:
            h.close()
        except Exception:
            pass
    mod._installed = False
    setup_llm_logger()


@pytest.mark.unit
async def test_log_llm_call_appends_jsonl_entry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    log_file = tmp_path / "llm.jsonl"
    monkeypatch.setenv("LLM_LOG_FILE", str(log_file))

    from app.core.config import get_settings

    get_settings.cache_clear()
    _reinstall_logger()

    agent: Agent[None, _Out] = Agent(
        model=TestModel(),
        output_type=_Out,
        system_prompt="You are a smoke-test agent.",
    )
    result = await agent.run("Hello world")
    log_llm_call(run_id=uuid4(), phase="extract", result=result, duration_ms=42)

    # Force handlers to flush.
    for h in logging.getLogger("app.llm_requests").handlers:
        h.flush()

    assert log_file.exists()
    lines = log_file.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    entry = json.loads(lines[0])
    assert entry["phase"] == "extract"
    assert entry["provider"] == "test"
    assert entry["model"] == "test"
    assert entry["duration_ms"] == 42
    assert entry["run_id"]
    assert isinstance(entry["messages"], list)
    assert len(entry["messages"]) >= 2

    parts_by_kind: dict[str, list[dict]] = {}
    for msg in entry["messages"]:
        assert "parts" in msg
        assert "kind" in msg
        for p in msg["parts"]:
            parts_by_kind.setdefault(p["part_kind"], []).append(p)

    # The TestModel run emits a system prompt, a user prompt, and a tool call
    # (because output_type forces a `final_result` tool call).
    assert "system-prompt" in parts_by_kind
    assert parts_by_kind["system-prompt"][0]["content"] == "You are a smoke-test agent."
    assert "user-prompt" in parts_by_kind
    assert parts_by_kind["user-prompt"][0]["content"] == "Hello world"
    assert "tool-call" in parts_by_kind
    assert parts_by_kind["tool-call"][0]["tool_name"] == "final_result"


@pytest.mark.unit
async def test_log_llm_call_disabled_when_path_empty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LLM_LOG_FILE", "")
    from app.core.config import get_settings

    get_settings.cache_clear()
    _reinstall_logger()

    agent: Agent[None, _Out] = Agent(
        model=TestModel(),
        output_type=_Out,
        system_prompt="x",
    )
    result = await agent.run("x")
    # Should not raise; just no-op.
    log_llm_call(run_id=None, phase="judge", result=result, duration_ms=1)
