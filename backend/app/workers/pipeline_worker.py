"""Background worker entry point.

Phase 1 uses FastAPI `BackgroundTasks` which runs in the same process as the
API. Future iterations swap this for an `arq` / `rq` worker on Redis without
changing the API surface — `enqueue_run` is the only function callers touch.
"""

from __future__ import annotations

import logging
from uuid import UUID

from fastapi import BackgroundTasks

from app.ai.pipeline import run_pipeline

log = logging.getLogger(__name__)


def enqueue_run(background_tasks: BackgroundTasks, run_id: UUID) -> None:
    """Schedule the pipeline to execute on the FastAPI background runner."""
    log.info("enqueuing pipeline for run %s", run_id)
    background_tasks.add_task(run_pipeline, run_id)
