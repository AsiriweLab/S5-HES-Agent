"""
Experiment Versioning API

REST API endpoints for managing experiment versions,
providing Git-like version control for research workflows.
"""

from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from src.output.research import (
    ConfigDiff,
    ConfigurationSnapshot,
    Experiment,
    ExperimentStatus,
    ExperimentVersion,
    ProvenanceMetadata,
    RAGSourceReference,
    VersionComparison,
    VersionType,
    get_experiment_versioning,
)
import src.api.simulation as simulation_api

router = APIRouter(prefix="/api/experiments", tags=["experiments"])


# =============================================================================
# Request/Response Models
# =============================================================================


class CreateExperimentRequest(BaseModel):
    """Request to create a new experiment."""
    name: str
    description: Optional[str] = None
    tags: list[str] = Field(default_factory=list)
    category: Optional[str] = None
    initial_config: Optional[dict[str, Any]] = None


class UpdateExperimentRequest(BaseModel):
    """Request to update experiment metadata."""
    name: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    tags: Optional[list[str]] = None
    category: Optional[str] = None


class CommitRequest(BaseModel):
    """Request to commit a new version."""
    message: str
    version_type: str = "patch"  # major, minor, patch
    home_config: dict[str, Any] = Field(default_factory=dict)
    simulation_params: dict[str, Any] = Field(default_factory=dict)
    threat_scenarios: list[dict[str, Any]] = Field(default_factory=list)
    behavior_config: dict[str, Any] = Field(default_factory=dict)
    research_integrity: dict[str, Any] = Field(default_factory=dict)
    tags: list[str] = Field(default_factory=list)
    notes: Optional[str] = None

    # Provenance info
    created_by: str = "user"
    research_question: Optional[str] = None
    hypothesis: Optional[str] = None
    methodology_notes: Optional[str] = None
    llm_assisted: bool = False
    llm_model: Optional[str] = None
    rag_sources: list[dict[str, Any]] = Field(default_factory=list)


class CheckoutRequest(BaseModel):
    """Request to checkout a version or branch."""
    version_id: Optional[str] = None
    branch: Optional[str] = None


class CreateBranchRequest(BaseModel):
    """Request to create a branch."""
    branch_name: str
    from_version_id: Optional[str] = None


class AddTagRequest(BaseModel):
    """Request to add a tag to a version."""
    tag: str


class UpdateNotesRequest(BaseModel):
    """Request to update version notes."""
    notes: str


class SaveSimulationRunRequest(BaseModel):
    """Request to save a completed simulation run as an experiment."""
    name: str
    description: Optional[str] = None
    tags: list[str] = Field(default_factory=list)
    category: Optional[str] = None
    # Simulation run data
    simulation_id: str
    completed_at: str
    duration_minutes: int
    simulation_mode: str = "benign"  # benign or threat
    # Configuration snapshots
    home_config: dict[str, Any]
    threat_scenario: Optional[dict[str, Any]] = None
    # Results
    statistics: dict[str, Any]
    event_log: list[dict[str, Any]] = Field(default_factory=list)


class ExperimentListResponse(BaseModel):
    """Response with list of experiments."""
    experiments: list[dict[str, Any]]
    total: int


class VersionLogResponse(BaseModel):
    """Response with version history."""
    versions: list[dict[str, Any]]
    total: int
    branch: str


class StatsResponse(BaseModel):
    """Response with versioning statistics."""
    total_experiments: int
    total_versions: int
    total_branches: int
    status_breakdown: dict[str, int]
    storage_path: str


# =============================================================================
# API Endpoints
# =============================================================================


@router.get("/", response_model=ExperimentListResponse)
async def list_experiments(
    status: Optional[str] = Query(None, description="Filter by status"),
    category: Optional[str] = Query(None, description="Filter by category"),
    tags: Optional[str] = Query(None, description="Filter by tags (comma-separated)"),
) -> ExperimentListResponse:
    """List all experiments with optional filters."""
    versioning = get_experiment_versioning()

    status_enum = ExperimentStatus(status) if status else None
    tag_list = tags.split(",") if tags else None

    experiments = versioning.list_experiments(
        status=status_enum,
        category=category,
        tags=tag_list,
    )

    return ExperimentListResponse(
        experiments=[e.model_dump(mode="json") for e in experiments],
        total=len(experiments),
    )


@router.post("/", response_model=dict)
async def create_experiment(request: CreateExperimentRequest) -> dict:
    """Create a new experiment."""
    versioning = get_experiment_versioning()

    # Create initial config if provided
    initial_config = None
    if request.initial_config:
        initial_config = versioning.create_snapshot(
            home_config=request.initial_config.get("home_config", {}),
            simulation_params=request.initial_config.get("simulation_params", {}),
            threat_scenarios=request.initial_config.get("threat_scenarios", []),
            behavior_config=request.initial_config.get("behavior_config", {}),
            research_integrity=request.initial_config.get("research_integrity", {}),
        )

    experiment = versioning.create_experiment(
        name=request.name,
        description=request.description,
        initial_config=initial_config,
        tags=request.tags,
        category=request.category,
    )

    return experiment.model_dump(mode="json")


# -----------------------------------------------------------------------------
# Current State Endpoint (must be before /{experiment_id})
# -----------------------------------------------------------------------------


class CurrentStateResponse(BaseModel):
    """Response with current simulation state for importing into experiments."""
    has_home: bool
    has_threats: bool
    home_config: dict[str, Any]
    simulation_params: dict[str, Any]
    threat_scenarios: list[dict[str, Any]]
    behavior_config: dict[str, Any]
    summary: dict[str, Any]


@router.get("/current-state", response_model=CurrentStateResponse)
async def get_current_state() -> CurrentStateResponse:
    """
    Get the current simulation state for importing into experiments.

    This allows creating experiments with the current home configuration
    and threat scenarios from the Home Builder and Threat Builder.
    """
    home_config: dict[str, Any] = {}
    threat_scenarios: list[dict[str, Any]] = []
    behavior_config: dict[str, Any] = {}
    simulation_params: dict[str, Any] = {}

    # Access _current_home from the simulation module dynamically
    current_home = simulation_api._current_home
    has_home = current_home is not None
    has_threats = False

    summary: dict[str, Any] = {
        "total_rooms": 0,
        "total_devices": 0,
        "total_inhabitants": 0,
        "total_threats": 0,
    }

    if current_home:
        # Extract home configuration
        home_config = {
            "id": current_home.id,
            "name": current_home.name,
            "template": current_home.config.template.value,
            "total_area_sqm": current_home.config.total_area_sqm,
            "floors": current_home.config.floors,
            "has_garage": current_home.config.has_garage,
            "has_garden": current_home.config.has_garden,
            "rooms": [
                {
                    "id": room.id,
                    "name": room.name,
                    "room_type": room.room_type,
                    "area_sqm": room.config.area_sqm,
                    "floor_level": room.config.floor_level,
                    "device_ids": room.device_ids,
                }
                for room in current_home.rooms
            ],
            "devices": [
                {
                    "id": device.id,
                    "name": device.name,
                    "device_type": device.device_type,
                    "room_id": device.room_id,
                    "status": device.state.status,
                    "properties": device.state.properties,
                }
                for device in current_home.devices
            ],
            "inhabitants": [
                {
                    "id": inhabitant.id,
                    "name": inhabitant.name,
                    "type": inhabitant.inhabitant_type,
                    "age": inhabitant.age,
                    "schedule": {
                        "wake_time": inhabitant.schedule.wake_time.isoformat(),
                        "sleep_time": inhabitant.schedule.sleep_time.isoformat(),
                        "works_from_home": inhabitant.schedule.works_from_home,
                    },
                }
                for inhabitant in current_home.inhabitants
            ],
        }

        summary["total_rooms"] = len(current_home.rooms)
        summary["total_devices"] = len(current_home.devices)
        summary["total_inhabitants"] = len(current_home.inhabitants)

        # Extract behavior config from inhabitants
        behavior_config = {
            "occupancy_patterns": [
                {
                    "inhabitant_id": inhabitant.id,
                    "wake_time": inhabitant.schedule.wake_time.isoformat(),
                    "sleep_time": inhabitant.schedule.sleep_time.isoformat(),
                    "works_from_home": inhabitant.schedule.works_from_home,
                }
                for inhabitant in current_home.inhabitants
            ],
        }

    # Default simulation parameters
    simulation_params = {
        "duration_hours": 24,
        "time_compression": 1440,
        "enable_threats": True,
        "collect_all_events": True,
    }

    return CurrentStateResponse(
        has_home=has_home,
        has_threats=has_threats,
        home_config=home_config,
        simulation_params=simulation_params,
        threat_scenarios=threat_scenarios,
        behavior_config=behavior_config,
        summary=summary,
    )


# -----------------------------------------------------------------------------
# Save Simulation Run as Experiment
# -----------------------------------------------------------------------------


@router.post("/from-simulation", response_model=dict)
async def save_simulation_run(request: SaveSimulationRunRequest) -> dict:
    """
    Save a completed simulation run as a new experiment.

    This creates an experiment with:
    - The home configuration used
    - The threat scenario (if any)
    - Simulation results (statistics, event log)
    - Marked as 'completed' status
    """
    versioning = get_experiment_versioning()

    # Create initial config snapshot with simulation results
    initial_config = versioning.create_snapshot(
        home_config=request.home_config,
        simulation_params={
            "simulation_id": request.simulation_id,
            "completed_at": request.completed_at,
            "duration_minutes": request.duration_minutes,
            "simulation_mode": request.simulation_mode,
        },
        threat_scenarios=[request.threat_scenario] if request.threat_scenario else [],
        behavior_config={},
        research_integrity={
            "statistics": request.statistics,
            "event_log": request.event_log,
            "event_count": len(request.event_log),
        },
    )

    # Create experiment with completed status
    experiment = versioning.create_experiment(
        name=request.name,
        description=request.description or f"Simulation run completed at {request.completed_at}",
        initial_config=initial_config,
        tags=request.tags,
        category=request.category or "simulation-run",
    )

    # Update status to completed
    versioning.update_experiment(
        experiment_id=experiment.experiment_id,
        status=ExperimentStatus.COMPLETED,
    )

    # Refresh to get updated experiment
    experiment = versioning.get_experiment(experiment.experiment_id)

    return experiment.model_dump(mode="json") if experiment else {}


# -----------------------------------------------------------------------------
# Experiment CRUD Endpoints
# -----------------------------------------------------------------------------


@router.get("/{experiment_id}", response_model=dict)
async def get_experiment(experiment_id: str) -> dict:
    """Get an experiment by ID."""
    versioning = get_experiment_versioning()
    experiment = versioning.get_experiment(experiment_id)

    if not experiment:
        raise HTTPException(status_code=404, detail="Experiment not found")

    return experiment.model_dump(mode="json")


@router.put("/{experiment_id}", response_model=dict)
async def update_experiment(
    experiment_id: str,
    request: UpdateExperimentRequest,
) -> dict:
    """Update experiment metadata."""
    versioning = get_experiment_versioning()

    status_enum = ExperimentStatus(request.status) if request.status else None

    experiment = versioning.update_experiment(
        experiment_id=experiment_id,
        name=request.name,
        description=request.description,
        status=status_enum,
        tags=request.tags,
        category=request.category,
    )

    if not experiment:
        raise HTTPException(status_code=404, detail="Experiment not found")

    return experiment.model_dump(mode="json")


@router.delete("/{experiment_id}")
async def delete_experiment(experiment_id: str) -> dict:
    """Delete an experiment."""
    versioning = get_experiment_versioning()

    if not versioning.delete_experiment(experiment_id):
        raise HTTPException(status_code=404, detail="Experiment not found")

    return {"status": "deleted", "experiment_id": experiment_id}


# -----------------------------------------------------------------------------
# Version Control Endpoints
# -----------------------------------------------------------------------------


@router.post("/{experiment_id}/commit", response_model=dict)
async def commit_version(
    experiment_id: str,
    request: CommitRequest,
) -> dict:
    """Commit a new version of the experiment."""
    versioning = get_experiment_versioning()

    # Create snapshot
    snapshot = versioning.create_snapshot(
        home_config=request.home_config,
        simulation_params=request.simulation_params,
        threat_scenarios=request.threat_scenarios,
        behavior_config=request.behavior_config,
        research_integrity=request.research_integrity,
    )

    # Create provenance
    rag_refs = [
        RAGSourceReference(
            doc_id=src.get("doc_id", ""),
            title=src.get("title", ""),
            source=src.get("source", ""),
            category=src.get("category", ""),
            relevance_score=src.get("relevance_score", 0.0),
            excerpt=src.get("excerpt"),
        )
        for src in request.rag_sources
    ]

    provenance = ProvenanceMetadata(
        created_by=request.created_by,
        research_question=request.research_question,
        hypothesis=request.hypothesis,
        methodology_notes=request.methodology_notes,
        llm_assisted=request.llm_assisted,
        llm_model=request.llm_model,
        rag_sources=rag_refs,
    )

    # Map version type
    version_type_map = {
        "major": VersionType.MAJOR,
        "minor": VersionType.MINOR,
        "patch": VersionType.PATCH,
    }
    version_type = version_type_map.get(request.version_type.lower(), VersionType.PATCH)

    version = versioning.commit(
        experiment_id=experiment_id,
        config_snapshot=snapshot,
        message=request.message,
        version_type=version_type,
        provenance=provenance,
        tags=request.tags,
        notes=request.notes,
    )

    if not version:
        raise HTTPException(status_code=404, detail="Experiment not found")

    return version.model_dump(mode="json")


@router.post("/{experiment_id}/checkout", response_model=dict)
async def checkout_version(
    experiment_id: str,
    request: CheckoutRequest,
) -> dict:
    """Checkout a specific version or branch."""
    versioning = get_experiment_versioning()

    version = versioning.checkout(
        experiment_id=experiment_id,
        version_id=request.version_id,
        branch=request.branch,
    )

    if not version:
        raise HTTPException(status_code=404, detail="Version or branch not found")

    return version.model_dump(mode="json")


@router.get("/{experiment_id}/log", response_model=VersionLogResponse)
async def get_version_log(
    experiment_id: str,
    branch: Optional[str] = Query(None, description="Branch name"),
    limit: int = Query(50, description="Maximum versions to return"),
) -> VersionLogResponse:
    """Get version history for an experiment."""
    versioning = get_experiment_versioning()

    experiment = versioning.get_experiment(experiment_id)
    if not experiment:
        raise HTTPException(status_code=404, detail="Experiment not found")

    versions = versioning.get_version_log(
        experiment_id=experiment_id,
        branch=branch,
        limit=limit,
    )

    return VersionLogResponse(
        versions=[v.model_dump(mode="json") for v in versions],
        total=len(versions),
        branch=branch or experiment.current_branch,
    )


# -----------------------------------------------------------------------------
# Branch Endpoints
# -----------------------------------------------------------------------------


@router.get("/{experiment_id}/branches", response_model=dict)
async def list_branches(experiment_id: str) -> dict:
    """List all branches for an experiment."""
    versioning = get_experiment_versioning()

    branches = versioning.list_branches(experiment_id)
    if not branches:
        raise HTTPException(status_code=404, detail="Experiment not found")

    experiment = versioning.get_experiment(experiment_id)

    return {
        "branches": branches,
        "current_branch": experiment.current_branch if experiment else "main",
    }


@router.post("/{experiment_id}/branches", response_model=dict)
async def create_branch(
    experiment_id: str,
    request: CreateBranchRequest,
) -> dict:
    """Create a new branch."""
    versioning = get_experiment_versioning()

    if not versioning.create_branch(
        experiment_id=experiment_id,
        branch_name=request.branch_name,
        from_version_id=request.from_version_id,
    ):
        raise HTTPException(
            status_code=400,
            detail="Failed to create branch. Experiment not found or branch already exists.",
        )

    return {"status": "created", "branch": request.branch_name}


# -----------------------------------------------------------------------------
# Comparison Endpoints
# -----------------------------------------------------------------------------


@router.get("/{experiment_id}/diff", response_model=dict)
async def diff_versions(
    experiment_id: str,
    version_a: str = Query(..., description="First version ID"),
    version_b: str = Query(..., description="Second version ID"),
) -> dict:
    """Compare two versions."""
    versioning = get_experiment_versioning()

    comparison = versioning.diff(
        experiment_id=experiment_id,
        version_a_id=version_a,
        version_b_id=version_b,
    )

    if not comparison:
        raise HTTPException(status_code=404, detail="Versions not found")

    return comparison.model_dump(mode="json")


# -----------------------------------------------------------------------------
# Tag and Notes Endpoints
# -----------------------------------------------------------------------------


@router.post("/{experiment_id}/versions/{version_id}/tags", response_model=dict)
async def add_version_tag(
    experiment_id: str,
    version_id: str,
    request: AddTagRequest,
) -> dict:
    """Add a tag to a version."""
    versioning = get_experiment_versioning()

    if not versioning.add_tag(experiment_id, version_id, request.tag):
        raise HTTPException(status_code=404, detail="Experiment or version not found")

    return {"status": "added", "tag": request.tag}


@router.put("/{experiment_id}/versions/{version_id}/notes", response_model=dict)
async def update_version_notes(
    experiment_id: str,
    version_id: str,
    request: UpdateNotesRequest,
) -> dict:
    """Update notes for a version."""
    versioning = get_experiment_versioning()

    if not versioning.update_notes(experiment_id, version_id, request.notes):
        raise HTTPException(status_code=404, detail="Experiment or version not found")

    return {"status": "updated", "notes": request.notes}


# -----------------------------------------------------------------------------
# Export/Import Endpoints
# -----------------------------------------------------------------------------


@router.post("/{experiment_id}/export", response_model=dict)
async def export_experiment(
    experiment_id: str,
    export_path: Optional[str] = Query(None, description="Export directory path"),
    include_results: bool = Query(True, description="Include experiment results"),
) -> dict:
    """Export an experiment as a portable package."""
    versioning = get_experiment_versioning()

    # Default export path
    if not export_path:
        export_path = f"exports/experiments/{experiment_id}"

    if not versioning.export_experiment(
        experiment_id=experiment_id,
        export_path=export_path,
        include_results=include_results,
    ):
        raise HTTPException(status_code=404, detail="Experiment not found")

    return {
        "status": "exported",
        "experiment_id": experiment_id,
        "export_path": export_path,
    }


@router.post("/import", response_model=dict)
async def import_experiment(
    import_path: str = Query(..., description="Path to import from"),
) -> dict:
    """Import an experiment from a portable package."""
    versioning = get_experiment_versioning()

    experiment = versioning.import_experiment(import_path)
    if not experiment:
        raise HTTPException(status_code=400, detail="Failed to import experiment")

    return experiment.model_dump(mode="json")


# -----------------------------------------------------------------------------
# Statistics Endpoint
# -----------------------------------------------------------------------------


@router.get("/stats/overview", response_model=StatsResponse)
async def get_stats() -> StatsResponse:
    """Get experiment versioning statistics."""
    versioning = get_experiment_versioning()
    stats = versioning.get_stats()

    return StatsResponse(
        total_experiments=stats["total_experiments"],
        total_versions=stats["total_versions"],
        total_branches=stats["total_branches"],
        status_breakdown=stats["status_breakdown"],
        storage_path=stats["storage_path"],
    )

