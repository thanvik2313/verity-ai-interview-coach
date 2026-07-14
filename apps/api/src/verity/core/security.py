"""JWT access-token and refresh-token utilities.

Scope of this module (Task 2.1, Part A):
  - Issue and verify short-lived, signed JWT access tokens.
  - Generate opaque, high-entropy refresh tokens and hash them for storage.

Out of scope here (later tasks): persisting/rotating refresh sessions in
`auth_sessions`, revocation/token-family compromise handling, and the
OAuth flow that actually authenticates a user. Those consume the functions
below; this module has no database or HTTP dependency of its own, in
keeping with the ports-and-adapters rule that core/ holds framework-free
security primitives (FolderStructure.md §1-2).

Access tokens are Secure, HttpOnly, SameSite cookies set by the API host —
never returned to JavaScript and never stored in browser local storage
(Architecture.md §7). This module only produces/consumes the token string;
cookie handling belongs to the route layer added in a later task.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import jwt

from verity.core.config import Settings
from verity.core.errors import InvalidRefreshTokenError, InvalidTokenError, TokenExpiredError

ACCESS_TOKEN_TYPE = "access"  # noqa: S105 - a type discriminator, not a credential


@dataclass(frozen=True, slots=True)
class AccessTokenClaims:
    """Decoded, validated claims from a Verity access token.

    A plain dataclass rather than a Pydantic model: this is an internal
    security-layer value object, not a wire contract. The identity module's
    contracts/ layer (added in a later task) maps this to its own DTOs
    where it needs to cross the API boundary.
    """

    subject: str
    """The authenticated user's id (users.id), as a string."""

    role: str
    """The user's role at the time the token was issued (see users.role)."""

    session_id: str
    """Correlates this access token to its refresh session (auth_sessions.token_family_id).

    Populated by the OAuth/session-issuance code added in a later task; this
    module treats it as an opaque required claim.
    """

    token_id: str
    """Unique id for this specific token (JWT `jti`); useful for tracing/audit."""

    issued_at: datetime
    expires_at: datetime


def create_access_token(
    *,
    subject: str,
    role: str,
    session_id: str,
    settings: Settings,
    now: datetime | None = None,
) -> str:
    """Issue a signed, short-lived JWT access token.

    Args:
        subject: The user id the token authenticates as.
        role: The user's role at issuance time (candidate, support, admin, service).
        session_id: The refresh-session/token-family id this access token belongs to.
        settings: Application settings (signing key, algorithm, TTL, issuer/audience).
        now: Override for the current time; defaults to real UTC now. Exposed for tests.

    Returns:
        An encoded JWT string. The caller is responsible for transporting it
        as a Secure, HttpOnly, SameSite cookie.
    """
    issued_at = now or datetime.now(UTC)
    expires_at = issued_at + timedelta(seconds=settings.jwt_access_token_ttl_seconds)

    payload = {
        "sub": subject,
        "role": role,
        "sid": session_id,
        "type": ACCESS_TOKEN_TYPE,
        "jti": str(uuid.uuid4()),
        "iss": settings.jwt_issuer,
        "aud": settings.jwt_audience,
        "iat": issued_at,
        "nbf": issued_at,
        "exp": expires_at,
    }

    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str, *, settings: Settings) -> AccessTokenClaims:
    """Verify signature, issuer, audience, and expiry, and return typed claims.

    Raises:
        TokenExpiredError: The token's signature is valid but it has expired.
        InvalidTokenError: Any other validation failure (bad signature,
            wrong issuer/audience, malformed structure, wrong token type,
            missing required claim). Deliberately not distinguished further
            so callers can't be used as an oracle for *why* a token is bad.
    """
    try:
        raw_claims = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
            issuer=settings.jwt_issuer,
            audience=settings.jwt_audience,
            options={"require": ["sub", "role", "sid", "type", "jti", "iat", "exp"]},
        )
    except jwt.ExpiredSignatureError as exc:
        raise TokenExpiredError("Access token has expired.") from exc
    except jwt.InvalidTokenError as exc:
        raise InvalidTokenError("Access token failed validation.") from exc

    if raw_claims.get("type") != ACCESS_TOKEN_TYPE:
        raise InvalidTokenError("Token is not an access token.")

    try:
        return AccessTokenClaims(
            subject=str(raw_claims["sub"]),
            role=str(raw_claims["role"]),
            session_id=str(raw_claims["sid"]),
            token_id=str(raw_claims["jti"]),
            issued_at=datetime.fromtimestamp(raw_claims["iat"], tz=UTC),
            expires_at=datetime.fromtimestamp(raw_claims["exp"], tz=UTC),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise InvalidTokenError("Access token claims are malformed.") from exc


@dataclass(frozen=True, slots=True)
class RefreshToken:
    """A freshly generated refresh token pair.

    `raw_value` is returned to the caller exactly once and transported as a
    Secure, HttpOnly, SameSite cookie. Only `token_hash` is ever persisted
    (auth_sessions.refresh_token_hash) — the raw value is never stored or
    logged (Architecture.md §7, Database.md §4.1).
    """

    raw_value: str
    token_hash: str


def generate_refresh_token(*, settings: Settings) -> RefreshToken:
    """Generate a new high-entropy opaque refresh token and its storage hash."""
    raw_value = secrets.token_urlsafe(settings.refresh_token_bytes)
    return RefreshToken(raw_value=raw_value, token_hash=hash_refresh_token(raw_value))


def hash_refresh_token(raw_value: str) -> str:
    """Deterministically hash a raw refresh token for at-rest storage/lookup.

    SHA-256 is sufficient here (not a password hash): the input is a
    server-generated high-entropy random token, not a user-chosen secret, so
    there is no brute-force-by-guessing concern to justify a slow KDF.
    """
    return hashlib.sha256(raw_value.encode("utf-8")).hexdigest()


def verify_refresh_token(*, raw_value: str, expected_hash: str) -> None:
    """Constant-time-compare a presented raw refresh token against its stored hash.

    Raises:
        InvalidRefreshTokenError: The token does not match. Callers that also
            need reuse-detection/token-family revocation implement that in
            the session-persistence layer added in a later task; this
            function only checks the value itself.
    """
    computed_hash = hash_refresh_token(raw_value)
    if not hmac.compare_digest(computed_hash, expected_hash):
        raise InvalidRefreshTokenError("Refresh token does not match.")
