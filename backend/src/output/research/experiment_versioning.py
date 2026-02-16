"""
Experiment Versioning System

Git-like version control for smart home simulation experiments.
Enables reproducible research through:
- Configuration snapshots
- Version history with branching
- Provenance metadata tracking
- Comparison tools
"""

import hashlib
import json
import os
import shutil
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Optional
from uuid import uuid4

from pydantic import BaseModel, Field


# =============================================================================
# Enumerations
# =============================================================================


class ExperimentStatus(str, Enum):
    """Status of an experiment."""
    DRAFT = "draft"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    ARCHIVED = "archived"


class VersionType(str, Enum):
    """Type of version change."""
    MAJOR = "major"  # Breaking changes (new home config, different threat set)
    MINOR = "minor"  # Feature additions (new devices, parameters)
    PATCH = "patch"  # Bug fixes, small tweaks


class DiffType(str, Enum):
    """Types of differences between versions."""
    ADDED = "added"
    REMOVED = "removed"
    MODIFIED = "modified"
    UNCHANGED = "unchanged"


# =============================================================================
# Data Models
# =============================================================================


class SemanticVersion(BaseModel):
    """Semantic versioning for experiments."""
    major: int = 1
    minor: int = 0
    patch: int = 0

    def __str__(self) -> str:
        return f"{self.major}.{self.minor}.{self.patch}"

    def bump(self, version_type: VersionType) -> "SemanticVersion":
        """Return a new bumped version."""
        if version_type == VersionType.MAJOR:
            return SemanticVersion(major=self.major + 1, minor=0, patch=0)
        elif version_type == VersionType.MINOR:
            return SemanticVersion(major=self.major, minor=self.minor + 1, patch=0)
        else:  # PATCH
            return SemanticVersion(major=self.major, minor=self.minor, patch=self.patch + 1)

    @classmethod
    def parse(cls, version_str: str) -> "SemanticVersion":
        """Parse version string like '1.2.3'."""
        parts = version_str.split(".")
        return cls(
            major=int(parts[0]) if len(parts) > 0 else 1,
            minor=int(parts[1]) if len(parts) > 1 else 0,
            patch=int(parts[2]) if len(parts) > 2 else 0
        )


class RAGSourceReference(BaseModel):
    """Reference to RAG knowledge base source."""
    doc_id: str
    title: str
    source: str
    category: str
    relevance_score: float
    excerpt: Optional[str] = None
    retrieved_at: datetime = Field(default_factory=datetime.utcnow)


class ProvenanceMetadata(BaseModel):
    """Provenance tracking for research integrity."""
    created_by: str = "system"
    created_at: datetime = Field(default_factory=datetime.utcnow)
    modified_by: Optional[str] = None
    modified_at: Optional[datetime] = None

    # Research context
    research_question: Optional[str] = None
    hypothesis: Optional[str] = None
    methodology_notes: Optional[str] = None

    # RAG sources used
    rag_sources: list[RAGSourceReference] = Field(default_factory=list)

    # Configuration source
    llm_assisted: bool = False
    llm_model: Optional[str] = None
    llm_conversation_id: Optional[str] = None

    # Verification
    verification_passed: bool = False
    verification_timestamp: Optional[datetime] = None
    verification_warnings: list[str] = Field(default_factory=list)


class ConfigurationSnapshot(BaseModel):
    """Complete snapshot of experiment configuration."""
    snapshot_id: str = Field(default_factory=lambda: str(uuid4()))
    created_at: datetime = Field(default_factory=datetime.utcnow)

    # Home configuration
    home_config: dict[str, Any] = Field(default_factory=dict)

    # Simulation parameters
    simulation_params: dict[str, Any] = Field(default_factory=dict)

    # Threat scenarios
    threat_scenarios: list[dict[str, Any]] = Field(default_factory=list)

    # Behavior patterns
    behavior_config: dict[str, Any] = Field(default_factory=dict)

    # Research integrity settings
    research_integrity: dict[str, Any] = Field(default_factory=dict)

    # System info for reproducibility
    system_info: dict[str, Any] = Field(default_factory=dict)

    def compute_hash(self) -> str:
        """Compute content hash for this snapshot."""
        content = json.dumps({
            "home_config": self.home_config,
            "simulation_params": self.simulation_params,
            "threat_scenarios": self.threat_scenarios,
            "behavior_config": self.behavior_config,
        }, sort_keys=True, default=str)
        return hashlib.sha256(content.encode()).hexdigest()[:12]


class ExperimentVersion(BaseModel):
    """A single version of an experiment."""
    version_id: str = Field(default_factory=lambda: str(uuid4()))
    version: SemanticVersion = Field(default_factory=SemanticVersion)

    # Parent tracking for branching
    parent_version_id: Optional[str] = None
    branch_name: str = "main"

    # Configuration
    config_snapshot: ConfigurationSnapshot = Field(default_factory=ConfigurationSnapshot)

    # Metadata
    provenance: ProvenanceMetadata = Field(default_factory=ProvenanceMetadata)

    # Version info
    commit_message: str = "Initial version"
    tags: list[str] = Field(default_factory=list)
    notes: Optional[str] = None

    # Results reference (if experiment was run)
    results_path: Optional[str] = None
    metrics_summary: dict[str, Any] = Field(default_factory=dict)

    def get_content_hash(self) -> str:
        """Get hash of this version's configuration."""
        return self.config_snapshot.compute_hash()


class Experiment(BaseModel):
    """A complete experiment with version history."""
    experiment_id: str = Field(default_factory=lambda: str(uuid4()))
    name: str
    description: Optional[str] = None
    status: ExperimentStatus = ExperimentStatus.DRAFT

    # Version history
    versions: list[ExperimentVersion] = Field(default_factory=list)
    current_version_id: Optional[str] = None

    # Branches
    branches: dict[str, str] = Field(default_factory=lambda: {"main": ""})  # branch -> latest version_id
    current_branch: str = "main"

    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    last_modified: datetime = Field(default_factory=datetime.utcnow)

    # Organization
    tags: list[str] = Field(default_factory=list)
    category: Optional[str] = None

    def get_version(self, version_id: str) -> Optional[ExperimentVersion]:
        """Get a version by ID."""
        for v in self.versions:
            if v.version_id == version_id:
                return v
        return None

    def get_current_version(self) -> Optional[ExperimentVersion]:
        """Get the current version."""
        if self.current_version_id:
            return self.get_version(self.current_version_id)
        return None

    def get_latest_version(self, branch: Optional[str] = None) -> Optional[ExperimentVersion]:
        """Get the latest version in a branch."""
        target_branch = branch or self.current_branch
        version_id = self.branches.get(target_branch)
        if version_id:
            return self.get_version(version_id)
        return None

    def get_version_history(self, branch: Optional[str] = None) -> list[ExperimentVersion]:
        """Get version history for a branch."""
        target_branch = branch or self.current_branch
        return [v for v in self.versions if v.branch_name == target_branch]


class ConfigDiff(BaseModel):
    """Difference between two configurations."""
    field_path: str
    diff_type: DiffType
    old_value: Optional[Any] = None
    new_value: Optional[Any] = None


class VersionComparison(BaseModel):
    """Comparison between two versions."""
    version_a_id: str
    version_b_id: str
    differences: list[ConfigDiff] = Field(default_factory=list)
    summary: dict[str, int] = Field(default_factory=dict)  # {added: N, removed: M, modified: K}


# =============================================================================
# Experiment Versioning Service
# =============================================================================


class ExperimentVersioning:
    """
    Git-like version control for experiments.

    Features:
    - Create and manage experiments
    - Version control with semantic versioning
    - Branching support
    - Configuration snapshots
    - Provenance tracking
    - Comparison tools
    """

    def __init__(self, storage_path: Optional[str] = None):
        """Initialize versioning system."""
        self.storage_path = Path(storage_path or "experiments")
        self.storage_path.mkdir(parents=True, exist_ok=True)

        # In-memory cache
        self._experiments: dict[str, Experiment] = {}

        # Load existing experiments
        self._load_experiments()

    def _load_experiments(self) -> None:
        """Load experiments from storage."""
        for exp_file in self.storage_path.glob("*.json"):
            try:
                with open(exp_file, "r") as f:
                    data = json.load(f)
                    exp = Experiment.model_validate(data)
                    self._experiments[exp.experiment_id] = exp
            except Exception as e:
                print(f"Warning: Failed to load experiment {exp_file}: {e}")

    def _save_experiment(self, experiment: Experiment) -> None:
        """Save experiment to storage."""
        exp_file = self.storage_path / f"{experiment.experiment_id}.json"
        with open(exp_file, "w") as f:
            json.dump(experiment.model_dump(mode="json"), f, indent=2, default=str)

    # -------------------------------------------------------------------------
    # Experiment Management
    # -------------------------------------------------------------------------

    def create_experiment(
        self,
        name: str,
        description: Optional[str] = None,
        initial_config: Optional[ConfigurationSnapshot] = None,
        provenance: Optional[ProvenanceMetadata] = None,
        tags: Optional[list[str]] = None,
        category: Optional[str] = None,
    ) -> Experiment:
        """Create a new experiment."""
        experiment = Experiment(
            name=name,
            description=description,
            tags=tags or [],
            category=category,
        )

        # Create initial version
        initial_version = ExperimentVersion(
            version=SemanticVersion(major=1, minor=0, patch=0),
            config_snapshot=initial_config or ConfigurationSnapshot(),
            provenance=provenance or ProvenanceMetadata(),
            commit_message="Initial experiment creation",
            branch_name="main",
        )

        experiment.versions.append(initial_version)
        experiment.current_version_id = initial_version.version_id
        experiment.branches["main"] = initial_version.version_id

        # Store
        self._experiments[experiment.experiment_id] = experiment
        self._save_experiment(experiment)

        return experiment

    def get_experiment(self, experiment_id: str) -> Optional[Experiment]:
        """Get an experiment by ID."""
        return self._experiments.get(experiment_id)

    def list_experiments(
        self,
        status: Optional[ExperimentStatus] = None,
        category: Optional[str] = None,
        tags: Optional[list[str]] = None,
    ) -> list[Experiment]:
        """List experiments with optional filters."""
        experiments = list(self._experiments.values())

        if status:
            experiments = [e for e in experiments if e.status == status]
        if category:
            experiments = [e for e in experiments if e.category == category]
        if tags:
            experiments = [e for e in experiments if any(t in e.tags for t in tags)]

        return sorted(experiments, key=lambda e: e.last_modified, reverse=True)

    def delete_experiment(self, experiment_id: str) -> bool:
        """Delete an experiment."""
        if experiment_id in self._experiments:
            del self._experiments[experiment_id]
            exp_file = self.storage_path / f"{experiment_id}.json"
            if exp_file.exists():
                exp_file.unlink()
            return True
        return False

    def update_experiment(
        self,
        experiment_id: str,
        name: Optional[str] = None,
        description: Optional[str] = None,
        status: Optional[ExperimentStatus] = None,
        tags: Optional[list[str]] = None,
        category: Optional[str] = None,
    ) -> Optional[Experiment]:
        """Update experiment metadata."""
        experiment = self._experiments.get(experiment_id)
        if not experiment:
            return None

        if name is not None:
            experiment.name = name
        if description is not None:
            experiment.description = description
        if status is not None:
            experiment.status = status
        if tags is not None:
            experiment.tags = tags
        if category is not None:
            experiment.category = category

        experiment.last_modified = datetime.utcnow()
        self._save_experiment(experiment)

        return experiment

    # -------------------------------------------------------------------------
    # Version Control
    # -------------------------------------------------------------------------

    def commit(
        self,
        experiment_id: str,
        config_snapshot: ConfigurationSnapshot,
        message: str,
        version_type: VersionType = VersionType.PATCH,
        provenance: Optional[ProvenanceMetadata] = None,
        tags: Optional[list[str]] = None,
        notes: Optional[str] = None,
    ) -> Optional[ExperimentVersion]:
        """
        Commit a new version of the experiment.

        Similar to 'git commit'.
        """
        experiment = self._experiments.get(experiment_id)
        if not experiment:
            return None

        # Get current version for parent reference
        current = experiment.get_current_version()

        # Bump version
        new_version = current.version.bump(version_type) if current else SemanticVersion()

        # Create new version
        new_exp_version = ExperimentVersion(
            version=new_version,
            parent_version_id=current.version_id if current else None,
            branch_name=experiment.current_branch,
            config_snapshot=config_snapshot,
            provenance=provenance or ProvenanceMetadata(),
            commit_message=message,
            tags=tags or [],
            notes=notes,
        )

        # Update experiment
        experiment.versions.append(new_exp_version)
        experiment.current_version_id = new_exp_version.version_id
        experiment.branches[experiment.current_branch] = new_exp_version.version_id
        experiment.last_modified = datetime.utcnow()

        self._save_experiment(experiment)

        return new_exp_version

    def checkout(
        self,
        experiment_id: str,
        version_id: Optional[str] = None,
        branch: Optional[str] = None,
    ) -> Optional[ExperimentVersion]:
        """
        Checkout a specific version or branch.

        Similar to 'git checkout'.
        """
        experiment = self._experiments.get(experiment_id)
        if not experiment:
            return None

        if version_id:
            version = experiment.get_version(version_id)
            if version:
                experiment.current_version_id = version_id
                self._save_experiment(experiment)
                return version
        elif branch:
            if branch in experiment.branches:
                experiment.current_branch = branch
                experiment.current_version_id = experiment.branches[branch]
                self._save_experiment(experiment)
                return experiment.get_current_version()

        return None

    def create_branch(
        self,
        experiment_id: str,
        branch_name: str,
        from_version_id: Optional[str] = None,
    ) -> bool:
        """
        Create a new branch.

        Similar to 'git branch'.
        """
        experiment = self._experiments.get(experiment_id)
        if not experiment:
            return False

        if branch_name in experiment.branches:
            return False  # Branch already exists

        # Branch from specified version or current
        source_version_id = from_version_id or experiment.current_version_id
        if not source_version_id:
            return False

        experiment.branches[branch_name] = source_version_id
        self._save_experiment(experiment)

        return True

    def list_branches(self, experiment_id: str) -> dict[str, str]:
        """List all branches with their latest version IDs."""
        experiment = self._experiments.get(experiment_id)
        if not experiment:
            return {}
        return experiment.branches.copy()

    def get_version_log(
        self,
        experiment_id: str,
        branch: Optional[str] = None,
        limit: int = 50,
    ) -> list[ExperimentVersion]:
        """
        Get version history.

        Similar to 'git log'.
        """
        experiment = self._experiments.get(experiment_id)
        if not experiment:
            return []

        versions = experiment.get_version_history(branch)
        return sorted(versions, key=lambda v: v.provenance.created_at, reverse=True)[:limit]

    # -------------------------------------------------------------------------
    # Comparison Tools
    # -------------------------------------------------------------------------

    def diff(
        self,
        experiment_id: str,
        version_a_id: str,
        version_b_id: str,
    ) -> Optional[VersionComparison]:
        """
        Compare two versions.

        Similar to 'git diff'.
        """
        experiment = self._experiments.get(experiment_id)
        if not experiment:
            return None

        version_a = experiment.get_version(version_a_id)
        version_b = experiment.get_version(version_b_id)

        if not version_a or not version_b:
            return None

        differences = self._compute_diff(
            version_a.config_snapshot.model_dump(),
            version_b.config_snapshot.model_dump(),
        )

        # Compute summary
        summary = {
            "added": len([d for d in differences if d.diff_type == DiffType.ADDED]),
            "removed": len([d for d in differences if d.diff_type == DiffType.REMOVED]),
            "modified": len([d for d in differences if d.diff_type == DiffType.MODIFIED]),
        }

        return VersionComparison(
            version_a_id=version_a_id,
            version_b_id=version_b_id,
            differences=differences,
            summary=summary,
        )

    def _compute_diff(
        self,
        obj_a: dict[str, Any],
        obj_b: dict[str, Any],
        path: str = "",
    ) -> list[ConfigDiff]:
        """Recursively compute differences between two objects."""
        differences = []

        all_keys = set(obj_a.keys()) | set(obj_b.keys())

        for key in all_keys:
            current_path = f"{path}.{key}" if path else key

            in_a = key in obj_a
            in_b = key in obj_b

            if in_a and not in_b:
                differences.append(ConfigDiff(
                    field_path=current_path,
                    diff_type=DiffType.REMOVED,
                    old_value=obj_a[key],
                ))
            elif in_b and not in_a:
                differences.append(ConfigDiff(
                    field_path=current_path,
                    diff_type=DiffType.ADDED,
                    new_value=obj_b[key],
                ))
            elif obj_a[key] != obj_b[key]:
                # Recurse for nested dicts
                if isinstance(obj_a[key], dict) and isinstance(obj_b[key], dict):
                    differences.extend(self._compute_diff(obj_a[key], obj_b[key], current_path))
                else:
                    differences.append(ConfigDiff(
                        field_path=current_path,
                        diff_type=DiffType.MODIFIED,
                        old_value=obj_a[key],
                        new_value=obj_b[key],
                    ))

        return differences

    # -------------------------------------------------------------------------
    # Snapshot Management
    # -------------------------------------------------------------------------

    def create_snapshot(
        self,
        home_config: dict[str, Any],
        simulation_params: Optional[dict[str, Any]] = None,
        threat_scenarios: Optional[list[dict[str, Any]]] = None,
        behavior_config: Optional[dict[str, Any]] = None,
        research_integrity: Optional[dict[str, Any]] = None,
    ) -> ConfigurationSnapshot:
        """Create a configuration snapshot."""
        import platform
        import sys

        return ConfigurationSnapshot(
            home_config=home_config,
            simulation_params=simulation_params or {},
            threat_scenarios=threat_scenarios or [],
            behavior_config=behavior_config or {},
            research_integrity=research_integrity or {},
            system_info={
                "python_version": sys.version,
                "platform": platform.platform(),
                "timestamp": datetime.utcnow().isoformat(),
            },
        )

    # -------------------------------------------------------------------------
    # Tagging and Notes
    # -------------------------------------------------------------------------

    def add_tag(
        self,
        experiment_id: str,
        version_id: str,
        tag: str,
    ) -> bool:
        """Add a tag to a version."""
        experiment = self._experiments.get(experiment_id)
        if not experiment:
            return False

        version = experiment.get_version(version_id)
        if not version:
            return False

        if tag not in version.tags:
            version.tags.append(tag)
            self._save_experiment(experiment)

        return True

    def update_notes(
        self,
        experiment_id: str,
        version_id: str,
        notes: str,
    ) -> bool:
        """Update notes for a version."""
        experiment = self._experiments.get(experiment_id)
        if not experiment:
            return False

        version = experiment.get_version(version_id)
        if not version:
            return False

        version.notes = notes
        self._save_experiment(experiment)

        return True

    # -------------------------------------------------------------------------
    # Export/Import
    # -------------------------------------------------------------------------

    def export_experiment(
        self,
        experiment_id: str,
        export_path: str,
        include_results: bool = True,
    ) -> bool:
        """Export experiment as a portable package."""
        experiment = self._experiments.get(experiment_id)
        if not experiment:
            return False

        export_dir = Path(export_path)
        export_dir.mkdir(parents=True, exist_ok=True)

        # Export experiment metadata
        exp_file = export_dir / "experiment.json"
        with open(exp_file, "w") as f:
            json.dump(experiment.model_dump(mode="json"), f, indent=2, default=str)

        # Export each version's config
        versions_dir = export_dir / "versions"
        versions_dir.mkdir(exist_ok=True)

        for version in experiment.versions:
            version_file = versions_dir / f"{version.version_id}.json"
            with open(version_file, "w") as f:
                json.dump(version.model_dump(mode="json"), f, indent=2, default=str)

            # Copy results if requested
            if include_results and version.results_path:
                results_src = Path(version.results_path)
                if results_src.exists():
                    results_dest = export_dir / "results" / version.version_id
                    shutil.copytree(results_src, results_dest, dirs_exist_ok=True)

        return True

    def import_experiment(self, import_path: str) -> Optional[Experiment]:
        """Import experiment from a portable package."""
        import_dir = Path(import_path)
        exp_file = import_dir / "experiment.json"

        if not exp_file.exists():
            return None

        try:
            with open(exp_file, "r") as f:
                data = json.load(f)

            experiment = Experiment.model_validate(data)

            # Store imported experiment
            self._experiments[experiment.experiment_id] = experiment
            self._save_experiment(experiment)

            return experiment
        except Exception as e:
            print(f"Error importing experiment: {e}")
            return None

    # -------------------------------------------------------------------------
    # Statistics
    # -------------------------------------------------------------------------

    def get_stats(self) -> dict[str, Any]:
        """Get versioning system statistics."""
        experiments = list(self._experiments.values())

        total_versions = sum(len(e.versions) for e in experiments)
        total_branches = sum(len(e.branches) for e in experiments)

        status_counts = {}
        for e in experiments:
            status_counts[e.status.value] = status_counts.get(e.status.value, 0) + 1

        return {
            "total_experiments": len(experiments),
            "total_versions": total_versions,
            "total_branches": total_branches,
            "status_breakdown": status_counts,
            "storage_path": str(self.storage_path),
        }


# =============================================================================
# Singleton Instance
# =============================================================================

# Default storage path
DEFAULT_STORAGE_PATH = Path(__file__).parent.parent.parent.parent.parent / "experiments"

_versioning_instance: Optional[ExperimentVersioning] = None


def get_experiment_versioning(storage_path: Optional[str] = None) -> ExperimentVersioning:
    """Get or create the experiment versioning singleton."""
    global _versioning_instance

    if _versioning_instance is None:
        _versioning_instance = ExperimentVersioning(
            storage_path=storage_path or str(DEFAULT_STORAGE_PATH)
        )

    return _versioning_instance