"""
Simulation API Router

REST endpoints for managing smart home simulations.
"""

import asyncio
from datetime import datetime
from typing import Any, Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query
from pydantic import BaseModel, Field

from src.simulation import (
    Home,
    HomeTemplate,
    SimulationConfig,
    SimulationEngine,
    SimulationState,
    create_simulation_engine,
    get_simulation_engine,
)
from src.simulation.home import HomeGenerator, get_home_generator


router = APIRouter()


# =============================================================================
# Request/Response Models
# =============================================================================


class HomeCreateRequest(BaseModel):
    """Request to create a new home."""
    name: str = "My Smart Home"
    template: HomeTemplate = HomeTemplate.TWO_BEDROOM
    num_inhabitants: Optional[int] = None
    device_density: float = Field(default=1.0, ge=0.5, le=2.0)
    seed: Optional[int] = None


class CustomRoomConfig(BaseModel):
    """Configuration for a custom room."""
    id: str
    name: str
    type: str
    x: float = 0
    y: float = 0
    width: float = 100
    height: float = 100
    devices: list[dict[str, Any]] = Field(default_factory=list)


class CustomInhabitantConfig(BaseModel):
    """Configuration for a custom inhabitant."""
    id: str
    name: str
    role: str
    age: int = 30
    schedule: dict[str, Any] = Field(default_factory=dict)


class CustomHomeCreateRequest(BaseModel):
    """Request to create a custom home from Home Builder."""
    name: str = "Custom Home"
    rooms: list[CustomRoomConfig] = Field(default_factory=list)
    inhabitants: list[CustomInhabitantConfig] = Field(default_factory=list)


class ThreatEventConfig(BaseModel):
    """User-defined threat event to inject during simulation."""
    id: str
    type: str  # Threat type (e.g., "man_in_the_middle", "credential_theft")
    name: str  # Human-readable name
    startTime: int  # Minutes from simulation start
    duration: int  # Duration in minutes
    severity: str = "medium"  # low, medium, high, critical
    severityValue: int = 50  # Numeric severity 1-100
    targetDevices: list[str] = Field(default_factory=list)  # Device IDs to target
    description: str = ""
    attackVector: str = ""  # MITRE technique


class SimulationStartRequest(BaseModel):
    """Request to start a simulation."""
    duration_hours: float = Field(default=24, ge=0.0166, le=168)  # Min ~1 min, max 1 week
    time_compression: int = Field(default=1440, ge=1, le=86400)  # Max 1 day per second
    start_time: Optional[datetime] = None
    enable_threats: bool = False
    collect_all_events: bool = True
    threats: Optional[list[ThreatEventConfig]] = None  # User-defined threats to inject


class HomeResponse(BaseModel):
    """Response containing home information."""
    id: str
    name: str
    template: str
    total_rooms: int
    total_devices: int
    total_inhabitants: int
    config: dict[str, Any]


class SimulationStatusResponse(BaseModel):
    """Response containing simulation status."""
    id: Optional[str] = None  # None when idle (no simulation running)
    state: str
    simulation_time: Optional[str] = None
    progress_percent: float = 0.0
    total_ticks: int = 0
    total_events: int = 0
    events_by_type: dict[str, int] = {}
    devices_simulated: int = 0
    anomalies_generated: int = 0


class DeviceResponse(BaseModel):
    """Response containing device information."""
    id: str
    name: str
    device_type: str
    room_id: Optional[str]
    status: str
    properties: dict[str, Any]


class EventResponse(BaseModel):
    """Response containing simulation event."""
    id: str
    event_type: str
    timestamp: str
    source_id: str
    source_type: str
    data: dict[str, Any]
    is_anomaly: bool


# =============================================================================
# Home Management Endpoints
# =============================================================================


# In-memory storage for current home (would use database in production)
_current_home: Optional[Home] = None


@router.post("/home", response_model=HomeResponse)
async def create_home(request: HomeCreateRequest) -> HomeResponse:
    """Create a new smart home configuration."""
    global _current_home

    generator = get_home_generator(seed=request.seed)
    home = generator.generate_from_template(
        template=request.template,
        name=request.name,
        num_inhabitants=request.num_inhabitants,
        device_density=request.device_density,
    )

    _current_home = home

    return HomeResponse(
        id=home.id,
        name=home.name,
        template=home.config.template.value,
        total_rooms=len(home.rooms),
        total_devices=len(home.devices),
        total_inhabitants=len(home.inhabitants),
        config={
            "total_area_sqm": home.config.total_area_sqm,
            "floors": home.config.floors,
            "has_garage": home.config.has_garage,
            "has_garden": home.config.has_garden,
        },
    )


@router.get("/home", response_model=HomeResponse)
async def get_home() -> HomeResponse:
    """Get the current home configuration."""
    if _current_home is None:
        raise HTTPException(status_code=404, detail="No home configured. Create one first.")

    home = _current_home
    return HomeResponse(
        id=home.id,
        name=home.name,
        template=home.config.template.value,
        total_rooms=len(home.rooms),
        total_devices=len(home.devices),
        total_inhabitants=len(home.inhabitants),
        config={
            "total_area_sqm": home.config.total_area_sqm,
            "floors": home.config.floors,
            "has_garage": home.config.has_garage,
            "has_garden": home.config.has_garden,
        },
    )


@router.post("/home/custom", response_model=HomeResponse)
async def create_custom_home(request: CustomHomeCreateRequest) -> HomeResponse:
    """Create a custom home configuration from Home Builder."""
    global _current_home

    from datetime import time as dt_time
    from uuid import uuid4
    from src.simulation.models import (
        Home,
        HomeConfig,
        Room,
        RoomConfig,
        RoomType,
        Device,
        DeviceType,
        Inhabitant,
        InhabitantType,
        Schedule,
    )

    # Map room type strings to RoomType enum
    room_type_map = {
        "living_room": RoomType.LIVING_ROOM,
        "bedroom": RoomType.BEDROOM,
        "master_bedroom": RoomType.MASTER_BEDROOM,
        "kitchen": RoomType.KITCHEN,
        "bathroom": RoomType.BATHROOM,
        "office": RoomType.OFFICE,
        "garage": RoomType.GARAGE,
        "hallway": RoomType.HALLWAY,
        "entrance": RoomType.ENTRANCE,
        "dining_room": RoomType.DINING_ROOM,
        "laundry": RoomType.LAUNDRY,
        "basement": RoomType.BASEMENT,
        "garden": RoomType.GARDEN,
    }

    # Map inhabitant role strings to InhabitantType enum
    inhabitant_type_map = {
        "adult": InhabitantType.ADULT,
        "child": InhabitantType.CHILD,
        "elderly": InhabitantType.ELDERLY,
        "teenager": InhabitantType.TEENAGER,
        "pet": InhabitantType.PET,
    }

    # Map frontend device types to backend DeviceType enum
    # All 85 device types are supported - use the device type value directly
    # Common aliases are also provided for backward compatibility
    device_type_map = {
        # Frequently Used (aliases and direct values)
        "light": DeviceType.SMART_LIGHT,
        "smart_light": DeviceType.SMART_LIGHT,
        "plug": DeviceType.SMART_PLUG,
        "smart_plug": DeviceType.SMART_PLUG,
        "thermostat": DeviceType.THERMOSTAT,
        "camera": DeviceType.SECURITY_CAMERA,
        "security_camera": DeviceType.SECURITY_CAMERA,
        "lock": DeviceType.SMART_LOCK,
        "smart_lock": DeviceType.SMART_LOCK,
        "sensor": DeviceType.MOTION_SENSOR,
        "motion_sensor": DeviceType.MOTION_SENSOR,
        "speaker": DeviceType.SMART_SPEAKER,
        "smart_speaker": DeviceType.SMART_SPEAKER,
        "tv": DeviceType.SMART_TV,
        "smart_tv": DeviceType.SMART_TV,
        "doorbell": DeviceType.SMART_DOORBELL,
        "smart_doorbell": DeviceType.SMART_DOORBELL,
        "door_sensor": DeviceType.DOOR_SENSOR,
        "smoke_detector": DeviceType.SMOKE_DETECTOR,
        "router": DeviceType.ROUTER,

        # Security
        "window_sensor": DeviceType.WINDOW_SENSOR,
        "glass_break_sensor": DeviceType.GLASS_BREAK_SENSOR,
        "panic_button": DeviceType.PANIC_BUTTON,
        "siren_alarm": DeviceType.SIREN_ALARM,
        "safe_lock": DeviceType.SAFE_LOCK,
        "garage_door_controller": DeviceType.GARAGE_DOOR_CONTROLLER,
        "security_keypad": DeviceType.SECURITY_KEYPAD,
        "video_doorbell_pro": DeviceType.VIDEO_DOORBELL_PRO,
        "floodlight_camera": DeviceType.FLOODLIGHT_CAMERA,
        "ptz_camera": DeviceType.PTZ_CAMERA,
        "indoor_camera": DeviceType.INDOOR_CAMERA,
        "driveway_sensor": DeviceType.DRIVEWAY_SENSOR,

        # Lighting
        "smart_bulb_color": DeviceType.SMART_BULB_COLOR,
        "smart_bulb_white": DeviceType.SMART_BULB_WHITE,
        "light_strip": DeviceType.LIGHT_STRIP,
        "smart_switch": DeviceType.SMART_SWITCH,
        "smart_dimmer": DeviceType.SMART_DIMMER,
        "smart_blinds": DeviceType.SMART_BLINDS,
        "smart_curtains": DeviceType.SMART_CURTAINS,
        "ceiling_fan_light": DeviceType.CEILING_FAN_LIGHT,

        # Climate
        "smart_thermostat_pro": DeviceType.SMART_THERMOSTAT_PRO,
        "temperature_sensor": DeviceType.TEMPERATURE_SENSOR,
        "humidity_sensor": DeviceType.HUMIDITY_SENSOR,
        "air_quality_monitor": DeviceType.AIR_QUALITY_MONITOR,
        "smart_fan": DeviceType.SMART_FAN,
        "smart_ac": DeviceType.SMART_AC,
        "smart_heater": DeviceType.SMART_HEATER,
        "smart_humidifier": DeviceType.SMART_HUMIDIFIER,
        "smart_dehumidifier": DeviceType.SMART_DEHUMIDIFIER,
        "hvac_controller": DeviceType.HVAC_CONTROLLER,

        # Entertainment
        "streaming_device": DeviceType.STREAMING_DEVICE,
        "soundbar": DeviceType.SOUNDBAR,
        "smart_display": DeviceType.SMART_DISPLAY,
        "gaming_console": DeviceType.GAMING_CONSOLE,
        "media_server": DeviceType.MEDIA_SERVER,
        "smart_projector": DeviceType.SMART_PROJECTOR,
        "multi_room_audio": DeviceType.MULTI_ROOM_AUDIO,
        "smart_remote": DeviceType.SMART_REMOTE,

        # Kitchen
        "smart_refrigerator": DeviceType.SMART_REFRIGERATOR,
        "smart_oven": DeviceType.SMART_OVEN,
        "smart_microwave": DeviceType.SMART_MICROWAVE,
        "smart_coffee_maker": DeviceType.SMART_COFFEE_MAKER,
        "smart_kettle": DeviceType.SMART_KETTLE,
        "smart_toaster": DeviceType.SMART_TOASTER,
        "smart_blender": DeviceType.SMART_BLENDER,
        "smart_dishwasher": DeviceType.SMART_DISHWASHER,
        "smart_faucet": DeviceType.SMART_FAUCET,
        "smart_scale_kitchen": DeviceType.SMART_SCALE_KITCHEN,

        # Appliances
        "smart_washer": DeviceType.SMART_WASHER,
        "smart_dryer": DeviceType.SMART_DRYER,
        "smart_iron": DeviceType.SMART_IRON,
        "smart_sewing_machine": DeviceType.SMART_SEWING_MACHINE,
        "smart_water_heater": DeviceType.SMART_WATER_HEATER,
        "smart_garbage_disposal": DeviceType.SMART_GARBAGE_DISPOSAL,

        # Health
        "smart_scale": DeviceType.SMART_SCALE,
        "blood_pressure_monitor": DeviceType.BLOOD_PRESSURE_MONITOR,
        "sleep_tracker": DeviceType.SLEEP_TRACKER,
        "smart_pill_dispenser": DeviceType.SMART_PILL_DISPENSER,
        "air_purifier": DeviceType.AIR_PURIFIER,
        "smart_mattress": DeviceType.SMART_MATTRESS,
        "fitness_tracker_dock": DeviceType.FITNESS_TRACKER_DOCK,
        "smart_mirror": DeviceType.SMART_MIRROR,

        # Energy
        "smart_meter": DeviceType.SMART_METER,
        "solar_inverter": DeviceType.SOLAR_INVERTER,
        "battery_storage": DeviceType.BATTERY_STORAGE,
        "ev_charger": DeviceType.EV_CHARGER,
        "energy_monitor": DeviceType.ENERGY_MONITOR,
        "smart_circuit_breaker": DeviceType.SMART_CIRCUIT_BREAKER,

        # Network
        "hub": DeviceType.HUB,
        "mesh_node": DeviceType.MESH_NODE,
        "smart_bridge": DeviceType.SMART_BRIDGE,
        "network_switch": DeviceType.NETWORK_SWITCH,
        "range_extender": DeviceType.RANGE_EXTENDER,
        "nas_storage": DeviceType.NAS_STORAGE,

        # Outdoor
        "smart_sprinkler": DeviceType.SMART_SPRINKLER,
        "pool_controller": DeviceType.POOL_CONTROLLER,
        "weather_station": DeviceType.WEATHER_STATION,
        "outdoor_light": DeviceType.OUTDOOR_LIGHT,
        "gate_controller": DeviceType.GATE_CONTROLLER,
        "smart_grill": DeviceType.SMART_GRILL,
        "garden_sensor": DeviceType.GARDEN_SENSOR,
        "pest_repeller": DeviceType.PEST_REPELLER,

        # Cleaning
        "robot_vacuum": DeviceType.ROBOT_VACUUM,
        "robot_mop": DeviceType.ROBOT_MOP,
        "window_cleaner": DeviceType.WINDOW_CLEANER,
        "pool_cleaner": DeviceType.POOL_CLEANER,

        # Baby & Pet
        "baby_monitor": DeviceType.BABY_MONITOR,
        "smart_crib": DeviceType.SMART_CRIB,
        "pet_feeder": DeviceType.PET_FEEDER,
        "pet_camera": DeviceType.PET_CAMERA,
        "pet_door": DeviceType.PET_DOOR,
        "pet_tracker": DeviceType.PET_TRACKER,

        # Accessibility
        "voice_assistant_hub": DeviceType.VOICE_ASSISTANT_HUB,
        "automated_door": DeviceType.AUTOMATED_DOOR,
        "emergency_alert": DeviceType.EMERGENCY_ALERT,
        "hearing_loop": DeviceType.HEARING_LOOP,

        # Safety Sensors
        "co_detector": DeviceType.CO_DETECTOR,
        "water_leak_sensor": DeviceType.WATER_LEAK_SENSOR,
        "flood_sensor": DeviceType.FLOOD_SENSOR,
        "radon_detector": DeviceType.RADON_DETECTOR,
    }

    home_id = str(uuid4())[:8]

    # Create home config
    home_config = HomeConfig(
        template=HomeTemplate.TWO_BEDROOM,  # Use TWO_BEDROOM as default for custom
        total_area_sqm=sum(r.width * r.height / 100 for r in request.rooms) or 100,
        floors=1,
        has_garage=any(r.type == "garage" for r in request.rooms),
        has_garden=any(r.type == "garden" for r in request.rooms),
    )

    # Build rooms with devices
    rooms = []
    all_devices = []

    for room_config in request.rooms:
        room_type = room_type_map.get(room_config.type, RoomType.LIVING_ROOM)
        device_ids = []

        # Create devices for this room
        for device_data in room_config.devices:
            device_type_str = device_data.get("type", "plug")
            device_type = device_type_map.get(device_type_str, DeviceType.SMART_PLUG)
            device_id = device_data.get("id", str(uuid4())[:8])

            device = Device(
                id=device_id,
                name=device_data.get("name", f"{device_type_str.title()} in {room_config.name}"),
                device_type=device_type,
                room_id=room_config.id,
            )
            all_devices.append(device)
            device_ids.append(device.id)

        room = Room(
            id=room_config.id,
            name=room_config.name,
            room_type=room_type,
            config=RoomConfig(
                area_sqm=room_config.width * room_config.height / 100,
                floor_level=0,
            ),
            device_ids=device_ids,
        )
        rooms.append(room)

    # Build inhabitants
    inhabitants = []
    for inh_config in request.inhabitants:
        schedule_data = inh_config.schedule
        inhabitant_type = inhabitant_type_map.get(inh_config.role, InhabitantType.ADULT)

        schedule = Schedule(
            wake_time=dt_time(schedule_data.get("wakeUp", 7), 0),
            sleep_time=dt_time(schedule_data.get("sleep", 23), 0),
            works_from_home=schedule_data.get("workFromHome", False),
        )

        inhabitant = Inhabitant(
            id=inh_config.id,
            name=inh_config.name,
            inhabitant_type=inhabitant_type,
            age=inh_config.age,
            schedule=schedule,
        )
        inhabitants.append(inhabitant)

    # Create the Home object
    home = Home(
        id=home_id,
        name=request.name,
        config=home_config,
        rooms=rooms,
        devices=all_devices,
        inhabitants=inhabitants,
    )

    _current_home = home

    return HomeResponse(
        id=home.id,
        name=home.name,
        template="custom",
        total_rooms=len(home.rooms),
        total_devices=len(home.devices),
        total_inhabitants=len(home.inhabitants),
        config={
            "total_area_sqm": home.config.total_area_sqm,
            "floors": home.config.floors,
            "has_garage": home.config.has_garage,
            "has_garden": home.config.has_garden,
        },
    )


@router.get("/home/rooms")
async def get_rooms() -> list[dict[str, Any]]:
    """Get all rooms in the current home."""
    if _current_home is None:
        raise HTTPException(status_code=404, detail="No home configured")

    return [
        {
            "id": room.id,
            "name": room.name,
            "room_type": room.room_type,
            "area_sqm": room.config.area_sqm,
            "floor_level": room.config.floor_level,
            "device_count": len(room.device_ids),
        }
        for room in _current_home.rooms
    ]


@router.get("/home/devices", response_model=list[DeviceResponse])
async def get_devices(
    room_id: Optional[str] = Query(None, description="Filter by room ID"),
    device_type: Optional[str] = Query(None, description="Filter by device type"),
) -> list[DeviceResponse]:
    """Get all devices in the current home."""
    if _current_home is None:
        raise HTTPException(status_code=404, detail="No home configured")

    devices = _current_home.devices

    if room_id:
        devices = [d for d in devices if d.room_id == room_id]

    if device_type:
        devices = [d for d in devices if d.device_type == device_type]

    return [
        DeviceResponse(
            id=d.id,
            name=d.name,
            device_type=d.device_type,
            room_id=d.room_id,
            status=d.state.status,
            properties=d.state.properties,
        )
        for d in devices
    ]


@router.get("/home/inhabitants")
async def get_inhabitants() -> list[dict[str, Any]]:
    """Get all inhabitants in the current home."""
    if _current_home is None:
        raise HTTPException(status_code=404, detail="No home configured")

    return [
        {
            "id": i.id,
            "name": i.name,
            "type": i.inhabitant_type,
            "age": i.age,
            "is_home": i.is_home,
            "current_activity": i.current_activity,
            "schedule": {
                "wake_time": i.schedule.wake_time.isoformat(),
                "sleep_time": i.schedule.sleep_time.isoformat(),
                "works_from_home": i.schedule.works_from_home,
            },
        }
        for i in _current_home.inhabitants
    ]


@router.get("/home/stats")
async def get_home_stats() -> dict[str, Any]:
    """Get statistics about the current home."""
    if _current_home is None:
        raise HTTPException(status_code=404, detail="No home configured")

    stats = _current_home.get_stats()
    return {
        "total_devices": stats.total_devices,
        "total_rooms": stats.total_rooms,
        "total_inhabitants": stats.total_inhabitants,
        "devices_online": stats.devices_online,
        "devices_offline": stats.devices_offline,
        "devices_compromised": stats.devices_compromised,
        "total_network_traffic_bytes": stats.total_network_traffic_bytes,
    }


# =============================================================================
# Simulation Control Endpoints
# =============================================================================


@router.post("/start", response_model=SimulationStatusResponse)
async def start_simulation(
    request: SimulationStartRequest,
    background_tasks: BackgroundTasks,
) -> SimulationStatusResponse:
    """Start a new simulation."""
    from loguru import logger

    if _current_home is None:
        raise HTTPException(status_code=400, detail="No home configured. Create one first.")

    # Check if simulation already running
    current_engine = get_simulation_engine()
    if current_engine and current_engine.stats.state == SimulationState.RUNNING:
        raise HTTPException(status_code=400, detail="Simulation already running")

    # Auto-enable threats if user provides threat scenarios
    enable_threats = request.enable_threats
    if request.threats and len(request.threats) > 0:
        enable_threats = True
        logger.info(f"User provided {len(request.threats)} threat scenarios - enabling threats")

    # Create simulation config
    config = SimulationConfig(
        duration_hours=request.duration_hours,
        time_compression=request.time_compression,
        start_time=request.start_time,
        enable_threats=enable_threats,
        collect_all_events=request.collect_all_events,
    )

    # Create and start engine
    engine = create_simulation_engine(_current_home, config)

    # Store user-defined threats for scheduled injection
    if request.threats and engine.threat_injector:
        # Store threats on the engine for scheduled injection
        engine._user_defined_threats = request.threats
        logger.info(f"Stored {len(request.threats)} user-defined threats for scheduled injection")

    # Run simulation in background
    background_tasks.add_task(engine.run)

    # Wait briefly for simulation to start
    await asyncio.sleep(0.1)

    return SimulationStatusResponse(
        id=engine.stats.id,
        state=engine.stats.state.value,
        simulation_time=engine.stats.simulation_current_time.isoformat() if engine.stats.simulation_current_time else None,
        progress_percent=0.0,
        total_ticks=engine.stats.total_ticks,
        total_events=engine.stats.total_events,
        events_by_type=engine.stats.events_by_type,
        devices_simulated=engine.stats.devices_simulated,
        anomalies_generated=engine.stats.anomalies_generated,
    )


@router.get("/status", response_model=SimulationStatusResponse)
async def get_simulation_status() -> SimulationStatusResponse:
    """Get current simulation status. Returns idle state when no simulation is running."""
    engine = get_simulation_engine()
    if engine is None:
        # Return idle state instead of 404 - this allows polling without errors
        return SimulationStatusResponse(
            id=None,
            state="idle",
            simulation_time=None,
            progress_percent=0.0,
            total_ticks=0,
            total_events=0,
            events_by_type={},
            devices_simulated=0,
            anomalies_generated=0,
        )

    # Calculate progress
    progress = 0.0
    if engine.stats.simulation_start_time and engine.stats.simulation_end_time and engine.stats.simulation_current_time:
        total_duration = (engine.stats.simulation_end_time - engine.stats.simulation_start_time).total_seconds()
        elapsed = (engine.stats.simulation_current_time - engine.stats.simulation_start_time).total_seconds()
        progress = min(100.0, (elapsed / total_duration) * 100) if total_duration > 0 else 0.0

    return SimulationStatusResponse(
        id=engine.stats.id,
        state=engine.stats.state.value,
        simulation_time=engine.stats.simulation_current_time.isoformat() if engine.stats.simulation_current_time else None,
        progress_percent=round(progress, 2),
        total_ticks=engine.stats.total_ticks,
        total_events=engine.stats.total_events,
        events_by_type=engine.stats.events_by_type,
        devices_simulated=engine.stats.devices_simulated,
        anomalies_generated=engine.stats.anomalies_generated,
    )


@router.post("/pause")
async def pause_simulation() -> dict[str, str]:
    """Pause the current simulation."""
    engine = get_simulation_engine()
    if engine is None:
        raise HTTPException(status_code=404, detail="No simulation running")

    if engine.stats.state != SimulationState.RUNNING:
        raise HTTPException(status_code=400, detail="Simulation is not running")

    engine.pause()
    return {"status": "paused"}


@router.post("/resume")
async def resume_simulation() -> dict[str, str]:
    """Resume a paused simulation."""
    engine = get_simulation_engine()
    if engine is None:
        raise HTTPException(status_code=404, detail="No simulation running")

    if engine.stats.state != SimulationState.PAUSED:
        raise HTTPException(status_code=400, detail="Simulation is not paused")

    engine.resume()
    return {"status": "resumed"}


@router.post("/stop")
async def stop_simulation() -> dict[str, str]:
    """Stop the current simulation."""
    engine = get_simulation_engine()
    if engine is None:
        raise HTTPException(status_code=404, detail="No simulation running")

    # If already completed or stopped, return success (idempotent)
    if engine.stats.state == SimulationState.COMPLETED:
        return {"status": "already_completed"}
    if engine.stats.state == SimulationState.ERROR:
        return {"status": "already_stopped"}
    if engine.stats.state == SimulationState.IDLE:
        return {"status": "not_started"}

    engine.stop()
    return {"status": "stopping"}


# =============================================================================
# Event Retrieval Endpoints
# =============================================================================


@router.get("/events", response_model=list[EventResponse])
async def get_events(
    event_type: Optional[str] = Query(None, description="Filter by event type"),
    device_id: Optional[str] = Query(None, description="Filter by device ID"),
    anomalies_only: bool = Query(False, description="Only return anomalies"),
    limit: int = Query(100, ge=1, le=10000),
    offset: int = Query(0, ge=0),
) -> list[EventResponse]:
    """Get simulation events with optional filtering."""
    engine = get_simulation_engine()
    if engine is None:
        # Return empty list instead of 404 - no events when no simulation
        return []

    # Get filtered events
    events = engine.get_events(
        device_id=device_id,
        anomalies_only=anomalies_only,
    )

    if event_type:
        # Handle both enum and string event_type
        events = [
            e for e in events
            if (e.event_type.value if hasattr(e.event_type, 'value') else e.event_type) == event_type
        ]

    # Apply pagination
    events = events[offset : offset + limit]

    return [
        EventResponse(
            id=e.id,
            event_type=e.event_type.value if hasattr(e.event_type, 'value') else e.event_type,
            timestamp=e.timestamp.isoformat(),
            source_id=e.source_id,
            source_type=e.source_type,
            data=e.data,
            is_anomaly=e.is_anomaly,
        )
        for e in events
    ]


@router.get("/events/export")
async def export_events() -> list[dict[str, Any]]:
    """Export all simulation events."""
    engine = get_simulation_engine()
    if engine is None:
        raise HTTPException(status_code=404, detail="No simulation data available")

    return engine.export_events()


@router.get("/devices/{device_id}/data")
async def get_device_data(device_id: str) -> list[dict[str, Any]]:
    """Get all telemetry data for a specific device."""
    engine = get_simulation_engine()
    if engine is None:
        raise HTTPException(status_code=404, detail="No simulation data available")

    return engine.get_device_data(device_id)


# =============================================================================
# Template Information Endpoints
# =============================================================================


@router.get("/templates")
async def get_templates() -> list[dict[str, Any]]:
    """Get available home templates."""
    from src.simulation.home.home_generator import TEMPLATE_CONFIGS

    return [
        {
            "id": template.value,
            "name": template.value.replace("_", " ").title(),
            "rooms": len(config["rooms"]),
            "typical_devices": config["typical_devices"],
            "typical_inhabitants": config["typical_inhabitants"],
            "total_area_sqm": config["total_area"],
            "floors": config["floors"],
        }
        for template, config in TEMPLATE_CONFIGS.items()
    ]


@router.get("/device-types")
async def get_device_types() -> list[dict[str, str]]:
    """Get available device types (flat list)."""
    from src.simulation.models import DeviceType

    return [
        {"id": dt.value, "name": dt.value.replace("_", " ").title()}
        for dt in DeviceType
    ]


@router.get("/device-types/categorized")
async def get_device_types_categorized() -> dict[str, Any]:
    """Get available device types organized by category.

    Returns device types with FREQUENTLY_USED category first,
    followed by other categories in logical order.
    """
    from src.simulation.models import (
        DeviceCategory,
        DeviceType,
        get_all_device_types_organized,
        DEVICE_CATEGORY_MAP,
    )

    organized = get_all_device_types_organized()

    # Build response with category metadata
    result = {
        "categories": [],
        "devices_by_category": {},
        "total_device_types": len(DeviceType),
    }

    # Category display names and icons for UI
    category_metadata = {
        DeviceCategory.FREQUENTLY_USED: {"name": "Frequently Used", "icon": "star", "priority": 0},
        DeviceCategory.SECURITY: {"name": "Security", "icon": "shield", "priority": 1},
        DeviceCategory.LIGHTING: {"name": "Lighting", "icon": "lightbulb", "priority": 2},
        DeviceCategory.CLIMATE: {"name": "Climate & HVAC", "icon": "thermometer", "priority": 3},
        DeviceCategory.ENTERTAINMENT: {"name": "Entertainment", "icon": "tv", "priority": 4},
        DeviceCategory.KITCHEN: {"name": "Kitchen", "icon": "utensils", "priority": 5},
        DeviceCategory.APPLIANCES: {"name": "Appliances", "icon": "washing-machine", "priority": 6},
        DeviceCategory.HEALTH: {"name": "Health & Wellness", "icon": "heart", "priority": 7},
        DeviceCategory.ENERGY: {"name": "Energy Management", "icon": "bolt", "priority": 8},
        DeviceCategory.NETWORK: {"name": "Network & Infrastructure", "icon": "wifi", "priority": 9},
        DeviceCategory.OUTDOOR: {"name": "Outdoor & Garden", "icon": "tree", "priority": 10},
        DeviceCategory.CLEANING: {"name": "Cleaning", "icon": "broom", "priority": 11},
        DeviceCategory.BABY_PET: {"name": "Baby & Pet", "icon": "paw", "priority": 12},
        DeviceCategory.ACCESSIBILITY: {"name": "Accessibility", "icon": "universal-access", "priority": 13},
        DeviceCategory.MISC: {"name": "Other", "icon": "ellipsis", "priority": 14},
    }

    for category, devices in organized.items():
        meta = category_metadata.get(category, {"name": category.value.title(), "icon": "circle", "priority": 99})
        result["categories"].append({
            "id": category.value,
            "name": meta["name"],
            "icon": meta["icon"],
            "priority": meta["priority"],
            "device_count": len(devices),
        })

        result["devices_by_category"][category.value] = [
            {
                "id": dt.value,
                "name": dt.value.replace("_", " ").title(),
                "category": category.value,
            }
            for dt in devices
        ]

    # Sort categories by priority (FREQUENTLY_USED first)
    result["categories"].sort(key=lambda x: x["priority"])

    return result
