"""Typed exception hierarchy for the Verity API core layer.

Domain and application code raises these instead of leaking library-specific
exceptions (jwt.*, cryptography.*, pydantic.*) across module boundaries.
FastAPI exception handlers, registered in `verity.main.app`, translate them
into safe HTTP responses without exposing internals (Architecture.md §7 —
error payloads never include tokens, keys, or raw candidate content).
"""

from __future__ import annotations


class VerityError(Exception):
    """Base class for all application-raised errors."""


class ConfigurationError(VerityError):
    """Raised when required configuration is missing or invalid.

    This is a startup-time/programmer error, not a per-request condition —
    it should generally cause the process to fail fast rather than be
    caught per-request.
    """


class AuthenticationError(VerityError):
    """Base class for errors that mean 'this caller is not authenticated'.

    Callers should treat any subclass as equivalent to HTTP 401 and must not
    branch user-visible behavior on the specific subclass, to avoid leaking
    which part of a token was wrong (Architecture.md §7).
    """


class InvalidTokenError(AuthenticationError):
    """A JWT failed signature, structure, issuer, or audience validation."""


class TokenExpiredError(AuthenticationError):
    """A JWT was structurally valid but is past its expiry."""


class InvalidRefreshTokenError(AuthenticationError):
    """An opaque refresh token failed hash comparison."""


class EncryptionError(VerityError):
    """Raised when encrypting or decrypting sensitive field data fails."""


class DecryptionError(EncryptionError):
    """Raised specifically when ciphertext cannot be decrypted or is invalid.

    Kept distinct from EncryptionError so callers can tell a corrupt/tampered
    value apart from a misconfigured key, without exposing that distinction
    to end users.
    """
