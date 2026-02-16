"""
Human Behavior Engine

Main orchestrator for human behavior simulation in smart homes.
Coordinates activity scheduling, occupancy modeling, and device interactions.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Optional

from loguru import logger

from src.simulation.behavior.activity_scheduler import ActivityScheduler
from src.simulation.behavior.occupancy import OccupancyModel, OccupancyState
from src.simulation.behavior.patterns import PatternLibrary, WeeklyPattern
from src.simulation.models import (
    ActivityType,
    Device,
    DeviceType,
    EventType,
    Home,
    Inhabitant,
    InhabitantType,
    RoomType,
    SimulationEvent,
)


@dataclass
class BehaviorConfig:
    """Configuration for behavior simulation."""
    # Transition probabilities
    activity_change_probability: float = 0.1  # Per tick
    spontaneous_device_interaction: float = 0.05

    # Timing
    min_activity_duration_minutes: int = 5
    max_activity_duration_minutes: int = 240

    # Multi-person coordination
    enable_coordination: bool = True
    family_meal_probability: float = 0.7  # Probability of eating together

    # Device interaction
    enable_device_interactions: bool = True
    interaction_delay_seconds: float = 5.0

    # Randomness
    random_seed: Optional[int] = None


@dataclass
class InhabitantBehaviorState:
    """Tracks behavior state for a single inhabitant."""
    inhabitant_id: str
    weekly_pattern: Optional[WeeklyPattern] = None
    current_activity: ActivityType = ActivityType.RELAXING
    activity_start_time: Optional[datetime] = None
    last_device_interaction: Optional[datetime] = None
    interaction_count: int = 0
    pending_interactions: list[dict] = field(default_factory=list)


class HumanBehaviorEngine:
    """
    Main engine for simulating human behavior in smart homes.

    Responsibilities:
    - Coordinate activity scheduling for all inhabitants
    - Manage room occupancy
    - Generate device interactions based on activities
    - Handle multi-person coordination
    - Generate realistic behavior events
    """

    def __init__(
        self,
        home: Home,
        config: Optional[BehaviorConfig] = None,
    ):
        self.home = home
        self.config = config or BehaviorConfig()

        # Initialize sub-components
        self.activity_scheduler = ActivityScheduler(seed=self.config.random_seed)
        self.occupancy_model = OccupancyModel(home, seed=self.config.random_seed)

        # Initialize inhabitant states
        self.inhabitant_states: dict[str, InhabitantBehaviorState] = {}
        self._initialize_inhabitants()

        # Room type mapping for quick lookup
        self.room_types: dict[str, RoomType] = {
            room.id: room.room_type for room in home.rooms
        }
        self.room_ids = [room.id for room in home.rooms]

        # Device mapping by room
        self.room_devices: dict[str, list[Device]] = {}
        for room in home.rooms:
            self.room_devices[room.id] = [
                d for d in home.devices if d.room_id == room.id
            ]

        # Statistics
        self.total_events_generated: int = 0
        self.device_interactions_generated: int = 0

        logger.info(
            f"HumanBehaviorEngine initialized: "
            f"{len(home.inhabitants)} inhabitants, "
            f"{len(home.rooms)} rooms"
        )

    def _initialize_inhabitants(self) -> None:
        """Initialize behavior state for all inhabitants."""
        for inhabitant in self.home.inhabitants:
            # Get weekly pattern for inhabitant type
            weekly_pattern = PatternLibrary.get_weekly_pattern(
                inhabitant.inhabitant_type
            )

            state = InhabitantBehaviorState(
                inhabitant_id=inhabitant.id,
                weekly_pattern=weekly_pattern,
                current_activity=inhabitant.current_activity,
            )
            self.inhabitant_states[inhabitant.id] = state

            # Initialize in activity scheduler
            self.activity_scheduler.initialize_inhabitant(
                inhabitant,
                datetime.utcnow(),
            )

    def update(
        self,
        current_time: datetime,
        delta_seconds: float,
    ) -> list[SimulationEvent]:
        """
        Update behavior simulation for one tick.

        Args:
            current_time: Current simulation time
            delta_seconds: Seconds elapsed since last tick

        Returns:
            List of generated events
        """
        events = []

        # Update each inhabitant
        for inhabitant in self.home.inhabitants:
            inhabitant_events = self._update_inhabitant(
                inhabitant, current_time, delta_seconds
            )
            events.extend(inhabitant_events)

        # Update occupancy model
        self.occupancy_model.update(current_time)

        # Multi-person coordination events
        if self.config.enable_coordination:
            coordination_events = self._handle_coordination(current_time)
            events.extend(coordination_events)

        self.total_events_generated += len(events)
        return events

    def _update_inhabitant(
        self,
        inhabitant: Inhabitant,
        current_time: datetime,
        delta_seconds: float,
    ) -> list[SimulationEvent]:
        """Update a single inhabitant's behavior."""
        events = []
        state = self.inhabitant_states.get(inhabitant.id)

        if not state:
            return events

        # Update activity through scheduler
        activity_events = self.activity_scheduler.update(
            inhabitant,
            current_time,
            self.room_ids,
            self.room_types,
        )
        events.extend(activity_events)

        # Process activity changes
        for event in activity_events:
            if event.event_type == EventType.INHABITANT_ACTIVITY:
                # Update state
                new_activity = ActivityType(event.data.get("to_activity"))
                state.current_activity = new_activity
                state.activity_start_time = current_time

                # Handle room changes via occupancy model
                to_room = event.data.get("to_room")
                from_room = event.data.get("from_room")

                if to_room != from_room:
                    occupancy_events = self.occupancy_model.move_inhabitant(
                        inhabitant.id, to_room, current_time
                    )
                    # Don't add duplicate movement events
                    # events.extend(occupancy_events)

                # Handle leaving/arriving
                if new_activity == ActivityType.LEAVING:
                    leave_events = self.occupancy_model.inhabitant_leaves_home(
                        inhabitant.id, current_time
                    )
                    # events.extend(leave_events)
                elif new_activity == ActivityType.ARRIVING:
                    entry_room = self._find_entry_room()
                    arrive_events = self.occupancy_model.inhabitant_arrives_home(
                        inhabitant.id, entry_room, current_time
                    )
                    # events.extend(arrive_events)

        # Generate device interactions
        if self.config.enable_device_interactions and inhabitant.is_home:
            device_events = self._generate_device_interactions(
                inhabitant, state, current_time
            )
            events.extend(device_events)

        return events

    def _find_entry_room(self) -> str:
        """Find the entry room (entrance or garage)."""
        for room in self.home.rooms:
            if room.room_type in [RoomType.ENTRANCE, RoomType.GARAGE]:
                return room.id
        # Fallback to first room
        return self.room_ids[0] if self.room_ids else ""

    def _generate_device_interactions(
        self,
        inhabitant: Inhabitant,
        state: InhabitantBehaviorState,
        current_time: datetime,
    ) -> list[SimulationEvent]:
        """Generate device interaction events based on activity."""
        events = []

        if not inhabitant.current_room_id:
            return events

        # Get devices in current room
        room_devices = self.room_devices.get(inhabitant.current_room_id, [])
        if not room_devices:
            return events

        # Determine which devices to interact with based on activity
        activity = state.current_activity
        interaction_targets = self._get_interaction_targets(activity)

        for device in room_devices:
            if device.device_type in interaction_targets:
                # Check interaction probability and cooldown
                interaction_prob = interaction_targets[device.device_type]

                if state.last_device_interaction:
                    time_since = (current_time - state.last_device_interaction).total_seconds()
                    if time_since < self.config.interaction_delay_seconds:
                        continue

                import random
                if random.random() < interaction_prob:
                    # Generate interaction event
                    command = self._generate_device_command(device, activity)

                    event = SimulationEvent(
                        event_type=EventType.DEVICE_STATE_CHANGE,
                        timestamp=current_time,
                        source_id=device.id,
                        source_type="device",
                        data={
                            "triggered_by": inhabitant.id,
                            "activity": activity.value,
                            "command": command,
                            "device_type": device.device_type.value,
                        },
                    )
                    events.append(event)

                    state.last_device_interaction = current_time
                    state.interaction_count += 1
                    self.device_interactions_generated += 1

        return events

    def _get_interaction_targets(
        self,
        activity: ActivityType,
    ) -> dict[DeviceType, float]:
        """Get device types to interact with based on activity."""
        interaction_map = {
            ActivityType.SLEEPING: {
                DeviceType.SMART_LIGHT: 0.8,
                DeviceType.THERMOSTAT: 0.3,
                DeviceType.SMART_BLINDS: 0.4,
            },
            ActivityType.PERSONAL_CARE: {
                DeviceType.SMART_LIGHT: 0.6,
            },
            ActivityType.EATING: {
                DeviceType.SMART_LIGHT: 0.3,
                DeviceType.SMART_SPEAKER: 0.2,
            },
            ActivityType.COOKING: {
                DeviceType.SMART_PLUG: 0.5,
                DeviceType.SMART_LIGHT: 0.4,
                DeviceType.SMART_SPEAKER: 0.3,
            },
            ActivityType.WORKING: {
                DeviceType.SMART_LIGHT: 0.5,
                DeviceType.SMART_PLUG: 0.3,
                DeviceType.THERMOSTAT: 0.2,
            },
            ActivityType.RELAXING: {
                DeviceType.SMART_TV: 0.4,
                DeviceType.SMART_LIGHT: 0.3,
                DeviceType.SMART_SPEAKER: 0.3,
            },
            ActivityType.ENTERTAINMENT: {
                DeviceType.SMART_TV: 0.7,
                DeviceType.SMART_SPEAKER: 0.5,
                DeviceType.SMART_LIGHT: 0.4,
            },
            ActivityType.LEAVING: {
                DeviceType.SMART_LOCK: 0.9,
                DeviceType.SMART_LIGHT: 0.7,
                DeviceType.THERMOSTAT: 0.5,
                DeviceType.SECURITY_CAMERA: 0.3,
            },
            ActivityType.ARRIVING: {
                DeviceType.SMART_LOCK: 0.9,
                DeviceType.SMART_LIGHT: 0.7,
                DeviceType.THERMOSTAT: 0.4,
            },
            ActivityType.EXERCISING: {
                DeviceType.SMART_SPEAKER: 0.5,
                DeviceType.SMART_TV: 0.3,
            },
        }
        return interaction_map.get(activity, {})

    def _generate_device_command(
        self,
        device: Device,
        activity: ActivityType,
    ) -> dict[str, Any]:
        """Generate an appropriate command for a device based on activity."""
        import random

        commands = {
            DeviceType.SMART_LIGHT: {
                ActivityType.SLEEPING: {"action": "turn_off"},
                ActivityType.PERSONAL_CARE: {"action": "turn_on", "brightness": 100},
                ActivityType.RELAXING: {"action": "set_brightness", "brightness": 50},
                ActivityType.ENTERTAINMENT: {"action": "set_brightness", "brightness": 30},
                ActivityType.WORKING: {"action": "turn_on", "brightness": 100},
                ActivityType.LEAVING: {"action": "turn_off"},
                ActivityType.ARRIVING: {"action": "turn_on", "brightness": 80},
            },
            DeviceType.SMART_LOCK: {
                ActivityType.LEAVING: {"action": "lock"},
                ActivityType.ARRIVING: {"action": "unlock", "method": "app"},
                ActivityType.SLEEPING: {"action": "lock"},
            },
            DeviceType.THERMOSTAT: {
                ActivityType.SLEEPING: {"action": "set_temperature", "temperature": 18.0},
                ActivityType.LEAVING: {"action": "set_mode", "mode": "away"},
                ActivityType.ARRIVING: {"action": "set_mode", "mode": "home"},
                ActivityType.WORKING: {"action": "set_temperature", "temperature": 22.0},
            },
            DeviceType.SMART_TV: {
                ActivityType.ENTERTAINMENT: {"action": "turn_on"},
                ActivityType.RELAXING: {"action": "turn_on"},
                ActivityType.SLEEPING: {"action": "turn_off"},
                ActivityType.LEAVING: {"action": "turn_off"},
            },
            DeviceType.SMART_SPEAKER: {
                ActivityType.COOKING: {"action": "play_music"},
                ActivityType.EXERCISING: {"action": "play_music"},
                ActivityType.RELAXING: {"action": "play_music"},
                ActivityType.SLEEPING: {"action": "stop"},
            },
            DeviceType.SMART_PLUG: {
                ActivityType.COOKING: {"action": "turn_on"},
                ActivityType.LEAVING: {"action": "turn_off"},
            },
            DeviceType.SMART_BLINDS: {
                ActivityType.SLEEPING: {"action": "close"},
                ActivityType.PERSONAL_CARE: {"action": "open"},
            },
        }

        device_commands = commands.get(device.device_type, {})
        return device_commands.get(activity, {"action": "status"})

    def _handle_coordination(
        self,
        current_time: datetime,
    ) -> list[SimulationEvent]:
        """Handle multi-person coordination (e.g., family meals)."""
        events = []

        # Check for meal coordination
        hour = current_time.hour
        if hour in [7, 12, 18, 19]:  # Typical meal times
            home_inhabitants = [
                inh for inh in self.home.inhabitants if inh.is_home
            ]

            if len(home_inhabitants) >= 2:
                # Check if coordination should occur
                import random
                if random.random() < self.config.family_meal_probability * 0.01:
                    # Find dining area
                    dining_room = None
                    for room in self.home.rooms:
                        if room.room_type in [RoomType.DINING_ROOM, RoomType.KITCHEN]:
                            dining_room = room.id
                            break

                    if dining_room:
                        event = SimulationEvent(
                            event_type=EventType.SYSTEM_EVENT,
                            timestamp=current_time,
                            source_id="behavior_engine",
                            source_type="system",
                            data={
                                "event": "family_coordination",
                                "type": "meal",
                                "participants": [i.id for i in home_inhabitants],
                                "location": dining_room,
                            },
                        )
                        events.append(event)

        return events

    def get_occupancy_state(self) -> OccupancyState:
        """Get current home occupancy state."""
        return self.occupancy_model.get_home_state()

    def get_inhabitant_activity(
        self,
        inhabitant_id: str,
    ) -> Optional[ActivityType]:
        """Get current activity for an inhabitant."""
        state = self.inhabitant_states.get(inhabitant_id)
        return state.current_activity if state else None

    def force_activity(
        self,
        inhabitant_id: str,
        activity: ActivityType,
        current_time: datetime,
        room_id: Optional[str] = None,
    ) -> Optional[SimulationEvent]:
        """Force an activity transition (for threat simulation)."""
        inhabitant = None
        for inh in self.home.inhabitants:
            if inh.id == inhabitant_id:
                inhabitant = inh
                break

        if not inhabitant:
            return None

        return self.activity_scheduler.force_activity(
            inhabitant, activity, current_time, room_id
        )

    def get_behavior_stats(self) -> dict:
        """Get behavior simulation statistics."""
        return {
            "total_events_generated": self.total_events_generated,
            "device_interactions": self.device_interactions_generated,
            "occupancy": self.occupancy_model.get_occupancy_stats(),
            "inhabitant_states": {
                inh_id: {
                    "activity": state.current_activity.value,
                    "interaction_count": state.interaction_count,
                }
                for inh_id, state in self.inhabitant_states.items()
            },
        }
