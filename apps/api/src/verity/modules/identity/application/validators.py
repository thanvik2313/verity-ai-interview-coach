"""Application-level validation and policy enforcement for the identity module.

Distinct from Pydantic field validation in `contracts/` (Milestone C),
which validates *shape* (e.g. "is this a 1-255 character string?"). These
functions enforce *business* invariants that depend on more than one
field, or on policy that isn't expressible as a Pydantic constraint at
all — most importantly Database.md §4.1's "Roles are candidate, support,
admin, or service and never inferred from OAuth."
"""

from __future__ import annotations

from verity.modules.identity.application.exceptions import (
    InvalidIdentityError,
    RoleAssignmentError,
)
from verity.modules.identity.application.types import ExternalIdentity, NewUserProfile
from verity.modules.identity.domain.models import UserRole


def build_new_user_profile(identity: ExternalIdentity) -> NewUserProfile:
    """Translate a verified external identity into a policy-compliant new
    user profile.

    Enforces Database.md §4.1's "never inferred from OAuth" rule by
    hardcoding `role=UserRole.CANDIDATE` here rather than accepting a role
    from the caller — every account created through this path is a
    candidate account, full stop. A support/admin/service account is
    provisioned some other way, out of this milestone's scope.
    """
    display_name = identity.display_name.strip()
    if not display_name:
        raise InvalidIdentityError(
            "External identity did not include a usable display name."
        )

    email = identity.email.strip()
    if not email or "@" not in email:
        raise InvalidIdentityError(
            "External identity did not include a valid email address."
        )

    return NewUserProfile(email=email, display_name=display_name, role=UserRole.CANDIDATE)


def ensure_role_assignment_allowed(
    *, requested_role: UserRole, actor_role: UserRole | None
) -> None:
    """Guard for any future path that lets a caller request a role
    directly (e.g. an admin console) — not used by the OAuth-derived
    signup path above, which never accepts a role from its input at all.

    Only an existing `admin` may assign `admin` or `service`; nothing may
    assign either to itself or to anyone else without that privilege.
    """
    if requested_role in (UserRole.ADMIN, UserRole.SERVICE) and actor_role != UserRole.ADMIN:
        raise RoleAssignmentError(
            f"Role '{requested_role.value}' can only be assigned by an existing admin."
        )
