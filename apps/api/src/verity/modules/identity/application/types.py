"""Internal application-layer value objects for the identity module.

Distinct from `contracts/` (Milestone C): contracts are the API-facing
wire shapes a route handler serializes to JSON. These types are what
application services actually accept and return — an adapter (a route
handler, or e.g. an admin CLI, both added in later tasks) maps between the
two. Keeping them separate means contracts/ can change to fit a specific
endpoint's response shape without changing a service's signature, and a
service stays reusable by more than one adapter.

Distinct from `domain/` (Milestone B): `domain/models.py` holds the
persistence-mapped `User` entity. None of these types import SQLAlchemy.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from verity.modules.identity.domain.models import UserRole


@dataclass(frozen=True, slots=True)
class ExternalIdentity:
    """A verified identity handed to the application layer by an OAuth
    adapter (added in a later task) once it has completed the provider
    handshake and validated the provider's response.

    Deliberately provider-agnostic: the find-or-create use case in
    `services.py` does not know or care whether `provider` is `"google"`
    or something added later — OAuth protocol specifics stay in the
    adapter that constructs this value, not in the application layer.
    """

    provider: str
    provider_subject: str
    """The provider's stable subject/user id (e.g. Google's `sub` claim),
    not the email — so a later email change at the provider does not
    orphan the account. Not yet persisted anywhere (no repository exists
    yet); reserved for the repository design added in a later task."""
    email: str
    display_name: str


@dataclass(frozen=True, slots=True)
class NewUserProfile:
    """Fields required to create a new identity, already policy-checked by
    `validators.build_new_user_profile` before a service acts on them —
    in particular, `role` is always `UserRole.CANDIDATE` for this path.
    """

    email: str
    display_name: str
    role: UserRole


@dataclass(frozen=True, slots=True)
class IssuedTokenPair:
    """The result of issuing a new (or rotated) access/refresh token pair.

    Both raw token values appear here exactly once, for the caller to set
    as Secure/HttpOnly cookies (TechStack.md §3) — the application layer
    itself never stores or logs either raw value.
    """

    access_token: str
    access_token_expires_at: datetime
    refresh_token: str
    refresh_token_expires_at: datetime
    session_id: UUID


@dataclass(frozen=True, slots=True)
class StoredRefreshSession:
    """The persisted shape of one row of Database.md's `auth_sessions`
    table, as far as the application layer needs to know it. No ORM model
    for `auth_sessions` exists yet (Milestone B covered only `users`) —
    this is the port-level contract a repository implementation (added in
    a later task) must satisfy.
    """

    session_id: UUID
    user_id: UUID
    token_hash: str
    expires_at: datetime


@dataclass(frozen=True, slots=True)
class AuthenticatedUser:
    """A minimal, application-layer view of "who is making this request,"
    built from an already-validated access token. Distinct from
    `contracts.TokenPayload` (Milestone C), which is the validated *wire*
    shape of decoded claims; this is what a service method would receive
    once a caller (a JWT dependency, added in a later task) has already
    performed that validation.
    """

    user_id: UUID
    role: UserRole
    session_id: UUID
