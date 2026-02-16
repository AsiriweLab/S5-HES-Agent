"""
Tests for Threat Injection System

Unit tests for threat catalog, injector, scenarios, and ground truth labeling.
"""

from datetime import datetime, timedelta

import pytest

from src.simulation.home import HomeGenerator
from src.simulation.models import (
    DeviceType,
    EventType,
    Home,
    HomeTemplate,
    SimulationEvent,
)
from src.simulation.threats.ground_truth import (
    GroundTruthLabeler,
    LabeledEvent,
    LabelType,
)
from src.simulation.threats.scenarios import (
    BotnetScenario,
    DataExfiltrationScenario,
    DeviceTamperingScenario,
    EnergyTheftScenario,
    UnauthorizedAccessScenario,
)
from src.simulation.threats.threat_catalog import (
    ThreatCatalog,
    ThreatCategory,
    ThreatSeverity,
    ThreatType,
)
from src.simulation.threats.threat_injector import (
    ThreatConfig,
    ThreatInjector,
    ThreatInstance,
    ThreatPhase,
)


# =============================================================================
# Threat Catalog Tests
# =============================================================================


class TestThreatCatalog:
    """Tests for threat catalog."""

    def test_catalog_initialization(self):
        """Test catalog initialization."""
        ThreatCatalog.initialize()

        threats = ThreatCatalog.get_all_threats()
        assert len(threats) > 0

    def test_get_threat_by_type(self):
        """Test getting threat by type."""
        ThreatCatalog.initialize()

        threat = ThreatCatalog.get_threat(ThreatType.ENERGY_THEFT)
        assert threat is not None
        assert threat.threat_type == ThreatType.ENERGY_THEFT
        assert threat.category == ThreatCategory.ENERGY_FRAUD

    def test_get_threats_by_category(self):
        """Test filtering threats by category."""
        ThreatCatalog.initialize()

        data_threats = ThreatCatalog.get_threats_by_category(ThreatCategory.DATA_THEFT)
        assert len(data_threats) > 0
        assert all(t.category == ThreatCategory.DATA_THEFT for t in data_threats)

    def test_get_threats_by_severity(self):
        """Test filtering threats by severity."""
        ThreatCatalog.initialize()

        high_severity = ThreatCatalog.get_threats_by_severity(ThreatSeverity.HIGH)
        assert len(high_severity) > 0
        assert all(t.severity == ThreatSeverity.HIGH for t in high_severity)

    def test_get_threats_for_device(self):
        """Test getting threats for device type."""
        ThreatCatalog.initialize()

        lock_threats = ThreatCatalog.get_threats_for_device(DeviceType.SMART_LOCK)
        assert len(lock_threats) > 0

    def test_threat_definition_completeness(self):
        """Test that threat definitions have required fields."""
        ThreatCatalog.initialize()

        for threat in ThreatCatalog.get_all_threats():
            assert threat.name is not None
            assert threat.description is not None
            assert threat.severity is not None
            assert threat.category is not None
            assert len(threat.target_device_types) > 0

    def test_threat_summary(self):
        """Test threat catalog summary."""
        ThreatCatalog.initialize()

        summary = ThreatCatalog.get_threat_summary()

        assert "total_threats" in summary
        assert "by_category" in summary
        assert "by_severity" in summary
        assert summary["total_threats"] > 0


# =============================================================================
# Threat Scenario Tests
# =============================================================================


class TestThreatScenarios:
    """Tests for threat scenarios."""

    @pytest.fixture
    def home_with_devices(self) -> Home:
        """Create a home with various devices."""
        generator = HomeGenerator(seed=42)
        return generator.generate_from_template(HomeTemplate.FAMILY_HOUSE)

    def test_energy_theft_scenario(self, home_with_devices):
        """Test energy theft scenario."""
        scenario = EnergyTheftScenario(
            ThreatType.ENERGY_THEFT,
            home_with_devices,
            seed=42,
        )

        targets = scenario.select_targets()
        # Should target meters and plugs
        assert isinstance(targets, list)

    def test_energy_theft_instance_creation(self, home_with_devices):
        """Test creating energy theft instance."""
        scenario = EnergyTheftScenario(
            ThreatType.ENERGY_THEFT,
            home_with_devices,
            seed=42,
        )

        current_time = datetime.utcnow()
        instance = scenario.create_instance(current_time)

        assert instance.threat_type == ThreatType.ENERGY_THEFT
        assert instance.phase == ThreatPhase.RECONNAISSANCE
        assert instance.start_time == current_time

    def test_data_exfiltration_scenario(self, home_with_devices):
        """Test data exfiltration scenario."""
        scenario = DataExfiltrationScenario(
            ThreatType.DATA_EXFILTRATION,
            home_with_devices,
            seed=42,
        )

        targets = scenario.select_targets()
        # Should target cameras, speakers, sensors
        assert isinstance(targets, list)

    def test_device_tampering_scenario(self, home_with_devices):
        """Test device tampering scenario."""
        scenario = DeviceTamperingScenario(
            ThreatType.DEVICE_TAMPERING,
            home_with_devices,
            seed=42,
        )

        targets = scenario.select_targets()
        # Should target security-critical devices
        assert isinstance(targets, list)

    def test_unauthorized_access_scenario(self, home_with_devices):
        """Test unauthorized access scenario."""
        scenario = UnauthorizedAccessScenario(
            ThreatType.UNAUTHORIZED_ACCESS,
            home_with_devices,
            seed=42,
        )

        targets = scenario.select_targets()
        assert isinstance(targets, list)

    def test_botnet_scenario(self, home_with_devices):
        """Test botnet recruitment scenario."""
        scenario = BotnetScenario(
            ThreatType.BOTNET_RECRUITMENT,
            home_with_devices,
            seed=42,
        )

        targets = scenario.select_targets()
        assert isinstance(targets, list)

    def test_scenario_phase_advancement(self, home_with_devices):
        """Test phase advancement in scenario."""
        scenario = EnergyTheftScenario(
            ThreatType.ENERGY_THEFT,
            home_with_devices,
            seed=42,
        )

        current_time = datetime.utcnow()
        instance = scenario.create_instance(current_time)

        # Should start in reconnaissance
        assert instance.phase == ThreatPhase.RECONNAISSANCE

        # Advance time
        future_time = current_time + timedelta(minutes=10)
        new_phase = scenario.advance_phase(instance, future_time)

        # Should have advanced
        assert new_phase in ThreatPhase

    def test_scenario_event_generation(self, home_with_devices):
        """Test event generation from scenario."""
        scenario = DataExfiltrationScenario(
            ThreatType.DATA_EXFILTRATION,
            home_with_devices,
            seed=42,
        )

        current_time = datetime.utcnow()
        instance = scenario.create_instance(current_time)

        # Generate events (may be empty due to probability)
        events = scenario.generate_phase_events(instance, current_time)
        assert isinstance(events, list)


# =============================================================================
# Threat Injector Tests
# =============================================================================


class TestThreatInjector:
    """Tests for threat injector."""

    @pytest.fixture
    def home_with_devices(self) -> Home:
        """Create a home with various devices."""
        generator = HomeGenerator(seed=42)
        return generator.generate_from_template(HomeTemplate.FAMILY_HOUSE)

    def test_injector_initialization(self, home_with_devices):
        """Test injector initialization."""
        config = ThreatConfig(random_seed=42)
        injector = ThreatInjector(home_with_devices, config)

        assert injector.home == home_with_devices
        assert len(injector.active_threats) == 0

    def test_register_scenario(self, home_with_devices):
        """Test registering scenario."""
        injector = ThreatInjector(home_with_devices)

        injector.register_scenario(ThreatType.ENERGY_THEFT, EnergyTheftScenario)
        assert ThreatType.ENERGY_THEFT in injector._scenarios

    def test_manual_threat_injection(self, home_with_devices):
        """Test manually injecting a threat."""
        config = ThreatConfig(random_seed=42)
        injector = ThreatInjector(home_with_devices, config)

        # Register scenario
        injector.register_scenario(ThreatType.ENERGY_THEFT, EnergyTheftScenario)

        current_time = datetime.utcnow()
        instance = injector.inject_threat(ThreatType.ENERGY_THEFT, current_time)

        assert instance is not None
        assert instance.threat_type == ThreatType.ENERGY_THEFT
        assert instance.id in injector.active_threats

    def test_threat_update(self, home_with_devices):
        """Test updating threats."""
        config = ThreatConfig(random_seed=42)
        injector = ThreatInjector(home_with_devices, config)
        injector.register_scenario(ThreatType.ENERGY_THEFT, EnergyTheftScenario)

        current_time = datetime.utcnow()
        injector.inject_threat(ThreatType.ENERGY_THEFT, current_time)

        # Update should generate events
        events = injector.update(current_time, 60.0)
        assert isinstance(events, list)

    def test_stop_threat(self, home_with_devices):
        """Test stopping a threat."""
        injector = ThreatInjector(home_with_devices)
        injector.register_scenario(ThreatType.ENERGY_THEFT, EnergyTheftScenario)

        current_time = datetime.utcnow()
        instance = injector.inject_threat(ThreatType.ENERGY_THEFT, current_time)

        # Stop the threat
        success = injector.stop_threat(instance.id)
        assert success
        assert instance.id not in injector.active_threats

    def test_get_active_threats(self, home_with_devices):
        """Test getting active threats."""
        injector = ThreatInjector(home_with_devices)
        injector.register_scenario(ThreatType.ENERGY_THEFT, EnergyTheftScenario)
        injector.register_scenario(ThreatType.DATA_EXFILTRATION, DataExfiltrationScenario)

        current_time = datetime.utcnow()
        injector.inject_threat(ThreatType.ENERGY_THEFT, current_time)
        injector.inject_threat(ThreatType.DATA_EXFILTRATION, current_time)

        active = injector.get_active_threats()
        assert len(active) == 2

    def test_threat_stats(self, home_with_devices):
        """Test threat statistics."""
        injector = ThreatInjector(home_with_devices)
        injector.register_scenario(ThreatType.ENERGY_THEFT, EnergyTheftScenario)

        current_time = datetime.utcnow()
        injector.inject_threat(ThreatType.ENERGY_THEFT, current_time)

        stats = injector.get_threat_stats()

        assert "total_injected" in stats
        assert "active_count" in stats
        assert stats["total_injected"] == 1


# =============================================================================
# Ground Truth Labeler Tests
# =============================================================================


class TestGroundTruthLabeler:
    """Tests for ground truth labeler."""

    def test_labeler_initialization(self):
        """Test labeler initialization."""
        labeler = GroundTruthLabeler()

        assert len(labeler.labeled_events) == 0
        assert all(count == 0 for count in labeler.label_counts.values())

    def test_label_benign_event(self):
        """Test labeling benign event."""
        labeler = GroundTruthLabeler()

        event = SimulationEvent(
            event_type=EventType.DEVICE_STATE_CHANGE,
            timestamp=datetime.utcnow(),
            source_id="device_1",
            source_type="device",
            data={"action": "turn_on"},
            is_anomaly=False,
        )

        labeled = labeler.label_event(event)

        assert labeled.label_type == LabelType.BENIGN
        assert labeled.label_confidence == 1.0
        assert labeled.threat_label is None

    def test_label_suspicious_event(self):
        """Test labeling suspicious event."""
        labeler = GroundTruthLabeler()

        event = SimulationEvent(
            event_type=EventType.DEVICE_STATE_CHANGE,
            timestamp=datetime.utcnow(),
            source_id="device_1",
            source_type="device",
            data={"action": "unusual_command"},
            is_anomaly=True,  # Marked as anomaly but no threat ID
        )

        labeled = labeler.label_event(event)

        assert labeled.label_type == LabelType.SUSPICIOUS

    def test_label_malicious_event(self):
        """Test labeling malicious event."""
        labeler = GroundTruthLabeler()

        # Create and register threat instance
        instance = ThreatInstance(
            id="threat_123",
            threat_type=ThreatType.ENERGY_THEFT,
            phase=ThreatPhase.EXECUTION,
        )
        instance.definition = ThreatCatalog.get_threat(ThreatType.ENERGY_THEFT)
        instance.target_device_ids = ["device_1"]

        labeler.register_threat(instance)

        # Create event associated with threat
        event = SimulationEvent(
            event_type=EventType.DEVICE_STATE_CHANGE,
            timestamp=datetime.utcnow(),
            source_id="device_1",
            source_type="device",
            data={"action": "falsify_reading"},
            is_anomaly=True,
            threat_id="threat_123",
        )

        labeled = labeler.label_event(event)

        assert labeled.label_type == LabelType.MALICIOUS
        assert labeled.threat_label is not None
        assert labeled.threat_label.threat_type == ThreatType.ENERGY_THEFT

    def test_label_batch(self):
        """Test labeling batch of events."""
        labeler = GroundTruthLabeler()

        events = [
            SimulationEvent(
                event_type=EventType.DEVICE_STATE_CHANGE,
                timestamp=datetime.utcnow(),
                source_id=f"device_{i}",
                source_type="device",
                data={},
            )
            for i in range(10)
        ]

        labeled = labeler.label_batch(events)

        assert len(labeled) == 10
        assert all(l.label_type == LabelType.BENIGN for l in labeled)

    def test_feature_hints(self):
        """Test feature hint extraction."""
        labeler = GroundTruthLabeler()

        event = SimulationEvent(
            event_type=EventType.NETWORK_TRAFFIC,
            timestamp=datetime.utcnow(),
            source_id="device_1",
            source_type="device",
            data={"bytes_sent": 1000},
        )

        labeled = labeler.label_event(event)

        assert "hour_of_day" in labeled.feature_hints
        assert "day_of_week" in labeled.feature_hints
        assert labeled.feature_hints.get("has_network_activity") == True

    def test_export_to_dict(self):
        """Test exporting to dictionary."""
        labeler = GroundTruthLabeler()

        # Add some events
        for i in range(5):
            event = SimulationEvent(
                event_type=EventType.DEVICE_STATE_CHANGE,
                timestamp=datetime.utcnow(),
                source_id=f"device_{i}",
                source_type="device",
                data={},
            )
            labeler.label_event(event)

        exported = labeler.export_to_dict()

        assert len(exported) == 5
        assert "label" in exported[0]
        assert "timestamp" in exported[0]

    def test_statistics(self):
        """Test labeling statistics."""
        labeler = GroundTruthLabeler()

        # Add benign events
        for i in range(8):
            event = SimulationEvent(
                event_type=EventType.DEVICE_STATE_CHANGE,
                timestamp=datetime.utcnow(),
                source_id=f"device_{i}",
                source_type="device",
                data={},
            )
            labeler.label_event(event)

        # Add suspicious events
        for i in range(2):
            event = SimulationEvent(
                event_type=EventType.DEVICE_STATE_CHANGE,
                timestamp=datetime.utcnow(),
                source_id=f"device_{i}",
                source_type="device",
                data={},
                is_anomaly=True,
            )
            labeler.label_event(event)

        stats = labeler.get_statistics()

        assert stats["total_events"] == 10
        assert stats["label_distribution"]["benign"] == 8
        assert stats["label_distribution"]["suspicious"] == 2

    def test_filtered_retrieval(self):
        """Test filtered event retrieval."""
        labeler = GroundTruthLabeler()

        # Add events
        base_time = datetime.utcnow()
        for i in range(5):
            event = SimulationEvent(
                event_type=EventType.DEVICE_STATE_CHANGE,
                timestamp=base_time + timedelta(minutes=i),
                source_id=f"device_{i}",
                source_type="device",
                data={},
            )
            labeler.label_event(event)

        # Filter by time
        filtered = labeler.get_labeled_events(
            start_time=base_time + timedelta(minutes=2),
        )

        assert len(filtered) == 3  # Events at minutes 2, 3, 4

    def test_clear(self):
        """Test clearing labeled events."""
        labeler = GroundTruthLabeler()

        # Add some events
        for i in range(5):
            event = SimulationEvent(
                event_type=EventType.DEVICE_STATE_CHANGE,
                timestamp=datetime.utcnow(),
                source_id=f"device_{i}",
                source_type="device",
                data={},
            )
            labeler.label_event(event)

        assert len(labeler.labeled_events) == 5

        labeler.clear()

        assert len(labeler.labeled_events) == 0
        assert all(count == 0 for count in labeler.label_counts.values())
