"""Add topic_match to sources for per-keyword coverage tracking.

Revision ID: 0004_source_topic_match
Revises: 0003_observability
Create Date: 2026-05-28 18:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004_source_topic_match"
down_revision: str | Sequence[str] | None = "0003_observability"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("sources", sa.Column("topic_match", sa.String(length=128), nullable=True))


def downgrade() -> None:
    op.drop_column("sources", "topic_match")
