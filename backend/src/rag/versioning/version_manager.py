"""
Knowledge Base Version Manager.

Manages versioning, snapshots, and change tracking for the knowledge base.
Enables reproducible research by tracking document additions, modifications,
and deletions over time.
"""

import hashlib
import json
import shutil
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Optional
import uuid

from loguru import logger


class ChangeType(str, Enum):
    """Types of changes to the knowledge base."""
    ADD = "add"
    UPDATE = "update"
    DELETE = "delete"
    BULK_ADD = "bulk_add"
    BULK_DELETE = "bulk_delete"
    RESTORE = "restore"
    RESET = "reset"


@dataclass
class ChangeRecord:
    """Record of a single change to the knowledge base."""
    change_id: str
    change_type: ChangeType
    timestamp: datetime
    doc_id: Optional[str] = None
    doc_ids: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)
    user: str = "system"
    description: str = ""

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "change_id": self.change_id,
            "change_type": self.change_type.value,
            "timestamp": self.timestamp.isoformat(),
            "doc_id": self.doc_id,
            "doc_ids": self.doc_ids,
            "metadata": self.metadata,
            "user": self.user,
            "description": self.description,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ChangeRecord":
        """Create from dictionary."""
        return cls(
            change_id=data["change_id"],
            change_type=ChangeType(data["change_type"]),
            timestamp=datetime.fromisoformat(data["timestamp"]),
            doc_id=data.get("doc_id"),
            doc_ids=data.get("doc_ids", []),
            metadata=data.get("metadata", {}),
            user=data.get("user", "system"),
            description=data.get("description", ""),
        )


@dataclass
class KBVersion:
    """Represents a version of the knowledge base."""
    version_id: str
    version_number: int
    name: str
    description: str
    created_at: datetime
    created_by: str = "system"
    document_count: int = 0
    hash: str = ""
    parent_version: Optional[str] = None
    tags: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "version_id": self.version_id,
            "version_number": self.version_number,
            "name": self.name,
            "description": self.description,
            "created_at": self.created_at.isoformat(),
            "created_by": self.created_by,
            "document_count": self.document_count,
            "hash": self.hash,
            "parent_version": self.parent_version,
            "tags": self.tags,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "KBVersion":
        """Create from dictionary."""
        return cls(
            version_id=data["version_id"],
            version_number=data["version_number"],
            name=data["name"],
            description=data.get("description", ""),
            created_at=datetime.fromisoformat(data["created_at"]),
            created_by=data.get("created_by", "system"),
            document_count=data.get("document_count", 0),
            hash=data.get("hash", ""),
            parent_version=data.get("parent_version"),
            tags=data.get("tags", []),
            metadata=data.get("metadata", {}),
        )


@dataclass
class VersionSnapshot:
    """Complete snapshot of the knowledge base at a point in time."""
    version: KBVersion
    documents: list[dict]  # Document metadata (not full content to save space)
    change_log: list[ChangeRecord]

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "version": self.version.to_dict(),
            "documents": self.documents,
            "change_log": [c.to_dict() for c in self.change_log],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "VersionSnapshot":
        """Create from dictionary."""
        return cls(
            version=KBVersion.from_dict(data["version"]),
            documents=data.get("documents", []),
            change_log=[ChangeRecord.from_dict(c) for c in data.get("change_log", [])],
        )


class VersionManager:
    """
    Manages knowledge base versioning.

    Features:
    - Version creation and tracking
    - Change logging
    - Snapshot creation and restoration
    - Version comparison (diff)
    - Rollback capabilities
    """

    def __init__(self, data_dir: Path = None):
        """
        Initialize the version manager.

        Args:
            data_dir: Directory for version data storage
        """
        self.data_dir = data_dir or Path("data/kb_versions")
        self.data_dir.mkdir(parents=True, exist_ok=True)

        self.versions_dir = self.data_dir / "versions"
        self.versions_dir.mkdir(exist_ok=True)

        self.snapshots_dir = self.data_dir / "snapshots"
        self.snapshots_dir.mkdir(exist_ok=True)

        # Load existing state
        self._versions: dict[str, KBVersion] = {}
        self._change_log: list[ChangeRecord] = []
        self._current_version: Optional[str] = None
        self._version_counter = 0

        self._load_state()

        logger.info(f"VersionManager initialized: {len(self._versions)} versions loaded")

    def _load_state(self) -> None:
        """Load persisted state."""
        state_file = self.data_dir / "state.json"
        if state_file.exists():
            with open(state_file) as f:
                data = json.load(f)

            self._version_counter = data.get("version_counter", 0)
            self._current_version = data.get("current_version")

            # Load versions
            for v_data in data.get("versions", []):
                version = KBVersion.from_dict(v_data)
                self._versions[version.version_id] = version

            # Load change log (last 1000 entries)
            for c_data in data.get("change_log", [])[-1000:]:
                self._change_log.append(ChangeRecord.from_dict(c_data))

    def _save_state(self) -> None:
        """Persist current state."""
        state = {
            "version_counter": self._version_counter,
            "current_version": self._current_version,
            "versions": [v.to_dict() for v in self._versions.values()],
            "change_log": [c.to_dict() for c in self._change_log[-1000:]],
        }

        state_file = self.data_dir / "state.json"
        with open(state_file, "w") as f:
            json.dump(state, f, indent=2)

    def create_version(
        self,
        name: str,
        description: str = "",
        created_by: str = "system",
        document_hashes: list[str] = None,
        tags: list[str] = None,
    ) -> KBVersion:
        """
        Create a new version of the knowledge base.

        Args:
            name: Version name (e.g., "v1.0", "sprint-7-release")
            description: Version description
            created_by: User/system creating the version
            document_hashes: List of document content hashes for integrity
            tags: Version tags for categorization

        Returns:
            Created version
        """
        self._version_counter += 1

        # Generate version hash
        hash_content = f"{name}:{self._version_counter}:{datetime.utcnow().isoformat()}"
        if document_hashes:
            hash_content += ":" + ":".join(sorted(document_hashes))
        version_hash = hashlib.sha256(hash_content.encode()).hexdigest()[:16]

        version = KBVersion(
            version_id=f"v{self._version_counter}-{uuid.uuid4().hex[:8]}",
            version_number=self._version_counter,
            name=name,
            description=description,
            created_at=datetime.utcnow(),
            created_by=created_by,
            document_count=len(document_hashes) if document_hashes else 0,
            hash=version_hash,
            parent_version=self._current_version,
            tags=tags or [],
        )

        self._versions[version.version_id] = version
        self._current_version = version.version_id

        # Record change
        self._record_change(
            ChangeType.ADD,
            description=f"Created version: {name}",
            metadata={"version_id": version.version_id},
        )

        self._save_state()
        logger.info(f"Created KB version: {version.version_id} ({name})")

        return version

    def create_snapshot(
        self,
        documents: list[dict],
        name: str = None,
        description: str = "",
    ) -> VersionSnapshot:
        """
        Create a complete snapshot of the current knowledge base.

        Args:
            documents: List of document metadata to snapshot
            name: Optional snapshot name
            description: Snapshot description

        Returns:
            Created snapshot
        """
        # Create version if name provided, otherwise use current
        if name:
            version = self.create_version(
                name=name,
                description=description,
                document_hashes=[d.get("hash", d.get("doc_id", "")) for d in documents],
            )
        else:
            version = self.get_current_version()
            if not version:
                version = self.create_version(
                    name=f"snapshot-{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}",
                    description=description,
                    document_hashes=[d.get("hash", d.get("doc_id", "")) for d in documents],
                )

        # Update document count
        version.document_count = len(documents)

        # Get recent changes for this snapshot
        recent_changes = self._change_log[-100:]

        snapshot = VersionSnapshot(
            version=version,
            documents=documents,
            change_log=recent_changes,
        )

        # Save snapshot
        snapshot_file = self.snapshots_dir / f"{version.version_id}.json"
        with open(snapshot_file, "w") as f:
            json.dump(snapshot.to_dict(), f, indent=2)

        logger.info(f"Created snapshot: {version.version_id} ({len(documents)} documents)")

        return snapshot

    def get_snapshot(self, version_id: str) -> Optional[VersionSnapshot]:
        """
        Retrieve a snapshot by version ID.

        Args:
            version_id: Version ID to retrieve

        Returns:
            Snapshot if found
        """
        snapshot_file = self.snapshots_dir / f"{version_id}.json"
        if not snapshot_file.exists():
            return None

        with open(snapshot_file) as f:
            data = json.load(f)

        return VersionSnapshot.from_dict(data)

    def list_versions(
        self,
        limit: int = 50,
        tags: list[str] = None,
    ) -> list[KBVersion]:
        """
        List all versions.

        Args:
            limit: Maximum versions to return
            tags: Filter by tags

        Returns:
            List of versions (newest first)
        """
        versions = list(self._versions.values())

        # Filter by tags if provided
        if tags:
            versions = [v for v in versions if any(t in v.tags for t in tags)]

        # Sort by version number (descending)
        versions.sort(key=lambda v: v.version_number, reverse=True)

        return versions[:limit]

    def get_version(self, version_id: str) -> Optional[KBVersion]:
        """Get a specific version."""
        return self._versions.get(version_id)

    def get_current_version(self) -> Optional[KBVersion]:
        """Get the current active version."""
        if self._current_version:
            return self._versions.get(self._current_version)
        return None

    def set_current_version(self, version_id: str) -> bool:
        """
        Set the current active version.

        Args:
            version_id: Version to set as current

        Returns:
            True if successful
        """
        if version_id not in self._versions:
            return False

        old_version = self._current_version
        self._current_version = version_id

        self._record_change(
            ChangeType.RESTORE,
            description=f"Changed current version from {old_version} to {version_id}",
            metadata={"old_version": old_version, "new_version": version_id},
        )

        self._save_state()
        return True

    def diff_versions(
        self,
        version_a: str,
        version_b: str,
    ) -> dict:
        """
        Compare two versions and return differences.

        Args:
            version_a: First version ID
            version_b: Second version ID

        Returns:
            Dictionary describing differences
        """
        snapshot_a = self.get_snapshot(version_a)
        snapshot_b = self.get_snapshot(version_b)

        if not snapshot_a or not snapshot_b:
            return {"error": "One or both versions not found"}

        # Get document sets
        docs_a = {d.get("doc_id"): d for d in snapshot_a.documents}
        docs_b = {d.get("doc_id"): d for d in snapshot_b.documents}

        ids_a = set(docs_a.keys())
        ids_b = set(docs_b.keys())

        added = ids_b - ids_a
        removed = ids_a - ids_b
        common = ids_a & ids_b

        # Check for modifications in common documents
        modified = []
        for doc_id in common:
            if docs_a[doc_id].get("hash") != docs_b[doc_id].get("hash"):
                modified.append(doc_id)

        return {
            "version_a": version_a,
            "version_b": version_b,
            "documents_added": list(added),
            "documents_removed": list(removed),
            "documents_modified": modified,
            "added_count": len(added),
            "removed_count": len(removed),
            "modified_count": len(modified),
            "total_a": len(docs_a),
            "total_b": len(docs_b),
        }

    def record_document_change(
        self,
        change_type: ChangeType,
        doc_id: str = None,
        doc_ids: list[str] = None,
        metadata: dict = None,
        user: str = "system",
        description: str = "",
    ) -> ChangeRecord:
        """
        Record a document change to the audit log.

        Args:
            change_type: Type of change
            doc_id: Single document ID (for ADD/UPDATE/DELETE)
            doc_ids: Multiple document IDs (for BULK operations)
            metadata: Additional metadata
            user: User making the change
            description: Change description

        Returns:
            Created change record
        """
        return self._record_change(
            change_type=change_type,
            doc_id=doc_id,
            doc_ids=doc_ids or [],
            metadata=metadata or {},
            user=user,
            description=description,
        )

    def record_change(
        self,
        change_type: ChangeType,
        doc_id: str = None,
        doc_ids: list[str] = None,
        metadata: dict = None,
        user: str = "system",
        description: str = "",
    ) -> ChangeRecord:
        """
        Record a change to the knowledge base. Public API for external change tracking.

        This is an alias for record_document_change() for API consistency.

        Args:
            change_type: Type of change
            doc_id: Single document ID (for ADD/UPDATE/DELETE)
            doc_ids: Multiple document IDs (for BULK operations)
            metadata: Additional metadata
            user: User making the change
            description: Change description

        Returns:
            Created change record
        """
        return self._record_change(
            change_type=change_type,
            doc_id=doc_id,
            doc_ids=doc_ids or [],
            metadata=metadata or {},
            user=user,
            description=description,
        )

    def _record_change(
        self,
        change_type: ChangeType,
        doc_id: str = None,
        doc_ids: list[str] = None,
        metadata: dict = None,
        user: str = "system",
        description: str = "",
    ) -> ChangeRecord:
        """Internal method to record changes."""
        record = ChangeRecord(
            change_id=f"chg-{uuid.uuid4().hex[:12]}",
            change_type=change_type,
            timestamp=datetime.utcnow(),
            doc_id=doc_id,
            doc_ids=doc_ids or [],
            metadata=metadata or {},
            user=user,
            description=description,
        )

        self._change_log.append(record)

        # Trim log if too long
        if len(self._change_log) > 10000:
            self._change_log = self._change_log[-5000:]

        return record

    def get_change_log(
        self,
        limit: int = 100,
        change_type: ChangeType = None,
        since: datetime = None,
    ) -> list[ChangeRecord]:
        """
        Get recent changes from the audit log.

        Args:
            limit: Maximum changes to return
            change_type: Filter by change type
            since: Filter changes since this time

        Returns:
            List of change records (newest first)
        """
        changes = self._change_log.copy()

        if change_type:
            changes = [c for c in changes if c.change_type == change_type]

        if since:
            changes = [c for c in changes if c.timestamp >= since]

        # Sort by timestamp descending
        changes.sort(key=lambda c: c.timestamp, reverse=True)

        return changes[:limit]

    def get_document_history(self, doc_id: str) -> list[ChangeRecord]:
        """
        Get change history for a specific document.

        Args:
            doc_id: Document ID to get history for

        Returns:
            List of changes involving this document
        """
        return [
            c for c in self._change_log
            if c.doc_id == doc_id or doc_id in c.doc_ids
        ]

    def get_stats(self) -> dict:
        """Get versioning statistics."""
        return {
            "total_versions": len(self._versions),
            "current_version": self._current_version,
            "version_counter": self._version_counter,
            "change_log_size": len(self._change_log),
            "snapshots_count": len(list(self.snapshots_dir.glob("*.json"))),
            "data_dir": str(self.data_dir),
        }

    def cleanup_old_snapshots(self, keep_count: int = 10) -> int:
        """
        Clean up old snapshots keeping only the most recent.

        Args:
            keep_count: Number of snapshots to keep

        Returns:
            Number of snapshots deleted
        """
        snapshots = list(self.snapshots_dir.glob("*.json"))

        if len(snapshots) <= keep_count:
            return 0

        # Sort by modification time
        snapshots.sort(key=lambda p: p.stat().st_mtime, reverse=True)

        deleted = 0
        for snapshot in snapshots[keep_count:]:
            try:
                snapshot.unlink()
                deleted += 1
            except Exception as e:
                logger.warning(f"Failed to delete snapshot {snapshot}: {e}")

        logger.info(f"Cleaned up {deleted} old snapshots")
        return deleted


# Global instance
_version_manager: Optional[VersionManager] = None


def get_version_manager() -> VersionManager:
    """Get or create the global version manager instance."""
    global _version_manager
    if _version_manager is None:
        _version_manager = VersionManager()
    return _version_manager
