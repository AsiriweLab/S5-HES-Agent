"""
Threat Injector Agent for the Smart-HES Agent Framework.

Responsible for injecting security threats into simulations
and generating ground truth labels for attack detection research.
"""

import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Optional
from uuid import uuid4

from loguru import logger

from src.ai.agents.base_agent import (
    AbstractAgent,
    AgentMessage,
    AgentResult,
    AgentState,
    AgentTask,
    MessageType,
)
from src.ai.llm import LLMEngine, get_llm_engine
from src.ai.llm.prompts import get_prompt_manager


class ThreatSeverity(str, Enum):
    """Severity levels for threats."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ThreatCategory(str, Enum):
    """Categories of security threats."""
    DATA_EXFILTRATION = "data_exfiltration"
    DEVICE_TAMPERING = "device_tampering"
    ENERGY_THEFT = "energy_theft"
    DDOS_ATTACK = "ddos_attack"
    CAMERA_HIJACK = "camera_hijack"
    MAN_IN_THE_MIDDLE = "man_in_the_middle"
    REPLAY_ATTACK = "replay_attack"
    CREDENTIAL_THEFT = "credential_theft"
    FIRMWARE_MANIPULATION = "firmware_manipulation"
    RANSOMWARE = "ransomware"


@dataclass
class ThreatSignature:
    """Defines the signature of a specific threat type."""
    threat_type: ThreatCategory
    name: str
    description: str
    severity: ThreatSeverity
    target_device_types: list[str]
    attack_indicators: list[str]
    detection_difficulty: str  # easy, medium, hard
    mitre_attack_ids: list[str] = field(default_factory=list)
    typical_duration_minutes: int = 30


# Predefined threat catalog
THREAT_CATALOG: dict[ThreatCategory, ThreatSignature] = {
    ThreatCategory.DATA_EXFILTRATION: ThreatSignature(
        threat_type=ThreatCategory.DATA_EXFILTRATION,
        name="Data Exfiltration",
        description="Unauthorized extraction of sensitive data from IoT devices",
        severity=ThreatSeverity.HIGH,
        target_device_types=["security_camera", "smart_speaker", "smart_tv"],
        attack_indicators=[
            "unusual_outbound_traffic",
            "large_data_transfers",
            "connection_to_unknown_ips",
            "encrypted_traffic_spikes",
        ],
        detection_difficulty="hard",
        mitre_attack_ids=["T1041", "T1048"],
        typical_duration_minutes=60,
    ),
    ThreatCategory.DEVICE_TAMPERING: ThreatSignature(
        threat_type=ThreatCategory.DEVICE_TAMPERING,
        name="Device Tampering",
        description="Physical or logical manipulation of device behavior",
        severity=ThreatSeverity.MEDIUM,
        target_device_types=["smart_lock", "thermostat", "smart_meter"],
        attack_indicators=[
            "unexpected_state_changes",
            "command_injection",
            "configuration_modifications",
            "firmware_changes",
        ],
        detection_difficulty="easy",
        mitre_attack_ids=["T1200"],
        typical_duration_minutes=15,
    ),
    ThreatCategory.ENERGY_THEFT: ThreatSignature(
        threat_type=ThreatCategory.ENERGY_THEFT,
        name="Energy Theft",
        description="Manipulation of smart meter readings to steal electricity",
        severity=ThreatSeverity.MEDIUM,
        target_device_types=["smart_meter", "smart_plug"],
        attack_indicators=[
            "meter_reading_anomalies",
            "consumption_pattern_changes",
            "negative_readings",
            "timestamp_irregularities",
        ],
        detection_difficulty="hard",
        mitre_attack_ids=["T1565"],
        typical_duration_minutes=1440,  # 24 hours - ongoing
    ),
    ThreatCategory.DDOS_ATTACK: ThreatSignature(
        threat_type=ThreatCategory.DDOS_ATTACK,
        name="DDoS Attack",
        description="Denial of service attack overwhelming device resources",
        severity=ThreatSeverity.HIGH,
        target_device_types=["smart_router", "security_camera", "smart_hub"],
        attack_indicators=[
            "traffic_spike",
            "device_unresponsive",
            "connection_timeouts",
            "resource_exhaustion",
        ],
        detection_difficulty="easy",
        mitre_attack_ids=["T1498", "T1499"],
        typical_duration_minutes=30,
    ),
    ThreatCategory.CAMERA_HIJACK: ThreatSignature(
        threat_type=ThreatCategory.CAMERA_HIJACK,
        name="Camera Hijack",
        description="Unauthorized access to security camera feeds",
        severity=ThreatSeverity.HIGH,
        target_device_types=["security_camera", "smart_doorbell"],
        attack_indicators=[
            "unauthorized_stream_access",
            "credential_brute_force",
            "ptz_commands_from_unknown",
            "recording_disabled",
        ],
        detection_difficulty="medium",
        mitre_attack_ids=["T1125"],
        typical_duration_minutes=120,
    ),
    ThreatCategory.MAN_IN_THE_MIDDLE: ThreatSignature(
        threat_type=ThreatCategory.MAN_IN_THE_MIDDLE,
        name="Man-in-the-Middle",
        description="Interception of device communications",
        severity=ThreatSeverity.CRITICAL,
        target_device_types=["*"],  # Any device
        attack_indicators=[
            "certificate_warnings",
            "unexpected_relay_nodes",
            "packet_modification",
            "arp_spoofing",
        ],
        detection_difficulty="medium",
        mitre_attack_ids=["T1557"],
        typical_duration_minutes=60,
    ),
    ThreatCategory.REPLAY_ATTACK: ThreatSignature(
        threat_type=ThreatCategory.REPLAY_ATTACK,
        name="Replay Attack",
        description="Replaying captured commands to control devices",
        severity=ThreatSeverity.MEDIUM,
        target_device_types=["smart_lock", "garage_door", "smart_plug"],
        attack_indicators=[
            "duplicate_commands",
            "stale_timestamps",
            "invalid_nonce",
            "sequence_number_reuse",
        ],
        detection_difficulty="medium",
        mitre_attack_ids=["T1574"],
        typical_duration_minutes=5,
    ),
}


@dataclass
class InjectedThreat:
    """An active threat injection."""
    threat_id: str
    threat_type: ThreatCategory
    target_devices: list[str]
    start_time: datetime
    end_time: datetime
    severity: ThreatSeverity
    attack_phases: list[dict] = field(default_factory=list)
    ground_truth_labels: list[dict] = field(default_factory=list)
    status: str = "pending"  # pending, active, completed, aborted


class ThreatInjectorAgent(AbstractAgent):
    """
    Agent responsible for security threat injection.

    Capabilities:
    - Inject various security threats into simulations
    - Create multi-stage attack scenarios
    - Generate ground truth labels for ML training
    - Simulate attack patterns based on MITRE ATT&CK
    """

    def __init__(
        self,
        agent_id: Optional[str] = None,
        llm_engine: Optional[LLMEngine] = None,
    ):
        super().__init__(
            agent_id=agent_id,
            name="ThreatInjector",
            description="Injects security threats and generates ground truth labels",
        )

        self.llm_engine = llm_engine or get_llm_engine()
        self.prompt_manager = get_prompt_manager()

        # Active threats
        self._active_threats: dict[str, InjectedThreat] = {}
        self._threat_history: list[InjectedThreat] = []

        # Register tools
        self._register_tools()

        logger.info(f"ThreatInjectorAgent initialized: {self.agent_id}")

    @property
    def agent_type(self) -> str:
        return "threat_injector"

    @property
    def capabilities(self) -> list[str]:
        return [
            "inject_threat",
            "abort_threat",
            "create_scenario",
            "get_threat_status",
            "list_threats",
            "generate_ground_truth",
            "get_threat_catalog",
        ]

    def _register_tools(self) -> None:
        """Register available tools."""
        self.register_tool(
            "get_threat_signature",
            self._get_threat_signature,
            "Get signature for a threat type",
        )
        self.register_tool(
            "validate_targets",
            self._validate_targets,
            "Validate target devices for a threat type",
        )
        self.register_tool(
            "calculate_attack_timeline",
            self._calculate_attack_timeline,
            "Calculate attack phase timeline",
        )

    async def execute_task(self, task: AgentTask) -> AgentResult:
        """Execute a threat injection task."""
        start_time = time.perf_counter()
        self.set_state(AgentState.EXECUTING)
        self._current_task = task

        try:
            result = None

            if task.task_type == "inject_threat":
                result = await self._inject_threat(task.parameters)
            elif task.task_type == "abort_threat":
                result = await self._abort_threat(task.parameters)
            elif task.task_type == "create_scenario":
                result = await self._create_scenario(task.parameters)
            elif task.task_type == "get_threat_status":
                result = await self._get_threat_status(task.parameters)
            elif task.task_type == "list_threats":
                result = await self._list_threats(task.parameters)
            elif task.task_type == "generate_ground_truth":
                result = await self._generate_ground_truth(task.parameters)
            elif task.task_type == "get_threat_catalog":
                result = self._get_threat_catalog()
            else:
                result = await self._llm_handle_task(task)

            execution_time = (time.perf_counter() - start_time) * 1000
            self.set_state(AgentState.IDLE)

            agent_result = AgentResult(
                success=True,
                data=result,
                execution_time_ms=execution_time,
            )
            self._record_task_completion(task, agent_result)
            return agent_result

        except Exception as e:
            logger.error(f"ThreatInjectorAgent task failed: {e}")
            execution_time = (time.perf_counter() - start_time) * 1000
            self.set_state(AgentState.ERROR)

            agent_result = AgentResult(
                success=False,
                error=str(e),
                execution_time_ms=execution_time,
            )
            self._record_task_completion(task, agent_result)
            return agent_result

    async def handle_message(self, message: AgentMessage) -> Optional[AgentMessage]:
        """Handle incoming messages."""
        if message.message_type == MessageType.REQUEST:
            action = message.content.get("action")
            params = message.content.get("parameters", {})

            task = AgentTask.create(
                task_type=action,
                description=f"Request from {message.sender}",
                parameters=params,
            )

            result = await self.execute_task(task)

            return AgentMessage.create(
                sender=self.agent_id,
                receiver=message.sender,
                message_type=MessageType.RESPONSE,
                content={
                    "success": result.success,
                    "data": result.data,
                    "error": result.error,
                },
                correlation_id=message.message_id,
            )

        return None

    async def _inject_threat(self, params: dict) -> dict:
        """Inject a security threat into the simulation."""
        threat_type_str = params.get("threat_type")
        target_devices = params.get("target_devices", [])
        duration_minutes = params.get("duration_minutes", 30)
        severity_str = params.get("severity")
        start_delay_seconds = params.get("start_delay_seconds", 0)

        # Parse threat type
        try:
            threat_type = ThreatCategory(threat_type_str)
        except ValueError:
            raise ValueError(f"Unknown threat type: {threat_type_str}")

        # Get threat signature
        signature = THREAT_CATALOG.get(threat_type)
        if not signature:
            raise ValueError(f"No signature found for threat type: {threat_type}")

        # Override severity if provided
        if severity_str:
            severity = ThreatSeverity(severity_str)
        else:
            severity = signature.severity

        # Calculate timing
        start_time = datetime.utcnow() + timedelta(seconds=start_delay_seconds)
        end_time = start_time + timedelta(minutes=duration_minutes)

        # Generate attack phases
        attack_phases = self._generate_attack_phases(signature, duration_minutes)

        # Generate ground truth labels
        ground_truth = self._generate_ground_truth_labels(
            threat_type, target_devices, start_time, end_time, attack_phases
        )

        # Create injected threat
        threat = InjectedThreat(
            threat_id=str(uuid4()),
            threat_type=threat_type,
            target_devices=target_devices,
            start_time=start_time,
            end_time=end_time,
            severity=severity,
            attack_phases=attack_phases,
            ground_truth_labels=ground_truth,
            status="active" if start_delay_seconds == 0 else "pending",
        )

        self._active_threats[threat.threat_id] = threat

        logger.info(
            f"Injected threat: {threat_type.value} targeting {len(target_devices)} devices "
            f"(severity={severity.value}, duration={duration_minutes}min)"
        )

        return {
            "threat_id": threat.threat_id,
            "threat_type": threat_type.value,
            "severity": severity.value,
            "target_devices": target_devices,
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "attack_phases": attack_phases,
            "ground_truth_label_count": len(ground_truth),
        }

    async def _abort_threat(self, params: dict) -> dict:
        """Abort an active threat."""
        threat_id = params.get("threat_id")

        if threat_id not in self._active_threats:
            raise ValueError(f"Threat not found: {threat_id}")

        threat = self._active_threats[threat_id]
        threat.status = "aborted"
        threat.end_time = datetime.utcnow()

        self._threat_history.append(threat)
        del self._active_threats[threat_id]

        return {"threat_id": threat_id, "status": "aborted"}

    async def _create_scenario(self, params: dict) -> dict:
        """Create a complex attack scenario using LLM assistance."""
        scenario_description = params.get("description", "")
        target_home = params.get("target_home", {})
        duration_hours = params.get("duration_hours", 1)

        system_prompt = self.prompt_manager.get_agent_prompt("threat_injector")

        prompt = f"""Create a detailed attack scenario based on this description:

Description: {scenario_description}

Target Home Configuration:
{target_home}

Duration: {duration_hours} hours

Create a multi-stage attack scenario including:
1. Attack phases with timing
2. Target devices for each phase
3. Expected indicators of compromise
4. Severity progression

Return as JSON matching the threat_config schema."""

        result = await self.llm_engine.generate_json(
            prompt=prompt,
            schema=self.prompt_manager.get_json_schema("threat_config"),
            system_prompt=system_prompt,
            use_rag=True,
            rag_query="IoT attack patterns MITRE ATT&CK multi-stage",
        )

        return {"scenario": result}

    async def _get_threat_status(self, params: dict) -> dict:
        """Get status of a specific threat."""
        threat_id = params.get("threat_id")

        if threat_id in self._active_threats:
            threat = self._active_threats[threat_id]
            return {
                "threat_id": threat.threat_id,
                "status": threat.status,
                "threat_type": threat.threat_type.value,
                "target_devices": threat.target_devices,
                "start_time": threat.start_time.isoformat(),
                "end_time": threat.end_time.isoformat(),
                "severity": threat.severity.value,
            }

        # Check history
        for threat in self._threat_history:
            if threat.threat_id == threat_id:
                return {
                    "threat_id": threat.threat_id,
                    "status": threat.status,
                    "threat_type": threat.threat_type.value,
                }

        raise ValueError(f"Threat not found: {threat_id}")

    async def _list_threats(self, params: dict) -> dict:
        """List all threats."""
        include_history = params.get("include_history", False)

        active = [
            {
                "threat_id": t.threat_id,
                "threat_type": t.threat_type.value,
                "status": t.status,
                "severity": t.severity.value,
            }
            for t in self._active_threats.values()
        ]

        result = {"active_threats": active, "active_count": len(active)}

        if include_history:
            history = [
                {
                    "threat_id": t.threat_id,
                    "threat_type": t.threat_type.value,
                    "status": t.status,
                }
                for t in self._threat_history[-20:]  # Last 20
            ]
            result["history"] = history

        return result

    async def _generate_ground_truth(self, params: dict) -> dict:
        """Generate ground truth labels for a threat."""
        threat_id = params.get("threat_id")

        if threat_id not in self._active_threats:
            raise ValueError(f"Threat not found: {threat_id}")

        threat = self._active_threats[threat_id]

        return {
            "threat_id": threat_id,
            "ground_truth_labels": threat.ground_truth_labels,
            "label_count": len(threat.ground_truth_labels),
        }

    def _get_threat_catalog(self) -> dict:
        """Get the full threat catalog."""
        return {
            "threats": [
                {
                    "type": sig.threat_type.value,
                    "name": sig.name,
                    "description": sig.description,
                    "severity": sig.severity.value,
                    "target_devices": sig.target_device_types,
                    "detection_difficulty": sig.detection_difficulty,
                    "mitre_ids": sig.mitre_attack_ids,
                }
                for sig in THREAT_CATALOG.values()
            ],
            "total_threat_types": len(THREAT_CATALOG),
        }

    async def _llm_handle_task(self, task: AgentTask) -> dict:
        """Use LLM for complex threat analysis."""
        system_prompt = self.prompt_manager.get_agent_prompt("threat_injector")

        result = await self.llm_engine.generate(
            prompt=task.description,
            system_prompt=system_prompt,
            use_rag=True,
            rag_query="IoT security threats attack patterns vulnerabilities",
        )

        return {
            "response": result.content,
            "confidence": result.confidence.value,
            "sources": result.sources,
        }

    def _generate_attack_phases(
        self,
        signature: ThreatSignature,
        duration_minutes: int,
    ) -> list[dict]:
        """Generate attack phases based on threat signature."""
        phases = []

        # Standard attack phases
        phase_templates = [
            {"name": "Reconnaissance", "percent": 0.15},
            {"name": "Initial Access", "percent": 0.10},
            {"name": "Execution", "percent": 0.40},
            {"name": "Persistence", "percent": 0.20},
            {"name": "Exfiltration/Impact", "percent": 0.15},
        ]

        current_offset = 0
        for template in phase_templates:
            phase_duration = int(duration_minutes * template["percent"])
            phases.append({
                "phase_name": template["name"],
                "start_offset_minutes": current_offset,
                "duration_minutes": max(1, phase_duration),
                "indicators": signature.attack_indicators[:2],  # Subset of indicators
            })
            current_offset += phase_duration

        return phases

    def _generate_ground_truth_labels(
        self,
        threat_type: ThreatCategory,
        target_devices: list[str],
        start_time: datetime,
        end_time: datetime,
        attack_phases: list[dict],
    ) -> list[dict]:
        """Generate ground truth labels for ML training."""
        labels = []

        # Generate labels for each device at regular intervals
        current_time = start_time
        interval = timedelta(seconds=30)  # Label every 30 seconds

        while current_time < end_time:
            # Determine current phase
            elapsed_minutes = (current_time - start_time).total_seconds() / 60
            current_phase = None
            for phase in attack_phases:
                phase_end = phase["start_offset_minutes"] + phase["duration_minutes"]
                if elapsed_minutes >= phase["start_offset_minutes"] and elapsed_minutes < phase_end:
                    current_phase = phase
                    break

            for device_id in target_devices:
                labels.append({
                    "timestamp": current_time.isoformat(),
                    "device_id": device_id,
                    "threat_type": threat_type.value,
                    "is_attack": True,
                    "attack_phase": current_phase["phase_name"] if current_phase else "unknown",
                    "confidence": 1.0,  # Ground truth is 100% confident
                })

            current_time += interval

        return labels

    # Tool implementations
    def _get_threat_signature(self, threat_type: str) -> dict:
        """Get threat signature."""
        try:
            category = ThreatCategory(threat_type)
            sig = THREAT_CATALOG.get(category)
            if sig:
                return {
                    "name": sig.name,
                    "description": sig.description,
                    "severity": sig.severity.value,
                    "indicators": sig.attack_indicators,
                }
        except ValueError:
            pass
        return {}

    def _validate_targets(self, threat_type: str, target_devices: list[dict]) -> dict:
        """Validate if target devices are appropriate for the threat type."""
        try:
            category = ThreatCategory(threat_type)
            sig = THREAT_CATALOG.get(category)
            if not sig:
                return {"valid": False, "reason": "Unknown threat type"}

            if "*" in sig.target_device_types:
                return {"valid": True, "reason": "All device types valid"}

            invalid_devices = []
            for device in target_devices:
                if device.get("device_type") not in sig.target_device_types:
                    invalid_devices.append(device.get("device_id"))

            if invalid_devices:
                return {
                    "valid": False,
                    "reason": f"Invalid target devices: {invalid_devices}",
                    "valid_types": sig.target_device_types,
                }

            return {"valid": True}

        except ValueError:
            return {"valid": False, "reason": "Unknown threat type"}

    def _calculate_attack_timeline(
        self,
        duration_minutes: int,
        phase_count: int = 5,
    ) -> list[dict]:
        """Calculate attack phase timeline."""
        phase_duration = duration_minutes // phase_count
        phases = []

        for i in range(phase_count):
            phases.append({
                "phase": i + 1,
                "start_minute": i * phase_duration,
                "end_minute": (i + 1) * phase_duration,
            })

        return phases
