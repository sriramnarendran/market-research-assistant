"""Admin metrics routes — require admin role."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy import func, not_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas import (
    AdminOverview,
    AppErrorRow,
    RunMetrics,
    UsageDayRow,
    UserUsageSummary,
)
from app.core.deps import AdminUser, not_found
from app.db.models import TERMINAL_STATUSES, AppEvent, Run, Source, UsageEvent, User
from app.db.session import get_session

router = APIRouter(prefix="/admin", tags=["admin"])

_SUCCESS_STATUSES = ("done", "done_with_warnings")
# Ephemeral accounts created by integration tests (see tests/conftest.py).
_TEST_SIGNUP_PREFIXES = ("test-", "bad-", "dup-", "rl-", "other-")


def _admin_user_filters():
    """Exclude pytest junk signups and users who never logged in or ran."""
    exclude_test = not_(
        or_(
            *[
                User.email.like(f"{prefix}%@example.com")
                for prefix in _TEST_SIGNUP_PREFIXES
            ]
        )
    )
    has_run = (
        select(Run.id).where(Run.user_id == User.id).correlate(User).exists()
    )
    engaged = or_(User.last_login_at.isnot(None), has_run)
    return exclude_test, engaged


@router.get("/metrics/overview", response_model=AdminOverview)
async def metrics_overview(
    _admin: AdminUser,
    session: AsyncSession = Depends(get_session),
) -> AdminOverview:
    exclude_test, engaged = _admin_user_filters()

    total_users = (
        await session.execute(
            select(func.count()).select_from(User).where(exclude_test, engaged)
        )
    ).scalar_one()

    week_ago = datetime.now(UTC) - timedelta(days=7)
    active_users = (
        await session.execute(
            select(func.count(func.distinct(User.id)))
            .select_from(User)
            .outerjoin(Run, Run.user_id == User.id)
            .where(
                exclude_test,
                engaged,
                or_(
                    User.last_login_at >= week_ago,
                    Run.created_at >= week_ago,
                ),
            )
        )
    ).scalar_one()

    today_start = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    runs_today = (
        await session.execute(
            select(func.count()).select_from(Run).where(Run.created_at >= today_start)
        )
    ).scalar_one()

    total_runs = (
        await session.execute(select(func.count()).select_from(Run))
    ).scalar_one()

    terminal = tuple(TERMINAL_STATUSES)
    completed_runs = (
        await session.execute(
            select(func.count()).select_from(Run).where(Run.status.in_(_SUCCESS_STATUSES))
        )
    ).scalar_one()

    in_progress_runs = (
        await session.execute(
            select(func.count()).select_from(Run).where(~Run.status.in_(terminal))
        )
    ).scalar_one()

    failed_runs = (
        await session.execute(
            select(func.count()).select_from(Run).where(Run.status.like("failed_%"))
        )
    ).scalar_one()

    reports_generated = (
        await session.execute(
            select(func.count()).select_from(Run).where(Run.report.isnot(None))
        )
    ).scalar_one()

    total_sources = (
        await session.execute(select(func.count()).select_from(Source))
    ).scalar_one()

    url_sources = (
        await session.execute(
            select(func.count()).select_from(Source).where(Source.origin == "url_path")
        )
    ).scalar_one()

    search_sources = (
        await session.execute(
            select(func.count()).select_from(Source).where(Source.origin == "tavily")
        )
    ).scalar_one()

    sources_today = (
        await session.execute(
            select(func.count()).select_from(Source).where(Source.fetched_at >= today_start)
        )
    ).scalar_one()

    return AdminOverview(
        total_users=int(total_users),
        active_users_7d=int(active_users),
        total_runs=int(total_runs),
        runs_today=int(runs_today),
        completed_runs=int(completed_runs),
        in_progress_runs=int(in_progress_runs),
        failed_runs=int(failed_runs),
        reports_generated=int(reports_generated),
        total_sources=int(total_sources),
        url_sources=int(url_sources),
        search_sources=int(search_sources),
        sources_today=int(sources_today),
    )


@router.get("/metrics/usage", response_model=list[UsageDayRow])
async def metrics_usage(
    _admin: AdminUser,
    session: AsyncSession = Depends(get_session),
) -> list[UsageDayRow]:
    cutoff = datetime.now(UTC) - timedelta(days=90)
    day_col = func.date_trunc("day", UsageEvent.created_at).label("day")
    rows = (
        await session.execute(
            select(
                day_col,
                UsageEvent.provider,
                UsageEvent.phase,
                func.sum(UsageEvent.input_tokens).label("input_tokens"),
                func.sum(UsageEvent.output_tokens).label("output_tokens"),
                func.sum(UsageEvent.cost_usd).label("cost_usd"),
            )
            .where(UsageEvent.created_at >= cutoff)
            .group_by(day_col, UsageEvent.provider, UsageEvent.phase)
            .order_by(day_col.desc())
        )
    ).all()

    return [
        UsageDayRow(
            day=row.day.date().isoformat() if row.day else "",
            provider=row.provider,
            phase=row.phase,
            input_tokens=int(row.input_tokens or 0),
            output_tokens=int(row.output_tokens or 0),
            cost_usd=float(row.cost_usd or 0),
        )
        for row in rows
    ]


@router.get("/metrics/runs", response_model=RunMetrics)
async def metrics_runs(
    _admin: AdminUser,
    session: AsyncSession = Depends(get_session),
) -> RunMetrics:
    total = (await session.execute(select(func.count()).select_from(Run))).scalar_one()

    terminal = tuple(TERMINAL_STATUSES)
    terminal_count = (
        await session.execute(
            select(func.count()).select_from(Run).where(Run.status.in_(terminal))
        )
    ).scalar_one()

    success = (
        await session.execute(
            select(func.count())
            .select_from(Run)
            .where(Run.status.in_(_SUCCESS_STATUSES))
        )
    ).scalar_one()

    failure_rows = (
        await session.execute(
            select(Run.status, func.count())
            .where(Run.status.like("failed_%"))
            .group_by(Run.status)
        )
    ).all()
    failure_breakdown = {status: int(cnt) for status, cnt in failure_rows}

    duration_expr = func.extract(
        "epoch", Run.completed_at - Run.created_at
    )
    p50 = (
        await session.execute(
            select(func.percentile_cont(0.5).within_group(duration_expr)).where(
                Run.completed_at.isnot(None),
                Run.status.in_(terminal),
            )
        )
    ).scalar_one()
    p95 = (
        await session.execute(
            select(func.percentile_cont(0.95).within_group(duration_expr)).where(
                Run.completed_at.isnot(None),
                Run.status.in_(terminal),
            )
        )
    ).scalar_one()

    rate = float(success) / float(terminal_count) if terminal_count else 0.0
    return RunMetrics(
        total_runs=int(total),
        success_rate=rate,
        p50_duration_sec=float(p50) if p50 is not None else None,
        p95_duration_sec=float(p95) if p95 is not None else None,
        failure_breakdown=failure_breakdown,
    )


@router.get("/users/{user_id}/usage", response_model=UserUsageSummary)
async def user_usage(
    user_id: UUID,
    _admin: AdminUser,
    session: AsyncSession = Depends(get_session),
) -> UserUsageSummary:
    user = (
        await session.execute(select(User).where(User.id == user_id))
    ).scalar_one_or_none()
    if user is None:
        from app.core.deps import not_found

        raise not_found(f"user {user_id} not found")

    run_count = (
        await session.execute(
            select(func.count()).select_from(Run).where(Run.user_id == user_id)
        )
    ).scalar_one()

    usage = (
        await session.execute(
            select(
                func.coalesce(func.sum(UsageEvent.input_tokens), 0),
                func.coalesce(func.sum(UsageEvent.output_tokens), 0),
                func.coalesce(func.sum(UsageEvent.cost_usd), 0),
            )
            .select_from(UsageEvent)
            .join(Run, Run.id == UsageEvent.run_id)
            .where(Run.user_id == user_id)
        )
    ).one()

    return UserUsageSummary(
        user_id=user.id,
        email=user.email,
        total_runs=int(run_count),
        input_tokens=int(usage[0]),
        output_tokens=int(usage[1]),
        cost_usd=float(usage[2]),
    )


@router.get("/errors", response_model=list[AppErrorRow])
async def recent_errors(
    _admin: AdminUser,
    session: AsyncSession = Depends(get_session),
    limit: int = 50,
) -> list[AppErrorRow]:
    rows = (
        await session.execute(
            select(AppEvent)
            .where(AppEvent.kind == "exception")
            .order_by(AppEvent.created_at.desc())
            .limit(min(limit, 200))
        )
    ).scalars().all()
    return [
        AppErrorRow(id=e.id, created_at=e.created_at, payload=e.payload) for e in rows
    ]
