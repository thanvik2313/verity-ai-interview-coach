"""create auth_sessions table

Revision ID: 0002
Revises: 0001
Create Date: 2026-07-16

Database.md §4.1 — server-revocable rotating refresh sessions. Added in
Part E to back the SQLAlchemy adapter satisfying Part D's frozen
`RefreshSessionRepository` port. `token_family_id` groups every row in a
rotation chain; `rotated_from_id` links a row to the one it replaced;
`revoked_at`/`compromise_detected_at` mark rows inactive.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "auth_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("token_family_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("refresh_token_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rotated_from_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("compromise_detected_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_auth_sessions_user_id_users",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["rotated_from_id"],
            ["auth_sessions.id"],
            name="fk_auth_sessions_rotated_from_id_auth_sessions",
            ondelete="SET NULL",
        ),
    )
    op.create_index("ix_auth_sessions_user_id", "auth_sessions", ["user_id"])
    op.create_index("ix_auth_sessions_token_family_id", "auth_sessions", ["token_family_id"])


def downgrade() -> None:
    op.drop_index("ix_auth_sessions_token_family_id", table_name="auth_sessions")
    op.drop_index("ix_auth_sessions_user_id", table_name="auth_sessions")
    op.drop_table("auth_sessions")
