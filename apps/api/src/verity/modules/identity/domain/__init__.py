"""Identity module — domain layer.

Framework-free entities, value objects, and invariants (FolderStructure.md
§2). `models.py` in this package currently also holds the SQLAlchemy 2.0
async ORM mapping for `User`, on explicit instruction for Task 2.1 Part B;
see the deviation note at the top of `models.py` for why that diverges
from TechStack.md §3's persistence-adapter boundary.
"""

from verity.modules.identity.domain.models import User, UserRole, UserStatus

__all__ = ["User", "UserRole", "UserStatus"]