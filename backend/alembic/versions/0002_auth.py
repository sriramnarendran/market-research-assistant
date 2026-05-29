"""Phase 2 auth columns on users.

Revision ID: 0002_auth
Revises: 0001_initial
Create Date: 2026-05-28 12:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002_auth"
down_revision: str | Sequence[str] | None = "0001_initial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Placeholder hash for existing rows — seed script replaces with real Argon2 hashes.
_PLACEHOLDER_HASH = "$argon2id$v=19$m=65536,t=3,p=4$placeholder$placeholder"


def upgrade() -> None:
    # Backfill email for rows that only have NULL email (dev user).
    op.execute(
        sa.text(
            "UPDATE users SET email = 'dev@local' WHERE email IS NULL"
        )
    )

    op.add_column(
        "users",
        sa.Column("password_hash", sa.Text(), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column("role", sa.String(length=16), server_default="user", nullable=False),
    )
    op.add_column(
        "users",
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.execute(
        sa.text(f"UPDATE users SET password_hash = '{_PLACEHOLDER_HASH}' WHERE password_hash IS NULL")
    )
    op.alter_column("users", "password_hash", nullable=False)

    op.alter_column("users", "email", existing_type=sa.String(length=320), nullable=False)

    op.create_check_constraint(
        "users_role_check",
        "users",
        "role IN ('user', 'admin')",
    )


def downgrade() -> None:
    op.drop_constraint("users_role_check", "users", type_="check")
    op.alter_column("users", "email", existing_type=sa.String(length=320), nullable=True)
    op.drop_column("users", "last_login_at")
    op.drop_column("users", "role")
    op.drop_column("users", "password_hash")
