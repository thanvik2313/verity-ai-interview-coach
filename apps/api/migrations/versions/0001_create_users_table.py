"""create users table

Revision ID: 0001
Revises:
Create Date: 2026-07-15

Database.md §4.1 — root identity table. Roles are candidate, support,
admin, or service and are never inferred from OAuth; the displayable email
is encrypted (email_ciphertext) and a separate keyed, normalized-email
lookup hash (email_lookup_hash) enforces uniqueness without storing
plaintext email for lookup.

`status` values (active, suspended, pending_deletion, deleted) are not
enumerated in Database.md; they are inferred from the account-deletion
workflow in §8 — see the assumption note in
verity/modules/identity/domain/models.py.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0001"
down_revision: str | None = None
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None

_USER_ROLE_VALUES = ("candidate", "support", "admin", "service")
_USER_STATUS_VALUES = ("active", "suspended", "pending_deletion", "deleted")

user_role_enum = postgresql.ENUM(*_USER_ROLE_VALUES, name="user_role")
user_status_enum = postgresql.ENUM(*_USER_STATUS_VALUES, name="user_status")


def upgrade() -> None:
    bind = op.get_bind()
    user_role_enum.create(bind, checkfirst=True)
    user_status_enum.create(bind, checkfirst=True)

    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("email_lookup_hash", sa.String(length=64), nullable=False),
        sa.Column("email_ciphertext", sa.Text(), nullable=False),
        sa.Column("display_name", sa.String(length=255), nullable=False),
        sa.Column(
            "role",
            postgresql.ENUM(*_USER_ROLE_VALUES, name="user_role", create_type=False),
            nullable=False,
            server_default="candidate",
        ),
        sa.Column(
            "status",
            postgresql.ENUM(*_USER_STATUS_VALUES, name="user_status", create_type=False),
            nullable=False,
            server_default="active",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("email_lookup_hash", name="uq_users_email_lookup_hash"),
    )


def downgrade() -> None:
    op.drop_table("users")

    bind = op.get_bind()
    user_status_enum.drop(bind, checkfirst=True)
    user_role_enum.drop(bind, checkfirst=True)