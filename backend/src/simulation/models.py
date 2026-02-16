"""
Core Simulation Data Models

Pydantic models for the Smart Home simulation engine.
Includes Home, Room, Device, and Inhabitant models.
"""

from datetime import datetime, time
from enum import Enum
from typing import Any, Optional
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


# =============================================================================
# Enumerations
# =============================================================================


class RoomType(str, Enum):
    """Types of rooms in a smart home."""
    LIVING_ROOM = "living_room"
    BEDROOM = "bedroom"
    MASTER_BEDROOM = "master_bedroom"
    KITCHEN = "kitchen"
    BATHROOM = "bathroom"
    OFFICE = "office"
    GARAGE = "garage"
    HALLWAY = "hallway"
    ENTRANCE = "entrance"
    DINING_ROOM = "dining_room"
    BASEMENT = "basement"
    ATTIC = "attic"
    LAUNDRY = "laundry"
    GARDEN = "garden"
    BALCONY = "balcony"


class DeviceCategory(str, Enum):
    """Categories of IoT devices for organization."""
    FREQUENTLY_USED = "frequently_used"  # Most common devices - shown first
    SECURITY = "security"
    LIGHTING = "lighting"
    CLIMATE = "climate"
    ENTERTAINMENT = "entertainment"
    KITCHEN = "kitchen"
    APPLIANCES = "appliances"
    HEALTH = "health"
    ENERGY = "energy"
    NETWORK = "network"
    OUTDOOR = "outdoor"
    CLEANING = "cleaning"
    BABY_PET = "baby_pet"
    ACCESSIBILITY = "accessibility"
    INDUSTRIAL = "industrial"  # P1 EXPANSION: ICS/SCADA devices (Modbus, etc.)
    MISC = "misc"


class DeviceType(str, Enum):
    """Types of IoT devices - 118 total types organized by category.

    Categories:
    - FREQUENTLY_USED: Most common smart home devices (shown first in UI)
    - SECURITY: Locks, cameras, alarms, sensors
    - LIGHTING: Lights, switches, dimmers
    - CLIMATE: Thermostats, HVAC, fans, air quality
    - ENTERTAINMENT: TVs, speakers, gaming, streaming
    - KITCHEN: Refrigerators, ovens, coffee makers, etc.
    - APPLIANCES: Washers, dryers, vacuums, etc.
    - HEALTH: Medical devices, sleep trackers, etc.
    - ENERGY: Meters, solar, batteries, EV chargers
    - NETWORK: Routers, hubs, bridges, mesh
    - OUTDOOR: Sprinklers, pool, weather, gates
    - CLEANING: Robot vacuums, mops, air purifiers
    - BABY_PET: Monitors, feeders, trackers
    - ACCESSIBILITY: Voice control, automated doors, alerts
    - INDUSTRIAL: ICS/SCADA devices (Modbus sensors, PLCs, etc.) - P1 EXPANSION
    - MISC: Other smart devices
    """

    # ==========================================================================
    # FREQUENTLY USED (Most common - displayed first in UI) - 12 devices
    # ==========================================================================
    SMART_LIGHT = "smart_light"
    SMART_PLUG = "smart_plug"
    THERMOSTAT = "thermostat"
    SECURITY_CAMERA = "security_camera"
    SMART_LOCK = "smart_lock"
    MOTION_SENSOR = "motion_sensor"
    SMART_SPEAKER = "smart_speaker"
    SMART_TV = "smart_tv"
    SMART_DOORBELL = "smart_doorbell"
    DOOR_SENSOR = "door_sensor"
    SMOKE_DETECTOR = "smoke_detector"
    ROUTER = "router"

    # ==========================================================================
    # SECURITY (Locks, cameras, alarms, sensors) - 12 devices
    # ==========================================================================
    WINDOW_SENSOR = "window_sensor"
    GLASS_BREAK_SENSOR = "glass_break_sensor"
    PANIC_BUTTON = "panic_button"
    SIREN_ALARM = "siren_alarm"
    SAFE_LOCK = "safe_lock"
    GARAGE_DOOR_CONTROLLER = "garage_door_controller"
    SECURITY_KEYPAD = "security_keypad"
    VIDEO_DOORBELL_PRO = "video_doorbell_pro"
    FLOODLIGHT_CAMERA = "floodlight_camera"
    PTZ_CAMERA = "ptz_camera"
    INDOOR_CAMERA = "indoor_camera"
    DRIVEWAY_SENSOR = "driveway_sensor"

    # ==========================================================================
    # LIGHTING (Lights, switches, dimmers) - 8 devices
    # ==========================================================================
    SMART_BULB_COLOR = "smart_bulb_color"
    SMART_BULB_WHITE = "smart_bulb_white"
    LIGHT_STRIP = "light_strip"
    SMART_SWITCH = "smart_switch"
    SMART_DIMMER = "smart_dimmer"
    SMART_BLINDS = "smart_blinds"
    SMART_CURTAINS = "smart_curtains"
    CEILING_FAN_LIGHT = "ceiling_fan_light"

    # ==========================================================================
    # CLIMATE (Thermostats, HVAC, fans, air quality) - 10 devices
    # ==========================================================================
    SMART_THERMOSTAT_PRO = "smart_thermostat_pro"
    TEMPERATURE_SENSOR = "temperature_sensor"
    HUMIDITY_SENSOR = "humidity_sensor"
    AIR_QUALITY_MONITOR = "air_quality_monitor"
    SMART_FAN = "smart_fan"
    SMART_AC = "smart_ac"
    SMART_HEATER = "smart_heater"
    SMART_HUMIDIFIER = "smart_humidifier"
    SMART_DEHUMIDIFIER = "smart_dehumidifier"
    HVAC_CONTROLLER = "hvac_controller"

    # ==========================================================================
    # ENTERTAINMENT (TVs, speakers, gaming, streaming) - 9 devices (P3 EXPANSION: ir_hub added)
    # ==========================================================================
    STREAMING_DEVICE = "streaming_device"
    SOUNDBAR = "soundbar"
    SMART_DISPLAY = "smart_display"
    GAMING_CONSOLE = "gaming_console"
    MEDIA_SERVER = "media_server"
    SMART_PROJECTOR = "smart_projector"
    MULTI_ROOM_AUDIO = "multi_room_audio"
    SMART_REMOTE = "smart_remote"
    IR_HUB = "ir_hub"  # P3 EXPANSION (2026-01-18): IR remote hub (T007: 1,307,778 samples)

    # ==========================================================================
    # KITCHEN (Refrigerators, ovens, coffee makers, etc.) - 10 devices
    # ==========================================================================
    SMART_REFRIGERATOR = "smart_refrigerator"
    SMART_OVEN = "smart_oven"
    SMART_MICROWAVE = "smart_microwave"
    SMART_COFFEE_MAKER = "smart_coffee_maker"
    SMART_KETTLE = "smart_kettle"
    SMART_TOASTER = "smart_toaster"
    SMART_BLENDER = "smart_blender"
    SMART_DISHWASHER = "smart_dishwasher"
    SMART_FAUCET = "smart_faucet"
    SMART_SCALE_KITCHEN = "smart_scale_kitchen"

    # ==========================================================================
    # APPLIANCES (Washers, dryers, etc.) - 6 devices
    # ==========================================================================
    SMART_WASHER = "smart_washer"
    SMART_DRYER = "smart_dryer"
    SMART_IRON = "smart_iron"
    SMART_SEWING_MACHINE = "smart_sewing_machine"
    SMART_WATER_HEATER = "smart_water_heater"
    SMART_GARBAGE_DISPOSAL = "smart_garbage_disposal"

    # ==========================================================================
    # HEALTH & WELLNESS - 9 devices (P3 EXPANSION: health_monitor added)
    # ==========================================================================
    SMART_SCALE = "smart_scale"
    BLOOD_PRESSURE_MONITOR = "blood_pressure_monitor"
    SLEEP_TRACKER = "sleep_tracker"
    SMART_PILL_DISPENSER = "smart_pill_dispenser"
    AIR_PURIFIER = "air_purifier"
    SMART_MATTRESS = "smart_mattress"
    FITNESS_TRACKER_DOCK = "fitness_tracker_dock"
    SMART_MIRROR = "smart_mirror"
    HEALTH_MONITOR = "health_monitor"  # P3 EXPANSION (2026-01-18): Heart rate monitor (T007: 165,319 samples)

    # ==========================================================================
    # ENERGY MANAGEMENT - 6 devices
    # ==========================================================================
    SMART_METER = "smart_meter"
    SOLAR_INVERTER = "solar_inverter"
    BATTERY_STORAGE = "battery_storage"
    EV_CHARGER = "ev_charger"
    ENERGY_MONITOR = "energy_monitor"
    SMART_CIRCUIT_BREAKER = "smart_circuit_breaker"

    # ==========================================================================
    # NETWORK & INFRASTRUCTURE - 6 devices
    # ==========================================================================
    HUB = "hub"
    MESH_NODE = "mesh_node"
    SMART_BRIDGE = "smart_bridge"
    NETWORK_SWITCH = "network_switch"
    RANGE_EXTENDER = "range_extender"
    NAS_STORAGE = "nas_storage"

    # ==========================================================================
    # OUTDOOR & GARDEN - 8 devices
    # ==========================================================================
    SMART_SPRINKLER = "smart_sprinkler"
    POOL_CONTROLLER = "pool_controller"
    WEATHER_STATION = "weather_station"
    OUTDOOR_LIGHT = "outdoor_light"
    GATE_CONTROLLER = "gate_controller"
    SMART_GRILL = "smart_grill"
    GARDEN_SENSOR = "garden_sensor"
    PEST_REPELLER = "pest_repeller"

    # ==========================================================================
    # CLEANING - 4 devices
    # ==========================================================================
    ROBOT_VACUUM = "robot_vacuum"
    ROBOT_MOP = "robot_mop"
    WINDOW_CLEANER = "window_cleaner"
    POOL_CLEANER = "pool_cleaner"

    # ==========================================================================
    # BABY & PET - 6 devices
    # ==========================================================================
    BABY_MONITOR = "baby_monitor"
    SMART_CRIB = "smart_crib"
    PET_FEEDER = "pet_feeder"
    PET_CAMERA = "pet_camera"
    PET_DOOR = "pet_door"
    PET_TRACKER = "pet_tracker"

    # ==========================================================================
    # ACCESSIBILITY - 4 devices
    # ==========================================================================
    VOICE_ASSISTANT_HUB = "voice_assistant_hub"
    AUTOMATED_DOOR = "automated_door"
    EMERGENCY_ALERT = "emergency_alert"
    HEARING_LOOP = "hearing_loop"

    # ==========================================================================
    # SAFETY SENSORS - 4 devices
    # ==========================================================================
    CO_DETECTOR = "co_detector"
    WATER_LEAK_SENSOR = "water_leak_sensor"
    FLOOD_SENSOR = "flood_sensor"
    RADON_DETECTOR = "radon_detector"

    # ==========================================================================
    # INDUSTRIAL - P1 EXPANSION (2026-01-18) - ICS/SCADA Devices
    # ==========================================================================
    INDUSTRIAL_SENSOR = "industrial_sensor"  # Modbus protocol sensor (T003: 287,194 samples)
    PROXIMITY_SENSOR = "proximity_sensor"  # Distance sensor (T007: 1,143,540 samples)
    SOUND_SENSOR = "sound_sensor"  # Sound sensor (T007: 1,512,883 samples)
    WATER_QUALITY_SENSOR = "water_quality_sensor"  # pH sensor (T007: 1,192,777 samples)


# Device category mapping - maps each device type to its category
DEVICE_CATEGORY_MAP: dict[DeviceType, DeviceCategory] = {
    # Frequently Used
    DeviceType.SMART_LIGHT: DeviceCategory.FREQUENTLY_USED,
    DeviceType.SMART_PLUG: DeviceCategory.FREQUENTLY_USED,
    DeviceType.THERMOSTAT: DeviceCategory.FREQUENTLY_USED,
    DeviceType.SECURITY_CAMERA: DeviceCategory.FREQUENTLY_USED,
    DeviceType.SMART_LOCK: DeviceCategory.FREQUENTLY_USED,
    DeviceType.MOTION_SENSOR: DeviceCategory.FREQUENTLY_USED,
    DeviceType.SMART_SPEAKER: DeviceCategory.FREQUENTLY_USED,
    DeviceType.SMART_TV: DeviceCategory.FREQUENTLY_USED,
    DeviceType.SMART_DOORBELL: DeviceCategory.FREQUENTLY_USED,
    DeviceType.DOOR_SENSOR: DeviceCategory.FREQUENTLY_USED,
    DeviceType.SMOKE_DETECTOR: DeviceCategory.FREQUENTLY_USED,
    DeviceType.ROUTER: DeviceCategory.FREQUENTLY_USED,

    # Security
    DeviceType.WINDOW_SENSOR: DeviceCategory.SECURITY,
    DeviceType.GLASS_BREAK_SENSOR: DeviceCategory.SECURITY,
    DeviceType.PANIC_BUTTON: DeviceCategory.SECURITY,
    DeviceType.SIREN_ALARM: DeviceCategory.SECURITY,
    DeviceType.SAFE_LOCK: DeviceCategory.SECURITY,
    DeviceType.GARAGE_DOOR_CONTROLLER: DeviceCategory.SECURITY,
    DeviceType.SECURITY_KEYPAD: DeviceCategory.SECURITY,
    DeviceType.VIDEO_DOORBELL_PRO: DeviceCategory.SECURITY,
    DeviceType.FLOODLIGHT_CAMERA: DeviceCategory.SECURITY,
    DeviceType.PTZ_CAMERA: DeviceCategory.SECURITY,
    DeviceType.INDOOR_CAMERA: DeviceCategory.SECURITY,
    DeviceType.DRIVEWAY_SENSOR: DeviceCategory.SECURITY,

    # Lighting
    DeviceType.SMART_BULB_COLOR: DeviceCategory.LIGHTING,
    DeviceType.SMART_BULB_WHITE: DeviceCategory.LIGHTING,
    DeviceType.LIGHT_STRIP: DeviceCategory.LIGHTING,
    DeviceType.SMART_SWITCH: DeviceCategory.LIGHTING,
    DeviceType.SMART_DIMMER: DeviceCategory.LIGHTING,
    DeviceType.SMART_BLINDS: DeviceCategory.LIGHTING,
    DeviceType.SMART_CURTAINS: DeviceCategory.LIGHTING,
    DeviceType.CEILING_FAN_LIGHT: DeviceCategory.LIGHTING,

    # Climate
    DeviceType.SMART_THERMOSTAT_PRO: DeviceCategory.CLIMATE,
    DeviceType.TEMPERATURE_SENSOR: DeviceCategory.CLIMATE,
    DeviceType.HUMIDITY_SENSOR: DeviceCategory.CLIMATE,
    DeviceType.AIR_QUALITY_MONITOR: DeviceCategory.CLIMATE,
    DeviceType.SMART_FAN: DeviceCategory.CLIMATE,
    DeviceType.SMART_AC: DeviceCategory.CLIMATE,
    DeviceType.SMART_HEATER: DeviceCategory.CLIMATE,
    DeviceType.SMART_HUMIDIFIER: DeviceCategory.CLIMATE,
    DeviceType.SMART_DEHUMIDIFIER: DeviceCategory.CLIMATE,
    DeviceType.HVAC_CONTROLLER: DeviceCategory.CLIMATE,

    # Entertainment
    DeviceType.STREAMING_DEVICE: DeviceCategory.ENTERTAINMENT,
    DeviceType.SOUNDBAR: DeviceCategory.ENTERTAINMENT,
    DeviceType.SMART_DISPLAY: DeviceCategory.ENTERTAINMENT,
    DeviceType.GAMING_CONSOLE: DeviceCategory.ENTERTAINMENT,
    DeviceType.MEDIA_SERVER: DeviceCategory.ENTERTAINMENT,
    DeviceType.SMART_PROJECTOR: DeviceCategory.ENTERTAINMENT,
    DeviceType.MULTI_ROOM_AUDIO: DeviceCategory.ENTERTAINMENT,
    DeviceType.SMART_REMOTE: DeviceCategory.ENTERTAINMENT,
    DeviceType.IR_HUB: DeviceCategory.ENTERTAINMENT,  # P3 EXPANSION (2026-01-18)

    # Kitchen
    DeviceType.SMART_REFRIGERATOR: DeviceCategory.KITCHEN,
    DeviceType.SMART_OVEN: DeviceCategory.KITCHEN,
    DeviceType.SMART_MICROWAVE: DeviceCategory.KITCHEN,
    DeviceType.SMART_COFFEE_MAKER: DeviceCategory.KITCHEN,
    DeviceType.SMART_KETTLE: DeviceCategory.KITCHEN,
    DeviceType.SMART_TOASTER: DeviceCategory.KITCHEN,
    DeviceType.SMART_BLENDER: DeviceCategory.KITCHEN,
    DeviceType.SMART_DISHWASHER: DeviceCategory.KITCHEN,
    DeviceType.SMART_FAUCET: DeviceCategory.KITCHEN,
    DeviceType.SMART_SCALE_KITCHEN: DeviceCategory.KITCHEN,

    # Appliances
    DeviceType.SMART_WASHER: DeviceCategory.APPLIANCES,
    DeviceType.SMART_DRYER: DeviceCategory.APPLIANCES,
    DeviceType.SMART_IRON: DeviceCategory.APPLIANCES,
    DeviceType.SMART_SEWING_MACHINE: DeviceCategory.APPLIANCES,
    DeviceType.SMART_WATER_HEATER: DeviceCategory.APPLIANCES,
    DeviceType.SMART_GARBAGE_DISPOSAL: DeviceCategory.APPLIANCES,

    # Health
    DeviceType.SMART_SCALE: DeviceCategory.HEALTH,
    DeviceType.BLOOD_PRESSURE_MONITOR: DeviceCategory.HEALTH,
    DeviceType.SLEEP_TRACKER: DeviceCategory.HEALTH,
    DeviceType.SMART_PILL_DISPENSER: DeviceCategory.HEALTH,
    DeviceType.AIR_PURIFIER: DeviceCategory.HEALTH,
    DeviceType.SMART_MATTRESS: DeviceCategory.HEALTH,
    DeviceType.FITNESS_TRACKER_DOCK: DeviceCategory.HEALTH,
    DeviceType.SMART_MIRROR: DeviceCategory.HEALTH,
    DeviceType.HEALTH_MONITOR: DeviceCategory.HEALTH,  # P3 EXPANSION (2026-01-18)

    # Energy
    DeviceType.SMART_METER: DeviceCategory.ENERGY,
    DeviceType.SOLAR_INVERTER: DeviceCategory.ENERGY,
    DeviceType.BATTERY_STORAGE: DeviceCategory.ENERGY,
    DeviceType.EV_CHARGER: DeviceCategory.ENERGY,
    DeviceType.ENERGY_MONITOR: DeviceCategory.ENERGY,
    DeviceType.SMART_CIRCUIT_BREAKER: DeviceCategory.ENERGY,

    # Network
    DeviceType.HUB: DeviceCategory.NETWORK,
    DeviceType.MESH_NODE: DeviceCategory.NETWORK,
    DeviceType.SMART_BRIDGE: DeviceCategory.NETWORK,
    DeviceType.NETWORK_SWITCH: DeviceCategory.NETWORK,
    DeviceType.RANGE_EXTENDER: DeviceCategory.NETWORK,
    DeviceType.NAS_STORAGE: DeviceCategory.NETWORK,

    # Outdoor
    DeviceType.SMART_SPRINKLER: DeviceCategory.OUTDOOR,
    DeviceType.POOL_CONTROLLER: DeviceCategory.OUTDOOR,
    DeviceType.WEATHER_STATION: DeviceCategory.OUTDOOR,
    DeviceType.OUTDOOR_LIGHT: DeviceCategory.OUTDOOR,
    DeviceType.GATE_CONTROLLER: DeviceCategory.OUTDOOR,
    DeviceType.SMART_GRILL: DeviceCategory.OUTDOOR,
    DeviceType.GARDEN_SENSOR: DeviceCategory.OUTDOOR,
    DeviceType.PEST_REPELLER: DeviceCategory.OUTDOOR,

    # Cleaning
    DeviceType.ROBOT_VACUUM: DeviceCategory.CLEANING,
    DeviceType.ROBOT_MOP: DeviceCategory.CLEANING,
    DeviceType.WINDOW_CLEANER: DeviceCategory.CLEANING,
    DeviceType.POOL_CLEANER: DeviceCategory.CLEANING,

    # Baby & Pet
    DeviceType.BABY_MONITOR: DeviceCategory.BABY_PET,
    DeviceType.SMART_CRIB: DeviceCategory.BABY_PET,
    DeviceType.PET_FEEDER: DeviceCategory.BABY_PET,
    DeviceType.PET_CAMERA: DeviceCategory.BABY_PET,
    DeviceType.PET_DOOR: DeviceCategory.BABY_PET,
    DeviceType.PET_TRACKER: DeviceCategory.BABY_PET,

    # Accessibility
    DeviceType.VOICE_ASSISTANT_HUB: DeviceCategory.ACCESSIBILITY,
    DeviceType.AUTOMATED_DOOR: DeviceCategory.ACCESSIBILITY,
    DeviceType.EMERGENCY_ALERT: DeviceCategory.ACCESSIBILITY,
    DeviceType.HEARING_LOOP: DeviceCategory.ACCESSIBILITY,

    # Safety Sensors
    DeviceType.CO_DETECTOR: DeviceCategory.SECURITY,
    DeviceType.WATER_LEAK_SENSOR: DeviceCategory.SECURITY,
    DeviceType.FLOOD_SENSOR: DeviceCategory.SECURITY,
    DeviceType.RADON_DETECTOR: DeviceCategory.SECURITY,

    # Industrial - P1 EXPANSION (2026-01-18)
    DeviceType.INDUSTRIAL_SENSOR: DeviceCategory.INDUSTRIAL,
    DeviceType.PROXIMITY_SENSOR: DeviceCategory.INDUSTRIAL,
    DeviceType.SOUND_SENSOR: DeviceCategory.INDUSTRIAL,
    DeviceType.WATER_QUALITY_SENSOR: DeviceCategory.INDUSTRIAL,
}


def get_devices_by_category(category: DeviceCategory) -> list[DeviceType]:
    """Get all device types in a specific category."""
    return [dt for dt, cat in DEVICE_CATEGORY_MAP.items() if cat == category]


def get_device_category(device_type: DeviceType) -> DeviceCategory:
    """Get the category for a specific device type."""
    return DEVICE_CATEGORY_MAP.get(device_type, DeviceCategory.MISC)


def get_all_device_types_organized() -> dict[DeviceCategory, list[DeviceType]]:
    """Get all device types organized by category, with FREQUENTLY_USED first."""
    result: dict[DeviceCategory, list[DeviceType]] = {}

    # Ensure FREQUENTLY_USED is first
    for category in DeviceCategory:
        devices = get_devices_by_category(category)
        if devices:
            result[category] = devices

    return result


class DeviceProtocol(str, Enum):
    """Communication protocols for IoT devices."""
    WIFI = "wifi"
    ZIGBEE = "zigbee"
    ZWAVE = "z-wave"
    BLUETOOTH = "bluetooth"
    BLE = "ble"
    MATTER = "matter"
    THREAD = "thread"
    MQTT = "mqtt"
    HTTP = "http"
    COAP = "coap"
    # P1 EXPANSION (2026-01-18): Industrial protocols
    ETHERNET = "ethernet"  # Wired Ethernet/TCP
    MODBUS = "modbus"  # Modbus/TCP industrial protocol


class DeviceStatus(str, Enum):
    """Device operational status."""
    ONLINE = "online"
    OFFLINE = "offline"
    ERROR = "error"
    UPDATING = "updating"
    COMPROMISED = "compromised"


class SecurityLevel(str, Enum):
    """Security level of a device."""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    CRITICAL = "critical"  # For security devices like locks


class HomeTemplate(str, Enum):
    """Pre-defined home templates."""
    STUDIO_APARTMENT = "studio_apartment"
    ONE_BEDROOM = "one_bedroom"
    TWO_BEDROOM = "two_bedroom"
    FAMILY_HOUSE = "family_house"
    SMART_MANSION = "smart_mansion"


class InhabitantType(str, Enum):
    """Types of inhabitants."""
    ADULT = "adult"
    CHILD = "child"
    ELDERLY = "elderly"
    TEENAGER = "teenager"
    PET = "pet"


class ActivityType(str, Enum):
    """Types of daily activities."""
    SLEEPING = "sleeping"
    WAKING_UP = "waking_up"
    WORKING = "working"
    COOKING = "cooking"
    EATING = "eating"
    WATCHING_TV = "watching_tv"
    SHOWERING = "showering"
    LEAVING_HOME = "leaving_home"
    ARRIVING_HOME = "arriving_home"
    EXERCISING = "exercising"
    RELAXING = "relaxing"
    AWAY = "away"
    # Extended activity types for behavior simulation
    PERSONAL_CARE = "personal_care"
    ENTERTAINMENT = "entertainment"
    LEAVING = "leaving"
    ARRIVING = "arriving"


# =============================================================================
# Device Models
# =============================================================================


class DeviceConfig(BaseModel):
    """Configuration for a device."""
    manufacturer: str = "Generic"
    model: str = "Default"
    firmware_version: str = "1.0.0"
    protocol: DeviceProtocol = DeviceProtocol.WIFI
    security_level: SecurityLevel = SecurityLevel.MEDIUM
    update_interval_seconds: int = 60
    has_encryption: bool = True
    has_authentication: bool = True
    default_credentials: bool = False  # Vulnerability indicator
    known_vulnerabilities: list[str] = Field(default_factory=list)


class DeviceState(BaseModel):
    """Current state of a device."""
    is_on: bool = True
    status: DeviceStatus = DeviceStatus.ONLINE
    last_seen: datetime = Field(default_factory=datetime.utcnow)
    battery_level: Optional[float] = None  # 0-100, None for wired devices
    signal_strength: float = -50.0  # dBm
    cpu_usage: float = 5.0  # percentage
    memory_usage: float = 30.0  # percentage
    network_tx_bytes: int = 0
    network_rx_bytes: int = 0
    properties: dict[str, Any] = Field(default_factory=dict)  # Device-specific


class Device(BaseModel):
    """A smart home IoT device."""
    id: str = Field(default_factory=lambda: str(uuid4()))
    name: str
    device_type: DeviceType
    room_id: Optional[str] = None
    config: DeviceConfig = Field(default_factory=DeviceConfig)
    state: DeviceState = Field(default_factory=DeviceState)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    ip_address: Optional[str] = None
    mac_address: Optional[str] = None

    model_config = ConfigDict(use_enum_values=True)


# =============================================================================
# Room Models
# =============================================================================


class RoomConfig(BaseModel):
    """Configuration for a room."""
    area_sqm: float = 20.0
    has_window: bool = True
    has_external_door: bool = False
    floor_level: int = 0  # 0 = ground, negative = basement


class Room(BaseModel):
    """A room in the smart home."""
    id: str = Field(default_factory=lambda: str(uuid4()))
    name: str
    room_type: RoomType
    config: RoomConfig = Field(default_factory=RoomConfig)
    device_ids: list[str] = Field(default_factory=list)
    adjacent_room_ids: list[str] = Field(default_factory=list)

    model_config = ConfigDict(use_enum_values=True)


# =============================================================================
# Inhabitant Models
# =============================================================================


class Schedule(BaseModel):
    """Daily schedule for an inhabitant."""
    wake_time: time = time(7, 0)
    sleep_time: time = time(23, 0)
    work_start: Optional[time] = time(9, 0)
    work_end: Optional[time] = time(17, 0)
    works_from_home: bool = False
    weekend_schedule_different: bool = True


class Inhabitant(BaseModel):
    """A person or pet living in the home."""
    id: str = Field(default_factory=lambda: str(uuid4()))
    name: str
    inhabitant_type: InhabitantType = InhabitantType.ADULT
    age: Optional[int] = None
    schedule: Schedule = Field(default_factory=Schedule)
    current_room_id: Optional[str] = None
    current_activity: ActivityType = ActivityType.RELAXING
    is_home: bool = True
    tech_savviness: float = 0.5  # 0-1, affects device interaction patterns

    model_config = ConfigDict(use_enum_values=True)


# =============================================================================
# Home Model
# =============================================================================


class HomeConfig(BaseModel):
    """Configuration for the smart home."""
    template: HomeTemplate = HomeTemplate.TWO_BEDROOM
    total_area_sqm: float = 100.0
    floors: int = 1
    has_garage: bool = False
    has_garden: bool = False
    has_basement: bool = False
    has_smart_hub: bool = True
    internet_speed_mbps: float = 100.0
    security_system_enabled: bool = True


class HomeStats(BaseModel):
    """Statistics about the home."""
    total_devices: int = 0
    total_rooms: int = 0
    total_inhabitants: int = 0
    devices_online: int = 0
    devices_offline: int = 0
    devices_compromised: int = 0
    total_network_traffic_bytes: int = 0


class Home(BaseModel):
    """A complete smart home environment."""
    id: str = Field(default_factory=lambda: str(uuid4()))
    name: str = "My Smart Home"
    config: HomeConfig = Field(default_factory=HomeConfig)
    rooms: list[Room] = Field(default_factory=list)
    devices: list[Device] = Field(default_factory=list)
    inhabitants: list[Inhabitant] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    last_updated: datetime = Field(default_factory=datetime.utcnow)

    model_config = ConfigDict(use_enum_values=True)

    def get_room_by_id(self, room_id: str) -> Optional[Room]:
        """Get a room by ID."""
        for room in self.rooms:
            if room.id == room_id:
                return room
        return None

    def get_device_by_id(self, device_id: str) -> Optional[Device]:
        """Get a device by ID."""
        for device in self.devices:
            if device.id == device_id:
                return device
        return None

    def get_devices_in_room(self, room_id: str) -> list[Device]:
        """Get all devices in a specific room."""
        return [d for d in self.devices if d.room_id == room_id]

    def get_devices_by_type(self, device_type: DeviceType) -> list[Device]:
        """Get all devices of a specific type."""
        return [d for d in self.devices if d.device_type == device_type]

    def get_inhabitant_by_id(self, inhabitant_id: str) -> Optional[Inhabitant]:
        """Get an inhabitant by ID."""
        for inhabitant in self.inhabitants:
            if inhabitant.id == inhabitant_id:
                return inhabitant
        return None

    def get_stats(self) -> HomeStats:
        """Calculate current home statistics."""
        online = sum(1 for d in self.devices if d.state.status == DeviceStatus.ONLINE)
        offline = sum(1 for d in self.devices if d.state.status == DeviceStatus.OFFLINE)
        compromised = sum(1 for d in self.devices if d.state.status == DeviceStatus.COMPROMISED)
        total_traffic = sum(d.state.network_tx_bytes + d.state.network_rx_bytes for d in self.devices)

        return HomeStats(
            total_devices=len(self.devices),
            total_rooms=len(self.rooms),
            total_inhabitants=len(self.inhabitants),
            devices_online=online,
            devices_offline=offline,
            devices_compromised=compromised,
            total_network_traffic_bytes=total_traffic,
        )


# =============================================================================
# Simulation Event Models
# =============================================================================


class EventType(str, Enum):
    """Types of simulation events."""
    DEVICE_STATE_CHANGE = "device_state_change"
    DEVICE_DATA_GENERATED = "device_data_generated"
    INHABITANT_ACTIVITY = "inhabitant_activity"
    INHABITANT_MOVEMENT = "inhabitant_movement"
    THREAT_INJECTED = "threat_injected"
    THREAT_DETECTED = "threat_detected"
    NETWORK_TRAFFIC = "network_traffic"
    SYSTEM_EVENT = "system_event"


class SimulationEvent(BaseModel):
    """An event that occurs during simulation."""
    id: str = Field(default_factory=lambda: str(uuid4()))
    event_type: EventType
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    source_id: str  # Device ID, Inhabitant ID, or "system"
    source_type: str  # "device", "inhabitant", "threat", "system"
    data: dict[str, Any] = Field(default_factory=dict)
    is_anomaly: bool = False
    threat_id: Optional[str] = None  # If this event is part of a threat

    model_config = ConfigDict(use_enum_values=True)
