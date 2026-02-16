"""
Device Manager Agent for the Smart-HES Agent Framework.

Responsible for managing IoT device operations, states, and telemetry data.
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


# Device type specifications
DEVICE_SPECS = {
    "smart_lock": {
        "states": ["locked", "unlocked", "jammed"],
        "commands": ["lock", "unlock", "check_status"],
        "data_fields": ["battery_level", "lock_state", "last_activity"],
    },
    "security_camera": {
        "states": ["recording", "idle", "offline", "motion_detected"],
        "commands": ["start_recording", "stop_recording", "capture_snapshot"],
        "data_fields": ["is_recording", "motion_detected", "storage_used_gb"],
    },
    "thermostat": {
        "states": ["heating", "cooling", "idle", "fan_only"],
        "commands": ["set_temperature", "set_mode", "set_schedule"],
        "data_fields": ["current_temp", "target_temp", "humidity", "mode"],
    },
    "smart_light": {
        "states": ["on", "off", "dimmed"],
        "commands": ["turn_on", "turn_off", "set_brightness", "set_color"],
        "data_fields": ["is_on", "brightness", "color_temp"],
    },
    "motion_sensor": {
        "states": ["idle", "motion_detected", "offline"],
        "commands": ["enable", "disable", "set_sensitivity"],
        "data_fields": ["motion_detected", "last_motion_time", "battery_level"],
    },
    "smoke_detector": {
        "states": ["normal", "alarm", "test", "offline"],
        "commands": ["test", "silence", "reset"],
        "data_fields": ["alarm_state", "battery_level", "last_test_time"],
    },
    "smart_plug": {
        "states": ["on", "off"],
        "commands": ["turn_on", "turn_off", "toggle"],
        "data_fields": ["is_on", "power_consumption_w", "energy_kwh"],
    },
    "door_sensor": {
        "states": ["open", "closed"],
        "commands": ["check_status"],
        "data_fields": ["is_open", "last_change_time", "battery_level"],
    },
}


class DeviceManagerAgent(AbstractAgent):
    """
    Agent responsible for IoT device management.

    Capabilities:
    - Add/remove devices from simulation
    - Control device states
    - Configure device settings
    - Monitor device health
    - Generate device telemetry
    """

    def __init__(
        self,
        agent_id: Optional[str] = None,
        llm_engine: Optional[LLMEngine] = None,
    ):
        super().__init__(
            agent_id=agent_id,
            name="DeviceManager",
            description="Manages IoT device operations and telemetry",
        )

        self.llm_engine = llm_engine or get_llm_engine()
        self.prompt_manager = get_prompt_manager()

        # In-memory device state tracking
        self._device_states: dict[str, dict] = {}

        # Register tools
        self._register_tools()

        logger.info(f"DeviceManagerAgent initialized: {self.agent_id}")

    @property
    def agent_type(self) -> str:
        return "device_manager"

    @property
    def capabilities(self) -> list[str]:
        return [
            "add_device",
            "remove_device",
            "configure_device",
            "control_device",
            "get_device_status",
            "generate_telemetry",
            "list_devices",
            "validate_device_config",
        ]

    def _register_tools(self) -> None:
        """Register available tools."""
        self.register_tool(
            "get_device_spec",
            self._get_device_spec,
            "Get specification for a device type",
        )
        self.register_tool(
            "validate_command",
            self._validate_command,
            "Validate a device command",
        )
        self.register_tool(
            "get_supported_devices",
            self._get_supported_devices,
            "Get list of supported device types",
        )

    async def execute_task(self, task: AgentTask) -> AgentResult:
        """Execute a device management task."""
        start_time = time.perf_counter()
        self.set_state(AgentState.EXECUTING)
        self._current_task = task

        try:
            result = None

            if task.task_type == "add_device":
                result = await self._add_device(task.parameters)
            elif task.task_type == "remove_device":
                result = await self._remove_device(task.parameters)
            elif task.task_type == "configure_device":
                result = await self._configure_device(task.parameters)
            elif task.task_type == "control_device":
                result = await self._control_device(task.parameters)
            elif task.task_type == "get_device_status":
                result = await self._get_device_status(task.parameters)
            elif task.task_type == "generate_telemetry":
                result = await self._generate_telemetry(task.parameters)
            elif task.task_type == "list_devices":
                result = await self._list_devices(task.parameters)
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
            logger.error(f"DeviceManagerAgent task failed: {e}")
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

    async def _add_device(self, params: dict) -> dict:
        """Add a new device to the simulation."""
        device_id = params.get("device_id")
        device_type = params.get("device_type")
        room = params.get("room")
        config = params.get("config", {})

        # Validate device type
        if device_type not in DEVICE_SPECS:
            raise ValueError(f"Unsupported device type: {device_type}")

        spec = DEVICE_SPECS[device_type]

        # Initialize device state
        device_state = {
            "device_id": device_id,
            "device_type": device_type,
            "room": room,
            "state": spec["states"][0],  # Default to first state
            "config": config,
            "data": {field: None for field in spec["data_fields"]},
            "online": True,
        }

        self._device_states[device_id] = device_state

        logger.info(f"Added device: {device_id} ({device_type}) to {room}")

        return {
            "device_id": device_id,
            "status": "added",
            "initial_state": device_state,
        }

    async def _remove_device(self, params: dict) -> dict:
        """Remove a device from the simulation."""
        device_id = params.get("device_id")

        if device_id not in self._device_states:
            raise ValueError(f"Device not found: {device_id}")

        del self._device_states[device_id]
        logger.info(f"Removed device: {device_id}")

        return {"device_id": device_id, "status": "removed"}

    async def _configure_device(self, params: dict) -> dict:
        """Configure a device."""
        device_id = params.get("device_id")
        config = params.get("config", {})

        if device_id not in self._device_states:
            raise ValueError(f"Device not found: {device_id}")

        self._device_states[device_id]["config"].update(config)

        return {
            "device_id": device_id,
            "status": "configured",
            "config": self._device_states[device_id]["config"],
        }

    async def _control_device(self, params: dict) -> dict:
        """Send a control command to a device."""
        device_id = params.get("device_id")
        command = params.get("command")
        command_params = params.get("params", {})

        if device_id not in self._device_states:
            raise ValueError(f"Device not found: {device_id}")

        device = self._device_states[device_id]
        device_type = device["device_type"]
        spec = DEVICE_SPECS[device_type]

        # Validate command
        if command not in spec["commands"]:
            raise ValueError(f"Invalid command '{command}' for device type '{device_type}'")

        # Simulate command execution
        old_state = device["state"]
        new_state = self._simulate_command(device_type, command, device["state"])
        device["state"] = new_state

        logger.debug(f"Device {device_id}: {command} ({old_state} -> {new_state})")

        return {
            "device_id": device_id,
            "command": command,
            "old_state": old_state,
            "new_state": new_state,
            "success": True,
        }

    async def _get_device_status(self, params: dict) -> dict:
        """Get status of a device."""
        device_id = params.get("device_id")

        if device_id not in self._device_states:
            raise ValueError(f"Device not found: {device_id}")

        return self._device_states[device_id].copy()

    async def _generate_telemetry(self, params: dict) -> dict:
        """Generate telemetry data for devices."""
        device_ids = params.get("device_ids", list(self._device_states.keys()))
        telemetry = []

        import random
        from datetime import datetime

        for device_id in device_ids:
            if device_id not in self._device_states:
                continue

            device = self._device_states[device_id]
            device_type = device["device_type"]

            # Generate mock telemetry based on device type
            data = self._generate_device_data(device_type, device["state"])
            device["data"].update(data)

            telemetry.append({
                "device_id": device_id,
                "device_type": device_type,
                "timestamp": datetime.utcnow().isoformat(),
                "state": device["state"],
                "data": data,
            })

        return {"telemetry": telemetry, "device_count": len(telemetry)}

    async def _list_devices(self, params: dict) -> dict:
        """List all devices."""
        room = params.get("room")
        device_type = params.get("device_type")

        devices = list(self._device_states.values())

        if room:
            devices = [d for d in devices if d["room"] == room]
        if device_type:
            devices = [d for d in devices if d["device_type"] == device_type]

        return {
            "devices": devices,
            "total_count": len(self._device_states),
            "filtered_count": len(devices),
        }

    async def _llm_handle_task(self, task: AgentTask) -> dict:
        """Use LLM for complex device management queries."""
        # Build device types string for context
        device_types_str = "\n".join([
            f"- {dtype}: states={spec['states']}, commands={spec['commands']}"
            for dtype, spec in DEVICE_SPECS.items()
        ])

        system_prompt = self.prompt_manager.get_agent_prompt(
            "device_manager",
            device_types=device_types_str,
        )

        result = await self.llm_engine.generate(
            prompt=task.description,
            system_prompt=system_prompt,
            use_rag=True,
        )

        return {
            "response": result.content,
            "confidence": result.confidence.value,
        }

    def _simulate_command(self, device_type: str, command: str, current_state: str) -> str:
        """Simulate the effect of a command on device state."""
        state_transitions = {
            "smart_lock": {
                "lock": "locked",
                "unlock": "unlocked",
            },
            "smart_light": {
                "turn_on": "on",
                "turn_off": "off",
            },
            "smart_plug": {
                "turn_on": "on",
                "turn_off": "off",
                "toggle": "off" if current_state == "on" else "on",
            },
            "thermostat": {
                "set_mode": current_state,  # Would need mode parameter
            },
            "security_camera": {
                "start_recording": "recording",
                "stop_recording": "idle",
            },
        }

        if device_type in state_transitions and command in state_transitions[device_type]:
            return state_transitions[device_type][command]

        return current_state

    def _generate_device_data(self, device_type: str, state: str) -> dict:
        """Generate mock telemetry data for a device."""
        import random

        data_generators = {
            "smart_lock": lambda: {
                "battery_level": random.randint(50, 100),
                "lock_state": state,
            },
            "thermostat": lambda: {
                "current_temp": round(random.uniform(18, 26), 1),
                "target_temp": 22.0,
                "humidity": random.randint(30, 60),
                "mode": state,
            },
            "smart_light": lambda: {
                "is_on": state == "on",
                "brightness": random.randint(0, 100) if state == "on" else 0,
            },
            "motion_sensor": lambda: {
                "motion_detected": state == "motion_detected",
                "battery_level": random.randint(60, 100),
            },
            "security_camera": lambda: {
                "is_recording": state == "recording",
                "motion_detected": random.random() > 0.8,
                "storage_used_gb": round(random.uniform(10, 100), 1),
            },
            "smart_plug": lambda: {
                "is_on": state == "on",
                "power_consumption_w": round(random.uniform(0, 150), 1) if state == "on" else 0,
            },
        }

        if device_type in data_generators:
            return data_generators[device_type]()

        return {}

    # Tool implementations
    def _get_device_spec(self, device_type: str) -> dict:
        """Get device specification."""
        return DEVICE_SPECS.get(device_type, {})

    def _validate_command(self, device_type: str, command: str) -> dict:
        """Validate if a command is valid for a device type."""
        spec = DEVICE_SPECS.get(device_type)
        if not spec:
            return {"valid": False, "reason": "Unknown device type"}

        if command not in spec["commands"]:
            return {
                "valid": False,
                "reason": f"Invalid command. Valid commands: {spec['commands']}",
            }

        return {"valid": True}

    def _get_supported_devices(self) -> list[str]:
        """Get list of supported device types."""
        return list(DEVICE_SPECS.keys())
