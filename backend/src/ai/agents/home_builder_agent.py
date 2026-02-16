"""
Home Builder Agent for the Smart-HES Agent Framework.

Responsible for creating and modifying smart home configurations
based on user requirements and best practices.

Features:
- RAG-enhanced validation against IoT security knowledge base
- Best practices recommendations from research literature
- Security configuration validation
"""

import time
from typing import Any, Optional

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
from src.rag import get_knowledge_base


class HomeBuilderAgent(AbstractAgent):
    """
    Agent responsible for smart home configuration generation.

    Capabilities:
    - Create new smart home configurations
    - Modify existing home layouts
    - Add/remove rooms
    - Generate inhabitant profiles
    - Validate home configurations
    """

    def __init__(
        self,
        agent_id: Optional[str] = None,
        llm_engine: Optional[LLMEngine] = None,
        enable_rag_validation: bool = True,
    ):
        super().__init__(
            agent_id=agent_id,
            name="HomeBuilder",
            description="Creates and manages smart home configurations",
        )

        self.llm_engine = llm_engine or get_llm_engine()
        self.prompt_manager = get_prompt_manager()
        self.enable_rag_validation = enable_rag_validation

        # Initialize knowledge base for RAG-based validation
        if enable_rag_validation:
            self.knowledge_base = get_knowledge_base()
        else:
            self.knowledge_base = None

        # Register tools
        self._register_tools()

        logger.info(
            f"HomeBuilderAgent initialized: {self.agent_id} "
            f"(RAG validation: {'enabled' if enable_rag_validation else 'disabled'})"
        )

    @property
    def agent_type(self) -> str:
        return "home_builder"

    @property
    def capabilities(self) -> list[str]:
        return [
            "create_home",
            "modify_home",
            "add_room",
            "remove_room",
            "add_inhabitant",
            "remove_inhabitant",
            "validate_home",
            "validate_home_with_rag",
            "generate_schedule",
        ]

    def _register_tools(self) -> None:
        """Register available tools for this agent."""
        self.register_tool(
            "validate_room_config",
            self._validate_room_config,
            "Validate room configuration against best practices",
        )
        self.register_tool(
            "suggest_devices",
            self._suggest_devices_for_room,
            "Suggest appropriate devices for a room type",
        )
        self.register_tool(
            "calculate_device_count",
            self._calculate_device_count,
            "Calculate recommended device count for home type",
        )
        self.register_tool(
            "validate_security_config",
            self._validate_security_with_rag,
            "Validate security configuration against RAG knowledge base",
        )

    async def execute_task(self, task: AgentTask) -> AgentResult:
        """Execute a home building task."""
        start_time = time.perf_counter()
        self.set_state(AgentState.EXECUTING)
        self._current_task = task

        try:
            result = None
            if task.task_type == "create_home":
                result = await self._create_home(task.parameters)
            elif task.task_type == "modify_home":
                result = await self._modify_home(task.parameters)
            elif task.task_type == "add_room":
                result = await self._add_room(task.parameters)
            elif task.task_type == "validate_home":
                result = await self._validate_home(task.parameters)
            else:
                # Default: Use LLM to handle the task
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
            logger.error(f"HomeBuilderAgent task failed: {e}")
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
            # Handle request from other agents
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

        elif message.message_type == MessageType.STATUS:
            # Return our status
            return AgentMessage.create(
                sender=self.agent_id,
                receiver=message.sender,
                message_type=MessageType.STATUS,
                content=self.get_status(),
                correlation_id=message.message_id,
            )

        return None

    async def _create_home(self, params: dict) -> dict:
        """Create a new smart home configuration."""
        home_type = params.get("home_type", "two_bedroom")
        requirements = params.get("requirements", "")
        inhabitant_count = params.get("inhabitant_count", 2)

        # Get the agent prompt
        system_prompt = self.prompt_manager.get_agent_prompt("home_builder")

        prompt = f"""Create a smart home configuration with these requirements:
- Home type: {home_type}
- Number of inhabitants: {inhabitant_count}
- Additional requirements: {requirements or "Standard smart home setup"}

Generate a complete home configuration including:
1. All rooms with their types and floors
2. Appropriate devices for each room
3. Inhabitant profiles with schedules

Return as JSON matching the home_config schema."""

        result = await self.llm_engine.generate_json(
            prompt=prompt,
            schema=self.prompt_manager.get_json_schema("home_config"),
            system_prompt=system_prompt,
            use_rag=True,
            rag_query=f"smart home {home_type} device placement best practices",
        )

        # Validate the result
        validated = await self._validate_home({"home_config": result})
        if not validated.get("valid", False):
            logger.warning(f"Generated home has validation issues: {validated.get('issues')}")

        return {
            "home_config": result,
            "validation": validated,
        }

    async def _modify_home(self, params: dict) -> dict:
        """Modify an existing home configuration."""
        current_home = params.get("current_home", {})
        modifications = params.get("modifications", "")

        system_prompt = self.prompt_manager.get_agent_prompt("home_builder")

        prompt = f"""Modify this smart home configuration:

Current configuration:
{current_home}

Requested modifications:
{modifications}

Return the updated configuration as JSON."""

        result = await self.llm_engine.generate_json(
            prompt=prompt,
            schema=self.prompt_manager.get_json_schema("home_config"),
            system_prompt=system_prompt,
        )

        return {"modified_home": result}

    async def _add_room(self, params: dict) -> dict:
        """Add a room to an existing home."""
        current_home = params.get("current_home", {})
        room_type = params.get("room_type", "bedroom")
        room_name = params.get("room_name", f"New {room_type}")
        floor = params.get("floor", 1)

        # Add room to configuration
        new_room = {
            "name": room_name,
            "room_type": room_type,
            "floor": floor,
        }

        # Get suggested devices for the room
        suggested_devices = self._suggest_devices_for_room(room_type)

        return {
            "new_room": new_room,
            "suggested_devices": suggested_devices,
        }

    async def _validate_home(self, params: dict) -> dict:
        """
        Validate a home configuration with optional RAG-based security validation.

        Performs:
        1. Structural validation (required fields, room types, device placement)
        2. Security validation (essential devices, security best practices)
        3. RAG-based validation against knowledge base (if enabled)
        """
        home_config = params.get("home_config", {})
        use_rag = params.get("use_rag", self.enable_rag_validation)
        issues = []
        warnings = []
        recommendations = []

        # =========================================================================
        # 1. Structural Validation
        # =========================================================================
        if not home_config.get("rooms"):
            issues.append("No rooms defined")
        if not home_config.get("devices"):
            issues.append("No devices defined")

        # Validate room types
        valid_room_types = [
            "living_room", "bedroom", "kitchen", "bathroom",
            "garage", "office", "dining_room", "hallway",
            "basement", "attic", "laundry", "entry",
        ]
        for room in home_config.get("rooms", []):
            if room.get("room_type") not in valid_room_types:
                warnings.append(f"Unknown room type: {room.get('room_type')}")

        # Check device placement
        room_names = {r.get("name") for r in home_config.get("rooms", [])}
        for device in home_config.get("devices", []):
            if device.get("room") not in room_names:
                issues.append(f"Device {device.get('device_type')} assigned to non-existent room: {device.get('room')}")

        # =========================================================================
        # 2. Security Validation (Essential Devices)
        # =========================================================================
        device_types = {d.get("device_type") for d in home_config.get("devices", [])}
        essential_devices = {"smoke_detector", "smart_lock"}
        missing_essential = essential_devices - device_types
        if missing_essential:
            warnings.append(f"Missing essential security devices: {missing_essential}")

        # Check for security cameras at entry points
        entry_rooms = [r for r in home_config.get("rooms", []) if r.get("room_type") in ["entry", "garage"]]
        if entry_rooms and "security_camera" not in device_types:
            warnings.append("No security cameras at entry points (entry/garage)")

        # =========================================================================
        # 3. RAG-Based Validation (Best Practices from Knowledge Base)
        # =========================================================================
        rag_validation = None
        if use_rag and self.knowledge_base:
            rag_validation = await self._validate_with_rag(home_config)
            if rag_validation:
                recommendations.extend(rag_validation.get("recommendations", []))
                warnings.extend(rag_validation.get("warnings", []))

        return {
            "valid": len(issues) == 0,
            "issues": issues,
            "warnings": warnings,
            "recommendations": recommendations,
            "device_count": len(home_config.get("devices", [])),
            "room_count": len(home_config.get("rooms", [])),
            "rag_validation": rag_validation,
        }

    async def _validate_with_rag(self, home_config: dict) -> dict:
        """
        Validate home configuration against RAG knowledge base.

        Queries the knowledge base for:
        - IoT security best practices
        - Device placement recommendations
        - Protocol security considerations
        """
        if not self.knowledge_base:
            return None

        recommendations = []
        warnings = []
        rag_sources = []

        # Extract device types and protocols from config
        device_types = [d.get("device_type") for d in home_config.get("devices", [])]
        protocols = set()
        for device in home_config.get("devices", []):
            if device.get("protocol"):
                protocols.add(device.get("protocol"))

        # Query 1: General IoT security best practices
        try:
            security_context = self.knowledge_base.get_rag_context(
                "smart home IoT security best practices device configuration",
                n_results=3,
            )
            if security_context.has_context:
                rag_sources.extend(security_context.sources)

                # Check for network segmentation recommendation
                for ctx in security_context.contexts:
                    if "segmentation" in ctx.lower() or "vlan" in ctx.lower():
                        recommendations.append(
                            "Consider network segmentation (VLAN) for IoT devices to limit lateral movement"
                        )
                        break

                # Check for default credentials warning
                for ctx in security_context.contexts:
                    if "default" in ctx.lower() and ("credential" in ctx.lower() or "password" in ctx.lower()):
                        recommendations.append(
                            "Ensure all devices have unique, strong passwords - avoid default credentials"
                        )
                        break
        except Exception as e:
            logger.warning(f"RAG security query failed: {e}")

        # Query 2: Protocol-specific security
        if protocols:
            protocol_list = ", ".join(protocols)
            try:
                protocol_context = self.knowledge_base.get_rag_context(
                    f"IoT protocol security {protocol_list} vulnerabilities",
                    n_results=2,
                )
                if protocol_context.has_context:
                    rag_sources.extend(protocol_context.sources)

                    # Check for Z-Wave S0 warning
                    if "z-wave" in protocol_list.lower() or "zwave" in protocol_list.lower():
                        for ctx in protocol_context.contexts:
                            if "s0" in ctx.lower() and ("weak" in ctx.lower() or "legacy" in ctx.lower()):
                                warnings.append(
                                    "Z-Wave S0 devices use weak encryption - prefer S2 devices"
                                )
                                break

                    # Check for Zigbee key sharing warning
                    if "zigbee" in protocol_list.lower():
                        for ctx in protocol_context.contexts:
                            if "key" in ctx.lower() and ("network" in ctx.lower() or "sharing" in ctx.lower()):
                                recommendations.append(
                                    "Zigbee network key is shared - compromise of one device may affect all"
                                )
                                break
            except Exception as e:
                logger.warning(f"RAG protocol query failed: {e}")

        # Query 3: Device-specific security (for security-critical devices)
        security_devices = [d for d in device_types if d in ["smart_lock", "security_camera", "alarm_panel"]]
        if security_devices:
            try:
                device_context = self.knowledge_base.get_rag_context(
                    f"smart home {' '.join(security_devices)} security vulnerabilities attacks",
                    n_results=2,
                )
                if device_context.has_context:
                    rag_sources.extend(device_context.sources)

                    # Check for smart lock warnings
                    if "smart_lock" in security_devices:
                        for ctx in device_context.contexts:
                            if "replay" in ctx.lower() or "brute" in ctx.lower():
                                recommendations.append(
                                    "Smart locks should use anti-replay protection and rate limiting"
                                )
                                break

                    # Check for camera warnings
                    if "security_camera" in security_devices:
                        for ctx in device_context.contexts:
                            if "stream" in ctx.lower() or "rtsp" in ctx.lower():
                                recommendations.append(
                                    "Secure camera streams with encryption - avoid unencrypted RTSP"
                                )
                                break
            except Exception as e:
                logger.warning(f"RAG device query failed: {e}")

        # Deduplicate sources
        unique_sources = list(set(rag_sources))

        return {
            "recommendations": recommendations,
            "warnings": warnings,
            "sources": unique_sources,
            "queries_executed": 3,
            "knowledge_base_consulted": True,
        }

    async def _llm_handle_task(self, task: AgentTask) -> dict:
        """Use LLM to handle an unstructured task."""
        system_prompt = self.prompt_manager.get_agent_prompt("home_builder")

        result = await self.llm_engine.generate(
            prompt=task.description,
            system_prompt=system_prompt,
            use_rag=True,
        )

        return {
            "response": result.content,
            "confidence": result.confidence.value,
            "sources": result.sources,
        }

    # Tool implementations
    def _validate_room_config(self, room: dict) -> dict:
        """Validate a room configuration."""
        issues = []

        if not room.get("name"):
            issues.append("Room name is required")
        if not room.get("room_type"):
            issues.append("Room type is required")

        return {"valid": len(issues) == 0, "issues": issues}

    def _validate_security_with_rag(self, home_config: dict) -> dict:
        """
        Synchronous tool wrapper for RAG-based security validation.

        Checks home configuration against IoT security knowledge base.
        """
        if not self.knowledge_base:
            return {
                "validated": False,
                "reason": "Knowledge base not available",
                "recommendations": [],
            }

        # Extract device info for quick validation
        devices = home_config.get("devices", [])
        device_types = [d.get("device_type") for d in devices]

        recommendations = []

        # Check for security-critical devices without encryption
        security_critical = ["smart_lock", "security_camera", "alarm_panel"]
        for device in devices:
            if device.get("device_type") in security_critical:
                if not device.get("encrypted", True):
                    recommendations.append(
                        f"Device '{device.get('name', device.get('device_type'))}' "
                        f"should use encrypted communication"
                    )

        # Check for devices with default credentials flag
        for device in devices:
            if device.get("uses_default_credentials", False):
                recommendations.append(
                    f"Device '{device.get('name', device.get('device_type'))}' "
                    f"is using default credentials - security risk!"
                )

        return {
            "validated": True,
            "device_count": len(devices),
            "security_critical_count": len([d for d in device_types if d in security_critical]),
            "recommendations": recommendations,
        }

    def _suggest_devices_for_room(self, room_type: str) -> list[dict]:
        """Suggest devices appropriate for a room type."""
        device_suggestions = {
            "living_room": [
                {"device_type": "smart_light", "count": 2},
                {"device_type": "smart_tv", "count": 1},
                {"device_type": "smart_speaker", "count": 1},
                {"device_type": "motion_sensor", "count": 1},
                {"device_type": "thermostat", "count": 1},
            ],
            "bedroom": [
                {"device_type": "smart_light", "count": 1},
                {"device_type": "smart_blinds", "count": 1},
                {"device_type": "motion_sensor", "count": 1},
                {"device_type": "smoke_detector", "count": 1},
            ],
            "kitchen": [
                {"device_type": "smart_light", "count": 1},
                {"device_type": "smoke_detector", "count": 1},
                {"device_type": "water_leak_sensor", "count": 1},
                {"device_type": "smart_plug", "count": 2},
            ],
            "bathroom": [
                {"device_type": "smart_light", "count": 1},
                {"device_type": "water_leak_sensor", "count": 1},
                {"device_type": "motion_sensor", "count": 1},
            ],
            "garage": [
                {"device_type": "smart_light", "count": 1},
                {"device_type": "motion_sensor", "count": 1},
                {"device_type": "security_camera", "count": 1},
                {"device_type": "co_detector", "count": 1},
            ],
            "entry": [
                {"device_type": "smart_lock", "count": 1},
                {"device_type": "smart_doorbell", "count": 1},
                {"device_type": "security_camera", "count": 1},
                {"device_type": "motion_sensor", "count": 1},
            ],
            "office": [
                {"device_type": "smart_light", "count": 1},
                {"device_type": "smart_plug", "count": 2},
                {"device_type": "motion_sensor", "count": 1},
            ],
        }

        return device_suggestions.get(room_type, [
            {"device_type": "smart_light", "count": 1},
            {"device_type": "motion_sensor", "count": 1},
        ])

    def _calculate_device_count(self, home_type: str) -> dict:
        """Calculate recommended device counts for a home type."""
        recommendations = {
            "studio": {"min": 5, "max": 10, "typical": 7},
            "one_bedroom": {"min": 8, "max": 15, "typical": 12},
            "two_bedroom": {"min": 12, "max": 25, "typical": 18},
            "family_house": {"min": 20, "max": 40, "typical": 28},
            "smart_mansion": {"min": 40, "max": 80, "typical": 55},
        }

        return recommendations.get(home_type, {"min": 10, "max": 20, "typical": 15})
