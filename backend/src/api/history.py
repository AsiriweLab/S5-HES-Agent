"""
History API

REST API endpoints for retrieving historical simulation data,
events, and experiment runs for the History page.
"""

from typing import Any, Optional
from datetime import datetime, timedelta

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from src.output.research import (
    ExperimentStatus,
    get_experiment_versioning,
)

router = APIRouter(prefix="/api/history", tags=["history"])


# =============================================================================
# Response Models
# =============================================================================


class HistoricalEvent(BaseModel):
    """A historical event from simulation runs."""
    id: str
    timestamp: str
    category: str  # simulation, security, device, network, user
    type: str
    severity: str  # info, low, medium, high, critical
    source: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)
    tags: list[str] = Field(default_factory=list)
    simulation_id: Optional[str] = None


class SimulationRun(BaseModel):
    """A completed simulation run."""
    id: str
    name: str
    start_time: str
    end_time: Optional[str] = None
    duration_minutes: int
    status: str  # completed, failed, aborted
    total_events: int
    threats_detected: int
    threats_blocked: int
    compromised_devices: int
    home_config: str
    threat_scenario: Optional[str] = None
    category: Optional[str] = None
    tags: list[str] = Field(default_factory=list)


class TimelinePoint(BaseModel):
    """A data point for timeline charts."""
    timestamp: str
    value: int
    category: str


class HistoryEventsResponse(BaseModel):
    """Response with historical events."""
    events: list[HistoricalEvent]
    total: int
    page: int
    page_size: int
    total_pages: int


class SimulationRunsResponse(BaseModel):
    """Response with simulation runs."""
    simulations: list[SimulationRun]
    total: int


class AnalyticsResponse(BaseModel):
    """Response with analytics data."""
    category_stats: dict[str, int]
    severity_stats: dict[str, int]
    timeline_data: list[TimelinePoint]
    summary: dict[str, Any]


class HistoryStatsResponse(BaseModel):
    """Response with overall history statistics."""
    total_events: int
    total_simulations: int
    completed_simulations: int
    failed_simulations: int
    avg_events_per_simulation: float
    total_threats_detected: int
    total_threats_blocked: int


# =============================================================================
# Helper Functions
# =============================================================================


def extract_events_from_experiment(experiment: Any) -> list[HistoricalEvent]:
    """Extract events from an experiment's research_integrity data."""
    events: list[HistoricalEvent] = []

    if not experiment or not experiment.versions:
        return events

    # Get the latest version
    latest = experiment.versions[-1]
    if not latest.config_snapshot:
        return events

    # Extract events from research_integrity.event_log
    research_data = latest.config_snapshot.research_integrity
    event_log = research_data.get("event_log", [])

    # Get experiment start time for converting simulation timestamps
    exp_start = experiment.created_at or datetime.now()

    for event_data in event_log:
        # Handle timestamp - can be ISO string or simulation seconds (int/float)
        raw_timestamp = event_data.get("timestamp")
        if isinstance(raw_timestamp, (int, float)):
            # Convert simulation seconds to ISO timestamp
            event_time = exp_start + timedelta(seconds=raw_timestamp)
            timestamp_str = event_time.isoformat()
        elif isinstance(raw_timestamp, str):
            timestamp_str = raw_timestamp
        else:
            timestamp_str = datetime.now().isoformat()

        try:
            event = HistoricalEvent(
                id=event_data.get("id", f"evt-{experiment.experiment_id}-{len(events)}"),
                timestamp=timestamp_str,
                category=map_event_category(event_data.get("type", "system")),
                type=event_data.get("type", "unknown"),
                severity=map_event_severity(event_data.get("type", "")),
                source=event_data.get("deviceId", event_data.get("source", "system")),
                message=event_data.get("message", ""),
                details=event_data.get("details", {}),
                tags=extract_event_tags(event_data),
                simulation_id=experiment.experiment_id,
            )
            events.append(event)
        except Exception:
            # Skip malformed events
            continue

    return events


def map_event_category(event_type: str) -> str:
    """Map event type to category."""
    type_lower = event_type.lower()
    if "attack" in type_lower or "threat" in type_lower:
        return "security"
    elif "device" in type_lower or "sensor" in type_lower:
        return "device"
    elif "network" in type_lower or "mesh" in type_lower:
        return "network"
    elif "user" in type_lower or "inhabitant" in type_lower:
        return "user"
    else:
        return "simulation"


def map_event_severity(event_type: str) -> str:
    """Map event type to severity."""
    type_lower = event_type.lower()
    if "critical" in type_lower or "compromise" in type_lower:
        return "critical"
    elif "attack" in type_lower or "threat" in type_lower:
        return "high"
    elif "warning" in type_lower:
        return "medium"
    elif "detection" in type_lower:
        return "low"
    else:
        return "info"


def extract_event_tags(event_data: dict) -> list[str]:
    """Extract relevant tags from event data."""
    tags = []
    event_type = event_data.get("type", "").lower()

    if "attack" in event_type:
        tags.append("attack")
    if "threat" in event_type:
        tags.append("threat")
    if "detection" in event_type:
        tags.append("detection")
    if event_data.get("threatId"):
        tags.append("threat-related")
    if event_data.get("deviceId"):
        tags.append("device-related")

    return tags


def experiment_to_simulation_run(experiment: Any) -> SimulationRun:
    """Convert an experiment to a SimulationRun."""
    # Get latest version for config snapshot
    latest_version = experiment.versions[-1] if experiment.versions else None
    config = latest_version.config_snapshot if latest_version else None

    # Extract statistics
    research_data = config.research_integrity if config else {}
    statistics = research_data.get("statistics", {})
    event_log = research_data.get("event_log", [])

    # Get simulation params
    sim_params = config.simulation_params if config else {}

    # Map status
    status_map = {
        ExperimentStatus.COMPLETED: "completed",
        ExperimentStatus.FAILED: "failed",
        ExperimentStatus.ARCHIVED: "completed",
    }
    status = status_map.get(experiment.status, "completed")

    # Calculate times
    created_at = experiment.created_at.isoformat() if experiment.created_at else datetime.now().isoformat()
    completed_at = sim_params.get("completed_at", experiment.updated_at.isoformat() if experiment.updated_at else None)

    return SimulationRun(
        id=experiment.experiment_id,
        name=experiment.name,
        start_time=created_at,
        end_time=completed_at,
        duration_minutes=sim_params.get("duration_minutes", 0),
        status=status,
        total_events=len(event_log),
        threats_detected=statistics.get("detectedThreats", 0),
        threats_blocked=statistics.get("blockedThreats", 0),
        compromised_devices=statistics.get("compromisedDevices", 0),
        home_config=f"home-{experiment.experiment_id[:8]}.json",
        threat_scenario=f"threat-{experiment.experiment_id[:8]}.json" if sim_params.get("simulation_mode") == "threat" else None,
        category=experiment.category,
        tags=experiment.tags,
    )


# =============================================================================
# API Endpoints
# =============================================================================


@router.get("/events", response_model=HistoryEventsResponse)
async def get_events(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=200, description="Items per page"),
    category: Optional[str] = Query(None, description="Filter by category"),
    severity: Optional[str] = Query(None, description="Filter by severity"),
    search: Optional[str] = Query(None, description="Search query"),
    start_date: Optional[str] = Query(None, description="Start date (ISO format)"),
    end_date: Optional[str] = Query(None, description="End date (ISO format)"),
) -> HistoryEventsResponse:
    """
    Get historical events from all simulation runs.

    Supports filtering by category, severity, search query, and date range.
    """
    versioning = get_experiment_versioning()

    # Get all experiments (simulation runs are stored as experiments)
    experiments = versioning.list_experiments(
        status=ExperimentStatus.COMPLETED,
        category="simulation-run",
    )

    # Also include experiments without category filter for backwards compatibility
    all_experiments = versioning.list_experiments(status=ExperimentStatus.COMPLETED)

    # Combine and deduplicate
    exp_ids = {e.experiment_id for e in experiments}
    for exp in all_experiments:
        if exp.experiment_id not in exp_ids:
            experiments.append(exp)

    # Extract all events
    all_events: list[HistoricalEvent] = []
    for exp in experiments:
        events = extract_events_from_experiment(exp)
        all_events.extend(events)

    # Sort by timestamp descending
    all_events.sort(key=lambda e: e.timestamp, reverse=True)

    # Apply filters
    filtered_events = all_events

    if category:
        filtered_events = [e for e in filtered_events if e.category == category]

    if severity:
        filtered_events = [e for e in filtered_events if e.severity == severity]

    if search:
        search_lower = search.lower()
        filtered_events = [
            e for e in filtered_events
            if search_lower in e.message.lower()
            or search_lower in e.source.lower()
            or search_lower in e.type.lower()
            or any(search_lower in tag.lower() for tag in e.tags)
        ]

    if start_date:
        try:
            start = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
            filtered_events = [
                e for e in filtered_events
                if datetime.fromisoformat(e.timestamp.replace('Z', '+00:00')) >= start
            ]
        except ValueError:
            pass

    if end_date:
        try:
            end = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
            filtered_events = [
                e for e in filtered_events
                if datetime.fromisoformat(e.timestamp.replace('Z', '+00:00')) <= end
            ]
        except ValueError:
            pass

    # Paginate
    total = len(filtered_events)
    total_pages = max(1, (total + page_size - 1) // page_size)
    start_idx = (page - 1) * page_size
    end_idx = start_idx + page_size
    page_events = filtered_events[start_idx:end_idx]

    return HistoryEventsResponse(
        events=page_events,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.get("/simulations", response_model=SimulationRunsResponse)
async def get_simulations(
    status: Optional[str] = Query(None, description="Filter by status"),
    limit: int = Query(50, ge=1, le=200, description="Maximum results"),
) -> SimulationRunsResponse:
    """
    Get all simulation runs.

    Returns completed simulation runs with their statistics.
    """
    versioning = get_experiment_versioning()

    # Get experiments that are simulation runs
    status_enum = ExperimentStatus(status) if status else None
    experiments = versioning.list_experiments(status=status_enum)

    # Convert to simulation runs
    simulations: list[SimulationRun] = []
    for exp in experiments:
        try:
            sim_run = experiment_to_simulation_run(exp)
            simulations.append(sim_run)
        except Exception:
            continue

    # Sort by start time descending
    simulations.sort(key=lambda s: s.start_time, reverse=True)

    # Limit results
    simulations = simulations[:limit]

    return SimulationRunsResponse(
        simulations=simulations,
        total=len(simulations),
    )


@router.get("/analytics", response_model=AnalyticsResponse)
async def get_analytics(
    days: int = Query(7, ge=1, le=90, description="Number of days to analyze"),
) -> AnalyticsResponse:
    """
    Get analytics data for the history dashboard.

    Returns category/severity distributions and timeline data.
    """
    versioning = get_experiment_versioning()

    # Get all completed experiments
    experiments = versioning.list_experiments(status=ExperimentStatus.COMPLETED)

    # Extract all events
    all_events: list[HistoricalEvent] = []
    for exp in experiments:
        events = extract_events_from_experiment(exp)
        all_events.extend(events)

    # Calculate date range
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)

    # Filter events within date range
    events_in_range = []
    for event in all_events:
        try:
            event_time = datetime.fromisoformat(event.timestamp.replace('Z', '+00:00'))
            if start_date <= event_time <= end_date:
                events_in_range.append(event)
        except ValueError:
            continue

    # Category stats
    category_stats: dict[str, int] = {}
    for event in events_in_range:
        category_stats[event.category] = category_stats.get(event.category, 0) + 1

    # Severity stats
    severity_stats: dict[str, int] = {}
    for event in events_in_range:
        severity_stats[event.severity] = severity_stats.get(event.severity, 0) + 1

    # Timeline data (hourly aggregation)
    timeline_data: list[TimelinePoint] = []
    hours_in_range = days * 24
    for i in range(min(hours_in_range, 168)):  # Max 7 days hourly
        hour_start = end_date - timedelta(hours=i+1)
        hour_end = end_date - timedelta(hours=i)

        count = sum(
            1 for e in events_in_range
            if hour_start <= datetime.fromisoformat(e.timestamp.replace('Z', '+00:00')) < hour_end
        )

        timeline_data.append(TimelinePoint(
            timestamp=hour_start.isoformat(),
            value=count,
            category="events",
        ))

    # Reverse to chronological order
    timeline_data.reverse()

    # Summary stats
    summary = {
        "total_events": len(events_in_range),
        "total_simulations": len(experiments),
        "avg_events_per_day": len(events_in_range) / max(1, days),
        "most_common_category": max(category_stats, key=category_stats.get) if category_stats else None,
        "most_common_severity": max(severity_stats, key=severity_stats.get) if severity_stats else None,
    }

    return AnalyticsResponse(
        category_stats=category_stats,
        severity_stats=severity_stats,
        timeline_data=timeline_data,
        summary=summary,
    )


@router.get("/stats", response_model=HistoryStatsResponse)
async def get_stats() -> HistoryStatsResponse:
    """
    Get overall history statistics.

    Returns aggregate statistics across all simulation runs.
    """
    versioning = get_experiment_versioning()

    # Get all experiments
    all_experiments = versioning.list_experiments()
    completed = versioning.list_experiments(status=ExperimentStatus.COMPLETED)
    failed = versioning.list_experiments(status=ExperimentStatus.FAILED)

    # Calculate totals
    total_events = 0
    total_threats_detected = 0
    total_threats_blocked = 0

    for exp in all_experiments:
        if exp.versions:
            latest = exp.versions[-1]
            if latest.config_snapshot:
                research_data = latest.config_snapshot.research_integrity
                event_log = research_data.get("event_log", [])
                statistics = research_data.get("statistics", {})

                total_events += len(event_log)
                total_threats_detected += statistics.get("detectedThreats", 0)
                total_threats_blocked += statistics.get("blockedThreats", 0)

    avg_events = total_events / max(1, len(all_experiments))

    return HistoryStatsResponse(
        total_events=total_events,
        total_simulations=len(all_experiments),
        completed_simulations=len(completed),
        failed_simulations=len(failed),
        avg_events_per_simulation=round(avg_events, 2),
        total_threats_detected=total_threats_detected,
        total_threats_blocked=total_threats_blocked,
    )


@router.get("/simulation/{simulation_id}", response_model=SimulationRun)
async def get_simulation(simulation_id: str) -> SimulationRun:
    """
    Get a specific simulation run by ID.
    """
    versioning = get_experiment_versioning()
    experiment = versioning.get_experiment(simulation_id)

    if not experiment:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Simulation not found")

    return experiment_to_simulation_run(experiment)


@router.get("/simulation/{simulation_id}/events", response_model=HistoryEventsResponse)
async def get_simulation_events(
    simulation_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
) -> HistoryEventsResponse:
    """
    Get events for a specific simulation run.
    """
    versioning = get_experiment_versioning()
    experiment = versioning.get_experiment(simulation_id)

    if not experiment:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Simulation not found")

    events = extract_events_from_experiment(experiment)
    events.sort(key=lambda e: e.timestamp, reverse=True)

    # Paginate
    total = len(events)
    total_pages = max(1, (total + page_size - 1) // page_size)
    start_idx = (page - 1) * page_size
    end_idx = start_idx + page_size
    page_events = events[start_idx:end_idx]

    return HistoryEventsResponse(
        events=page_events,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )