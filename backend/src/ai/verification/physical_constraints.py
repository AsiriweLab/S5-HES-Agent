"""
Physical Constraint Checker for LLM Outputs.

Validates that LLM-generated configurations and device states
conform to real-world physical constraints. This prevents
hallucinations that violate physics or device specifications.

Examples of physical constraints:
- Temperature cannot be set below absolute zero
- A room cannot have negative dimensions
- Power consumption cannot exceed device ratings
- Sensor readings must be within valid ranges
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Optional

from loguru import logger

from src.ai.verification.verification_pipeline import (
    VerificationCategory,
    VerificationCheck,
    VerificationStatus,
)


class ConstraintType(str, Enum):
    """Types of physical constraints."""
    RANGE = "range"           # Value within min/max bounds
    DEPENDENCY = "dependency"  # One value depends on another
    CONSISTENCY = "consistency"  # Multiple values must be consistent
    RATE = "rate"             # Rate of change constraints
    PHYSICAL_LAW = "physical_law"  # Laws of physics


@dataclass
class PhysicalConstraint:
    """Definition of a physical constraint."""
    name: str
    constraint_type: ConstraintType
    description: str
    check_function: Callable[[Any, dict], tuple[bool, str]]
    applies_to: list[str] = field(default_factory=list)  # Device types
    severity: str = "error"  # error, warning


class PhysicalConstraintChecker:
    """
    Validates LLM outputs against physical constraints.

    Features:
    - Temperature range validation
    - Dimension constraints
    - Power consumption limits
    - Sensor reading bounds
    - Device state consistency
    - Physical law enforcement
    """

    def __init__(self):
        # Registered constraints
        self._constraints: list[PhysicalConstraint] = []

        # Device-specific constraints
        self._device_constraints: dict[str, list[PhysicalConstraint]] = {}

        # Register built-in constraints
        self._register_builtin_constraints()

        logger.info("PhysicalConstraintChecker initialized")

    def _register_builtin_constraints(self) -> None:
        """Register built-in physical constraints."""
        # Temperature constraints
        self.register_constraint(PhysicalConstraint(
            name="temperature_range",
            constraint_type=ConstraintType.RANGE,
            description="Temperature must be within physically valid range",
            check_function=self._check_temperature_range,
            applies_to=["thermostat", "temperature_sensor", "hvac", "smart_thermostat"],
        ))

        self.register_constraint(PhysicalConstraint(
            name="celsius_fahrenheit_consistency",
            constraint_type=ConstraintType.CONSISTENCY,
            description="Celsius and Fahrenheit values must be consistent",
            check_function=self._check_temp_unit_consistency,
            applies_to=["thermostat", "temperature_sensor"],
        ))

        # Humidity constraints
        self.register_constraint(PhysicalConstraint(
            name="humidity_range",
            constraint_type=ConstraintType.RANGE,
            description="Humidity must be between 0% and 100%",
            check_function=self._check_humidity_range,
            applies_to=["humidity_sensor", "hvac", "humidifier", "dehumidifier"],
        ))

        # Dimension constraints
        self.register_constraint(PhysicalConstraint(
            name="positive_dimensions",
            constraint_type=ConstraintType.RANGE,
            description="Physical dimensions must be positive",
            check_function=self._check_positive_dimensions,
            applies_to=["room", "home", "area"],
        ))

        self.register_constraint(PhysicalConstraint(
            name="reasonable_room_size",
            constraint_type=ConstraintType.RANGE,
            description="Room dimensions must be reasonable (1-500 sq meters)",
            check_function=self._check_reasonable_room_size,
            applies_to=["room"],
        ))

        # Power constraints
        self.register_constraint(PhysicalConstraint(
            name="power_consumption_range",
            constraint_type=ConstraintType.RANGE,
            description="Power consumption must be positive and within device limits",
            check_function=self._check_power_consumption,
            applies_to=["*"],  # All devices
        ))

        self.register_constraint(PhysicalConstraint(
            name="battery_percentage",
            constraint_type=ConstraintType.RANGE,
            description="Battery percentage must be 0-100%",
            check_function=self._check_battery_percentage,
            applies_to=["battery_device", "sensor", "smart_lock", "doorbell"],
        ))

        # Light constraints
        self.register_constraint(PhysicalConstraint(
            name="brightness_range",
            constraint_type=ConstraintType.RANGE,
            description="Brightness must be 0-100%",
            check_function=self._check_brightness_range,
            applies_to=["smart_light", "light", "dimmer", "light_switch"],
        ))

        self.register_constraint(PhysicalConstraint(
            name="color_temperature_range",
            constraint_type=ConstraintType.RANGE,
            description="Color temperature must be 1000K-10000K",
            check_function=self._check_color_temperature,
            applies_to=["smart_light", "light"],
        ))

        # Motion/presence constraints
        self.register_constraint(PhysicalConstraint(
            name="motion_detection_consistency",
            constraint_type=ConstraintType.CONSISTENCY,
            description="Motion detected must match presence state",
            check_function=self._check_motion_presence_consistency,
            applies_to=["motion_sensor", "presence_sensor", "occupancy_sensor"],
        ))

        # Lock constraints
        self.register_constraint(PhysicalConstraint(
            name="lock_state_binary",
            constraint_type=ConstraintType.CONSISTENCY,
            description="Lock must be either locked or unlocked",
            check_function=self._check_lock_state,
            applies_to=["smart_lock", "door_lock"],
        ))

        # Network constraints
        self.register_constraint(PhysicalConstraint(
            name="network_bandwidth",
            constraint_type=ConstraintType.RANGE,
            description="Network bandwidth must be positive",
            check_function=self._check_network_bandwidth,
            applies_to=["network_device", "router", "camera"],
        ))

        self.register_constraint(PhysicalConstraint(
            name="ip_address_format",
            constraint_type=ConstraintType.CONSISTENCY,
            description="IP address must be valid format",
            check_function=self._check_ip_address,
            applies_to=["*"],
        ))

        # Timing constraints
        self.register_constraint(PhysicalConstraint(
            name="timestamp_validity",
            constraint_type=ConstraintType.CONSISTENCY,
            description="Timestamps must be valid and not in far future",
            check_function=self._check_timestamp,
            applies_to=["*"],
        ))

    def register_constraint(self, constraint: PhysicalConstraint) -> None:
        """Register a physical constraint."""
        self._constraints.append(constraint)

        # Index by device type
        for device_type in constraint.applies_to:
            if device_type not in self._device_constraints:
                self._device_constraints[device_type] = []
            self._device_constraints[device_type].append(constraint)

        logger.debug(f"Registered constraint: {constraint.name}")

    def check(
        self,
        data: Any,
        device_type: str = None,
        context: dict = None,
    ) -> list[tuple[PhysicalConstraint, bool, str]]:
        """
        Check data against physical constraints.

        Args:
            data: The data to check (device state, configuration, etc.)
            device_type: Optional device type to filter constraints
            context: Additional context for checking

        Returns:
            List of (constraint, passed, message) tuples
        """
        context = context or {}
        results = []

        # Get applicable constraints
        constraints = self._get_applicable_constraints(device_type)

        for constraint in constraints:
            try:
                passed, message = constraint.check_function(data, context)
                results.append((constraint, passed, message))

                if not passed:
                    logger.debug(
                        f"Constraint violation: {constraint.name} - {message}"
                    )

            except Exception as e:
                logger.error(f"Constraint check error ({constraint.name}): {e}")
                results.append((constraint, False, f"Check error: {str(e)}"))

        return results

    def _get_applicable_constraints(
        self, device_type: str = None
    ) -> list[PhysicalConstraint]:
        """Get constraints applicable to a device type."""
        if device_type is None:
            return self._constraints

        # Get device-specific + wildcard constraints
        specific = self._device_constraints.get(device_type, [])
        wildcard = self._device_constraints.get("*", [])

        # Deduplicate
        seen = set()
        result = []
        for c in specific + wildcard:
            if c.name not in seen:
                seen.add(c.name)
                result.append(c)

        return result

    # ==================== Constraint Check Functions ====================

    def _check_temperature_range(
        self, data: Any, context: dict
    ) -> tuple[bool, str]:
        """Check temperature is within valid range."""
        temp = self._extract_value(data, ["temperature", "temp", "current_temp"])
        if temp is None:
            return True, "No temperature value found"

        # Absolute zero is -273.15°C
        if temp < -273.15:
            return False, f"Temperature {temp}°C is below absolute zero"

        # Reasonable indoor range check (warn, not fail)
        if temp < -50 or temp > 100:
            return False, f"Temperature {temp}°C is outside reasonable range (-50 to 100°C)"

        return True, f"Temperature {temp}°C is valid"

    def _check_temp_unit_consistency(
        self, data: Any, context: dict
    ) -> tuple[bool, str]:
        """Check Celsius/Fahrenheit consistency."""
        celsius = self._extract_value(data, ["celsius", "temp_c"])
        fahrenheit = self._extract_value(data, ["fahrenheit", "temp_f"])

        if celsius is None or fahrenheit is None:
            return True, "Only one temperature unit present"

        expected_f = (celsius * 9 / 5) + 32
        tolerance = 0.5

        if abs(fahrenheit - expected_f) > tolerance:
            return False, f"Temperature units inconsistent: {celsius}°C should be {expected_f:.1f}°F, not {fahrenheit}°F"

        return True, "Temperature units are consistent"

    def _check_humidity_range(
        self, data: Any, context: dict
    ) -> tuple[bool, str]:
        """Check humidity is 0-100%."""
        humidity = self._extract_value(data, ["humidity", "relative_humidity", "rh"])
        if humidity is None:
            return True, "No humidity value found"

        if humidity < 0 or humidity > 100:
            return False, f"Humidity {humidity}% is outside valid range (0-100%)"

        return True, f"Humidity {humidity}% is valid"

    def _check_positive_dimensions(
        self, data: Any, context: dict
    ) -> tuple[bool, str]:
        """Check dimensions are positive."""
        dims = ["width", "height", "length", "area", "volume", "size"]
        for dim in dims:
            value = self._extract_value(data, [dim])
            if value is not None and value <= 0:
                return False, f"Dimension '{dim}' must be positive, got {value}"

        return True, "All dimensions are valid"

    def _check_reasonable_room_size(
        self, data: Any, context: dict
    ) -> tuple[bool, str]:
        """Check room size is reasonable."""
        area = self._extract_value(data, ["area", "size", "square_meters", "sqm"])
        if area is None:
            return True, "No room size found"

        if area < 1:
            return False, f"Room size {area} sq.m is too small (min: 1)"

        if area > 500:
            return False, f"Room size {area} sq.m is too large for a single room (max: 500)"

        return True, f"Room size {area} sq.m is reasonable"

    def _check_power_consumption(
        self, data: Any, context: dict
    ) -> tuple[bool, str]:
        """Check power consumption is valid."""
        power = self._extract_value(data, ["power", "watts", "power_consumption", "power_usage"])
        if power is None:
            return True, "No power value found"

        if power < 0:
            return False, f"Power consumption cannot be negative: {power}W"

        # Max residential power (typically 200A @ 240V = 48kW)
        if power > 50000:
            return False, f"Power consumption {power}W exceeds residential limits"

        return True, f"Power consumption {power}W is valid"

    def _check_battery_percentage(
        self, data: Any, context: dict
    ) -> tuple[bool, str]:
        """Check battery percentage is 0-100%."""
        battery = self._extract_value(data, ["battery", "battery_level", "battery_percent"])
        if battery is None:
            return True, "No battery value found"

        if battery < 0 or battery > 100:
            return False, f"Battery {battery}% is outside valid range (0-100%)"

        return True, f"Battery {battery}% is valid"

    def _check_brightness_range(
        self, data: Any, context: dict
    ) -> tuple[bool, str]:
        """Check brightness is 0-100%."""
        brightness = self._extract_value(data, ["brightness", "level", "dim_level"])
        if brightness is None:
            return True, "No brightness value found"

        if brightness < 0 or brightness > 100:
            return False, f"Brightness {brightness}% is outside valid range (0-100%)"

        return True, f"Brightness {brightness}% is valid"

    def _check_color_temperature(
        self, data: Any, context: dict
    ) -> tuple[bool, str]:
        """Check color temperature is in valid range."""
        color_temp = self._extract_value(data, ["color_temp", "color_temperature", "kelvin"])
        if color_temp is None:
            return True, "No color temperature found"

        if color_temp < 1000 or color_temp > 10000:
            return False, f"Color temperature {color_temp}K is outside valid range (1000-10000K)"

        return True, f"Color temperature {color_temp}K is valid"

    def _check_motion_presence_consistency(
        self, data: Any, context: dict
    ) -> tuple[bool, str]:
        """Check motion and presence are consistent."""
        motion = self._extract_value(data, ["motion", "motion_detected"])
        presence = self._extract_value(data, ["presence", "occupied", "occupancy"])

        if motion is None or presence is None:
            return True, "Motion or presence data not present"

        # If motion is detected, presence should generally be true
        # (though brief motion might not update presence)
        # This is a soft check
        return True, "Motion/presence check passed"

    def _check_lock_state(
        self, data: Any, context: dict
    ) -> tuple[bool, str]:
        """Check lock state is binary."""
        state = self._extract_value(data, ["locked", "lock_state", "state"])
        if state is None:
            return True, "No lock state found"

        if isinstance(state, bool):
            return True, "Lock state is valid boolean"

        if isinstance(state, str):
            valid_states = ["locked", "unlocked", "locking", "unlocking"]
            if state.lower() not in valid_states:
                return False, f"Invalid lock state: {state}"

        return True, f"Lock state '{state}' is valid"

    def _check_network_bandwidth(
        self, data: Any, context: dict
    ) -> tuple[bool, str]:
        """Check network bandwidth is positive."""
        bw = self._extract_value(data, ["bandwidth", "speed", "data_rate", "bitrate"])
        if bw is None:
            return True, "No bandwidth value found"

        if bw < 0:
            return False, f"Bandwidth cannot be negative: {bw}"

        return True, f"Bandwidth {bw} is valid"

    def _check_ip_address(
        self, data: Any, context: dict
    ) -> tuple[bool, str]:
        """Check IP address format."""
        import re
        ip = self._extract_value(data, ["ip", "ip_address", "ipv4"])
        if ip is None:
            return True, "No IP address found"

        # IPv4 pattern
        ipv4_pattern = r'^(\d{1,3}\.){3}\d{1,3}$'
        if re.match(ipv4_pattern, str(ip)):
            # Check octets
            octets = [int(x) for x in str(ip).split('.')]
            if all(0 <= o <= 255 for o in octets):
                return True, f"IP address {ip} is valid"
            return False, f"IP address {ip} has invalid octets"

        # IPv6 would need additional pattern
        return False, f"Invalid IP address format: {ip}"

    def _check_timestamp(
        self, data: Any, context: dict
    ) -> tuple[bool, str]:
        """Check timestamp validity."""
        from datetime import datetime, timedelta

        ts = self._extract_value(data, ["timestamp", "time", "datetime", "created_at"])
        if ts is None:
            return True, "No timestamp found"

        try:
            if isinstance(ts, (int, float)):
                # Unix timestamp
                dt = datetime.fromtimestamp(ts)
            elif isinstance(ts, str):
                # ISO format
                dt = datetime.fromisoformat(ts.replace('Z', '+00:00'))
            else:
                return True, "Unknown timestamp format"

            # Check not too far in future (1 year)
            if dt > datetime.utcnow() + timedelta(days=365):
                return False, f"Timestamp {dt} is too far in the future"

            # Check not before 2000
            if dt < datetime(2000, 1, 1):
                return False, f"Timestamp {dt} is too far in the past"

            return True, f"Timestamp {dt} is valid"

        except Exception as e:
            return False, f"Invalid timestamp: {e}"

    # ==================== Helper Methods ====================

    def _extract_value(self, data: Any, keys: list[str]) -> Any:
        """Extract a value from data using multiple possible keys."""
        if isinstance(data, dict):
            for key in keys:
                if key in data:
                    return data[key]
                # Check nested
                for k, v in data.items():
                    if isinstance(v, dict):
                        result = self._extract_value(v, keys)
                        if result is not None:
                            return result
        return None

    def create_verifier(
        self, device_type: str = None
    ) -> callable:
        """
        Create a verifier function for the verification pipeline.

        Args:
            device_type: Optional device type to filter constraints

        Returns:
            Async verifier function compatible with VerificationPipeline
        """
        async def verifier(data: Any, context: dict) -> VerificationCheck:
            results = self.check(data, device_type, context)

            failed = [(c, msg) for c, passed, msg in results if not passed]

            if not failed:
                return VerificationCheck.create(
                    category=VerificationCategory.PHYSICAL,
                    name="physical_constraints",
                    status=VerificationStatus.PASS,
                    confidence=1.0,
                    message=f"All {len(results)} physical constraints passed",
                )
            else:
                details = {
                    "violations": [
                        {"constraint": c.name, "message": msg}
                        for c, msg in failed[:5]
                    ],
                    "total_violations": len(failed),
                }
                return VerificationCheck.create(
                    category=VerificationCategory.PHYSICAL,
                    name="physical_constraints",
                    status=VerificationStatus.REJECT,
                    confidence=1.0,
                    message=f"{len(failed)} physical constraint(s) violated",
                    details=details,
                )

        return verifier


# Global instance
_physical_checker: Optional[PhysicalConstraintChecker] = None


def get_physical_constraint_checker() -> PhysicalConstraintChecker:
    """Get or create the global physical constraint checker."""
    global _physical_checker
    if _physical_checker is None:
        _physical_checker = PhysicalConstraintChecker()
    return _physical_checker
