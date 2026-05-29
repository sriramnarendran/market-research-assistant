"""Run routes — create, poll, list."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas import (
    RunCreateRequest,
    RunCreateResponse,
    RunDetail,
    RunSummary,
    SourceSummary,
    UrlFetchFailure,
)
from app.core.deps import CurrentUser, get_current_user, not_found
from app.core.rate_limit import limiter
from app.db.models import Run, RunEvent, Source, User
from app.db.session import get_session
from app.services.pdf_export import render_report_pdf
from app.services.pdf_errors import PdfExportUnavailableError
from app.workers.pipeline_worker import enqueue_run

router = APIRouter(prefix="/runs", tags=["runs"])

_FETCH_FAIL_PREFIX = "fetch failed for "


async def _url_fetch_failures(session: AsyncSession, run_id: UUID) -> list[UrlFetchFailure]:
    rows = (
        await session.execute(
            select(RunEvent.detail).where(
                RunEvent.run_id == run_id,
                RunEvent.detail.like(f"{_FETCH_FAIL_PREFIX}%"),
            )
        )
    ).scalars().all()
    out: list[UrlFetchFailure] = []
    for detail in rows:
        if not detail:
            continue
        rest = detail[len(_FETCH_FAIL_PREFIX) :]
        url, sep, err = rest.partition(": ")
        if sep and url:
            out.append(UrlFetchFailure(url=url, error=err))
    return out


@router.post(
    "",
    response_model=RunCreateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new run",
    description=(
        "Validates input shape (SSRF checks happen during fetch), creates a "
        "`queued` run, schedules the pipeline as a background task, and "
        "returns immediately with the run id."
    ),
)
@limiter.limit("5/hour")
@limiter.limit("20/day")
async def create_run(
    request: Request,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> RunCreateResponse:
    payload = RunCreateRequest.model_validate(await request.json())
    background_tasks = BackgroundTasks()
    if not payload.topics and not payload.urls:
        raise HTTPException(status_code=400, detail="provide at least one topic or url")

    if payload.prior_run_id is not None:
        prior = (
            await session.execute(
                select(Run).where(
                    Run.id == payload.prior_run_id,
                    Run.user_id == user.id,
                )
            )
        ).scalar_one_or_none()
        if prior is None:
            raise HTTPException(status_code=400, detail="prior_run_id not found")

    run = Run(
        user_id=user.id,
        prior_run_id=payload.prior_run_id,
        status="queued",
        topics=list(payload.topics),
        urls=list(payload.urls),
    )
    session.add(run)
    await session.flush()
    run_id = run.id
    # Commit so the worker (which opens its own session) can see the row.
    await session.commit()

    enqueue_run(background_tasks, run_id)
    body = RunCreateResponse(id=run_id, status="queued")
    return JSONResponse(
        status_code=status.HTTP_201_CREATED,
        content=body.model_dump(mode="json"),
        background=background_tasks,
    )


@router.get(
    "",
    response_model=list[RunSummary],
    summary="List runs for the current user",
)
async def list_runs(
    user: CurrentUser,
    session: AsyncSession = Depends(get_session),
    limit: int = 50,
) -> list[RunSummary]:
    stmt = (
        select(Run)
        .where(Run.user_id == user.id)
        .order_by(Run.created_at.desc())
        .limit(min(limit, 200))
    )
    rows = (await session.execute(stmt)).scalars().all()
    return [
        RunSummary(
            id=r.id,
            status=r.status,
            topics=list(r.topics or []),
            urls=list(r.urls or []),
            created_at=r.created_at,
            completed_at=r.completed_at,
            failure_reason=r.failure_reason,
            has_report=r.report is not None,
        )
        for r in rows
    ]


@router.get(
    "/{run_id}",
    response_model=RunDetail,
    summary="Get run detail (poll target)",
)
async def get_run(
    run_id: UUID,
    user: CurrentUser,
    session: AsyncSession = Depends(get_session),
) -> RunDetail:
    stmt = select(Run).where(Run.id == run_id, Run.user_id == user.id)
    run = (await session.execute(stmt)).scalar_one_or_none()
    if run is None:
        raise not_found(f"run {run_id} not found")
    return RunDetail(
        id=run.id,
        status=run.status,
        topics=list(run.topics or []),
        urls=list(run.urls or []),
        created_at=run.created_at,
        completed_at=run.completed_at,
        failure_reason=run.failure_reason,
        url_fetch_failures=await _url_fetch_failures(session, run.id),
        report=run.report,
    )


@router.get(
    "/{run_id}/sources",
    response_model=list[SourceSummary],
    summary="List sources collected so far for a run",
)
async def list_run_sources(
    run_id: UUID,
    user: CurrentUser,
    session: AsyncSession = Depends(get_session),
) -> list[SourceSummary]:
    run = (
        await session.execute(
            select(Run).where(Run.id == run_id, Run.user_id == user.id)
        )
    ).scalar_one_or_none()
    if run is None:
        raise not_found(f"run {run_id} not found")

    rows = (
        await session.execute(
            select(Source)
            .where(Source.run_id == run_id)
            .order_by(Source.fetched_at.asc(), Source.id.asc())
        )
    ).scalars().all()
    return [
        SourceSummary(
            id=s.id,
            url=s.url,
            origin=s.origin,
            title=s.title,
            topic_match=s.topic_match,
            bytes=s.bytes,
            fetched_at=s.fetched_at,
        )
        for s in rows
    ]


@router.get(
    "/{run_id}/export.pdf",
    summary="Export run report as PDF",
    responses={
        200: {"content": {"application/pdf": {}}},
        409: {"description": "Report not ready"},
    },
)
async def export_run_pdf(
    run_id: UUID,
    user: CurrentUser,
    session: AsyncSession = Depends(get_session),
) -> Response:
    stmt = select(Run).where(Run.id == run_id, Run.user_id == user.id)
    run = (await session.execute(stmt)).scalar_one_or_none()
    if run is None:
        raise not_found(f"run {run_id} not found")
    if run.report is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="report not available yet",
        )

    try:
        pdf_bytes = render_report_pdf(
            run.report,
            run_id=run.id,
            topics=list(run.topics or []),
        )
    except PdfExportUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    filename = f"report-{run_id}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
