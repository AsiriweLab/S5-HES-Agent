"""
Smart Device Implementations

Concrete implementations for various smart home device types.
Each device generates realistic data and responds to commands.
"""

import math
import random
from datetime import datetime
from typing import Any

from src.simulation.devices.base_device import (
    ActuatorDevice,
    HybridDevice,
    SensorDevice,
)
from src.simulation.models import (
    Device,
    DeviceStatus,
    EventType,
    SimulationEvent,
)


# =============================================================================
# Security Devices
# =============================================================================


class SmartLockBehavior(ActuatorDevice):
    """
    Smart lock device behavior.

    Properties:
    - is_locked: Current lock state
    - lock_method: last method used (keypad, app, auto)
    - failed_attempts: Count of failed unlock attempts
    """

    def __init__(self, device: Device):
        super().__init__(device)
        self.set_property("is_locked", True)
        self.set_property("lock_method", "manual")
        self.set_property("failed_attempts", 0)
        self.set_property("auto_lock_seconds", 30)

    def generate_data(self, current_time: datetime) -> dict[str, Any]:
        return {
            "is_locked": self.get_property("is_locked"),
            "lock_method": self.get_property("lock_method"),
            "failed_attempts": self.get_property("failed_attempts"),
            "battery_level": self.device.state.battery_level,
            "timestamp": current_time.isoformat(),
        }

    def handle_command(self, command: str, params: dict[str, Any]) -> bool:
        if command == "lock":
            self.set_property("is_locked", True)
            self.set_property("lock_method", params.get("method", "app"))
            return True
        elif command == "unlock":
            # Simulate PIN verification
            if params.get("pin") == self.get_property("pin_code", "1234"):
                self.set_property("is_locked", False)
                self.set_property("lock_method", params.get("method", "app"))
                self.set_property("failed_attempts", 0)
                return True
            else:
                failed = self.get_property("failed_attempts", 0)
                self.set_property("failed_attempts", failed + 1)
                return False
        elif command == "set_pin":
            self.set_property("pin_code", params.get("pin", "1234"))
            return True
        return False


class SecurityCameraBehavior(HybridDevice):
    """
    Security camera device behavior.

    Properties:
    - is_recording: Whether actively recording
    - motion_detected: Recent motion detection
    - night_vision: Night vision mode enabled
    - resolution: Video resolution
    """

    def __init__(self, device: Device):
        super().__init__(device, report_interval_seconds=30)
        self.set_property("is_recording", True)
        self.set_property("motion_detected", False)
        self.set_property("night_vision", False)
        self.set_property("resolution", "1080p")
        self.set_property("storage_used_mb", random.randint(1000, 10000))

    def generate_data(self, current_time: datetime) -> dict[str, Any]:
        # Simulate motion detection (10% chance when recording)
        motion = random.random() < 0.1 if self.get_property("is_recording") else False
        self.set_property("motion_detected", motion)

        # Simulate storage growth
        if self.get_property("is_recording"):
            current_storage = self.get_property("storage_used_mb", 0)
            self.set_property("storage_used_mb", current_storage + random.randint(1, 5))

        return {
            "is_recording": self.get_property("is_recording"),
            "motion_detected": motion,
            "night_vision": self.get_property("night_vision"),
            "resolution": self.get_property("resolution"),
            "storage_used_mb": self.get_property("storage_used_mb"),
            "fps": 30 if self.get_property("is_recording") else 0,
            "timestamp": current_time.isoformat(),
        }

    def handle_command(self, command: str, params: dict[str, Any]) -> bool:
        if command == "start_recording":
            self.set_property("is_recording", True)
            return True
        elif command == "stop_recording":
            self.set_property("is_recording", False)
            return True
        elif command == "toggle_night_vision":
            current = self.get_property("night_vision", False)
            self.set_property("night_vision", not current)
            return True
        elif command == "set_resolution":
            self.set_property("resolution", params.get("resolution", "1080p"))
            return True
        return False


class MotionSensorBehavior(SensorDevice):
    """
    Motion sensor device behavior.

    Properties:
    - motion_detected: Current motion state
    - sensitivity: Detection sensitivity (1-10)
    - cooldown_seconds: Time between detections
    """

    def __init__(self, device: Device):
        super().__init__(device, report_interval_seconds=10)
        self.set_property("motion_detected", False)
        self.set_property("sensitivity", 7)
        self.set_property("last_motion_time", None)

    def generate_data(self, current_time: datetime) -> dict[str, Any]:
        # Motion detection based on sensitivity
        sensitivity = self.get_property("sensitivity", 7)
        detection_chance = sensitivity / 100  # Higher sensitivity = more detections

        # Simulate realistic motion patterns (higher during day)
        hour = current_time.hour
        if 8 <= hour <= 22:  # Daytime
            detection_chance *= 2

        motion = random.random() < detection_chance
        self.set_property("motion_detected", motion)
        if motion:
            self.set_property("last_motion_time", current_time.isoformat())

        return {
            "motion_detected": motion,
            "sensitivity": sensitivity,
            "battery_level": self.device.state.battery_level,
            "last_motion_time": self.get_property("last_motion_time"),
            "timestamp": current_time.isoformat(),
        }

    def handle_command(self, command: str, params: dict[str, Any]) -> bool:
        if command == "set_sensitivity":
            sensitivity = max(1, min(10, params.get("sensitivity", 7)))
            self.set_property("sensitivity", sensitivity)
            return True
        return False


class DoorSensorBehavior(SensorDevice):
    """
    Door/window contact sensor behavior.

    Properties:
    - is_open: Door open state
    - open_count: Total open events today
    """

    def __init__(self, device: Device):
        super().__init__(device, report_interval_seconds=5)
        self.set_property("is_open", False)
        self.set_property("open_count", 0)
        self.set_property("last_opened", None)

    def generate_data(self, current_time: datetime) -> dict[str, Any]:
        return {
            "is_open": self.get_property("is_open"),
            "open_count": self.get_property("open_count"),
            "last_opened": self.get_property("last_opened"),
            "battery_level": self.device.state.battery_level,
            "timestamp": current_time.isoformat(),
        }

    def handle_command(self, command: str, params: dict[str, Any]) -> bool:
        # Door sensors typically don't accept commands, but we simulate state changes
        if command == "simulate_open":
            self.set_property("is_open", True)
            self.set_property("last_opened", datetime.utcnow().isoformat())
            self.set_property("open_count", self.get_property("open_count", 0) + 1)
            return True
        elif command == "simulate_close":
            self.set_property("is_open", False)
            return True
        return False


class SmartDoorbellBehavior(HybridDevice):
    """
    Smart doorbell with camera and button.

    Properties:
    - button_pressed: Recent button press
    - motion_detected: Motion at door
    - two_way_audio: Audio enabled
    """

    def __init__(self, device: Device):
        super().__init__(device, report_interval_seconds=30)
        self.set_property("button_pressed", False)
        self.set_property("motion_detected", False)
        self.set_property("two_way_audio", True)
        self.set_property("chime_enabled", True)

    def generate_data(self, current_time: datetime) -> dict[str, Any]:
        # Simulate occasional motion/button press
        motion = random.random() < 0.05
        button = random.random() < 0.01

        self.set_property("motion_detected", motion)
        self.set_property("button_pressed", button)

        return {
            "button_pressed": button,
            "motion_detected": motion,
            "two_way_audio": self.get_property("two_way_audio"),
            "battery_level": self.device.state.battery_level,
            "timestamp": current_time.isoformat(),
        }

    def handle_command(self, command: str, params: dict[str, Any]) -> bool:
        if command == "toggle_audio":
            current = self.get_property("two_way_audio", True)
            self.set_property("two_way_audio", not current)
            return True
        elif command == "toggle_chime":
            current = self.get_property("chime_enabled", True)
            self.set_property("chime_enabled", not current)
            return True
        return False


# =============================================================================
# Environmental Devices
# =============================================================================


class ThermostatBehavior(HybridDevice):
    """
    Smart thermostat with temperature control.

    Uses physics-based temperature simulation.

    Properties:
    - current_temp: Current temperature
    - target_temp: Target temperature
    - mode: heat/cool/auto/off
    - hvac_running: HVAC currently active
    """

    def __init__(self, device: Device):
        super().__init__(device, report_interval_seconds=60)
        self.set_property("current_temp", 21.0)  # Celsius
        self.set_property("target_temp", 22.0)
        self.set_property("mode", "auto")
        self.set_property("hvac_running", False)
        self.set_property("humidity", 45.0)
        self.set_property("fan_mode", "auto")

    def update(self, current_time: datetime, delta_seconds: float) -> list[SimulationEvent]:
        events = super().update(current_time, delta_seconds)

        # Physics-based temperature simulation
        current = self.get_property("current_temp", 21.0)
        target = self.get_property("target_temp", 22.0)
        mode = self.get_property("mode", "auto")

        # Ambient temperature (varies by time of day)
        hour = current_time.hour
        ambient = 15 + 5 * math.sin((hour - 6) * math.pi / 12)  # 10-20°C range

        # Temperature drift toward ambient
        drift_rate = 0.001 * delta_seconds  # Degrees per second
        current += (ambient - current) * drift_rate

        # HVAC effect
        hvac_running = False
        if mode != "off":
            temp_diff = target - current
            if abs(temp_diff) > 0.5:  # Hysteresis
                hvac_running = True
                hvac_power = 0.01 * delta_seconds  # Degrees per second
                if mode == "heat" and temp_diff > 0:
                    current += hvac_power
                elif mode == "cool" and temp_diff < 0:
                    current -= hvac_power
                elif mode == "auto":
                    current += hvac_power if temp_diff > 0 else -hvac_power

        self.set_property("current_temp", round(current, 1))
        self.set_property("hvac_running", hvac_running)

        return events

    def generate_data(self, current_time: datetime) -> dict[str, Any]:
        return {
            "current_temp": self.get_property("current_temp"),
            "target_temp": self.get_property("target_temp"),
            "mode": self.get_property("mode"),
            "hvac_running": self.get_property("hvac_running"),
            "humidity": self.get_property("humidity") + random.uniform(-2, 2),
            "fan_mode": self.get_property("fan_mode"),
            "timestamp": current_time.isoformat(),
        }

    def handle_command(self, command: str, params: dict[str, Any]) -> bool:
        if command == "set_temperature":
            temp = params.get("temperature", 22.0)
            temp = max(10, min(30, temp))  # Clamp to valid range
            self.set_property("target_temp", temp)
            return True
        elif command == "set_mode":
            mode = params.get("mode", "auto")
            if mode in ["heat", "cool", "auto", "off"]:
                self.set_property("mode", mode)
                return True
        elif command == "set_fan":
            fan = params.get("fan_mode", "auto")
            if fan in ["auto", "on", "off"]:
                self.set_property("fan_mode", fan)
                return True
        return False


class SmartLightBehavior(ActuatorDevice):
    """
    Smart light bulb behavior.

    Properties:
    - brightness: 0-100
    - color_temp: Color temperature in Kelvin
    - rgb: RGB color tuple (if supported)
    """

    def __init__(self, device: Device):
        super().__init__(device)
        self.set_property("brightness", 100)
        self.set_property("color_temp", 4000)  # Kelvin
        self.set_property("rgb", (255, 255, 255))
        self.set_property("supports_color", random.random() < 0.5)

    def generate_data(self, current_time: datetime) -> dict[str, Any]:
        return {
            "is_on": self.device.state.is_on,
            "brightness": self.get_property("brightness") if self.device.state.is_on else 0,
            "color_temp": self.get_property("color_temp"),
            "rgb": self.get_property("rgb") if self.get_property("supports_color") else None,
            "timestamp": current_time.isoformat(),
        }

    def handle_command(self, command: str, params: dict[str, Any]) -> bool:
        if command == "turn_on":
            self.device.state.is_on = True
            return True
        elif command == "turn_off":
            self.device.state.is_on = False
            return True
        elif command == "set_brightness":
            brightness = max(0, min(100, params.get("brightness", 100)))
            self.set_property("brightness", brightness)
            return True
        elif command == "set_color_temp":
            temp = max(2700, min(6500, params.get("color_temp", 4000)))
            self.set_property("color_temp", temp)
            return True
        elif command == "set_rgb" and self.get_property("supports_color"):
            rgb = params.get("rgb", (255, 255, 255))
            self.set_property("rgb", tuple(max(0, min(255, c)) for c in rgb))
            return True
        return False


class SmartPlugBehavior(HybridDevice):
    """
    Smart plug with energy monitoring.

    Properties:
    - power_watts: Current power draw
    - energy_kwh: Total energy consumed
    - voltage: Current voltage
    """

    def __init__(self, device: Device):
        super().__init__(device, report_interval_seconds=60)
        self.set_property("power_watts", 0)
        self.set_property("energy_kwh", 0)
        self.set_property("voltage", 120.0)
        self.set_property("current_amps", 0)

    def update(self, current_time: datetime, delta_seconds: float) -> list[SimulationEvent]:
        events = super().update(current_time, delta_seconds)

        # Accumulate energy when on
        if self.device.state.is_on:
            power = self.get_property("power_watts", 0)
            energy = self.get_property("energy_kwh", 0)
            energy += (power * delta_seconds) / 3600000  # Convert W*s to kWh
            self.set_property("energy_kwh", round(energy, 4))

        return events

    def generate_data(self, current_time: datetime) -> dict[str, Any]:
        # Simulate realistic power readings
        base_power = random.uniform(50, 150) if self.device.state.is_on else 0.5
        self.set_property("power_watts", round(base_power, 1))
        self.set_property("current_amps", round(base_power / 120, 2))

        return {
            "is_on": self.device.state.is_on,
            "power_watts": self.get_property("power_watts"),
            "energy_kwh": self.get_property("energy_kwh"),
            "voltage": self.get_property("voltage") + random.uniform(-2, 2),
            "current_amps": self.get_property("current_amps"),
            "timestamp": current_time.isoformat(),
        }

    def handle_command(self, command: str, params: dict[str, Any]) -> bool:
        if command == "turn_on":
            self.device.state.is_on = True
            return True
        elif command == "turn_off":
            self.device.state.is_on = False
            self.set_property("power_watts", 0.5)  # Standby power
            return True
        elif command == "reset_energy":
            self.set_property("energy_kwh", 0)
            return True
        return False


# =============================================================================
# Safety Devices
# =============================================================================


class SmokeDetectorBehavior(SensorDevice):
    """
    Smoke/fire detector behavior.

    Properties:
    - smoke_detected: Smoke alarm triggered
    - smoke_level: Smoke concentration (ppm)
    - test_mode: In test mode
    """

    def __init__(self, device: Device):
        super().__init__(device, report_interval_seconds=300)  # 5 min intervals
        self.set_property("smoke_detected", False)
        self.set_property("smoke_level", 0)
        self.set_property("test_mode", False)
        self.set_property("alarm_active", False)

    def generate_data(self, current_time: datetime) -> dict[str, Any]:
        # Very rare smoke detection (0.01%)
        smoke_level = random.uniform(0, 10)  # Normal background
        if random.random() < 0.0001:
            smoke_level = random.uniform(100, 500)  # Smoke event

        smoke_detected = smoke_level > 50
        self.set_property("smoke_level", round(smoke_level, 1))
        self.set_property("smoke_detected", smoke_detected)
        self.set_property("alarm_active", smoke_detected)

        return {
            "smoke_detected": smoke_detected,
            "smoke_level": self.get_property("smoke_level"),
            "alarm_active": self.get_property("alarm_active"),
            "battery_level": self.device.state.battery_level,
            "test_mode": self.get_property("test_mode"),
            "timestamp": current_time.isoformat(),
        }

    def handle_command(self, command: str, params: dict[str, Any]) -> bool:
        if command == "test":
            self.set_property("test_mode", True)
            self.set_property("alarm_active", True)
            return True
        elif command == "silence":
            self.set_property("alarm_active", False)
            self.set_property("test_mode", False)
            return True
        return False


class WaterLeakSensorBehavior(SensorDevice):
    """
    Water leak detector behavior.

    Properties:
    - leak_detected: Water detected
    - moisture_level: Moisture percentage
    """

    def __init__(self, device: Device):
        super().__init__(device, report_interval_seconds=60)
        self.set_property("leak_detected", False)
        self.set_property("moisture_level", 0)

    def generate_data(self, current_time: datetime) -> dict[str, Any]:
        # Very rare leak (0.01%)
        moisture = random.uniform(0, 5)
        if random.random() < 0.0001:
            moisture = random.uniform(50, 100)

        leak_detected = moisture > 30
        self.set_property("moisture_level", round(moisture, 1))
        self.set_property("leak_detected", leak_detected)

        return {
            "leak_detected": leak_detected,
            "moisture_level": self.get_property("moisture_level"),
            "battery_level": self.device.state.battery_level,
            "timestamp": current_time.isoformat(),
        }

    def handle_command(self, command: str, params: dict[str, Any]) -> bool:
        return False  # No commands for water leak sensor


# =============================================================================
# Entertainment & Other Devices
# =============================================================================


class SmartSpeakerBehavior(HybridDevice):
    """
    Smart speaker behavior.

    Properties:
    - playing: Currently playing audio
    - volume: Volume level (0-100)
    - muted: Microphone muted
    """

    def __init__(self, device: Device):
        super().__init__(device, report_interval_seconds=60)
        self.set_property("playing", False)
        self.set_property("volume", 50)
        self.set_property("muted", False)
        self.set_property("current_media", None)

    def generate_data(self, current_time: datetime) -> dict[str, Any]:
        return {
            "playing": self.get_property("playing"),
            "volume": self.get_property("volume"),
            "muted": self.get_property("muted"),
            "current_media": self.get_property("current_media"),
            "timestamp": current_time.isoformat(),
        }

    def handle_command(self, command: str, params: dict[str, Any]) -> bool:
        if command == "play":
            self.set_property("playing", True)
            self.set_property("current_media", params.get("media", "Unknown"))
            return True
        elif command == "pause":
            self.set_property("playing", False)
            return True
        elif command == "set_volume":
            volume = max(0, min(100, params.get("volume", 50)))
            self.set_property("volume", volume)
            return True
        elif command == "mute":
            self.set_property("muted", True)
            return True
        elif command == "unmute":
            self.set_property("muted", False)
            return True
        return False


class SmartTVBehavior(HybridDevice):
    """
    Smart TV behavior.

    Properties:
    - power_on: TV powered on
    - channel: Current channel/input
    - volume: Volume level
    """

    def __init__(self, device: Device):
        super().__init__(device, report_interval_seconds=60)
        self.set_property("power_on", False)
        self.set_property("channel", "HDMI1")
        self.set_property("volume", 30)
        self.set_property("app", None)

    def generate_data(self, current_time: datetime) -> dict[str, Any]:
        return {
            "power_on": self.get_property("power_on"),
            "channel": self.get_property("channel"),
            "volume": self.get_property("volume"),
            "app": self.get_property("app"),
            "timestamp": current_time.isoformat(),
        }

    def handle_command(self, command: str, params: dict[str, Any]) -> bool:
        if command == "power_on":
            self.set_property("power_on", True)
            self.device.state.is_on = True
            return True
        elif command == "power_off":
            self.set_property("power_on", False)
            self.device.state.is_on = False
            return True
        elif command == "set_channel":
            self.set_property("channel", params.get("channel", "HDMI1"))
            return True
        elif command == "set_volume":
            volume = max(0, min(100, params.get("volume", 30)))
            self.set_property("volume", volume)
            return True
        elif command == "launch_app":
            self.set_property("app", params.get("app"))
            return True
        return False


class SmartBlindsBehavior(ActuatorDevice):
    """
    Smart blinds/shades behavior.

    Properties:
    - position: Blind position (0=closed, 100=open)
    - tilt: Slat tilt angle (-90 to 90)
    """

    def __init__(self, device: Device):
        super().__init__(device)
        self.set_property("position", 50)
        self.set_property("tilt", 0)
        self.set_property("moving", False)

    def generate_data(self, current_time: datetime) -> dict[str, Any]:
        return {
            "position": self.get_property("position"),
            "tilt": self.get_property("tilt"),
            "moving": self.get_property("moving"),
            "timestamp": current_time.isoformat(),
        }

    def handle_command(self, command: str, params: dict[str, Any]) -> bool:
        if command == "set_position":
            position = max(0, min(100, params.get("position", 50)))
            self.set_property("position", position)
            self.set_property("moving", True)
            return True
        elif command == "set_tilt":
            tilt = max(-90, min(90, params.get("tilt", 0)))
            self.set_property("tilt", tilt)
            return True
        elif command == "open":
            self.set_property("position", 100)
            self.set_property("moving", True)
            return True
        elif command == "close":
            self.set_property("position", 0)
            self.set_property("moving", True)
            return True
        return False


class SmartMeterBehavior(SensorDevice):
    """
    Smart energy meter behavior.

    Properties:
    - total_power_watts: Total home power consumption
    - energy_kwh: Total energy consumed
    """

    def __init__(self, device: Device):
        super().__init__(device, report_interval_seconds=60)
        self.set_property("total_power_watts", 500)
        self.set_property("energy_kwh", 0)
        self.set_property("voltage", 120)
        self.set_property("frequency", 60.0)

    def generate_data(self, current_time: datetime) -> dict[str, Any]:
        # Simulate realistic power consumption patterns
        hour = current_time.hour
        base_power = 300  # Always-on loads

        # Time-based patterns
        if 6 <= hour <= 9:  # Morning peak
            base_power += random.uniform(500, 1500)
        elif 17 <= hour <= 21:  # Evening peak
            base_power += random.uniform(800, 2000)
        elif 0 <= hour <= 5:  # Night
            base_power += random.uniform(50, 200)
        else:  # Daytime
            base_power += random.uniform(200, 800)

        self.set_property("total_power_watts", round(base_power, 1))

        return {
            "total_power_watts": self.get_property("total_power_watts"),
            "energy_kwh": self.get_property("energy_kwh"),
            "voltage": self.get_property("voltage") + random.uniform(-2, 2),
            "frequency": self.get_property("frequency") + random.uniform(-0.1, 0.1),
            "timestamp": current_time.isoformat(),
        }

    def handle_command(self, command: str, params: dict[str, Any]) -> bool:
        return False  # Meters don't accept commands


# =============================================================================
# Network & Infrastructure Devices
# =============================================================================


class RouterBehavior(HybridDevice):
    """
    Smart router/gateway behavior.

    Properties:
    - connected_devices: Number of connected devices
    - upload_speed_mbps: Current upload speed
    - download_speed_mbps: Current download speed
    - wifi_clients: WiFi connected clients
    """

    def __init__(self, device: Device):
        super().__init__(device, report_interval_seconds=30)
        self.set_property("connected_devices", random.randint(5, 20))
        self.set_property("upload_speed_mbps", 0)
        self.set_property("download_speed_mbps", 0)
        self.set_property("wifi_clients", random.randint(3, 15))
        self.set_property("wan_status", "connected")
        self.set_property("uptime_seconds", random.randint(86400, 2592000))
        self.set_property("cpu_usage_percent", 15)
        self.set_property("memory_usage_percent", 40)
        self.set_property("wifi_2g_enabled", True)
        self.set_property("wifi_5g_enabled", True)
        self.set_property("guest_network_enabled", False)

    def update(self, current_time: datetime, delta_seconds: float) -> list[SimulationEvent]:
        events = super().update(current_time, delta_seconds)

        # Increment uptime
        uptime = self.get_property("uptime_seconds", 0)
        self.set_property("uptime_seconds", uptime + int(delta_seconds))

        return events

    def generate_data(self, current_time: datetime) -> dict[str, Any]:
        # Simulate network traffic patterns
        hour = current_time.hour

        # Base bandwidth usage varies by time
        if 19 <= hour <= 23:  # Evening streaming peak
            download = random.uniform(50, 200)
            upload = random.uniform(5, 30)
        elif 9 <= hour <= 17:  # Work hours
            download = random.uniform(20, 80)
            upload = random.uniform(10, 40)
        else:  # Off-peak
            download = random.uniform(5, 30)
            upload = random.uniform(1, 10)

        self.set_property("download_speed_mbps", round(download, 1))
        self.set_property("upload_speed_mbps", round(upload, 1))

        # CPU usage correlates with traffic
        cpu = 10 + (download / 200) * 50 + random.uniform(-5, 5)
        self.set_property("cpu_usage_percent", round(min(95, max(5, cpu)), 1))

        # Occasional device count changes
        if random.random() < 0.1:
            devices = self.get_property("connected_devices", 10)
            devices += random.randint(-2, 2)
            self.set_property("connected_devices", max(1, min(50, devices)))

        return {
            "connected_devices": self.get_property("connected_devices"),
            "wifi_clients": self.get_property("wifi_clients"),
            "download_speed_mbps": self.get_property("download_speed_mbps"),
            "upload_speed_mbps": self.get_property("upload_speed_mbps"),
            "wan_status": self.get_property("wan_status"),
            "uptime_seconds": self.get_property("uptime_seconds"),
            "cpu_usage_percent": self.get_property("cpu_usage_percent"),
            "memory_usage_percent": self.get_property("memory_usage_percent"),
            "wifi_2g_enabled": self.get_property("wifi_2g_enabled"),
            "wifi_5g_enabled": self.get_property("wifi_5g_enabled"),
            "timestamp": current_time.isoformat(),
        }

    def handle_command(self, command: str, params: dict[str, Any]) -> bool:
        if command == "reboot":
            self.set_property("uptime_seconds", 0)
            self.set_property("wan_status", "reconnecting")
            return True
        elif command == "toggle_wifi_2g":
            current = self.get_property("wifi_2g_enabled", True)
            self.set_property("wifi_2g_enabled", not current)
            return True
        elif command == "toggle_wifi_5g":
            current = self.get_property("wifi_5g_enabled", True)
            self.set_property("wifi_5g_enabled", not current)
            return True
        elif command == "toggle_guest_network":
            current = self.get_property("guest_network_enabled", False)
            self.set_property("guest_network_enabled", not current)
            return True
        elif command == "block_device":
            # Would block a device by MAC
            return True
        return False


# =============================================================================
# Additional Security Devices
# =============================================================================


class GlassBreakSensorBehavior(SensorDevice):
    """
    Glass break sensor behavior.

    Properties:
    - glass_break_detected: Glass break event detected
    - sensitivity: Detection sensitivity (1-10)
    - sound_level_db: Ambient sound level
    """

    def __init__(self, device: Device):
        super().__init__(device, report_interval_seconds=10)
        self.set_property("glass_break_detected", False)
        self.set_property("sensitivity", 7)
        self.set_property("sound_level_db", 30)
        self.set_property("last_trigger_time", None)

    def generate_data(self, current_time: datetime) -> dict[str, Any]:
        # Very rare glass break detection (0.001%)
        sound_level = random.uniform(25, 45)  # Normal ambient
        glass_break = False

        if random.random() < 0.00001:
            sound_level = random.uniform(90, 120)  # Glass break sound
            glass_break = True
            self.set_property("last_trigger_time", current_time.isoformat())

        self.set_property("sound_level_db", round(sound_level, 1))
        self.set_property("glass_break_detected", glass_break)

        return {
            "glass_break_detected": glass_break,
            "sensitivity": self.get_property("sensitivity"),
            "sound_level_db": self.get_property("sound_level_db"),
            "battery_level": self.device.state.battery_level,
            "last_trigger_time": self.get_property("last_trigger_time"),
            "timestamp": current_time.isoformat(),
        }

    def handle_command(self, command: str, params: dict[str, Any]) -> bool:
        if command == "set_sensitivity":
            sensitivity = max(1, min(10, params.get("sensitivity", 7)))
            self.set_property("sensitivity", sensitivity)
            return True
        elif command == "test":
            self.set_property("glass_break_detected", True)
            self.set_property("last_trigger_time", datetime.utcnow().isoformat())
            return True
        return False


class PanicButtonBehavior(SensorDevice):
    """
    Panic button behavior.

    Properties:
    - pressed: Button currently pressed
    - press_count: Total press count
    """

    def __init__(self, device: Device):
        super().__init__(device, report_interval_seconds=5)
        self.set_property("pressed", False)
        self.set_property("press_count", 0)
        self.set_property("last_press_time", None)
        self.set_property("alert_sent", False)

    def generate_data(self, current_time: datetime) -> dict[str, Any]:
        # Reset pressed state after reporting
        pressed = self.get_property("pressed", False)
        if pressed:
            self.set_property("pressed", False)
            self.set_property("alert_sent", True)

        return {
            "pressed": pressed,
            "press_count": self.get_property("press_count"),
            "last_press_time": self.get_property("last_press_time"),
            "alert_sent": self.get_property("alert_sent"),
            "battery_level": self.device.state.battery_level,
            "timestamp": current_time.isoformat(),
        }

    def handle_command(self, command: str, params: dict[str, Any]) -> bool:
        if command == "press":
            self.set_property("pressed", True)
            self.set_property("press_count", self.get_property("press_count", 0) + 1)
            self.set_property("last_press_time", datetime.utcnow().isoformat())
            self.set_property("alert_sent", False)
            return True
        elif command == "clear_alert":
            self.set_property("alert_sent", False)
            return True
        return False


class SirenAlarmBehavior(ActuatorDevice):
    """
    Siren/alarm behavior.

    Properties:
    - siren_active: Siren currently sounding
    - volume: Volume level (0-100)
    - pattern: Alarm pattern (steady, pulse, escalating)
    """

    def __init__(self, device: Device):
        super().__init__(device)
        self.set_property("siren_active", False)
        self.set_property("volume", 100)
        self.set_property("pattern", "steady")
        self.set_property("strobe_active", False)
        self.set_property("duration_seconds", 0)

    def generate_data(self, current_time: datetime) -> dict[str, Any]:
        return {
            "siren_active": self.get_property("siren_active"),
            "strobe_active": self.get_property("strobe_active"),
            "volume": self.get_property("volume"),
            "pattern": self.get_property("pattern"),
            "duration_seconds": self.get_property("duration_seconds"),
            "timestamp": current_time.isoformat(),
        }

    def handle_command(self, command: str, params: dict[str, Any]) -> bool:
        if command == "activate":
            self.set_property("siren_active", True)
            self.set_property("strobe_active", params.get("strobe", True))
            self.set_property("pattern", params.get("pattern", "steady"))
            return True
        elif command == "deactivate":
            self.set_property("siren_active", False)
            self.set_property("strobe_active", False)
            self.set_property("duration_seconds", 0)
            return True
        elif command == "set_volume":
            volume = max(0, min(100, params.get("volume", 100)))
            self.set_property("volume", volume)
            return True
        elif command == "set_pattern":
            pattern = params.get("pattern", "steady")
            if pattern in ["steady", "pulse", "escalating", "chirp"]:
                self.set_property("pattern", pattern)
                return True
        return False


class SafeLockBehavior(ActuatorDevice):
    """
    Smart safe lock behavior.

    Properties:
    - is_locked: Safe locked state
    - door_open: Safe door open/closed
    - failed_attempts: Failed unlock attempts
    """

    def __init__(self, device: Device):
        super().__init__(device)
        self.set_property("is_locked", True)
        self.set_property("door_open", False)
        self.set_property("failed_attempts", 0)
        self.set_property("last_access_time", None)
        self.set_property("tamper_detected", False)
        self.set_property("lockout_active", False)

    def generate_data(self, current_time: datetime) -> dict[str, Any]:
        return {
            "is_locked": self.get_property("is_locked"),
            "door_open": self.get_property("door_open"),
            "failed_attempts": self.get_property("failed_attempts"),
            "last_access_time": self.get_property("last_access_time"),
            "tamper_detected": self.get_property("tamper_detected"),
            "lockout_active": self.get_property("lockout_active"),
            "battery_level": self.device.state.battery_level,
            "timestamp": current_time.isoformat(),
        }

    def handle_command(self, command: str, params: dict[str, Any]) -> bool:
        if command == "unlock":
            if self.get_property("lockout_active"):
                return False
            # Verify PIN
            if params.get("pin") == self.get_property("pin_code", "0000"):
                self.set_property("is_locked", False)
                self.set_property("failed_attempts", 0)
                self.set_property("last_access_time", datetime.utcnow().isoformat())
                return True
            else:
                failed = self.get_property("failed_attempts", 0) + 1
                self.set_property("failed_attempts", failed)
                if failed >= 5:
                    self.set_property("lockout_active", True)
                return False
        elif command == "lock":
            if not self.get_property("door_open"):
                self.set_property("is_locked", True)
                return True
            return False
        elif command == "set_pin":
            self.set_property("pin_code", params.get("pin", "0000"))
            return True
        elif command == "clear_lockout":
            self.set_property("lockout_active", False)
            self.set_property("failed_attempts", 0)
            return True
        return False


class GarageDoorControllerBehavior(HybridDevice):
    """
    Garage door controller behavior.

    Properties:
    - door_state: open/closed/opening/closing
    - position_percent: Door position (0=closed, 100=open)
    - obstruction_detected: Safety sensor triggered
    """

    def __init__(self, device: Device):
        super().__init__(device, report_interval_seconds=5)
        self.set_property("door_state", "closed")
        self.set_property("position_percent", 0)
        self.set_property("obstruction_detected", False)
        self.set_property("light_on", False)
        self.set_property("auto_close_enabled", True)
        self.set_property("auto_close_seconds", 300)

    def update(self, current_time: datetime, delta_seconds: float) -> list[SimulationEvent]:
        events = super().update(current_time, delta_seconds)

        # Simulate door movement
        state = self.get_property("door_state")
        position = self.get_property("position_percent", 0)

        if state == "opening":
            position += delta_seconds * 10  # 10% per second
            if position >= 100:
                position = 100
                self.set_property("door_state", "open")
            self.set_property("position_percent", position)
        elif state == "closing":
            if self.get_property("obstruction_detected"):
                self.set_property("door_state", "opening")  # Safety reverse
            else:
                position -= delta_seconds * 10
                if position <= 0:
                    position = 0
                    self.set_property("door_state", "closed")
                self.set_property("position_percent", position)

        return events

    def generate_data(self, current_time: datetime) -> dict[str, Any]:
        return {
            "door_state": self.get_property("door_state"),
            "position_percent": self.get_property("position_percent"),
            "obstruction_detected": self.get_property("obstruction_detected"),
            "light_on": self.get_property("light_on"),
            "auto_close_enabled": self.get_property("auto_close_enabled"),
            "timestamp": current_time.isoformat(),
        }

    def handle_command(self, command: str, params: dict[str, Any]) -> bool:
        if command == "open":
            state = self.get_property("door_state")
            if state in ["closed", "closing"]:
                self.set_property("door_state", "opening")
                self.set_property("light_on", True)
                return True
        elif command == "close":
            state = self.get_property("door_state")
            if state in ["open", "opening"]:
                self.set_property("door_state", "closing")
                return True
        elif command == "stop":
            state = self.get_property("door_state")
            if state in ["opening", "closing"]:
                self.set_property("door_state", "stopped")
                return True
        elif command == "toggle":
            state = self.get_property("door_state")
            if state == "closed":
                self.set_property("door_state", "opening")
                self.set_property("light_on", True)
            elif state == "open":
                self.set_property("door_state", "closing")
            return True
        elif command == "toggle_light":
            current = self.get_property("light_on", False)
            self.set_property("light_on", not current)
            return True
        return False


class SecurityKeypadBehavior(HybridDevice):
    """
    Security keypad behavior.

    Properties:
    - armed_state: disarmed/armed_home/armed_away
    - entry_delay_active: Entry delay countdown
    - alarm_triggered: Alarm currently triggered
    """

    def __init__(self, device: Device):
        super().__init__(device, report_interval_seconds=10)
        self.set_property("armed_state", "disarmed")
        self.set_property("entry_delay_active", False)
        self.set_property("entry_delay_seconds", 30)
        self.set_property("exit_delay_seconds", 60)
        self.set_property("alarm_triggered", False)
        self.set_property("chime_enabled", True)
        self.set_property("last_armed_time", None)
        self.set_property("failed_attempts", 0)

    def generate_data(self, current_time: datetime) -> dict[str, Any]:
        return {
            "armed_state": self.get_property("armed_state"),
            "entry_delay_active": self.get_property("entry_delay_active"),
            "alarm_triggered": self.get_property("alarm_triggered"),
            "chime_enabled": self.get_property("chime_enabled"),
            "last_armed_time": self.get_property("last_armed_time"),
            "failed_attempts": self.get_property("failed_attempts"),
            "timestamp": current_time.isoformat(),
        }

    def handle_command(self, command: str, params: dict[str, Any]) -> bool:
        if command == "arm_home":
            if params.get("pin") == self.get_property("pin_code", "1234"):
                self.set_property("armed_state", "armed_home")
                self.set_property("last_armed_time", datetime.utcnow().isoformat())
                self.set_property("failed_attempts", 0)
                return True
            self.set_property("failed_attempts", self.get_property("failed_attempts", 0) + 1)
            return False
        elif command == "arm_away":
            if params.get("pin") == self.get_property("pin_code", "1234"):
                self.set_property("armed_state", "armed_away")
                self.set_property("last_armed_time", datetime.utcnow().isoformat())
                self.set_property("failed_attempts", 0)
                return True
            self.set_property("failed_attempts", self.get_property("failed_attempts", 0) + 1)
            return False
        elif command == "disarm":
            if params.get("pin") == self.get_property("pin_code", "1234"):
                self.set_property("armed_state", "disarmed")
                self.set_property("alarm_triggered", False)
                self.set_property("entry_delay_active", False)
                self.set_property("failed_attempts", 0)
                return True
            self.set_property("failed_attempts", self.get_property("failed_attempts", 0) + 1)
            return False
        elif command == "trigger_alarm":
            if self.get_property("armed_state") != "disarmed":
                self.set_property("alarm_triggered", True)
                return True
        elif command == "set_pin":
            self.set_property("pin_code", params.get("pin", "1234"))
            return True
        elif command == "toggle_chime":
            current = self.get_property("chime_enabled", True)
            self.set_property("chime_enabled", not current)
            return True
        return False


class FloodlightCameraBehavior(HybridDevice):
    """
    Floodlight camera behavior (camera + motion-activated lights).

    Properties:
    - is_recording: Camera recording state
    - motion_detected: Motion triggered
    - light_on: Floodlight state
    - brightness: Light brightness
    """

    def __init__(self, device: Device):
        super().__init__(device, report_interval_seconds=30)
        self.set_property("is_recording", True)
        self.set_property("motion_detected", False)
        self.set_property("light_on", False)
        self.set_property("brightness", 100)
        self.set_property("night_vision", True)
        self.set_property("siren_available", True)
        self.set_property("two_way_audio", True)
        self.set_property("motion_zones_enabled", True)

    def generate_data(self, current_time: datetime) -> dict[str, Any]:
        # Motion detection triggers light
        motion = random.random() < 0.05
        self.set_property("motion_detected", motion)

        # Auto-light on motion at night
        hour = current_time.hour
        is_night = hour < 6 or hour > 20
        if motion and is_night:
            self.set_property("light_on", True)

        return {
            "is_recording": self.get_property("is_recording"),
            "motion_detected": motion,
            "light_on": self.get_property("light_on"),
            "brightness": self.get_property("brightness"),
            "night_vision": self.get_property("night_vision"),
            "is_night": is_night,
            "timestamp": current_time.isoformat(),
        }

    def handle_command(self, command: str, params: dict[str, Any]) -> bool:
        if command == "turn_on_light":
            self.set_property("light_on", True)
            return True
        elif command == "turn_off_light":
            self.set_property("light_on", False)
            return True
        elif command == "set_brightness":
            brightness = max(0, min(100, params.get("brightness", 100)))
            self.set_property("brightness", brightness)
            return True
        elif command == "start_recording":
            self.set_property("is_recording", True)
            return True
        elif command == "stop_recording":
            self.set_property("is_recording", False)
            return True
        elif command == "activate_siren":
            # Would trigger siren
            return True
        elif command == "toggle_night_vision":
            current = self.get_property("night_vision", True)
            self.set_property("night_vision", not current)
            return True
        return False


class PTZCameraBehavior(HybridDevice):
    """
    Pan-Tilt-Zoom camera behavior.

    Properties:
    - pan_angle: Current pan position (-180 to 180)
    - tilt_angle: Current tilt position (-90 to 90)
    - zoom_level: Zoom level (1x to 20x)
    """

    def __init__(self, device: Device):
        super().__init__(device, report_interval_seconds=30)
        self.set_property("is_recording", True)
        self.set_property("pan_angle", 0)
        self.set_property("tilt_angle", 0)
        self.set_property("zoom_level", 1.0)
        self.set_property("tracking_enabled", False)
        self.set_property("motion_detected", False)
        self.set_property("preset_positions", {})
        self.set_property("patrol_enabled", False)

    def generate_data(self, current_time: datetime) -> dict[str, Any]:
        motion = random.random() < 0.08
        self.set_property("motion_detected", motion)

        # Auto-tracking simulation
        if self.get_property("tracking_enabled") and motion:
            pan = self.get_property("pan_angle", 0)
            pan += random.uniform(-10, 10)
            self.set_property("pan_angle", max(-180, min(180, pan)))

        return {
            "is_recording": self.get_property("is_recording"),
            "pan_angle": self.get_property("pan_angle"),
            "tilt_angle": self.get_property("tilt_angle"),
            "zoom_level": self.get_property("zoom_level"),
            "tracking_enabled": self.get_property("tracking_enabled"),
            "motion_detected": motion,
            "patrol_enabled": self.get_property("patrol_enabled"),
            "timestamp": current_time.isoformat(),
        }

    def handle_command(self, command: str, params: dict[str, Any]) -> bool:
        if command == "set_pan":
            pan = max(-180, min(180, params.get("angle", 0)))
            self.set_property("pan_angle", pan)
            return True
        elif command == "set_tilt":
            tilt = max(-90, min(90, params.get("angle", 0)))
            self.set_property("tilt_angle", tilt)
            return True
        elif command == "set_zoom":
            zoom = max(1.0, min(20.0, params.get("level", 1.0)))
            self.set_property("zoom_level", zoom)
            return True
        elif command == "go_to_preset":
            presets = self.get_property("preset_positions", {})
            preset_name = params.get("preset")
            if preset_name in presets:
                pos = presets[preset_name]
                self.set_property("pan_angle", pos.get("pan", 0))
                self.set_property("tilt_angle", pos.get("tilt", 0))
                self.set_property("zoom_level", pos.get("zoom", 1.0))
                return True
        elif command == "save_preset":
            presets = self.get_property("preset_positions", {})
            preset_name = params.get("preset", "default")
            presets[preset_name] = {
                "pan": self.get_property("pan_angle"),
                "tilt": self.get_property("tilt_angle"),
                "zoom": self.get_property("zoom_level"),
            }
            self.set_property("preset_positions", presets)
            return True
        elif command == "toggle_tracking":
            current = self.get_property("tracking_enabled", False)
            self.set_property("tracking_enabled", not current)
            return True
        elif command == "toggle_patrol":
            current = self.get_property("patrol_enabled", False)
            self.set_property("patrol_enabled", not current)
            return True
        elif command == "start_recording":
            self.set_property("is_recording", True)
            return True
        elif command == "stop_recording":
            self.set_property("is_recording", False)
            return True
        return False


class IndoorCameraBehavior(HybridDevice):
    """
    Indoor camera behavior (simpler than outdoor cameras).

    Properties:
    - is_recording: Recording state
    - privacy_mode: Camera disabled for privacy
    - motion_detected: Motion event
    """

    def __init__(self, device: Device):
        super().__init__(device, report_interval_seconds=30)
        self.set_property("is_recording", True)
        self.set_property("privacy_mode", False)
        self.set_property("motion_detected", False)
        self.set_property("sound_detected", False)
        self.set_property("night_vision", True)
        self.set_property("resolution", "1080p")
        self.set_property("two_way_audio", True)

    def generate_data(self, current_time: datetime) -> dict[str, Any]:
        if self.get_property("privacy_mode"):
            return {
                "privacy_mode": True,
                "is_recording": False,
                "timestamp": current_time.isoformat(),
            }

        motion = random.random() < 0.1
        sound = random.random() < 0.05
        self.set_property("motion_detected", motion)
        self.set_property("sound_detected", sound)

        return {
            "is_recording": self.get_property("is_recording"),
            "privacy_mode": False,
            "motion_detected": motion,
            "sound_detected": sound,
            "night_vision": self.get_property("night_vision"),
            "resolution": self.get_property("resolution"),
            "timestamp": current_time.isoformat(),
        }

    def handle_command(self, command: str, params: dict[str, Any]) -> bool:
        if command == "enable_privacy":
            self.set_property("privacy_mode", True)
            self.set_property("is_recording", False)
            return True
        elif command == "disable_privacy":
            self.set_property("privacy_mode", False)
            return True
        elif command == "start_recording":
            if not self.get_property("privacy_mode"):
                self.set_property("is_recording", True)
                return True
        elif command == "stop_recording":
            self.set_property("is_recording", False)
            return True
        elif command == "set_resolution":
            res = params.get("resolution", "1080p")
            if res in ["720p", "1080p", "2K", "4K"]:
                self.set_property("resolution", res)
                return True
        elif command == "toggle_night_vision":
            current = self.get_property("night_vision", True)
            self.set_property("night_vision", not current)
            return True
        return False


class DrivewaySensorBehavior(SensorDevice):
    """
    Driveway/vehicle detection sensor behavior.

    Properties:
    - vehicle_detected: Vehicle in driveway
    - detection_count: Daily detection count
    """

    def __init__(self, device: Device):
        super().__init__(device, report_interval_seconds=10)
        self.set_property("vehicle_detected", False)
        self.set_property("detection_count", 0)
        self.set_property("last_detection_time", None)
        self.set_property("sensitivity", 7)

    def generate_data(self, current_time: datetime) -> dict[str, Any]:
        # Simulate occasional vehicle detection
        hour = current_time.hour

        # Higher probability during commute times
        if 7 <= hour <= 9 or 17 <= hour <= 19:
            detection_chance = 0.02
        else:
            detection_chance = 0.005

        vehicle = random.random() < detection_chance
        if vehicle and not self.get_property("vehicle_detected"):
            self.set_property("detection_count", self.get_property("detection_count", 0) + 1)
            self.set_property("last_detection_time", current_time.isoformat())

        self.set_property("vehicle_detected", vehicle)

        return {
            "vehicle_detected": vehicle,
            "detection_count": self.get_property("detection_count"),
            "last_detection_time": self.get_property("last_detection_time"),
            "sensitivity": self.get_property("sensitivity"),
            "battery_level": self.device.state.battery_level,
            "timestamp": current_time.isoformat(),
        }

    def handle_command(self, command: str, params: dict[str, Any]) -> bool:
        if command == "set_sensitivity":
            sensitivity = max(1, min(10, params.get("sensitivity", 7)))
            self.set_property("sensitivity", sensitivity)
            return True
        elif command == "reset_count":
            self.set_property("detection_count", 0)
            return True
        return False


# =============================================================================
# Lighting Devices
# =============================================================================


class SmartBulbColorBehavior(ActuatorDevice):
    """
    Color-capable smart bulb behavior.

    Properties:
    - brightness: 0-100
    - color_temp: Color temperature in Kelvin
    - rgb: RGB color tuple
    - hue: Hue value (0-360)
    - saturation: Saturation (0-100)
    """

    def __init__(self, device: Device):
        super().__init__(device)
        self.set_property("brightness", 100)
        self.set_property("color_temp", 4000)
        self.set_property("rgb", (255, 255, 255))
        self.set_property("hue", 0)
        self.set_property("saturation", 0)
        self.set_property("effect", "none")  # none, rainbow, candle, pulse

    def generate_data(self, current_time: datetime) -> dict[str, Any]:
        return {
            "is_on": self.device.state.is_on,
            "brightness": self.get_property("brightness") if self.device.state.is_on else 0,
            "color_temp": self.get_property("color_temp"),
            "rgb": self.get_property("rgb"),
            "hue": self.get_property("hue"),
            "saturation": self.get_property("saturation"),
            "effect": self.get_property("effect"),
            "timestamp": current_time.isoformat(),
        }

    def handle_command(self, command: str, params: dict[str, Any]) -> bool:
        if command == "turn_on":
            self.device.state.is_on = True
            return True
        elif command == "turn_off":
            self.device.state.is_on = False
            return True
        elif command == "set_brightness":
            brightness = max(0, min(100, params.get("brightness", 100)))
            self.set_property("brightness", brightness)
            return True
        elif command == "set_color_temp":
            temp = max(2000, min(6500, params.get("color_temp", 4000)))
            self.set_property("color_temp", temp)
            return True
        elif command == "set_rgb":
            rgb = params.get("rgb", (255, 255, 255))
            self.set_property("rgb", tuple(max(0, min(255, c)) for c in rgb))
            return True
        elif command == "set_hue":
            hue = max(0, min(360, params.get("hue", 0)))
            self.set_property("hue", hue)
            return True
        elif command == "set_saturation":
            sat = max(0, min(100, params.get("saturation", 100)))
            self.set_property("saturation", sat)
            return True
        elif command == "set_effect":
            effect = params.get("effect", "none")
            if effect in ["none", "rainbow", "candle", "pulse", "strobe"]:
                self.set_property("effect", effect)
                return True
        return False


class SmartBulbWhiteBehavior(ActuatorDevice):
    """
    White-only smart bulb behavior (tunable white).

    Properties:
    - brightness: 0-100
    - color_temp: Color temperature in Kelvin (2700-6500)
    """

    def __init__(self, device: Device):
        super().__init__(device)
        self.set_property("brightness", 100)
        self.set_property("color_temp", 4000)

    def generate_data(self, current_time: datetime) -> dict[str, Any]:
        return {
            "is_on": self.device.state.is_on,
            "brightness": self.get_property("brightness") if self.device.state.is_on else 0,
            "color_temp": self.get_property("color_temp"),
            "timestamp": current_time.isoformat(),
        }

    def handle_command(self, command: str, params: dict[str, Any]) -> bool:
        if command == "turn_on":
            self.device.state.is_on = True
            return True
        elif command == "turn_off":
            self.device.state.is_on = False
            return True
        elif command == "set_brightness":
            brightness = max(0, min(100, params.get("brightness", 100)))
            self.set_property("brightness", brightness)
            return True
        elif command == "set_color_temp":
            temp = max(2700, min(6500, params.get("color_temp", 4000)))
            self.set_property("color_temp", temp)
            return True
        return False


class LightStripBehavior(ActuatorDevice):
    """
    LED light strip behavior with segment control.

    Properties:
    - brightness: Overall brightness
    - segments: Individual segment colors
    - effect: Current effect mode
    """

    def __init__(self, device: Device):
        super().__init__(device)
        self.set_property("brightness", 100)
        self.set_property("segment_count", 10)
        self.set_property("segments", [(255, 255, 255)] * 10)
        self.set_property("effect", "none")
        self.set_property("sync_to_music", False)

    def generate_data(self, current_time: datetime) -> dict[str, Any]:
        return {
            "is_on": self.device.state.is_on,
            "brightness": self.get_property("brightness") if self.device.state.is_on else 0,
            "segment_count": self.get_property("segment_count"),
            "effect": self.get_property("effect"),
            "sync_to_music": self.get_property("sync_to_music"),
            "timestamp": current_time.isoformat(),
        }

    def handle_command(self, command: str, params: dict[str, Any]) -> bool:
        if command == "turn_on":
            self.device.state.is_on = True
            return True
        elif command == "turn_off":
            self.device.state.is_on = False
            return True
        elif command == "set_brightness":
            brightness = max(0, min(100, params.get("brightness", 100)))
            self.set_property("brightness", brightness)
            return True
        elif command == "set_segment_color":
            segment_idx = params.get("segment", 0)
            color = params.get("color", (255, 255, 255))
            segments = list(self.get_property("segments", []))
            if 0 <= segment_idx < len(segments):
                segments[segment_idx] = tuple(color)
                self.set_property("segments", segments)
                return True
        elif command == "set_all_segments":
            color = params.get("color", (255, 255, 255))
            count = self.get_property("segment_count", 10)
            self.set_property("segments", [tuple(color)] * count)
            return True
        elif command == "set_effect":
            effect = params.get("effect", "none")
            if effect in ["none", "rainbow", "chase", "breathe", "wave", "fire"]:
                self.set_property("effect", effect)
                return True
        elif command == "toggle_music_sync":
            current = self.get_property("sync_to_music", False)
            self.set_property("sync_to_music", not current)
            return True
        return False


class SmartSwitchBehavior(ActuatorDevice):
    """
    Smart wall switch behavior.

    Properties:
    - switch_state: On/off state
    - load_watts: Connected load power
    """

    def __init__(self, device: Device):
        super().__init__(device)
        self.set_property("switch_state", False)
        self.set_property("load_watts", 0)
        self.set_property("schedule_enabled", False)

    def generate_data(self, current_time: datetime) -> dict[str, Any]:
        # Simulate load when on
        load = random.uniform(40, 200) if self.get_property("switch_state") else 0
        self.set_property("load_watts", round(load, 1))

        return {
            "switch_state": self.get_property("switch_state"),
            "load_watts": self.get_property("load_watts"),
            "schedule_enabled": self.get_property("schedule_enabled"),
            "timestamp": current_time.isoformat(),
        }

    def handle_command(self, command: str, params: dict[str, Any]) -> bool:
        if command == "turn_on":
            self.set_property("switch_state", True)
            self.device.state.is_on = True
            return True
        elif command == "turn_off":
            self.set_property("switch_state", False)
            self.device.state.is_on = False
            return True
        elif command == "toggle":
            current = self.get_property("switch_state", False)
            self.set_property("switch_state", not current)
            self.device.state.is_on = not current
            return True
        elif command == "toggle_schedule":
            current = self.get_property("schedule_enabled", False)
            self.set_property("schedule_enabled", not current)
            return True
        return False


class SmartDimmerBehavior(ActuatorDevice):
    """
    Smart dimmer switch behavior.

    Properties:
    - brightness: Dimmer level (0-100)
    - fade_rate: Fade speed
    """

    def __init__(self, device: Device):
        super().__init__(device)
        self.set_property("brightness", 0)
        self.set_property("fade_rate", 1.0)  # Seconds to full brightness
        self.set_property("minimum_level", 10)
        self.set_property("maximum_level", 100)

    def generate_data(self, current_time: datetime) -> dict[str, Any]:
        return {
            "is_on": self.device.state.is_on,
            "brightness": self.get_property("brightness"),
            "fade_rate": self.get_property("fade_rate"),
            "minimum_level": self.get_property("minimum_level"),
            "maximum_level": self.get_property("maximum_level"),
            "timestamp": current_time.isoformat(),
        }

    def handle_command(self, command: str, params: dict[str, Any]) -> bool:
        if command == "turn_on":
            self.device.state.is_on = True
            self.set_property("brightness", self.get_property("maximum_level", 100))
            return True
        elif command == "turn_off":
            self.device.state.is_on = False
            self.set_property("brightness", 0)
            return True
        elif command == "set_brightness":
            min_level = self.get_property("minimum_level", 0)
            max_level = self.get_property("maximum_level", 100)
            brightness = max(min_level, min(max_level, params.get("brightness", 100)))
            self.set_property("brightness", brightness)
            self.device.state.is_on = brightness > 0
            return True
        elif command == "set_fade_rate":
            rate = max(0.1, min(10.0, params.get("fade_rate", 1.0)))
            self.set_property("fade_rate", rate)
            return True
        elif command == "set_limits":
            min_level = max(0, min(50, params.get("minimum", 10)))
            max_level = max(50, min(100, params.get("maximum", 100)))
            self.set_property("minimum_level", min_level)
            self.set_property("maximum_level", max_level)
            return True
        return False


class SmartCurtainsBehavior(ActuatorDevice):
    """
    Smart curtains/drapes behavior.

    Properties:
    - position: Curtain position (0=closed, 100=open)
    - moving: Currently moving
    """

    def __init__(self, device: Device):
        super().__init__(device)
        self.set_property("position", 50)
        self.set_property("moving", False)
        self.set_property("target_position", 50)
        self.set_property("auto_close_time", None)

    def update(self, current_time: datetime, delta_seconds: float) -> list[SimulationEvent]:
        events = super().update(current_time, delta_seconds)

        # Simulate movement
        current = self.get_property("position", 50)
        target = self.get_property("target_position", 50)

        if current != target:
            self.set_property("moving", True)
            speed = 5 * delta_seconds  # 5% per second
            if current < target:
                current = min(target, current + speed)
            else:
                current = max(target, current - speed)
            self.set_property("position", round(current, 1))

            if current == target:
                self.set_property("moving", False)

        return events

    def generate_data(self, current_time: datetime) -> dict[str, Any]:
        return {
            "position": self.get_property("position"),
            "moving": self.get_property("moving"),
            "target_position": self.get_property("target_position"),
            "timestamp": current_time.isoformat(),
        }

    def handle_command(self, command: str, params: dict[str, Any]) -> bool:
        if command == "set_position":
            position = max(0, min(100, params.get("position", 50)))
            self.set_property("target_position", position)
            return True
        elif command == "open":
            self.set_property("target_position", 100)
            return True
        elif command == "close":
            self.set_property("target_position", 0)
            return True
        elif command == "stop":
            current = self.get_property("position", 50)
            self.set_property("target_position", current)
            self.set_property("moving", False)
            return True
        return False


class CeilingFanLightBehavior(HybridDevice):
    """
    Ceiling fan with integrated light behavior.

    Properties:
    - fan_speed: Fan speed (0=off, 1-6)
    - light_on: Light state
    - light_brightness: Light brightness
    - reverse: Fan direction reversed
    """

    def __init__(self, device: Device):
        super().__init__(device, report_interval_seconds=30)
        self.set_property("fan_speed", 0)
        self.set_property("light_on", False)
        self.set_property("light_brightness", 100)
        self.set_property("reverse", False)
        self.set_property("breeze_mode", False)

    def generate_data(self, current_time: datetime) -> dict[str, Any]:
        return {
            "fan_speed": self.get_property("fan_speed"),
            "light_on": self.get_property("light_on"),
            "light_brightness": self.get_property("light_brightness"),
            "reverse": self.get_property("reverse"),
            "breeze_mode": self.get_property("breeze_mode"),
            "timestamp": current_time.isoformat(),
        }

    def handle_command(self, command: str, params: dict[str, Any]) -> bool:
        if command == "set_fan_speed":
            speed = max(0, min(6, params.get("speed", 0)))
            self.set_property("fan_speed", speed)
            return True
        elif command == "fan_off":
            self.set_property("fan_speed", 0)
            return True
        elif command == "toggle_light":
            current = self.get_property("light_on", False)
            self.set_property("light_on", not current)
            return True
        elif command == "set_light_brightness":
            brightness = max(0, min(100, params.get("brightness", 100)))
            self.set_property("light_brightness", brightness)
            return True
        elif command == "toggle_reverse":
            current = self.get_property("reverse", False)
            self.set_property("reverse", not current)
            return True
        elif command == "toggle_breeze":
            current = self.get_property("breeze_mode", False)
            self.set_property("breeze_mode", not current)
            return True
        return False


# =============================================================================
# Climate Devices
# =============================================================================


class TemperatureSensorBehavior(SensorDevice):
    """
    Temperature sensor behavior.

    Properties:
    - temperature: Current temperature reading
    - humidity: Optional humidity reading
    """

    def __init__(self, device: Device):
        super().__init__(device, report_interval_seconds=60)
        self.set_property("temperature", 21.0)
        self.set_property("humidity", 45.0)
        self.set_property("temperature_unit", "celsius")

    def generate_data(self, current_time: datetime) -> dict[str, Any]:
        # Simulate temperature variation
        hour = current_time.hour
        base_temp = 20 + 3 * math.sin((hour - 6) * math.pi / 12)
        temp = base_temp + random.uniform(-0.5, 0.5)
        humidity = 45 + random.uniform(-5, 5)

        self.set_property("temperature", round(temp, 1))
        self.set_property("humidity", round(humidity, 1))

        return {
            "temperature": self.get_property("temperature"),
            "humidity": self.get_property("humidity"),
            "temperature_unit": self.get_property("temperature_unit"),
            "battery_level": self.device.state.battery_level,
            "timestamp": current_time.isoformat(),
        }

    def handle_command(self, command: str, params: dict[str, Any]) -> bool:
        if command == "set_unit":
            unit = params.get("unit", "celsius")
            if unit in ["celsius", "fahrenheit"]:
                self.set_property("temperature_unit", unit)
                return True
        return False


class HumiditySensorBehavior(SensorDevice):
    """
    Humidity sensor behavior.

    Properties:
    - humidity: Relative humidity percentage
    - temperature: Optional temperature
    """

    def __init__(self, device: Device):
        super().__init__(device, report_interval_seconds=60)
        self.set_property("humidity", 45.0)
        self.set_property("temperature", 21.0)
        self.set_property("dew_point", 10.0)

    def generate_data(self, current_time: datetime) -> dict[str, Any]:
        # Simulate humidity variation
        hour = current_time.hour
        base_humidity = 45 + 10 * math.sin((hour - 12) * math.pi / 12)
        humidity = base_humidity + random.uniform(-3, 3)
        temp = 21 + random.uniform(-1, 1)

        # Calculate dew point approximation
        dew_point = temp - ((100 - humidity) / 5)

        self.set_property("humidity", round(max(20, min(90, humidity)), 1))
        self.set_property("temperature", round(temp, 1))
        self.set_property("dew_point", round(dew_point, 1))

        return {
            "humidity": self.get_property("humidity"),
            "temperature": self.get_property("temperature"),
            "dew_point": self.get_property("dew_point"),
            "battery_level": self.device.state.battery_level,
            "timestamp": current_time.isoformat(),
        }

    def handle_command(self, command: str, params: dict[str, Any]) -> bool:
        return False  # Sensors don't accept commands


class AirQualityMonitorBehavior(SensorDevice):
    """
    Air quality monitor behavior.

    Properties:
    - aqi: Air Quality Index (0-500)
    - pm25: PM2.5 (µg/m³)
    - pm10: PM10 (µg/m³)
    - co2: CO2 (ppm)
    - voc: VOC level
    """

    def __init__(self, device: Device):
        super().__init__(device, report_interval_seconds=300)
        self.set_property("aqi", 50)
        self.set_property("pm25", 12.0)
        self.set_property("pm10", 20.0)
        self.set_property("co2", 450)
        self.set_property("voc", 0.1)
        self.set_property("temperature", 21.0)
        self.set_property("humidity", 45.0)

    def generate_data(self, current_time: datetime) -> dict[str, Any]:
        hour = current_time.hour

        # Indoor air quality varies with activity
        if 7 <= hour <= 9 or 18 <= hour <= 21:  # Cooking times
            pm25 = random.uniform(15, 35)
            co2 = random.uniform(500, 800)
        else:
            pm25 = random.uniform(5, 20)
            co2 = random.uniform(400, 600)

        pm10 = pm25 * random.uniform(1.3, 1.8)
        voc = random.uniform(0.05, 0.3)

        # Calculate AQI from PM2.5 (simplified)
        if pm25 <= 12:
            aqi = pm25 * 4.17
        elif pm25 <= 35.4:
            aqi = 50 + (pm25 - 12) * 2.1
        else:
            aqi = 100 + (pm25 - 35.4) * 2.5

        self.set_property("aqi", round(min(500, aqi)))
        self.set_property("pm25", round(pm25, 1))
        self.set_property("pm10", round(pm10, 1))
        self.set_property("co2", round(co2))
        self.set_property("voc", round(voc, 2))

        return {
            "aqi": self.get_property("aqi"),
            "pm25": self.get_property("pm25"),
            "pm10": self.get_property("pm10"),
            "co2": self.get_property("co2"),
            "voc": self.get_property("voc"),
            "temperature": self.get_property("temperature") + random.uniform(-0.5, 0.5),
            "humidity": self.get_property("humidity") + random.uniform(-2, 2),
            "timestamp": current_time.isoformat(),
        }

    def handle_command(self, command: str, params: dict[str, Any]) -> bool:
        return False  # Sensors don't accept commands


class SmartFanBehavior(ActuatorDevice):
    """
    Smart fan behavior.

    Properties:
    - speed: Fan speed (0-10)
    - oscillating: Oscillation enabled
    - timer_minutes: Auto-off timer
    """

    def __init__(self, device: Device):
        super().__init__(device)
        self.set_property("speed", 0)
        self.set_property("oscillating", False)
        self.set_property("timer_minutes", 0)
        self.set_property("mode", "normal")  # normal, natural, sleep

    def generate_data(self, current_time: datetime) -> dict[str, Any]:
        return {
            "is_on": self.device.state.is_on,
            "speed": self.get_property("speed"),
            "oscillating": self.get_property("oscillating"),
            "timer_minutes": self.get_property("timer_minutes"),
            "mode": self.get_property("mode"),
            "timestamp": current_time.isoformat(),
        }

    def handle_command(self, command: str, params: dict[str, Any]) -> bool:
        if command == "turn_on":
            self.device.state.is_on = True
            if self.get_property("speed") == 0:
                self.set_property("speed", 5)
            return True
        elif command == "turn_off":
            self.device.state.is_on = False
            self.set_property("speed", 0)
            return True
        elif command == "set_speed":
            speed = max(0, min(10, params.get("speed", 5)))
            self.set_property("speed", speed)
            self.device.state.is_on = speed > 0
            return True
        elif command == "toggle_oscillate":
            current = self.get_property("oscillating", False)
            self.set_property("oscillating", not current)
            return True
        elif command == "set_timer":
            timer = max(0, min(480, params.get("minutes", 0)))
            self.set_property("timer_minutes", timer)
            return True
        elif command == "set_mode":
            mode = params.get("mode", "normal")
            if mode in ["normal", "natural", "sleep"]:
                self.set_property("mode", mode)
                return True
        return False


class SmartACBehavior(HybridDevice):
    """
    Smart air conditioner behavior.

    Properties:
    - target_temp: Target temperature
    - current_temp: Current room temperature
    - mode: cool/heat/fan/auto/dry
    - fan_speed: Fan speed setting
    """

    def __init__(self, device: Device):
        super().__init__(device, report_interval_seconds=60)
        self.set_property("target_temp", 24.0)
        self.set_property("current_temp", 26.0)
        self.set_property("mode", "cool")
        self.set_property("fan_speed", "auto")
        self.set_property("swing_horizontal", False)
        self.set_property("swing_vertical", False)
        self.set_property("eco_mode", False)
        self.set_property("compressor_running", False)

    def update(self, current_time: datetime, delta_seconds: float) -> list[SimulationEvent]:
        events = super().update(current_time, delta_seconds)

        if self.device.state.is_on:
            current = self.get_property("current_temp", 26.0)
            target = self.get_property("target_temp", 24.0)
            mode = self.get_property("mode", "cool")

            # Simulate temperature change
            temp_diff = target - current
            compressor = False

            if mode == "cool" and current > target:
                current -= 0.01 * delta_seconds
                compressor = True
            elif mode == "heat" and current < target:
                current += 0.01 * delta_seconds
                compressor = True
            elif mode == "auto":
                if abs(temp_diff) > 1:
                    current += 0.01 * delta_seconds * (1 if temp_diff > 0 else -1)
                    compressor = True

            self.set_property("current_temp", round(current, 1))
            self.set_property("compressor_running", compressor)

        return events

    def generate_data(self, current_time: datetime) -> dict[str, Any]:
        return {
            "is_on": self.device.state.is_on,
            "target_temp": self.get_property("target_temp"),
            "current_temp": self.get_property("current_temp"),
            "mode": self.get_property("mode"),
            "fan_speed": self.get_property("fan_speed"),
            "swing_horizontal": self.get_property("swing_horizontal"),
            "swing_vertical": self.get_property("swing_vertical"),
            "eco_mode": self.get_property("eco_mode"),
            "compressor_running": self.get_property("compressor_running"),
            "timestamp": current_time.isoformat(),
        }

    def handle_command(self, command: str, params: dict[str, Any]) -> bool:
        if command == "turn_on":
            self.device.state.is_on = True
            return True
        elif command == "turn_off":
            self.device.state.is_on = False
            self.set_property("compressor_running", False)
            return True
        elif command == "set_temperature":
            temp = max(16, min(30, params.get("temperature", 24)))
            self.set_property("target_temp", temp)
            return True
        elif command == "set_mode":
            mode = params.get("mode", "cool")
            if mode in ["cool", "heat", "fan", "auto", "dry"]:
                self.set_property("mode", mode)
                return True
        elif command == "set_fan_speed":
            speed = params.get("speed", "auto")
            if speed in ["auto", "low", "medium", "high", "turbo"]:
                self.set_property("fan_speed", speed)
                return True
        elif command == "toggle_swing_h":
            current = self.get_property("swing_horizontal", False)
            self.set_property("swing_horizontal", not current)
            return True
        elif command == "toggle_swing_v":
            current = self.get_property("swing_vertical", False)
            self.set_property("swing_vertical", not current)
            return True
        elif command == "toggle_eco":
            current = self.get_property("eco_mode", False)
            self.set_property("eco_mode", not current)
            return True
        return False


class SmartHeaterBehavior(HybridDevice):
    """
    Smart heater behavior.

    Properties:
    - target_temp: Target temperature
    - current_temp: Room temperature
    - heat_level: Heating power level
    """

    def __init__(self, device: Device):
        super().__init__(device, report_interval_seconds=60)
        self.set_property("target_temp", 22.0)
        self.set_property("current_temp", 18.0)
        self.set_property("heat_level", "medium")  # low, medium, high
        self.set_property("eco_mode", False)
        self.set_property("child_lock", False)
        self.set_property("timer_minutes", 0)
        self.set_property("heating_active", False)

    def update(self, current_time: datetime, delta_seconds: float) -> list[SimulationEvent]:
        events = super().update(current_time, delta_seconds)

        if self.device.state.is_on:
            current = self.get_property("current_temp", 18.0)
            target = self.get_property("target_temp", 22.0)
            heat_level = self.get_property("heat_level", "medium")

            # Heat rate based on level
            rates = {"low": 0.005, "medium": 0.01, "high": 0.015}
            rate = rates.get(heat_level, 0.01)

            if current < target:
                current += rate * delta_seconds
                self.set_property("heating_active", True)
            else:
                self.set_property("heating_active", False)

            self.set_property("current_temp", round(current, 1))

        return events

    def generate_data(self, current_time: datetime) -> dict[str, Any]:
        return {
            "is_on": self.device.state.is_on,
            "target_temp": self.get_property("target_temp"),
            "current_temp": self.get_property("current_temp"),
            "heat_level": self.get_property("heat_level"),
            "eco_mode": self.get_property("eco_mode"),
            "child_lock": self.get_property("child_lock"),
            "heating_active": self.get_property("heating_active"),
            "timer_minutes": self.get_property("timer_minutes"),
            "timestamp": current_time.isoformat(),
        }

    def handle_command(self, command: str, params: dict[str, Any]) -> bool:
        if command == "turn_on":
            self.device.state.is_on = True
            return True
        elif command == "turn_off":
            self.device.state.is_on = False
            self.set_property("heating_active", False)
            return True
        elif command == "set_temperature":
            temp = max(15, min(30, params.get("temperature", 22)))
            self.set_property("target_temp", temp)
            return True
        elif command == "set_heat_level":
            level = params.get("level", "medium")
            if level in ["low", "medium", "high"]:
                self.set_property("heat_level", level)
                return True
        elif command == "toggle_eco":
            current = self.get_property("eco_mode", False)
            self.set_property("eco_mode", not current)
            return True
        elif command == "toggle_child_lock":
            current = self.get_property("child_lock", False)
            self.set_property("child_lock", not current)
            return True
        elif command == "set_timer":
            timer = max(0, min(480, params.get("minutes", 0)))
            self.set_property("timer_minutes", timer)
            return True
        return False


class SmartHumidifierBehavior(HybridDevice):
    """
    Smart humidifier behavior.

    Properties:
    - target_humidity: Target humidity percentage
    - current_humidity: Room humidity
    - mist_level: Mist output level
    """

    def __init__(self, device: Device):
        super().__init__(device, report_interval_seconds=60)
        self.set_property("target_humidity", 50)
        self.set_property("current_humidity", 35)
        self.set_property("mist_level", "medium")
        self.set_property("water_level", 100)  # Percentage remaining
        self.set_property("auto_mode", True)
        self.set_property("misting_active", False)

    def update(self, current_time: datetime, delta_seconds: float) -> list[SimulationEvent]:
        events = super().update(current_time, delta_seconds)

        if self.device.state.is_on and self.get_property("water_level", 0) > 0:
            current = self.get_property("current_humidity", 35)
            target = self.get_property("target_humidity", 50)
            mist_level = self.get_property("mist_level", "medium")

            rates = {"low": 0.02, "medium": 0.05, "high": 0.1}
            rate = rates.get(mist_level, 0.05)

            if current < target:
                current += rate * delta_seconds
                self.set_property("misting_active", True)
                # Consume water
                water = self.get_property("water_level", 100)
                water -= 0.001 * delta_seconds
                self.set_property("water_level", max(0, water))
            else:
                self.set_property("misting_active", False)

            self.set_property("current_humidity", round(min(80, current), 1))

        return events

    def generate_data(self, current_time: datetime) -> dict[str, Any]:
        return {
            "is_on": self.device.state.is_on,
            "target_humidity": self.get_property("target_humidity"),
            "current_humidity": self.get_property("current_humidity"),
            "mist_level": self.get_property("mist_level"),
            "water_level": round(self.get_property("water_level"), 1),
            "auto_mode": self.get_property("auto_mode"),
            "misting_active": self.get_property("misting_active"),
            "timestamp": current_time.isoformat(),
        }

    def handle_command(self, command: str, params: dict[str, Any]) -> bool:
        if command == "turn_on":
            self.device.state.is_on = True
            return True
        elif command == "turn_off":
            self.device.state.is_on = False
            self.set_property("misting_active", False)
            return True
        elif command == "set_humidity":
            humidity = max(30, min(70, params.get("humidity", 50)))
            self.set_property("target_humidity", humidity)
            return True
        elif command == "set_mist_level":
            level = params.get("level", "medium")
            if level in ["low", "medium", "high"]:
                self.set_property("mist_level", level)
                return True
        elif command == "toggle_auto":
            current = self.get_property("auto_mode", True)
            self.set_property("auto_mode", not current)
            return True
        elif command == "refill":
            self.set_property("water_level", 100)
            return True
        return False


class SmartDehumidifierBehavior(HybridDevice):
    """
    Smart dehumidifier behavior.

    Properties:
    - target_humidity: Target humidity percentage
    - current_humidity: Room humidity
    - tank_level: Water tank fill level
    """

    def __init__(self, device: Device):
        super().__init__(device, report_interval_seconds=60)
        self.set_property("target_humidity", 50)
        self.set_property("current_humidity", 70)
        self.set_property("fan_speed", "auto")
        self.set_property("tank_level", 0)  # Percentage full
        self.set_property("tank_full", False)
        self.set_property("continuous_drain", False)
        self.set_property("dehumidifying_active", False)

    def update(self, current_time: datetime, delta_seconds: float) -> list[SimulationEvent]:
        events = super().update(current_time, delta_seconds)

        if self.device.state.is_on and not self.get_property("tank_full", False):
            current = self.get_property("current_humidity", 70)
            target = self.get_property("target_humidity", 50)

            if current > target:
                current -= 0.03 * delta_seconds
                self.set_property("dehumidifying_active", True)

                # Fill tank unless continuous drain
                if not self.get_property("continuous_drain"):
                    tank = self.get_property("tank_level", 0)
                    tank += 0.001 * delta_seconds
                    self.set_property("tank_level", min(100, tank))
                    if tank >= 100:
                        self.set_property("tank_full", True)
                        self.set_property("dehumidifying_active", False)
            else:
                self.set_property("dehumidifying_active", False)

            self.set_property("current_humidity", round(max(30, current), 1))

        return events

    def generate_data(self, current_time: datetime) -> dict[str, Any]:
        return {
            "is_on": self.device.state.is_on,
            "target_humidity": self.get_property("target_humidity"),
            "current_humidity": self.get_property("current_humidity"),
            "fan_speed": self.get_property("fan_speed"),
            "tank_level": round(self.get_property("tank_level"), 1),
            "tank_full": self.get_property("tank_full"),
            "continuous_drain": self.get_property("continuous_drain"),
            "dehumidifying_active": self.get_property("dehumidifying_active"),
            "timestamp": current_time.isoformat(),
        }

    def handle_command(self, command: str, params: dict[str, Any]) -> bool:
        if command == "turn_on":
            if not self.get_property("tank_full"):
                self.device.state.is_on = True
                return True
            return False
        elif command == "turn_off":
            self.device.state.is_on = False
            self.set_property("dehumidifying_active", False)
            return True
        elif command == "set_humidity":
            humidity = max(30, min(70, params.get("humidity", 50)))
            self.set_property("target_humidity", humidity)
            return True
        elif command == "set_fan_speed":
            speed = params.get("speed", "auto")
            if speed in ["auto", "low", "medium", "high"]:
                self.set_property("fan_speed", speed)
                return True
        elif command == "empty_tank":
            self.set_property("tank_level", 0)
            self.set_property("tank_full", False)
            return True
        elif command == "toggle_continuous_drain":
            current = self.get_property("continuous_drain", False)
            self.set_property("continuous_drain", not current)
            return True
        return False


class AirPurifierBehavior(HybridDevice):
    """
    Smart air purifier behavior.

    Properties:
    - fan_speed: Fan speed setting
    - air_quality: Current AQI
    - filter_life: Filter life remaining percentage
    """

    def __init__(self, device: Device):
        super().__init__(device, report_interval_seconds=60)
        self.set_property("fan_speed", "auto")
        self.set_property("air_quality", 50)
        self.set_property("pm25", 15)
        self.set_property("filter_life", 100)
        self.set_property("auto_mode", True)
        self.set_property("child_lock", False)
        self.set_property("display_light", True)

    def update(self, current_time: datetime, delta_seconds: float) -> list[SimulationEvent]:
        events = super().update(current_time, delta_seconds)

        if self.device.state.is_on:
            # Improve air quality when running
            aqi = self.get_property("air_quality", 50)
            pm25 = self.get_property("pm25", 15)

            aqi = max(10, aqi - 0.01 * delta_seconds)
            pm25 = max(3, pm25 - 0.005 * delta_seconds)

            self.set_property("air_quality", round(aqi))
            self.set_property("pm25", round(pm25, 1))

            # Degrade filter
            filter_life = self.get_property("filter_life", 100)
            filter_life -= 0.0001 * delta_seconds
            self.set_property("filter_life", max(0, filter_life))

        return events

    def generate_data(self, current_time: datetime) -> dict[str, Any]:
        # Add some noise to readings
        if self.device.state.is_on:
            aqi = self.get_property("air_quality") + random.randint(-5, 5)
        else:
            # Air quality degrades when off
            aqi = min(150, self.get_property("air_quality") + random.uniform(0, 0.5))
            self.set_property("air_quality", round(aqi))

        return {
            "is_on": self.device.state.is_on,
            "fan_speed": self.get_property("fan_speed"),
            "air_quality": max(0, min(500, aqi)),
            "pm25": self.get_property("pm25"),
            "filter_life": round(self.get_property("filter_life"), 1),
            "auto_mode": self.get_property("auto_mode"),
            "child_lock": self.get_property("child_lock"),
            "display_light": self.get_property("display_light"),
            "timestamp": current_time.isoformat(),
        }

    def handle_command(self, command: str, params: dict[str, Any]) -> bool:
        if command == "turn_on":
            self.device.state.is_on = True
            return True
        elif command == "turn_off":
            self.device.state.is_on = False
            return True
        elif command == "set_fan_speed":
            speed = params.get("speed", "auto")
            if speed in ["auto", "sleep", "low", "medium", "high", "turbo"]:
                self.set_property("fan_speed", speed)
                return True
        elif command == "toggle_auto":
            current = self.get_property("auto_mode", True)
            self.set_property("auto_mode", not current)
            return True
        elif command == "toggle_child_lock":
            current = self.get_property("child_lock", False)
            self.set_property("child_lock", not current)
            return True
        elif command == "toggle_display":
            current = self.get_property("display_light", True)
            self.set_property("display_light", not current)
            return True
        elif command == "reset_filter":
            self.set_property("filter_life", 100)
            return True
        return False


# =============================================================================
# Entertainment Devices (8 types)
# =============================================================================


class StreamingDeviceBehavior(HybridDevice):
    """Streaming device (Roku, Fire TV, Apple TV, etc.)."""

    def __init__(self, device: Device):
        super().__init__(device, report_interval_seconds=60)
        self.set_property("is_playing", False)
        self.set_property("current_app", None)
        self.set_property("volume", 50)
        self.set_property("resolution", "4K")
        self.set_property("hdr_enabled", True)

    def generate_data(self, current_time: datetime) -> dict[str, Any]:
        return {
            "is_on": self.device.state.is_on,
            "is_playing": self.get_property("is_playing"),
            "current_app": self.get_property("current_app"),
            "volume": self.get_property("volume"),
            "resolution": self.get_property("resolution"),
            "hdr_enabled": self.get_property("hdr_enabled"),
            "timestamp": current_time.isoformat(),
        }

    def handle_command(self, command: str, params: dict[str, Any]) -> bool:
        if command == "turn_on":
            self.device.state.is_on = True
            return True
        elif command == "turn_off":
            self.device.state.is_on = False
            self.set_property("is_playing", False)
            return True
        elif command == "launch_app":
            self.set_property("current_app", params.get("app"))
            self.set_property("is_playing", True)
            return True
        elif command == "set_volume":
            self.set_property("volume", max(0, min(100, params.get("volume", 50))))
            return True
        return False


class SoundbarBehavior(ActuatorDevice):
    """Smart soundbar device."""

    def __init__(self, device: Device):
        super().__init__(device)
        self.set_property("volume", 30)
        self.set_property("bass", 50)
        self.set_property("treble", 50)
        self.set_property("sound_mode", "standard")
        self.set_property("input_source", "hdmi")
        self.set_property("subwoofer_level", 50)

    def generate_data(self, current_time: datetime) -> dict[str, Any]:
        return {
            "is_on": self.device.state.is_on,
            "volume": self.get_property("volume"),
            "bass": self.get_property("bass"),
            "treble": self.get_property("treble"),
            "sound_mode": self.get_property("sound_mode"),
            "input_source": self.get_property("input_source"),
            "subwoofer_level": self.get_property("subwoofer_level"),
            "timestamp": current_time.isoformat(),
        }

    def handle_command(self, command: str, params: dict[str, Any]) -> bool:
        if command == "turn_on":
            self.device.state.is_on = True
            return True
        elif command == "turn_off":
            self.device.state.is_on = False
            return True
        elif command == "set_volume":
            self.set_property("volume", max(0, min(100, params.get("volume", 30))))
            return True
        elif command == "set_sound_mode":
            mode = params.get("mode", "standard")
            if mode in ["standard", "movie", "music", "voice", "night", "sports"]:
                self.set_property("sound_mode", mode)
                return True
        elif command == "set_input":
            self.set_property("input_source", params.get("source", "hdmi"))
            return True
        return False


class SmartDisplayBehavior(HybridDevice):
    """Smart display (Echo Show, Google Nest Hub, etc.)."""

    def __init__(self, device: Device):
        super().__init__(device, report_interval_seconds=60)
        self.set_property("brightness", 70)
        self.set_property("volume", 50)
        self.set_property("screen_on", True)
        self.set_property("current_view", "clock")
        self.set_property("do_not_disturb", False)

    def generate_data(self, current_time: datetime) -> dict[str, Any]:
        return {
            "is_on": self.device.state.is_on,
            "brightness": self.get_property("brightness"),
            "volume": self.get_property("volume"),
            "screen_on": self.get_property("screen_on"),
            "current_view": self.get_property("current_view"),
            "do_not_disturb": self.get_property("do_not_disturb"),
            "timestamp": current_time.isoformat(),
        }

    def handle_command(self, command: str, params: dict[str, Any]) -> bool:
        if command == "turn_on":
            self.device.state.is_on = True
            return True
        elif command == "turn_off":
            self.device.state.is_on = False
            return True
        elif command == "set_brightness":
            self.set_property("brightness", max(0, min(100, params.get("brightness", 70))))
            return True
        elif command == "set_volume":
            self.set_property("volume", max(0, min(100, params.get("volume", 50))))
            return True
        elif command == "show_view":
            self.set_property("current_view", params.get("view", "clock"))
            return True
        elif command == "toggle_dnd":
            self.set_property("do_not_disturb", not self.get_property("do_not_disturb"))
            return True
        return False


class GamingConsoleBehavior(HybridDevice):
    """Gaming console (PlayStation, Xbox, Nintendo)."""

    def __init__(self, device: Device):
        super().__init__(device, report_interval_seconds=60)
        self.set_property("is_playing", False)
        self.set_property("current_game", None)
        self.set_property("controller_battery", 100)
        self.set_property("download_progress", None)
        self.set_property("online_status", "offline")

    def generate_data(self, current_time: datetime) -> dict[str, Any]:
        return {
            "is_on": self.device.state.is_on,
            "is_playing": self.get_property("is_playing"),
            "current_game": self.get_property("current_game"),
            "controller_battery": self.get_property("controller_battery"),
            "download_progress": self.get_property("download_progress"),
            "online_status": self.get_property("online_status"),
            "timestamp": current_time.isoformat(),
        }

    def handle_command(self, command: str, params: dict[str, Any]) -> bool:
        if command == "turn_on":
            self.device.state.is_on = True
            self.set_property("online_status", "online")
            return True
        elif command == "turn_off":
            self.device.state.is_on = False
            self.set_property("is_playing", False)
            self.set_property("online_status", "offline")
            return True
        elif command == "launch_game":
            self.set_property("current_game", params.get("game"))
            self.set_property("is_playing", True)
            return True
        elif command == "quit_game":
            self.set_property("current_game", None)
            self.set_property("is_playing", False)
            return True
        return False


class MediaServerBehavior(HybridDevice):
    """Media server (Plex, NAS media server)."""

    def __init__(self, device: Device):
        super().__init__(device, report_interval_seconds=120)
        self.set_property("active_streams", 0)
        self.set_property("storage_used_gb", random.randint(500, 2000))
        self.set_property("storage_total_gb", 4000)
        self.set_property("transcoding_active", False)
        self.set_property("connected_clients", 0)

    def generate_data(self, current_time: datetime) -> dict[str, Any]:
        return {
            "is_on": self.device.state.is_on,
            "active_streams": self.get_property("active_streams"),
            "storage_used_gb": self.get_property("storage_used_gb"),
            "storage_total_gb": self.get_property("storage_total_gb"),
            "storage_percent": round(self.get_property("storage_used_gb") / self.get_property("storage_total_gb") * 100, 1),
            "transcoding_active": self.get_property("transcoding_active"),
            "connected_clients": self.get_property("connected_clients"),
            "timestamp": current_time.isoformat(),
        }

    def handle_command(self, command: str, params: dict[str, Any]) -> bool:
        if command == "turn_on":
            self.device.state.is_on = True
            return True
        elif command == "turn_off":
            self.device.state.is_on = False
            self.set_property("active_streams", 0)
            return True
        elif command == "scan_library":
            return True
        elif command == "clear_cache":
            return True
        return False


class SmartProjectorBehavior(ActuatorDevice):
    """Smart projector device."""

    def __init__(self, device: Device):
        super().__init__(device)
        self.set_property("brightness", 100)
        self.set_property("input_source", "hdmi1")
        self.set_property("keystone", 0)
        self.set_property("lamp_hours", random.randint(100, 2000))
        self.set_property("lamp_life_remaining", 80)
        self.set_property("resolution", "1080p")

    def generate_data(self, current_time: datetime) -> dict[str, Any]:
        return {
            "is_on": self.device.state.is_on,
            "brightness": self.get_property("brightness"),
            "input_source": self.get_property("input_source"),
            "keystone": self.get_property("keystone"),
            "lamp_hours": self.get_property("lamp_hours"),
            "lamp_life_remaining": self.get_property("lamp_life_remaining"),
            "resolution": self.get_property("resolution"),
            "timestamp": current_time.isoformat(),
        }

    def handle_command(self, command: str, params: dict[str, Any]) -> bool:
        if command == "turn_on":
            self.device.state.is_on = True
            return True
        elif command == "turn_off":
            self.device.state.is_on = False
            return True
        elif command == "set_brightness":
            self.set_property("brightness", max(0, min(100, params.get("brightness", 100))))
            return True
        elif command == "set_input":
            self.set_property("input_source", params.get("source", "hdmi1"))
            return True
        elif command == "adjust_keystone":
            self.set_property("keystone", max(-40, min(40, params.get("keystone", 0))))
            return True
        return False


class MultiRoomAudioBehavior(HybridDevice):
    """Multi-room audio system (Sonos, etc.)."""

    def __init__(self, device: Device):
        super().__init__(device, report_interval_seconds=30)
        self.set_property("volume", 40)
        self.set_property("is_playing", False)
        self.set_property("current_track", None)
        self.set_property("group_name", None)
        self.set_property("grouped_speakers", [])
        self.set_property("source", "streaming")

    def generate_data(self, current_time: datetime) -> dict[str, Any]:
        return {
            "is_on": self.device.state.is_on,
            "volume": self.get_property("volume"),
            "is_playing": self.get_property("is_playing"),
            "current_track": self.get_property("current_track"),
            "group_name": self.get_property("group_name"),
            "grouped_speakers": self.get_property("grouped_speakers"),
            "source": self.get_property("source"),
            "timestamp": current_time.isoformat(),
        }

    def handle_command(self, command: str, params: dict[str, Any]) -> bool:
        if command == "turn_on":
            self.device.state.is_on = True
            return True
        elif command == "turn_off":
            self.device.state.is_on = False
            self.set_property("is_playing", False)
            return True
        elif command == "play":
            self.set_property("is_playing", True)
            return True
        elif command == "pause":
            self.set_property("is_playing", False)
            return True
        elif command == "set_volume":
            self.set_property("volume", max(0, min(100, params.get("volume", 40))))
            return True
        elif command == "join_group":
            self.set_property("group_name", params.get("group"))
            return True
        elif command == "leave_group":
            self.set_property("group_name", None)
            self.set_property("grouped_speakers", [])
            return True
        return False


class SmartRemoteBehavior(ActuatorDevice):
    """Universal smart remote control."""

    def __init__(self, device: Device):
        super().__init__(device)
        self.set_property("battery_level", random.randint(70, 100))
        self.set_property("current_activity", None)
        self.set_property("paired_devices", ["tv", "soundbar", "streaming"])
        self.set_property("backlight_on", False)

    def generate_data(self, current_time: datetime) -> dict[str, Any]:
        return {
            "battery_level": self.get_property("battery_level"),
            "current_activity": self.get_property("current_activity"),
            "paired_devices": self.get_property("paired_devices"),
            "backlight_on": self.get_property("backlight_on"),
            "timestamp": current_time.isoformat(),
        }

    def handle_command(self, command: str, params: dict[str, Any]) -> bool:
        if command == "start_activity":
            self.set_property("current_activity", params.get("activity"))
            return True
        elif command == "end_activity":
            self.set_property("current_activity", None)
            return True
        elif command == "send_command":
            return True
        elif command == "toggle_backlight":
            self.set_property("backlight_on", not self.get_property("backlight_on"))
            return True
        return False


# =============================================================================
# Kitchen Devices (10 types)
# =============================================================================


class SmartRefrigeratorBehavior(HybridDevice):
    """Smart refrigerator with temperature monitoring."""

    def __init__(self, device: Device):
        super().__init__(device, report_interval_seconds=300)
        self.set_property("fridge_temp", 37)
        self.set_property("freezer_temp", 0)
        self.set_property("door_open", False)
        self.set_property("ice_maker_on", True)
        self.set_property("water_filter_life", random.randint(50, 100))

    def generate_data(self, current_time: datetime) -> dict[str, Any]:
        return {
            "fridge_temp": self.get_property("fridge_temp") + random.uniform(-0.5, 0.5),
            "freezer_temp": self.get_property("freezer_temp") + random.uniform(-0.5, 0.5),
            "door_open": self.get_property("door_open"),
            "ice_maker_on": self.get_property("ice_maker_on"),
            "water_filter_life": self.get_property("water_filter_life"),
            "timestamp": current_time.isoformat(),
        }

    def handle_command(self, command: str, params: dict[str, Any]) -> bool:
        if command == "set_fridge_temp":
            self.set_property("fridge_temp", max(33, min(45, params.get("temp", 37))))
            return True
        elif command == "set_freezer_temp":
            self.set_property("freezer_temp", max(-10, min(10, params.get("temp", 0))))
            return True
        elif command == "toggle_ice_maker":
            self.set_property("ice_maker_on", not self.get_property("ice_maker_on"))
            return True
        return False


class SmartOvenBehavior(HybridDevice):
    """Smart oven with remote control."""

    def __init__(self, device: Device):
        super().__init__(device, report_interval_seconds=30)
        self.set_property("target_temp", 350)
        self.set_property("current_temp", 70)
        self.set_property("mode", "off")
        self.set_property("timer_minutes", 0)
        self.set_property("preheat_complete", False)

    def update(self, current_time: datetime, delta_seconds: float) -> list[SimulationEvent]:
        events = super().update(current_time, delta_seconds)
        mode = self.get_property("mode")
        if mode != "off":
            current = self.get_property("current_temp")
            target = self.get_property("target_temp")
            if current < target:
                current = min(target, current + 2 * delta_seconds)
                self.set_property("current_temp", round(current))
                if current >= target - 5:
                    self.set_property("preheat_complete", True)
        else:
            current = self.get_property("current_temp")
            if current > 70:
                self.set_property("current_temp", max(70, current - 0.5 * delta_seconds))
        return events

    def generate_data(self, current_time: datetime) -> dict[str, Any]:
        return {
            "target_temp": self.get_property("target_temp"),
            "current_temp": self.get_property("current_temp"),
            "mode": self.get_property("mode"),
            "timer_minutes": self.get_property("timer_minutes"),
            "preheat_complete": self.get_property("preheat_complete"),
            "timestamp": current_time.isoformat(),
        }

    def handle_command(self, command: str, params: dict[str, Any]) -> bool:
        if command == "set_temp":
            self.set_property("target_temp", max(150, min(550, params.get("temp", 350))))
            return True
        elif command == "set_mode":
            mode = params.get("mode", "off")
            if mode in ["off", "bake", "broil", "convection", "warm"]:
                self.set_property("mode", mode)
                if mode == "off":
                    self.set_property("preheat_complete", False)
                return True
        elif command == "set_timer":
            self.set_property("timer_minutes", max(0, params.get("minutes", 0)))
            return True
        return False


class SmartMicrowaveBehavior(ActuatorDevice):
    """Smart microwave oven."""

    def __init__(self, device: Device):
        super().__init__(device)
        self.set_property("power_level", 100)
        self.set_property("timer_seconds", 0)
        self.set_property("is_running", False)
        self.set_property("door_open", False)

    def generate_data(self, current_time: datetime) -> dict[str, Any]:
        return {
            "power_level": self.get_property("power_level"),
            "timer_seconds": self.get_property("timer_seconds"),
            "is_running": self.get_property("is_running"),
            "door_open": self.get_property("door_open"),
            "timestamp": current_time.isoformat(),
        }

    def handle_command(self, command: str, params: dict[str, Any]) -> bool:
        if command == "start":
            if not self.get_property("door_open"):
                self.set_property("is_running", True)
                return True
        elif command == "stop":
            self.set_property("is_running", False)
            return True
        elif command == "set_power":
            self.set_property("power_level", max(10, min(100, params.get("level", 100))))
            return True
        elif command == "set_timer":
            self.set_property("timer_seconds", max(0, params.get("seconds", 0)))
            return True
        return False


class SmartCoffeeMakerBehavior(HybridDevice):
    """Smart coffee maker."""

    def __init__(self, device: Device):
        super().__init__(device, report_interval_seconds=60)
        self.set_property("is_brewing", False)
        self.set_property("water_level", random.randint(50, 100))
        self.set_property("coffee_strength", "medium")
        self.set_property("cups_selected", 4)
        self.set_property("keep_warm", True)
        self.set_property("scheduled_time", None)

    def generate_data(self, current_time: datetime) -> dict[str, Any]:
        return {
            "is_on": self.device.state.is_on,
            "is_brewing": self.get_property("is_brewing"),
            "water_level": self.get_property("water_level"),
            "coffee_strength": self.get_property("coffee_strength"),
            "cups_selected": self.get_property("cups_selected"),
            "keep_warm": self.get_property("keep_warm"),
            "scheduled_time": self.get_property("scheduled_time"),
            "timestamp": current_time.isoformat(),
        }

    def handle_command(self, command: str, params: dict[str, Any]) -> bool:
        if command == "brew":
            if self.get_property("water_level") > 10:
                self.set_property("is_brewing", True)
                return True
        elif command == "stop":
            self.set_property("is_brewing", False)
            return True
        elif command == "set_strength":
            strength = params.get("strength", "medium")
            if strength in ["light", "medium", "strong", "extra_strong"]:
                self.set_property("coffee_strength", strength)
                return True
        elif command == "set_cups":
            self.set_property("cups_selected", max(1, min(12, params.get("cups", 4))))
            return True
        elif command == "schedule":
            self.set_property("scheduled_time", params.get("time"))
            return True
        return False


class SmartKettleBehavior(HybridDevice):
    """Smart electric kettle."""

    def __init__(self, device: Device):
        super().__init__(device, report_interval_seconds=10)
        self.set_property("target_temp", 212)
        self.set_property("current_temp", 70)
        self.set_property("is_heating", False)
        self.set_property("keep_warm", False)
        self.set_property("water_level", random.randint(30, 100))

    def update(self, current_time: datetime, delta_seconds: float) -> list[SimulationEvent]:
        events = super().update(current_time, delta_seconds)
        if self.get_property("is_heating"):
            current = self.get_property("current_temp")
            target = self.get_property("target_temp")
            if current < target:
                current = min(target, current + 5 * delta_seconds)
                self.set_property("current_temp", round(current))
            else:
                self.set_property("is_heating", False)
        return events

    def generate_data(self, current_time: datetime) -> dict[str, Any]:
        return {
            "target_temp": self.get_property("target_temp"),
            "current_temp": self.get_property("current_temp"),
            "is_heating": self.get_property("is_heating"),
            "keep_warm": self.get_property("keep_warm"),
            "water_level": self.get_property("water_level"),
            "timestamp": current_time.isoformat(),
        }

    def handle_command(self, command: str, params: dict[str, Any]) -> bool:
        if command == "start":
            if self.get_property("water_level") > 10:
                self.set_property("is_heating", True)
                return True
        elif command == "stop":
            self.set_property("is_heating", False)
            return True
        elif command == "set_temp":
            self.set_property("target_temp", max(100, min(212, params.get("temp", 212))))
            return True
        elif command == "toggle_keep_warm":
            self.set_property("keep_warm", not self.get_property("keep_warm"))
            return True
        return False


class SmartToasterBehavior(ActuatorDevice):
    """Smart toaster."""

    def __init__(self, device: Device):
        super().__init__(device)
        self.set_property("browning_level", 3)
        self.set_property("is_toasting", False)
        self.set_property("mode", "toast")

    def generate_data(self, current_time: datetime) -> dict[str, Any]:
        return {
            "browning_level": self.get_property("browning_level"),
            "is_toasting": self.get_property("is_toasting"),
            "mode": self.get_property("mode"),
            "timestamp": current_time.isoformat(),
        }

    def handle_command(self, command: str, params: dict[str, Any]) -> bool:
        if command == "start":
            self.set_property("is_toasting", True)
            return True
        elif command == "stop":
            self.set_property("is_toasting", False)
            return True
        elif command == "set_level":
            self.set_property("browning_level", max(1, min(7, params.get("level", 3))))
            return True
        elif command == "set_mode":
            mode = params.get("mode", "toast")
            if mode in ["toast", "bagel", "defrost", "reheat"]:
                self.set_property("mode", mode)
                return True
        return False


class SmartBlenderBehavior(ActuatorDevice):
    """Smart blender."""

    def __init__(self, device: Device):
        super().__init__(device)
        self.set_property("speed", 0)
        self.set_property("is_running", False)
        self.set_property("program", None)
        self.set_property("lid_secure", True)

    def generate_data(self, current_time: datetime) -> dict[str, Any]:
        return {
            "speed": self.get_property("speed"),
            "is_running": self.get_property("is_running"),
            "program": self.get_property("program"),
            "lid_secure": self.get_property("lid_secure"),
            "timestamp": current_time.isoformat(),
        }

    def handle_command(self, command: str, params: dict[str, Any]) -> bool:
        if command == "start":
            if self.get_property("lid_secure"):
                self.set_property("is_running", True)
                return True
        elif command == "stop":
            self.set_property("is_running", False)
            self.set_property("speed", 0)
            return True
        elif command == "set_speed":
            self.set_property("speed", max(0, min(10, params.get("speed", 5))))
            return True
        elif command == "run_program":
            program = params.get("program")
            if program in ["smoothie", "ice_crush", "soup", "pulse"]:
                self.set_property("program", program)
                self.set_property("is_running", True)
                return True
        return False


class SmartDishwasherBehavior(HybridDevice):
    """Smart dishwasher."""

    def __init__(self, device: Device):
        super().__init__(device, report_interval_seconds=60)
        self.set_property("cycle", "normal")
        self.set_property("is_running", False)
        self.set_property("progress_percent", 0)
        self.set_property("rinse_aid_level", random.randint(50, 100))
        self.set_property("time_remaining_minutes", 0)

    def update(self, current_time: datetime, delta_seconds: float) -> list[SimulationEvent]:
        events = super().update(current_time, delta_seconds)
        if self.get_property("is_running"):
            progress = self.get_property("progress_percent")
            progress += 0.02 * delta_seconds
            if progress >= 100:
                self.set_property("is_running", False)
                self.set_property("progress_percent", 0)
            else:
                self.set_property("progress_percent", round(progress, 1))
        return events

    def generate_data(self, current_time: datetime) -> dict[str, Any]:
        return {
            "cycle": self.get_property("cycle"),
            "is_running": self.get_property("is_running"),
            "progress_percent": self.get_property("progress_percent"),
            "rinse_aid_level": self.get_property("rinse_aid_level"),
            "time_remaining_minutes": self.get_property("time_remaining_minutes"),
            "timestamp": current_time.isoformat(),
        }

    def handle_command(self, command: str, params: dict[str, Any]) -> bool:
        if command == "start":
            self.set_property("is_running", True)
            self.set_property("progress_percent", 0)
            return True
        elif command == "stop":
            self.set_property("is_running", False)
            return True
        elif command == "set_cycle":
            cycle = params.get("cycle", "normal")
            if cycle in ["light", "normal", "heavy", "eco", "quick", "sanitize"]:
                self.set_property("cycle", cycle)
                return True
        return False


class SmartFaucetBehavior(ActuatorDevice):
    """Smart kitchen faucet."""

    def __init__(self, device: Device):
        super().__init__(device)
        self.set_property("is_flowing", False)
        self.set_property("temperature", "warm")
        self.set_property("flow_rate", "normal")
        self.set_property("total_gallons_today", random.uniform(5, 20))

    def generate_data(self, current_time: datetime) -> dict[str, Any]:
        return {
            "is_flowing": self.get_property("is_flowing"),
            "temperature": self.get_property("temperature"),
            "flow_rate": self.get_property("flow_rate"),
            "total_gallons_today": round(self.get_property("total_gallons_today"), 1),
            "timestamp": current_time.isoformat(),
        }

    def handle_command(self, command: str, params: dict[str, Any]) -> bool:
        if command == "turn_on":
            self.set_property("is_flowing", True)
            return True
        elif command == "turn_off":
            self.set_property("is_flowing", False)
            return True
        elif command == "set_temp":
            temp = params.get("temperature", "warm")
            if temp in ["cold", "warm", "hot"]:
                self.set_property("temperature", temp)
                return True
        elif command == "set_flow":
            flow = params.get("rate", "normal")
            if flow in ["low", "normal", "high"]:
                self.set_property("flow_rate", flow)
                return True
        return False


class SmartScaleKitchenBehavior(SensorDevice):
    """Smart kitchen scale."""

    def __init__(self, device: Device):
        super().__init__(device, report_interval_seconds=5)
        self.set_property("weight_grams", 0)
        self.set_property("unit", "grams")
        self.set_property("tare_weight", 0)

    def generate_data(self, current_time: datetime) -> dict[str, Any]:
        weight = max(0, self.get_property("weight_grams") - self.get_property("tare_weight"))
        return {
            "weight_grams": weight,
            "unit": self.get_property("unit"),
            "timestamp": current_time.isoformat(),
        }

    def handle_command(self, command: str, params: dict[str, Any]) -> bool:
        if command == "tare":
            self.set_property("tare_weight", self.get_property("weight_grams"))
            return True
        elif command == "set_unit":
            unit = params.get("unit", "grams")
            if unit in ["grams", "ounces", "pounds", "kg"]:
                self.set_property("unit", unit)
                return True
        elif command == "reset":
            self.set_property("tare_weight", 0)
            return True
        return False


# =============================================================================
# Appliances (6 types)
# =============================================================================


class SmartWasherBehavior(HybridDevice):
    """Smart washing machine."""

    def __init__(self, device: Device):
        super().__init__(device, report_interval_seconds=60)
        self.set_property("cycle", "normal")
        self.set_property("is_running", False)
        self.set_property("progress_percent", 0)
        self.set_property("water_temp", "warm")
        self.set_property("spin_speed", "medium")
        self.set_property("time_remaining_minutes", 0)

    def update(self, current_time: datetime, delta_seconds: float) -> list[SimulationEvent]:
        events = super().update(current_time, delta_seconds)
        if self.get_property("is_running"):
            progress = self.get_property("progress_percent")
            progress += 0.015 * delta_seconds
            if progress >= 100:
                self.set_property("is_running", False)
                self.set_property("progress_percent", 0)
            else:
                self.set_property("progress_percent", round(progress, 1))
        return events

    def generate_data(self, current_time: datetime) -> dict[str, Any]:
        return {
            "cycle": self.get_property("cycle"),
            "is_running": self.get_property("is_running"),
            "progress_percent": self.get_property("progress_percent"),
            "water_temp": self.get_property("water_temp"),
            "spin_speed": self.get_property("spin_speed"),
            "time_remaining_minutes": self.get_property("time_remaining_minutes"),
            "timestamp": current_time.isoformat(),
        }

    def handle_command(self, command: str, params: dict[str, Any]) -> bool:
        if command == "start":
            self.set_property("is_running", True)
            self.set_property("progress_percent", 0)
            return True
        elif command == "stop":
            self.set_property("is_running", False)
            return True
        elif command == "set_cycle":
            cycle = params.get("cycle", "normal")
            if cycle in ["delicate", "normal", "heavy", "quick", "bedding", "sanitize"]:
                self.set_property("cycle", cycle)
                return True
        elif command == "set_temp":
            temp = params.get("temp", "warm")
            if temp in ["cold", "warm", "hot"]:
                self.set_property("water_temp", temp)
                return True
        return False


class SmartDryerBehavior(HybridDevice):
    """Smart clothes dryer."""

    def __init__(self, device: Device):
        super().__init__(device, report_interval_seconds=60)
        self.set_property("cycle", "normal")
        self.set_property("is_running", False)
        self.set_property("progress_percent", 0)
        self.set_property("heat_level", "medium")
        self.set_property("time_remaining_minutes", 0)
        self.set_property("lint_filter_status", "clean")

    def update(self, current_time: datetime, delta_seconds: float) -> list[SimulationEvent]:
        events = super().update(current_time, delta_seconds)
        if self.get_property("is_running"):
            progress = self.get_property("progress_percent")
            progress += 0.02 * delta_seconds
            if progress >= 100:
                self.set_property("is_running", False)
                self.set_property("progress_percent", 0)
            else:
                self.set_property("progress_percent", round(progress, 1))
        return events

    def generate_data(self, current_time: datetime) -> dict[str, Any]:
        return {
            "cycle": self.get_property("cycle"),
            "is_running": self.get_property("is_running"),
            "progress_percent": self.get_property("progress_percent"),
            "heat_level": self.get_property("heat_level"),
            "time_remaining_minutes": self.get_property("time_remaining_minutes"),
            "lint_filter_status": self.get_property("lint_filter_status"),
            "timestamp": current_time.isoformat(),
        }

    def handle_command(self, command: str, params: dict[str, Any]) -> bool:
        if command == "start":
            self.set_property("is_running", True)
            self.set_property("progress_percent", 0)
            return True
        elif command == "stop":
            self.set_property("is_running", False)
            return True
        elif command == "set_cycle":
            cycle = params.get("cycle", "normal")
            if cycle in ["delicate", "normal", "heavy", "quick", "air_dry"]:
                self.set_property("cycle", cycle)
                return True
        elif command == "set_heat":
            heat = params.get("heat", "medium")
            if heat in ["no_heat", "low", "medium", "high"]:
                self.set_property("heat_level", heat)
                return True
        return False


class SmartIronBehavior(ActuatorDevice):
    """Smart iron."""

    def __init__(self, device: Device):
        super().__init__(device)
        self.set_property("target_temp", 300)
        self.set_property("current_temp", 70)
        self.set_property("steam_level", "medium")
        self.set_property("is_heating", False)
        self.set_property("auto_shutoff_minutes", 10)

    def generate_data(self, current_time: datetime) -> dict[str, Any]:
        return {
            "is_on": self.device.state.is_on,
            "target_temp": self.get_property("target_temp"),
            "current_temp": self.get_property("current_temp"),
            "steam_level": self.get_property("steam_level"),
            "is_heating": self.get_property("is_heating"),
            "timestamp": current_time.isoformat(),
        }

    def handle_command(self, command: str, params: dict[str, Any]) -> bool:
        if command == "turn_on":
            self.device.state.is_on = True
            self.set_property("is_heating", True)
            return True
        elif command == "turn_off":
            self.device.state.is_on = False
            self.set_property("is_heating", False)
            return True
        elif command == "set_temp":
            self.set_property("target_temp", max(200, min(450, params.get("temp", 300))))
            return True
        elif command == "set_steam":
            steam = params.get("level", "medium")
            if steam in ["off", "low", "medium", "high", "burst"]:
                self.set_property("steam_level", steam)
                return True
        return False


class SmartSewingMachineBehavior(ActuatorDevice):
    """Smart sewing machine."""

    def __init__(self, device: Device):
        super().__init__(device)
        self.set_property("stitch_type", "straight")
        self.set_property("speed", 50)
        self.set_property("needle_position", "center")
        self.set_property("thread_tension", 4)
        self.set_property("is_sewing", False)

    def generate_data(self, current_time: datetime) -> dict[str, Any]:
        return {
            "is_on": self.device.state.is_on,
            "stitch_type": self.get_property("stitch_type"),
            "speed": self.get_property("speed"),
            "needle_position": self.get_property("needle_position"),
            "thread_tension": self.get_property("thread_tension"),
            "is_sewing": self.get_property("is_sewing"),
            "timestamp": current_time.isoformat(),
        }

    def handle_command(self, command: str, params: dict[str, Any]) -> bool:
        if command == "turn_on":
            self.device.state.is_on = True
            return True
        elif command == "turn_off":
            self.device.state.is_on = False
            self.set_property("is_sewing", False)
            return True
        elif command == "set_stitch":
            stitch = params.get("type", "straight")
            if stitch in ["straight", "zigzag", "buttonhole", "overlock", "decorative"]:
                self.set_property("stitch_type", stitch)
                return True
        elif command == "set_speed":
            self.set_property("speed", max(1, min(100, params.get("speed", 50))))
            return True
        return False


class SmartWaterHeaterBehavior(HybridDevice):
    """Smart water heater."""

    def __init__(self, device: Device):
        super().__init__(device, report_interval_seconds=120)
        self.set_property("target_temp", 120)
        self.set_property("current_temp", 120)
        self.set_property("mode", "standard")
        self.set_property("is_heating", False)
        self.set_property("vacation_mode", False)

    def update(self, current_time: datetime, delta_seconds: float) -> list[SimulationEvent]:
        events = super().update(current_time, delta_seconds)
        if self.device.state.is_on and not self.get_property("vacation_mode"):
            current = self.get_property("current_temp")
            target = self.get_property("target_temp")
            if current < target - 5:
                self.set_property("is_heating", True)
                current = min(target, current + 0.1 * delta_seconds)
            else:
                self.set_property("is_heating", False)
            self.set_property("current_temp", round(current, 1))
        return events

    def generate_data(self, current_time: datetime) -> dict[str, Any]:
        return {
            "is_on": self.device.state.is_on,
            "target_temp": self.get_property("target_temp"),
            "current_temp": self.get_property("current_temp"),
            "mode": self.get_property("mode"),
            "is_heating": self.get_property("is_heating"),
            "vacation_mode": self.get_property("vacation_mode"),
            "timestamp": current_time.isoformat(),
        }

    def handle_command(self, command: str, params: dict[str, Any]) -> bool:
        if command == "turn_on":
            self.device.state.is_on = True
            return True
        elif command == "turn_off":
            self.device.state.is_on = False
            self.set_property("is_heating", False)
            return True
        elif command == "set_temp":
            self.set_property("target_temp", max(90, min(140, params.get("temp", 120))))
            return True
        elif command == "set_mode":
            mode = params.get("mode", "standard")
            if mode in ["eco", "standard", "high_demand"]:
                self.set_property("mode", mode)
                return True
        elif command == "toggle_vacation":
            self.set_property("vacation_mode", not self.get_property("vacation_mode"))
            return True
        return False


class SmartGarbageDisposalBehavior(ActuatorDevice):
    """Smart garbage disposal."""

    def __init__(self, device: Device):
        super().__init__(device)
        self.set_property("is_running", False)
        self.set_property("jam_detected", False)
        self.set_property("power_level", "normal")

    def generate_data(self, current_time: datetime) -> dict[str, Any]:
        return {
            "is_running": self.get_property("is_running"),
            "jam_detected": self.get_property("jam_detected"),
            "power_level": self.get_property("power_level"),
            "timestamp": current_time.isoformat(),
        }

    def handle_command(self, command: str, params: dict[str, Any]) -> bool:
        if command == "start":
            if not self.get_property("jam_detected"):
                self.set_property("is_running", True)
                return True
        elif command == "stop":
            self.set_property("is_running", False)
            return True
        elif command == "reverse":
            self.set_property("jam_detected", False)
            return True
        elif command == "set_power":
            power = params.get("level", "normal")
            if power in ["low", "normal", "high"]:
                self.set_property("power_level", power)
                return True
        return False


# =============================================================================
# Health & Wellness (7 types - AIR_PURIFIER already implemented above)
# =============================================================================


class SmartScaleBehavior(SensorDevice):
    """Smart body weight scale."""

    def __init__(self, device: Device):
        super().__init__(device, report_interval_seconds=10)
        self.set_property("weight_lbs", 0)
        self.set_property("body_fat_percent", 0)
        self.set_property("bmi", 0)
        self.set_property("user_profile", None)

    def generate_data(self, current_time: datetime) -> dict[str, Any]:
        return {
            "weight_lbs": self.get_property("weight_lbs"),
            "body_fat_percent": self.get_property("body_fat_percent"),
            "bmi": self.get_property("bmi"),
            "user_profile": self.get_property("user_profile"),
            "timestamp": current_time.isoformat(),
        }

    def handle_command(self, command: str, params: dict[str, Any]) -> bool:
        if command == "set_user":
            self.set_property("user_profile", params.get("user"))
            return True
        elif command == "clear":
            self.set_property("weight_lbs", 0)
            return True
        return False


class BloodPressureMonitorBehavior(SensorDevice):
    """Smart blood pressure monitor."""

    def __init__(self, device: Device):
        super().__init__(device, report_interval_seconds=5)
        self.set_property("systolic", 0)
        self.set_property("diastolic", 0)
        self.set_property("pulse", 0)
        self.set_property("is_measuring", False)
        self.set_property("irregular_heartbeat", False)

    def generate_data(self, current_time: datetime) -> dict[str, Any]:
        return {
            "systolic": self.get_property("systolic"),
            "diastolic": self.get_property("diastolic"),
            "pulse": self.get_property("pulse"),
            "is_measuring": self.get_property("is_measuring"),
            "irregular_heartbeat": self.get_property("irregular_heartbeat"),
            "timestamp": current_time.isoformat(),
        }

    def handle_command(self, command: str, params: dict[str, Any]) -> bool:
        if command == "start_measurement":
            self.set_property("is_measuring", True)
            return True
        elif command == "stop":
            self.set_property("is_measuring", False)
            return True
        return False


class SleepTrackerBehavior(SensorDevice):
    """Smart sleep tracker."""

    def __init__(self, device: Device):
        super().__init__(device, report_interval_seconds=300)
        self.set_property("sleep_stage", "awake")
        self.set_property("heart_rate", 70)
        self.set_property("movement_level", "none")
        self.set_property("sleep_score", 0)
        self.set_property("is_tracking", False)

    def generate_data(self, current_time: datetime) -> dict[str, Any]:
        return {
            "sleep_stage": self.get_property("sleep_stage"),
            "heart_rate": self.get_property("heart_rate"),
            "movement_level": self.get_property("movement_level"),
            "sleep_score": self.get_property("sleep_score"),
            "is_tracking": self.get_property("is_tracking"),
            "timestamp": current_time.isoformat(),
        }

    def handle_command(self, command: str, params: dict[str, Any]) -> bool:
        if command == "start_tracking":
            self.set_property("is_tracking", True)
            return True
        elif command == "stop_tracking":
            self.set_property("is_tracking", False)
            return True
        return False


class SmartPillDispenserBehavior(HybridDevice):
    """Smart pill dispenser."""

    def __init__(self, device: Device):
        super().__init__(device, report_interval_seconds=60)
        self.set_property("compartments", 7)
        self.set_property("next_dose_time", None)
        self.set_property("doses_remaining", random.randint(10, 28))
        self.set_property("alarm_enabled", True)
        self.set_property("last_dispensed", None)

    def generate_data(self, current_time: datetime) -> dict[str, Any]:
        return {
            "compartments": self.get_property("compartments"),
            "next_dose_time": self.get_property("next_dose_time"),
            "doses_remaining": self.get_property("doses_remaining"),
            "alarm_enabled": self.get_property("alarm_enabled"),
            "last_dispensed": self.get_property("last_dispensed"),
            "timestamp": current_time.isoformat(),
        }

    def handle_command(self, command: str, params: dict[str, Any]) -> bool:
        if command == "dispense":
            doses = self.get_property("doses_remaining")
            if doses > 0:
                self.set_property("doses_remaining", doses - 1)
                self.set_property("last_dispensed", datetime.now().isoformat())
                return True
        elif command == "set_schedule":
            self.set_property("next_dose_time", params.get("time"))
            return True
        elif command == "toggle_alarm":
            self.set_property("alarm_enabled", not self.get_property("alarm_enabled"))
            return True
        elif command == "refill":
            self.set_property("doses_remaining", params.get("doses", 28))
            return True
        return False


class SmartMattressBehavior(SensorDevice):
    """Smart mattress with sleep monitoring."""

    def __init__(self, device: Device):
        super().__init__(device, report_interval_seconds=60)
        self.set_property("firmness_left", 50)
        self.set_property("firmness_right", 50)
        self.set_property("temperature_left", 72)
        self.set_property("temperature_right", 72)
        self.set_property("occupancy", "empty")

    def generate_data(self, current_time: datetime) -> dict[str, Any]:
        return {
            "firmness_left": self.get_property("firmness_left"),
            "firmness_right": self.get_property("firmness_right"),
            "temperature_left": self.get_property("temperature_left"),
            "temperature_right": self.get_property("temperature_right"),
            "occupancy": self.get_property("occupancy"),
            "timestamp": current_time.isoformat(),
        }

    def handle_command(self, command: str, params: dict[str, Any]) -> bool:
        if command == "set_firmness":
            side = params.get("side", "both")
            firmness = max(0, min(100, params.get("firmness", 50)))
            if side in ["left", "both"]:
                self.set_property("firmness_left", firmness)
            if side in ["right", "both"]:
                self.set_property("firmness_right", firmness)
            return True
        elif command == "set_temperature":
            side = params.get("side", "both")
            temp = max(60, min(90, params.get("temp", 72)))
            if side in ["left", "both"]:
                self.set_property("temperature_left", temp)
            if side in ["right", "both"]:
                self.set_property("temperature_right", temp)
            return True
        return False


class FitnessTrackerDockBehavior(SensorDevice):
    """Fitness tracker dock/charger with data sync."""

    def __init__(self, device: Device):
        super().__init__(device, report_interval_seconds=60)
        self.set_property("tracker_connected", False)
        self.set_property("battery_level", 0)
        self.set_property("steps_today", 0)
        self.set_property("calories_burned", 0)
        self.set_property("sync_status", "idle")

    def generate_data(self, current_time: datetime) -> dict[str, Any]:
        return {
            "tracker_connected": self.get_property("tracker_connected"),
            "battery_level": self.get_property("battery_level"),
            "steps_today": self.get_property("steps_today"),
            "calories_burned": self.get_property("calories_burned"),
            "sync_status": self.get_property("sync_status"),
            "timestamp": current_time.isoformat(),
        }

    def handle_command(self, command: str, params: dict[str, Any]) -> bool:
        if command == "sync":
            self.set_property("sync_status", "syncing")
            return True
        return False


class SmartMirrorBehavior(HybridDevice):
    """Smart mirror with display."""

    def __init__(self, device: Device):
        super().__init__(device, report_interval_seconds=60)
        self.set_property("display_on", True)
        self.set_property("brightness", 70)
        self.set_property("current_widget", "clock")
        self.set_property("ambient_light", 50)

    def generate_data(self, current_time: datetime) -> dict[str, Any]:
        return {
            "is_on": self.device.state.is_on,
            "display_on": self.get_property("display_on"),
            "brightness": self.get_property("brightness"),
            "current_widget": self.get_property("current_widget"),
            "ambient_light": self.get_property("ambient_light"),
            "timestamp": current_time.isoformat(),
        }

    def handle_command(self, command: str, params: dict[str, Any]) -> bool:
        if command == "turn_on":
            self.device.state.is_on = True
            return True
        elif command == "turn_off":
            self.device.state.is_on = False
            return True
        elif command == "set_brightness":
            self.set_property("brightness", max(0, min(100, params.get("brightness", 70))))
            return True
        elif command == "show_widget":
            widget = params.get("widget", "clock")
            if widget in ["clock", "weather", "calendar", "news", "fitness"]:
                self.set_property("current_widget", widget)
                return True
        elif command == "toggle_display":
            self.set_property("display_on", not self.get_property("display_on"))
            return True
        return False


# =============================================================================
# ENERGY DEVICES (5 types)
# =============================================================================


class SolarInverterBehavior(HybridDevice):
    """Solar panel inverter monitoring."""

    def __init__(self, device: Device):
        super().__init__(device, report_interval_seconds=60)
        self.set_property("power_output_watts", 0)
        self.set_property("daily_yield_kwh", 0.0)
        self.set_property("total_yield_kwh", 0.0)
        self.set_property("efficiency_percent", 95.0)
        self.set_property("grid_status", "connected")
        self.set_property("dc_voltage", 0.0)
        self.set_property("ac_voltage", 230.0)

    def generate_data(self, current_time: datetime) -> dict[str, Any]:
        # Simulate solar output based on time of day
        hour = current_time.hour
        if 6 <= hour <= 18:
            base_output = 3000 * math.sin(math.pi * (hour - 6) / 12)
            output = max(0, base_output + random.uniform(-200, 200))
        else:
            output = 0
        self.set_property("power_output_watts", output)

        return {
            "power_output_watts": self.get_property("power_output_watts"),
            "daily_yield_kwh": self.get_property("daily_yield_kwh"),
            "total_yield_kwh": self.get_property("total_yield_kwh"),
            "efficiency_percent": self.get_property("efficiency_percent"),
            "grid_status": self.get_property("grid_status"),
            "dc_voltage": self.get_property("dc_voltage"),
            "ac_voltage": self.get_property("ac_voltage"),
            "timestamp": current_time.isoformat(),
        }

    def handle_command(self, command: str, params: dict[str, Any]) -> bool:
        if command == "reset_daily_yield":
            self.set_property("daily_yield_kwh", 0.0)
            return True
        elif command == "disconnect_grid":
            self.set_property("grid_status", "disconnected")
            return True
        elif command == "connect_grid":
            self.set_property("grid_status", "connected")
            return True
        return False


class BatteryStorageBehavior(HybridDevice):
    """Home battery storage system."""

    def __init__(self, device: Device):
        super().__init__(device, report_interval_seconds=60)
        self.set_property("charge_percent", 50.0)
        self.set_property("capacity_kwh", 13.5)
        self.set_property("power_flow_watts", 0)
        self.set_property("mode", "auto")  # auto, charge, discharge, standby
        self.set_property("health_percent", 100.0)
        self.set_property("temperature_celsius", 25.0)
        self.set_property("cycles", 0)

    def generate_data(self, current_time: datetime) -> dict[str, Any]:
        return {
            "charge_percent": self.get_property("charge_percent"),
            "capacity_kwh": self.get_property("capacity_kwh"),
            "power_flow_watts": self.get_property("power_flow_watts"),
            "mode": self.get_property("mode"),
            "health_percent": self.get_property("health_percent"),
            "temperature_celsius": self.get_property("temperature_celsius"),
            "cycles": self.get_property("cycles"),
            "timestamp": current_time.isoformat(),
        }

    def handle_command(self, command: str, params: dict[str, Any]) -> bool:
        if command == "set_mode":
            mode = params.get("mode", "auto")
            if mode in ["auto", "charge", "discharge", "standby"]:
                self.set_property("mode", mode)
                return True
        elif command == "set_reserve":
            reserve = params.get("reserve_percent", 20)
            self.set_property("reserve_percent", max(0, min(100, reserve)))
            return True
        return False

    def update(self, current_time: datetime, delta_seconds: float) -> list:
        events = super().update(current_time, delta_seconds)
        mode = self.get_property("mode")
        charge = self.get_property("charge_percent")

        if mode == "charge" and charge < 100:
            self.set_property("charge_percent", min(100, charge + 0.1))
            self.set_property("power_flow_watts", 3000)
        elif mode == "discharge" and charge > 0:
            self.set_property("charge_percent", max(0, charge - 0.1))
            self.set_property("power_flow_watts", -3000)
        else:
            self.set_property("power_flow_watts", 0)
        return events


class EVChargerBehavior(HybridDevice):
    """Electric vehicle charging station."""

    def __init__(self, device: Device):
        super().__init__(device, report_interval_seconds=30)
        self.set_property("charging_state", "idle")  # idle, connected, charging, complete
        self.set_property("power_output_kw", 0.0)
        self.set_property("max_power_kw", 11.0)
        self.set_property("energy_delivered_kwh", 0.0)
        self.set_property("session_energy_kwh", 0.0)
        self.set_property("vehicle_battery_percent", 0)
        self.set_property("scheduled_start", None)

    def generate_data(self, current_time: datetime) -> dict[str, Any]:
        return {
            "charging_state": self.get_property("charging_state"),
            "power_output_kw": self.get_property("power_output_kw"),
            "max_power_kw": self.get_property("max_power_kw"),
            "energy_delivered_kwh": self.get_property("energy_delivered_kwh"),
            "session_energy_kwh": self.get_property("session_energy_kwh"),
            "vehicle_battery_percent": self.get_property("vehicle_battery_percent"),
            "timestamp": current_time.isoformat(),
        }

    def handle_command(self, command: str, params: dict[str, Any]) -> bool:
        if command == "start_charging":
            if self.get_property("charging_state") == "connected":
                self.set_property("charging_state", "charging")
                self.set_property("power_output_kw", self.get_property("max_power_kw"))
                return True
        elif command == "stop_charging":
            self.set_property("charging_state", "connected")
            self.set_property("power_output_kw", 0.0)
            return True
        elif command == "set_max_power":
            power = params.get("power_kw", 11.0)
            self.set_property("max_power_kw", max(1.0, min(22.0, power)))
            return True
        elif command == "schedule":
            self.set_property("scheduled_start", params.get("start_time"))
            return True
        return False

    def update(self, current_time: datetime, delta_seconds: float) -> list:
        events = super().update(current_time, delta_seconds)
        if self.get_property("charging_state") == "charging":
            battery = self.get_property("vehicle_battery_percent")
            if battery < 100:
                self.set_property("vehicle_battery_percent", min(100, battery + 1))
                energy = delta_seconds / 3600 * self.get_property("power_output_kw")
                self.set_property("session_energy_kwh", self.get_property("session_energy_kwh") + energy)
            else:
                self.set_property("charging_state", "complete")
                self.set_property("power_output_kw", 0.0)
        return events


class EnergyMonitorBehavior(SensorDevice):
    """Whole-home energy monitoring."""

    def __init__(self, device: Device):
        super().__init__(device, report_interval_seconds=10)
        self.set_property("current_power_watts", 0)
        self.set_property("daily_usage_kwh", 0.0)
        self.set_property("monthly_usage_kwh", 0.0)
        self.set_property("voltage", 230.0)
        self.set_property("current_amps", 0.0)
        self.set_property("power_factor", 0.95)
        self.set_property("grid_frequency_hz", 50.0)

    def generate_data(self, current_time: datetime) -> dict[str, Any]:
        # Simulate varying power usage
        base_power = 500 + random.uniform(-100, 100)
        hour = current_time.hour
        if 7 <= hour <= 9 or 18 <= hour <= 22:
            base_power *= 2  # Peak hours
        self.set_property("current_power_watts", base_power)
        self.set_property("current_amps", base_power / 230)

        return {
            "current_power_watts": self.get_property("current_power_watts"),
            "daily_usage_kwh": self.get_property("daily_usage_kwh"),
            "monthly_usage_kwh": self.get_property("monthly_usage_kwh"),
            "voltage": self.get_property("voltage") + random.uniform(-2, 2),
            "current_amps": self.get_property("current_amps"),
            "power_factor": self.get_property("power_factor"),
            "grid_frequency_hz": self.get_property("grid_frequency_hz") + random.uniform(-0.1, 0.1),
            "timestamp": current_time.isoformat(),
        }

    def handle_command(self, command: str, params: dict[str, Any]) -> bool:
        # Sensor device - read-only, no commands
        return False


class SmartCircuitBreakerBehavior(HybridDevice):
    """Smart circuit breaker with remote control."""

    def __init__(self, device: Device):
        super().__init__(device, report_interval_seconds=30)
        self.set_property("circuit_on", True)
        self.set_property("current_amps", 0.0)
        self.set_property("max_amps", 20.0)
        self.set_property("tripped", False)
        self.set_property("trip_count", 0)
        self.set_property("power_watts", 0)

    def generate_data(self, current_time: datetime) -> dict[str, Any]:
        if self.get_property("circuit_on") and not self.get_property("tripped"):
            current = random.uniform(1, 15)
            self.set_property("current_amps", current)
            self.set_property("power_watts", current * 230)
        else:
            self.set_property("current_amps", 0)
            self.set_property("power_watts", 0)

        return {
            "circuit_on": self.get_property("circuit_on"),
            "current_amps": self.get_property("current_amps"),
            "max_amps": self.get_property("max_amps"),
            "tripped": self.get_property("tripped"),
            "trip_count": self.get_property("trip_count"),
            "power_watts": self.get_property("power_watts"),
            "timestamp": current_time.isoformat(),
        }

    def handle_command(self, command: str, params: dict[str, Any]) -> bool:
        if command == "turn_on":
            if not self.get_property("tripped"):
                self.set_property("circuit_on", True)
                return True
        elif command == "turn_off":
            self.set_property("circuit_on", False)
            return True
        elif command == "reset":
            self.set_property("tripped", False)
            self.set_property("circuit_on", True)
            return True
        elif command == "set_max_amps":
            amps = params.get("amps", 20)
            self.set_property("max_amps", max(5, min(100, amps)))
            return True
        return False


# =============================================================================
# NETWORK DEVICES (5 types - ROUTER already implemented above)
# =============================================================================


class HubBehavior(HybridDevice):
    """Smart home hub/controller."""

    def __init__(self, device: Device):
        super().__init__(device, report_interval_seconds=30)
        self.set_property("connected_devices", 0)
        self.set_property("protocols_active", ["zigbee", "zwave", "wifi"])
        self.set_property("automations_running", 0)
        self.set_property("cpu_usage_percent", 0)
        self.set_property("memory_usage_percent", 0)
        self.set_property("uptime_hours", 0)

    def generate_data(self, current_time: datetime) -> dict[str, Any]:
        self.set_property("cpu_usage_percent", random.uniform(5, 40))
        self.set_property("memory_usage_percent", random.uniform(20, 60))
        return {
            "is_on": self.device.state.is_on,
            "connected_devices": self.get_property("connected_devices"),
            "protocols_active": self.get_property("protocols_active"),
            "automations_running": self.get_property("automations_running"),
            "cpu_usage_percent": self.get_property("cpu_usage_percent"),
            "memory_usage_percent": self.get_property("memory_usage_percent"),
            "uptime_hours": self.get_property("uptime_hours"),
            "timestamp": current_time.isoformat(),
        }

    def handle_command(self, command: str, params: dict[str, Any]) -> bool:
        if command == "restart":
            self.set_property("uptime_hours", 0)
            return True
        elif command == "enable_protocol":
            protocol = params.get("protocol")
            protocols = self.get_property("protocols_active")
            if protocol and protocol not in protocols:
                protocols.append(protocol)
            return True
        return False


class MeshNodeBehavior(HybridDevice):
    """Mesh network node."""

    def __init__(self, device: Device):
        super().__init__(device, report_interval_seconds=30)
        self.set_property("connected_clients", 0)
        self.set_property("signal_strength_dbm", -50)
        self.set_property("channel", 6)
        self.set_property("backhaul_type", "wireless")
        self.set_property("throughput_mbps", 0)
        self.set_property("parent_node", None)

    def generate_data(self, current_time: datetime) -> dict[str, Any]:
        self.set_property("throughput_mbps", random.uniform(50, 300))
        self.set_property("signal_strength_dbm", random.randint(-70, -40))
        return {
            "is_on": self.device.state.is_on,
            "connected_clients": self.get_property("connected_clients"),
            "signal_strength_dbm": self.get_property("signal_strength_dbm"),
            "channel": self.get_property("channel"),
            "backhaul_type": self.get_property("backhaul_type"),
            "throughput_mbps": self.get_property("throughput_mbps"),
            "parent_node": self.get_property("parent_node"),
            "timestamp": current_time.isoformat(),
        }

    def handle_command(self, command: str, params: dict[str, Any]) -> bool:
        if command == "set_channel":
            self.set_property("channel", params.get("channel", 6))
            return True
        elif command == "set_backhaul":
            backhaul = params.get("type", "wireless")
            if backhaul in ["wireless", "ethernet"]:
                self.set_property("backhaul_type", backhaul)
                return True
        return False


class SmartBridgeBehavior(HybridDevice):
    """Protocol bridge device."""

    def __init__(self, device: Device):
        super().__init__(device, report_interval_seconds=60)
        self.set_property("source_protocol", "zigbee")
        self.set_property("target_protocol", "wifi")
        self.set_property("bridged_devices", 0)
        self.set_property("messages_forwarded", 0)
        self.set_property("status", "active")

    def generate_data(self, current_time: datetime) -> dict[str, Any]:
        self.set_property("messages_forwarded", self.get_property("messages_forwarded") + random.randint(0, 10))
        return {
            "is_on": self.device.state.is_on,
            "source_protocol": self.get_property("source_protocol"),
            "target_protocol": self.get_property("target_protocol"),
            "bridged_devices": self.get_property("bridged_devices"),
            "messages_forwarded": self.get_property("messages_forwarded"),
            "status": self.get_property("status"),
            "timestamp": current_time.isoformat(),
        }

    def handle_command(self, command: str, params: dict[str, Any]) -> bool:
        if command == "reset_stats":
            self.set_property("messages_forwarded", 0)
            return True
        return False


class NetworkSwitchBehavior(HybridDevice):
    """Managed network switch."""

    def __init__(self, device: Device):
        super().__init__(device, report_interval_seconds=30)
        self.set_property("ports_total", 8)
        self.set_property("ports_active", 0)
        self.set_property("poe_enabled", True)
        self.set_property("vlan_enabled", False)
        self.set_property("total_throughput_mbps", 0)
        self.set_property("port_status", {})

    def generate_data(self, current_time: datetime) -> dict[str, Any]:
        self.set_property("total_throughput_mbps", random.uniform(10, 500))
        return {
            "is_on": self.device.state.is_on,
            "ports_total": self.get_property("ports_total"),
            "ports_active": self.get_property("ports_active"),
            "poe_enabled": self.get_property("poe_enabled"),
            "vlan_enabled": self.get_property("vlan_enabled"),
            "total_throughput_mbps": self.get_property("total_throughput_mbps"),
            "timestamp": current_time.isoformat(),
        }

    def handle_command(self, command: str, params: dict[str, Any]) -> bool:
        if command == "enable_poe":
            self.set_property("poe_enabled", True)
            return True
        elif command == "disable_poe":
            self.set_property("poe_enabled", False)
            return True
        elif command == "enable_vlan":
            self.set_property("vlan_enabled", True)
            return True
        return False


class RangeExtenderBehavior(HybridDevice):
    """WiFi range extender."""

    def __init__(self, device: Device):
        super().__init__(device, report_interval_seconds=30)
        self.set_property("connected_clients", 0)
        self.set_property("signal_strength_dbm", -60)
        self.set_property("extended_ssid", "")
        self.set_property("throughput_mbps", 0)
        self.set_property("dual_band", True)

    def generate_data(self, current_time: datetime) -> dict[str, Any]:
        self.set_property("throughput_mbps", random.uniform(20, 150))
        self.set_property("signal_strength_dbm", random.randint(-75, -50))
        return {
            "is_on": self.device.state.is_on,
            "connected_clients": self.get_property("connected_clients"),
            "signal_strength_dbm": self.get_property("signal_strength_dbm"),
            "extended_ssid": self.get_property("extended_ssid"),
            "throughput_mbps": self.get_property("throughput_mbps"),
            "dual_band": self.get_property("dual_band"),
            "timestamp": current_time.isoformat(),
        }

    def handle_command(self, command: str, params: dict[str, Any]) -> bool:
        if command == "set_ssid":
            self.set_property("extended_ssid", params.get("ssid", ""))
            return True
        return False


class NASStorageBehavior(HybridDevice):
    """Network attached storage."""

    def __init__(self, device: Device):
        super().__init__(device, report_interval_seconds=60)
        self.set_property("total_capacity_tb", 4.0)
        self.set_property("used_capacity_tb", 0.0)
        self.set_property("drives_total", 2)
        self.set_property("drives_healthy", 2)
        self.set_property("raid_type", "RAID1")
        self.set_property("temperature_celsius", 35)
        self.set_property("active_connections", 0)

    def generate_data(self, current_time: datetime) -> dict[str, Any]:
        self.set_property("temperature_celsius", random.randint(30, 45))
        return {
            "is_on": self.device.state.is_on,
            "total_capacity_tb": self.get_property("total_capacity_tb"),
            "used_capacity_tb": self.get_property("used_capacity_tb"),
            "used_percent": (self.get_property("used_capacity_tb") / self.get_property("total_capacity_tb")) * 100,
            "drives_total": self.get_property("drives_total"),
            "drives_healthy": self.get_property("drives_healthy"),
            "raid_type": self.get_property("raid_type"),
            "temperature_celsius": self.get_property("temperature_celsius"),
            "active_connections": self.get_property("active_connections"),
            "timestamp": current_time.isoformat(),
        }

    def handle_command(self, command: str, params: dict[str, Any]) -> bool:
        if command == "spin_down":
            return True
        elif command == "start_backup":
            return True
        return False


# =============================================================================
# OUTDOOR DEVICES (8 types)
# =============================================================================


class SmartSprinklerBehavior(HybridDevice):
    """Smart irrigation/sprinkler system."""

    def __init__(self, device: Device):
        super().__init__(device, report_interval_seconds=60)
        self.set_property("zone_count", 6)
        self.set_property("active_zone", None)
        self.set_property("schedule_enabled", True)
        self.set_property("water_flow_gpm", 0)
        self.set_property("total_water_used_gallons", 0)
        self.set_property("rain_delay_active", False)
        self.set_property("soil_moisture_percent", 50)

    def generate_data(self, current_time: datetime) -> dict[str, Any]:
        if self.get_property("active_zone"):
            self.set_property("water_flow_gpm", random.uniform(2, 5))
        else:
            self.set_property("water_flow_gpm", 0)
        return {
            "is_on": self.device.state.is_on,
            "zone_count": self.get_property("zone_count"),
            "active_zone": self.get_property("active_zone"),
            "schedule_enabled": self.get_property("schedule_enabled"),
            "water_flow_gpm": self.get_property("water_flow_gpm"),
            "total_water_used_gallons": self.get_property("total_water_used_gallons"),
            "rain_delay_active": self.get_property("rain_delay_active"),
            "soil_moisture_percent": self.get_property("soil_moisture_percent"),
            "timestamp": current_time.isoformat(),
        }

    def handle_command(self, command: str, params: dict[str, Any]) -> bool:
        if command == "start_zone":
            zone = params.get("zone", 1)
            if 1 <= zone <= self.get_property("zone_count"):
                self.set_property("active_zone", zone)
                return True
        elif command == "stop":
            self.set_property("active_zone", None)
            return True
        elif command == "rain_delay":
            self.set_property("rain_delay_active", True)
            return True
        return False


class PoolControllerBehavior(HybridDevice):
    """Swimming pool controller."""

    def __init__(self, device: Device):
        super().__init__(device, report_interval_seconds=60)
        self.set_property("pump_running", False)
        self.set_property("heater_on", False)
        self.set_property("water_temp_fahrenheit", 78)
        self.set_property("target_temp_fahrenheit", 82)
        self.set_property("ph_level", 7.4)
        self.set_property("chlorine_ppm", 2.0)
        self.set_property("filter_pressure_psi", 12)

    def generate_data(self, current_time: datetime) -> dict[str, Any]:
        self.set_property("ph_level", round(7.2 + random.uniform(-0.3, 0.3), 2))
        self.set_property("chlorine_ppm", round(1.5 + random.uniform(-0.5, 0.5), 2))
        return {
            "pump_running": self.get_property("pump_running"),
            "heater_on": self.get_property("heater_on"),
            "water_temp_fahrenheit": self.get_property("water_temp_fahrenheit"),
            "target_temp_fahrenheit": self.get_property("target_temp_fahrenheit"),
            "ph_level": self.get_property("ph_level"),
            "chlorine_ppm": self.get_property("chlorine_ppm"),
            "filter_pressure_psi": self.get_property("filter_pressure_psi"),
            "timestamp": current_time.isoformat(),
        }

    def handle_command(self, command: str, params: dict[str, Any]) -> bool:
        if command == "pump_on":
            self.set_property("pump_running", True)
            return True
        elif command == "pump_off":
            self.set_property("pump_running", False)
            return True
        elif command == "heater_on":
            self.set_property("heater_on", True)
            return True
        elif command == "heater_off":
            self.set_property("heater_on", False)
            return True
        elif command == "set_temp":
            self.set_property("target_temp_fahrenheit", params.get("temp", 82))
            return True
        return False


class WeatherStationBehavior(SensorDevice):
    """Outdoor weather station."""

    def __init__(self, device: Device):
        super().__init__(device, report_interval_seconds=60)
        self.set_property("temperature_fahrenheit", 72)
        self.set_property("humidity_percent", 50)
        self.set_property("wind_speed_mph", 5)
        self.set_property("wind_direction", "N")
        self.set_property("barometric_pressure_inhg", 30.0)
        self.set_property("rainfall_inches", 0)
        self.set_property("uv_index", 5)

    def generate_data(self, current_time: datetime) -> dict[str, Any]:
        hour = current_time.hour
        base_temp = 65 + 15 * math.sin(math.pi * (hour - 6) / 12)
        self.set_property("temperature_fahrenheit", base_temp + random.uniform(-3, 3))
        self.set_property("humidity_percent", random.randint(40, 80))
        self.set_property("wind_speed_mph", random.uniform(0, 20))
        self.set_property("wind_direction", random.choice(["N", "NE", "E", "SE", "S", "SW", "W", "NW"]))
        return {
            "temperature_fahrenheit": round(self.get_property("temperature_fahrenheit"), 1),
            "humidity_percent": self.get_property("humidity_percent"),
            "wind_speed_mph": round(self.get_property("wind_speed_mph"), 1),
            "wind_direction": self.get_property("wind_direction"),
            "barometric_pressure_inhg": round(self.get_property("barometric_pressure_inhg") + random.uniform(-0.1, 0.1), 2),
            "rainfall_inches": self.get_property("rainfall_inches"),
            "uv_index": random.randint(0, 11) if 6 <= hour <= 18 else 0,
            "timestamp": current_time.isoformat(),
        }

    def handle_command(self, command: str, params: dict[str, Any]) -> bool:
        # Sensor device - read-only, no commands
        return False


class OutdoorLightBehavior(HybridDevice):
    """Outdoor smart light with motion detection."""

    def __init__(self, device: Device):
        super().__init__(device, report_interval_seconds=30)
        self.set_property("brightness", 100)
        self.set_property("motion_detected", False)
        self.set_property("dusk_to_dawn", True)
        self.set_property("color_temp_kelvin", 3000)

    def generate_data(self, current_time: datetime) -> dict[str, Any]:
        return {
            "is_on": self.device.state.is_on,
            "brightness": self.get_property("brightness"),
            "motion_detected": self.get_property("motion_detected"),
            "dusk_to_dawn": self.get_property("dusk_to_dawn"),
            "color_temp_kelvin": self.get_property("color_temp_kelvin"),
            "timestamp": current_time.isoformat(),
        }

    def handle_command(self, command: str, params: dict[str, Any]) -> bool:
        if command == "turn_on":
            self.device.state.is_on = True
            return True
        elif command == "turn_off":
            self.device.state.is_on = False
            return True
        elif command == "set_brightness":
            self.set_property("brightness", max(0, min(100, params.get("brightness", 100))))
            return True
        elif command == "enable_dusk_dawn":
            self.set_property("dusk_to_dawn", True)
            return True
        return False


class GateControllerBehavior(HybridDevice):
    """Smart gate/barrier controller."""

    def __init__(self, device: Device):
        super().__init__(device, report_interval_seconds=30)
        self.set_property("gate_state", "closed")  # open, closed, opening, closing
        self.set_property("obstruction_detected", False)
        self.set_property("auto_close_enabled", True)
        self.set_property("auto_close_delay_seconds", 30)

    def generate_data(self, current_time: datetime) -> dict[str, Any]:
        return {
            "gate_state": self.get_property("gate_state"),
            "obstruction_detected": self.get_property("obstruction_detected"),
            "auto_close_enabled": self.get_property("auto_close_enabled"),
            "auto_close_delay_seconds": self.get_property("auto_close_delay_seconds"),
            "timestamp": current_time.isoformat(),
        }

    def handle_command(self, command: str, params: dict[str, Any]) -> bool:
        if command == "open":
            self.set_property("gate_state", "opening")
            return True
        elif command == "close":
            if not self.get_property("obstruction_detected"):
                self.set_property("gate_state", "closing")
                return True
        elif command == "stop":
            state = self.get_property("gate_state")
            if state in ["opening", "closing"]:
                self.set_property("gate_state", "stopped")
                return True
        return False


class SmartGrillBehavior(HybridDevice):
    """Smart outdoor grill."""

    def __init__(self, device: Device):
        super().__init__(device, report_interval_seconds=30)
        self.set_property("grill_on", False)
        self.set_property("current_temp_fahrenheit", 70)
        self.set_property("target_temp_fahrenheit", 400)
        self.set_property("probe_temp_fahrenheit", 0)
        self.set_property("fuel_level_percent", 100)
        self.set_property("lid_open", True)

    def generate_data(self, current_time: datetime) -> dict[str, Any]:
        return {
            "grill_on": self.get_property("grill_on"),
            "current_temp_fahrenheit": self.get_property("current_temp_fahrenheit"),
            "target_temp_fahrenheit": self.get_property("target_temp_fahrenheit"),
            "probe_temp_fahrenheit": self.get_property("probe_temp_fahrenheit"),
            "fuel_level_percent": self.get_property("fuel_level_percent"),
            "lid_open": self.get_property("lid_open"),
            "timestamp": current_time.isoformat(),
        }

    def handle_command(self, command: str, params: dict[str, Any]) -> bool:
        if command == "ignite":
            self.set_property("grill_on", True)
            return True
        elif command == "turn_off":
            self.set_property("grill_on", False)
            return True
        elif command == "set_temp":
            self.set_property("target_temp_fahrenheit", params.get("temp", 400))
            return True
        return False

    def update(self, current_time: datetime, delta_seconds: float) -> list:
        events = super().update(current_time, delta_seconds)
        if self.get_property("grill_on"):
            current = self.get_property("current_temp_fahrenheit")
            target = self.get_property("target_temp_fahrenheit")
            if current < target:
                self.set_property("current_temp_fahrenheit", min(target, current + 10))
        else:
            current = self.get_property("current_temp_fahrenheit")
            if current > 70:
                self.set_property("current_temp_fahrenheit", max(70, current - 5))
        return events


class GardenSensorBehavior(SensorDevice):
    """Garden/plant monitoring sensor."""

    def __init__(self, device: Device):
        super().__init__(device, report_interval_seconds=300)
        self.set_property("soil_moisture_percent", 50)
        self.set_property("soil_temperature_fahrenheit", 65)
        self.set_property("light_intensity_lux", 5000)
        self.set_property("soil_ph", 6.5)
        self.set_property("soil_fertility", "normal")

    def generate_data(self, current_time: datetime) -> dict[str, Any]:
        hour = current_time.hour
        light = 10000 * math.sin(math.pi * max(0, hour - 6) / 12) if 6 <= hour <= 18 else 0
        self.set_property("light_intensity_lux", max(0, light + random.uniform(-500, 500)))
        self.set_property("soil_moisture_percent", max(0, min(100, self.get_property("soil_moisture_percent") + random.uniform(-2, 1))))
        return {
            "soil_moisture_percent": round(self.get_property("soil_moisture_percent"), 1),
            "soil_temperature_fahrenheit": round(self.get_property("soil_temperature_fahrenheit") + random.uniform(-2, 2), 1),
            "light_intensity_lux": round(self.get_property("light_intensity_lux")),
            "soil_ph": round(self.get_property("soil_ph") + random.uniform(-0.1, 0.1), 2),
            "soil_fertility": self.get_property("soil_fertility"),
            "timestamp": current_time.isoformat(),
        }

    def handle_command(self, command: str, params: dict[str, Any]) -> bool:
        # Sensor device - read-only, no commands
        return False


class PestRepellerBehavior(HybridDevice):
    """Ultrasonic pest repeller."""

    def __init__(self, device: Device):
        super().__init__(device, report_interval_seconds=60)
        self.set_property("mode", "auto")  # auto, continuous, scheduled
        self.set_property("frequency_khz", 25)
        self.set_property("coverage_sqft", 1200)
        self.set_property("pest_activity_detected", False)

    def generate_data(self, current_time: datetime) -> dict[str, Any]:
        self.set_property("pest_activity_detected", random.random() < 0.1)
        return {
            "is_on": self.device.state.is_on,
            "mode": self.get_property("mode"),
            "frequency_khz": self.get_property("frequency_khz"),
            "coverage_sqft": self.get_property("coverage_sqft"),
            "pest_activity_detected": self.get_property("pest_activity_detected"),
            "timestamp": current_time.isoformat(),
        }

    def handle_command(self, command: str, params: dict[str, Any]) -> bool:
        if command == "turn_on":
            self.device.state.is_on = True
            return True
        elif command == "turn_off":
            self.device.state.is_on = False
            return True
        elif command == "set_mode":
            mode = params.get("mode", "auto")
            if mode in ["auto", "continuous", "scheduled"]:
                self.set_property("mode", mode)
                return True
        return False


# =============================================================================
# CLEANING DEVICES (4 types)
# =============================================================================


class RobotVacuumBehavior(HybridDevice):
    """Robot vacuum cleaner."""

    def __init__(self, device: Device):
        super().__init__(device, report_interval_seconds=30)
        self.set_property("state", "docked")  # docked, cleaning, returning, paused, error
        self.set_property("battery_percent", 100)
        self.set_property("cleaning_mode", "auto")  # auto, spot, edge, turbo
        self.set_property("dustbin_full", False)
        self.set_property("area_cleaned_sqm", 0)
        self.set_property("cleaning_time_minutes", 0)
        self.set_property("error_code", None)

    def generate_data(self, current_time: datetime) -> dict[str, Any]:
        return {
            "state": self.get_property("state"),
            "battery_percent": self.get_property("battery_percent"),
            "cleaning_mode": self.get_property("cleaning_mode"),
            "dustbin_full": self.get_property("dustbin_full"),
            "area_cleaned_sqm": self.get_property("area_cleaned_sqm"),
            "cleaning_time_minutes": self.get_property("cleaning_time_minutes"),
            "error_code": self.get_property("error_code"),
            "timestamp": current_time.isoformat(),
        }

    def handle_command(self, command: str, params: dict[str, Any]) -> bool:
        if command == "start":
            if self.get_property("battery_percent") > 20:
                self.set_property("state", "cleaning")
                return True
        elif command == "pause":
            self.set_property("state", "paused")
            return True
        elif command == "dock":
            self.set_property("state", "returning")
            return True
        elif command == "set_mode":
            mode = params.get("mode", "auto")
            if mode in ["auto", "spot", "edge", "turbo"]:
                self.set_property("cleaning_mode", mode)
                return True
        return False

    def update(self, current_time: datetime, delta_seconds: float) -> list:
        events = super().update(current_time, delta_seconds)
        state = self.get_property("state")
        if state == "cleaning":
            battery = self.get_property("battery_percent")
            self.set_property("battery_percent", max(0, battery - 0.5))
            self.set_property("area_cleaned_sqm", self.get_property("area_cleaned_sqm") + 0.1)
            if battery <= 20:
                self.set_property("state", "returning")
        elif state == "docked":
            battery = self.get_property("battery_percent")
            self.set_property("battery_percent", min(100, battery + 1))
        return events


class RobotMopBehavior(HybridDevice):
    """Robot mop cleaner."""

    def __init__(self, device: Device):
        super().__init__(device, report_interval_seconds=30)
        self.set_property("state", "docked")
        self.set_property("battery_percent", 100)
        self.set_property("water_tank_percent", 100)
        self.set_property("mopping_mode", "standard")  # standard, deep, quick
        self.set_property("area_cleaned_sqm", 0)

    def generate_data(self, current_time: datetime) -> dict[str, Any]:
        return {
            "state": self.get_property("state"),
            "battery_percent": self.get_property("battery_percent"),
            "water_tank_percent": self.get_property("water_tank_percent"),
            "mopping_mode": self.get_property("mopping_mode"),
            "area_cleaned_sqm": self.get_property("area_cleaned_sqm"),
            "timestamp": current_time.isoformat(),
        }

    def handle_command(self, command: str, params: dict[str, Any]) -> bool:
        if command == "start":
            if self.get_property("battery_percent") > 20 and self.get_property("water_tank_percent") > 10:
                self.set_property("state", "mopping")
                return True
        elif command == "dock":
            self.set_property("state", "returning")
            return True
        elif command == "set_mode":
            mode = params.get("mode", "standard")
            if mode in ["standard", "deep", "quick"]:
                self.set_property("mopping_mode", mode)
                return True
        return False


class WindowCleanerBehavior(HybridDevice):
    """Robot window cleaner."""

    def __init__(self, device: Device):
        super().__init__(device, report_interval_seconds=30)
        self.set_property("state", "idle")  # idle, cleaning, paused
        self.set_property("battery_percent", 100)
        self.set_property("suction_strength", "high")
        self.set_property("cleaning_path", "auto")
        self.set_property("safety_rope_connected", True)

    def generate_data(self, current_time: datetime) -> dict[str, Any]:
        return {
            "state": self.get_property("state"),
            "battery_percent": self.get_property("battery_percent"),
            "suction_strength": self.get_property("suction_strength"),
            "cleaning_path": self.get_property("cleaning_path"),
            "safety_rope_connected": self.get_property("safety_rope_connected"),
            "timestamp": current_time.isoformat(),
        }

    def handle_command(self, command: str, params: dict[str, Any]) -> bool:
        if command == "start":
            if self.get_property("safety_rope_connected"):
                self.set_property("state", "cleaning")
                return True
        elif command == "stop":
            self.set_property("state", "idle")
            return True
        return False


class PoolCleanerBehavior(HybridDevice):
    """Robot pool cleaner."""

    def __init__(self, device: Device):
        super().__init__(device, report_interval_seconds=60)
        self.set_property("state", "idle")  # idle, cleaning, finished
        self.set_property("battery_percent", 100)
        self.set_property("cleaning_cycle", "full")  # full, floor, walls
        self.set_property("filter_status", "clean")
        self.set_property("run_time_hours", 0)

    def generate_data(self, current_time: datetime) -> dict[str, Any]:
        return {
            "state": self.get_property("state"),
            "battery_percent": self.get_property("battery_percent"),
            "cleaning_cycle": self.get_property("cleaning_cycle"),
            "filter_status": self.get_property("filter_status"),
            "run_time_hours": self.get_property("run_time_hours"),
            "timestamp": current_time.isoformat(),
        }

    def handle_command(self, command: str, params: dict[str, Any]) -> bool:
        if command == "start":
            self.set_property("state", "cleaning")
            return True
        elif command == "stop":
            self.set_property("state", "idle")
            return True
        elif command == "set_cycle":
            cycle = params.get("cycle", "full")
            if cycle in ["full", "floor", "walls"]:
                self.set_property("cleaning_cycle", cycle)
                return True
        return False


# =============================================================================
# BABY & PET DEVICES (6 types)
# =============================================================================


class BabyMonitorBehavior(HybridDevice):
    """Smart baby monitor with audio/video."""

    def __init__(self, device: Device):
        super().__init__(device, report_interval_seconds=10)
        self.set_property("video_on", True)
        self.set_property("audio_on", True)
        self.set_property("night_vision", True)
        self.set_property("sound_level_db", 30)
        self.set_property("motion_detected", False)
        self.set_property("temperature_fahrenheit", 72)
        self.set_property("humidity_percent", 45)

    def generate_data(self, current_time: datetime) -> dict[str, Any]:
        self.set_property("sound_level_db", random.randint(20, 60))
        self.set_property("motion_detected", random.random() < 0.1)
        return {
            "is_on": self.device.state.is_on,
            "video_on": self.get_property("video_on"),
            "audio_on": self.get_property("audio_on"),
            "night_vision": self.get_property("night_vision"),
            "sound_level_db": self.get_property("sound_level_db"),
            "motion_detected": self.get_property("motion_detected"),
            "temperature_fahrenheit": self.get_property("temperature_fahrenheit") + random.uniform(-1, 1),
            "humidity_percent": self.get_property("humidity_percent") + random.uniform(-2, 2),
            "timestamp": current_time.isoformat(),
        }

    def handle_command(self, command: str, params: dict[str, Any]) -> bool:
        if command == "turn_on":
            self.device.state.is_on = True
            return True
        elif command == "turn_off":
            self.device.state.is_on = False
            return True
        elif command == "toggle_night_vision":
            self.set_property("night_vision", not self.get_property("night_vision"))
            return True
        return False


class SmartCribBehavior(HybridDevice):
    """Smart baby crib with motion/sound."""

    def __init__(self, device: Device):
        super().__init__(device, report_interval_seconds=30)
        self.set_property("rocking_on", False)
        self.set_property("rocking_speed", "gentle")  # gentle, medium, strong
        self.set_property("white_noise_on", False)
        self.set_property("white_noise_type", "shush")
        self.set_property("night_light_on", False)
        self.set_property("baby_awake", False)

    def generate_data(self, current_time: datetime) -> dict[str, Any]:
        return {
            "is_on": self.device.state.is_on,
            "rocking_on": self.get_property("rocking_on"),
            "rocking_speed": self.get_property("rocking_speed"),
            "white_noise_on": self.get_property("white_noise_on"),
            "white_noise_type": self.get_property("white_noise_type"),
            "night_light_on": self.get_property("night_light_on"),
            "baby_awake": self.get_property("baby_awake"),
            "timestamp": current_time.isoformat(),
        }

    def handle_command(self, command: str, params: dict[str, Any]) -> bool:
        if command == "start_rocking":
            self.set_property("rocking_on", True)
            return True
        elif command == "stop_rocking":
            self.set_property("rocking_on", False)
            return True
        elif command == "set_rocking_speed":
            speed = params.get("speed", "gentle")
            if speed in ["gentle", "medium", "strong"]:
                self.set_property("rocking_speed", speed)
                return True
        elif command == "toggle_white_noise":
            self.set_property("white_noise_on", not self.get_property("white_noise_on"))
            return True
        return False


class PetFeederBehavior(HybridDevice):
    """Automatic pet feeder."""

    def __init__(self, device: Device):
        super().__init__(device, report_interval_seconds=60)
        self.set_property("food_level_percent", 80)
        self.set_property("portion_size_cups", 0.5)
        self.set_property("feedings_today", 0)
        self.set_property("next_feeding_time", None)
        self.set_property("schedule_enabled", True)
        self.set_property("low_food_alert", False)

    def generate_data(self, current_time: datetime) -> dict[str, Any]:
        food_level = self.get_property("food_level_percent")
        self.set_property("low_food_alert", food_level < 20)
        return {
            "food_level_percent": food_level,
            "portion_size_cups": self.get_property("portion_size_cups"),
            "feedings_today": self.get_property("feedings_today"),
            "next_feeding_time": self.get_property("next_feeding_time"),
            "schedule_enabled": self.get_property("schedule_enabled"),
            "low_food_alert": self.get_property("low_food_alert"),
            "timestamp": current_time.isoformat(),
        }

    def handle_command(self, command: str, params: dict[str, Any]) -> bool:
        if command == "dispense":
            portion = params.get("portion", self.get_property("portion_size_cups"))
            food_level = self.get_property("food_level_percent")
            if food_level > 5:
                self.set_property("food_level_percent", max(0, food_level - 5))
                self.set_property("feedings_today", self.get_property("feedings_today") + 1)
                return True
        elif command == "set_portion":
            self.set_property("portion_size_cups", params.get("cups", 0.5))
            return True
        return False


class PetCameraBehavior(HybridDevice):
    """Pet monitoring camera with treat dispenser."""

    def __init__(self, device: Device):
        super().__init__(device, report_interval_seconds=30)
        self.set_property("video_on", True)
        self.set_property("two_way_audio", True)
        self.set_property("motion_detected", False)
        self.set_property("bark_detected", False)
        self.set_property("treat_count", 20)
        self.set_property("laser_pointer_on", False)

    def generate_data(self, current_time: datetime) -> dict[str, Any]:
        self.set_property("motion_detected", random.random() < 0.2)
        self.set_property("bark_detected", random.random() < 0.05)
        return {
            "is_on": self.device.state.is_on,
            "video_on": self.get_property("video_on"),
            "two_way_audio": self.get_property("two_way_audio"),
            "motion_detected": self.get_property("motion_detected"),
            "bark_detected": self.get_property("bark_detected"),
            "treat_count": self.get_property("treat_count"),
            "laser_pointer_on": self.get_property("laser_pointer_on"),
            "timestamp": current_time.isoformat(),
        }

    def handle_command(self, command: str, params: dict[str, Any]) -> bool:
        if command == "dispense_treat":
            treats = self.get_property("treat_count")
            if treats > 0:
                self.set_property("treat_count", treats - 1)
                return True
        elif command == "toggle_laser":
            self.set_property("laser_pointer_on", not self.get_property("laser_pointer_on"))
            return True
        elif command == "speak":
            return True  # Two-way audio activated
        return False


class PetDoorBehavior(HybridDevice):
    """Smart pet door with access control."""

    def __init__(self, device: Device):
        super().__init__(device, report_interval_seconds=30)
        self.set_property("lock_state", "auto")  # locked, unlocked, auto
        self.set_property("door_state", "closed")  # open, closed
        self.set_property("last_pet_entry", None)
        self.set_property("last_pet_exit", None)
        self.set_property("entries_today", 0)
        self.set_property("exits_today", 0)
        self.set_property("curfew_enabled", False)

    def generate_data(self, current_time: datetime) -> dict[str, Any]:
        return {
            "lock_state": self.get_property("lock_state"),
            "door_state": self.get_property("door_state"),
            "last_pet_entry": self.get_property("last_pet_entry"),
            "last_pet_exit": self.get_property("last_pet_exit"),
            "entries_today": self.get_property("entries_today"),
            "exits_today": self.get_property("exits_today"),
            "curfew_enabled": self.get_property("curfew_enabled"),
            "timestamp": current_time.isoformat(),
        }

    def handle_command(self, command: str, params: dict[str, Any]) -> bool:
        if command == "lock":
            self.set_property("lock_state", "locked")
            return True
        elif command == "unlock":
            self.set_property("lock_state", "unlocked")
            return True
        elif command == "set_auto":
            self.set_property("lock_state", "auto")
            return True
        elif command == "enable_curfew":
            self.set_property("curfew_enabled", True)
            return True
        return False


class PetTrackerBehavior(SensorDevice):
    """GPS pet tracker collar."""

    def __init__(self, device: Device):
        super().__init__(device, report_interval_seconds=60)
        self.set_property("battery_percent", 100)
        self.set_property("latitude", 0.0)
        self.set_property("longitude", 0.0)
        self.set_property("in_safe_zone", True)
        self.set_property("activity_level", "resting")  # resting, walking, running
        self.set_property("last_location_update", None)

    def generate_data(self, current_time: datetime) -> dict[str, Any]:
        self.set_property("battery_percent", max(0, self.get_property("battery_percent") - 0.1))
        self.set_property("activity_level", random.choice(["resting", "walking", "running"]))
        self.set_property("last_location_update", current_time.isoformat())
        return {
            "battery_percent": round(self.get_property("battery_percent"), 1),
            "latitude": self.get_property("latitude") + random.uniform(-0.0001, 0.0001),
            "longitude": self.get_property("longitude") + random.uniform(-0.0001, 0.0001),
            "in_safe_zone": self.get_property("in_safe_zone"),
            "activity_level": self.get_property("activity_level"),
            "last_location_update": self.get_property("last_location_update"),
            "timestamp": current_time.isoformat(),
        }

    def handle_command(self, command: str, params: dict[str, Any]) -> bool:
        # Sensor device - read-only, no commands
        return False


# =============================================================================
# ACCESSIBILITY DEVICES (4 types)
# =============================================================================


class VoiceAssistantHubBehavior(HybridDevice):
    """Central voice assistant hub (Alexa/Google Home style)."""

    def __init__(self, device: Device):
        super().__init__(device, report_interval_seconds=30)
        self.set_property("listening", False)
        self.set_property("connected_devices", 0)
        self.set_property("last_command", None)
        self.set_property("volume", 50)
        self.set_property("muted", False)
        self.set_property("skills_active", 0)
        self.set_property("voice_profile", "default")

    def generate_data(self, current_time: datetime) -> dict[str, Any]:
        return {
            "is_on": self.device.state.is_on,
            "listening": self.get_property("listening"),
            "connected_devices": self.get_property("connected_devices"),
            "last_command": self.get_property("last_command"),
            "volume": self.get_property("volume"),
            "muted": self.get_property("muted"),
            "skills_active": self.get_property("skills_active"),
            "timestamp": current_time.isoformat(),
        }

    def handle_command(self, command: str, params: dict[str, Any]) -> bool:
        if command == "set_volume":
            self.set_property("volume", max(0, min(100, params.get("volume", 50))))
            return True
        elif command == "mute":
            self.set_property("muted", True)
            return True
        elif command == "unmute":
            self.set_property("muted", False)
            return True
        elif command == "voice_command":
            self.set_property("last_command", params.get("text"))
            return True
        return False


class AutomatedDoorBehavior(HybridDevice):
    """Automated door opener for accessibility."""

    def __init__(self, device: Device):
        super().__init__(device, report_interval_seconds=30)
        self.set_property("door_state", "closed")  # open, closed, opening, closing
        self.set_property("auto_close_enabled", True)
        self.set_property("auto_close_delay_seconds", 10)
        self.set_property("hold_open", False)
        self.set_property("sensor_active", True)
        self.set_property("push_button_enabled", True)

    def generate_data(self, current_time: datetime) -> dict[str, Any]:
        return {
            "door_state": self.get_property("door_state"),
            "auto_close_enabled": self.get_property("auto_close_enabled"),
            "auto_close_delay_seconds": self.get_property("auto_close_delay_seconds"),
            "hold_open": self.get_property("hold_open"),
            "sensor_active": self.get_property("sensor_active"),
            "push_button_enabled": self.get_property("push_button_enabled"),
            "timestamp": current_time.isoformat(),
        }

    def handle_command(self, command: str, params: dict[str, Any]) -> bool:
        if command == "open":
            self.set_property("door_state", "opening")
            return True
        elif command == "close":
            self.set_property("door_state", "closing")
            return True
        elif command == "hold_open":
            self.set_property("hold_open", True)
            self.set_property("door_state", "open")
            return True
        elif command == "release_hold":
            self.set_property("hold_open", False)
            return True
        return False


class EmergencyAlertBehavior(HybridDevice):
    """Emergency alert/PERS device."""

    def __init__(self, device: Device):
        super().__init__(device, report_interval_seconds=60)
        self.set_property("alert_active", False)
        self.set_property("battery_percent", 100)
        self.set_property("last_test", None)
        self.set_property("fall_detection_enabled", True)
        self.set_property("gps_enabled", True)
        self.set_property("location_lat", 0.0)
        self.set_property("location_lon", 0.0)

    def generate_data(self, current_time: datetime) -> dict[str, Any]:
        self.set_property("battery_percent", max(0, self.get_property("battery_percent") - 0.05))
        return {
            "alert_active": self.get_property("alert_active"),
            "battery_percent": round(self.get_property("battery_percent"), 1),
            "last_test": self.get_property("last_test"),
            "fall_detection_enabled": self.get_property("fall_detection_enabled"),
            "gps_enabled": self.get_property("gps_enabled"),
            "location_lat": self.get_property("location_lat"),
            "location_lon": self.get_property("location_lon"),
            "timestamp": current_time.isoformat(),
        }

    def handle_command(self, command: str, params: dict[str, Any]) -> bool:
        if command == "trigger_alert":
            self.set_property("alert_active", True)
            return True
        elif command == "cancel_alert":
            self.set_property("alert_active", False)
            return True
        elif command == "test":
            self.set_property("last_test", params.get("timestamp"))
            return True
        return False


class HearingLoopBehavior(HybridDevice):
    """Hearing loop/induction loop system."""

    def __init__(self, device: Device):
        super().__init__(device, report_interval_seconds=60)
        self.set_property("loop_active", False)
        self.set_property("volume_db", 0)
        self.set_property("coverage_sqm", 50)
        self.set_property("signal_strength", "normal")
        self.set_property("audio_source", "none")  # none, tv, microphone, aux

    def generate_data(self, current_time: datetime) -> dict[str, Any]:
        return {
            "is_on": self.device.state.is_on,
            "loop_active": self.get_property("loop_active"),
            "volume_db": self.get_property("volume_db"),
            "coverage_sqm": self.get_property("coverage_sqm"),
            "signal_strength": self.get_property("signal_strength"),
            "audio_source": self.get_property("audio_source"),
            "timestamp": current_time.isoformat(),
        }

    def handle_command(self, command: str, params: dict[str, Any]) -> bool:
        if command == "turn_on":
            self.device.state.is_on = True
            self.set_property("loop_active", True)
            return True
        elif command == "turn_off":
            self.device.state.is_on = False
            self.set_property("loop_active", False)
            return True
        elif command == "set_volume":
            self.set_property("volume_db", max(-20, min(20, params.get("db", 0))))
            return True
        elif command == "set_source":
            source = params.get("source", "none")
            if source in ["none", "tv", "microphone", "aux"]:
                self.set_property("audio_source", source)
                return True
        return False
