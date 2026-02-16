"""
Threat Scenarios

Concrete implementations of various IoT threat scenarios.
Each scenario defines target selection, attack phases, and event generation.
"""

import random
from datetime import datetime, timedelta
from typing import Optional

from loguru import logger

from src.simulation.models import (
    Device,
    DeviceType,
    EventType,
    Home,
    SimulationEvent,
)
from src.simulation.threats.threat_catalog import ThreatType
from src.simulation.threats.threat_injector import (
    ThreatInstance,
    ThreatPhase,
    ThreatScenario,
)


class EnergyTheftScenario(ThreatScenario):
    """
    Energy Theft Attack Scenario.

    Manipulates smart meter readings to underreport energy consumption.
    Attack phases:
    1. Reconnaissance: Identify meter communication patterns
    2. Initial Access: Compromise meter or gateway
    3. Execution: Gradually modify readings
    4. Persistence: Maintain falsified data stream
    """

    def __init__(self, threat_type: ThreatType, home: Home, seed: Optional[int] = None):
        super().__init__(threat_type, home, seed)
        self.reduction_percentage = self.rng.uniform(0.15, 0.4)  # 15-40% reduction

    def select_targets(self) -> list[str]:
        """Select smart meters and plugs as targets."""
        targets = []
        for device in self.home.devices:
            if device.device_type in [DeviceType.SMART_METER, DeviceType.SMART_PLUG]:
                targets.append(device.id)
        return targets[:3]  # Limit to 3 devices

    def generate_phase_events(
        self,
        instance: ThreatInstance,
        current_time: datetime,
    ) -> list[SimulationEvent]:
        """Generate events based on current phase."""
        events = []

        if instance.phase == ThreatPhase.RECONNAISSANCE:
            # Probe meter communication
            if self.rng.random() < 0.3:
                for target in instance.target_device_ids[:1]:
                    events.append(self._create_event(
                        instance,
                        EventType.NETWORK_TRAFFIC,
                        target,
                        current_time,
                        {
                            "action": "meter_probe",
                            "probe_type": "protocol_scan",
                            "bytes_sent": self.rng.randint(100, 500),
                        },
                    ))

        elif instance.phase == ThreatPhase.INITIAL_ACCESS:
            # Attempt to gain access
            if self.rng.random() < 0.2:
                target = self.rng.choice(instance.target_device_ids)
                success = self.rng.random() < 0.7
                events.append(self._create_event(
                    instance,
                    EventType.DEVICE_STATE_CHANGE,
                    target,
                    current_time,
                    {
                        "action": "authentication_attempt",
                        "method": "credential_replay",
                        "success": success,
                    },
                ))
                if success and target not in instance.compromised_device_ids:
                    instance.compromised_device_ids.append(target)

        elif instance.phase == ThreatPhase.EXECUTION:
            # Modify readings
            if self.rng.random() < 0.4 and instance.compromised_device_ids:
                target = self.rng.choice(instance.compromised_device_ids)
                original_reading = self.rng.uniform(100, 500)  # kWh
                falsified_reading = original_reading * (1 - self.reduction_percentage)

                events.append(self._create_event(
                    instance,
                    EventType.DEVICE_DATA_GENERATED,
                    target,
                    current_time,
                    {
                        "action": "reading_falsification",
                        "original_kwh": round(original_reading, 2),
                        "reported_kwh": round(falsified_reading, 2),
                        "reduction_percent": round(self.reduction_percentage * 100, 1),
                    },
                ))

        elif instance.phase == ThreatPhase.PERSISTENCE:
            # Maintain access
            if self.rng.random() < 0.1:
                events.append(self._create_event(
                    instance,
                    EventType.NETWORK_TRAFFIC,
                    instance.id,
                    current_time,
                    {
                        "action": "c2_heartbeat",
                        "interval_seconds": 300,
                    },
                ))

        return events

    def advance_phase(
        self,
        instance: ThreatInstance,
        current_time: datetime,
    ) -> ThreatPhase:
        """Determine next attack phase."""
        if not instance.phase_start_time:
            return instance.phase

        elapsed_minutes = (current_time - instance.phase_start_time).total_seconds() / 60

        if instance.phase == ThreatPhase.RECONNAISSANCE:
            if elapsed_minutes > 5:
                return ThreatPhase.INITIAL_ACCESS

        elif instance.phase == ThreatPhase.INITIAL_ACCESS:
            if instance.compromised_device_ids or elapsed_minutes > 10:
                if instance.compromised_device_ids:
                    return ThreatPhase.EXECUTION
                else:
                    return ThreatPhase.COMPLETED  # Failed to compromise

        elif instance.phase == ThreatPhase.EXECUTION:
            if elapsed_minutes > instance.planned_duration_minutes * 0.7:
                return ThreatPhase.PERSISTENCE

        elif instance.phase == ThreatPhase.PERSISTENCE:
            if elapsed_minutes > instance.planned_duration_minutes * 0.2:
                return ThreatPhase.COMPLETED

        return instance.phase


class DataExfiltrationScenario(ThreatScenario):
    """
    Data Exfiltration Scenario.

    Extracts sensitive data from cameras, speakers, and sensors.
    Uses covert channels and scheduled exfiltration.
    """

    def __init__(self, threat_type: ThreatType, home: Home, seed: Optional[int] = None):
        super().__init__(threat_type, home, seed)
        self.exfil_rate_kbps = self.rng.uniform(10, 100)

    def select_targets(self) -> list[str]:
        """Select devices with valuable data."""
        targets = []
        priority_types = [
            DeviceType.SECURITY_CAMERA,
            DeviceType.SMART_SPEAKER,
            DeviceType.MOTION_SENSOR,
            DeviceType.SMART_TV,
        ]

        for device in self.home.devices:
            if device.device_type in priority_types:
                targets.append(device.id)

        return targets[:5]

    def generate_phase_events(
        self,
        instance: ThreatInstance,
        current_time: datetime,
    ) -> list[SimulationEvent]:
        """Generate data exfiltration events."""
        events = []

        if instance.phase == ThreatPhase.RECONNAISSANCE:
            if self.rng.random() < 0.25:
                events.append(self._create_event(
                    instance,
                    EventType.NETWORK_TRAFFIC,
                    "scanner",
                    current_time,
                    {
                        "action": "network_scan",
                        "scan_type": "service_discovery",
                        "targets_found": len(instance.target_device_ids),
                    },
                ))

        elif instance.phase == ThreatPhase.INITIAL_ACCESS:
            if self.rng.random() < 0.3:
                target = self.rng.choice(instance.target_device_ids)
                # Try various exploitation methods
                method = self.rng.choice([
                    "default_credentials",
                    "cve_exploit",
                    "api_abuse",
                ])
                success = self.rng.random() < 0.6

                events.append(self._create_event(
                    instance,
                    EventType.DEVICE_STATE_CHANGE,
                    target,
                    current_time,
                    {
                        "action": "exploitation_attempt",
                        "method": method,
                        "success": success,
                    },
                ))

                if success and target not in instance.compromised_device_ids:
                    instance.compromised_device_ids.append(target)

        elif instance.phase == ThreatPhase.EXECUTION:
            # Collect data from compromised devices
            if self.rng.random() < 0.4 and instance.compromised_device_ids:
                target = self.rng.choice(instance.compromised_device_ids)
                data_types = ["video_frame", "audio_sample", "sensor_reading", "log_data"]
                data_type = self.rng.choice(data_types)

                bytes_collected = self.rng.randint(1000, 50000)

                events.append(self._create_event(
                    instance,
                    EventType.DEVICE_DATA_GENERATED,
                    target,
                    current_time,
                    {
                        "action": "data_collection",
                        "data_type": data_type,
                        "bytes": bytes_collected,
                        "encrypted": True,
                    },
                ))

        elif instance.phase == ThreatPhase.EXFILTRATION:
            # Exfiltrate collected data
            if self.rng.random() < 0.5:
                bytes_sent = int(self.exfil_rate_kbps * 1024 * self.rng.uniform(1, 5))
                instance.data_exfiltrated_bytes += bytes_sent

                events.append(self._create_event(
                    instance,
                    EventType.NETWORK_TRAFFIC,
                    "exfil_channel",
                    current_time,
                    {
                        "action": "data_exfiltration",
                        "method": self.rng.choice(["https", "dns_tunnel", "icmp_covert"]),
                        "bytes_sent": bytes_sent,
                        "destination": "external_server",
                        "total_exfiltrated": instance.data_exfiltrated_bytes,
                    },
                ))

        return events

    def advance_phase(
        self,
        instance: ThreatInstance,
        current_time: datetime,
    ) -> ThreatPhase:
        """Advance through exfiltration phases."""
        if not instance.phase_start_time:
            return instance.phase

        elapsed = (current_time - instance.phase_start_time).total_seconds() / 60

        if instance.phase == ThreatPhase.RECONNAISSANCE:
            if elapsed > 3:
                return ThreatPhase.INITIAL_ACCESS

        elif instance.phase == ThreatPhase.INITIAL_ACCESS:
            if instance.compromised_device_ids and elapsed > 5:
                return ThreatPhase.EXECUTION
            elif elapsed > 15:
                return ThreatPhase.COMPLETED

        elif instance.phase == ThreatPhase.EXECUTION:
            if elapsed > instance.planned_duration_minutes * 0.5:
                return ThreatPhase.EXFILTRATION

        elif instance.phase == ThreatPhase.EXFILTRATION:
            if elapsed > instance.planned_duration_minutes * 0.4:
                return ThreatPhase.CLEANUP

        elif instance.phase == ThreatPhase.CLEANUP:
            if elapsed > 5:
                return ThreatPhase.COMPLETED

        return instance.phase


class DeviceTamperingScenario(ThreatScenario):
    """
    Device Tampering Scenario.

    Modifies device configurations or firmware to alter behavior.
    Targets security-critical devices like locks and smoke detectors.
    """

    def __init__(self, threat_type: ThreatType, home: Home, seed: Optional[int] = None):
        super().__init__(threat_type, home, seed)

    def select_targets(self) -> list[str]:
        """Select security-critical devices."""
        targets = []
        critical_types = [
            DeviceType.SMART_LOCK,
            DeviceType.SMOKE_DETECTOR,
            DeviceType.SECURITY_CAMERA,
            DeviceType.THERMOSTAT,
        ]

        for device in self.home.devices:
            if device.device_type in critical_types:
                targets.append(device.id)

        return targets[:2]  # Focus attack on few devices

    def generate_phase_events(
        self,
        instance: ThreatInstance,
        current_time: datetime,
    ) -> list[SimulationEvent]:
        """Generate tampering events."""
        events = []

        if instance.phase == ThreatPhase.RECONNAISSANCE:
            if self.rng.random() < 0.3:
                events.append(self._create_event(
                    instance,
                    EventType.NETWORK_TRAFFIC,
                    "recon",
                    current_time,
                    {
                        "action": "firmware_version_check",
                        "targets": instance.target_device_ids,
                    },
                ))

        elif instance.phase == ThreatPhase.INITIAL_ACCESS:
            if self.rng.random() < 0.25 and instance.target_device_ids:
                target = self.rng.choice(instance.target_device_ids)
                events.append(self._create_event(
                    instance,
                    EventType.DEVICE_STATE_CHANGE,
                    target,
                    current_time,
                    {
                        "action": "admin_login_attempt",
                        "method": "brute_force",
                        "attempts": self.rng.randint(5, 20),
                    },
                ))

                if self.rng.random() < 0.5:
                    instance.compromised_device_ids.append(target)

        elif instance.phase == ThreatPhase.EXECUTION:
            if self.rng.random() < 0.3 and instance.compromised_device_ids:
                target = self.rng.choice(instance.compromised_device_ids)

                tampering_actions = [
                    {
                        "action": "config_modification",
                        "parameter": "sensitivity",
                        "old_value": "high",
                        "new_value": "low",
                    },
                    {
                        "action": "disable_feature",
                        "feature": "alarm",
                        "reason": "stealth",
                    },
                    {
                        "action": "add_backdoor_user",
                        "username": "service_" + str(self.rng.randint(100, 999)),
                    },
                    {
                        "action": "modify_threshold",
                        "parameter": "motion_sensitivity",
                        "change": -50,
                    },
                ]

                tampering = self.rng.choice(tampering_actions)
                events.append(self._create_event(
                    instance,
                    EventType.DEVICE_STATE_CHANGE,
                    target,
                    current_time,
                    tampering,
                ))

        return events

    def advance_phase(
        self,
        instance: ThreatInstance,
        current_time: datetime,
    ) -> ThreatPhase:
        """Advance tampering phases."""
        if not instance.phase_start_time:
            return instance.phase

        elapsed = (current_time - instance.phase_start_time).total_seconds() / 60

        if instance.phase == ThreatPhase.RECONNAISSANCE:
            if elapsed > 2:
                return ThreatPhase.INITIAL_ACCESS

        elif instance.phase == ThreatPhase.INITIAL_ACCESS:
            if instance.compromised_device_ids:
                return ThreatPhase.EXECUTION
            elif elapsed > 10:
                return ThreatPhase.COMPLETED

        elif instance.phase == ThreatPhase.EXECUTION:
            if elapsed > instance.planned_duration_minutes * 0.8:
                return ThreatPhase.COMPLETED

        return instance.phase


class UnauthorizedAccessScenario(ThreatScenario):
    """
    Unauthorized Physical Access Scenario.

    Exploits smart lock vulnerabilities to gain physical access.
    Simulates credential theft, replay attacks, and API exploitation.
    """

    def __init__(self, threat_type: ThreatType, home: Home, seed: Optional[int] = None):
        super().__init__(threat_type, home, seed)
        self.failed_attempts = 0

    def select_targets(self) -> list[str]:
        """Select smart locks and doorbells."""
        targets = []
        for device in self.home.devices:
            if device.device_type in [DeviceType.SMART_LOCK, DeviceType.SMART_DOORBELL]:
                targets.append(device.id)
        return targets

    def generate_phase_events(
        self,
        instance: ThreatInstance,
        current_time: datetime,
    ) -> list[SimulationEvent]:
        """Generate unauthorized access events."""
        events = []

        if instance.phase == ThreatPhase.RECONNAISSANCE:
            if self.rng.random() < 0.4:
                events.append(self._create_event(
                    instance,
                    EventType.NETWORK_TRAFFIC,
                    "attacker",
                    current_time,
                    {
                        "action": "lock_discovery",
                        "protocol": "bluetooth_le",
                        "locks_found": len([
                            t for t in instance.target_device_ids
                        ]),
                    },
                ))

        elif instance.phase == ThreatPhase.INITIAL_ACCESS:
            if self.rng.random() < 0.4 and instance.target_device_ids:
                target = self.rng.choice(instance.target_device_ids)

                attack_methods = [
                    ("pin_bruteforce", 0.2),
                    ("replay_attack", 0.4),
                    ("credential_stuffing", 0.3),
                    ("api_bypass", 0.5),
                ]

                method, success_prob = self.rng.choice(attack_methods)
                success = self.rng.random() < success_prob

                events.append(self._create_event(
                    instance,
                    EventType.DEVICE_STATE_CHANGE,
                    target,
                    current_time,
                    {
                        "action": "unlock_attempt",
                        "method": method,
                        "success": success,
                        "failed_attempts": self.failed_attempts,
                    },
                ))

                if success:
                    instance.compromised_device_ids.append(target)
                else:
                    self.failed_attempts += 1

        elif instance.phase == ThreatPhase.EXECUTION:
            if instance.compromised_device_ids:
                target = instance.compromised_device_ids[0]

                events.append(self._create_event(
                    instance,
                    EventType.DEVICE_STATE_CHANGE,
                    target,
                    current_time,
                    {
                        "action": "lock_state_change",
                        "state": "unlocked",
                        "authorized": False,
                        "method": "exploited",
                    },
                ))

        return events

    def advance_phase(
        self,
        instance: ThreatInstance,
        current_time: datetime,
    ) -> ThreatPhase:
        """Advance access phases."""
        if not instance.phase_start_time:
            return instance.phase

        elapsed = (current_time - instance.phase_start_time).total_seconds() / 60

        if instance.phase == ThreatPhase.RECONNAISSANCE:
            if elapsed > 2:
                return ThreatPhase.INITIAL_ACCESS

        elif instance.phase == ThreatPhase.INITIAL_ACCESS:
            if instance.compromised_device_ids:
                return ThreatPhase.EXECUTION
            elif elapsed > 5 or self.failed_attempts > 10:
                return ThreatPhase.COMPLETED  # Gave up or blocked

        elif instance.phase == ThreatPhase.EXECUTION:
            if elapsed > 1:  # Quick in and out
                return ThreatPhase.COMPLETED

        return instance.phase


class BotnetScenario(ThreatScenario):
    """
    Botnet Recruitment Scenario.

    Compromises devices to recruit them into a botnet.
    Simulates Mirai-style attacks with scanning and payload delivery.
    """

    def __init__(self, threat_type: ThreatType, home: Home, seed: Optional[int] = None):
        super().__init__(threat_type, home, seed)
        self.c2_domain = f"c2-{self.rng.randint(1000, 9999)}.malware.net"

    def select_targets(self) -> list[str]:
        """Select devices suitable for botnet."""
        targets = []
        botnet_types = [
            DeviceType.SECURITY_CAMERA,
            DeviceType.ROUTER,
            DeviceType.SMART_TV,
            DeviceType.SMART_PLUG,
        ]

        for device in self.home.devices:
            if device.device_type in botnet_types:
                targets.append(device.id)

        return targets

    def generate_phase_events(
        self,
        instance: ThreatInstance,
        current_time: datetime,
    ) -> list[SimulationEvent]:
        """Generate botnet recruitment events."""
        events = []

        if instance.phase == ThreatPhase.RECONNAISSANCE:
            if self.rng.random() < 0.3:
                events.append(self._create_event(
                    instance,
                    EventType.NETWORK_TRAFFIC,
                    "scanner",
                    current_time,
                    {
                        "action": "port_scan",
                        "ports": [23, 80, 8080, 443],
                        "targets": len(instance.target_device_ids),
                    },
                ))

        elif instance.phase == ThreatPhase.INITIAL_ACCESS:
            if self.rng.random() < 0.35 and instance.target_device_ids:
                target = self.rng.choice(instance.target_device_ids)

                # Mirai-style default credential attack
                credentials_tried = [
                    ("admin", "admin"),
                    ("root", "root"),
                    ("admin", "password"),
                    ("root", ""),
                ]

                success = self.rng.random() < 0.4

                events.append(self._create_event(
                    instance,
                    EventType.DEVICE_STATE_CHANGE,
                    target,
                    current_time,
                    {
                        "action": "credential_spray",
                        "attempts": len(credentials_tried),
                        "success": success,
                    },
                ))

                if success and target not in instance.compromised_device_ids:
                    instance.compromised_device_ids.append(target)

        elif instance.phase == ThreatPhase.EXECUTION:
            if self.rng.random() < 0.3 and instance.compromised_device_ids:
                target = self.rng.choice(instance.compromised_device_ids)

                events.append(self._create_event(
                    instance,
                    EventType.DEVICE_STATE_CHANGE,
                    target,
                    current_time,
                    {
                        "action": "malware_installation",
                        "payload": "botnet_agent",
                        "size_bytes": self.rng.randint(10000, 50000),
                    },
                ))

        elif instance.phase == ThreatPhase.PERSISTENCE:
            if self.rng.random() < 0.2 and instance.compromised_device_ids:
                target = self.rng.choice(instance.compromised_device_ids)

                events.append(self._create_event(
                    instance,
                    EventType.NETWORK_TRAFFIC,
                    target,
                    current_time,
                    {
                        "action": "c2_communication",
                        "destination": self.c2_domain,
                        "command": self.rng.choice(["heartbeat", "update", "scan_order"]),
                        "bytes_sent": self.rng.randint(50, 500),
                    },
                ))

                # Occasionally participate in scanning
                if self.rng.random() < 0.3:
                    events.append(self._create_event(
                        instance,
                        EventType.NETWORK_TRAFFIC,
                        target,
                        current_time,
                        {
                            "action": "outbound_scan",
                            "scan_type": "telnet_probe",
                            "targets_scanned": self.rng.randint(100, 1000),
                        },
                    ))

        return events

    def advance_phase(
        self,
        instance: ThreatInstance,
        current_time: datetime,
    ) -> ThreatPhase:
        """Advance botnet phases."""
        if not instance.phase_start_time:
            return instance.phase

        elapsed = (current_time - instance.phase_start_time).total_seconds() / 60

        if instance.phase == ThreatPhase.RECONNAISSANCE:
            if elapsed > 3:
                return ThreatPhase.INITIAL_ACCESS

        elif instance.phase == ThreatPhase.INITIAL_ACCESS:
            if instance.compromised_device_ids and elapsed > 5:
                return ThreatPhase.EXECUTION
            elif elapsed > 15:
                return ThreatPhase.COMPLETED

        elif instance.phase == ThreatPhase.EXECUTION:
            if elapsed > 5:
                return ThreatPhase.PERSISTENCE

        elif instance.phase == ThreatPhase.PERSISTENCE:
            # Botnet persists until explicitly stopped
            if elapsed > instance.planned_duration_minutes:
                return ThreatPhase.COMPLETED

        return instance.phase


class SurveillanceScenario(ThreatScenario):
    """
    Unauthorized Surveillance Scenario.

    Hijacks cameras and microphones to monitor occupants.
    Common threat for security cameras, smart speakers, and doorbells.
    """

    def __init__(self, threat_type: ThreatType, home: Home, seed: Optional[int] = None):
        super().__init__(threat_type, home, seed)
        self.stream_quality = self.rng.choice(["low", "medium", "high"])
        self.recording_active = False

    def select_targets(self) -> list[str]:
        """Select devices with cameras/microphones."""
        targets = []
        surveillance_types = [
            DeviceType.SECURITY_CAMERA,
            DeviceType.SMART_SPEAKER,
            DeviceType.SMART_DOORBELL,
            DeviceType.SMART_TV,
            DeviceType.BABY_MONITOR,
        ]

        for device in self.home.devices:
            if device.device_type in surveillance_types:
                targets.append(device.id)

        return targets[:4]

    def generate_phase_events(
        self,
        instance: ThreatInstance,
        current_time: datetime,
    ) -> list[SimulationEvent]:
        """Generate surveillance events."""
        events = []

        if instance.phase == ThreatPhase.RECONNAISSANCE:
            if self.rng.random() < 0.25:
                events.append(self._create_event(
                    instance,
                    EventType.NETWORK_TRAFFIC,
                    "scanner",
                    current_time,
                    {
                        "action": "rtsp_scan",
                        "protocol": "rtsp",
                        "streams_found": len(instance.target_device_ids),
                    },
                ))

        elif instance.phase == ThreatPhase.INITIAL_ACCESS:
            if self.rng.random() < 0.3 and instance.target_device_ids:
                target = self.rng.choice(instance.target_device_ids)
                success = self.rng.random() < 0.5

                events.append(self._create_event(
                    instance,
                    EventType.DEVICE_STATE_CHANGE,
                    target,
                    current_time,
                    {
                        "action": "stream_hijack_attempt",
                        "method": self.rng.choice(["default_creds", "rtsp_exploit", "api_bypass"]),
                        "success": success,
                    },
                ))

                if success and target not in instance.compromised_device_ids:
                    instance.compromised_device_ids.append(target)

        elif instance.phase == ThreatPhase.EXECUTION:
            if instance.compromised_device_ids:
                target = self.rng.choice(instance.compromised_device_ids)

                # Start recording
                if self.rng.random() < 0.4:
                    self.recording_active = True
                    events.append(self._create_event(
                        instance,
                        EventType.DEVICE_STATE_CHANGE,
                        target,
                        current_time,
                        {
                            "action": "recording_started",
                            "type": self.rng.choice(["video", "audio", "both"]),
                            "quality": self.stream_quality,
                        },
                    ))

                # Stream data
                if self.recording_active and self.rng.random() < 0.5:
                    bandwidth = {"low": 500, "medium": 2000, "high": 5000}
                    bytes_sent = self.rng.randint(
                        bandwidth[self.stream_quality] * 100,
                        bandwidth[self.stream_quality] * 500,
                    )
                    instance.data_exfiltrated_bytes += bytes_sent

                    events.append(self._create_event(
                        instance,
                        EventType.NETWORK_TRAFFIC,
                        target,
                        current_time,
                        {
                            "action": "stream_exfiltration",
                            "bytes_sent": bytes_sent,
                            "destination": "external_server",
                            "encrypted": True,
                        },
                    ))

        return events

    def advance_phase(
        self,
        instance: ThreatInstance,
        current_time: datetime,
    ) -> ThreatPhase:
        """Advance surveillance phases."""
        if not instance.phase_start_time:
            return instance.phase

        elapsed = (current_time - instance.phase_start_time).total_seconds() / 60

        if instance.phase == ThreatPhase.RECONNAISSANCE:
            if elapsed > 3:
                return ThreatPhase.INITIAL_ACCESS

        elif instance.phase == ThreatPhase.INITIAL_ACCESS:
            if instance.compromised_device_ids:
                return ThreatPhase.EXECUTION
            elif elapsed > 10:
                return ThreatPhase.COMPLETED

        elif instance.phase == ThreatPhase.EXECUTION:
            if elapsed > instance.planned_duration_minutes:
                return ThreatPhase.COMPLETED

        return instance.phase


class RansomwareScenario(ThreatScenario):
    """
    IoT Ransomware Scenario.

    Locks or disables smart home devices and demands payment.
    Targets critical devices like locks, thermostats, and security panels.
    """

    def __init__(self, threat_type: ThreatType, home: Home, seed: Optional[int] = None):
        super().__init__(threat_type, home, seed)
        self.ransom_amount = self.rng.uniform(0.5, 5.0)  # BTC
        self.devices_locked = 0

    def select_targets(self) -> list[str]:
        """Select critical devices for ransomware."""
        targets = []
        ransom_types = [
            DeviceType.SMART_LOCK,
            DeviceType.THERMOSTAT,
            DeviceType.HUB,
            DeviceType.SECURITY_KEYPAD,
            DeviceType.GARAGE_DOOR_CONTROLLER,
            DeviceType.SMART_BLINDS,
        ]

        for device in self.home.devices:
            if device.device_type in ransom_types:
                targets.append(device.id)

        return targets

    def generate_phase_events(
        self,
        instance: ThreatInstance,
        current_time: datetime,
    ) -> list[SimulationEvent]:
        """Generate ransomware events."""
        events = []

        if instance.phase == ThreatPhase.RECONNAISSANCE:
            if self.rng.random() < 0.3:
                events.append(self._create_event(
                    instance,
                    EventType.NETWORK_TRAFFIC,
                    "scanner",
                    current_time,
                    {
                        "action": "device_enumeration",
                        "devices_found": len(instance.target_device_ids),
                        "critical_devices": len([t for t in instance.target_device_ids]),
                    },
                ))

        elif instance.phase == ThreatPhase.INITIAL_ACCESS:
            if self.rng.random() < 0.4 and instance.target_device_ids:
                target = self.rng.choice(instance.target_device_ids)
                success = self.rng.random() < 0.6

                events.append(self._create_event(
                    instance,
                    EventType.DEVICE_STATE_CHANGE,
                    target,
                    current_time,
                    {
                        "action": "exploit_attempt",
                        "vulnerability": self.rng.choice([
                            "auth_bypass",
                            "command_injection",
                            "buffer_overflow",
                        ]),
                        "success": success,
                    },
                ))

                if success and target not in instance.compromised_device_ids:
                    instance.compromised_device_ids.append(target)

        elif instance.phase == ThreatPhase.EXECUTION:
            if instance.compromised_device_ids:
                # Lock devices one by one
                for target in instance.compromised_device_ids:
                    if self.rng.random() < 0.5:
                        self.devices_locked += 1
                        events.append(self._create_event(
                            instance,
                            EventType.DEVICE_STATE_CHANGE,
                            target,
                            current_time,
                            {
                                "action": "device_locked",
                                "encryption": "AES-256",
                                "reversible": True,
                            },
                        ))

                # Display ransom message
                if self.devices_locked > 0 and self.rng.random() < 0.3:
                    events.append(self._create_event(
                        instance,
                        EventType.SYSTEM_EVENT,
                        instance.id,
                        current_time,
                        {
                            "action": "ransom_demand",
                            "amount_btc": round(self.ransom_amount, 4),
                            "devices_locked": self.devices_locked,
                            "deadline_hours": 48,
                            "wallet": f"bc1q{self.rng.randint(100000, 999999)}",
                        },
                    ))

        return events

    def advance_phase(
        self,
        instance: ThreatInstance,
        current_time: datetime,
    ) -> ThreatPhase:
        """Advance ransomware phases."""
        if not instance.phase_start_time:
            return instance.phase

        elapsed = (current_time - instance.phase_start_time).total_seconds() / 60

        if instance.phase == ThreatPhase.RECONNAISSANCE:
            if elapsed > 2:
                return ThreatPhase.INITIAL_ACCESS

        elif instance.phase == ThreatPhase.INITIAL_ACCESS:
            if instance.compromised_device_ids and elapsed > 3:
                return ThreatPhase.EXECUTION
            elif elapsed > 10:
                return ThreatPhase.COMPLETED

        elif instance.phase == ThreatPhase.EXECUTION:
            if elapsed > instance.planned_duration_minutes:
                return ThreatPhase.COMPLETED

        return instance.phase


class SensorInterceptionScenario(ThreatScenario):
    """
    Sensor Data Interception Scenario.

    Passively intercepts sensor data to gather intelligence
    about occupancy patterns and environmental conditions.
    """

    def __init__(self, threat_type: ThreatType, home: Home, seed: Optional[int] = None):
        super().__init__(threat_type, home, seed)
        self.data_collected = {}

    def select_targets(self) -> list[str]:
        """Select sensor devices."""
        targets = []
        sensor_types = [
            DeviceType.MOTION_SENSOR,
            DeviceType.DOOR_SENSOR,
            DeviceType.WINDOW_SENSOR,
            DeviceType.TEMPERATURE_SENSOR,
            DeviceType.HUMIDITY_SENSOR,
            DeviceType.AIR_QUALITY_MONITOR,
            DeviceType.MOTION_SENSOR,
            DeviceType.PROXIMITY_SENSOR,
        ]

        for device in self.home.devices:
            if device.device_type in sensor_types:
                targets.append(device.id)

        return targets

    def generate_phase_events(
        self,
        instance: ThreatInstance,
        current_time: datetime,
    ) -> list[SimulationEvent]:
        """Generate sensor interception events."""
        events = []

        if instance.phase == ThreatPhase.RECONNAISSANCE:
            if self.rng.random() < 0.2:
                events.append(self._create_event(
                    instance,
                    EventType.NETWORK_TRAFFIC,
                    "sniffer",
                    current_time,
                    {
                        "action": "protocol_analysis",
                        "protocols_detected": ["zigbee", "z-wave", "mqtt"],
                        "sensors_found": len(instance.target_device_ids),
                    },
                ))

        elif instance.phase == ThreatPhase.INITIAL_ACCESS:
            # Passive interception doesn't require full compromise
            if self.rng.random() < 0.4:
                events.append(self._create_event(
                    instance,
                    EventType.NETWORK_TRAFFIC,
                    "sniffer",
                    current_time,
                    {
                        "action": "traffic_capture_started",
                        "mode": "promiscuous",
                        "filter": "sensor_protocols",
                    },
                ))
                # Mark as "compromised" for phase tracking
                if not instance.compromised_device_ids:
                    instance.compromised_device_ids = ["passive_capture"]

        elif instance.phase == ThreatPhase.EXECUTION:
            # Collect sensor data
            if self.rng.random() < 0.5 and instance.target_device_ids:
                target = self.rng.choice(instance.target_device_ids)
                sensor_data = {
                    "motion_detected": self.rng.choice([True, False]),
                    "temperature_c": round(self.rng.uniform(18, 28), 1),
                    "occupancy": self.rng.choice([True, False]),
                    "door_open": self.rng.choice([True, False]),
                }

                events.append(self._create_event(
                    instance,
                    EventType.DEVICE_DATA_GENERATED,
                    target,
                    current_time,
                    {
                        "action": "sensor_data_intercepted",
                        "data": sensor_data,
                        "encrypted": False,
                    },
                ))

                instance.data_exfiltrated_bytes += self.rng.randint(50, 200)

        return events

    def advance_phase(
        self,
        instance: ThreatInstance,
        current_time: datetime,
    ) -> ThreatPhase:
        """Advance interception phases."""
        if not instance.phase_start_time:
            return instance.phase

        elapsed = (current_time - instance.phase_start_time).total_seconds() / 60

        if instance.phase == ThreatPhase.RECONNAISSANCE:
            if elapsed > 5:
                return ThreatPhase.INITIAL_ACCESS

        elif instance.phase == ThreatPhase.INITIAL_ACCESS:
            if elapsed > 5:
                return ThreatPhase.EXECUTION

        elif instance.phase == ThreatPhase.EXECUTION:
            if elapsed > instance.planned_duration_minutes:
                return ThreatPhase.COMPLETED

        return instance.phase


class FirmwareModificationScenario(ThreatScenario):
    """
    Malicious Firmware Modification Scenario.

    Replaces device firmware with malicious code for
    persistent control and backdoor access.
    """

    def __init__(self, threat_type: ThreatType, home: Home, seed: Optional[int] = None):
        super().__init__(threat_type, home, seed)
        self.payload_size = self.rng.randint(500000, 5000000)

    def select_targets(self) -> list[str]:
        """Select devices suitable for firmware modification."""
        targets = []
        firmware_types = [
            DeviceType.ROUTER,
            DeviceType.SECURITY_CAMERA,
            DeviceType.SMART_LOCK,
            DeviceType.HUB,
            DeviceType.THERMOSTAT,
            DeviceType.SMART_TV,
        ]

        for device in self.home.devices:
            if device.device_type in firmware_types:
                targets.append(device.id)

        return targets[:2]  # Focus on few high-value targets

    def generate_phase_events(
        self,
        instance: ThreatInstance,
        current_time: datetime,
    ) -> list[SimulationEvent]:
        """Generate firmware modification events."""
        events = []

        if instance.phase == ThreatPhase.RECONNAISSANCE:
            if self.rng.random() < 0.3:
                events.append(self._create_event(
                    instance,
                    EventType.NETWORK_TRAFFIC,
                    "scanner",
                    current_time,
                    {
                        "action": "firmware_version_probe",
                        "targets": instance.target_device_ids,
                        "versions_found": len(instance.target_device_ids),
                    },
                ))

        elif instance.phase == ThreatPhase.INITIAL_ACCESS:
            if self.rng.random() < 0.25 and instance.target_device_ids:
                target = self.rng.choice(instance.target_device_ids)
                success = self.rng.random() < 0.4  # Hard to exploit

                events.append(self._create_event(
                    instance,
                    EventType.DEVICE_STATE_CHANGE,
                    target,
                    current_time,
                    {
                        "action": "admin_access_attempt",
                        "method": self.rng.choice([
                            "ssh_exploit",
                            "web_ui_bypass",
                            "telnet_backdoor",
                        ]),
                        "success": success,
                    },
                ))

                if success and target not in instance.compromised_device_ids:
                    instance.compromised_device_ids.append(target)

        elif instance.phase == ThreatPhase.EXECUTION:
            if instance.compromised_device_ids:
                target = self.rng.choice(instance.compromised_device_ids)

                # Upload malicious firmware
                if self.rng.random() < 0.3:
                    events.append(self._create_event(
                        instance,
                        EventType.NETWORK_TRAFFIC,
                        target,
                        current_time,
                        {
                            "action": "firmware_upload",
                            "size_bytes": self.payload_size,
                            "source": "malicious_server",
                        },
                    ))

                # Flash firmware
                if self.rng.random() < 0.2:
                    events.append(self._create_event(
                        instance,
                        EventType.DEVICE_STATE_CHANGE,
                        target,
                        current_time,
                        {
                            "action": "firmware_flash",
                            "status": "in_progress",
                            "percentage": self.rng.randint(10, 100),
                        },
                    ))

        elif instance.phase == ThreatPhase.PERSISTENCE:
            if instance.compromised_device_ids and self.rng.random() < 0.2:
                target = self.rng.choice(instance.compromised_device_ids)

                events.append(self._create_event(
                    instance,
                    EventType.DEVICE_STATE_CHANGE,
                    target,
                    current_time,
                    {
                        "action": "backdoor_active",
                        "firmware_version": f"1.0.{self.rng.randint(100, 999)}-modified",
                        "rootkit_installed": True,
                    },
                ))

        return events

    def advance_phase(
        self,
        instance: ThreatInstance,
        current_time: datetime,
    ) -> ThreatPhase:
        """Advance firmware modification phases."""
        if not instance.phase_start_time:
            return instance.phase

        elapsed = (current_time - instance.phase_start_time).total_seconds() / 60

        if instance.phase == ThreatPhase.RECONNAISSANCE:
            if elapsed > 3:
                return ThreatPhase.INITIAL_ACCESS

        elif instance.phase == ThreatPhase.INITIAL_ACCESS:
            if instance.compromised_device_ids and elapsed > 5:
                return ThreatPhase.EXECUTION
            elif elapsed > 15:
                return ThreatPhase.COMPLETED

        elif instance.phase == ThreatPhase.EXECUTION:
            if elapsed > instance.planned_duration_minutes * 0.7:
                return ThreatPhase.PERSISTENCE

        elif instance.phase == ThreatPhase.PERSISTENCE:
            if elapsed > instance.planned_duration_minutes * 0.3:
                return ThreatPhase.COMPLETED

        return instance.phase


class HVACManipulationScenario(ThreatScenario):
    """
    HVAC System Manipulation Scenario.

    Maliciously controls heating/cooling systems to cause
    discomfort, property damage, or energy waste.
    """

    def __init__(self, threat_type: ThreatType, home: Home, seed: Optional[int] = None):
        super().__init__(threat_type, home, seed)
        self.extreme_temp = self.rng.choice([5, 35])  # Very cold or very hot

    def select_targets(self) -> list[str]:
        """Select HVAC-related devices."""
        targets = []
        hvac_types = [
            DeviceType.THERMOSTAT,
            DeviceType.SMART_FAN,
            DeviceType.AIR_PURIFIER,
            DeviceType.SMART_HUMIDIFIER,
            DeviceType.SMART_DEHUMIDIFIER,
            DeviceType.CEILING_FAN_LIGHT,
        ]

        for device in self.home.devices:
            if device.device_type in hvac_types:
                targets.append(device.id)

        return targets

    def generate_phase_events(
        self,
        instance: ThreatInstance,
        current_time: datetime,
    ) -> list[SimulationEvent]:
        """Generate HVAC manipulation events."""
        events = []

        if instance.phase == ThreatPhase.RECONNAISSANCE:
            if self.rng.random() < 0.25:
                events.append(self._create_event(
                    instance,
                    EventType.NETWORK_TRAFFIC,
                    "scanner",
                    current_time,
                    {
                        "action": "hvac_discovery",
                        "devices_found": len(instance.target_device_ids),
                        "protocols": ["zigbee", "wifi", "z-wave"],
                    },
                ))

        elif instance.phase == ThreatPhase.INITIAL_ACCESS:
            if self.rng.random() < 0.35 and instance.target_device_ids:
                target = self.rng.choice(instance.target_device_ids)
                success = self.rng.random() < 0.6

                events.append(self._create_event(
                    instance,
                    EventType.DEVICE_STATE_CHANGE,
                    target,
                    current_time,
                    {
                        "action": "hvac_access_attempt",
                        "method": self.rng.choice(["api_exploit", "cloud_compromise", "local_bypass"]),
                        "success": success,
                    },
                ))

                if success and target not in instance.compromised_device_ids:
                    instance.compromised_device_ids.append(target)

        elif instance.phase == ThreatPhase.EXECUTION:
            if instance.compromised_device_ids:
                target = self.rng.choice(instance.compromised_device_ids)

                # Manipulate temperature
                if self.rng.random() < 0.4:
                    events.append(self._create_event(
                        instance,
                        EventType.DEVICE_STATE_CHANGE,
                        target,
                        current_time,
                        {
                            "action": "temperature_override",
                            "previous_setpoint": self.rng.randint(18, 24),
                            "new_setpoint": self.extreme_temp,
                            "mode": "heat" if self.extreme_temp > 30 else "cool",
                        },
                    ))

                # Override schedule
                if self.rng.random() < 0.3:
                    events.append(self._create_event(
                        instance,
                        EventType.DEVICE_STATE_CHANGE,
                        target,
                        current_time,
                        {
                            "action": "schedule_disabled",
                            "manual_mode": True,
                            "lock_controls": True,
                        },
                    ))

        return events

    def advance_phase(
        self,
        instance: ThreatInstance,
        current_time: datetime,
    ) -> ThreatPhase:
        """Advance HVAC manipulation phases."""
        if not instance.phase_start_time:
            return instance.phase

        elapsed = (current_time - instance.phase_start_time).total_seconds() / 60

        if instance.phase == ThreatPhase.RECONNAISSANCE:
            if elapsed > 3:
                return ThreatPhase.INITIAL_ACCESS

        elif instance.phase == ThreatPhase.INITIAL_ACCESS:
            if instance.compromised_device_ids:
                return ThreatPhase.EXECUTION
            elif elapsed > 10:
                return ThreatPhase.COMPLETED

        elif instance.phase == ThreatPhase.EXECUTION:
            if elapsed > instance.planned_duration_minutes:
                return ThreatPhase.COMPLETED

        return instance.phase


class SafetySystemBypassScenario(ThreatScenario):
    """
    Safety System Bypass Scenario.

    Disables or bypasses safety systems like smoke detectors,
    CO monitors, and security alarms.
    """

    def __init__(self, threat_type: ThreatType, home: Home, seed: Optional[int] = None):
        super().__init__(threat_type, home, seed)
        self.systems_disabled = 0

    def select_targets(self) -> list[str]:
        """Select safety devices."""
        targets = []
        safety_types = [
            DeviceType.SMOKE_DETECTOR,
            DeviceType.CO_DETECTOR,
            DeviceType.WATER_LEAK_SENSOR,
            DeviceType.SECURITY_KEYPAD,
            DeviceType.GLASS_BREAK_SENSOR,
            DeviceType.SIREN_ALARM,
        ]

        for device in self.home.devices:
            if device.device_type in safety_types:
                targets.append(device.id)

        return targets

    def generate_phase_events(
        self,
        instance: ThreatInstance,
        current_time: datetime,
    ) -> list[SimulationEvent]:
        """Generate safety bypass events."""
        events = []

        if instance.phase == ThreatPhase.RECONNAISSANCE:
            if self.rng.random() < 0.3:
                events.append(self._create_event(
                    instance,
                    EventType.NETWORK_TRAFFIC,
                    "scanner",
                    current_time,
                    {
                        "action": "safety_system_scan",
                        "sensors_found": len(instance.target_device_ids),
                        "alarm_system_detected": any(
                            "security" in t.lower() or "siren" in t.lower()
                            for t in instance.target_device_ids
                        ),
                    },
                ))

        elif instance.phase == ThreatPhase.INITIAL_ACCESS:
            if self.rng.random() < 0.4 and instance.target_device_ids:
                target = self.rng.choice(instance.target_device_ids)
                success = self.rng.random() < 0.5

                events.append(self._create_event(
                    instance,
                    EventType.DEVICE_STATE_CHANGE,
                    target,
                    current_time,
                    {
                        "action": "safety_device_access",
                        "method": self.rng.choice(["jamming", "api_exploit", "firmware_bug"]),
                        "success": success,
                    },
                ))

                if success and target not in instance.compromised_device_ids:
                    instance.compromised_device_ids.append(target)

        elif instance.phase == ThreatPhase.EXECUTION:
            if instance.compromised_device_ids:
                target = self.rng.choice(instance.compromised_device_ids)

                # Disable safety system
                if self.rng.random() < 0.5:
                    self.systems_disabled += 1
                    events.append(self._create_event(
                        instance,
                        EventType.DEVICE_STATE_CHANGE,
                        target,
                        current_time,
                        {
                            "action": "safety_system_disabled",
                            "method": self.rng.choice([
                                "sensitivity_zeroed",
                                "alerts_suppressed",
                                "power_disabled",
                            ]),
                            "silent": True,
                        },
                    ))

                # Spoof normal status
                if self.rng.random() < 0.3:
                    events.append(self._create_event(
                        instance,
                        EventType.DEVICE_STATE_CHANGE,
                        target,
                        current_time,
                        {
                            "action": "status_spoofed",
                            "reported_status": "ok",
                            "actual_status": "disabled",
                        },
                    ))

        return events

    def advance_phase(
        self,
        instance: ThreatInstance,
        current_time: datetime,
    ) -> ThreatPhase:
        """Advance safety bypass phases."""
        if not instance.phase_start_time:
            return instance.phase

        elapsed = (current_time - instance.phase_start_time).total_seconds() / 60

        if instance.phase == ThreatPhase.RECONNAISSANCE:
            if elapsed > 2:
                return ThreatPhase.INITIAL_ACCESS

        elif instance.phase == ThreatPhase.INITIAL_ACCESS:
            if instance.compromised_device_ids:
                return ThreatPhase.EXECUTION
            elif elapsed > 8:
                return ThreatPhase.COMPLETED

        elif instance.phase == ThreatPhase.EXECUTION:
            if elapsed > instance.planned_duration_minutes:
                return ThreatPhase.COMPLETED

        return instance.phase


class CredentialTheftScenario(ThreatScenario):
    """
    Credential Theft Scenario.

    Steals authentication credentials from IoT devices
    for lateral movement and persistent access.
    """

    def __init__(self, threat_type: ThreatType, home: Home, seed: Optional[int] = None):
        super().__init__(threat_type, home, seed)
        self.credentials_stolen = 0

    def select_targets(self) -> list[str]:
        """Select devices with credentials."""
        targets = []
        cred_types = [
            DeviceType.HUB,
            DeviceType.ROUTER,
            DeviceType.SMART_LOCK,
            DeviceType.SECURITY_KEYPAD,
            DeviceType.SMART_DOORBELL,
        ]

        for device in self.home.devices:
            if device.device_type in cred_types:
                targets.append(device.id)

        return targets

    def generate_phase_events(
        self,
        instance: ThreatInstance,
        current_time: datetime,
    ) -> list[SimulationEvent]:
        """Generate credential theft events."""
        events = []

        if instance.phase == ThreatPhase.RECONNAISSANCE:
            if self.rng.random() < 0.3:
                events.append(self._create_event(
                    instance,
                    EventType.NETWORK_TRAFFIC,
                    "scanner",
                    current_time,
                    {
                        "action": "auth_endpoint_scan",
                        "targets": len(instance.target_device_ids),
                        "endpoints_found": self.rng.randint(1, len(instance.target_device_ids)),
                    },
                ))

        elif instance.phase == ThreatPhase.INITIAL_ACCESS:
            if self.rng.random() < 0.35 and instance.target_device_ids:
                target = self.rng.choice(instance.target_device_ids)

                events.append(self._create_event(
                    instance,
                    EventType.DEVICE_STATE_CHANGE,
                    target,
                    current_time,
                    {
                        "action": "brute_force_attempt",
                        "attempts": self.rng.randint(100, 1000),
                        "rate_limited": self.rng.choice([True, False]),
                    },
                ))

                if self.rng.random() < 0.4:
                    instance.compromised_device_ids.append(target)

        elif instance.phase == ThreatPhase.EXECUTION:
            if instance.compromised_device_ids:
                target = self.rng.choice(instance.compromised_device_ids)

                # Extract credentials
                if self.rng.random() < 0.4:
                    self.credentials_stolen += 1
                    cred_types = ["admin_password", "api_key", "wifi_psk", "oauth_token"]

                    events.append(self._create_event(
                        instance,
                        EventType.DEVICE_DATA_GENERATED,
                        target,
                        current_time,
                        {
                            "action": "credential_extraction",
                            "credential_type": self.rng.choice(cred_types),
                            "method": self.rng.choice(["memory_dump", "config_read", "mitm"]),
                        },
                    ))

                    instance.data_exfiltrated_bytes += self.rng.randint(100, 500)

        elif instance.phase == ThreatPhase.EXFILTRATION:
            if self.credentials_stolen > 0 and self.rng.random() < 0.4:
                events.append(self._create_event(
                    instance,
                    EventType.NETWORK_TRAFFIC,
                    "exfil",
                    current_time,
                    {
                        "action": "credentials_exfiltrated",
                        "count": self.credentials_stolen,
                        "destination": "c2_server",
                        "encrypted": True,
                    },
                ))

        return events

    def advance_phase(
        self,
        instance: ThreatInstance,
        current_time: datetime,
    ) -> ThreatPhase:
        """Advance credential theft phases."""
        if not instance.phase_start_time:
            return instance.phase

        elapsed = (current_time - instance.phase_start_time).total_seconds() / 60

        if instance.phase == ThreatPhase.RECONNAISSANCE:
            if elapsed > 3:
                return ThreatPhase.INITIAL_ACCESS

        elif instance.phase == ThreatPhase.INITIAL_ACCESS:
            if instance.compromised_device_ids and elapsed > 5:
                return ThreatPhase.EXECUTION
            elif elapsed > 12:
                return ThreatPhase.COMPLETED

        elif instance.phase == ThreatPhase.EXECUTION:
            if elapsed > instance.planned_duration_minutes * 0.6:
                return ThreatPhase.EXFILTRATION

        elif instance.phase == ThreatPhase.EXFILTRATION:
            if elapsed > instance.planned_duration_minutes * 0.3:
                return ThreatPhase.COMPLETED

        return instance.phase


class DenialOfServiceScenario(ThreatScenario):
    """
    Denial of Service Scenario.

    Renders IoT devices unavailable through resource
    exhaustion or network flooding.
    """

    def __init__(self, threat_type: ThreatType, home: Home, seed: Optional[int] = None):
        super().__init__(threat_type, home, seed)
        self.attack_type = self.rng.choice(["flood", "amplification", "slowloris"])

    def select_targets(self) -> list[str]:
        """Select critical devices for DoS."""
        targets = []
        dos_types = [
            DeviceType.HUB,
            DeviceType.ROUTER,
            DeviceType.SMART_LOCK,
            DeviceType.THERMOSTAT,
            DeviceType.SECURITY_KEYPAD,
        ]

        for device in self.home.devices:
            if device.device_type in dos_types:
                targets.append(device.id)

        return targets

    def generate_phase_events(
        self,
        instance: ThreatInstance,
        current_time: datetime,
    ) -> list[SimulationEvent]:
        """Generate DoS events."""
        events = []

        if instance.phase == ThreatPhase.RECONNAISSANCE:
            if self.rng.random() < 0.3:
                events.append(self._create_event(
                    instance,
                    EventType.NETWORK_TRAFFIC,
                    "scanner",
                    current_time,
                    {
                        "action": "service_scan",
                        "targets": len(instance.target_device_ids),
                        "open_ports_found": self.rng.randint(2, 10),
                    },
                ))

        elif instance.phase == ThreatPhase.EXECUTION:
            if instance.target_device_ids:
                target = self.rng.choice(instance.target_device_ids)

                # Execute DoS attack
                if self.rng.random() < 0.5:
                    packets = self.rng.randint(1000, 100000)

                    events.append(self._create_event(
                        instance,
                        EventType.NETWORK_TRAFFIC,
                        target,
                        current_time,
                        {
                            "action": "dos_attack",
                            "type": self.attack_type,
                            "packets_per_second": packets,
                            "bandwidth_mbps": packets * self.rng.uniform(0.001, 0.01),
                        },
                    ))

                # Device becomes unresponsive
                if self.rng.random() < 0.3:
                    events.append(self._create_event(
                        instance,
                        EventType.DEVICE_STATE_CHANGE,
                        target,
                        current_time,
                        {
                            "action": "device_degraded",
                            "response_time_ms": self.rng.randint(5000, 30000),
                            "packet_loss_percent": self.rng.randint(50, 100),
                        },
                    ))

        return events

    def advance_phase(
        self,
        instance: ThreatInstance,
        current_time: datetime,
    ) -> ThreatPhase:
        """Advance DoS phases."""
        if not instance.phase_start_time:
            return instance.phase

        elapsed = (current_time - instance.phase_start_time).total_seconds() / 60

        if instance.phase == ThreatPhase.RECONNAISSANCE:
            if elapsed > 2:
                return ThreatPhase.EXECUTION

        elif instance.phase == ThreatPhase.EXECUTION:
            if elapsed > instance.planned_duration_minutes:
                return ThreatPhase.COMPLETED

        return instance.phase


class ManInTheMiddleScenario(ThreatScenario):
    """
    Man-in-the-Middle Attack Scenario.

    Intercepts and potentially modifies communications between
    IoT devices and their control systems. Uses ARP spoofing,
    SSL stripping, and packet injection techniques.
    """

    def __init__(self, threat_type: ThreatType, home: Home, seed: Optional[int] = None):
        super().__init__(threat_type, home, seed)
        self.interception_method = self.rng.choice([
            "arp_spoofing",
            "ssl_stripping",
            "rogue_ap",
        ])
        self.packets_intercepted = 0
        self.packets_modified = 0

    def select_targets(self) -> list[str]:
        """Select network devices and high-value targets."""
        targets = []
        mitm_types = [
            DeviceType.HUB,
            DeviceType.ROUTER,
            DeviceType.SMART_LOCK,
            DeviceType.THERMOSTAT,
            DeviceType.SECURITY_CAMERA,
            DeviceType.SMART_DOORBELL,
        ]

        for device in self.home.devices:
            if device.device_type in mitm_types:
                targets.append(device.id)

        return targets[:5]

    def generate_phase_events(
        self,
        instance: ThreatInstance,
        current_time: datetime,
    ) -> list[SimulationEvent]:
        """Generate MITM attack events."""
        events = []

        if instance.phase == ThreatPhase.RECONNAISSANCE:
            if self.rng.random() < 0.3:
                events.append(self._create_event(
                    instance,
                    EventType.NETWORK_TRAFFIC,
                    "scanner",
                    current_time,
                    {
                        "action": "network_mapping",
                        "devices_discovered": len(instance.target_device_ids),
                        "gateway_identified": True,
                        "arp_table_captured": True,
                    },
                ))

        elif instance.phase == ThreatPhase.INITIAL_ACCESS:
            if self.rng.random() < 0.4:
                events.append(self._create_event(
                    instance,
                    EventType.NETWORK_TRAFFIC,
                    "attacker",
                    current_time,
                    {
                        "action": "mitm_setup",
                        "method": self.interception_method,
                        "target_gateway": "router",
                        "spoofed_mac": f"00:11:22:{self.rng.randint(10, 99)}:{self.rng.randint(10, 99)}:{self.rng.randint(10, 99)}",
                    },
                ))

                # MITM positioned successfully
                if self.rng.random() < 0.7:
                    instance.compromised_device_ids = ["mitm_position"]

        elif instance.phase == ThreatPhase.EXECUTION:
            if instance.compromised_device_ids:
                # Intercept traffic
                if self.rng.random() < 0.5 and instance.target_device_ids:
                    target = self.rng.choice(instance.target_device_ids)
                    packets = self.rng.randint(10, 100)
                    self.packets_intercepted += packets

                    events.append(self._create_event(
                        instance,
                        EventType.NETWORK_TRAFFIC,
                        target,
                        current_time,
                        {
                            "action": "traffic_interception",
                            "packets_captured": packets,
                            "protocols": self.rng.choice([
                                ["http", "mqtt"],
                                ["coap", "http"],
                                ["mqtt", "websocket"],
                            ]),
                            "sensitive_data_found": self.rng.choice([True, False]),
                        },
                    ))

                # Modify traffic
                if self.rng.random() < 0.3:
                    target = self.rng.choice(instance.target_device_ids)
                    modified = self.rng.randint(1, 10)
                    self.packets_modified += modified

                    events.append(self._create_event(
                        instance,
                        EventType.NETWORK_TRAFFIC,
                        target,
                        current_time,
                        {
                            "action": "packet_modification",
                            "packets_modified": modified,
                            "modification_type": self.rng.choice([
                                "command_injection",
                                "data_alteration",
                                "credential_capture",
                            ]),
                            "total_intercepted": self.packets_intercepted,
                        },
                    ))

                # SSL stripping attempt
                if self.interception_method == "ssl_stripping" and self.rng.random() < 0.2:
                    events.append(self._create_event(
                        instance,
                        EventType.NETWORK_TRAFFIC,
                        "ssl_stripper",
                        current_time,
                        {
                            "action": "ssl_downgrade",
                            "original_protocol": "https",
                            "downgraded_to": "http",
                            "success": self.rng.random() < 0.6,
                        },
                    ))

        elif instance.phase == ThreatPhase.EXFILTRATION:
            if self.rng.random() < 0.4:
                bytes_sent = self.rng.randint(1000, 10000)
                instance.data_exfiltrated_bytes += bytes_sent

                events.append(self._create_event(
                    instance,
                    EventType.NETWORK_TRAFFIC,
                    "exfil",
                    current_time,
                    {
                        "action": "captured_data_exfiltration",
                        "bytes_sent": bytes_sent,
                        "data_types": ["credentials", "commands", "sensor_data"],
                        "total_packets_intercepted": self.packets_intercepted,
                        "total_packets_modified": self.packets_modified,
                    },
                ))

        return events

    def advance_phase(
        self,
        instance: ThreatInstance,
        current_time: datetime,
    ) -> ThreatPhase:
        """Advance MITM attack phases."""
        if not instance.phase_start_time:
            return instance.phase

        elapsed = (current_time - instance.phase_start_time).total_seconds() / 60

        if instance.phase == ThreatPhase.RECONNAISSANCE:
            if elapsed > 3:
                return ThreatPhase.INITIAL_ACCESS

        elif instance.phase == ThreatPhase.INITIAL_ACCESS:
            if instance.compromised_device_ids and elapsed > 2:
                return ThreatPhase.EXECUTION
            elif elapsed > 10:
                return ThreatPhase.COMPLETED

        elif instance.phase == ThreatPhase.EXECUTION:
            if elapsed > instance.planned_duration_minutes * 0.7:
                return ThreatPhase.EXFILTRATION

        elif instance.phase == ThreatPhase.EXFILTRATION:
            if elapsed > instance.planned_duration_minutes * 0.2:
                return ThreatPhase.CLEANUP

        elif instance.phase == ThreatPhase.CLEANUP:
            if elapsed > 2:
                return ThreatPhase.COMPLETED

        return instance.phase


class DNSSpoofingScenario(ThreatScenario):
    """
    DNS Spoofing Attack Scenario.

    Poisons DNS responses to redirect IoT device traffic to
    malicious servers for data interception or malware delivery.
    """

    def __init__(self, threat_type: ThreatType, home: Home, seed: Optional[int] = None):
        super().__init__(threat_type, home, seed)
        self.spoofed_domains = []
        self.redirected_requests = 0
        self.malicious_ip = f"192.168.{self.rng.randint(100, 200)}.{self.rng.randint(1, 254)}"

    def select_targets(self) -> list[str]:
        """Select devices that make DNS queries."""
        targets = []
        dns_types = [
            DeviceType.ROUTER,
            DeviceType.HUB,
            DeviceType.SMART_TV,
            DeviceType.SECURITY_CAMERA,
            DeviceType.SMART_SPEAKER,
            DeviceType.SMART_DOORBELL,
        ]

        for device in self.home.devices:
            if device.device_type in dns_types:
                targets.append(device.id)

        return targets

    def generate_phase_events(
        self,
        instance: ThreatInstance,
        current_time: datetime,
    ) -> list[SimulationEvent]:
        """Generate DNS spoofing events."""
        events = []

        if instance.phase == ThreatPhase.RECONNAISSANCE:
            if self.rng.random() < 0.3:
                events.append(self._create_event(
                    instance,
                    EventType.NETWORK_TRAFFIC,
                    "dns_scanner",
                    current_time,
                    {
                        "action": "dns_traffic_analysis",
                        "queries_observed": self.rng.randint(50, 200),
                        "unique_domains": self.rng.randint(10, 30),
                        "dns_server_identified": True,
                    },
                ))

        elif instance.phase == ThreatPhase.INITIAL_ACCESS:
            if self.rng.random() < 0.35:
                # Attempt to poison DNS cache
                target_domains = [
                    "api.smartdevice.com",
                    "update.iot-vendor.com",
                    "cloud.home-automation.net",
                    "firmware.device-maker.io",
                ]
                domain = self.rng.choice(target_domains)
                success = self.rng.random() < 0.6

                events.append(self._create_event(
                    instance,
                    EventType.NETWORK_TRAFFIC,
                    "dns_poisoner",
                    current_time,
                    {
                        "action": "dns_cache_poisoning",
                        "target_domain": domain,
                        "spoofed_ip": self.malicious_ip,
                        "ttl_seconds": self.rng.randint(300, 3600),
                        "success": success,
                    },
                ))

                if success:
                    self.spoofed_domains.append(domain)
                    if not instance.compromised_device_ids:
                        instance.compromised_device_ids = ["dns_poisoned"]

        elif instance.phase == ThreatPhase.EXECUTION:
            if instance.compromised_device_ids and self.spoofed_domains:
                # Redirect traffic
                if self.rng.random() < 0.5 and instance.target_device_ids:
                    target = self.rng.choice(instance.target_device_ids)
                    domain = self.rng.choice(self.spoofed_domains)
                    self.redirected_requests += 1

                    events.append(self._create_event(
                        instance,
                        EventType.NETWORK_TRAFFIC,
                        target,
                        current_time,
                        {
                            "action": "traffic_redirected",
                            "original_domain": domain,
                            "redirected_to": self.malicious_ip,
                            "request_type": self.rng.choice(["api_call", "update_check", "telemetry"]),
                            "total_redirected": self.redirected_requests,
                        },
                    ))

                # Capture credentials or data
                if self.rng.random() < 0.3:
                    events.append(self._create_event(
                        instance,
                        EventType.DEVICE_DATA_GENERATED,
                        "fake_server",
                        current_time,
                        {
                            "action": "data_captured",
                            "data_type": self.rng.choice([
                                "api_credentials",
                                "device_token",
                                "user_data",
                                "firmware_request",
                            ]),
                            "bytes_captured": self.rng.randint(100, 5000),
                        },
                    ))

                    instance.data_exfiltrated_bytes += self.rng.randint(100, 5000)

                # Serve malicious content
                if self.rng.random() < 0.2:
                    events.append(self._create_event(
                        instance,
                        EventType.NETWORK_TRAFFIC,
                        "fake_server",
                        current_time,
                        {
                            "action": "malicious_response",
                            "response_type": self.rng.choice([
                                "fake_update",
                                "modified_config",
                                "credential_phish",
                            ]),
                            "bytes_sent": self.rng.randint(1000, 50000),
                        },
                    ))

        return events

    def advance_phase(
        self,
        instance: ThreatInstance,
        current_time: datetime,
    ) -> ThreatPhase:
        """Advance DNS spoofing phases."""
        if not instance.phase_start_time:
            return instance.phase

        elapsed = (current_time - instance.phase_start_time).total_seconds() / 60

        if instance.phase == ThreatPhase.RECONNAISSANCE:
            if elapsed > 3:
                return ThreatPhase.INITIAL_ACCESS

        elif instance.phase == ThreatPhase.INITIAL_ACCESS:
            if self.spoofed_domains and elapsed > 3:
                return ThreatPhase.EXECUTION
            elif elapsed > 12:
                return ThreatPhase.COMPLETED

        elif instance.phase == ThreatPhase.EXECUTION:
            if elapsed > instance.planned_duration_minutes:
                return ThreatPhase.COMPLETED

        return instance.phase


class ARPPoisoningScenario(ThreatScenario):
    """
    ARP Cache Poisoning Scenario.

    Sends falsified ARP messages to link attacker's MAC address
    with legitimate network devices, enabling traffic interception.
    """

    def __init__(self, threat_type: ThreatType, home: Home, seed: Optional[int] = None):
        super().__init__(threat_type, home, seed)
        self.attacker_mac = f"de:ad:be:ef:{self.rng.randint(10, 99)}:{self.rng.randint(10, 99)}"
        self.poisoned_entries = 0
        self.intercepted_traffic_bytes = 0

    def select_targets(self) -> list[str]:
        """Select network devices for ARP poisoning."""
        targets = []
        arp_types = [
            DeviceType.ROUTER,
            DeviceType.HUB,
            DeviceType.SECURITY_CAMERA,
            DeviceType.SMART_LOCK,
            DeviceType.THERMOSTAT,
            DeviceType.SMART_TV,
        ]

        for device in self.home.devices:
            if device.device_type in arp_types:
                targets.append(device.id)

        return targets

    def generate_phase_events(
        self,
        instance: ThreatInstance,
        current_time: datetime,
    ) -> list[SimulationEvent]:
        """Generate ARP poisoning events."""
        events = []

        if instance.phase == ThreatPhase.RECONNAISSANCE:
            if self.rng.random() < 0.35:
                events.append(self._create_event(
                    instance,
                    EventType.NETWORK_TRAFFIC,
                    "arp_scanner",
                    current_time,
                    {
                        "action": "arp_table_scan",
                        "entries_discovered": len(instance.target_device_ids) + self.rng.randint(5, 15),
                        "gateway_mac": f"aa:bb:cc:{self.rng.randint(10, 99)}:{self.rng.randint(10, 99)}:{self.rng.randint(10, 99)}",
                        "network_segment": "192.168.1.0/24",
                    },
                ))

        elif instance.phase == ThreatPhase.INITIAL_ACCESS:
            if self.rng.random() < 0.4 and instance.target_device_ids:
                target = self.rng.choice(instance.target_device_ids)

                # Send gratuitous ARP
                events.append(self._create_event(
                    instance,
                    EventType.NETWORK_TRAFFIC,
                    "arp_poisoner",
                    current_time,
                    {
                        "action": "gratuitous_arp",
                        "target_device": target,
                        "spoofed_ip": f"192.168.1.{self.rng.randint(1, 254)}",
                        "attacker_mac": self.attacker_mac,
                        "arp_type": self.rng.choice(["reply", "request"]),
                    },
                ))

                if self.rng.random() < 0.7:
                    self.poisoned_entries += 1
                    if target not in instance.compromised_device_ids:
                        instance.compromised_device_ids.append(target)

        elif instance.phase == ThreatPhase.EXECUTION:
            if instance.compromised_device_ids:
                # Maintain ARP poisoning
                if self.rng.random() < 0.3:
                    events.append(self._create_event(
                        instance,
                        EventType.NETWORK_TRAFFIC,
                        "arp_maintainer",
                        current_time,
                        {
                            "action": "arp_refresh",
                            "poisoned_entries": self.poisoned_entries,
                            "refresh_interval_seconds": self.rng.randint(10, 30),
                        },
                    ))

                # Intercept traffic
                if self.rng.random() < 0.5:
                    target = self.rng.choice(instance.compromised_device_ids)
                    bytes_captured = self.rng.randint(500, 5000)
                    self.intercepted_traffic_bytes += bytes_captured

                    events.append(self._create_event(
                        instance,
                        EventType.NETWORK_TRAFFIC,
                        target,
                        current_time,
                        {
                            "action": "traffic_capture",
                            "bytes_intercepted": bytes_captured,
                            "packet_types": self.rng.choice([
                                ["tcp", "udp"],
                                ["mqtt", "http"],
                                ["coap", "tcp"],
                            ]),
                            "forwarded_to_destination": True,
                            "total_bytes_captured": self.intercepted_traffic_bytes,
                        },
                    ))

                # Modify intercepted traffic
                if self.rng.random() < 0.2:
                    events.append(self._create_event(
                        instance,
                        EventType.NETWORK_TRAFFIC,
                        "traffic_modifier",
                        current_time,
                        {
                            "action": "packet_manipulation",
                            "manipulation_type": self.rng.choice([
                                "command_injection",
                                "response_modification",
                                "credential_theft",
                            ]),
                            "packets_modified": self.rng.randint(1, 10),
                        },
                    ))

        elif instance.phase == ThreatPhase.CLEANUP:
            if self.rng.random() < 0.5:
                events.append(self._create_event(
                    instance,
                    EventType.NETWORK_TRAFFIC,
                    "cleanup",
                    current_time,
                    {
                        "action": "arp_cache_restore",
                        "entries_restored": self.poisoned_entries,
                        "total_traffic_intercepted_bytes": self.intercepted_traffic_bytes,
                    },
                ))

        return events

    def advance_phase(
        self,
        instance: ThreatInstance,
        current_time: datetime,
    ) -> ThreatPhase:
        """Advance ARP poisoning phases."""
        if not instance.phase_start_time:
            return instance.phase

        elapsed = (current_time - instance.phase_start_time).total_seconds() / 60

        if instance.phase == ThreatPhase.RECONNAISSANCE:
            if elapsed > 2:
                return ThreatPhase.INITIAL_ACCESS

        elif instance.phase == ThreatPhase.INITIAL_ACCESS:
            if instance.compromised_device_ids and elapsed > 3:
                return ThreatPhase.EXECUTION
            elif elapsed > 8:
                return ThreatPhase.COMPLETED

        elif instance.phase == ThreatPhase.EXECUTION:
            if elapsed > instance.planned_duration_minutes * 0.85:
                return ThreatPhase.CLEANUP

        elif instance.phase == ThreatPhase.CLEANUP:
            if elapsed > 2:
                return ThreatPhase.COMPLETED

        return instance.phase


class MeterTamperingScenario(ThreatScenario):
    """
    Smart Meter Tampering Scenario.

    Direct manipulation of smart meter hardware or software to
    falsify energy readings or bypass metering entirely. Requires
    physical access to the meter in most cases.
    """

    def __init__(self, threat_type: ThreatType, home: Home, seed: Optional[int] = None):
        super().__init__(threat_type, home, seed)
        self.tampering_method = self.rng.choice([
            "calibration_manipulation",
            "pulse_interception",
            "register_modification",
            "bypass_installation",
        ])
        self.original_calibration = 1.0
        self.tampered_calibration = self.rng.uniform(0.5, 0.8)

    def select_targets(self) -> list[str]:
        """Select smart meters and energy monitors."""
        targets = []
        meter_types = [
            DeviceType.SMART_METER,
            DeviceType.ENERGY_MONITOR,
        ]

        for device in self.home.devices:
            if device.device_type in meter_types:
                targets.append(device.id)

        return targets

    def generate_phase_events(
        self,
        instance: ThreatInstance,
        current_time: datetime,
    ) -> list[SimulationEvent]:
        """Generate meter tampering events."""
        events = []

        if instance.phase == ThreatPhase.RECONNAISSANCE:
            if self.rng.random() < 0.3:
                events.append(self._create_event(
                    instance,
                    EventType.NETWORK_TRAFFIC,
                    "meter_scanner",
                    current_time,
                    {
                        "action": "meter_inspection",
                        "meters_found": len(instance.target_device_ids),
                        "meter_model": f"SM-{self.rng.randint(1000, 9999)}",
                        "firmware_version": f"v{self.rng.randint(1, 5)}.{self.rng.randint(0, 9)}",
                        "security_seal_status": "intact",
                    },
                ))

        elif instance.phase == ThreatPhase.INITIAL_ACCESS:
            if self.rng.random() < 0.35 and instance.target_device_ids:
                target = self.rng.choice(instance.target_device_ids)

                events.append(self._create_event(
                    instance,
                    EventType.DEVICE_STATE_CHANGE,
                    target,
                    current_time,
                    {
                        "action": "physical_access_gained",
                        "method": self.rng.choice([
                            "meter_cover_removed",
                            "optical_port_access",
                            "debug_port_connection",
                        ]),
                        "seal_tampered": True,
                    },
                ))

                if self.rng.random() < 0.6:
                    instance.compromised_device_ids.append(target)

        elif instance.phase == ThreatPhase.EXECUTION:
            if instance.compromised_device_ids:
                target = self.rng.choice(instance.compromised_device_ids)

                # Perform tampering based on method
                if self.tampering_method == "calibration_manipulation":
                    if self.rng.random() < 0.4:
                        events.append(self._create_event(
                            instance,
                            EventType.DEVICE_STATE_CHANGE,
                            target,
                            current_time,
                            {
                                "action": "calibration_modified",
                                "original_factor": self.original_calibration,
                                "new_factor": round(self.tampered_calibration, 3),
                                "reading_reduction_percent": round(
                                    (1 - self.tampered_calibration) * 100, 1
                                ),
                            },
                        ))

                elif self.tampering_method == "pulse_interception":
                    if self.rng.random() < 0.4:
                        events.append(self._create_event(
                            instance,
                            EventType.DEVICE_STATE_CHANGE,
                            target,
                            current_time,
                            {
                                "action": "pulse_interception_device_installed",
                                "pulses_blocked_percent": self.rng.randint(20, 50),
                                "detection_risk": "low",
                            },
                        ))

                elif self.tampering_method == "register_modification":
                    if self.rng.random() < 0.4:
                        original_reading = self.rng.uniform(10000, 50000)
                        events.append(self._create_event(
                            instance,
                            EventType.DEVICE_STATE_CHANGE,
                            target,
                            current_time,
                            {
                                "action": "register_value_modified",
                                "original_kwh": round(original_reading, 2),
                                "new_kwh": round(original_reading * 0.7, 2),
                                "rollback_detected": False,
                            },
                        ))

                elif self.tampering_method == "bypass_installation":
                    if self.rng.random() < 0.3:
                        events.append(self._create_event(
                            instance,
                            EventType.DEVICE_STATE_CHANGE,
                            target,
                            current_time,
                            {
                                "action": "bypass_installed",
                                "bypass_type": self.rng.choice([
                                    "jumper_wire",
                                    "parallel_circuit",
                                    "neutral_diversion",
                                ]),
                                "metered_load_percent": self.rng.randint(30, 70),
                            },
                        ))

        elif instance.phase == ThreatPhase.PERSISTENCE:
            if self.rng.random() < 0.2 and instance.compromised_device_ids:
                target = self.rng.choice(instance.compromised_device_ids)

                events.append(self._create_event(
                    instance,
                    EventType.DEVICE_DATA_GENERATED,
                    target,
                    current_time,
                    {
                        "action": "falsified_reading_reported",
                        "actual_kwh": round(self.rng.uniform(10, 50), 2),
                        "reported_kwh": round(self.rng.uniform(5, 30), 2),
                        "tampering_method": self.tampering_method,
                    },
                ))

        return events

    def advance_phase(
        self,
        instance: ThreatInstance,
        current_time: datetime,
    ) -> ThreatPhase:
        """Advance meter tampering phases."""
        if not instance.phase_start_time:
            return instance.phase

        elapsed = (current_time - instance.phase_start_time).total_seconds() / 60

        if instance.phase == ThreatPhase.RECONNAISSANCE:
            if elapsed > 5:
                return ThreatPhase.INITIAL_ACCESS

        elif instance.phase == ThreatPhase.INITIAL_ACCESS:
            if instance.compromised_device_ids and elapsed > 10:
                return ThreatPhase.EXECUTION
            elif elapsed > 20:
                return ThreatPhase.COMPLETED

        elif instance.phase == ThreatPhase.EXECUTION:
            if elapsed > instance.planned_duration_minutes * 0.6:
                return ThreatPhase.PERSISTENCE

        elif instance.phase == ThreatPhase.PERSISTENCE:
            if elapsed > instance.planned_duration_minutes * 0.4:
                return ThreatPhase.COMPLETED

        return instance.phase


class UsageFalsificationScenario(ThreatScenario):
    """
    Energy Usage Falsification Scenario.

    Manipulates reported energy usage data through software attacks
    on energy monitoring systems. Unlike meter tampering, this is
    purely a software/network attack.
    """

    def __init__(self, threat_type: ThreatType, home: Home, seed: Optional[int] = None):
        super().__init__(threat_type, home, seed)
        self.falsification_method = self.rng.choice([
            "data_injection",
            "report_modification",
            "time_shifting",
            "api_manipulation",
        ])
        self.readings_falsified = 0

    def select_targets(self) -> list[str]:
        """Select energy monitoring devices."""
        targets = []
        energy_types = [
            DeviceType.SMART_METER,
            DeviceType.SMART_PLUG,
            DeviceType.ENERGY_MONITOR,
        ]

        for device in self.home.devices:
            if device.device_type in energy_types:
                targets.append(device.id)

        return targets

    def generate_phase_events(
        self,
        instance: ThreatInstance,
        current_time: datetime,
    ) -> list[SimulationEvent]:
        """Generate usage falsification events."""
        events = []

        if instance.phase == ThreatPhase.RECONNAISSANCE:
            if self.rng.random() < 0.3:
                events.append(self._create_event(
                    instance,
                    EventType.NETWORK_TRAFFIC,
                    "energy_scanner",
                    current_time,
                    {
                        "action": "energy_api_discovery",
                        "endpoints_found": self.rng.randint(3, 8),
                        "authentication_type": self.rng.choice([
                            "oauth",
                            "api_key",
                            "basic_auth",
                        ]),
                        "reporting_interval_minutes": self.rng.choice([5, 15, 30, 60]),
                    },
                ))

        elif instance.phase == ThreatPhase.INITIAL_ACCESS:
            if self.rng.random() < 0.4 and instance.target_device_ids:
                target = self.rng.choice(instance.target_device_ids)
                success = self.rng.random() < 0.5

                events.append(self._create_event(
                    instance,
                    EventType.DEVICE_STATE_CHANGE,
                    target,
                    current_time,
                    {
                        "action": "api_access_attempt",
                        "method": self.rng.choice([
                            "credential_stuffing",
                            "token_theft",
                            "api_key_extraction",
                        ]),
                        "success": success,
                    },
                ))

                if success and target not in instance.compromised_device_ids:
                    instance.compromised_device_ids.append(target)

        elif instance.phase == ThreatPhase.EXECUTION:
            if instance.compromised_device_ids:
                target = self.rng.choice(instance.compromised_device_ids)

                if self.falsification_method == "data_injection":
                    if self.rng.random() < 0.4:
                        actual_kwh = self.rng.uniform(5, 30)
                        self.readings_falsified += 1

                        events.append(self._create_event(
                            instance,
                            EventType.DEVICE_DATA_GENERATED,
                            target,
                            current_time,
                            {
                                "action": "false_reading_injected",
                                "actual_kwh": round(actual_kwh, 2),
                                "injected_kwh": round(actual_kwh * self.rng.uniform(0.5, 0.8), 2),
                                "readings_falsified": self.readings_falsified,
                            },
                        ))

                elif self.falsification_method == "report_modification":
                    if self.rng.random() < 0.4:
                        events.append(self._create_event(
                            instance,
                            EventType.NETWORK_TRAFFIC,
                            target,
                            current_time,
                            {
                                "action": "report_intercepted_and_modified",
                                "original_total_kwh": round(self.rng.uniform(100, 500), 2),
                                "modified_total_kwh": round(self.rng.uniform(50, 350), 2),
                                "modification_method": "mitm_modification",
                            },
                        ))
                        self.readings_falsified += 1

                elif self.falsification_method == "time_shifting":
                    if self.rng.random() < 0.4:
                        events.append(self._create_event(
                            instance,
                            EventType.DEVICE_DATA_GENERATED,
                            target,
                            current_time,
                            {
                                "action": "usage_time_shifted",
                                "original_timestamp": current_time.isoformat(),
                                "shifted_timestamp": (
                                    current_time - timedelta(hours=self.rng.randint(1, 6))
                                ).isoformat(),
                                "purpose": "off_peak_billing",
                            },
                        ))
                        self.readings_falsified += 1

                elif self.falsification_method == "api_manipulation":
                    if self.rng.random() < 0.4:
                        events.append(self._create_event(
                            instance,
                            EventType.NETWORK_TRAFFIC,
                            target,
                            current_time,
                            {
                                "action": "api_request_manipulation",
                                "endpoint": "/api/v1/usage/submit",
                                "original_value": round(self.rng.uniform(10, 50), 2),
                                "submitted_value": round(self.rng.uniform(5, 30), 2),
                            },
                        ))
                        self.readings_falsified += 1

        return events

    def advance_phase(
        self,
        instance: ThreatInstance,
        current_time: datetime,
    ) -> ThreatPhase:
        """Advance usage falsification phases."""
        if not instance.phase_start_time:
            return instance.phase

        elapsed = (current_time - instance.phase_start_time).total_seconds() / 60

        if instance.phase == ThreatPhase.RECONNAISSANCE:
            if elapsed > 3:
                return ThreatPhase.INITIAL_ACCESS

        elif instance.phase == ThreatPhase.INITIAL_ACCESS:
            if instance.compromised_device_ids and elapsed > 5:
                return ThreatPhase.EXECUTION
            elif elapsed > 15:
                return ThreatPhase.COMPLETED

        elif instance.phase == ThreatPhase.EXECUTION:
            if elapsed > instance.planned_duration_minutes:
                return ThreatPhase.COMPLETED

        return instance.phase


class JammingScenario(ThreatScenario):
    """
    Wireless Jamming Scenario.

    Disrupts wireless communications between IoT devices by
    broadcasting interference signals on WiFi, Zigbee, Z-Wave,
    or Bluetooth frequencies.
    """

    def __init__(self, threat_type: ThreatType, home: Home, seed: Optional[int] = None):
        super().__init__(threat_type, home, seed)
        self.jamming_type = self.rng.choice([
            "continuous",
            "intermittent",
            "reactive",
            "selective",
        ])
        self.target_frequency = self.rng.choice([
            "2.4ghz_wifi",
            "5ghz_wifi",
            "zigbee",
            "z_wave",
            "bluetooth",
        ])
        self.devices_affected = 0

    def select_targets(self) -> list[str]:
        """Select wireless devices vulnerable to jamming."""
        targets = []
        wireless_types = [
            DeviceType.MOTION_SENSOR,
            DeviceType.DOOR_SENSOR,
            DeviceType.WINDOW_SENSOR,
            DeviceType.SMART_LOCK,
            DeviceType.SECURITY_CAMERA,
            DeviceType.SMOKE_DETECTOR,
            DeviceType.THERMOSTAT,
        ]

        for device in self.home.devices:
            if device.device_type in wireless_types:
                targets.append(device.id)

        return targets

    def generate_phase_events(
        self,
        instance: ThreatInstance,
        current_time: datetime,
    ) -> list[SimulationEvent]:
        """Generate jamming attack events."""
        events = []

        if instance.phase == ThreatPhase.RECONNAISSANCE:
            if self.rng.random() < 0.35:
                events.append(self._create_event(
                    instance,
                    EventType.NETWORK_TRAFFIC,
                    "spectrum_analyzer",
                    current_time,
                    {
                        "action": "spectrum_analysis",
                        "frequencies_scanned": ["2.4ghz", "5ghz", "868mhz", "915mhz"],
                        "active_channels": self.rng.randint(3, 10),
                        "devices_detected": len(instance.target_device_ids),
                        "noise_floor_dbm": self.rng.randint(-90, -70),
                    },
                ))

        elif instance.phase == ThreatPhase.EXECUTION:
            # Start jamming
            if self.rng.random() < 0.4:
                events.append(self._create_event(
                    instance,
                    EventType.NETWORK_TRAFFIC,
                    "jammer",
                    current_time,
                    {
                        "action": "jamming_active",
                        "jamming_type": self.jamming_type,
                        "target_frequency": self.target_frequency,
                        "power_dbm": self.rng.randint(10, 30),
                        "bandwidth_mhz": self.rng.randint(20, 80),
                    },
                ))

            # Device communication disruption
            if self.rng.random() < 0.5 and instance.target_device_ids:
                target = self.rng.choice(instance.target_device_ids)
                self.devices_affected += 1

                events.append(self._create_event(
                    instance,
                    EventType.DEVICE_STATE_CHANGE,
                    target,
                    current_time,
                    {
                        "action": "communication_disrupted",
                        "signal_strength_dbm": self.rng.randint(-95, -80),
                        "packet_loss_percent": self.rng.randint(50, 100),
                        "connection_status": self.rng.choice([
                            "degraded",
                            "disconnected",
                            "intermittent",
                        ]),
                        "total_devices_affected": self.devices_affected,
                    },
                ))

            # Security system impact
            if self.rng.random() < 0.3:
                events.append(self._create_event(
                    instance,
                    EventType.SYSTEM_EVENT,
                    "security_system",
                    current_time,
                    {
                        "action": "sensor_offline_alert",
                        "offline_sensors": self.rng.randint(1, len(instance.target_device_ids)),
                        "alert_triggered": self.rng.choice([True, False]),
                        "backup_channel_available": self.rng.choice([True, False]),
                    },
                ))

            # Intermittent jamming pattern
            if self.jamming_type == "intermittent" and self.rng.random() < 0.3:
                events.append(self._create_event(
                    instance,
                    EventType.NETWORK_TRAFFIC,
                    "jammer",
                    current_time,
                    {
                        "action": "jamming_pulse",
                        "duration_ms": self.rng.randint(100, 1000),
                        "interval_ms": self.rng.randint(500, 5000),
                        "purpose": "detection_evasion",
                    },
                ))

        return events

    def advance_phase(
        self,
        instance: ThreatInstance,
        current_time: datetime,
    ) -> ThreatPhase:
        """Advance jamming attack phases."""
        if not instance.phase_start_time:
            return instance.phase

        elapsed = (current_time - instance.phase_start_time).total_seconds() / 60

        if instance.phase == ThreatPhase.RECONNAISSANCE:
            if elapsed > 3:
                return ThreatPhase.EXECUTION

        elif instance.phase == ThreatPhase.EXECUTION:
            if elapsed > instance.planned_duration_minutes:
                return ThreatPhase.COMPLETED

        return instance.phase


class ResourceExhaustionScenario(ThreatScenario):
    """
    Resource Exhaustion Attack Scenario.

    Exhausts device resources (CPU, memory, storage, battery) to
    degrade performance or cause device failure.
    """

    def __init__(self, threat_type: ThreatType, home: Home, seed: Optional[int] = None):
        super().__init__(threat_type, home, seed)
        self.exhaustion_method = self.rng.choice([
            "cpu_intensive",
            "memory_exhaustion",
            "storage_fill",
            "battery_drain",
            "connection_exhaustion",
        ])

    def select_targets(self) -> list[str]:
        """Select devices vulnerable to resource exhaustion."""
        targets = []
        resource_types = [
            DeviceType.HUB,
            DeviceType.SECURITY_CAMERA,
            DeviceType.SMART_SPEAKER,
            DeviceType.MOTION_SENSOR,
            DeviceType.SMART_DOORBELL,
            DeviceType.THERMOSTAT,
        ]

        for device in self.home.devices:
            if device.device_type in resource_types:
                targets.append(device.id)

        return targets

    def generate_phase_events(
        self,
        instance: ThreatInstance,
        current_time: datetime,
    ) -> list[SimulationEvent]:
        """Generate resource exhaustion events."""
        events = []

        if instance.phase == ThreatPhase.RECONNAISSANCE:
            if self.rng.random() < 0.3:
                events.append(self._create_event(
                    instance,
                    EventType.NETWORK_TRAFFIC,
                    "resource_scanner",
                    current_time,
                    {
                        "action": "device_profiling",
                        "devices_profiled": len(instance.target_device_ids),
                        "resource_constraints_identified": [
                            "limited_memory",
                            "constrained_cpu",
                            "battery_powered",
                        ],
                    },
                ))

        elif instance.phase == ThreatPhase.INITIAL_ACCESS:
            if self.rng.random() < 0.4 and instance.target_device_ids:
                target = self.rng.choice(instance.target_device_ids)

                events.append(self._create_event(
                    instance,
                    EventType.NETWORK_TRAFFIC,
                    "attacker",
                    current_time,
                    {
                        "action": "connection_established",
                        "target": target,
                        "protocol": self.rng.choice(["http", "mqtt", "coap"]),
                        "connections_opened": self.rng.randint(5, 50),
                    },
                ))

                if self.rng.random() < 0.7:
                    instance.compromised_device_ids.append(target)

        elif instance.phase == ThreatPhase.EXECUTION:
            if instance.target_device_ids:
                target = self.rng.choice(instance.target_device_ids)

                if self.exhaustion_method == "cpu_intensive":
                    if self.rng.random() < 0.4:
                        events.append(self._create_event(
                            instance,
                            EventType.DEVICE_STATE_CHANGE,
                            target,
                            current_time,
                            {
                                "action": "cpu_exhaustion_attack",
                                "request_type": self.rng.choice([
                                    "crypto_operations",
                                    "complex_queries",
                                    "recursive_processing",
                                ]),
                                "cpu_usage_percent": self.rng.randint(85, 100),
                                "response_time_ms": self.rng.randint(5000, 30000),
                            },
                        ))

                elif self.exhaustion_method == "memory_exhaustion":
                    if self.rng.random() < 0.4:
                        events.append(self._create_event(
                            instance,
                            EventType.DEVICE_STATE_CHANGE,
                            target,
                            current_time,
                            {
                                "action": "memory_exhaustion_attack",
                                "method": self.rng.choice([
                                    "large_payload_requests",
                                    "session_accumulation",
                                    "cache_flooding",
                                ]),
                                "memory_usage_percent": self.rng.randint(90, 100),
                                "oom_risk": self.rng.choice([True, False]),
                            },
                        ))

                elif self.exhaustion_method == "connection_exhaustion":
                    if self.rng.random() < 0.4:
                        events.append(self._create_event(
                            instance,
                            EventType.NETWORK_TRAFFIC,
                            target,
                            current_time,
                            {
                                "action": "connection_flood",
                                "connections_opened": self.rng.randint(100, 1000),
                                "connection_state": "half_open",
                                "max_connections_reached": True,
                            },
                        ))

                elif self.exhaustion_method == "battery_drain":
                    if self.rng.random() < 0.4:
                        events.append(self._create_event(
                            instance,
                            EventType.DEVICE_STATE_CHANGE,
                            target,
                            current_time,
                            {
                                "action": "battery_drain_attack",
                                "method": self.rng.choice([
                                    "continuous_wake",
                                    "radio_activation",
                                    "sensor_polling",
                                ]),
                                "battery_level_percent": self.rng.randint(5, 30),
                                "drain_rate_increase": f"{self.rng.randint(200, 500)}%",
                            },
                        ))

                elif self.exhaustion_method == "storage_fill":
                    if self.rng.random() < 0.4:
                        events.append(self._create_event(
                            instance,
                            EventType.DEVICE_STATE_CHANGE,
                            target,
                            current_time,
                            {
                                "action": "storage_exhaustion",
                                "method": self.rng.choice([
                                    "log_flooding",
                                    "config_expansion",
                                    "cache_overflow",
                                ]),
                                "storage_used_percent": self.rng.randint(95, 100),
                                "write_failures": self.rng.randint(1, 50),
                            },
                        ))

                # Device degradation
                if self.rng.random() < 0.3:
                    events.append(self._create_event(
                        instance,
                        EventType.DEVICE_STATE_CHANGE,
                        target,
                        current_time,
                        {
                            "action": "device_degradation",
                            "status": self.rng.choice([
                                "unresponsive",
                                "slow_response",
                                "partial_failure",
                                "reboot_required",
                            ]),
                            "service_availability": f"{self.rng.randint(0, 30)}%",
                        },
                    ))

        return events

    def advance_phase(
        self,
        instance: ThreatInstance,
        current_time: datetime,
    ) -> ThreatPhase:
        """Advance resource exhaustion phases."""
        if not instance.phase_start_time:
            return instance.phase

        elapsed = (current_time - instance.phase_start_time).total_seconds() / 60

        if instance.phase == ThreatPhase.RECONNAISSANCE:
            if elapsed > 2:
                return ThreatPhase.INITIAL_ACCESS

        elif instance.phase == ThreatPhase.INITIAL_ACCESS:
            if elapsed > 3:
                return ThreatPhase.EXECUTION

        elif instance.phase == ThreatPhase.EXECUTION:
            if elapsed > instance.planned_duration_minutes:
                return ThreatPhase.COMPLETED

        return instance.phase


class LocationTrackingScenario(ThreatScenario):
    """
    Location Tracking Scenario.

    Tracks occupant location and movement patterns within the
    home through motion sensors, presence detection, and device
    usage patterns.
    """

    def __init__(self, threat_type: ThreatType, home: Home, seed: Optional[int] = None):
        super().__init__(threat_type, home, seed)
        self.tracking_method = self.rng.choice([
            "sensor_correlation",
            "device_usage_inference",
            "wifi_triangulation",
            "presence_monitoring",
        ])
        self.location_samples = 0
        self.rooms_identified = set()

    def select_targets(self) -> list[str]:
        """Select devices that reveal location information."""
        targets = []
        location_types = [
            DeviceType.MOTION_SENSOR,
            DeviceType.MOTION_SENSOR,
            DeviceType.DOOR_SENSOR,
            DeviceType.SMART_SPEAKER,
            DeviceType.SMART_LIGHT,
            DeviceType.SMART_PLUG,
        ]

        for device in self.home.devices:
            if device.device_type in location_types:
                targets.append(device.id)

        return targets

    def generate_phase_events(
        self,
        instance: ThreatInstance,
        current_time: datetime,
    ) -> list[SimulationEvent]:
        """Generate location tracking events."""
        events = []

        if instance.phase == ThreatPhase.RECONNAISSANCE:
            if self.rng.random() < 0.3:
                events.append(self._create_event(
                    instance,
                    EventType.NETWORK_TRAFFIC,
                    "location_scanner",
                    current_time,
                    {
                        "action": "location_aware_device_discovery",
                        "motion_sensors": sum(1 for _ in instance.target_device_ids if "motion" in _.lower()),
                        "presence_devices": len(instance.target_device_ids),
                        "room_mapping_possible": True,
                    },
                ))

        elif instance.phase == ThreatPhase.INITIAL_ACCESS:
            if self.rng.random() < 0.4:
                events.append(self._create_event(
                    instance,
                    EventType.NETWORK_TRAFFIC,
                    "tracker",
                    current_time,
                    {
                        "action": "sensor_data_access",
                        "method": self.rng.choice([
                            "api_polling",
                            "mqtt_subscription",
                            "traffic_sniffing",
                        ]),
                        "success": True,
                    },
                ))

                if not instance.compromised_device_ids:
                    instance.compromised_device_ids = ["tracking_active"]

        elif instance.phase == ThreatPhase.EXECUTION:
            if instance.compromised_device_ids:
                # Collect location data
                if self.rng.random() < 0.5 and instance.target_device_ids:
                    target = self.rng.choice(instance.target_device_ids)
                    room = self.rng.choice([
                        "living_room",
                        "bedroom",
                        "kitchen",
                        "bathroom",
                        "office",
                        "garage",
                    ])
                    self.rooms_identified.add(room)
                    self.location_samples += 1

                    events.append(self._create_event(
                        instance,
                        EventType.DEVICE_DATA_GENERATED,
                        target,
                        current_time,
                        {
                            "action": "location_data_captured",
                            "sensor_id": target,
                            "detected_room": room,
                            "occupancy_status": self.rng.choice([True, False]),
                            "timestamp": current_time.isoformat(),
                            "total_samples": self.location_samples,
                        },
                    ))

                    instance.data_exfiltrated_bytes += self.rng.randint(50, 200)

                # Build movement pattern
                if self.rng.random() < 0.3 and self.location_samples > 5:
                    events.append(self._create_event(
                        instance,
                        EventType.DEVICE_DATA_GENERATED,
                        "pattern_analyzer",
                        current_time,
                        {
                            "action": "movement_pattern_analysis",
                            "rooms_tracked": list(self.rooms_identified),
                            "pattern_type": self.rng.choice([
                                "morning_routine",
                                "evening_activity",
                                "sleep_schedule",
                                "absence_pattern",
                            ]),
                            "confidence": round(self.rng.uniform(0.6, 0.95), 2),
                            "samples_analyzed": self.location_samples,
                        },
                    ))

                # Presence inference
                if self.rng.random() < 0.25:
                    events.append(self._create_event(
                        instance,
                        EventType.DEVICE_DATA_GENERATED,
                        "inference_engine",
                        current_time,
                        {
                            "action": "presence_inference",
                            "home_occupied": self.rng.choice([True, False]),
                            "occupant_count_estimate": self.rng.randint(0, 4),
                            "confidence": round(self.rng.uniform(0.7, 0.9), 2),
                        },
                    ))

        elif instance.phase == ThreatPhase.EXFILTRATION:
            if self.rng.random() < 0.4:
                bytes_sent = self.rng.randint(500, 2000)
                instance.data_exfiltrated_bytes += bytes_sent

                events.append(self._create_event(
                    instance,
                    EventType.NETWORK_TRAFFIC,
                    "exfil",
                    current_time,
                    {
                        "action": "location_data_exfiltration",
                        "bytes_sent": bytes_sent,
                        "data_points": self.location_samples,
                        "rooms_profiled": len(self.rooms_identified),
                        "destination": "tracking_server",
                    },
                ))

        return events

    def advance_phase(
        self,
        instance: ThreatInstance,
        current_time: datetime,
    ) -> ThreatPhase:
        """Advance location tracking phases."""
        if not instance.phase_start_time:
            return instance.phase

        elapsed = (current_time - instance.phase_start_time).total_seconds() / 60

        if instance.phase == ThreatPhase.RECONNAISSANCE:
            if elapsed > 3:
                return ThreatPhase.INITIAL_ACCESS

        elif instance.phase == ThreatPhase.INITIAL_ACCESS:
            if instance.compromised_device_ids and elapsed > 2:
                return ThreatPhase.EXECUTION
            elif elapsed > 10:
                return ThreatPhase.COMPLETED

        elif instance.phase == ThreatPhase.EXECUTION:
            if elapsed > instance.planned_duration_minutes * 0.8:
                return ThreatPhase.EXFILTRATION

        elif instance.phase == ThreatPhase.EXFILTRATION:
            if elapsed > instance.planned_duration_minutes * 0.15:
                return ThreatPhase.COMPLETED

        return instance.phase


class BehaviorProfilingScenario(ThreatScenario):
    """
    Behavior Profiling Scenario.

    Builds detailed profiles of occupant behavior through analysis
    of device usage patterns, schedules, and preferences. Long-term
    passive surveillance threat.
    """

    def __init__(self, threat_type: ThreatType, home: Home, seed: Optional[int] = None):
        super().__init__(threat_type, home, seed)
        self.profiling_categories = []
        self.data_points_collected = 0
        self.profile_completeness = 0.0

    def select_targets(self) -> list[str]:
        """Select devices that reveal behavioral patterns."""
        targets = []
        behavior_types = [
            DeviceType.SMART_TV,
            DeviceType.SMART_SPEAKER,
            DeviceType.SMART_REFRIGERATOR,
            DeviceType.SMART_OVEN,
            DeviceType.SMART_COFFEE_MAKER,
            DeviceType.SMART_LIGHT,
            DeviceType.THERMOSTAT,
            DeviceType.SMART_WASHER,
        ]

        for device in self.home.devices:
            if device.device_type in behavior_types:
                targets.append(device.id)

        return targets

    def generate_phase_events(
        self,
        instance: ThreatInstance,
        current_time: datetime,
    ) -> list[SimulationEvent]:
        """Generate behavior profiling events."""
        events = []

        if instance.phase == ThreatPhase.RECONNAISSANCE:
            if self.rng.random() < 0.25:
                events.append(self._create_event(
                    instance,
                    EventType.NETWORK_TRAFFIC,
                    "behavior_scanner",
                    current_time,
                    {
                        "action": "behavioral_device_discovery",
                        "smart_appliances": len(instance.target_device_ids),
                        "data_sources_identified": [
                            "usage_logs",
                            "schedules",
                            "preferences",
                            "consumption_patterns",
                        ],
                    },
                ))

        elif instance.phase == ThreatPhase.INITIAL_ACCESS:
            if self.rng.random() < 0.35:
                events.append(self._create_event(
                    instance,
                    EventType.NETWORK_TRAFFIC,
                    "profiler",
                    current_time,
                    {
                        "action": "data_collection_setup",
                        "method": self.rng.choice([
                            "cloud_api_access",
                            "local_network_monitoring",
                            "app_data_extraction",
                        ]),
                        "collection_interval_minutes": self.rng.choice([5, 15, 30]),
                    },
                ))

                if not instance.compromised_device_ids:
                    instance.compromised_device_ids = ["profiling_active"]

        elif instance.phase == ThreatPhase.EXECUTION:
            if instance.compromised_device_ids:
                # Collect behavioral data
                if self.rng.random() < 0.4 and instance.target_device_ids:
                    target = self.rng.choice(instance.target_device_ids)

                    behavior_categories = [
                        ("entertainment", ["tv_watching_hours", "content_preferences", "volume_levels"]),
                        ("cooking", ["meal_times", "appliance_usage", "food_preferences"]),
                        ("sleep", ["bedtime", "wake_time", "sleep_duration"]),
                        ("work", ["work_hours", "productivity_patterns", "meeting_times"]),
                        ("energy", ["consumption_patterns", "hvac_preferences", "lighting_habits"]),
                    ]

                    category, data_points = self.rng.choice(behavior_categories)
                    if category not in self.profiling_categories:
                        self.profiling_categories.append(category)

                    self.data_points_collected += len(data_points)
                    self.profile_completeness = min(
                        1.0, self.data_points_collected / 50
                    )

                    events.append(self._create_event(
                        instance,
                        EventType.DEVICE_DATA_GENERATED,
                        target,
                        current_time,
                        {
                            "action": "behavioral_data_collected",
                            "category": category,
                            "data_points": data_points,
                            "sample_value": self.rng.choice([
                                "21:30 daily",
                                "high preference",
                                "72°F setpoint",
                                "3.5 hours avg",
                            ]),
                            "total_data_points": self.data_points_collected,
                        },
                    ))

                    instance.data_exfiltrated_bytes += self.rng.randint(100, 500)

                # Pattern analysis
                if self.rng.random() < 0.25 and self.data_points_collected > 10:
                    events.append(self._create_event(
                        instance,
                        EventType.DEVICE_DATA_GENERATED,
                        "ml_analyzer",
                        current_time,
                        {
                            "action": "pattern_extraction",
                            "patterns_identified": self.rng.randint(1, 5),
                            "categories_analyzed": self.profiling_categories,
                            "profile_completeness": round(self.profile_completeness, 2),
                        },
                    ))

                # Build comprehensive profile
                if self.rng.random() < 0.2 and self.profile_completeness > 0.5:
                    events.append(self._create_event(
                        instance,
                        EventType.DEVICE_DATA_GENERATED,
                        "profile_builder",
                        current_time,
                        {
                            "action": "profile_compilation",
                            "profile_sections": self.profiling_categories,
                            "inference_capabilities": [
                                "predict_absence",
                                "estimate_income",
                                "identify_routines",
                                "assess_security_habits",
                            ],
                            "marketable_value": self.rng.choice([
                                "high",
                                "medium",
                                "very_high",
                            ]),
                        },
                    ))

        elif instance.phase == ThreatPhase.EXFILTRATION:
            if self.rng.random() < 0.4:
                bytes_sent = self.rng.randint(1000, 5000)
                instance.data_exfiltrated_bytes += bytes_sent

                events.append(self._create_event(
                    instance,
                    EventType.NETWORK_TRAFFIC,
                    "exfil",
                    current_time,
                    {
                        "action": "profile_exfiltration",
                        "bytes_sent": bytes_sent,
                        "profile_categories": self.profiling_categories,
                        "data_points_included": self.data_points_collected,
                        "profile_completeness": round(self.profile_completeness, 2),
                    },
                ))

        return events

    def advance_phase(
        self,
        instance: ThreatInstance,
        current_time: datetime,
    ) -> ThreatPhase:
        """Advance behavior profiling phases."""
        if not instance.phase_start_time:
            return instance.phase

        elapsed = (current_time - instance.phase_start_time).total_seconds() / 60

        if instance.phase == ThreatPhase.RECONNAISSANCE:
            if elapsed > 5:
                return ThreatPhase.INITIAL_ACCESS

        elif instance.phase == ThreatPhase.INITIAL_ACCESS:
            if instance.compromised_device_ids and elapsed > 3:
                return ThreatPhase.EXECUTION
            elif elapsed > 15:
                return ThreatPhase.COMPLETED

        elif instance.phase == ThreatPhase.EXECUTION:
            # Behavior profiling is a long-term attack
            if elapsed > instance.planned_duration_minutes * 0.85:
                return ThreatPhase.EXFILTRATION

        elif instance.phase == ThreatPhase.EXFILTRATION:
            if elapsed > instance.planned_duration_minutes * 0.1:
                return ThreatPhase.COMPLETED

        return instance.phase
