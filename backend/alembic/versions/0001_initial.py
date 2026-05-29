"""Phase 1 initial schema: users, runs, sources, run_facts, usage_events, run_events.

Revision ID: 0001_initial
Revises:
Create Date: 2026-05-28 00:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001_initial"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


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

JUDGE_VERDICTS = ("verified", "unsupported", "contradicted")
DIFF_TAGS = ("new", "unchanged", "removed")
SOURCE_ORIGINS = ("url_path", "tavily")


def _in_list(col: str, values: tuple[str, ...]) -> str:
    quoted = ",".join(f"'{v}'" for v in values)
    return f"{col} IN ({quoted})"


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(length=320), nullable=True, unique=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )

    op.create_table(
        "runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "prior_run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("runs.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("status", sa.String(length=40), nullable=False, server_default="queued"),
        sa.Column(
            "topics",
            postgresql.ARRAY(sa.String()),
            nullable=False,
            server_default=sa.text("ARRAY[]::text[]"),
        ),
        sa.Column(
            "urls",
            postgresql.ARRAY(sa.String()),
            nullable=False,
            server_default=sa.text("ARRAY[]::text[]"),
        ),
        sa.Column("report", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("failure_reason", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(_in_list("status", RUN_STATUSES), name="runs_status_check"),
    )
    op.create_index("ix_runs_user_id_created_at", "runs", ["user_id", "created_at"])
    op.create_index("ix_runs_status", "runs", ["status"])

    op.create_table(
        "sources",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("origin", sa.String(length=16), nullable=False),
        sa.Column("title", sa.Text(), nullable=True),
        sa.Column("fetched_text", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("bytes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "fetched_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(_in_list("origin", SOURCE_ORIGINS), name="sources_origin_check"),
    )
    op.create_index("ix_sources_run_id", "sources", ["run_id"])

    op.create_table(
        "run_facts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("claim_hash", sa.String(length=64), nullable=False),
        sa.Column("claim", sa.Text(), nullable=False),
        sa.Column("evidence", sa.Text(), nullable=True),
        sa.Column("theme", sa.Text(), nullable=True),
        sa.Column(
            "source_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("sources.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("judge_verdict", sa.String(length=16), nullable=True),
        sa.Column("judge_rationale", sa.Text(), nullable=True),
        sa.Column("diff_tag", sa.String(length=16), nullable=True),
        sa.CheckConstraint(
            "judge_verdict IS NULL OR "
            + _in_list("judge_verdict", JUDGE_VERDICTS),
            name="run_facts_judge_verdict_check",
        ),
        sa.CheckConstraint(
            "diff_tag IS NULL OR " + _in_list("diff_tag", DIFF_TAGS),
            name="run_facts_diff_tag_check",
        ),
    )
    op.create_index("ix_run_facts_run_id", "run_facts", ["run_id"])
    op.create_index("ix_run_facts_claim_hash", "run_facts", ["claim_hash"])

    op.create_table(
        "usage_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("runs.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("model", sa.String(length=64), nullable=False),
        sa.Column("phase", sa.String(length=32), nullable=False),
        sa.Column("input_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("output_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("cost_usd", sa.Numeric(12, 6), nullable=False, server_default="0"),
        sa.Column("duration_ms", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index("ix_usage_events_run_id", "usage_events", ["run_id"])
    op.create_index("ix_usage_events_created_at", "usage_events", ["created_at"])

    op.create_table(
        "run_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("from_state", sa.String(length=40), nullable=True),
        sa.Column("to_state", sa.String(length=40), nullable=False),
        sa.Column("detail", sa.Text(), nullable=True),
        sa.Column(
            "at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index("ix_run_events_run_id_at", "run_events", ["run_id", "at"])


def downgrade() -> None:
    op.drop_index("ix_run_events_run_id_at", table_name="run_events")
    op.drop_table("run_events")
    op.drop_index("ix_usage_events_created_at", table_name="usage_events")
    op.drop_index("ix_usage_events_run_id", table_name="usage_events")
    op.drop_table("usage_events")
    op.drop_index("ix_run_facts_claim_hash", table_name="run_facts")
    op.drop_index("ix_run_facts_run_id", table_name="run_facts")
    op.drop_table("run_facts")
    op.drop_index("ix_sources_run_id", table_name="sources")
    op.drop_table("sources")
    op.drop_index("ix_runs_status", table_name="runs")
    op.drop_index("ix_runs_user_id_created_at", table_name="runs")
    op.drop_table("runs")
    op.drop_table("users")
