"""SQLAlchemy async adapter for `UserRepository` (Part D's port).

Implements `verity.modules.identity.application.interfaces.UserRepository`
without SQLAlchemy leaking into the application layer — this file is the
only place that translates between `NewUserProfile`/`User` and actual SQL.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from verity.core.config import Settings
from verity.core.crypto import encrypt_email, hash_email
from verity.modules.identity.application.types import NewUserProfile
from verity.modules.identity.domain.models import User, UserStatus, generate_uuid7


class SqlAlchemyUserRepository:
    """Concrete `UserRepository` backed by the async SQLAlchemy session
    infrastructure from Part A (`verity.db.session`).

    Not wired into any FastAPI dependency yet — out of this milestone's
    scope. Construct directly with a session obtained from
    `verity.db.session.get_db` once a route exists.
    """

    def __init__(self, session: AsyncSession, *, settings: Settings) -> None:
        self._session = session
        self._settings = settings

    async def get_by_id(self, user_id: UUID) -> User | None:
        return await self._session.get(User, user_id)

    async def get_by_email_hash(self, email_lookup_hash: str) -> User | None:
        result = await self._session.execute(
            select(User).where(User.email_lookup_hash == email_lookup_hash)
        )
        return result.scalar_one_or_none()

    async def create(self, profile: NewUserProfile) -> User:
        user = User(
            id=generate_uuid7(),
            email_lookup_hash=hash_email(profile.email, hash_key=self._settings.email_hash_key),
            email_ciphertext=encrypt_email(
                profile.email, encryption_key=self._settings.email_encryption_key
            ),
            display_name=profile.display_name,
            role=profile.role,
            status=UserStatus.ACTIVE,
        )
        self._session.add(user)
        await self._session.flush()
        return user

    async def save(self, user: User) -> None:
        self._session.add(user)
        await self._session.flush()
