"""
Threat Injector

Orchestrates threat injection into the simulation.
Manages threat lifecycle, timing, and event generation.
"""

import random
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Optional
from uuid import uuid4

from loguru import logger

from src.simulation.models import (
    Device,
    DeviceType,
    EventType,
    Home,
    SimulationEvent,
)
from src.simulation.threats.threat_catalog import (
    ThreatCatalog,
    ThreatDefinition,
    ThreatSeverity,
    ThreatType,
)


class ThreatPhase(str, Enum):
    """Phases of a threat attack."""
    RECONNAISSANCE = "reconnaissance"  # Initial probing
    INITIAL_ACCESS = "initial_access"  # Gaining foothold
    EXECUTION = "execution"            # Main attack phase
    PERSISTENCE = "persistence"        # Maintaining access
    EXFILTRATION = "exfiltration"     # Data extraction (if applicable)
    CLEANUP = "cleanup"               # Covering tracks
    COMPLETED = "completed"           # Attack finished


@dataclass
class ThreatConfig:
    """Configuration for threat injection."""
    # Enabled threat types
    enabled_threats: list[ThreatType] = field(default_factory=lambda: list(ThreatType))

    # Timing
    min_time_between_threats_minutes: int = 30
    max_concurrent_threats: int = 3

    # Probability
    threat_probability_per_hour: float = 0.1

    # Severity filter
    max_severity: ThreatSeverity = ThreatSeverity.CRITICAL

    # Target constraints
    target_specific_devices: list[str] = field(default_factory=list)
    exclude_device_types: list[DeviceType] = field(default_factory=list)

    # Randomness
    random_seed: Optional[int] = None


@dataclass
class ThreatInstance:
    """An active threat instance in the simulation."""
    id: str = field(default_factory=lambda: str(uuid4()))
    threat_type: ThreatType = ThreatType.DATA_EXFILTRATION
    definition: Optional[ThreatDefinition] = None

    # Timing
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    planned_duration_minutes: int = 30

    # State
    phase: ThreatPhase = ThreatPhase.RECONNAISSANCE
    phase_start_time: Optional[datetime] = None
    is_active: bool = True
    is_detected: bool = False

    # Targets
    target_device_ids: list[str] = field(default_factory=list)
    compromised_device_ids: list[str] = field(default_factory=list)

    # Progress
    progress: float = 0.0  # 0-1
    events_generated: int = 0
    data_exfiltrated_bytes: int = 0

    # Detection
    detection_events: list[str] = field(default_factory=list)


class ThreatScenario(ABC):
    """Abstract base class for threat scenarios."""

    def __init__(
        self,
        threat_type: ThreatType,
        home: Home,
        seed: Optional[int] = None,
    ):
        self.threat_type = threat_type
        self.home = home
        self.rng = random.Random(seed)
        self.definition = ThreatCatalog.get_threat(threat_type)

    @abstractmethod
    def select_targets(self) -> list[str]:
        """Select target devices for this threat."""
        pass

    @abstractmethod
    def generate_phase_events(
        self,
        instance: ThreatInstance,
        current_time: datetime,
    ) -> list[SimulationEvent]:
        """Generate events for the current threat phase."""
        pass

    @abstractmethod
    def advance_phase(
        self,
        instance: ThreatInstance,
        current_time: datetime,
    ) -> ThreatPhase:
        """Determine the next phase of the attack."""
        pass

    def create_instance(self, current_time: datetime) -> ThreatInstance:
        """Create a new threat instance."""
        targets = self.select_targets()

        if not targets:
            logger.warning(f"No valid targets for {self.threat_type}")

        min_duration, max_duration = self.definition.typical_duration_minutes
        duration = self.rng.randint(min_duration, max_duration)

        return ThreatInstance(
            threat_type=self.threat_type,
            definition=self.definition,
            start_time=current_time,
            planned_duration_minutes=duration,
            phase=ThreatPhase.RECONNAISSANCE,
            phase_start_time=current_time,
            target_device_ids=targets,
        )

    def _create_event(
        self,
        instance: ThreatInstance,
        event_type: EventType,
        source_id: str,
        current_time: datetime,
        data: dict[str, Any],
    ) -> SimulationEvent:
        """Helper to create a threat-related event."""
        return SimulationEvent(
            event_type=event_type,
            timestamp=current_time,
            source_id=source_id,
            source_type="threat",
            data={
                **data,
                "threat_type": self.threat_type.value,
                "threat_phase": instance.phase.value,
            },
            is_anomaly=True,
            threat_id=instance.id,
        )


class ThreatInjector:
    """
    Main class for injecting threats into the simulation.

    Responsibilities:
    - Schedule threat injection based on configuration
    - Manage active threat instances
    - Generate threat-related events
    - Track threat lifecycle
    """

    def __init__(
        self,
        home: Home,
        config: Optional[ThreatConfig] = None,
    ):
        self.home = home
        self.config = config or ThreatConfig()
        self.rng = random.Random(self.config.random_seed)

        # Active threats
        self.active_threats: dict[str, ThreatInstance] = {}
        self.completed_threats: list[ThreatInstance] = []

        # Scenarios registry
        self._scenarios: dict[ThreatType, type[ThreatScenario]] = {}

        # Timing
        self.last_threat_time: Optional[datetime] = None

        # Statistics
        self.total_threats_injected: int = 0
        self.total_events_generated: int = 0

        # Initialize catalog
        ThreatCatalog.initialize()

        logger.info(
            f"ThreatInjector initialized: "
            f"{len(self.config.enabled_threats)} threat types enabled"
        )

    def register_scenario(
        self,
        threat_type: ThreatType,
        scenario_class: type[ThreatScenario],
    ) -> None:
        """Register a threat scenario implementation."""
        self._scenarios[threat_type] = scenario_class

    def register_default_scenarios(self) -> None:
        """Register all default threat scenario implementations."""
        from src.simulation.threats.scenarios import (
            EnergyTheftScenario,
            DataExfiltrationScenario,
            DeviceTamperingScenario,
            UnauthorizedAccessScenario,
            BotnetScenario,
            SurveillanceScenario,
            RansomwareScenario,
            SensorInterceptionScenario,
            FirmwareModificationScenario,
            HVACManipulationScenario,
            SafetySystemBypassScenario,
            CredentialTheftScenario,
            DenialOfServiceScenario,
            ManInTheMiddleScenario,
            DNSSpoofingScenario,
            ARPPoisoningScenario,
            MeterTamperingScenario,
            UsageFalsificationScenario,
            JammingScenario,
            ResourceExhaustionScenario,
            LocationTrackingScenario,
            BehaviorProfilingScenario,
        )

        # Map ThreatType to scenario classes
        scenario_map = {
            ThreatType.ENERGY_THEFT: EnergyTheftScenario,
            ThreatType.DATA_EXFILTRATION: DataExfiltrationScenario,
            ThreatType.DEVICE_TAMPERING: DeviceTamperingScenario,
            ThreatType.UNAUTHORIZED_ACCESS: UnauthorizedAccessScenario,
            ThreatType.BOTNET_RECRUITMENT: BotnetScenario,
            ThreatType.SURVEILLANCE: SurveillanceScenario,
            ThreatType.RANSOMWARE: RansomwareScenario,
            ThreatType.SENSOR_DATA_INTERCEPTION: SensorInterceptionScenario,
            ThreatType.FIRMWARE_MODIFICATION: FirmwareModificationScenario,
            ThreatType.HVAC_MANIPULATION: HVACManipulationScenario,
            ThreatType.SAFETY_SYSTEM_BYPASS: SafetySystemBypassScenario,
            ThreatType.CREDENTIAL_THEFT: CredentialTheftScenario,
            ThreatType.DENIAL_OF_SERVICE: DenialOfServiceScenario,
            ThreatType.MAN_IN_THE_MIDDLE: ManInTheMiddleScenario,
            ThreatType.DNS_SPOOFING: DNSSpoofingScenario,
            ThreatType.ARP_POISONING: ARPPoisoningScenario,
            ThreatType.METER_TAMPERING: MeterTamperingScenario,
            ThreatType.USAGE_FALSIFICATION: UsageFalsificationScenario,
            ThreatType.JAMMING: JammingScenario,
            ThreatType.RESOURCE_EXHAUSTION: ResourceExhaustionScenario,
            ThreatType.LOCATION_TRACKING: LocationTrackingScenario,
            ThreatType.BEHAVIOR_PROFILING: BehaviorProfilingScenario,
        }

        for threat_type, scenario_class in scenario_map.items():
            self.register_scenario(threat_type, scenario_class)

        logger.info(f"Registered {len(scenario_map)} default threat scenarios")

    def update(
        self,
        current_time: datetime,
        delta_seconds: float,
    ) -> list[SimulationEvent]:
        """
        Update threat injection for one simulation tick.

        Args:
            current_time: Current simulation time
            delta_seconds: Seconds since last tick

        Returns:
            List of threat-related events
        """
        events = []

        # Check if we should inject a new threat
        if self._should_inject_threat(current_time):
            new_events = self._inject_random_threat(current_time)
            events.extend(new_events)

        # Update active threats
        for threat_id, instance in list(self.active_threats.items()):
            threat_events = self._update_threat(instance, current_time)
            events.extend(threat_events)

            # Check if threat completed
            if not instance.is_active:
                self.active_threats.pop(threat_id)
                self.completed_threats.append(instance)

        self.total_events_generated += len(events)
        return events

    def _should_inject_threat(self, current_time: datetime) -> bool:
        """Determine if a new threat should be injected."""
        # Check concurrent limit
        if len(self.active_threats) >= self.config.max_concurrent_threats:
            return False

        # Check time since last threat
        if self.last_threat_time:
            elapsed = (current_time - self.last_threat_time).total_seconds() / 60
            if elapsed < self.config.min_time_between_threats_minutes:
                return False

        # Probability check (adjusted for tick frequency)
        # Assuming ~1 tick per second at default compression
        prob_per_tick = self.config.threat_probability_per_hour / 3600
        return self.rng.random() < prob_per_tick

    def _inject_random_threat(
        self,
        current_time: datetime,
    ) -> list[SimulationEvent]:
        """Inject a random threat based on configuration."""
        events = []

        # Select threat type
        available_threats = [
            t for t in self.config.enabled_threats
            if t in self._scenarios
        ]

        if not available_threats:
            logger.warning("No threat scenarios available")
            return events

        # Filter by severity
        filtered_threats = []
        severity_order = [
            ThreatSeverity.LOW,
            ThreatSeverity.MEDIUM,
            ThreatSeverity.HIGH,
            ThreatSeverity.CRITICAL,
        ]
        max_idx = severity_order.index(self.config.max_severity)

        for threat_type in available_threats:
            definition = ThreatCatalog.get_threat(threat_type)
            if definition:
                sev_idx = severity_order.index(definition.severity)
                if sev_idx <= max_idx:
                    filtered_threats.append(threat_type)

        if not filtered_threats:
            return events

        # Select random threat
        threat_type = self.rng.choice(filtered_threats)

        # Create scenario and instance
        scenario_class = self._scenarios[threat_type]
        scenario = scenario_class(threat_type, self.home, self.config.random_seed)
        instance = scenario.create_instance(current_time)

        if not instance.target_device_ids:
            return events

        # Store scenario reference for updates
        instance._scenario = scenario

        # Add to active threats
        self.active_threats[instance.id] = instance
        self.last_threat_time = current_time
        self.total_threats_injected += 1

        # Generate initial events
        event = SimulationEvent(
            event_type=EventType.THREAT_INJECTED,
            timestamp=current_time,
            source_id=instance.id,
            source_type="threat",
            data={
                "threat_type": threat_type.value,
                "severity": instance.definition.severity.value,
                "targets": instance.target_device_ids,
                "planned_duration_minutes": instance.planned_duration_minutes,
            },
            is_anomaly=True,
            threat_id=instance.id,
        )
        events.append(event)

        logger.info(
            f"Injected threat: {threat_type.value} targeting "
            f"{len(instance.target_device_ids)} devices"
        )

        return events

    def _update_threat(
        self,
        instance: ThreatInstance,
        current_time: datetime,
    ) -> list[SimulationEvent]:
        """Update an active threat instance."""
        events = []

        if not hasattr(instance, '_scenario'):
            return events

        scenario = instance._scenario

        # Generate phase events
        phase_events = scenario.generate_phase_events(instance, current_time)
        events.extend(phase_events)
        instance.events_generated += len(phase_events)

        # Check for phase advancement
        new_phase = scenario.advance_phase(instance, current_time)
        if new_phase != instance.phase:
            instance.phase = new_phase
            instance.phase_start_time = current_time

            if new_phase == ThreatPhase.COMPLETED:
                instance.is_active = False
                instance.end_time = current_time

                # Generate completion event
                event = SimulationEvent(
                    event_type=EventType.SYSTEM_EVENT,
                    timestamp=current_time,
                    source_id=instance.id,
                    source_type="threat",
                    data={
                        "event": "threat_completed",
                        "threat_type": instance.threat_type.value,
                        "duration_minutes": (
                            (current_time - instance.start_time).total_seconds() / 60
                            if instance.start_time else 0
                        ),
                        "events_generated": instance.events_generated,
                        "was_detected": instance.is_detected,
                    },
                    is_anomaly=True,
                    threat_id=instance.id,
                )
                events.append(event)

        # Update progress
        if instance.start_time and instance.is_active:
            elapsed = (current_time - instance.start_time).total_seconds() / 60
            instance.progress = min(elapsed / instance.planned_duration_minutes, 1.0)

        return events

    def inject_threat(
        self,
        threat_type: ThreatType,
        current_time: datetime,
        target_device_ids: Optional[list[str]] = None,
    ) -> Optional[ThreatInstance]:
        """Manually inject a specific threat."""
        if threat_type not in self._scenarios:
            logger.error(f"No scenario registered for {threat_type}")
            return None

        scenario_class = self._scenarios[threat_type]
        scenario = scenario_class(threat_type, self.home, self.config.random_seed)
        instance = scenario.create_instance(current_time)

        if target_device_ids:
            instance.target_device_ids = target_device_ids

        instance._scenario = scenario
        self.active_threats[instance.id] = instance
        self.total_threats_injected += 1

        logger.info(f"Manually injected threat: {threat_type.value}")
        return instance

    def stop_threat(self, threat_id: str) -> bool:
        """Stop an active threat."""
        if threat_id in self.active_threats:
            instance = self.active_threats.pop(threat_id)
            instance.is_active = False
            instance.phase = ThreatPhase.COMPLETED
            self.completed_threats.append(instance)
            return True
        return False

    def get_active_threats(self) -> list[ThreatInstance]:
        """Get all active threat instances."""
        return list(self.active_threats.values())

    def get_threat_stats(self) -> dict[str, Any]:
        """Get threat injection statistics."""
        return {
            "total_injected": self.total_threats_injected,
            "total_events": self.total_events_generated,
            "active_count": len(self.active_threats),
            "completed_count": len(self.completed_threats),
            "active_threats": [
                {
                    "id": t.id,
                    "type": t.threat_type.value,
                    "phase": t.phase.value,
                    "progress": t.progress,
                    "targets": len(t.target_device_ids),
                }
                for t in self.active_threats.values()
            ],
            "by_type": self._count_by_type(),
        }

    def _count_by_type(self) -> dict[str, int]:
        """Count threats by type."""
        counts: dict[str, int] = {}
        for instance in self.completed_threats:
            key = instance.threat_type.value
            counts[key] = counts.get(key, 0) + 1
        for instance in self.active_threats.values():
            key = instance.threat_type.value
            counts[key] = counts.get(key, 0) + 1
        return counts
