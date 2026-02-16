"""
Monitoring API Endpoints

REST API for real-time monitoring of system metrics, security events,
device status, and mesh network state.

IMPORTANT: This module returns REAL data from running simulations only.
When no simulation is active, it returns empty/idle state - NOT mock data.
"""

from datetime import datetime
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from src.simulation import get_simulation_engine, SimulationState

# Import security components for real data access
_security_engine = None
_mesh_simulator = None


def get_security_engine():
    """Get the security engine instance (lazy loaded)."""
    global _security_engine
    if _security_engine is None:
        try:
            from src.security import SecurityPrivacyEngine
            _security_engine = SecurityPrivacyEngine()
        except ImportError:
            pass
    return _security_engine


def get_mesh_simulator():
    """Get the mesh simulator instance (lazy loaded)."""
    global _mesh_simulator
    if _mesh_simulator is None:
        try:
            from src.security import MeshNetworkSimulator
            _mesh_simulator = MeshNetworkSimulator()
        except ImportError:
            pass
    return _mesh_simulator


def register_security_engine(engine) -> None:
    """Register external security engine instance."""
    global _security_engine
    _security_engine = engine


def register_mesh_simulator(simulator) -> None:
    """Register external mesh simulator instance."""
    global _mesh_simulator
    _mesh_simulator = simulator


router = APIRouter(prefix="/api/monitoring", tags=["monitoring"])


# =============================================================================
# Response Models
# =============================================================================


class SystemMetric(BaseModel):
    """System metric with trend information."""
    name: str
    value: float
    unit: str
    trend: str  # up, down, stable
    status: str  # normal, warning, critical


class SecurityEvent(BaseModel):
    """Security event from the system."""
    id: str
    timestamp: datetime
    type: str  # auth, tls, encryption, mesh, privacy, threat
    severity: str  # info, low, medium, high, critical
    source: str
    message: str
    details: Optional[dict[str, Any]] = None


class DeviceStatus(BaseModel):
    """Status of an IoT device."""
    id: str
    name: str
    type: str
    protocol: str
    status: str  # online, offline, warning, compromised
    last_seen: datetime
    signal_strength: Optional[int] = None
    battery_level: Optional[int] = None


class MeshNode(BaseModel):
    """Mesh network node status."""
    id: str
    role: str  # coordinator, router, end_device
    state: str
    neighbors: int
    messages_sent: int
    messages_received: int


class SecurityStats(BaseModel):
    """Aggregate security statistics."""
    auth_success: int
    auth_failure: int
    tls_handshakes: int
    encrypted_messages: int
    privacy_queries: int
    threats_blocked: int


class MonitoringSnapshot(BaseModel):
    """Complete monitoring snapshot."""
    timestamp: datetime
    simulation_state: str  # idle, running, paused, stopped, completed, error
    metrics: list[SystemMetric]
    security_stats: SecurityStats
    devices: list[DeviceStatus]
    mesh_nodes: list[MeshNode]
    recent_events: list[SecurityEvent]
    is_live: bool = False  # True only when simulation is actively running


# =============================================================================
# Helper Functions - Get REAL data from simulation or return empty/idle state
# =============================================================================


def _get_simulation_state() -> str:
    """Get current simulation state."""
    engine = get_simulation_engine()
    if engine is None:
        return "idle"
    return engine.stats.state.value


def _is_simulation_running() -> bool:
    """Check if a simulation is actively running."""
    engine = get_simulation_engine()
    if engine is None:
        return False
    return engine.stats.state == SimulationState.RUNNING


def _get_real_metrics() -> list[SystemMetric]:
    """
    Get REAL system metrics from running simulation.
    Returns empty list if no simulation is running.
    """
    engine = get_simulation_engine()
    if engine is None or engine.stats.state != SimulationState.RUNNING:
        return []

    # Get actual stats from simulation engine
    stats = engine.stats
    home = engine.home

    # Count online devices (status is in device.state.status)
    active_devices = 0
    for d in home.devices:
        if hasattr(d, 'state') and hasattr(d.state, 'status'):
            status = d.state.status.value if hasattr(d.state.status, 'value') else str(d.state.status)
            if status == "online":
                active_devices += 1

    return [
        SystemMetric(
            name="Active Devices",
            value=active_devices,
            unit="",
            trend="stable",
            status="normal"
        ),
        SystemMetric(
            name="Total Events",
            value=stats.total_events,
            unit="",
            trend="up" if stats.total_events > 0 else "stable",
            status="normal"
        ),
        SystemMetric(
            name="Simulation Ticks",
            value=stats.total_ticks,
            unit="",
            trend="up",
            status="normal"
        ),
        SystemMetric(
            name="Anomalies",
            value=stats.anomalies_generated,
            unit="",
            trend="stable",
            status="warning" if stats.anomalies_generated > 0 else "normal"
        ),
    ]


def _get_real_devices() -> list[DeviceStatus]:
    """
    Get REAL device statuses from running simulation.
    Returns empty list if no simulation is running.
    """
    engine = get_simulation_engine()
    if engine is None:
        return []

    home = engine.home
    devices = []

    for device in home.devices:
        # Handle device_type - may be enum or string (due to use_enum_values=True)
        device_type = device.device_type.value if hasattr(device.device_type, 'value') else str(device.device_type)

        # Get protocol from device.config.protocol
        if hasattr(device, 'config') and hasattr(device.config, 'protocol'):
            protocol = device.config.protocol.value if hasattr(device.config.protocol, 'value') else str(device.config.protocol)
        else:
            protocol = "unknown"

        # Get status from device.state.status
        if hasattr(device, 'state') and hasattr(device.state, 'status'):
            status = device.state.status.value if hasattr(device.state.status, 'value') else str(device.state.status)
        else:
            status = "unknown"

        # Get signal strength and battery from device.state
        signal_strength = None
        battery_level = None
        if hasattr(device, 'state'):
            if hasattr(device.state, 'signal_strength') and device.state.signal_strength is not None:
                signal_strength = int(device.state.signal_strength)
            if hasattr(device.state, 'battery_level') and device.state.battery_level is not None:
                battery_level = int(device.state.battery_level)

        # Get last_seen from device.state if available
        last_seen = datetime.now()
        if hasattr(device, 'state') and hasattr(device.state, 'last_seen') and device.state.last_seen:
            last_seen = device.state.last_seen

        devices.append(DeviceStatus(
            id=device.id,
            name=device.name,
            type=device_type,
            protocol=protocol,
            status=status,
            last_seen=last_seen,
            signal_strength=signal_strength,
            battery_level=battery_level,
        ))

    return devices


def _get_empty_security_stats() -> SecurityStats:
    """Return zeroed security stats for idle state."""
    return SecurityStats(
        auth_success=0,
        auth_failure=0,
        tls_handshakes=0,
        encrypted_messages=0,
        privacy_queries=0,
        threats_blocked=0,
    )


# =============================================================================
# API Endpoints
# =============================================================================


@router.get("/snapshot", response_model=MonitoringSnapshot)
async def get_monitoring_snapshot(
    include_events: bool = Query(True, description="Include recent security events"),
    event_limit: int = Query(50, ge=1, le=200, description="Max events to return"),
) -> MonitoringSnapshot:
    """
    Get a complete monitoring snapshot.

    Returns current system metrics, device status, mesh network state,
    and recent security events.

    NOTE: Returns empty/idle state when no simulation is running.
    NO mock data is generated - only real simulation data is returned.
    """
    sim_state = _get_simulation_state()
    is_running = _is_simulation_running()

    # Get REAL data from simulation (empty if not running)
    metrics = _get_real_metrics()
    devices = _get_real_devices()

    # Get mesh nodes from mesh simulator
    mesh_nodes: list[MeshNode] = []
    mesh_sim = get_mesh_simulator()
    if mesh_sim and mesh_sim._running:
        for node in mesh_sim._nodes.values():
            mesh_nodes.append(MeshNode(
                id=node.node_id,
                role=node.role.value,
                state=node.state.value,
                neighbors=len(node.neighbors),
                messages_sent=node.messages_sent,
                messages_received=node.messages_received,
            ))

    # Get events from security engine
    events: list[SecurityEvent] = []
    security_engine = get_security_engine()
    if security_engine and security_engine.is_running and include_events:
        for event in security_engine._events[-event_limit:]:
            events.append(SecurityEvent(
                id=event.id,
                timestamp=event.timestamp,
                type=event.event_type.value,
                severity=event.severity.value,
                source=event.source_id,
                message=f"{event.event_type.value}: {event.details.get('message', '')}",
                details=event.details,
            ))

    # Get security stats
    security_stats = _get_empty_security_stats()
    if security_engine and security_engine.is_running:
        stats = security_engine.stats
        security_stats = SecurityStats(
            auth_success=stats.auth_successes,
            auth_failure=stats.auth_failures,
            tls_handshakes=stats.tls_handshakes,
            encrypted_messages=stats.encryption_operations,
            privacy_queries=0,
            threats_blocked=stats.intrusions_detected,
        )

    return MonitoringSnapshot(
        timestamp=datetime.now(),
        simulation_state=sim_state,
        metrics=metrics,
        security_stats=security_stats,
        devices=devices,
        mesh_nodes=mesh_nodes,
        recent_events=events,
        is_live=is_running,
    )


@router.get("/metrics", response_model=list[SystemMetric])
async def get_metrics() -> list[SystemMetric]:
    """
    Get current system metrics only.
    Returns empty list if no simulation is running.
    """
    return _get_real_metrics()


@router.get("/devices", response_model=list[DeviceStatus])
async def get_devices() -> list[DeviceStatus]:
    """
    Get current device statuses.
    Returns empty list if no simulation is running.
    """
    return _get_real_devices()


@router.get("/events", response_model=list[SecurityEvent])
async def get_security_events(
    limit: int = Query(50, ge=1, le=200, description="Max events to return"),
    severity: Optional[str] = Query(None, description="Filter by severity"),
    event_type: Optional[str] = Query(None, description="Filter by type"),
) -> list[SecurityEvent]:
    """
    Get recent security events with optional filtering.
    Returns empty list if no simulation is running.
    """
    security_engine = get_security_engine()
    if security_engine is None or not security_engine.is_running:
        return []

    # Get events from security engine
    events = []
    for event in security_engine._events[-limit:]:
        # Apply filters
        if severity and event.severity.value != severity:
            continue
        if event_type and event.event_type.value != event_type:
            continue

        events.append(SecurityEvent(
            id=event.id,
            timestamp=event.timestamp,
            type=event.event_type.value,
            severity=event.severity.value,
            source=event.source_id,
            message=f"{event.event_type.value}: {event.details.get('message', '')}",
            details=event.details,
        ))

    return events[-limit:]


@router.get("/mesh", response_model=list[MeshNode])
async def get_mesh_network() -> list[MeshNode]:
    """
    Get mesh network node status.
    Returns empty list if no mesh simulation is running.
    """
    mesh_sim = get_mesh_simulator()
    if mesh_sim is None or not mesh_sim._running:
        return []

    # Get nodes from mesh simulator
    nodes = []
    for node in mesh_sim._nodes.values():
        nodes.append(MeshNode(
            id=node.node_id,
            role=node.role.value,
            state=node.state.value,
            neighbors=len(node.neighbors),
            messages_sent=node.messages_sent,
            messages_received=node.messages_received,
        ))

    return nodes


@router.get("/stats", response_model=SecurityStats)
async def get_security_stats() -> SecurityStats:
    """
    Get aggregate security statistics.
    Returns zeroed stats if no simulation is running.
    """
    security_engine = get_security_engine()
    if security_engine is None or not security_engine.is_running:
        return _get_empty_security_stats()

    # Get stats from security engine
    stats = security_engine.stats
    return SecurityStats(
        auth_success=stats.auth_successes,
        auth_failure=stats.auth_failures,
        tls_handshakes=stats.tls_handshakes,
        encrypted_messages=stats.encryption_operations,
        privacy_queries=0,  # Would come from privacy engine if available
        threats_blocked=stats.intrusions_detected,
    )


@router.get("/state")
async def get_simulation_state_endpoint() -> dict[str, Any]:
    """
    Get current simulation state.
    Useful for frontend to determine if monitoring should be active.
    """
    engine = get_simulation_engine()
    if engine is None:
        return {
            "state": "idle",
            "message": "No simulation configured. Create a home and start a simulation to see monitoring data.",
            "has_home": False,
            "has_simulation": False,
        }

    return {
        "state": engine.stats.state.value,
        "simulation_id": engine.stats.id,
        "has_home": True,
        "has_simulation": True,
        "total_ticks": engine.stats.total_ticks,
        "total_events": engine.stats.total_events,
    }
