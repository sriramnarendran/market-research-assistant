"""Delete observability rows older than RETENTION_DAYS."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete

from app.db.models import AppEvent, RunEvent, Source, UsageEvent
from app.db.session import get_session_factory

RETENTION_DAYS = 30


async def run_retention() -> None:
    cutoff = datetime.now(UTC) - timedelta(days=RETENTION_DAYS)
    session_factory = get_session_factory()
    async with session_factory() as session:
        for model, label in (
            (AppEvent, "app_events"),
            (UsageEvent, "usage_events"),
        ):
            result = await session.execute(
                delete(model).where(model.created_at < cutoff)  # type: ignore[attr-defined]
            )
            print(f"[retention] deleted {result.rowcount} rows from {label}")

        result = await session.execute(delete(RunEvent).where(RunEvent.at < cutoff))
        print(f"[retention] deleted {result.rowcount} rows from run_events")

        result = await session.execute(delete(Source).where(Source.fetched_at < cutoff))
        print(f"[retention] deleted {result.rowcount} rows from sources")

        await session.commit()


if __name__ == "__main__":
    asyncio.run(run_retention())
