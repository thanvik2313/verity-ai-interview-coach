"""SQLAlchemy async adapter for `RefreshSessionRepository` (Part D's port).

`StoredRefreshSession.session_id` corresponds to `AuthSession.token_family_id`,
not `AuthSession.id` — see the mapping note in
`verity.modules.identity.domain.session_models.AuthSession`.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from verity.modules.identity.application.exceptions import InvalidSessionError
from verity.modules.identity.application.types import StoredRefreshSession
from verity.modules.identity.domain.models import generate_uuid7
from verity.modules.identity.domain.session_models import AuthSession


class SqlAlchemyRefreshSessionRepository:
    """Concrete `RefreshSessionRepository` backed by `AuthSession`.

    Not wired into any FastAPI dependency yet — out of this milestone's
    scope. Construct directly with a session obtained from
    `verity.db.session.get_db` once a route exists.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self, *, user_id: UUID, token_hash: str, expires_at: datetime
    ) -> StoredRefreshSession:
        row = AuthSession(
            id=generate_uuid7(),
            user_id=user_id,
            token_family_id=generate_uuid7(),
            refresh_token_hash=token_hash,
            expires_at=expires_at,
        )
        self._session.add(row)
        await self._session.flush()
        return self._to_dto(row)

    async def get(self, session_id: UUID) -> StoredRefreshSession | None:
        row = await self._get_active_head(session_id)
        return self._to_dto(row) if row is not None else None

    async def rotate(
        self, session_id: UUID, *, new_token_hash: str, expires_at: datetime
    ) -> StoredRefreshSession:
        current = await self._get_active_head(session_id)
        if current is None:
            raise InvalidSessionError(f"No active refresh session for family {session_id}.")

        current.revoked_at = datetime.now(UTC)

        new_row = AuthSession(
            id=generate_uuid7(),
            user_id=current.user_id,
            token_family_id=current.token_family_id,
            refresh_token_hash=new_token_hash,
            expires_at=expires_at,
            rotated_from_id=current.id,
        )
        self._session.add(new_row)
        await self._session.flush()
        return self._to_dto(new_row)

    async def revoke(self, session_id: UUID) -> None:
        await self._session.execute(
            update(AuthSession)
            .where(AuthSession.token_family_id == session_id, AuthSession.revoked_at.is_(None))
            .values(revoked_at=datetime.now(UTC))
        )
        await self._session.flush()

    async def revoke_all_for_user(self, user_id: UUID) -> None:
        await self._session.execute(
            update(AuthSession)
            .where(AuthSession.user_id == user_id, AuthSession.revoked_at.is_(None))
            .values(revoked_at=datetime.now(UTC))
        )
        await self._session.flush()

    async def _get_active_head(self, token_family_id: UUID) -> AuthSession | None:
        result = await self._session.execute(
            select(AuthSession)
            .where(
                AuthSession.token_family_id == token_family_id,
                AuthSession.revoked_at.is_(None),
            )
            .order_by(AuthSession.id.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    @staticmethod
    def _to_dto(row: AuthSession) -> StoredRefreshSession:
        return StoredRefreshSession(
            session_id=row.token_family_id,
            user_id=row.user_id,
            token_hash=row.refresh_token_hash,
            expires_at=row.expires_at,
        )
