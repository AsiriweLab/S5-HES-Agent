"""
Knowledge Base Versioning System.

Provides version control and tracking for the knowledge base:
- Snapshot creation and restoration
- Change tracking and audit logs
- Version diffing
- Rollback capabilities
"""

from src.rag.versioning.version_manager import (
    VersionManager,
    KBVersion,
    VersionSnapshot,
    ChangeType,
    ChangeRecord,
    get_version_manager,
)

__all__ = [
    "VersionManager",
    "KBVersion",
    "VersionSnapshot",
    "ChangeType",
    "ChangeRecord",
    "get_version_manager",
]
