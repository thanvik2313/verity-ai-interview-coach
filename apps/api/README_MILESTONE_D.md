# Sprint 2 — Milestone D: Identity Application Layer

Scope actually implemented: the identity module's `application/` layer —
use-case orchestration (`services.py`), the repository ports it depends on
(`interfaces.py`), internal application-level value objects (`types.py`),
business-policy validation (`validators.py`), and a use-case-level
exception hierarchy (`exceptions.py`). No repositories, routes, JWT
dependencies, OAuth, or frontend code were added.

## Purpose

This layer holds the identity module's actual business logic — "find or
create a user for a verified external identity and issue tokens," "rotate
a refresh session," "log out" — independent of both persistence (no
SQLAlchemy queries) and transport (no FastAPI). Per FolderStructure.md
§2's stated shape, route handlers will call these services once they
exist, and these services depend only on `interfaces.py`'s ports —
concrete SQLAlchemy repositories and the Google OAuth adapter, both added
in a later task, are the only pieces that make this layer reachable from a
real HTTP request.

## Files created

| File | Purpose |
| --- | --- |
| `apps/api/src/verity/modules/identity/application/types.py` | Internal value objects services actually use: `ExternalIdentity` (a verified, provider-agnostic identity handed in by a future OAuth adapter), `NewUserProfile`, `IssuedTokenPair`, `StoredRefreshSession` (the port-level shape of a not-yet-modeled `auth_sessions` row), `AuthenticatedUser`. |
| `apps/api/src/verity/modules/identity/application/interfaces.py` | `UserRepository` and `RefreshSessionRepository` — `typing.Protocol` ports with no concrete implementation, satisfying "do not implement repositories yet." |
| `apps/api/src/verity/modules/identity/application/exceptions.py` | `IdentityApplicationError` and six use-case-level subclasses (`UserNotFoundError`, `AccountNotActiveError`, `InvalidSessionError`, `InvalidIdentityError`, `RoleAssignmentError`, `DuplicateIdentityError`), extending `core.errors.VerityError`. |
| `apps/api/src/verity/modules/identity/application/validators.py` | `build_new_user_profile` (hardcodes `role=candidate` for every OAuth-derived signup — Database.md §4.1's "never inferred from OAuth"); `ensure_role_assignment_allowed` (forward-looking guard restricting `admin`/`service` assignment to an existing admin). |
| `apps/api/src/verity/modules/identity/application/services.py` | `IdentitySessionService` (find-or-create-then-issue-tokens, refresh/rotate, logout, logout-all) and `IdentityQueryService` (`get_current_user` → `UserRead`). Built entirely against `interfaces.py`'s ports plus `core.security`/`core.crypto`. |
| `apps/api/src/verity/modules/identity/application/__init__.py` | Package init; re-exports the module's public surface. |

## Assumptions made

- **`ExternalIdentity` is provider-agnostic** (`provider`, `provider_subject`, `email`, `display_name`) rather than Google-specific. API.md/Architecture.md describe the *result* of OAuth (a verified identity) without dictating this exact shape; this is a reasonable inferred contract for what an OAuth adapter, built in a later task, will need to hand the application layer.
- **`RefreshSessionRepository`'s shape is inferred**, not copied from a migration — no `auth_sessions` ORM model or migration exists yet (Milestone B covered only `users`). The port's fields (`user_id`, `token_hash`, `expires_at`) are the minimum Database.md's narrative description of session rotation implies; the eventual model/migration is the authority, and this port may need a small adjustment once it exists.
- **Session expiry is checked in the application layer**, not delegated to the repository (`refresh_session` compares `stored.expires_at` against `datetime.now(UTC)` itself) — kept here rather than in a not-yet-existing repository so the business rule ("an expired session cannot be refreshed") is visible and testable independent of any specific database.
- **Refresh-token mismatch is *not* wrapped** in an application-layer exception — `core.errors.InvalidRefreshTokenError` is allowed to propagate as-is from `verity.core.security.verify_refresh_token`, since it is already a typed `AuthenticationError` that Milestone A's `verity.main.app` exception handlers map to 401 identically to any application-layer error. Wrapping it would add a layer of indirection without adding caller-visible information.
- **`DuplicateIdentityError` is defined but never raised** in this milestone — it exists for a future repository implementation to raise after translating a unique-constraint violation on `users.email_lookup_hash` under a concurrent-signup race. Flagged in its own docstring so it doesn't read as dead code.
- **`modules/identity/__init__.py` was intentionally left unmodified** even though its docstring (written during Milestones B/C) doesn't yet mention `application/`. It wasn't in this milestone's file list, and the instructions were explicit about creating only the listed files — the docstring becoming slightly stale is a known, accepted side effect, not an oversight.

## Verification performed

- `python -m py_compile` on every new file — pass.
- `ruff check` across all of `src` (23 files total) — pass, zero findings.
- `mypy --explicit-package-bases` across `src` and `migrations` (23 source files) — pass, zero findings.
- Static import audit confirming zero `fastapi` or `sqlalchemy` imports anywhere under `application/`, and that every cross-module import resolves only to `verity.core.*`, `verity.modules.identity.domain.*`, `verity.modules.identity.contracts.*`, or another `application/` file.
- A full behavioral run against real in-memory fakes that satisfy `UserRepository`/`RefreshSessionRepository` structurally (no inheritance, matching the `Protocol` contract), covering: first-login find-or-create with role forced to `candidate`; idempotent second login; `UserRead` projection excluding both email fields; refresh/rotation; stale-refresh-token reuse rejection; unknown-session rejection; expired-session rejection; suspended-account rejection; single-session logout; logout-all; malformed-identity rejection; unknown-user query rejection; and the role-assignment policy guard in both the rejecting and allowing direction. All checks passed.

## Not implemented (explicitly out of scope for Milestone D)

Concrete repositories/adapters, authentication routes, JWT dependencies
(`get_current_user` FastAPI dependency), Google OAuth, frontend code, and
AI features.
