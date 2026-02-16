"""
Smart Home Simulation Module

Core simulation engine for IoT smart home environments.
"""

from src.simulation.engine import (
    SimulationConfig,
    SimulationEngine,
    SimulationState,
    SimulationStats,
    create_simulation_engine,
    get_simulation_engine,
)
from src.simulation.models import (
    ActivityType,
    Device,
    DeviceConfig,
    DeviceProtocol,
    DeviceState,
    DeviceStatus,
    DeviceType,
    EventType,
    Home,
    HomeConfig,
    HomeStats,
    HomeTemplate,
    Inhabitant,
    InhabitantType,
    Room,
    RoomConfig,
    RoomType,
    Schedule,
    SecurityLevel,
    SimulationEvent,
)

__all__ = [
    # Engine
    "SimulationEngine",
    "SimulationConfig",
    "SimulationState",
    "SimulationStats",
    "create_simulation_engine",
    "get_simulation_engine",
    # Models
    "Home",
    "HomeConfig",
    "HomeStats",
    "HomeTemplate",
    "Room",
    "RoomConfig",
    "RoomType",
    "Device",
    "DeviceConfig",
    "DeviceState",
    "DeviceStatus",
    "DeviceType",
    "DeviceProtocol",
    "SecurityLevel",
    "Inhabitant",
    "InhabitantType",
    "Schedule",
    "ActivityType",
    "EventType",
    "SimulationEvent",
]
