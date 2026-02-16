"""Threat Injection System - Security threat and anomaly simulation.

Provides realistic IoT security threat scenarios for research:
- Energy theft attacks
- Data exfiltration
- Device tampering
- Unauthorized access
- Botnet recruitment
- Surveillance
- Ransomware
- Sensor interception
- Firmware modification
- HVAC manipulation
- Safety system bypass
- Credential theft
- Denial of service
- Man-in-the-middle attacks
- DNS spoofing
- ARP poisoning
- Meter tampering
- Usage falsification
- Wireless jamming
- Resource exhaustion
- Location tracking
- Behavior profiling
"""

from src.simulation.threats.threat_catalog import (
    ThreatCategory,
    ThreatSeverity,
    ThreatType,
    ThreatDefinition,
    ThreatCatalog,
    ThreatFrequency,
    ThreatPriority,
)
from src.simulation.threats.threat_injector import (
    ThreatInjector,
    ThreatConfig,
    ThreatInstance,
    ThreatPhase,
)
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
    # Network Attack scenarios
    ManInTheMiddleScenario,
    DNSSpoofingScenario,
    ARPPoisoningScenario,
    # Energy Fraud scenarios
    MeterTamperingScenario,
    UsageFalsificationScenario,
    # Service Disruption scenarios
    JammingScenario,
    ResourceExhaustionScenario,
    # Privacy Violation scenarios
    LocationTrackingScenario,
    BehaviorProfilingScenario,
)
from src.simulation.threats.ground_truth import (
    GroundTruthLabeler,
    ThreatLabel,
    LabeledEvent,
)

__all__ = [
    # Catalog
    "ThreatCategory",
    "ThreatSeverity",
    "ThreatType",
    "ThreatDefinition",
    "ThreatCatalog",
    "ThreatFrequency",
    "ThreatPriority",
    # Injector
    "ThreatInjector",
    "ThreatConfig",
    "ThreatInstance",
    "ThreatPhase",
    # Scenarios - Original
    "EnergyTheftScenario",
    "DataExfiltrationScenario",
    "DeviceTamperingScenario",
    "UnauthorizedAccessScenario",
    "BotnetScenario",
    "SurveillanceScenario",
    "RansomwareScenario",
    "SensorInterceptionScenario",
    "FirmwareModificationScenario",
    "HVACManipulationScenario",
    "SafetySystemBypassScenario",
    "CredentialTheftScenario",
    "DenialOfServiceScenario",
    # Scenarios - Network Attack
    "ManInTheMiddleScenario",
    "DNSSpoofingScenario",
    "ARPPoisoningScenario",
    # Scenarios - Energy Fraud
    "MeterTamperingScenario",
    "UsageFalsificationScenario",
    # Scenarios - Service Disruption
    "JammingScenario",
    "ResourceExhaustionScenario",
    # Scenarios - Privacy Violation
    "LocationTrackingScenario",
    "BehaviorProfilingScenario",
    # Ground Truth
    "GroundTruthLabeler",
    "ThreatLabel",
    "LabeledEvent",
]
