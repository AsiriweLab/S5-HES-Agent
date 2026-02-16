"""Device Models - Smart device behavior simulation."""

from src.simulation.devices.base_device import (
    ActuatorDevice,
    DeviceBehavior,
    HybridDevice,
    SensorDevice,
)
from src.simulation.devices.device_registry import (
    DeviceFactory,
    DeviceRegistry,
    get_device_registry,
)
from src.simulation.devices.smart_devices import (
    DoorSensorBehavior,
    MotionSensorBehavior,
    SecurityCameraBehavior,
    SmartBlindsBehavior,
    SmartDoorbellBehavior,
    SmartLightBehavior,
    SmartLockBehavior,
    SmartMeterBehavior,
    SmartPlugBehavior,
    SmartSpeakerBehavior,
    SmartTVBehavior,
    SmokeDetectorBehavior,
    ThermostatBehavior,
    WaterLeakSensorBehavior,
)

__all__ = [
    # Base classes
    "DeviceBehavior",
    "SensorDevice",
    "ActuatorDevice",
    "HybridDevice",
    # Registry
    "DeviceRegistry",
    "DeviceFactory",
    "get_device_registry",
    # Device behaviors
    "SmartLockBehavior",
    "SecurityCameraBehavior",
    "MotionSensorBehavior",
    "DoorSensorBehavior",
    "SmartDoorbellBehavior",
    "ThermostatBehavior",
    "SmartLightBehavior",
    "SmartPlugBehavior",
    "SmokeDetectorBehavior",
    "WaterLeakSensorBehavior",
    "SmartSpeakerBehavior",
    "SmartTVBehavior",
    "SmartBlindsBehavior",
    "SmartMeterBehavior",
]
