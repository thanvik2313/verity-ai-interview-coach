"""Ports the identity application layer depends on.

Clean Architecture / dependency inversion (FolderStructure.md §2:
"application services depend on contracts/ports; adapters implement
ports"). Every interface here is a `typing.Protocol` — structural typing,
no base class an adapter must inherit from, and a Protocol definition
itself carries no SQLAlchemy or framework dependency. Concrete
implementations (a SQLAlchemy-backed `UserRepository`, a Postgres-backed
`RefreshSessionRepository`, etc.) belong in `adapters/`, added in a later
task; none exist yet, matching this milestone's "do not implement
repositories yet."
"""

from __future__ import annotations

from datetime import datetime
from typing import Protocol
from uuid import UUID

from verity.modules.identity.application.types import NewUserProfile, StoredRefreshSession
from verity.modules.identity.domain.models import User


class UserRepository(Protocol):
    """Persistence port for `User` (Milestone B's ORM entity).

    Methods are `async` to match the project's async SQLAlchemy stack
    (TechStack.md §3), even though no implementation exists yet.
    """

    async def get_by_id(self, user_id: UUID) -> User | None:
        """Look up a user by primary key, or None if no such user exists."""
        ...

    async def get_by_email_hash(self, email_lookup_hash: str) -> User | None:
        """Look up a user by their keyed email lookup hash (Database.md
        §4.1), or None if no such user exists. Never accepts a plaintext
        email — callers hash it first via `verity.core.crypto.hash_email`.
        """
        ...

    async def create(self, profile: NewUserProfile) -> User:
        """Insert and return a new user for an already policy-checked profile."""
        ...

    async def save(self, user: User) -> None:
        """Persist changes to an already-loaded `User` (e.g. a status
        transition). Kept distinct from `create` so a service can never
        accidentally insert a duplicate row when it only meant to update
        one.
        """
        ...


class RefreshSessionRepository(Protocol):
    """Persistence port for refresh sessions (Database.md `auth_sessions`).

    No `auth_sessions` ORM model exists yet — Milestone B covered only
    `users`. This port describes the shape the application layer needs;
    the concrete table/model and its adapter are added together in a
    later task.
    """

    async def create(
        self, *, user_id: UUID, token_hash: str, expires_at: datetime
    ) -> StoredRefreshSession:
        """Persist a new refresh session and return its stored record."""
        ...

    async def get(self, session_id: UUID) -> StoredRefreshSession | None:
        """Look up a session's current stored record, or None if it does
        not exist or has already been revoked."""
        ...

    async def rotate(
        self, session_id: UUID, *, new_token_hash: str, expires_at: datetime
    ) -> StoredRefreshSession:
        """Replace a session's stored hash/expiry after a successful
        refresh, and return the updated record."""
        ...

    async def revoke(self, session_id: UUID) -> None:
        """Revoke a single session (used by logout)."""
        ...

    async def revoke_all_for_user(self, user_id: UUID) -> None:
        """Revoke every session belonging to a user (used by logout-all)."""
        ...
