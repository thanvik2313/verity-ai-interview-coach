"""Identity application service — authentication core (Part F).

Verifies an already-issued access token and resolves it to an
authenticated identity. This is the missing "reverse direction" of Part
D's `IdentitySessionService`, which only issues/rotates/revokes tokens —
nothing before this milestone actually validated one against current
account *and session* state. A JWT-based FastAPI dependency (added in a
later task, out of this milestone's scope) is the intended caller.
"""

from __future__ import annotations

from uuid import UUID

from verity.core.config import Settings
from verity.core.errors import InvalidTokenError
from verity.core.security import decode_access_token
from verity.modules.identity.application.exceptions import (
    AccountNotActiveError,
    InvalidSessionError,
    UserNotFoundError,
)
from verity.modules.identity.application.interfaces import (
    RefreshSessionRepository,
    UserRepository,
)
from verity.modules.identity.application.types import AuthenticatedUser
from verity.modules.identity.domain.models import UserRole, UserStatus


class AuthenticationService:
    """Use case: "who is this access token for, and are they still allowed
    to act?"

    Re-checks current state on every call rather than trusting the token's
    claims alone, because a stateless JWT cannot reflect either of these
    happening after it was issued but before it naturally expires:

    - the account being suspended/deleted (`UserRepository`, reused from
      Part D/E), or
    - the owning session being revoked via logout or refresh-token-reuse
      detection (`RefreshSessionRepository`, reused from Part D/E — its
      `get()` already returns `None` for a revoked session, per the Part E
      adapter; no interface or adapter change was needed here).

    This second check is what makes logout an effective, immediate
    revocation of any access token issued under that session, not just a
    block on future refreshes.
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

    async def authenticate_access_token(self, token: str) -> AuthenticatedUser:
        """Validate `token` and return the caller's current identity.

        Raises:
            core.errors.TokenExpiredError: The token's signature is valid
                but it has expired (propagated as-is from
                `core.security.decode_access_token` — already a typed
                `AuthenticationError`).
            core.errors.InvalidTokenError: The token failed validation, or
                its claims were structurally valid but semantically
                malformed (unparseable UUID/role).
            UserNotFoundError: The token's subject no longer exists (e.g.
                account deleted after the token was issued).
            AccountNotActiveError: The user exists but is not active.
            InvalidSessionError: The owning session has been revoked
                (logout, logout-all, or reuse-detected rotation) or has
                expired, even though the access token JWT itself is still
                within its own TTL.
        """
        claims = decode_access_token(token, settings=self._settings)

        try:
            user_id = UUID(claims.subject)
            session_id = UUID(claims.session_id)
            role = UserRole(claims.role)
        except ValueError as exc:
            raise InvalidTokenError("Access token claims are malformed.") from exc

        user = await self._users.get_by_id(user_id)
        if user is None:
            raise UserNotFoundError(
                f"User {user_id} referenced by an access token no longer exists."
            )
        if user.status != UserStatus.ACTIVE:
            raise AccountNotActiveError(f"User {user.id} is not active.")

        session = await self._sessions.get(session_id)
        if session is None:
            raise InvalidSessionError(
                f"Session {session_id} for user {user_id} has been revoked or expired."
            )

        return AuthenticatedUser(user_id=user.id, role=role, session_id=session_id)
