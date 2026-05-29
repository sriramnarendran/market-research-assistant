"""Per-LLM-call transcript logger.

Writes one JSON line per `agent.run()` to a dedicated rotating log file. Each
line contains the full Pydantic AI message graph (system prompt, user prompt,
every tool call + tool return, the model's final structured output) plus
metadata (run id, phase, provider, model, duration, token usage).

This is intentionally separate from the application log so an engineer can
`tail -f logs/llm_requests.jsonl` and see exactly what's being sent to / coming
back from each agent invocation, without noise from request logs.

Disable by setting `LLM_LOG_FILE=""` (e.g. in tests). Size-bounded by
`LLM_LOG_MAX_BYTES` with `LLM_LOG_BACKUP_COUNT` rotated copies retained.
"""

from __future__ import annotations

import json
import logging
import logging.handlers
from datetime import UTC, datetime
from pathlib import Path
from threading import Lock
from typing import Any
from uuid import UUID

from app.ai.models import info_for
from app.core.config import get_settings

_LOGGER_NAME = "app.llm_requests"
_INSTALL_LOCK = Lock()
_installed = False
_log = logging.getLogger(__name__)


# -----------------------------------------------------------------------------
# Setup
# -----------------------------------------------------------------------------


def setup_llm_logger() -> None:
    """Install the rotating file handler for the LLM transcript logger.

    Idempotent — safe to call multiple times. Called from the FastAPI lifespan
    and from the worker entry point so background tasks also write.
    """
    global _installed
    with _INSTALL_LOCK:
        if _installed:
            return

        settings = get_settings()
        if not settings.LLM_LOG_FILE:
            _installed = True
            return

        path = _resolve_path(settings.LLM_LOG_FILE)
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            _log.warning("could not create LLM log dir %s: %s", path.parent, e)
            _installed = True
            return

        logger = logging.getLogger(_LOGGER_NAME)
        logger.setLevel(logging.INFO)
        logger.propagate = False  # don't double-log to root

        # Remove any pre-existing handlers to keep the install idempotent.
        for h in list(logger.handlers):
            logger.removeHandler(h)
            try:
                h.close()
            except Exception:
                pass

        handler = logging.handlers.RotatingFileHandler(
            str(path),
            maxBytes=settings.LLM_LOG_MAX_BYTES or 0,
            backupCount=settings.LLM_LOG_BACKUP_COUNT or 0,
            encoding="utf-8",
            delay=True,  # don't open file until first write
        )
        # One JSON object per line — no formatting, no timestamps in the log
        # line itself (we include them inside the JSON payload).
        handler.setFormatter(logging.Formatter("%(message)s"))
        logger.addHandler(handler)
        _installed = True


def _resolve_path(raw: str) -> Path:
    p = Path(raw)
    if not p.is_absolute():
        p = Path.cwd() / p
    return p


# -----------------------------------------------------------------------------
# Logging API
# -----------------------------------------------------------------------------


def log_llm_call(
    *,
    run_id: UUID | None,
    phase: str,
    result: Any,
    duration_ms: int,
) -> None:
    """Append one JSON line describing a completed `agent.run()`.

    Quiet on failure — logging must never break the pipeline.
    """
    settings = get_settings()
    if not settings.LLM_LOG_FILE:
        return

    logger = logging.getLogger(_LOGGER_NAME)
    if not logger.handlers:
        # First call before lifespan / worker setup ran. Install now so we
        # don't lose entries.
        setup_llm_logger()
        if not logger.handlers:
            return

    try:
        entry = _build_entry(run_id=run_id, phase=phase, result=result, duration_ms=duration_ms)
        logger.info(json.dumps(entry, ensure_ascii=False, default=_default_json))
    except Exception:  # noqa: BLE001
        _log.exception("llm transcript log write failed")


# -----------------------------------------------------------------------------
# Serialisation
# -----------------------------------------------------------------------------


def _build_entry(
    *,
    run_id: UUID | None,
    phase: str,
    result: Any,
    duration_ms: int,
) -> dict[str, Any]:
    info = info_for(phase)
    usage = _usage_dict(_get_usage(result))
    messages = _serialise_messages(result)
    return {
        "timestamp": datetime.now(UTC).isoformat(),
        "run_id": str(run_id) if run_id else None,
        "phase": phase,
        "provider": info.provider,
        "model": info.model,
        "duration_ms": duration_ms,
        "usage": usage,
        "messages": messages,
    }


def _get_usage(result: Any) -> Any:
    """Pydantic AI 1.x exposes `usage` as a property; older was a method.

    Prefer the property; only call if the attribute is purely callable (older
    API) — calling the 1.x property emits a DeprecationWarning.
    """
    usage = getattr(result, "usage", None)
    if usage is None:
        return None
    # Heuristic: a `RunUsage` object has int-valued usage fields; a method does
    # not. Use this to avoid calling the deprecated method shim.
    if isinstance(getattr(usage, "input_tokens", None), int):
        return usage
    if callable(usage):
        try:
            return usage()
        except Exception:
            return None
    return usage


def _usage_dict(usage: Any) -> dict[str, int]:
    if usage is None:
        return {}
    fields = (
        "requests",
        "input_tokens",
        "output_tokens",
        "total_tokens",
        "cache_read_tokens",
        "cache_write_tokens",
    )
    out: dict[str, int] = {}
    for f in fields:
        v = getattr(usage, f, None)
        if isinstance(v, int):
            out[f] = v
    return out


def _serialise_messages(result: Any) -> list[dict[str, Any]]:
    """Pull the full message graph from a Pydantic AI result.

    Uses `ModelMessagesTypeAdapter` to round-trip the messages to JSON-ready
    dicts. Each message has `parts: [{part_kind: 'system-prompt'|'user-prompt'|
    'tool-call'|'tool-return'|'text', ...}]` plus `kind: 'request'|'response'`,
    timestamps, run / conversation ids, and per-response usage.
    """
    try:
        from pydantic_ai.messages import ModelMessagesTypeAdapter
    except Exception:
        return []

    getter = getattr(result, "all_messages", None) or getattr(result, "new_messages", None)
    if not callable(getter):
        return []
    try:
        messages = list(getter())
    except Exception:
        return []
    try:
        dumped = ModelMessagesTypeAdapter.dump_python(messages, mode="json")
        return dumped if isinstance(dumped, list) else []
    except Exception:
        return [{"_unparseable": repr(messages)}]


def _default_json(obj: Any) -> Any:
    """Last-resort JSON fallback (UUIDs, datetimes, etc.)."""
    if isinstance(obj, UUID):
        return str(obj)
    if isinstance(obj, datetime):
        return obj.isoformat()
    if hasattr(obj, "model_dump"):
        try:
            return obj.model_dump(mode="json")
        except Exception:
            pass
    return repr(obj)
