"""
Base Device Classes

Abstract base classes for IoT device simulation.
Each device type implements specific behavior and data generation.
"""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Optional
from uuid import uuid4

from loguru import logger

from src.simulation.models import (
    Device,
    DeviceState,
    DeviceStatus,
    EventType,
    SimulationEvent,
)


class DeviceBehavior(ABC):
    """
    Abstract base class for device behavior simulation.

    Each device type implements:
    - update(): Called each simulation tick
    - generate_data(): Generate device-specific telemetry
    - handle_command(): Handle external commands
    """

    def __init__(self, device: Device):
        self.device = device
        self._last_update: Optional[datetime] = None
        self._data_buffer: list[dict[str, Any]] = []

    @property
    def device_id(self) -> str:
        return self.device.id

    @property
    def is_online(self) -> bool:
        return self.device.state.status == DeviceStatus.ONLINE

    @abstractmethod
    def update(self, current_time: datetime, delta_seconds: float) -> list[SimulationEvent]:
        """
        Update device state for the current simulation tick.

        Args:
            current_time: Current simulation time
            delta_seconds: Seconds since last update

        Returns:
            List of events generated during update
        """
        pass

    @abstractmethod
    def generate_data(self, current_time: datetime) -> dict[str, Any]:
        """
        Generate device telemetry data.

        Args:
            current_time: Current simulation time

        Returns:
            Dictionary of telemetry data
        """
        pass

    @abstractmethod
    def handle_command(self, command: str, params: dict[str, Any]) -> bool:
        """
        Handle an external command sent to the device.

        Args:
            command: Command name
            params: Command parameters

        Returns:
            True if command was handled successfully
        """
        pass

    def _create_event(
        self,
        event_type: EventType,
        data: dict[str, Any],
        current_time: datetime,
        is_anomaly: bool = False,
    ) -> SimulationEvent:
        """Helper to create a simulation event."""
        return SimulationEvent(
            event_type=event_type,
            timestamp=current_time,
            source_id=self.device_id,
            source_type="device",
            data={
                "device_type": self.device.device_type,
                "device_name": self.device.name,
                **data,
            },
            is_anomaly=is_anomaly,
        )

    def _update_network_stats(self, tx_bytes: int = 0, rx_bytes: int = 0) -> None:
        """Update network traffic statistics."""
        self.device.state.network_tx_bytes += tx_bytes
        self.device.state.network_rx_bytes += rx_bytes

    def set_status(self, status: DeviceStatus) -> None:
        """Update device status."""
        old_status = self.device.state.status
        self.device.state.status = status
        if old_status != status:
            logger.debug(f"Device {self.device.name} status: {old_status} -> {status}")

    def set_property(self, key: str, value: Any) -> None:
        """Set a device-specific property."""
        self.device.state.properties[key] = value

    def get_property(self, key: str, default: Any = None) -> Any:
        """Get a device-specific property."""
        return self.device.state.properties.get(key, default)


class SensorDevice(DeviceBehavior):
    """Base class for sensor-type devices that primarily report data."""

    def __init__(self, device: Device, report_interval_seconds: int = 60):
        super().__init__(device)
        self.report_interval = report_interval_seconds
        self._last_report: Optional[datetime] = None

    def update(self, current_time: datetime, delta_seconds: float) -> list[SimulationEvent]:
        events = []

        if not self.is_online:
            return events

        # Check if it's time to report
        if self._last_report is None or (
            current_time - self._last_report
        ).total_seconds() >= self.report_interval:
            data = self.generate_data(current_time)
            events.append(
                self._create_event(EventType.DEVICE_DATA_GENERATED, data, current_time)
            )
            self._last_report = current_time
            self._update_network_stats(tx_bytes=len(str(data)))

        self._last_update = current_time
        return events


class ActuatorDevice(DeviceBehavior):
    """Base class for actuator-type devices that perform actions."""

    def __init__(self, device: Device):
        super().__init__(device)
        self._pending_commands: list[tuple[str, dict]] = []

    def queue_command(self, command: str, params: dict[str, Any]) -> None:
        """Queue a command for execution."""
        self._pending_commands.append((command, params))

    def update(self, current_time: datetime, delta_seconds: float) -> list[SimulationEvent]:
        events = []

        if not self.is_online:
            return events

        # Process pending commands
        while self._pending_commands:
            command, params = self._pending_commands.pop(0)
            success = self.handle_command(command, params)
            events.append(
                self._create_event(
                    EventType.DEVICE_STATE_CHANGE,
                    {
                        "command": command,
                        "params": params,
                        "success": success,
                    },
                    current_time,
                )
            )

        self._last_update = current_time
        return events


class HybridDevice(DeviceBehavior):
    """Base class for devices that both sense and actuate."""

    def __init__(self, device: Device, report_interval_seconds: int = 60):
        super().__init__(device)
        self.report_interval = report_interval_seconds
        self._last_report: Optional[datetime] = None
        self._pending_commands: list[tuple[str, dict]] = []

    def queue_command(self, command: str, params: dict[str, Any]) -> None:
        """Queue a command for execution."""
        self._pending_commands.append((command, params))

    def update(self, current_time: datetime, delta_seconds: float) -> list[SimulationEvent]:
        events = []

        if not self.is_online:
            return events

        # Process pending commands
        while self._pending_commands:
            command, params = self._pending_commands.pop(0)
            success = self.handle_command(command, params)
            events.append(
                self._create_event(
                    EventType.DEVICE_STATE_CHANGE,
                    {
                        "command": command,
                        "params": params,
                        "success": success,
                    },
                    current_time,
                )
            )

        # Generate periodic data
        if self._last_report is None or (
            current_time - self._last_report
        ).total_seconds() >= self.report_interval:
            data = self.generate_data(current_time)
            events.append(
                self._create_event(EventType.DEVICE_DATA_GENERATED, data, current_time)
            )
            self._last_report = current_time
            self._update_network_stats(tx_bytes=len(str(data)))

        self._last_update = current_time
        return events
