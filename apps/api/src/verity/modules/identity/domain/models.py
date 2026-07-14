"""Identity module — domain entities.

Deviation note: TechStack.md §3 states SQLAlchemy models stay internal to
the persistence adapter, and FolderStructure.md §2 states domain/ does not
import SQLAlchemy. This file is placed here on explicit, specific
instruction (exact path + "SQLAlchemy 2.0 async ORM model") for Task 2.1
Part B. Flagged as a documented deviation from TechStack.md §3, not a
silent substitution — a future refactor can move the mapped class to
adapters/ and leave only a framework-free entity/enums here without
touching the migration below, since Alembic's revision hand-writes its DDL
rather than importing this class.

Database.md §4.1 users columns: id, email_lookup_hash, email_ciphertext,
display_name, role, status. Roles are candidate, support, admin, or
service and are never inferred from OAuth — this model does not enforce
that; it is an application-layer policy applied wherever a User is
created (added in a later task).

Database.md does not enumerate `status` values. ACTIVE / SUSPENDED /
PENDING_DELETION / DELETED are inferred from the account-deletion workflow
in Database.md §8 ("Deletion immediately revokes access, then
asynchronously erases or anonymizes data") — flagged as an assumption for
review, not spec text.
"""

from __future__ import annotations

import enum
import secrets
import time
import uuid

from sqlalchemy import Enum as SAEnum
from sqlalchemy import String, Text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from verity.db.base import Base, TimestampMixin


def generate_uuid7() -> uuid.UUID:
    """Generate a time-sortable UUIDv7 (RFC 9562) using only the stdlib.

    Placed here rather than in a shared `db`/`core` location because Part B
    of Task 2.1 is scoped to exactly six files and does not include editing
    `db/base.py`. Belongs in a shared location once that file is next
    touched, so every future table's primary key adopts the same generator
    instead of duplicating it.

    Bit layout (128 bits total, big-endian):
        48 bits  unix_ts_ms
         4 bits  version (0111)
        12 bits  rand_a
         2 bits  variant (10)
        62 bits  rand_b
    """
    unix_ts_ms = time.time_ns() // 1_000_000
    rand_a = secrets.randbits(12)
    rand_b = secrets.randbits(62)

    value = unix_ts_ms << 80
    value |= 0x7 << 76
    value |= rand_a << 64
    value |= 0b10 << 62
    value |= rand_b

    return uuid.UUID(int=value)


class UserRole(str, enum.Enum):
    """Database.md §4.1: "Roles are candidate, support, admin, or service
    and never inferred from OAuth."
    """

    CANDIDATE = "candidate"
    SUPPORT = "support"
    ADMIN = "admin"
    SERVICE = "service"


class UserStatus(str, enum.Enum):
    """Account lifecycle status.

    Not enumerated in Database.md; inferred from the deletion/anonymization
    workflow described in Database.md §8. Revisit if the eventual
    `data_subject_requests` implementation needs a different vocabulary.
    """

    ACTIVE = "active"
    SUSPENDED = "suspended"
    PENDING_DELETION = "pending_deletion"
    DELETED = "deleted"


class User(Base, TimestampMixin):
    """Root identity (Database.md §4.1).

    The displayable email is never stored in plaintext: `email_ciphertext`
    holds the Fernet-encrypted value (`verity.core.crypto.encrypt_email`,
    Part A) and `email_lookup_hash` holds a keyed, non-reversible
    HMAC-SHA256 hash (`verity.core.crypto.hash_email`, Part A) used only
    for uniqueness/lookup. Both are populated by a repository added in a
    later task — this model only declares the columns.
    """

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=generate_uuid7,
    )

    email_lookup_hash: Mapped[str] = mapped_column(
        String(64),  # HMAC-SHA256 hex digest is always 64 characters
        unique=True,
        nullable=False,
    )

    email_ciphertext: Mapped[str] = mapped_column(
        Text(),  # Fernet tokens are variable-length base64url
        nullable=False,
    )

    display_name: Mapped[str] = mapped_column(String(255), nullable=False)

    role: Mapped[UserRole] = mapped_column(
        SAEnum(
            UserRole,
            name="user_role",
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        nullable=False,
        default=UserRole.CANDIDATE,
        server_default=UserRole.CANDIDATE.value,
    )

    status: Mapped[UserStatus] = mapped_column(
        SAEnum(
            UserStatus,
            name="user_status",
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        nullable=False,
        default=UserStatus.ACTIVE,
        server_default=UserStatus.ACTIVE.value,
    )

    def __repr__(self) -> str:
        # Deliberately excludes email_ciphertext/email_lookup_hash — even
        # though neither is plaintext, repr() output tends to end up in
        # logs/tracebacks and should carry the minimum necessary
        # (Architecture.md §7).
        return f"User(id={self.id!r}, role={self.role!r}, status={self.status!r})"