"""Encryption and keyed hashing helpers for sensitive user PII.

Database.md §4.1 specifies the `users` table stores email two ways:
  - `email_ciphertext`: the displayable email, encrypted at rest.
  - `email_lookup_hash`: a keyed, non-reversible hash used only for
    uniqueness enforcement and lookup — never for display.

This module provides both primitives. It does not touch the database; the
identity module's `User` model and repository (added in a later task) call
these functions when writing/reading the email fields.
"""

from __future__ import annotations

import hashlib
import hmac

from cryptography.fernet import Fernet, InvalidToken

from verity.core.errors import DecryptionError, EncryptionError

_EMAIL_HASH_CONTEXT = b"verity:email-lookup:v1"
"""Domain-separation prefix. If another field ever needs a keyed hash with the
same secret, this prevents a hash collision across use cases."""


def normalize_email(email: str) -> str:
    """Canonicalize an email address before it is encrypted or hashed.

    Ensures `Person@Example.com` and `person@example.com` collide correctly
    on `email_lookup_hash` (Database.md: "keyed normalized-email lookup hash
    is unique"). Kept intentionally simple (case-fold + trim); it does not
    attempt provider-specific canonicalization (e.g. Gmail dot-stripping).
    """
    return email.strip().casefold()


def hash_email(email: str, *, hash_key: str) -> str:
    """Compute the keyed, non-reversible lookup hash for a normalized email.

    Uses HMAC-SHA256 keyed with `VERITY_EMAIL_HASH_KEY` so the hash cannot be
    reproduced, and email addresses cannot be dictionary-attacked, without
    that key.
    """
    normalized = normalize_email(email)
    digest = hmac.new(
        key=hash_key.encode("utf-8"),
        msg=_EMAIL_HASH_CONTEXT + normalized.encode("utf-8"),
        digestmod=hashlib.sha256,
    )
    return digest.hexdigest()


def _fernet(encryption_key: str) -> Fernet:
    try:
        return Fernet(encryption_key.encode("utf-8"))
    except (ValueError, TypeError) as exc:
        raise EncryptionError(
            "VERITY_EMAIL_ENCRYPTION_KEY is not a valid Fernet key. Generate one with "
            "`python -c \"from cryptography.fernet import Fernet; "
            'print(Fernet.generate_key().decode())"`.'
        ) from exc


def encrypt_email(email: str, *, encryption_key: str) -> str:
    """Encrypt a (already-normalized-by-caller-if-desired) email for storage.

    The displayable email is stored as-provided inside the ciphertext — this
    function does not itself normalize, so callers control whether they
    preserve the user's original casing for display while relying on
    `hash_email` (which does normalize) for uniqueness.
    """
    fernet = _fernet(encryption_key)
    try:
        token = fernet.encrypt(email.encode("utf-8"))
    except Exception as exc:  # noqa: BLE001 - re-raised as a typed encryption error
        raise EncryptionError("Failed to encrypt email.") from exc
    return token.decode("utf-8")


def decrypt_email(ciphertext: str, *, encryption_key: str) -> str:
    """Decrypt a stored `email_ciphertext` value back to a displayable email.

    Raises:
        DecryptionError: The ciphertext is invalid, was encrypted with a
            different key, or has been tampered with.
    """
    fernet = _fernet(encryption_key)
    try:
        plaintext = fernet.decrypt(ciphertext.encode("utf-8"))
    except InvalidToken as exc:
        raise DecryptionError("Email ciphertext is invalid or was tampered with.") from exc
    except Exception as exc:  # noqa: BLE001 - re-raised as a typed decryption error
        raise DecryptionError("Failed to decrypt email.") from exc
    return plaintext.decode("utf-8")
