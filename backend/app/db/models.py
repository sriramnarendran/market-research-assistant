"""SQLAlchemy ORM models."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import sqltypes

from app.db.base import Base


# -----------------------------------------------------------------------------
# Run status string set — kept as Python constants so the worker can transition
# without importing enums into the DB. We CHECK-constrain at the table level.
# -----------------------------------------------------------------------------

RUN_STATUSES = (
    "queued",
    "fetching",
    "extracting",
    "researching",
    "synthesizing",
    "judging",
    "done",
    "done_with_warnings",
    "failed_fetch",
    "failed_agent",
    "failed_synth",
    "failed_budget",
    "failed_unknown",
)

TERMINAL_STATUSES = frozenset(
    {
        "done",
        "done_with_warnings",
        "failed_fetch",
        "failed_agent",
        "failed_synth",
        "failed_budget",
        "failed_unknown",
    }
)

JUDGE_VERDICTS = ("verified", "unsupported", "contradicted")
DIFF_TAGS = ("new", "unchanged", "removed")
SOURCE_ORIGINS = ("url_path", "tavily")
USER_ROLES = ("user", "admin")
APP_EVENT_KINDS = ("request", "exception")


# -----------------------------------------------------------------------------
# Models
# -----------------------------------------------------------------------------


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint(
            "role IN ('" + "','".join(USER_ROLES) + "')",
            name="users_role_check",
        ),
    )

    id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), primary_key=True, default=uuid4)
    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    role: Mapped[str] = mapped_column(String(16), default="user", nullable=False)
    last_login_at: Mapped[datetime | None] = mapped_column(
        sqltypes.DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        sqltypes.DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    runs: Mapped[list[Run]] = relationship(back_populates="user", cascade="all, delete-orphan")


class Run(Base):
    __tablename__ = "runs"
    __table_args__ = (
        CheckConstraint(
            "status IN ('"
            + "','".join(RUN_STATUSES)
            + "')",
            name="runs_status_check",
        ),
        Index("ix_runs_user_id_created_at", "user_id", "created_at"),
        Index("ix_runs_status", "status"),
    )

    id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    prior_run_id: Mapped[UUID | None] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("runs.id", ondelete="SET NULL"),
        nullable=True,
    )
    status: Mapped[str] = mapped_column(String(40), default="queued", nullable=False)
    topics: Mapped[list[str]] = mapped_column(ARRAY(String), default=list, nullable=False)
    urls: Mapped[list[str]] = mapped_column(ARRAY(String), default=list, nullable=False)
    report: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    failure_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        sqltypes.DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        sqltypes.DateTime(timezone=True), nullable=True
    )

    user: Mapped[User] = relationship(back_populates="runs")
    sources: Mapped[list[Source]] = relationship(
        back_populates="run", cascade="all, delete-orphan"
    )
    facts: Mapped[list[RunFact]] = relationship(
        back_populates="run", cascade="all, delete-orphan"
    )
    usage_events: Mapped[list[UsageEvent]] = relationship(
        back_populates="run", cascade="all, delete-orphan"
    )
    run_events: Mapped[list[RunEvent]] = relationship(
        back_populates="run", cascade="all, delete-orphan"
    )


class Source(Base):
    __tablename__ = "sources"
    __table_args__ = (
        CheckConstraint(
            "origin IN ('" + "','".join(SOURCE_ORIGINS) + "')",
            name="sources_origin_check",
        ),
        Index("ix_sources_run_id", "run_id"),
    )

    id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), primary_key=True, default=uuid4)
    run_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("runs.id", ondelete="CASCADE"), nullable=False
    )
    url: Mapped[str] = mapped_column(Text, nullable=False)
    origin: Mapped[str] = mapped_column(String(16), nullable=False)
    title: Mapped[str | None] = mapped_column(Text, nullable=True)
    fetched_text: Mapped[str] = mapped_column(Text, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    bytes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    fetched_at: Mapped[datetime] = mapped_column(
        sqltypes.DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    topic_match: Mapped[str | None] = mapped_column(String(128), nullable=True)

    run: Mapped[Run] = relationship(back_populates="sources")


class RunFact(Base):
    __tablename__ = "run_facts"
    __table_args__ = (
        CheckConstraint(
            "judge_verdict IS NULL OR judge_verdict IN ('"
            + "','".join(JUDGE_VERDICTS)
            + "')",
            name="run_facts_judge_verdict_check",
        ),
        CheckConstraint(
            "diff_tag IS NULL OR diff_tag IN ('" + "','".join(DIFF_TAGS) + "')",
            name="run_facts_diff_tag_check",
        ),
        Index("ix_run_facts_run_id", "run_id"),
        Index("ix_run_facts_claim_hash", "claim_hash"),
    )

    id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), primary_key=True, default=uuid4)
    run_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("runs.id", ondelete="CASCADE"), nullable=False
    )
    claim_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    claim: Mapped[str] = mapped_column(Text, nullable=False)
    evidence: Mapped[str | None] = mapped_column(Text, nullable=True)
    theme: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_id: Mapped[UUID | None] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("sources.id", ondelete="SET NULL"),
        nullable=True,
    )
    judge_verdict: Mapped[str | None] = mapped_column(String(16), nullable=True)
    judge_rationale: Mapped[str | None] = mapped_column(Text, nullable=True)
    diff_tag: Mapped[str | None] = mapped_column(String(16), nullable=True)

    run: Mapped[Run] = relationship(back_populates="facts")


class UsageEvent(Base):
    __tablename__ = "usage_events"
    __table_args__ = (
        Index("ix_usage_events_run_id", "run_id"),
        Index("ix_usage_events_created_at", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), primary_key=True, default=uuid4)
    run_id: Mapped[UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("runs.id", ondelete="CASCADE"), nullable=True
    )
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    model: Mapped[str] = mapped_column(String(64), nullable=False)
    phase: Mapped[str] = mapped_column(String(32), nullable=False)
    input_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    cost_usd: Mapped[Decimal] = mapped_column(
        Numeric(12, 6), default=Decimal("0"), nullable=False
    )
    duration_ms: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        sqltypes.DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    run: Mapped[Run | None] = relationship(back_populates="usage_events")


class RunEvent(Base):
    __tablename__ = "run_events"
    __table_args__ = (
        Index("ix_run_events_run_id_at", "run_id", "at"),
    )

    id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), primary_key=True, default=uuid4)
    run_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("runs.id", ondelete="CASCADE"), nullable=False
    )
    from_state: Mapped[str | None] = mapped_column(String(40), nullable=True)
    to_state: Mapped[str] = mapped_column(String(40), nullable=False)
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    at: Mapped[datetime] = mapped_column(
        sqltypes.DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    run: Mapped[Run] = relationship(back_populates="run_events")


class AppEvent(Base):
    __tablename__ = "app_events"
    __table_args__ = (
        CheckConstraint(
            "kind IN ('" + "','".join(APP_EVENT_KINDS) + "')",
            name="app_events_kind_check",
        ),
        Index("ix_app_events_kind_created_at", "kind", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), primary_key=True, default=uuid4)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    user_id: Mapped[UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    run_id: Mapped[UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("runs.id", ondelete="SET NULL"), nullable=True
    )
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        sqltypes.DateTime(timezone=True), server_default=func.now(), nullable=False
    )
