"""
Ground Truth Labeler

Provides accurate ground truth labels for all simulation events.
Critical for training and evaluating intrusion detection systems.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional
from uuid import uuid4

from loguru import logger

from src.simulation.models import EventType, SimulationEvent
from src.simulation.threats.threat_catalog import (
    ThreatCategory,
    ThreatSeverity,
    ThreatType,
)
from src.simulation.threats.threat_injector import ThreatInstance, ThreatPhase


class LabelType(str, Enum):
    """Types of ground truth labels."""
    BENIGN = "benign"           # Normal activity
    MALICIOUS = "malicious"     # Threat-related activity
    SUSPICIOUS = "suspicious"   # Anomalous but not confirmed threat
    UNKNOWN = "unknown"         # Unable to classify


@dataclass
class ThreatLabel:
    """Ground truth label for a threat event."""
    threat_id: str
    threat_type: ThreatType
    threat_category: ThreatCategory
    severity: ThreatSeverity
    phase: ThreatPhase
    target_device_id: Optional[str] = None
    attack_technique: Optional[str] = None
    mitre_id: Optional[str] = None


@dataclass
class LabeledEvent:
    """An event with ground truth labels."""
    id: str = field(default_factory=lambda: str(uuid4()))
    event_id: str = ""
    timestamp: datetime = field(default_factory=datetime.utcnow)

    # Original event data
    event_type: EventType = EventType.SYSTEM_EVENT
    source_id: str = ""
    source_type: str = ""
    data: dict[str, Any] = field(default_factory=dict)

    # Ground truth labels
    label_type: LabelType = LabelType.UNKNOWN
    is_anomaly: bool = False
    threat_label: Optional[ThreatLabel] = None

    # Confidence and metadata
    label_confidence: float = 1.0  # 1.0 for synthetic data
    label_source: str = "simulation"  # "simulation", "manual", "model"
    label_timestamp: datetime = field(default_factory=datetime.utcnow)

    # Feature hints (useful for ML)
    feature_hints: dict[str, Any] = field(default_factory=dict)


class GroundTruthLabeler:
    """
    Labels simulation events with ground truth for ML training.

    Features:
    - Automatic labeling of threat events
    - Benign event identification
    - Export in various formats (JSON, CSV, ARFF)
    - Statistics on label distribution
    """

    def __init__(self):
        self.labeled_events: list[LabeledEvent] = []
        self.threat_instances: dict[str, ThreatInstance] = {}
        self.threat_events: dict[str, list[str]] = {}  # threat_id -> event_ids

        # Statistics
        self.label_counts: dict[LabelType, int] = {t: 0 for t in LabelType}
        self.threat_type_counts: dict[str, int] = {}

    def register_threat(self, instance: ThreatInstance) -> None:
        """Register a threat instance for labeling."""
        self.threat_instances[instance.id] = instance
        self.threat_events[instance.id] = []

    def label_event(
        self,
        event: SimulationEvent,
    ) -> LabeledEvent:
        """
        Label a simulation event with ground truth.

        Args:
            event: The simulation event to label

        Returns:
            Labeled event with ground truth
        """
        labeled = LabeledEvent(
            event_id=event.id,
            timestamp=event.timestamp,
            event_type=event.event_type,
            source_id=event.source_id,
            source_type=event.source_type,
            data=event.data,
            is_anomaly=event.is_anomaly,
        )

        # Check if this is a threat event
        if event.threat_id and event.threat_id in self.threat_instances:
            labeled = self._label_threat_event(labeled, event)
        elif event.is_anomaly:
            labeled.label_type = LabelType.SUSPICIOUS
            labeled.label_confidence = 0.8
        else:
            labeled.label_type = LabelType.BENIGN
            labeled.label_confidence = 1.0

        # Add feature hints
        labeled.feature_hints = self._extract_feature_hints(event)

        # Update statistics
        self.label_counts[labeled.label_type] += 1

        self.labeled_events.append(labeled)
        return labeled

    def _label_threat_event(
        self,
        labeled: LabeledEvent,
        event: SimulationEvent,
    ) -> LabeledEvent:
        """Label an event associated with a threat."""
        instance = self.threat_instances[event.threat_id]

        labeled.label_type = LabelType.MALICIOUS
        labeled.label_confidence = 1.0

        # Create threat label
        threat_label = ThreatLabel(
            threat_id=instance.id,
            threat_type=instance.threat_type,
            threat_category=instance.definition.category if instance.definition else ThreatCategory.DEVICE_COMPROMISE,
            severity=instance.definition.severity if instance.definition else ThreatSeverity.MEDIUM,
            phase=instance.phase,
        )

        # Add target info if available
        if instance.target_device_ids:
            threat_label.target_device_id = instance.target_device_ids[0]

        # Map to MITRE technique if available
        if instance.definition and instance.definition.mitre_techniques:
            threat_label.mitre_id = instance.definition.mitre_techniques[0]

        # Extract attack technique from event data
        if "action" in event.data:
            threat_label.attack_technique = event.data["action"]

        labeled.threat_label = threat_label

        # Track threat events
        self.threat_events[event.threat_id].append(event.id)

        # Update threat type counts
        threat_key = instance.threat_type.value
        self.threat_type_counts[threat_key] = self.threat_type_counts.get(threat_key, 0) + 1

        return labeled

    def _extract_feature_hints(
        self,
        event: SimulationEvent,
    ) -> dict[str, Any]:
        """Extract feature hints for ML from event."""
        hints = {
            "hour_of_day": event.timestamp.hour,
            "day_of_week": event.timestamp.weekday(),
            "is_weekend": event.timestamp.weekday() >= 5,
            "event_type_code": list(EventType).index(event.event_type),
        }

        # Network features
        if event.event_type == EventType.NETWORK_TRAFFIC:
            hints["has_network_activity"] = True
            hints["bytes_sent"] = event.data.get("bytes_sent", 0)
            hints["bytes_received"] = event.data.get("bytes_received", 0)

        # Device features
        if event.event_type == EventType.DEVICE_STATE_CHANGE:
            hints["has_state_change"] = True
            hints["action"] = event.data.get("action", "unknown")

        # Data features
        if event.event_type == EventType.DEVICE_DATA_GENERATED:
            hints["has_data_generation"] = True

        return hints

    def label_batch(
        self,
        events: list[SimulationEvent],
    ) -> list[LabeledEvent]:
        """Label a batch of events."""
        return [self.label_event(event) for event in events]

    def get_labeled_events(
        self,
        label_type: Optional[LabelType] = None,
        threat_type: Optional[ThreatType] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> list[LabeledEvent]:
        """Get filtered labeled events."""
        events = self.labeled_events

        if label_type:
            events = [e for e in events if e.label_type == label_type]

        if threat_type:
            events = [
                e for e in events
                if e.threat_label and e.threat_label.threat_type == threat_type
            ]

        if start_time:
            events = [e for e in events if e.timestamp >= start_time]

        if end_time:
            events = [e for e in events if e.timestamp <= end_time]

        return events

    def export_to_dict(
        self,
        include_feature_hints: bool = True,
    ) -> list[dict[str, Any]]:
        """Export labeled events as dictionaries."""
        exported = []

        def _enum_to_str(val):
            """Convert enum or string to string."""
            return val.value if hasattr(val, 'value') else str(val)

        for event in self.labeled_events:
            record = {
                "id": event.id,
                "event_id": event.event_id,
                "timestamp": event.timestamp.isoformat(),
                "event_type": _enum_to_str(event.event_type),
                "source_id": event.source_id,
                "source_type": event.source_type,
                "label": _enum_to_str(event.label_type),
                "is_anomaly": event.is_anomaly,
                "label_confidence": event.label_confidence,
            }

            if event.threat_label:
                record["threat_id"] = event.threat_label.threat_id
                record["threat_type"] = _enum_to_str(event.threat_label.threat_type)
                record["threat_category"] = _enum_to_str(event.threat_label.threat_category)
                record["threat_severity"] = _enum_to_str(event.threat_label.severity)
                record["threat_phase"] = _enum_to_str(event.threat_label.phase)
                record["attack_technique"] = event.threat_label.attack_technique
                record["mitre_id"] = event.threat_label.mitre_id

            if include_feature_hints:
                for key, value in event.feature_hints.items():
                    record[f"feature_{key}"] = value

            exported.append(record)

        return exported

    def export_to_csv_format(self) -> tuple[list[str], list[list]]:
        """Export as CSV-compatible format (headers, rows)."""
        if not self.labeled_events:
            return [], []

        # Determine all columns
        sample = self.export_to_dict(include_feature_hints=True)
        headers = list(sample[0].keys()) if sample else []

        rows = []
        for record in sample:
            row = [record.get(h, "") for h in headers]
            rows.append(row)

        return headers, rows

    def get_statistics(self) -> dict[str, Any]:
        """Get labeling statistics."""
        total = len(self.labeled_events)

        return {
            "total_events": total,
            "label_distribution": {
                label.value: count for label, count in self.label_counts.items()
            },
            "label_percentages": {
                label.value: (count / total * 100 if total > 0 else 0)
                for label, count in self.label_counts.items()
            },
            "threat_type_distribution": self.threat_type_counts,
            "threats_tracked": len(self.threat_instances),
            "total_threat_events": sum(
                len(events) for events in self.threat_events.values()
            ),
            "benign_ratio": (
                self.label_counts[LabelType.BENIGN] / total if total > 0 else 0
            ),
            "anomaly_ratio": (
                (self.label_counts[LabelType.MALICIOUS] +
                 self.label_counts[LabelType.SUSPICIOUS]) / total
                if total > 0 else 0
            ),
        }

    def get_threat_timeline(
        self,
        threat_id: str,
    ) -> list[dict[str, Any]]:
        """Get timeline of events for a specific threat."""
        event_ids = self.threat_events.get(threat_id, [])
        timeline = []

        for event in self.labeled_events:
            if event.event_id in event_ids:
                timeline.append({
                    "timestamp": event.timestamp.isoformat(),
                    "event_type": event.event_type.value,
                    "phase": event.threat_label.phase.value if event.threat_label else "unknown",
                    "action": event.data.get("action", "unknown"),
                    "source_id": event.source_id,
                })

        return sorted(timeline, key=lambda x: x["timestamp"])

    def clear(self) -> None:
        """Clear all labeled events."""
        self.labeled_events.clear()
        self.threat_instances.clear()
        self.threat_events.clear()
        self.label_counts = {t: 0 for t in LabelType}
        self.threat_type_counts.clear()
