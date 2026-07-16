"""Identity module — refresh session persistence entity.

Added in Part E to satisfy Part D's frozen `RefreshSessionRepository`
port, which needs somewhere to persist `StoredRefreshSession` records.
Columns match Database.md §4.1's `auth_sessions` row exactly: user_id,
token_family_id, refresh_token_hash, expires_at, revoked_at,
rotated_from_id, compromise_detected_at.

Deviation note: mirrors the same domain/SQLAlchemy placement deviation
already flagged in `models.py` (Part B) — TechStack.md §3 says SQLAlchemy
models stay internal to the persistence adapter. Kept alongside `User` for
consistency with that existing decision rather than splitting entity
placement across two conventions.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from verity.db.base import Base
from verity.modules.identity.domain.models import generate_uuid7


class AuthSession(Base):
    """Server-revocable rotating refresh session (Database.md §4.1).

    One row per issuance *and* per rotation: `token_family_id` is shared
    by every row in a rotation chain, `rotated_from_id` links a row to the
    row it replaced, and `revoked_at`/`compromise_detected_at` mark a row
    inactive. Full family-wide "reuse revokes the token family" behavior
    is not yet reachable through Part D's frozen `RefreshSessionRepository`
    interface (see the Part E conflict note); this model persists the
    columns needed for it ahead of that interface change.
    """

    __tablename__ = "auth_sessions"

    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=generate_uuid7,
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE", name="fk_auth_sessions_user_id_users"),
        nullable=False,
        index=True,
    )

    token_family_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        nullable=False,
        index=True,
    )
    """Shared by every row in one rotation chain. This, not `id`, is what
    `verity.core.security` calls the JWT `sid` claim and what
    `application.types.StoredRefreshSession.session_id` refers to."""

    refresh_token_hash: Mapped[str] = mapped_column(
        String(64),  # SHA-256 hex digest — verity.core.security.hash_refresh_token
        nullable=False,
    )

    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    rotated_from_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey(
            "auth_sessions.id",
            ondelete="SET NULL",
            name="fk_auth_sessions_rotated_from_id_auth_sessions",
        ),
        nullable=True,
    )

    compromise_detected_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    """Set when a repository implementation detects refresh-token reuse
    (Database.md §4.1). Not written by any code path in this milestone —
    see the interface-boundary note above."""

    def __repr__(self) -> str:
        return (
            f"AuthSession(id={self.id!r}, token_family_id={self.token_family_id!r}, "
            f"revoked_at={self.revoked_at!r})"
        )
