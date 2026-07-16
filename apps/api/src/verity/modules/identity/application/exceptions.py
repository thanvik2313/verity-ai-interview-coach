"""Identity application-layer exceptions.

Extends `verity.core.errors` (an allowed `core` dependency) with use-case
level failures. Kept distinct from `core.errors` because these describe
*business* outcomes of a use case (e.g. "no such user"), not
infrastructure/security-primitive failures (e.g. "bad JWT signature").
Route handlers (added in a later task) map these to HTTP status codes the
same way `verity.main.app` already maps `core.errors.AuthenticationError`.
"""

from __future__ import annotations

from verity.core.errors import VerityError


class IdentityApplicationError(VerityError):
    """Base class for identity-module application-layer errors."""


class UserNotFoundError(IdentityApplicationError):
    """No user exists for the given identifier/lookup key."""


class AccountNotActiveError(IdentityApplicationError):
    """The user exists but its status does not permit this operation.

    Deliberately generic (not e.g. `AccountSuspendedError`) so callers
    can't use the exception type to distinguish suspended vs
    pending_deletion vs deleted and branch user-visible behavior on it —
    mirrors `core.errors.AuthenticationError`'s same non-disclosure rule.
    """


class DuplicateIdentityError(IdentityApplicationError):
    """An account already exists for this external identity's email.

    Not raised anywhere in this milestone's `services.py` — find-or-create
    there simply returns the existing user. Reserved for a repository
    implementation (added in a later task) to raise after translating a
    unique-constraint violation on `users.email_lookup_hash` under a
    concurrent-signup race, so that case has a stable, typed identity for
    callers to catch rather than a raw database error leaking upward.
    """


class InvalidSessionError(IdentityApplicationError):
    """A refresh session is missing, expired, revoked, or reused.

    Deliberately generic for the same reason as `AccountNotActiveError` —
    the specific cause (revoked vs expired vs reuse-detected) is a detail
    for server-side audit logging, not for a caller-visible exception type.
    """


class InvalidIdentityError(IdentityApplicationError):
    """A verified `ExternalIdentity` is missing data this module requires
    (e.g. no display name, no usable email) to create or match an account.
    """


class RoleAssignmentError(IdentityApplicationError):
    """A requested role assignment violates identity policy.

    E.g. an attempt to create or promote a user directly to `admin` or
    `service` through a flow that policy restricts to `candidate`
    (Database.md §4.1: roles are "never inferred from OAuth").
    """
