"""
Occupancy Model

Models the presence and location of inhabitants within the home.
Tracks room occupancy, movement patterns, and multi-person coordination.
"""

import random
from dataclasses import dataclass, field
from datetime import datetime, time, timedelta
from enum import Enum
from typing import Optional

from loguru import logger

from src.simulation.models import (
    ActivityType,
    EventType,
    Home,
    Inhabitant,
    InhabitantType,
    Room,
    RoomType,
    SimulationEvent,
)


class OccupancyState(str, Enum):
    """Occupancy state for the home."""
    EMPTY = "empty"              # No one home
    PARTIAL = "partial"          # Some inhabitants home
    FULL = "full"                # All inhabitants home
    SLEEPING = "sleeping"        # Everyone home and asleep
    AWAY_VACATION = "away_vacation"  # Extended absence


@dataclass
class RoomOccupancy:
    """Tracks occupancy of a single room."""
    room_id: str
    room_type: RoomType
    current_occupants: list[str] = field(default_factory=list)
    max_comfortable_occupancy: int = 4
    last_occupied: Optional[datetime] = None
    total_occupancy_seconds: float = 0.0


@dataclass
class InhabitantLocation:
    """Tracks an inhabitant's location and movement history."""
    inhabitant_id: str
    current_room_id: Optional[str] = None
    previous_room_id: Optional[str] = None
    entered_room_at: Optional[datetime] = None
    is_home: bool = True
    left_home_at: Optional[datetime] = None


class OccupancyModel:
    """
    Models home occupancy patterns.

    Features:
    - Room-level occupancy tracking
    - Movement between rooms
    - Multi-person coordination (avoid overcrowding)
    - Time-based occupancy patterns
    - Vacancy detection for security
    """

    def __init__(self, home: Home, seed: Optional[int] = None):
        self.home = home
        self.rng = random.Random(seed)

        # Initialize room occupancy
        self.room_occupancy: dict[str, RoomOccupancy] = {}
        for room in home.rooms:
            self.room_occupancy[room.id] = RoomOccupancy(
                room_id=room.id,
                room_type=room.room_type,
                max_comfortable_occupancy=self._get_max_occupancy(room.room_type),
            )

        # Initialize inhabitant locations
        self.inhabitant_locations: dict[str, InhabitantLocation] = {}
        for inhabitant in home.inhabitants:
            self.inhabitant_locations[inhabitant.id] = InhabitantLocation(
                inhabitant_id=inhabitant.id,
                current_room_id=inhabitant.current_room_id,
                is_home=inhabitant.is_home,
            )

        # Statistics
        self.total_movements: int = 0
        self.state_history: list[tuple[datetime, OccupancyState]] = []

    def _get_max_occupancy(self, room_type: RoomType) -> int:
        """Get comfortable max occupancy for a room type."""
        occupancy_limits = {
            RoomType.LIVING_ROOM: 8,
            RoomType.BEDROOM: 2,
            RoomType.MASTER_BEDROOM: 2,
            RoomType.KITCHEN: 4,
            RoomType.BATHROOM: 1,
            RoomType.OFFICE: 2,
            RoomType.GARAGE: 3,
            RoomType.HALLWAY: 6,
            RoomType.ENTRANCE: 4,
            RoomType.DINING_ROOM: 8,
            RoomType.BASEMENT: 4,
            RoomType.ATTIC: 2,
            RoomType.LAUNDRY: 2,
            RoomType.GARDEN: 10,
            RoomType.BALCONY: 4,
        }
        return occupancy_limits.get(room_type, 4)

    def get_home_state(self) -> OccupancyState:
        """Get the current occupancy state of the home."""
        home_inhabitants = [
            loc for loc in self.inhabitant_locations.values() if loc.is_home
        ]

        if not home_inhabitants:
            return OccupancyState.EMPTY

        total = len(self.inhabitant_locations)
        home_count = len(home_inhabitants)

        # Check if everyone is sleeping
        all_sleeping = all(
            self._is_in_bedroom(loc.current_room_id)
            for loc in home_inhabitants
        )

        if all_sleeping and home_count == total:
            return OccupancyState.SLEEPING

        if home_count == total:
            return OccupancyState.FULL

        return OccupancyState.PARTIAL

    def _is_in_bedroom(self, room_id: Optional[str]) -> bool:
        """Check if a room is a bedroom."""
        if not room_id:
            return False
        occupancy = self.room_occupancy.get(room_id)
        if occupancy:
            return occupancy.room_type in [RoomType.BEDROOM, RoomType.MASTER_BEDROOM]
        return False

    def get_room_occupants(self, room_id: str) -> list[str]:
        """Get list of inhabitant IDs in a room."""
        occupancy = self.room_occupancy.get(room_id)
        return occupancy.current_occupants if occupancy else []

    def is_room_occupied(self, room_id: str) -> bool:
        """Check if a room is occupied."""
        return len(self.get_room_occupants(room_id)) > 0

    def is_room_available(self, room_id: str) -> bool:
        """Check if room has capacity for another occupant."""
        occupancy = self.room_occupancy.get(room_id)
        if not occupancy:
            return False
        return len(occupancy.current_occupants) < occupancy.max_comfortable_occupancy

    def move_inhabitant(
        self,
        inhabitant_id: str,
        to_room_id: Optional[str],
        current_time: datetime,
    ) -> list[SimulationEvent]:
        """
        Move an inhabitant to a new room.

        Returns list of events generated.
        """
        events = []
        location = self.inhabitant_locations.get(inhabitant_id)

        if not location:
            logger.warning(f"Unknown inhabitant: {inhabitant_id}")
            return events

        from_room_id = location.current_room_id

        # Remove from current room
        if from_room_id and from_room_id in self.room_occupancy:
            room_occ = self.room_occupancy[from_room_id]
            if inhabitant_id in room_occ.current_occupants:
                room_occ.current_occupants.remove(inhabitant_id)

                # Update occupancy time
                if location.entered_room_at:
                    duration = (current_time - location.entered_room_at).total_seconds()
                    room_occ.total_occupancy_seconds += duration

        # Add to new room
        if to_room_id and to_room_id in self.room_occupancy:
            room_occ = self.room_occupancy[to_room_id]
            if inhabitant_id not in room_occ.current_occupants:
                room_occ.current_occupants.append(inhabitant_id)
            room_occ.last_occupied = current_time

        # Update location
        location.previous_room_id = from_room_id
        location.current_room_id = to_room_id
        location.entered_room_at = current_time

        self.total_movements += 1

        # Generate movement event
        if from_room_id != to_room_id:
            event = SimulationEvent(
                event_type=EventType.INHABITANT_MOVEMENT,
                timestamp=current_time,
                source_id=inhabitant_id,
                source_type="inhabitant",
                data={
                    "from_room": from_room_id,
                    "to_room": to_room_id,
                    "from_room_type": self._get_room_type(from_room_id),
                    "to_room_type": self._get_room_type(to_room_id),
                },
            )
            events.append(event)

        return events

    def _get_room_type(self, room_id: Optional[str]) -> Optional[str]:
        """Get room type as string."""
        if not room_id:
            return None
        occupancy = self.room_occupancy.get(room_id)
        if not occupancy:
            return None
        # Handle both enum and string values
        rt = occupancy.room_type
        return rt.value if hasattr(rt, 'value') else str(rt)

    def inhabitant_leaves_home(
        self,
        inhabitant_id: str,
        current_time: datetime,
    ) -> list[SimulationEvent]:
        """Handle inhabitant leaving the home."""
        events = []
        location = self.inhabitant_locations.get(inhabitant_id)

        if not location:
            return events

        # Remove from current room
        if location.current_room_id:
            events.extend(self.move_inhabitant(inhabitant_id, None, current_time))

        location.is_home = False
        location.left_home_at = current_time

        # Generate leave event
        event = SimulationEvent(
            event_type=EventType.INHABITANT_MOVEMENT,
            timestamp=current_time,
            source_id=inhabitant_id,
            source_type="inhabitant",
            data={
                "action": "left_home",
                "home_state": self.get_home_state().value,
            },
        )
        events.append(event)

        return events

    def inhabitant_arrives_home(
        self,
        inhabitant_id: str,
        entry_room_id: str,
        current_time: datetime,
    ) -> list[SimulationEvent]:
        """Handle inhabitant arriving home."""
        events = []
        location = self.inhabitant_locations.get(inhabitant_id)

        if not location:
            return events

        location.is_home = True
        location.left_home_at = None

        # Move to entry room
        events.extend(self.move_inhabitant(inhabitant_id, entry_room_id, current_time))

        # Generate arrive event
        event = SimulationEvent(
            event_type=EventType.INHABITANT_MOVEMENT,
            timestamp=current_time,
            source_id=inhabitant_id,
            source_type="inhabitant",
            data={
                "action": "arrived_home",
                "entry_room": entry_room_id,
                "home_state": self.get_home_state().value,
            },
        )
        events.append(event)

        return events

    def select_room_for_activity(
        self,
        activity: ActivityType,
        inhabitant_id: str,
        preferred_rooms: list[RoomType],
    ) -> Optional[str]:
        """
        Select the best room for an activity.

        Considers:
        - Room type preferences
        - Current occupancy
        - Multi-person coordination
        """
        available_rooms = []

        for room_id, occupancy in self.room_occupancy.items():
            # Check room type preference
            if occupancy.room_type not in preferred_rooms:
                continue

            # Check availability
            if not self.is_room_available(room_id):
                continue

            # Calculate score
            score = 1.0

            # Prefer empty rooms for private activities
            private_activities = [
                ActivityType.SLEEPING,
                ActivityType.PERSONAL_CARE,
                ActivityType.WORKING,
            ]
            if activity in private_activities:
                if len(occupancy.current_occupants) == 0:
                    score += 2.0
                elif len(occupancy.current_occupants) == 1:
                    score += 0.5

            # Prefer occupied rooms for social activities
            social_activities = [
                ActivityType.EATING,
                ActivityType.ENTERTAINMENT,
                ActivityType.RELAXING,
            ]
            if activity in social_activities:
                score += len(occupancy.current_occupants) * 0.3

            available_rooms.append((room_id, score))

        if not available_rooms:
            # Fallback to any room of preferred type
            for room_id, occupancy in self.room_occupancy.items():
                if occupancy.room_type in preferred_rooms:
                    return room_id
            return None

        # Weighted random selection
        total_score = sum(score for _, score in available_rooms)
        if total_score == 0:
            return available_rooms[0][0] if available_rooms else None

        r = self.rng.random() * total_score
        cumulative = 0
        for room_id, score in available_rooms:
            cumulative += score
            if r <= cumulative:
                return room_id

        return available_rooms[-1][0]

    def get_occupancy_stats(self) -> dict:
        """Get occupancy statistics."""
        total_inhabitants = len(self.inhabitant_locations)
        home_count = sum(1 for loc in self.inhabitant_locations.values() if loc.is_home)

        room_stats = {}
        for room_id, occupancy in self.room_occupancy.items():
            # Handle both enum and string values
            rt = occupancy.room_type
            room_type_str = rt.value if hasattr(rt, 'value') else str(rt)
            room_stats[room_id] = {
                "room_type": room_type_str,
                "current_occupants": len(occupancy.current_occupants),
                "max_occupancy": occupancy.max_comfortable_occupancy,
                "total_occupancy_seconds": occupancy.total_occupancy_seconds,
            }

        return {
            "home_state": self.get_home_state().value,
            "total_inhabitants": total_inhabitants,
            "inhabitants_home": home_count,
            "inhabitants_away": total_inhabitants - home_count,
            "total_movements": self.total_movements,
            "room_stats": room_stats,
        }

    def get_vacancy_duration(self, current_time: datetime) -> Optional[timedelta]:
        """Get how long the home has been empty (for security detection)."""
        if self.get_home_state() != OccupancyState.EMPTY:
            return None

        # Find the most recent departure
        last_departure = None
        for location in self.inhabitant_locations.values():
            if location.left_home_at:
                if last_departure is None or location.left_home_at > last_departure:
                    last_departure = location.left_home_at

        if last_departure:
            return current_time - last_departure
        return None

    def update(self, current_time: datetime) -> None:
        """Update occupancy model state."""
        current_state = self.get_home_state()

        # Track state changes
        if not self.state_history or self.state_history[-1][1] != current_state:
            self.state_history.append((current_time, current_state))

            # Limit history size
            if len(self.state_history) > 1000:
                self.state_history = self.state_history[-500:]
