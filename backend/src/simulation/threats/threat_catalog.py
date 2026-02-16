"""
Threat Catalog

Defines the catalog of IoT security threats for simulation.
Based on real-world IoT attack patterns and academic research.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

from src.simulation.models import DeviceType


class ThreatCategory(str, Enum):
    """High-level threat categories."""
    DATA_THEFT = "data_theft"              # Stealing user data
    DEVICE_COMPROMISE = "device_compromise" # Taking control of devices
    SERVICE_DISRUPTION = "service_disruption"  # DoS, jamming
    PHYSICAL_IMPACT = "physical_impact"    # Real-world consequences
    ENERGY_FRAUD = "energy_fraud"          # Manipulating energy usage
    PRIVACY_VIOLATION = "privacy_violation" # Surveillance, tracking
    NETWORK_ATTACK = "network_attack"      # Network-level attacks


class ThreatSeverity(str, Enum):
    """Threat severity levels."""
    LOW = "low"           # Minor impact, easily detected
    MEDIUM = "medium"     # Moderate impact, some evasion
    HIGH = "high"         # Significant impact, sophisticated
    CRITICAL = "critical" # Severe impact, advanced persistent


class ThreatType(str, Enum):
    """Specific threat types."""
    # Data Theft
    DATA_EXFILTRATION = "data_exfiltration"
    CREDENTIAL_THEFT = "credential_theft"
    SENSOR_DATA_INTERCEPTION = "sensor_data_interception"

    # Device Compromise
    DEVICE_TAMPERING = "device_tampering"
    FIRMWARE_MODIFICATION = "firmware_modification"
    BOTNET_RECRUITMENT = "botnet_recruitment"
    RANSOMWARE = "ransomware"

    # Service Disruption
    DENIAL_OF_SERVICE = "denial_of_service"
    JAMMING = "jamming"
    RESOURCE_EXHAUSTION = "resource_exhaustion"

    # Physical Impact
    UNAUTHORIZED_ACCESS = "unauthorized_access"
    SAFETY_SYSTEM_BYPASS = "safety_system_bypass"
    HVAC_MANIPULATION = "hvac_manipulation"

    # Energy Fraud
    ENERGY_THEFT = "energy_theft"
    METER_TAMPERING = "meter_tampering"
    USAGE_FALSIFICATION = "usage_falsification"

    # Privacy
    SURVEILLANCE = "surveillance"
    LOCATION_TRACKING = "location_tracking"
    BEHAVIOR_PROFILING = "behavior_profiling"

    # Network
    MAN_IN_THE_MIDDLE = "man_in_the_middle"
    DNS_SPOOFING = "dns_spoofing"
    ARP_POISONING = "arp_poisoning"


@dataclass
class ThreatIndicator:
    """Indicator of Compromise (IoC) for threat detection."""
    name: str
    description: str
    detection_method: str  # "network", "device_state", "behavioral", "energy"
    threshold: Optional[float] = None
    pattern: Optional[str] = None


class ThreatFrequency(str, Enum):
    """How frequently a threat type occurs in the wild."""
    VERY_COMMON = "very_common"   # >50% of attacks
    COMMON = "common"              # 20-50% of attacks
    OCCASIONAL = "occasional"      # 5-20% of attacks
    RARE = "rare"                  # <5% of attacks


class ThreatPriority(str, Enum):
    """Priority for threat simulation/research."""
    CRITICAL = "critical"   # Essential for any IoT security research
    HIGH = "high"           # Important for comprehensive testing
    MEDIUM = "medium"       # Useful for specific scenarios
    LOW = "low"             # Edge cases or specialized research


@dataclass
class ThreatDefinition:
    """Complete definition of a threat type."""
    threat_type: ThreatType
    category: ThreatCategory
    name: str
    description: str
    severity: ThreatSeverity

    # Target characteristics
    target_device_types: list[DeviceType] = field(default_factory=list)
    requires_network_access: bool = True
    requires_physical_access: bool = False

    # Attack characteristics
    typical_duration_minutes: tuple[int, int] = (10, 60)  # min, max
    detection_difficulty: float = 0.5  # 0-1, higher = harder to detect
    evasion_techniques: list[str] = field(default_factory=list)

    # Impact
    data_impact: bool = False
    availability_impact: bool = False
    integrity_impact: bool = False
    safety_impact: bool = False
    financial_impact: bool = False

    # Detection
    indicators: list[ThreatIndicator] = field(default_factory=list)

    # MITRE ATT&CK mapping (for academic reference)
    mitre_techniques: list[str] = field(default_factory=list)

    # Academic references
    references: list[str] = field(default_factory=list)

    # Frequency and priority (for simulation weighting)
    frequency: ThreatFrequency = ThreatFrequency.OCCASIONAL
    priority: ThreatPriority = ThreatPriority.MEDIUM


class ThreatCatalog:
    """
    Catalog of predefined threat definitions.

    Based on:
    - OWASP IoT Top 10
    - MITRE ATT&CK for IoT
    - Academic research papers
    - Real-world IoT attack reports
    """

    _threats: dict[ThreatType, ThreatDefinition] = {}

    @classmethod
    def initialize(cls) -> None:
        """Initialize the threat catalog with predefined threats."""
        cls._threats = {
            # Energy Theft
            ThreatType.ENERGY_THEFT: ThreatDefinition(
                threat_type=ThreatType.ENERGY_THEFT,
                category=ThreatCategory.ENERGY_FRAUD,
                name="Energy Theft Attack",
                description=(
                    "Manipulation of smart meter readings to reduce reported "
                    "energy consumption, causing financial loss to utilities."
                ),
                severity=ThreatSeverity.MEDIUM,
                target_device_types=[DeviceType.SMART_METER, DeviceType.SMART_PLUG],
                requires_network_access=True,
                requires_physical_access=False,
                typical_duration_minutes=(60, 1440),  # Hours to days
                detection_difficulty=0.6,
                evasion_techniques=[
                    "gradual_change",
                    "time_of_day_variation",
                    "baseline_mimicking",
                ],
                data_impact=False,
                availability_impact=False,
                integrity_impact=True,
                safety_impact=False,
                financial_impact=True,
                indicators=[
                    ThreatIndicator(
                        name="usage_anomaly",
                        description="Unexpected changes in energy consumption patterns",
                        detection_method="energy",
                        threshold=0.3,
                    ),
                    ThreatIndicator(
                        name="meter_command_injection",
                        description="Unusual commands sent to smart meter",
                        detection_method="network",
                        pattern="SET_READING|CALIBRATE|RESET",
                    ),
                ],
                mitre_techniques=["T1565", "T1495"],
                references=["IEEE_S&P_2021_SmartGrid"],
                frequency=ThreatFrequency.COMMON,
                priority=ThreatPriority.HIGH,
            ),

            # Data Exfiltration
            ThreatType.DATA_EXFILTRATION: ThreatDefinition(
                threat_type=ThreatType.DATA_EXFILTRATION,
                category=ThreatCategory.DATA_THEFT,
                name="Data Exfiltration",
                description=(
                    "Unauthorized extraction of sensitive data from IoT devices "
                    "including sensor readings, user behavior patterns, and credentials."
                ),
                severity=ThreatSeverity.HIGH,
                target_device_types=[
                    DeviceType.SECURITY_CAMERA,
                    DeviceType.SMART_SPEAKER,
                    DeviceType.MOTION_SENSOR,
                    DeviceType.SMART_TV,
                ],
                requires_network_access=True,
                requires_physical_access=False,
                typical_duration_minutes=(5, 120),
                detection_difficulty=0.7,
                evasion_techniques=[
                    "encrypted_channels",
                    "traffic_mimicking",
                    "low_bandwidth",
                    "scheduled_exfil",
                ],
                data_impact=True,
                availability_impact=False,
                integrity_impact=False,
                safety_impact=False,
                financial_impact=True,
                indicators=[
                    ThreatIndicator(
                        name="unusual_outbound_traffic",
                        description="Increased data transfer to unknown destinations",
                        detection_method="network",
                        threshold=1.5,  # 1.5x normal
                    ),
                    ThreatIndicator(
                        name="dns_tunneling",
                        description="Data encoded in DNS queries",
                        detection_method="network",
                        pattern="long_subdomain",
                    ),
                    ThreatIndicator(
                        name="off_hours_activity",
                        description="Device activity during unusual hours",
                        detection_method="behavioral",
                    ),
                ],
                mitre_techniques=["T1041", "T1567", "T1071"],
                references=["USENIX_2020_IoT_Privacy"],
                frequency=ThreatFrequency.VERY_COMMON,
                priority=ThreatPriority.CRITICAL,
            ),

            # Device Tampering
            ThreatType.DEVICE_TAMPERING: ThreatDefinition(
                threat_type=ThreatType.DEVICE_TAMPERING,
                category=ThreatCategory.DEVICE_COMPROMISE,
                name="Device Tampering",
                description=(
                    "Unauthorized modification of device configuration, firmware, "
                    "or operational parameters to alter device behavior."
                ),
                severity=ThreatSeverity.HIGH,
                target_device_types=[
                    DeviceType.SMART_LOCK,
                    DeviceType.THERMOSTAT,
                    DeviceType.SECURITY_CAMERA,
                    DeviceType.SMOKE_DETECTOR,
                ],
                requires_network_access=True,
                requires_physical_access=False,
                typical_duration_minutes=(1, 30),
                detection_difficulty=0.5,
                evasion_techniques=[
                    "legitimate_api_use",
                    "gradual_changes",
                    "timing_attacks",
                ],
                data_impact=False,
                availability_impact=True,
                integrity_impact=True,
                safety_impact=True,
                financial_impact=False,
                indicators=[
                    ThreatIndicator(
                        name="config_change",
                        description="Unexpected configuration modifications",
                        detection_method="device_state",
                    ),
                    ThreatIndicator(
                        name="firmware_version",
                        description="Unauthorized firmware changes",
                        detection_method="device_state",
                    ),
                    ThreatIndicator(
                        name="admin_access",
                        description="Unusual administrative access patterns",
                        detection_method="network",
                    ),
                ],
                mitre_techniques=["T1565.001", "T1542"],
                references=["BlackHat_2019_IoT"],
            ),

            # Unauthorized Access
            ThreatType.UNAUTHORIZED_ACCESS: ThreatDefinition(
                threat_type=ThreatType.UNAUTHORIZED_ACCESS,
                category=ThreatCategory.PHYSICAL_IMPACT,
                name="Unauthorized Physical Access",
                description=(
                    "Exploitation of smart lock vulnerabilities to gain "
                    "unauthorized physical access to the premises."
                ),
                severity=ThreatSeverity.CRITICAL,
                target_device_types=[
                    DeviceType.SMART_LOCK,
                    DeviceType.SMART_DOORBELL,
                ],
                requires_network_access=True,
                requires_physical_access=False,
                typical_duration_minutes=(1, 10),
                detection_difficulty=0.4,
                evasion_techniques=[
                    "replay_attack",
                    "credential_stuffing",
                    "timing_based",
                ],
                data_impact=False,
                availability_impact=False,
                integrity_impact=True,
                safety_impact=True,
                financial_impact=True,
                indicators=[
                    ThreatIndicator(
                        name="failed_unlock_attempts",
                        description="Multiple failed authentication attempts",
                        detection_method="device_state",
                        threshold=3,
                    ),
                    ThreatIndicator(
                        name="unusual_unlock_time",
                        description="Unlock at unusual times",
                        detection_method="behavioral",
                    ),
                    ThreatIndicator(
                        name="unknown_credentials",
                        description="Access with unrecognized credentials",
                        detection_method="device_state",
                    ),
                ],
                mitre_techniques=["T1078", "T1110"],
                references=["DEF_CON_27_SmartLocks"],
            ),

            # Botnet Recruitment
            ThreatType.BOTNET_RECRUITMENT: ThreatDefinition(
                threat_type=ThreatType.BOTNET_RECRUITMENT,
                category=ThreatCategory.DEVICE_COMPROMISE,
                name="Botnet Recruitment",
                description=(
                    "Compromising IoT devices to recruit them into a botnet "
                    "for DDoS attacks, cryptomining, or spam distribution."
                ),
                severity=ThreatSeverity.HIGH,
                target_device_types=[
                    DeviceType.SECURITY_CAMERA,
                    DeviceType.ROUTER,
                    DeviceType.SMART_TV,
                    DeviceType.SMART_PLUG,
                ],
                requires_network_access=True,
                requires_physical_access=False,
                typical_duration_minutes=(5, 30),  # Infection time
                detection_difficulty=0.6,
                evasion_techniques=[
                    "fileless_malware",
                    "encrypted_c2",
                    "domain_generation",
                    "p2p_communication",
                ],
                data_impact=False,
                availability_impact=True,
                integrity_impact=True,
                safety_impact=False,
                financial_impact=True,
                indicators=[
                    ThreatIndicator(
                        name="c2_communication",
                        description="Communication with known C2 servers",
                        detection_method="network",
                    ),
                    ThreatIndicator(
                        name="scan_activity",
                        description="Port scanning from device",
                        detection_method="network",
                    ),
                    ThreatIndicator(
                        name="resource_spike",
                        description="Unusual CPU/memory usage",
                        detection_method="device_state",
                        threshold=0.8,
                    ),
                ],
                mitre_techniques=["T1583.005", "T1595"],
                references=["Mirai_Botnet_Analysis_2016"],
            ),

            # Surveillance
            ThreatType.SURVEILLANCE: ThreatDefinition(
                threat_type=ThreatType.SURVEILLANCE,
                category=ThreatCategory.PRIVACY_VIOLATION,
                name="Unauthorized Surveillance",
                description=(
                    "Hijacking cameras and microphones for unauthorized "
                    "monitoring of inhabitants' activities."
                ),
                severity=ThreatSeverity.HIGH,
                target_device_types=[
                    DeviceType.SECURITY_CAMERA,
                    DeviceType.SMART_SPEAKER,
                    DeviceType.SMART_DOORBELL,
                    DeviceType.SMART_TV,
                ],
                requires_network_access=True,
                requires_physical_access=False,
                typical_duration_minutes=(30, 1440),
                detection_difficulty=0.8,
                evasion_techniques=[
                    "low_bandwidth_stream",
                    "encrypted_exfil",
                    "scheduled_recording",
                    "motion_triggered",
                ],
                data_impact=True,
                availability_impact=False,
                integrity_impact=False,
                safety_impact=True,
                financial_impact=False,
                indicators=[
                    ThreatIndicator(
                        name="camera_active_unusual",
                        description="Camera active during unexpected times",
                        detection_method="device_state",
                    ),
                    ThreatIndicator(
                        name="stream_destination",
                        description="Video stream to unknown destination",
                        detection_method="network",
                    ),
                    ThreatIndicator(
                        name="mic_activation",
                        description="Microphone activated without user action",
                        detection_method="device_state",
                    ),
                ],
                mitre_techniques=["T1125", "T1123"],
                references=["IoT_Privacy_Study_2022"],
            ),

            # Denial of Service
            ThreatType.DENIAL_OF_SERVICE: ThreatDefinition(
                threat_type=ThreatType.DENIAL_OF_SERVICE,
                category=ThreatCategory.SERVICE_DISRUPTION,
                name="Denial of Service",
                description=(
                    "Rendering IoT devices or services unavailable through "
                    "resource exhaustion or network flooding."
                ),
                severity=ThreatSeverity.MEDIUM,
                target_device_types=[
                    DeviceType.HUB,
                    DeviceType.ROUTER,
                    DeviceType.SMART_LOCK,
                    DeviceType.THERMOSTAT,
                ],
                requires_network_access=True,
                requires_physical_access=False,
                typical_duration_minutes=(5, 60),
                detection_difficulty=0.3,
                evasion_techniques=[
                    "amplification",
                    "slowloris",
                    "fragmentation",
                ],
                data_impact=False,
                availability_impact=True,
                integrity_impact=False,
                safety_impact=True,
                financial_impact=True,
                indicators=[
                    ThreatIndicator(
                        name="traffic_spike",
                        description="Sudden increase in network traffic",
                        detection_method="network",
                        threshold=10.0,
                    ),
                    ThreatIndicator(
                        name="device_unresponsive",
                        description="Device not responding to commands",
                        detection_method="device_state",
                    ),
                    ThreatIndicator(
                        name="connection_flood",
                        description="Excessive connection attempts",
                        detection_method="network",
                    ),
                ],
                mitre_techniques=["T1499", "T1498"],
                references=["DDoS_IoT_Survey_2021"],
            ),

            # Man in the Middle
            ThreatType.MAN_IN_THE_MIDDLE: ThreatDefinition(
                threat_type=ThreatType.MAN_IN_THE_MIDDLE,
                category=ThreatCategory.NETWORK_ATTACK,
                name="Man-in-the-Middle Attack",
                description=(
                    "Intercepting and potentially modifying communications "
                    "between IoT devices and their control systems."
                ),
                severity=ThreatSeverity.HIGH,
                target_device_types=[
                    DeviceType.HUB,
                    DeviceType.ROUTER,
                    DeviceType.SMART_LOCK,
                    DeviceType.THERMOSTAT,
                ],
                requires_network_access=True,
                requires_physical_access=False,
                typical_duration_minutes=(10, 120),
                detection_difficulty=0.7,
                evasion_techniques=[
                    "ssl_stripping",
                    "certificate_spoofing",
                    "traffic_injection",
                ],
                data_impact=True,
                availability_impact=False,
                integrity_impact=True,
                safety_impact=True,
                financial_impact=True,
                indicators=[
                    ThreatIndicator(
                        name="cert_mismatch",
                        description="Certificate validation failures",
                        detection_method="network",
                    ),
                    ThreatIndicator(
                        name="arp_anomaly",
                        description="ARP table inconsistencies",
                        detection_method="network",
                    ),
                    ThreatIndicator(
                        name="latency_increase",
                        description="Increased communication latency",
                        detection_method="network",
                        threshold=2.0,
                    ),
                ],
                mitre_techniques=["T1557", "T1040"],
                references=["Network_Security_IoT_2020"],
            ),

            # Credential Theft
            ThreatType.CREDENTIAL_THEFT: ThreatDefinition(
                threat_type=ThreatType.CREDENTIAL_THEFT,
                category=ThreatCategory.DATA_THEFT,
                name="Credential Theft",
                description=(
                    "Stealing authentication credentials from IoT devices "
                    "or hub systems through various attack vectors including "
                    "phishing, keylogging, or memory scraping."
                ),
                severity=ThreatSeverity.HIGH,
                target_device_types=[
                    DeviceType.HUB,
                    DeviceType.ROUTER,
                    DeviceType.SMART_LOCK,
                    DeviceType.SECURITY_KEYPAD,
                    DeviceType.SMART_DOORBELL,
                ],
                requires_network_access=True,
                requires_physical_access=False,
                typical_duration_minutes=(5, 60),
                detection_difficulty=0.7,
                evasion_techniques=[
                    "encrypted_exfil",
                    "credential_caching",
                    "token_theft",
                ],
                data_impact=True,
                availability_impact=False,
                integrity_impact=True,
                safety_impact=True,
                financial_impact=True,
                indicators=[
                    ThreatIndicator(
                        name="brute_force_attempts",
                        description="Multiple failed authentication attempts",
                        detection_method="device_state",
                        threshold=5,
                    ),
                    ThreatIndicator(
                        name="credential_dump",
                        description="Attempts to access credential storage",
                        detection_method="device_state",
                    ),
                    ThreatIndicator(
                        name="unusual_auth_source",
                        description="Authentication from unknown IP/device",
                        detection_method="network",
                    ),
                ],
                mitre_techniques=["T1110", "T1555", "T1552"],
                references=["IoT_Auth_Attacks_2022"],
            ),

            # Sensor Data Interception
            ThreatType.SENSOR_DATA_INTERCEPTION: ThreatDefinition(
                threat_type=ThreatType.SENSOR_DATA_INTERCEPTION,
                category=ThreatCategory.DATA_THEFT,
                name="Sensor Data Interception",
                description=(
                    "Intercepting and capturing sensor data streams from IoT "
                    "devices to gather intelligence about occupancy patterns, "
                    "environmental conditions, or user behavior."
                ),
                severity=ThreatSeverity.MEDIUM,
                target_device_types=[
                    DeviceType.MOTION_SENSOR,
                    DeviceType.DOOR_SENSOR,
                    DeviceType.WINDOW_SENSOR,
                    DeviceType.TEMPERATURE_SENSOR,
                    DeviceType.HUMIDITY_SENSOR,
                    DeviceType.AIR_QUALITY_MONITOR,
                    DeviceType.DRIVEWAY_SENSOR,
                    DeviceType.GARDEN_SENSOR,
                ],
                requires_network_access=True,
                requires_physical_access=False,
                typical_duration_minutes=(30, 480),
                detection_difficulty=0.6,
                evasion_techniques=[
                    "passive_monitoring",
                    "protocol_mimicking",
                    "selective_capture",
                ],
                data_impact=True,
                availability_impact=False,
                integrity_impact=False,
                safety_impact=False,
                financial_impact=False,
                indicators=[
                    ThreatIndicator(
                        name="promiscuous_mode",
                        description="Device in promiscuous mode capturing traffic",
                        detection_method="network",
                    ),
                    ThreatIndicator(
                        name="data_mirroring",
                        description="Sensor data being duplicated to unknown destination",
                        detection_method="network",
                    ),
                    ThreatIndicator(
                        name="packet_injection",
                        description="Injected packets on sensor network",
                        detection_method="network",
                    ),
                ],
                mitre_techniques=["T1040", "T1557"],
                references=["Sensor_Security_Survey_2021"],
            ),

            # Firmware Modification
            ThreatType.FIRMWARE_MODIFICATION: ThreatDefinition(
                threat_type=ThreatType.FIRMWARE_MODIFICATION,
                category=ThreatCategory.DEVICE_COMPROMISE,
                name="Malicious Firmware Modification",
                description=(
                    "Replacing or modifying device firmware with malicious code "
                    "to gain persistent control, create backdoors, or alter "
                    "device functionality."
                ),
                severity=ThreatSeverity.CRITICAL,
                target_device_types=[
                    DeviceType.ROUTER,
                    DeviceType.SECURITY_CAMERA,
                    DeviceType.SMART_LOCK,
                    DeviceType.HUB,
                    DeviceType.THERMOSTAT,
                    DeviceType.SMART_TV,
                ],
                requires_network_access=True,
                requires_physical_access=False,
                typical_duration_minutes=(15, 90),
                detection_difficulty=0.8,
                evasion_techniques=[
                    "signed_firmware_bypass",
                    "secure_boot_circumvention",
                    "rootkit_installation",
                ],
                data_impact=True,
                availability_impact=True,
                integrity_impact=True,
                safety_impact=True,
                financial_impact=True,
                indicators=[
                    ThreatIndicator(
                        name="firmware_hash_mismatch",
                        description="Firmware hash doesn't match known good version",
                        detection_method="device_state",
                    ),
                    ThreatIndicator(
                        name="unexpected_reboot",
                        description="Device rebooted unexpectedly during update",
                        detection_method="device_state",
                    ),
                    ThreatIndicator(
                        name="update_traffic",
                        description="Firmware update from unknown source",
                        detection_method="network",
                    ),
                ],
                mitre_techniques=["T1542", "T1495", "T1601"],
                references=["Firmware_Attack_Analysis_2023"],
            ),

            # Ransomware
            ThreatType.RANSOMWARE: ThreatDefinition(
                threat_type=ThreatType.RANSOMWARE,
                category=ThreatCategory.DEVICE_COMPROMISE,
                name="IoT Ransomware",
                description=(
                    "Locking or disabling IoT devices and demanding payment "
                    "for restoration. Can target smart locks, thermostats, or "
                    "entire smart home systems."
                ),
                severity=ThreatSeverity.CRITICAL,
                target_device_types=[
                    DeviceType.SMART_LOCK,
                    DeviceType.THERMOSTAT,
                    DeviceType.HUB,
                    DeviceType.SECURITY_KEYPAD,
                    DeviceType.GARAGE_DOOR_CONTROLLER,
                ],
                requires_network_access=True,
                requires_physical_access=False,
                typical_duration_minutes=(5, 30),
                detection_difficulty=0.4,
                evasion_techniques=[
                    "encryption",
                    "wiper_threat",
                    "timer_delay",
                ],
                data_impact=True,
                availability_impact=True,
                integrity_impact=True,
                safety_impact=True,
                financial_impact=True,
                indicators=[
                    ThreatIndicator(
                        name="mass_encryption",
                        description="Multiple devices encrypted simultaneously",
                        detection_method="device_state",
                    ),
                    ThreatIndicator(
                        name="ransom_message",
                        description="Ransom demand displayed or transmitted",
                        detection_method="device_state",
                    ),
                    ThreatIndicator(
                        name="c2_communication",
                        description="Communication with ransomware C2 server",
                        detection_method="network",
                    ),
                ],
                mitre_techniques=["T1486", "T1490"],
                references=["IoT_Ransomware_Study_2022"],
            ),

            # Jamming
            ThreatType.JAMMING: ThreatDefinition(
                threat_type=ThreatType.JAMMING,
                category=ThreatCategory.SERVICE_DISRUPTION,
                name="Wireless Jamming",
                description=(
                    "Disrupting wireless communications between IoT devices "
                    "by broadcasting interference signals on WiFi, Zigbee, "
                    "Z-Wave, or Bluetooth frequencies."
                ),
                severity=ThreatSeverity.MEDIUM,
                target_device_types=[
                    DeviceType.MOTION_SENSOR,
                    DeviceType.DOOR_SENSOR,
                    DeviceType.WINDOW_SENSOR,
                    DeviceType.SMART_LOCK,
                    DeviceType.SECURITY_CAMERA,
                    DeviceType.SMOKE_DETECTOR,
                ],
                requires_network_access=False,
                requires_physical_access=False,  # But requires proximity
                typical_duration_minutes=(5, 120),
                detection_difficulty=0.3,
                evasion_techniques=[
                    "intermittent_jamming",
                    "selective_frequency",
                    "pulse_jamming",
                ],
                data_impact=False,
                availability_impact=True,
                integrity_impact=False,
                safety_impact=True,
                financial_impact=True,
                indicators=[
                    ThreatIndicator(
                        name="signal_loss",
                        description="Multiple devices losing connectivity",
                        detection_method="network",
                    ),
                    ThreatIndicator(
                        name="noise_floor",
                        description="Elevated noise floor on wireless channels",
                        detection_method="network",
                    ),
                    ThreatIndicator(
                        name="packet_loss",
                        description="Abnormally high packet loss rate",
                        detection_method="network",
                        threshold=0.5,
                    ),
                ],
                mitre_techniques=["T1464"],
                references=["Wireless_Jamming_Attacks_2021"],
            ),

            # Resource Exhaustion
            ThreatType.RESOURCE_EXHAUSTION: ThreatDefinition(
                threat_type=ThreatType.RESOURCE_EXHAUSTION,
                category=ThreatCategory.SERVICE_DISRUPTION,
                name="Resource Exhaustion Attack",
                description=(
                    "Exhausting device resources (CPU, memory, storage, battery) "
                    "to degrade performance or cause device failure."
                ),
                severity=ThreatSeverity.MEDIUM,
                target_device_types=[
                    DeviceType.HUB,
                    DeviceType.SECURITY_CAMERA,
                    DeviceType.SMART_SPEAKER,
                    DeviceType.MOTION_SENSOR,
                    DeviceType.SMART_DOORBELL,
                ],
                requires_network_access=True,
                requires_physical_access=False,
                typical_duration_minutes=(10, 180),
                detection_difficulty=0.5,
                evasion_techniques=[
                    "slowloris",
                    "memory_leak",
                    "cpu_intensive_ops",
                ],
                data_impact=False,
                availability_impact=True,
                integrity_impact=False,
                safety_impact=True,
                financial_impact=True,
                indicators=[
                    ThreatIndicator(
                        name="high_cpu",
                        description="Sustained high CPU usage",
                        detection_method="device_state",
                        threshold=0.9,
                    ),
                    ThreatIndicator(
                        name="memory_pressure",
                        description="Low available memory",
                        detection_method="device_state",
                        threshold=0.95,
                    ),
                    ThreatIndicator(
                        name="battery_drain",
                        description="Abnormal battery consumption",
                        detection_method="device_state",
                        threshold=2.0,
                    ),
                ],
                mitre_techniques=["T1499"],
                references=["Resource_Exhaustion_IoT_2020"],
            ),

            # Safety System Bypass
            ThreatType.SAFETY_SYSTEM_BYPASS: ThreatDefinition(
                threat_type=ThreatType.SAFETY_SYSTEM_BYPASS,
                category=ThreatCategory.PHYSICAL_IMPACT,
                name="Safety System Bypass",
                description=(
                    "Disabling or bypassing safety systems like smoke detectors, "
                    "carbon monoxide monitors, water leak sensors, or security alarms."
                ),
                severity=ThreatSeverity.CRITICAL,
                target_device_types=[
                    DeviceType.SMOKE_DETECTOR,
                    DeviceType.CO_DETECTOR,
                    DeviceType.WATER_LEAK_SENSOR,
                    DeviceType.SECURITY_KEYPAD,
                    DeviceType.GLASS_BREAK_SENSOR,
                    DeviceType.SIREN_ALARM,
                ],
                requires_network_access=True,
                requires_physical_access=False,
                typical_duration_minutes=(1, 30),
                detection_difficulty=0.5,
                evasion_techniques=[
                    "gradual_threshold_change",
                    "silent_disable",
                    "sensor_spoofing",
                ],
                data_impact=False,
                availability_impact=True,
                integrity_impact=True,
                safety_impact=True,
                financial_impact=True,
                indicators=[
                    ThreatIndicator(
                        name="sensor_offline",
                        description="Safety sensor went offline unexpectedly",
                        detection_method="device_state",
                    ),
                    ThreatIndicator(
                        name="threshold_modified",
                        description="Detection thresholds modified",
                        detection_method="device_state",
                    ),
                    ThreatIndicator(
                        name="tamper_alert",
                        description="Device tamper detection triggered",
                        detection_method="device_state",
                    ),
                ],
                mitre_techniques=["T1565", "T1489"],
                references=["Safety_System_Vulnerabilities_2022"],
            ),

            # HVAC Manipulation
            ThreatType.HVAC_MANIPULATION: ThreatDefinition(
                threat_type=ThreatType.HVAC_MANIPULATION,
                category=ThreatCategory.PHYSICAL_IMPACT,
                name="HVAC System Manipulation",
                description=(
                    "Maliciously controlling heating, ventilation, and air "
                    "conditioning systems to cause discomfort, property damage, "
                    "or energy waste."
                ),
                severity=ThreatSeverity.MEDIUM,
                target_device_types=[
                    DeviceType.THERMOSTAT,
                    DeviceType.HVAC_CONTROLLER,
                    DeviceType.AIR_PURIFIER,
                    DeviceType.SMART_HUMIDIFIER,
                    DeviceType.SMART_DEHUMIDIFIER,
                    DeviceType.CEILING_FAN_LIGHT,
                ],
                requires_network_access=True,
                requires_physical_access=False,
                typical_duration_minutes=(30, 480),
                detection_difficulty=0.4,
                evasion_techniques=[
                    "gradual_change",
                    "schedule_mimicking",
                    "comfort_range_abuse",
                ],
                data_impact=False,
                availability_impact=True,
                integrity_impact=True,
                safety_impact=True,
                financial_impact=True,
                indicators=[
                    ThreatIndicator(
                        name="extreme_setpoint",
                        description="Temperature set to extreme values",
                        detection_method="device_state",
                    ),
                    ThreatIndicator(
                        name="schedule_override",
                        description="Scheduled settings being overridden",
                        detection_method="device_state",
                    ),
                    ThreatIndicator(
                        name="energy_spike",
                        description="Unusual HVAC energy consumption",
                        detection_method="energy",
                        threshold=2.0,
                    ),
                ],
                mitre_techniques=["T1565"],
                references=["Smart_HVAC_Security_2021"],
            ),

            # Meter Tampering
            ThreatType.METER_TAMPERING: ThreatDefinition(
                threat_type=ThreatType.METER_TAMPERING,
                category=ThreatCategory.ENERGY_FRAUD,
                name="Smart Meter Tampering",
                description=(
                    "Direct manipulation of smart meter hardware or software "
                    "to falsify energy readings or bypass metering entirely."
                ),
                severity=ThreatSeverity.HIGH,
                target_device_types=[
                    DeviceType.SMART_METER,
                    DeviceType.ENERGY_MONITOR,
                ],
                requires_network_access=True,
                requires_physical_access=True,
                typical_duration_minutes=(30, 120),
                detection_difficulty=0.7,
                evasion_techniques=[
                    "calibration_manipulation",
                    "pulse_interception",
                    "register_modification",
                ],
                data_impact=False,
                availability_impact=False,
                integrity_impact=True,
                safety_impact=False,
                financial_impact=True,
                indicators=[
                    ThreatIndicator(
                        name="calibration_change",
                        description="Meter calibration values modified",
                        detection_method="device_state",
                    ),
                    ThreatIndicator(
                        name="seal_tamper",
                        description="Physical seal tampering detected",
                        detection_method="device_state",
                    ),
                    ThreatIndicator(
                        name="reading_discontinuity",
                        description="Sudden jump or drop in readings",
                        detection_method="energy",
                    ),
                ],
                mitre_techniques=["T1565"],
                references=["Smart_Meter_Fraud_2020"],
            ),

            # Usage Falsification
            ThreatType.USAGE_FALSIFICATION: ThreatDefinition(
                threat_type=ThreatType.USAGE_FALSIFICATION,
                category=ThreatCategory.ENERGY_FRAUD,
                name="Energy Usage Falsification",
                description=(
                    "Manipulating reported energy usage data through software "
                    "attacks on energy monitoring systems."
                ),
                severity=ThreatSeverity.MEDIUM,
                target_device_types=[
                    DeviceType.SMART_METER,
                    DeviceType.SMART_PLUG,
                    DeviceType.ENERGY_MONITOR,
                ],
                requires_network_access=True,
                requires_physical_access=False,
                typical_duration_minutes=(60, 1440),
                detection_difficulty=0.6,
                evasion_techniques=[
                    "data_injection",
                    "report_modification",
                    "time_shifting",
                ],
                data_impact=False,
                availability_impact=False,
                integrity_impact=True,
                safety_impact=False,
                financial_impact=True,
                indicators=[
                    ThreatIndicator(
                        name="usage_pattern_anomaly",
                        description="Usage pattern deviates from historical norm",
                        detection_method="energy",
                        threshold=0.4,
                    ),
                    ThreatIndicator(
                        name="negative_usage",
                        description="Negative usage values reported",
                        detection_method="energy",
                    ),
                    ThreatIndicator(
                        name="timestamp_anomaly",
                        description="Report timestamps don't match expected sequence",
                        detection_method="device_state",
                    ),
                ],
                mitre_techniques=["T1565"],
                references=["Energy_Data_Integrity_2021"],
            ),

            # Location Tracking
            ThreatType.LOCATION_TRACKING: ThreatDefinition(
                threat_type=ThreatType.LOCATION_TRACKING,
                category=ThreatCategory.PRIVACY_VIOLATION,
                name="Location Tracking",
                description=(
                    "Tracking occupant location and movement patterns within "
                    "the home through motion sensors, presence detection, and "
                    "device usage patterns."
                ),
                severity=ThreatSeverity.MEDIUM,
                target_device_types=[
                    DeviceType.MOTION_SENSOR,
                    DeviceType.DRIVEWAY_SENSOR,
                    DeviceType.DRIVEWAY_SENSOR,
                    DeviceType.SMART_SPEAKER,
                    DeviceType.SMART_LIGHT,
                    DeviceType.SMART_PLUG,
                ],
                requires_network_access=True,
                requires_physical_access=False,
                typical_duration_minutes=(60, 1440),
                detection_difficulty=0.8,
                evasion_techniques=[
                    "passive_collection",
                    "correlation_analysis",
                    "pattern_inference",
                ],
                data_impact=True,
                availability_impact=False,
                integrity_impact=False,
                safety_impact=True,
                financial_impact=False,
                indicators=[
                    ThreatIndicator(
                        name="sensor_polling",
                        description="Frequent polling of location-aware sensors",
                        detection_method="network",
                    ),
                    ThreatIndicator(
                        name="data_aggregation",
                        description="Multiple sensor data being collected together",
                        detection_method="network",
                    ),
                    ThreatIndicator(
                        name="external_report",
                        description="Location data sent to external server",
                        detection_method="network",
                    ),
                ],
                mitre_techniques=["T1430"],
                references=["Indoor_Location_Privacy_2022"],
            ),

            # Behavior Profiling
            ThreatType.BEHAVIOR_PROFILING: ThreatDefinition(
                threat_type=ThreatType.BEHAVIOR_PROFILING,
                category=ThreatCategory.PRIVACY_VIOLATION,
                name="Behavior Profiling",
                description=(
                    "Building detailed profiles of occupant behavior through "
                    "analysis of device usage patterns, schedules, and preferences."
                ),
                severity=ThreatSeverity.MEDIUM,
                target_device_types=[
                    DeviceType.SMART_TV,
                    DeviceType.SMART_SPEAKER,
                    DeviceType.SMART_REFRIGERATOR,
                    DeviceType.SMART_OVEN,
                    DeviceType.SMART_COFFEE_MAKER,
                    DeviceType.SMART_LIGHT,
                ],
                requires_network_access=True,
                requires_physical_access=False,
                typical_duration_minutes=(120, 2880),
                detection_difficulty=0.9,
                evasion_techniques=[
                    "long_term_collection",
                    "statistical_analysis",
                    "machine_learning",
                ],
                data_impact=True,
                availability_impact=False,
                integrity_impact=False,
                safety_impact=True,
                financial_impact=True,
                indicators=[
                    ThreatIndicator(
                        name="usage_logging",
                        description="Detailed usage logs being collected",
                        detection_method="device_state",
                    ),
                    ThreatIndicator(
                        name="pattern_extraction",
                        description="Pattern analysis on device data",
                        detection_method="behavioral",
                    ),
                    ThreatIndicator(
                        name="profile_export",
                        description="User profile data being transmitted",
                        detection_method="network",
                    ),
                ],
                mitre_techniques=["T1119"],
                references=["IoT_Behavior_Privacy_2022"],
            ),

            # DNS Spoofing
            ThreatType.DNS_SPOOFING: ThreatDefinition(
                threat_type=ThreatType.DNS_SPOOFING,
                category=ThreatCategory.NETWORK_ATTACK,
                name="DNS Spoofing Attack",
                description=(
                    "Poisoning DNS responses to redirect IoT device traffic "
                    "to malicious servers for data interception or malware delivery."
                ),
                severity=ThreatSeverity.HIGH,
                target_device_types=[
                    DeviceType.ROUTER,
                    DeviceType.HUB,
                    DeviceType.SMART_TV,
                    DeviceType.SECURITY_CAMERA,
                ],
                requires_network_access=True,
                requires_physical_access=False,
                typical_duration_minutes=(10, 180),
                detection_difficulty=0.6,
                evasion_techniques=[
                    "cache_poisoning",
                    "ttl_manipulation",
                    "selective_spoofing",
                ],
                data_impact=True,
                availability_impact=True,
                integrity_impact=True,
                safety_impact=False,
                financial_impact=True,
                indicators=[
                    ThreatIndicator(
                        name="dns_mismatch",
                        description="DNS responses don't match expected IPs",
                        detection_method="network",
                    ),
                    ThreatIndicator(
                        name="ttl_anomaly",
                        description="Unusual DNS record TTL values",
                        detection_method="network",
                    ),
                    ThreatIndicator(
                        name="redirect_detected",
                        description="Traffic redirected to unknown servers",
                        detection_method="network",
                    ),
                ],
                mitre_techniques=["T1557.004"],
                references=["DNS_Security_IoT_2021"],
            ),

            # ARP Poisoning
            ThreatType.ARP_POISONING: ThreatDefinition(
                threat_type=ThreatType.ARP_POISONING,
                category=ThreatCategory.NETWORK_ATTACK,
                name="ARP Cache Poisoning",
                description=(
                    "Sending falsified ARP messages to link attacker's MAC "
                    "address with legitimate network devices, enabling traffic "
                    "interception."
                ),
                severity=ThreatSeverity.HIGH,
                target_device_types=[
                    DeviceType.ROUTER,
                    DeviceType.HUB,
                    DeviceType.SECURITY_CAMERA,
                    DeviceType.SMART_LOCK,
                ],
                requires_network_access=True,
                requires_physical_access=False,
                typical_duration_minutes=(5, 120),
                detection_difficulty=0.5,
                evasion_techniques=[
                    "gratuitous_arp",
                    "targeted_poisoning",
                    "timing_attack",
                ],
                data_impact=True,
                availability_impact=False,
                integrity_impact=True,
                safety_impact=True,
                financial_impact=True,
                indicators=[
                    ThreatIndicator(
                        name="arp_table_change",
                        description="Unexpected ARP table modifications",
                        detection_method="network",
                    ),
                    ThreatIndicator(
                        name="duplicate_mac",
                        description="Multiple IPs with same MAC address",
                        detection_method="network",
                    ),
                    ThreatIndicator(
                        name="arp_flood",
                        description="Excessive ARP traffic detected",
                        detection_method="network",
                    ),
                ],
                mitre_techniques=["T1557.002"],
                references=["ARP_Attacks_LAN_2020"],
            ),
        }

    @classmethod
    def get_threat(cls, threat_type: ThreatType) -> Optional[ThreatDefinition]:
        """Get a threat definition by type."""
        if not cls._threats:
            cls.initialize()
        return cls._threats.get(threat_type)

    @classmethod
    def get_all_threats(cls) -> list[ThreatDefinition]:
        """Get all threat definitions."""
        if not cls._threats:
            cls.initialize()
        return list(cls._threats.values())

    @classmethod
    def get_threats_by_category(cls, category: ThreatCategory) -> list[ThreatDefinition]:
        """Get threats by category."""
        if not cls._threats:
            cls.initialize()
        return [t for t in cls._threats.values() if t.category == category]

    @classmethod
    def get_threats_by_severity(cls, severity: ThreatSeverity) -> list[ThreatDefinition]:
        """Get threats by severity level."""
        if not cls._threats:
            cls.initialize()
        return [t for t in cls._threats.values() if t.severity == severity]

    @classmethod
    def get_threats_for_device(cls, device_type: DeviceType) -> list[ThreatDefinition]:
        """Get threats that can target a specific device type."""
        if not cls._threats:
            cls.initialize()
        return [
            t for t in cls._threats.values()
            if device_type in t.target_device_types
        ]

    @classmethod
    def get_threats_by_frequency(cls, frequency: ThreatFrequency) -> list[ThreatDefinition]:
        """Get threats by frequency level."""
        if not cls._threats:
            cls.initialize()
        return [t for t in cls._threats.values() if t.frequency == frequency]

    @classmethod
    def get_threats_by_priority(cls, priority: ThreatPriority) -> list[ThreatDefinition]:
        """Get threats by priority level."""
        if not cls._threats:
            cls.initialize()
        return [t for t in cls._threats.values() if t.priority == priority]

    @classmethod
    def get_frequent_threats(cls) -> list[ThreatDefinition]:
        """Get the most frequently occurring threats (common + very_common)."""
        if not cls._threats:
            cls.initialize()
        return [
            t for t in cls._threats.values()
            if t.frequency in (ThreatFrequency.VERY_COMMON, ThreatFrequency.COMMON)
        ]

    @classmethod
    def get_critical_threats(cls) -> list[ThreatDefinition]:
        """Get threats with critical priority for essential research."""
        if not cls._threats:
            cls.initialize()
        return [
            t for t in cls._threats.values()
            if t.priority == ThreatPriority.CRITICAL
        ]

    @classmethod
    def get_threat_summary(cls) -> dict[str, Any]:
        """Get a summary of the threat catalog."""
        if not cls._threats:
            cls.initialize()

        return {
            "total_threats": len(cls._threats),
            "by_category": {
                cat.value: len(cls.get_threats_by_category(cat))
                for cat in ThreatCategory
            },
            "by_severity": {
                sev.value: len(cls.get_threats_by_severity(sev))
                for sev in ThreatSeverity
            },
            "by_frequency": {
                freq.value: len(cls.get_threats_by_frequency(freq))
                for freq in ThreatFrequency
            },
            "by_priority": {
                pri.value: len(cls.get_threats_by_priority(pri))
                for pri in ThreatPriority
            },
            "threat_types": [t.value for t in cls._threats.keys()],
        }
