"""
Device Registry and Factory

Factory pattern for creating device behavior instances.
Maps device types to their behavior implementations.
"""

from typing import Optional

from loguru import logger

from src.simulation.devices.base_device import DeviceBehavior
from src.simulation.devices.smart_devices import (
    # Original devices
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
    # Network & Infrastructure
    RouterBehavior,
    # Security devices
    GlassBreakSensorBehavior,
    PanicButtonBehavior,
    SirenAlarmBehavior,
    SafeLockBehavior,
    GarageDoorControllerBehavior,
    SecurityKeypadBehavior,
    FloodlightCameraBehavior,
    PTZCameraBehavior,
    IndoorCameraBehavior,
    DrivewaySensorBehavior,
    # Lighting devices
    SmartBulbColorBehavior,
    SmartBulbWhiteBehavior,
    LightStripBehavior,
    SmartSwitchBehavior,
    SmartDimmerBehavior,
    SmartCurtainsBehavior,
    CeilingFanLightBehavior,
    # Climate devices
    TemperatureSensorBehavior,
    HumiditySensorBehavior,
    AirQualityMonitorBehavior,
    SmartFanBehavior,
    SmartACBehavior,
    SmartHeaterBehavior,
    SmartHumidifierBehavior,
    SmartDehumidifierBehavior,
    AirPurifierBehavior,
    # Entertainment devices
    StreamingDeviceBehavior,
    SoundbarBehavior,
    SmartDisplayBehavior,
    GamingConsoleBehavior,
    MediaServerBehavior,
    SmartProjectorBehavior,
    MultiRoomAudioBehavior,
    SmartRemoteBehavior,
    # Kitchen devices
    SmartRefrigeratorBehavior,
    SmartOvenBehavior,
    SmartMicrowaveBehavior,
    SmartCoffeeMakerBehavior,
    SmartKettleBehavior,
    SmartToasterBehavior,
    SmartBlenderBehavior,
    SmartDishwasherBehavior,
    SmartFaucetBehavior,
    SmartScaleKitchenBehavior,
    # Appliances
    SmartWasherBehavior,
    SmartDryerBehavior,
    SmartIronBehavior,
    SmartSewingMachineBehavior,
    SmartWaterHeaterBehavior,
    SmartGarbageDisposalBehavior,
    # Health & Wellness
    SmartScaleBehavior,
    BloodPressureMonitorBehavior,
    SleepTrackerBehavior,
    SmartPillDispenserBehavior,
    SmartMattressBehavior,
    FitnessTrackerDockBehavior,
    SmartMirrorBehavior,
    # Energy
    SolarInverterBehavior,
    BatteryStorageBehavior,
    EVChargerBehavior,
    EnergyMonitorBehavior,
    SmartCircuitBreakerBehavior,
    # Network
    HubBehavior,
    MeshNodeBehavior,
    SmartBridgeBehavior,
    NetworkSwitchBehavior,
    RangeExtenderBehavior,
    NASStorageBehavior,
    # Outdoor
    SmartSprinklerBehavior,
    PoolControllerBehavior,
    WeatherStationBehavior,
    OutdoorLightBehavior,
    GateControllerBehavior,
    SmartGrillBehavior,
    GardenSensorBehavior,
    PestRepellerBehavior,
    # Cleaning
    RobotVacuumBehavior,
    RobotMopBehavior,
    WindowCleanerBehavior,
    PoolCleanerBehavior,
    # Baby & Pet
    BabyMonitorBehavior,
    SmartCribBehavior,
    PetFeederBehavior,
    PetCameraBehavior,
    PetDoorBehavior,
    PetTrackerBehavior,
    # Accessibility
    VoiceAssistantHubBehavior,
    AutomatedDoorBehavior,
    EmergencyAlertBehavior,
    HearingLoopBehavior,
)
from src.simulation.models import Device, DeviceType


# Device type to behavior class mapping
DEVICE_BEHAVIORS: dict[DeviceType, type[DeviceBehavior]] = {
    # ==========================================================================
    # FREQUENTLY USED (12 devices)
    # ==========================================================================
    DeviceType.SMART_LIGHT: SmartLightBehavior,
    DeviceType.SMART_PLUG: SmartPlugBehavior,
    DeviceType.THERMOSTAT: ThermostatBehavior,
    DeviceType.SECURITY_CAMERA: SecurityCameraBehavior,
    DeviceType.SMART_LOCK: SmartLockBehavior,
    DeviceType.MOTION_SENSOR: MotionSensorBehavior,
    DeviceType.SMART_SPEAKER: SmartSpeakerBehavior,
    DeviceType.SMART_TV: SmartTVBehavior,
    DeviceType.SMART_DOORBELL: SmartDoorbellBehavior,
    DeviceType.DOOR_SENSOR: DoorSensorBehavior,
    DeviceType.SMOKE_DETECTOR: SmokeDetectorBehavior,
    DeviceType.ROUTER: RouterBehavior,

    # ==========================================================================
    # SECURITY (12 devices)
    # ==========================================================================
    DeviceType.WINDOW_SENSOR: DoorSensorBehavior,  # Reuses door sensor
    DeviceType.GLASS_BREAK_SENSOR: GlassBreakSensorBehavior,
    DeviceType.PANIC_BUTTON: PanicButtonBehavior,
    DeviceType.SIREN_ALARM: SirenAlarmBehavior,
    DeviceType.SAFE_LOCK: SafeLockBehavior,
    DeviceType.GARAGE_DOOR_CONTROLLER: GarageDoorControllerBehavior,
    DeviceType.SECURITY_KEYPAD: SecurityKeypadBehavior,
    DeviceType.VIDEO_DOORBELL_PRO: SmartDoorbellBehavior,  # Enhanced doorbell
    DeviceType.FLOODLIGHT_CAMERA: FloodlightCameraBehavior,
    DeviceType.PTZ_CAMERA: PTZCameraBehavior,
    DeviceType.INDOOR_CAMERA: IndoorCameraBehavior,
    DeviceType.DRIVEWAY_SENSOR: DrivewaySensorBehavior,

    # ==========================================================================
    # LIGHTING (8 devices)
    # ==========================================================================
    DeviceType.SMART_BULB_COLOR: SmartBulbColorBehavior,
    DeviceType.SMART_BULB_WHITE: SmartBulbWhiteBehavior,
    DeviceType.LIGHT_STRIP: LightStripBehavior,
    DeviceType.SMART_SWITCH: SmartSwitchBehavior,
    DeviceType.SMART_DIMMER: SmartDimmerBehavior,
    DeviceType.SMART_CURTAINS: SmartCurtainsBehavior,
    DeviceType.SMART_BLINDS: SmartBlindsBehavior,
    DeviceType.CEILING_FAN_LIGHT: CeilingFanLightBehavior,

    # ==========================================================================
    # CLIMATE (10 devices)
    # ==========================================================================
    DeviceType.SMART_THERMOSTAT_PRO: ThermostatBehavior,  # Enhanced thermostat
    DeviceType.TEMPERATURE_SENSOR: TemperatureSensorBehavior,
    DeviceType.HUMIDITY_SENSOR: HumiditySensorBehavior,
    DeviceType.AIR_QUALITY_MONITOR: AirQualityMonitorBehavior,
    DeviceType.SMART_FAN: SmartFanBehavior,
    DeviceType.SMART_AC: SmartACBehavior,
    DeviceType.SMART_HEATER: SmartHeaterBehavior,
    DeviceType.SMART_HUMIDIFIER: SmartHumidifierBehavior,
    DeviceType.SMART_DEHUMIDIFIER: SmartDehumidifierBehavior,
    DeviceType.HVAC_CONTROLLER: ThermostatBehavior,  # Reuses thermostat

    # ==========================================================================
    # HEALTH & WELLNESS (8 devices)
    # ==========================================================================
    DeviceType.AIR_PURIFIER: AirPurifierBehavior,
    DeviceType.SMART_SCALE: SmartScaleBehavior,
    DeviceType.BLOOD_PRESSURE_MONITOR: BloodPressureMonitorBehavior,
    DeviceType.SLEEP_TRACKER: SleepTrackerBehavior,
    DeviceType.SMART_PILL_DISPENSER: SmartPillDispenserBehavior,
    DeviceType.SMART_MATTRESS: SmartMattressBehavior,
    DeviceType.FITNESS_TRACKER_DOCK: FitnessTrackerDockBehavior,
    DeviceType.SMART_MIRROR: SmartMirrorBehavior,

    # ==========================================================================
    # ENERGY (6 devices)
    # ==========================================================================
    DeviceType.SMART_METER: SmartMeterBehavior,
    DeviceType.SOLAR_INVERTER: SolarInverterBehavior,
    DeviceType.BATTERY_STORAGE: BatteryStorageBehavior,
    DeviceType.EV_CHARGER: EVChargerBehavior,
    DeviceType.ENERGY_MONITOR: EnergyMonitorBehavior,
    DeviceType.SMART_CIRCUIT_BREAKER: SmartCircuitBreakerBehavior,

    # ==========================================================================
    # SAFETY SENSORS (4 devices)
    # ==========================================================================
    DeviceType.CO_DETECTOR: SmokeDetectorBehavior,  # Similar to smoke
    DeviceType.WATER_LEAK_SENSOR: WaterLeakSensorBehavior,
    DeviceType.FLOOD_SENSOR: WaterLeakSensorBehavior,  # Reuses water leak
    DeviceType.RADON_DETECTOR: AirQualityMonitorBehavior,  # Similar AQ monitoring

    # ==========================================================================
    # ENTERTAINMENT (8 devices)
    # ==========================================================================
    DeviceType.STREAMING_DEVICE: StreamingDeviceBehavior,
    DeviceType.SOUNDBAR: SoundbarBehavior,
    DeviceType.SMART_DISPLAY: SmartDisplayBehavior,
    DeviceType.GAMING_CONSOLE: GamingConsoleBehavior,
    DeviceType.MEDIA_SERVER: MediaServerBehavior,
    DeviceType.SMART_PROJECTOR: SmartProjectorBehavior,
    DeviceType.MULTI_ROOM_AUDIO: MultiRoomAudioBehavior,
    DeviceType.SMART_REMOTE: SmartRemoteBehavior,

    # ==========================================================================
    # KITCHEN (10 devices)
    # ==========================================================================
    DeviceType.SMART_REFRIGERATOR: SmartRefrigeratorBehavior,
    DeviceType.SMART_OVEN: SmartOvenBehavior,
    DeviceType.SMART_MICROWAVE: SmartMicrowaveBehavior,
    DeviceType.SMART_COFFEE_MAKER: SmartCoffeeMakerBehavior,
    DeviceType.SMART_KETTLE: SmartKettleBehavior,
    DeviceType.SMART_TOASTER: SmartToasterBehavior,
    DeviceType.SMART_BLENDER: SmartBlenderBehavior,
    DeviceType.SMART_DISHWASHER: SmartDishwasherBehavior,
    DeviceType.SMART_FAUCET: SmartFaucetBehavior,
    DeviceType.SMART_SCALE_KITCHEN: SmartScaleKitchenBehavior,

    # ==========================================================================
    # APPLIANCES (6 devices)
    # ==========================================================================
    DeviceType.SMART_WASHER: SmartWasherBehavior,
    DeviceType.SMART_DRYER: SmartDryerBehavior,
    DeviceType.SMART_IRON: SmartIronBehavior,
    DeviceType.SMART_SEWING_MACHINE: SmartSewingMachineBehavior,
    DeviceType.SMART_WATER_HEATER: SmartWaterHeaterBehavior,
    DeviceType.SMART_GARBAGE_DISPOSAL: SmartGarbageDisposalBehavior,

    # ==========================================================================
    # NETWORK (6 devices - ROUTER already in FREQUENTLY USED)
    # ==========================================================================
    DeviceType.HUB: HubBehavior,
    DeviceType.MESH_NODE: MeshNodeBehavior,
    DeviceType.SMART_BRIDGE: SmartBridgeBehavior,
    DeviceType.NETWORK_SWITCH: NetworkSwitchBehavior,
    DeviceType.RANGE_EXTENDER: RangeExtenderBehavior,
    DeviceType.NAS_STORAGE: NASStorageBehavior,

    # ==========================================================================
    # OUTDOOR (8 devices)
    # ==========================================================================
    DeviceType.SMART_SPRINKLER: SmartSprinklerBehavior,
    DeviceType.POOL_CONTROLLER: PoolControllerBehavior,
    DeviceType.WEATHER_STATION: WeatherStationBehavior,
    DeviceType.OUTDOOR_LIGHT: OutdoorLightBehavior,
    DeviceType.GATE_CONTROLLER: GateControllerBehavior,
    DeviceType.SMART_GRILL: SmartGrillBehavior,
    DeviceType.GARDEN_SENSOR: GardenSensorBehavior,
    DeviceType.PEST_REPELLER: PestRepellerBehavior,

    # ==========================================================================
    # CLEANING (4 devices)
    # ==========================================================================
    DeviceType.ROBOT_VACUUM: RobotVacuumBehavior,
    DeviceType.ROBOT_MOP: RobotMopBehavior,
    DeviceType.WINDOW_CLEANER: WindowCleanerBehavior,
    DeviceType.POOL_CLEANER: PoolCleanerBehavior,

    # ==========================================================================
    # BABY & PET (6 devices)
    # ==========================================================================
    DeviceType.BABY_MONITOR: BabyMonitorBehavior,
    DeviceType.SMART_CRIB: SmartCribBehavior,
    DeviceType.PET_FEEDER: PetFeederBehavior,
    DeviceType.PET_CAMERA: PetCameraBehavior,
    DeviceType.PET_DOOR: PetDoorBehavior,
    DeviceType.PET_TRACKER: PetTrackerBehavior,

    # ==========================================================================
    # ACCESSIBILITY (4 devices)
    # ==========================================================================
    DeviceType.VOICE_ASSISTANT_HUB: VoiceAssistantHubBehavior,
    DeviceType.AUTOMATED_DOOR: AutomatedDoorBehavior,
    DeviceType.EMERGENCY_ALERT: EmergencyAlertBehavior,
    DeviceType.HEARING_LOOP: HearingLoopBehavior,
}


class DeviceRegistry:
    """
    Registry for device behavior instances.

    Manages the mapping from Device models to their behavior implementations.
    """

    def __init__(self):
        self._behaviors: dict[str, DeviceBehavior] = {}

    def register(self, device: Device) -> Optional[DeviceBehavior]:
        """
        Register a device and create its behavior instance.

        Args:
            device: Device to register

        Returns:
            DeviceBehavior instance, or None if device type not supported
        """
        device_type = DeviceType(device.device_type)
        behavior_class = DEVICE_BEHAVIORS.get(device_type)

        if behavior_class is None:
            logger.warning(f"No behavior defined for device type: {device_type}")
            return None

        behavior = behavior_class(device)
        self._behaviors[device.id] = behavior
        logger.debug(f"Registered device: {device.name} ({device_type.value})")

        return behavior

    def get(self, device_id: str) -> Optional[DeviceBehavior]:
        """Get behavior instance by device ID."""
        return self._behaviors.get(device_id)

    def unregister(self, device_id: str) -> bool:
        """Remove a device from the registry."""
        if device_id in self._behaviors:
            del self._behaviors[device_id]
            return True
        return False

    def get_all(self) -> list[DeviceBehavior]:
        """Get all registered device behaviors."""
        return list(self._behaviors.values())

    def count(self) -> int:
        """Get the number of registered devices."""
        return len(self._behaviors)

    def clear(self) -> None:
        """Clear all registered devices."""
        self._behaviors.clear()


class DeviceFactory:
    """
    Factory for creating device behavior instances.

    Provides a clean interface for device instantiation.
    """

    @staticmethod
    def create_behavior(device: Device) -> Optional[DeviceBehavior]:
        """
        Create a behavior instance for a device.

        Args:
            device: Device model

        Returns:
            DeviceBehavior instance, or None if type not supported
        """
        device_type = DeviceType(device.device_type)
        behavior_class = DEVICE_BEHAVIORS.get(device_type)

        if behavior_class is None:
            logger.warning(f"No behavior defined for device type: {device_type}")
            return None

        return behavior_class(device)

    @staticmethod
    def get_supported_types() -> list[DeviceType]:
        """Get list of supported device types."""
        return list(DEVICE_BEHAVIORS.keys())

    @staticmethod
    def is_type_supported(device_type: DeviceType) -> bool:
        """Check if a device type is supported."""
        return device_type in DEVICE_BEHAVIORS


# Global registry instance
_device_registry: Optional[DeviceRegistry] = None


def get_device_registry() -> DeviceRegistry:
    """Get the global device registry instance."""
    global _device_registry
    if _device_registry is None:
        _device_registry = DeviceRegistry()
    return _device_registry
