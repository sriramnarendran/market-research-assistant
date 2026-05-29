"""Source routes — view raw fetched text for a source.

Useful for debugging citation issues and previewing source content in the
report viewer's drawer.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from fastapi import APIRouter

from app.api.schemas import SourceDetail
from app.core.deps import CurrentUser, DBSession, not_found
from app.db.models import Run, Source

router = APIRouter(prefix="/sources", tags=["sources"])


@router.get(
    "/{source_id}",
    response_model=SourceDetail,
    summary="Get a source's raw fetched text",
)
async def get_source(
    source_id: UUID,
    session: DBSession,
    user: CurrentUser,
) -> SourceDetail:
    stmt = (
        select(Source)
        .join(Run, Run.id == Source.run_id)
        .where(Source.id == source_id, Run.user_id == user.id)
    )
    src = (await session.execute(stmt)).scalar_one_or_none()
    if src is None:
        raise not_found(f"source {source_id} not found")
    return SourceDetail(
        id=src.id,
        run_id=src.run_id,
        url=src.url,
        origin=src.origin,
        title=src.title,
        topic_match=src.topic_match,
        fetched_text=src.fetched_text,
        bytes=src.bytes,
        fetched_at=src.fetched_at,
    )
