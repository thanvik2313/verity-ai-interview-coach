"""Identity application services — use-case orchestration.

Depends only on domain, contracts, and core (this milestone's stated
boundary) plus this module's own interfaces/types/validators/exceptions.
No FastAPI import, no SQLAlchemy query, no concrete repository or OAuth
adapter — those are injected here as `interfaces.py` ports and implemented
in `adapters/` in a later task. Until then, these services are usable only
with test doubles that satisfy `UserRepository`/`RefreshSessionRepository`.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

from verity.core.config import Settings
from verity.core.crypto import hash_email
from verity.core.errors import InvalidRefreshTokenError
from verity.core.security import (
    create_access_token,
    decode_access_token,
    generate_refresh_token,
    verify_refresh_token,
)
from verity.modules.identity.application.exceptions import (
    AccountNotActiveError,
    InvalidSessionError,
    RefreshTokenReuseDetectedError,
    UserNotFoundError,
)
from verity.modules.identity.application.interfaces import (
    RefreshSessionRepository,
    UserRepository,
)
from verity.modules.identity.application.types import ExternalIdentity, IssuedTokenPair
from verity.modules.identity.application.validators import build_new_user_profile
from verity.modules.identity.contracts.user_schemas import UserRead
from verity.modules.identity.domain.models import User, UserStatus


class IdentitySessionService:
    """Use cases for establishing, refreshing, and ending a session.

    Constructed with its ports injected — no adapter is wired up yet, so
    this class only becomes reachable from an actual HTTP request once a
    route handler and concrete repositories exist (both later tasks).
    """

    def __init__(
        self,
        *,
        users: UserRepository,
        sessions: RefreshSessionRepository,
        settings: Settings,
    ) -> None:
        self._users = users
        self._sessions = sessions
        self._settings = settings

    async def start_session_for_external_identity(
        self, identity: ExternalIdentity
    ) -> tuple[User, IssuedTokenPair]:
        """Find-or-create a user for a verified external identity, then
        issue a new token pair for them.

        The OAuth handshake itself — verifying `identity` really came from
        Google — is an adapter's job, done before this method is ever
        called. This method only knows about an already-verified
        `ExternalIdentity`; it never talks to an OAuth provider.
        """
        email_hash = hash_email(identity.email, hash_key=self._settings.email_hash_key)
        user = await self._users.get_by_email_hash(email_hash)

        if user is None:
            profile = build_new_user_profile(identity)
            user = await self._users.create(profile)

        self._ensure_active(user)
        token_pair = await self._issue_new_session(user)
        return user, token_pair

    async def refresh_session(
        self, *, session_id: UUID, raw_refresh_token: str
    ) -> IssuedTokenPair:
        """Rotate an active refresh session (API.md §3: `POST /v1/auth/refresh`).

        Raises:
            InvalidSessionError: The session does not exist, was already
                revoked, or has expired.
            RefreshTokenReuseDetectedError (an `InvalidSessionError`
                subclass): The presented refresh token did not match the
                session's stored hash while the session was otherwise
                still active — treated as a possible stolen/replayed
                token (Database.md §4.1: "Refresh-token reuse revokes the
                token family"), so the entire family is revoked via the
                existing `RefreshSessionRepository.revoke` port before
                this raises; no interface or adapter change was needed
                for that.
            UserNotFoundError: The session references a user that no
                longer exists.
            AccountNotActiveError: The user exists but is not active.
        """
        stored = await self._sessions.get(session_id)
        if stored is None:
            raise InvalidSessionError("Refresh session does not exist or was revoked.")
        if stored.expires_at <= datetime.now(UTC):
            raise InvalidSessionError("Refresh session has expired.")

        try:
            verify_refresh_token(raw_value=raw_refresh_token, expected_hash=stored.token_hash)
        except InvalidRefreshTokenError as exc:
            # A mismatched refresh token against an otherwise-active,
            # unexpired session most plausibly means this token was
            # already rotated away and is now being replayed — treat the
            # whole family as compromised rather than only failing this
            # one request.
            await self._sessions.revoke(session_id)
            raise RefreshTokenReuseDetectedError(
                "Refresh token did not match; session family revoked."
            ) from exc

        user = await self._users.get_by_id(stored.user_id)
        if user is None:
            raise UserNotFoundError(
                f"User {stored.user_id} referenced by session {session_id} no longer exists."
            )
        self._ensure_active(user)

        new_refresh = generate_refresh_token(settings=self._settings)
        new_expires_at = datetime.now(UTC) + timedelta(
            seconds=self._settings.refresh_token_ttl_seconds
        )
        rotated = await self._sessions.rotate(
            session_id, new_token_hash=new_refresh.token_hash, expires_at=new_expires_at
        )

        access_token, access_expires_at = self._issue_access_token(
            user, session_id=rotated.session_id
        )

        return IssuedTokenPair(
            access_token=access_token,
            access_token_expires_at=access_expires_at,
            refresh_token=new_refresh.raw_value,
            refresh_token_expires_at=rotated.expires_at,
            session_id=rotated.session_id,
        )

    async def end_session(self, session_id: UUID) -> None:
        """`POST /v1/auth/logout` (API.md §3) — revoke a single session."""
        await self._sessions.revoke(session_id)

    async def end_all_sessions(self, user_id: UUID) -> None:
        """`POST /v1/auth/logout-all` (API.md §3) — revoke every session
        for a user."""
        await self._sessions.revoke_all_for_user(user_id)

    async def _issue_new_session(self, user: User) -> IssuedTokenPair:
        refresh = generate_refresh_token(settings=self._settings)
        refresh_expires_at = datetime.now(UTC) + timedelta(
            seconds=self._settings.refresh_token_ttl_seconds
        )
        stored = await self._sessions.create(
            user_id=user.id, token_hash=refresh.token_hash, expires_at=refresh_expires_at
        )

        access_token, access_expires_at = self._issue_access_token(
            user, session_id=stored.session_id
        )

        return IssuedTokenPair(
            access_token=access_token,
            access_token_expires_at=access_expires_at,
            refresh_token=refresh.raw_value,
            refresh_token_expires_at=stored.expires_at,
            session_id=stored.session_id,
        )

    def _issue_access_token(self, user: User, *, session_id: UUID) -> tuple[str, datetime]:
        token = create_access_token(
            subject=str(user.id),
            role=user.role.value,
            session_id=str(session_id),
            settings=self._settings,
        )
        claims = decode_access_token(token, settings=self._settings)
        return token, claims.expires_at

    @staticmethod
    def _ensure_active(user: User) -> None:
        if user.status != UserStatus.ACTIVE:
            raise AccountNotActiveError(f"User {user.id} is not active.")


class IdentityQueryService:
    """Read-only use cases for identity data.

    Kept separate from `IdentitySessionService`: this service has no
    session/token side effects and needs only a `UserRepository`, so
    nothing that only reads identity data is forced to depend on session
    machinery it doesn't use.
    """

    def __init__(self, *, users: UserRepository) -> None:
        self._users = users

    async def get_current_user(self, user_id: UUID) -> UserRead:
        """`GET /v1/auth/me` (API.md §3) — the public projection of the
        caller's own identity.

        Raises:
            UserNotFoundError: No such user (e.g. deleted between token
                issuance and this call).
        """
        user = await self._users.get_by_id(user_id)
        if user is None:
            raise UserNotFoundError(f"User {user_id} not found.")
        return UserRead.model_validate(user)
