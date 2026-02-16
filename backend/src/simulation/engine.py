"""
Simulation Engine

Time-compressed simulation engine for smart home environments.
Orchestrates devices, generates events, and manages simulation state.
"""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Optional
from uuid import uuid4

from loguru import logger

from src.core.config import settings
from src.simulation.devices.device_registry import DeviceRegistry, get_device_registry
from src.simulation.models import (
    Device,
    DeviceStatus,
    EventType,
    Home,
    SimulationEvent,
)
from src.simulation.threats.threat_injector import ThreatInjector, ThreatConfig


class SimulationState(str, Enum):
    """Simulation state enumeration."""
    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPED = "stopped"
    COMPLETED = "completed"
    ERROR = "error"


@dataclass
class SimulationConfig:
    """Configuration for a simulation run."""
    duration_hours: float = 24  # Supports fractional hours (e.g., 0.5 = 30 min)
    time_compression: int = 1440  # 24 hours in 1 minute (1440x)
    tick_interval_ms: int = 100  # Real-time ms between ticks
    start_time: Optional[datetime] = None  # Simulation start time
    random_seed: Optional[int] = None
    enable_threats: bool = False
    enable_anomalies: bool = True
    collect_all_events: bool = True


@dataclass
class SimulationStats:
    """Statistics for a simulation run."""
    id: str = field(default_factory=lambda: str(uuid4()))
    state: SimulationState = SimulationState.IDLE
    start_real_time: Optional[datetime] = None
    end_real_time: Optional[datetime] = None
    simulation_start_time: Optional[datetime] = None
    simulation_current_time: Optional[datetime] = None
    simulation_end_time: Optional[datetime] = None
    total_ticks: int = 0
    total_events: int = 0
    events_by_type: dict[str, int] = field(default_factory=dict)
    devices_simulated: int = 0
    anomalies_generated: int = 0
    errors: list[str] = field(default_factory=list)


class SimulationEngine:
    """
    Time-compressed simulation engine.

    Features:
    - Configurable time compression (e.g., 24 hours in 1 minute)
    - Event-driven architecture
    - Device behavior orchestration
    - Async execution with pause/resume
    - Event collection for analysis
    """

    def __init__(
        self,
        home: Home,
        config: Optional[SimulationConfig] = None,
        device_registry: Optional[DeviceRegistry] = None,
    ):
        """
        Initialize the simulation engine.

        Args:
            home: Home model to simulate
            config: Simulation configuration
            device_registry: Device registry (uses global if not provided)
        """
        self.home = home
        self.config = config or SimulationConfig()
        self.device_registry = device_registry or get_device_registry()

        self.stats = SimulationStats()
        self._events: list[SimulationEvent] = []
        self._event_handlers: list[Callable[[SimulationEvent], None]] = []
        self._running = False
        self._paused = False
        self._stop_requested = False

        # User-defined threats for scheduled injection (set by API)
        self._user_defined_threats: list[Any] = []
        self._injected_threat_ids: set[str] = set()

        # Initialize device behaviors
        self._initialize_devices()

        # Initialize threat injector if threats are enabled
        self.threat_injector: Optional[ThreatInjector] = None
        if self.config.enable_threats:
            self.threat_injector = ThreatInjector(home, ThreatConfig())
            self.threat_injector.register_default_scenarios()
            logger.info("ThreatInjector initialized with default scenarios")

        logger.info(
            f"SimulationEngine initialized: {len(self.home.devices)} devices, "
            f"{self.config.time_compression}x compression, threats={'enabled' if self.config.enable_threats else 'disabled'}"
        )

    def _initialize_devices(self) -> None:
        """Initialize device behaviors for all devices."""
        self.device_registry.clear()
        for device in self.home.devices:
            self.device_registry.register(device)
        self.stats.devices_simulated = self.device_registry.count()

    def add_event_handler(self, handler: Callable[[SimulationEvent], None]) -> None:
        """Add an event handler callback."""
        self._event_handlers.append(handler)

    def remove_event_handler(self, handler: Callable[[SimulationEvent], None]) -> None:
        """Remove an event handler callback."""
        if handler in self._event_handlers:
            self._event_handlers.remove(handler)

    def _emit_event(self, event: SimulationEvent) -> None:
        """Emit an event to all handlers and store it."""
        if self.config.collect_all_events:
            self._events.append(event)

        # Update stats
        self.stats.total_events += 1
        event_type_str = event.event_type.value if isinstance(event.event_type, Enum) else str(event.event_type)
        self.stats.events_by_type[event_type_str] = (
            self.stats.events_by_type.get(event_type_str, 0) + 1
        )
        if event.is_anomaly:
            self.stats.anomalies_generated += 1

        # Notify handlers
        for handler in self._event_handlers:
            try:
                handler(event)
            except Exception as e:
                logger.error(f"Event handler error: {e}")

    async def run(self) -> SimulationStats:
        """
        Run the simulation.

        Returns:
            SimulationStats with results
        """
        if self._running:
            raise RuntimeError("Simulation already running")

        self._running = True
        self._stop_requested = False
        self.stats.state = SimulationState.RUNNING
        self.stats.start_real_time = datetime.utcnow()

        # Initialize simulation time
        sim_start = self.config.start_time or datetime.utcnow()
        sim_end = sim_start + timedelta(hours=self.config.duration_hours)
        current_sim_time = sim_start

        self.stats.simulation_start_time = sim_start
        self.stats.simulation_end_time = sim_end
        self.stats.simulation_current_time = current_sim_time

        logger.info(
            f"Starting simulation: {sim_start.isoformat()} to {sim_end.isoformat()} "
            f"({self.config.duration_hours}h at {self.config.time_compression}x)"
        )

        # Emit simulation start event
        self._emit_event(SimulationEvent(
            event_type=EventType.SYSTEM_EVENT,
            timestamp=current_sim_time,
            source_id="system",
            source_type="system",
            data={"event": "simulation_started", "config": {
                "duration_hours": self.config.duration_hours,
                "time_compression": self.config.time_compression,
            }},
        ))

        # Calculate time increments
        tick_interval_real = self.config.tick_interval_ms / 1000  # Convert to seconds
        sim_seconds_per_tick = tick_interval_real * self.config.time_compression

        try:
            while current_sim_time < sim_end and not self._stop_requested:
                # Handle pause
                while self._paused and not self._stop_requested:
                    await asyncio.sleep(0.1)

                if self._stop_requested:
                    break

                # Process one tick
                events = self._process_tick(current_sim_time, sim_seconds_per_tick)
                for event in events:
                    self._emit_event(event)

                # Advance simulation time
                current_sim_time += timedelta(seconds=sim_seconds_per_tick)
                self.stats.simulation_current_time = current_sim_time
                self.stats.total_ticks += 1

                # Real-time delay
                await asyncio.sleep(tick_interval_real)

            # Determine final state
            if self._stop_requested:
                self.stats.state = SimulationState.STOPPED
            else:
                self.stats.state = SimulationState.COMPLETED

        except Exception as e:
            logger.error(f"Simulation error: {e}")
            self.stats.state = SimulationState.ERROR
            self.stats.errors.append(str(e))

        finally:
            self._running = False
            self.stats.end_real_time = datetime.utcnow()

            # Emit simulation end event
            self._emit_event(SimulationEvent(
                event_type=EventType.SYSTEM_EVENT,
                timestamp=current_sim_time,
                source_id="system",
                source_type="system",
                data={"event": "simulation_ended", "state": self.stats.state.value},
            ))

            logger.info(
                f"Simulation {self.stats.state.value}: "
                f"{self.stats.total_ticks} ticks, {self.stats.total_events} events"
            )

        return self.stats

    def _process_tick(
        self,
        current_time: datetime,
        delta_seconds: float,
    ) -> list[SimulationEvent]:
        """Process one simulation tick."""
        events = []

        # Update all device behaviors
        for behavior in self.device_registry.get_all():
            try:
                device_events = behavior.update(current_time, delta_seconds)
                events.extend(device_events)
            except Exception as e:
                logger.error(f"Device update error ({behavior.device_id}): {e}")
                events.append(SimulationEvent(
                    event_type=EventType.SYSTEM_EVENT,
                    timestamp=current_time,
                    source_id=behavior.device_id,
                    source_type="device",
                    data={"error": str(e)},
                    is_anomaly=True,
                ))

        # Check for scheduled user-defined threats
        if self._user_defined_threats and self.stats.simulation_start_time:
            elapsed_minutes = (current_time - self.stats.simulation_start_time).total_seconds() / 60
            for threat in self._user_defined_threats:
                threat_id = threat.id if hasattr(threat, 'id') else threat.get('id')
                start_time = threat.startTime if hasattr(threat, 'startTime') else threat.get('startTime', 0)

                if threat_id not in self._injected_threat_ids and elapsed_minutes >= start_time:
                    self._injected_threat_ids.add(threat_id)
                    # Generate threat injection event
                    threat_name = threat.name if hasattr(threat, 'name') else threat.get('name', 'Unknown Threat')
                    threat_type = threat.type if hasattr(threat, 'type') else threat.get('type', 'unknown')
                    severity = threat.severity if hasattr(threat, 'severity') else threat.get('severity', 'medium')
                    duration = threat.duration if hasattr(threat, 'duration') else threat.get('duration', 30)
                    target_devices = threat.targetDevices if hasattr(threat, 'targetDevices') else threat.get('targetDevices', [])
                    description = threat.description if hasattr(threat, 'description') else threat.get('description', '')

                    events.append(SimulationEvent(
                        event_type=EventType.THREAT_INJECTED,
                        timestamp=current_time,
                        source_id=threat_id,
                        source_type="threat",
                        data={
                            "threat_type": threat_type,
                            "name": threat_name,
                            "severity": severity,
                            "duration_minutes": duration,
                            "targets": target_devices,
                            "description": description,
                            "scheduled_start_minutes": start_time,
                            "actual_start_minutes": elapsed_minutes,
                        },
                        is_anomaly=True,
                        threat_id=threat_id,
                    ))
                    logger.info(f"Injected user-defined threat: {threat_name} (ID: {threat_id})")

        # Update threat injector if enabled (for auto-generated threats)
        if self.threat_injector:
            try:
                threat_events = self.threat_injector.update(current_time, delta_seconds)
                events.extend(threat_events)
            except Exception as e:
                logger.error(f"Threat injector error: {e}")
                events.append(SimulationEvent(
                    event_type=EventType.SYSTEM_EVENT,
                    timestamp=current_time,
                    source_id="threat_injector",
                    source_type="system",
                    data={"error": str(e)},
                    is_anomaly=True,
                ))

        return events

    def pause(self) -> None:
        """Pause the simulation."""
        if self._running and not self._paused:
            self._paused = True
            self.stats.state = SimulationState.PAUSED
            logger.info("Simulation paused")

    def resume(self) -> None:
        """Resume a paused simulation."""
        if self._running and self._paused:
            self._paused = False
            self.stats.state = SimulationState.RUNNING
            logger.info("Simulation resumed")

    def stop(self) -> None:
        """Stop the simulation."""
        self._stop_requested = True
        self._paused = False
        logger.info("Simulation stop requested")

    def get_events(
        self,
        event_type: Optional[EventType] = None,
        device_id: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        anomalies_only: bool = False,
    ) -> list[SimulationEvent]:
        """
        Get filtered events from the simulation.

        Args:
            event_type: Filter by event type
            device_id: Filter by device ID
            start_time: Filter events after this time
            end_time: Filter events before this time
            anomalies_only: Only return anomaly events

        Returns:
            Filtered list of events
        """
        events = self._events

        if event_type:
            events = [e for e in events if e.event_type == event_type]

        if device_id:
            events = [e for e in events if e.source_id == device_id]

        if start_time:
            events = [e for e in events if e.timestamp >= start_time]

        if end_time:
            events = [e for e in events if e.timestamp <= end_time]

        if anomalies_only:
            events = [e for e in events if e.is_anomaly]

        return events

    def get_device_data(self, device_id: str) -> list[dict[str, Any]]:
        """Get all data generated by a specific device."""
        events = self.get_events(
            event_type=EventType.DEVICE_DATA_GENERATED,
            device_id=device_id,
        )
        return [e.data for e in events]

    def export_events(self) -> list[dict[str, Any]]:
        """Export all events as dictionaries."""
        return [
            {
                "id": e.id,
                "event_type": e.event_type.value if isinstance(e.event_type, Enum) else e.event_type,
                "timestamp": e.timestamp.isoformat(),
                "source_id": e.source_id,
                "source_type": e.source_type,
                "data": e.data,
                "is_anomaly": e.is_anomaly,
                "threat_id": e.threat_id,
            }
            for e in self._events
        ]


# Global engine instance management
_simulation_engine: Optional[SimulationEngine] = None


def get_simulation_engine() -> Optional[SimulationEngine]:
    """Get the current simulation engine instance."""
    return _simulation_engine


def create_simulation_engine(
    home: Home,
    config: Optional[SimulationConfig] = None,
) -> SimulationEngine:
    """Create and set the global simulation engine."""
    global _simulation_engine
    _simulation_engine = SimulationEngine(home, config)
    return _simulation_engine
