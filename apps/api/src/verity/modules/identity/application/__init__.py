"""Identity module — application layer.

Use-case orchestration (FolderStructure.md §2: "Use cases,
commands/queries, transaction boundaries, policies"). Depends only on
domain, contracts, and core — this milestone's stated boundary — plus its
own interfaces/types/validators/exceptions. Contains no FastAPI import and
defines no SQLAlchemy models. `adapters/` (concrete repositories, the
OAuth provider adapter, and route handlers) is added in a later task and
is the only place these services get wired to a real database or HTTP
framework.
"""

from verity.modules.identity.application.authentication_service import AuthenticationService
from verity.modules.identity.application.exceptions import (
    AccountNotActiveError,
    DuplicateIdentityError,
    IdentityApplicationError,
    InvalidIdentityError,
    InvalidSessionError,
    RefreshTokenReuseDetectedError,
    RoleAssignmentError,
    UserNotFoundError,
)
from verity.modules.identity.application.interfaces import (
    RefreshSessionRepository,
    UserRepository,
)
from verity.modules.identity.application.services import (
    IdentityQueryService,
    IdentitySessionService,
)
from verity.modules.identity.application.types import (
    AuthenticatedUser,
    ExternalIdentity,
    IssuedTokenPair,
    NewUserProfile,
    StoredRefreshSession,
)

__all__ = [
    "AccountNotActiveError",
    "AuthenticatedUser",
    "AuthenticationService",
    "DuplicateIdentityError",
    "ExternalIdentity",
    "IdentityApplicationError",
    "IdentityQueryService",
    "IdentitySessionService",
    "InvalidIdentityError",
    "InvalidSessionError",
    "IssuedTokenPair",
    "NewUserProfile",
    "RefreshSessionRepository",
    "RefreshTokenReuseDetectedError",
    "RoleAssignmentError",
    "StoredRefreshSession",
    "UserNotFoundError",
    "UserRepository",
]
