"""
Activity Scheduler

Markov-based activity transition system for realistic human behavior simulation.
Uses transition matrices to model activity changes based on time of day,
current activity, and individual preferences.
"""

import random
from dataclasses import dataclass, field
from datetime import datetime, time
from typing import Optional

import numpy as np
from loguru import logger

from src.simulation.models import (
    ActivityType,
    Inhabitant,
    InhabitantType,
    RoomType,
    SimulationEvent,
    EventType,
)


@dataclass
class ActivityTransition:
    """Represents an activity transition event."""
    inhabitant_id: str
    from_activity: ActivityType
    to_activity: ActivityType
    from_room: Optional[str]
    to_room: Optional[str]
    timestamp: datetime
    trigger: str  # "scheduled", "random", "interaction", "forced"
    probability: float


class MarkovActivityModel:
    """
    Markov chain model for activity transitions.

    Uses time-dependent transition matrices to model realistic
    activity changes throughout the day.
    """

    def __init__(self, seed: Optional[int] = None):
        self.rng = random.Random(seed)
        self.np_rng = np.random.default_rng(seed)

        # Activity order for matrix indexing
        self.activities = list(ActivityType)
        self.activity_to_idx = {a: i for i, a in enumerate(self.activities)}

        # Initialize transition matrices for different time periods
        self._init_transition_matrices()

    def _init_transition_matrices(self) -> None:
        """Initialize transition matrices for different time periods."""
        n = len(self.activities)

        # Morning transitions (6:00-9:00) - High activity changes
        self.morning_matrix = self._create_matrix({
            ActivityType.SLEEPING: {
                ActivityType.PERSONAL_CARE: 0.7,
                ActivityType.SLEEPING: 0.2,
                ActivityType.RELAXING: 0.1,
            },
            ActivityType.PERSONAL_CARE: {
                ActivityType.EATING: 0.6,
                ActivityType.PERSONAL_CARE: 0.2,
                ActivityType.LEAVING: 0.2,
            },
            ActivityType.EATING: {
                ActivityType.LEAVING: 0.5,
                ActivityType.PERSONAL_CARE: 0.2,
                ActivityType.WORKING: 0.2,
                ActivityType.EATING: 0.1,
            },
            ActivityType.LEAVING: {
                ActivityType.AWAY: 0.9,
                ActivityType.LEAVING: 0.1,
            },
        })

        # Daytime transitions (9:00-17:00) - Stable, work-focused
        self.daytime_matrix = self._create_matrix({
            ActivityType.AWAY: {
                ActivityType.AWAY: 0.85,
                ActivityType.ARRIVING: 0.15,
            },
            ActivityType.WORKING: {
                ActivityType.WORKING: 0.8,
                ActivityType.EATING: 0.1,
                ActivityType.RELAXING: 0.05,
                ActivityType.PERSONAL_CARE: 0.05,
            },
            ActivityType.RELAXING: {
                ActivityType.WORKING: 0.4,
                ActivityType.RELAXING: 0.3,
                ActivityType.EATING: 0.2,
                ActivityType.ENTERTAINMENT: 0.1,
            },
        })

        # Evening transitions (17:00-21:00) - Social, relaxed
        self.evening_matrix = self._create_matrix({
            ActivityType.ARRIVING: {
                ActivityType.RELAXING: 0.5,
                ActivityType.COOKING: 0.3,
                ActivityType.PERSONAL_CARE: 0.2,
            },
            ActivityType.AWAY: {
                ActivityType.ARRIVING: 0.8,
                ActivityType.AWAY: 0.2,
            },
            ActivityType.COOKING: {
                ActivityType.EATING: 0.7,
                ActivityType.COOKING: 0.2,
                ActivityType.RELAXING: 0.1,
            },
            ActivityType.EATING: {
                ActivityType.RELAXING: 0.4,
                ActivityType.ENTERTAINMENT: 0.3,
                ActivityType.EATING: 0.2,
                ActivityType.PERSONAL_CARE: 0.1,
            },
            ActivityType.RELAXING: {
                ActivityType.ENTERTAINMENT: 0.4,
                ActivityType.RELAXING: 0.4,
                ActivityType.EATING: 0.1,
                ActivityType.PERSONAL_CARE: 0.1,
            },
            ActivityType.ENTERTAINMENT: {
                ActivityType.ENTERTAINMENT: 0.6,
                ActivityType.RELAXING: 0.3,
                ActivityType.EATING: 0.1,
            },
        })

        # Night transitions (21:00-6:00) - Wind down, sleep
        self.night_matrix = self._create_matrix({
            ActivityType.ENTERTAINMENT: {
                ActivityType.RELAXING: 0.4,
                ActivityType.PERSONAL_CARE: 0.3,
                ActivityType.ENTERTAINMENT: 0.2,
                ActivityType.SLEEPING: 0.1,
            },
            ActivityType.RELAXING: {
                ActivityType.PERSONAL_CARE: 0.4,
                ActivityType.SLEEPING: 0.3,
                ActivityType.RELAXING: 0.2,
                ActivityType.ENTERTAINMENT: 0.1,
            },
            ActivityType.PERSONAL_CARE: {
                ActivityType.SLEEPING: 0.7,
                ActivityType.RELAXING: 0.2,
                ActivityType.PERSONAL_CARE: 0.1,
            },
            ActivityType.SLEEPING: {
                ActivityType.SLEEPING: 0.95,
                ActivityType.PERSONAL_CARE: 0.04,
                ActivityType.RELAXING: 0.01,
            },
        })

    def _create_matrix(
        self, transitions: dict[ActivityType, dict[ActivityType, float]]
    ) -> np.ndarray:
        """Create a transition matrix from sparse transitions."""
        n = len(self.activities)
        matrix = np.zeros((n, n))

        for from_activity, to_probs in transitions.items():
            from_idx = self.activity_to_idx[from_activity]
            for to_activity, prob in to_probs.items():
                to_idx = self.activity_to_idx[to_activity]
                matrix[from_idx, to_idx] = prob

        # Normalize rows (add self-transitions for undefined rows)
        for i in range(n):
            row_sum = matrix[i].sum()
            if row_sum == 0:
                matrix[i, i] = 1.0  # Stay in current activity
            elif row_sum < 1.0:
                matrix[i, i] += 1.0 - row_sum  # Add self-transition
            else:
                matrix[i] /= row_sum  # Normalize

        return matrix

    def get_matrix_for_time(self, current_time: time) -> np.ndarray:
        """Get the appropriate transition matrix for the time of day."""
        hour = current_time.hour

        if 6 <= hour < 9:
            return self.morning_matrix
        elif 9 <= hour < 17:
            return self.daytime_matrix
        elif 17 <= hour < 21:
            return self.evening_matrix
        else:
            return self.night_matrix

    def get_next_activity(
        self,
        current_activity: ActivityType,
        current_time: time,
        inhabitant_type: InhabitantType = InhabitantType.ADULT,
    ) -> tuple[ActivityType, float]:
        """
        Get the next activity based on Markov transition probabilities.

        Returns:
            Tuple of (next_activity, transition_probability)
        """
        matrix = self.get_matrix_for_time(current_time)
        current_idx = self.activity_to_idx[current_activity]

        # Get transition probabilities
        probs = matrix[current_idx].copy()

        # Apply inhabitant-type modifiers
        probs = self._apply_type_modifiers(probs, inhabitant_type, current_time)

        # Normalize
        probs /= probs.sum()

        # Sample next activity
        next_idx = self.np_rng.choice(len(self.activities), p=probs)
        next_activity = self.activities[next_idx]
        probability = probs[next_idx]

        return next_activity, probability

    def _apply_type_modifiers(
        self,
        probs: np.ndarray,
        inhabitant_type: InhabitantType,
        current_time: time,
    ) -> np.ndarray:
        """Apply inhabitant-type specific modifiers to probabilities."""
        hour = current_time.hour

        if inhabitant_type == InhabitantType.CHILD:
            # Children sleep earlier, play more
            sleep_idx = self.activity_to_idx[ActivityType.SLEEPING]
            entertainment_idx = self.activity_to_idx[ActivityType.ENTERTAINMENT]
            working_idx = self.activity_to_idx[ActivityType.WORKING]

            if hour >= 20:
                probs[sleep_idx] *= 2.0
            probs[entertainment_idx] *= 1.5
            probs[working_idx] *= 0.3  # Less work (homework only)

        elif inhabitant_type == InhabitantType.ELDERLY:
            # Elderly wake earlier, nap, less activity
            sleep_idx = self.activity_to_idx[ActivityType.SLEEPING]
            relaxing_idx = self.activity_to_idx[ActivityType.RELAXING]
            exercising_idx = self.activity_to_idx[ActivityType.EXERCISING]

            if 13 <= hour < 15:  # Nap time
                probs[sleep_idx] *= 1.5
            probs[relaxing_idx] *= 1.3
            probs[exercising_idx] *= 0.5

        elif inhabitant_type == InhabitantType.TEENAGER:
            # Teenagers sleep late, more entertainment
            sleep_idx = self.activity_to_idx[ActivityType.SLEEPING]
            entertainment_idx = self.activity_to_idx[ActivityType.ENTERTAINMENT]

            if hour < 10:
                probs[sleep_idx] *= 1.5
            probs[entertainment_idx] *= 1.3

        return probs


class ActivityScheduler:
    """
    Schedules activities for inhabitants based on patterns and Markov transitions.

    Combines:
    - Time-based activity patterns
    - Markov chain transitions for variability
    - Multi-person coordination
    """

    def __init__(self, seed: Optional[int] = None):
        self.rng = random.Random(seed)
        self.markov_model = MarkovActivityModel(seed)

        # Track activity durations (minutes)
        self.activity_durations = {
            ActivityType.SLEEPING: (300, 540),      # 5-9 hours
            ActivityType.PERSONAL_CARE: (10, 45),    # 10-45 min
            ActivityType.EATING: (15, 60),           # 15-60 min
            ActivityType.COOKING: (20, 90),          # 20-90 min
            ActivityType.WORKING: (30, 240),         # 30 min - 4 hours
            ActivityType.RELAXING: (15, 120),        # 15 min - 2 hours
            ActivityType.ENTERTAINMENT: (30, 180),   # 30 min - 3 hours
            ActivityType.EXERCISING: (20, 90),       # 20-90 min
            ActivityType.LEAVING: (2, 10),           # 2-10 min
            ActivityType.ARRIVING: (2, 10),          # 2-10 min
            ActivityType.AWAY: (60, 600),            # 1-10 hours
        }

        # Room preferences per activity
        self.activity_rooms = {
            ActivityType.SLEEPING: [RoomType.BEDROOM, RoomType.MASTER_BEDROOM],
            ActivityType.PERSONAL_CARE: [RoomType.BATHROOM, RoomType.BEDROOM],
            ActivityType.EATING: [RoomType.KITCHEN, RoomType.DINING_ROOM, RoomType.LIVING_ROOM],
            ActivityType.COOKING: [RoomType.KITCHEN],
            ActivityType.WORKING: [RoomType.OFFICE, RoomType.LIVING_ROOM, RoomType.BEDROOM],
            ActivityType.RELAXING: [RoomType.LIVING_ROOM, RoomType.BEDROOM, RoomType.GARDEN],
            ActivityType.ENTERTAINMENT: [RoomType.LIVING_ROOM, RoomType.BEDROOM],
            ActivityType.EXERCISING: [RoomType.LIVING_ROOM, RoomType.GARDEN, RoomType.GARAGE],
            ActivityType.LEAVING: [RoomType.ENTRANCE, RoomType.GARAGE, RoomType.HALLWAY],
            ActivityType.ARRIVING: [RoomType.ENTRANCE, RoomType.GARAGE, RoomType.HALLWAY],
            ActivityType.AWAY: [],
        }

        # Track inhabitant states
        self._inhabitant_states: dict[str, dict] = {}

    def initialize_inhabitant(
        self,
        inhabitant: Inhabitant,
        current_time: datetime,
    ) -> None:
        """Initialize tracking for an inhabitant."""
        self._inhabitant_states[inhabitant.id] = {
            "current_activity": inhabitant.current_activity,
            "activity_start": current_time,
            "next_transition": self._calculate_next_transition(
                inhabitant.current_activity, current_time
            ),
            "is_home": inhabitant.is_home,
        }

    def _calculate_next_transition(
        self,
        activity: ActivityType,
        current_time: datetime,
    ) -> datetime:
        """Calculate when the next activity transition should occur."""
        min_duration, max_duration = self.activity_durations.get(
            activity, (30, 120)
        )
        duration_minutes = self.rng.randint(min_duration, max_duration)
        return current_time + timedelta(minutes=duration_minutes)

    def update(
        self,
        inhabitant: Inhabitant,
        current_time: datetime,
        available_rooms: list[str],
        room_types: dict[str, RoomType],
    ) -> list[SimulationEvent]:
        """
        Update inhabitant activity state and generate events.

        Args:
            inhabitant: The inhabitant to update
            current_time: Current simulation time
            available_rooms: List of available room IDs
            room_types: Mapping of room IDs to room types

        Returns:
            List of simulation events generated
        """
        events = []

        # Initialize if needed
        if inhabitant.id not in self._inhabitant_states:
            self.initialize_inhabitant(inhabitant, current_time)

        state = self._inhabitant_states[inhabitant.id]

        # Check if transition is due
        if current_time >= state["next_transition"]:
            # Get next activity from Markov model
            next_activity, probability = self.markov_model.get_next_activity(
                state["current_activity"],
                current_time.time(),
                inhabitant.inhabitant_type,
            )

            # Select appropriate room
            target_room = self._select_room(
                next_activity, available_rooms, room_types
            )

            # Create transition event
            transition = ActivityTransition(
                inhabitant_id=inhabitant.id,
                from_activity=state["current_activity"],
                to_activity=next_activity,
                from_room=inhabitant.current_room_id,
                to_room=target_room,
                timestamp=current_time,
                trigger="scheduled",
                probability=probability,
            )

            # Generate simulation event
            event = SimulationEvent(
                event_type=EventType.INHABITANT_ACTIVITY,
                timestamp=current_time,
                source_id=inhabitant.id,
                source_type="inhabitant",
                data={
                    "from_activity": state["current_activity"].value,
                    "to_activity": next_activity.value,
                    "from_room": inhabitant.current_room_id,
                    "to_room": target_room,
                    "probability": probability,
                    "trigger": "scheduled",
                },
            )
            events.append(event)

            # Generate movement event if room changed
            if target_room and target_room != inhabitant.current_room_id:
                movement_event = SimulationEvent(
                    event_type=EventType.INHABITANT_MOVEMENT,
                    timestamp=current_time,
                    source_id=inhabitant.id,
                    source_type="inhabitant",
                    data={
                        "from_room": inhabitant.current_room_id,
                        "to_room": target_room,
                        "activity": next_activity.value,
                    },
                )
                events.append(movement_event)

            # Update state
            state["current_activity"] = next_activity
            state["activity_start"] = current_time
            state["next_transition"] = self._calculate_next_transition(
                next_activity, current_time
            )

            # Update inhabitant model
            inhabitant.current_activity = next_activity
            if target_room:
                inhabitant.current_room_id = target_room

            # Handle leaving/arriving
            if next_activity == ActivityType.LEAVING:
                state["is_home"] = False
                inhabitant.is_home = False
            elif next_activity == ActivityType.ARRIVING:
                state["is_home"] = True
                inhabitant.is_home = True

        return events

    def _select_room(
        self,
        activity: ActivityType,
        available_rooms: list[str],
        room_types: dict[str, RoomType],
    ) -> Optional[str]:
        """Select an appropriate room for the activity."""
        preferred_types = self.activity_rooms.get(activity, [])

        if not preferred_types:
            return None

        # Find rooms matching preferred types
        matching_rooms = [
            room_id for room_id in available_rooms
            if room_types.get(room_id) in preferred_types
        ]

        if matching_rooms:
            return self.rng.choice(matching_rooms)

        # Fallback to any available room
        if available_rooms:
            return self.rng.choice(available_rooms)

        return None

    def force_activity(
        self,
        inhabitant: Inhabitant,
        activity: ActivityType,
        current_time: datetime,
        room_id: Optional[str] = None,
    ) -> SimulationEvent:
        """Force an activity transition (e.g., for threat simulation)."""
        state = self._inhabitant_states.get(inhabitant.id, {})
        from_activity = state.get("current_activity", inhabitant.current_activity)

        # Create event
        event = SimulationEvent(
            event_type=EventType.INHABITANT_ACTIVITY,
            timestamp=current_time,
            source_id=inhabitant.id,
            source_type="inhabitant",
            data={
                "from_activity": from_activity.value,
                "to_activity": activity.value,
                "from_room": inhabitant.current_room_id,
                "to_room": room_id,
                "probability": 1.0,
                "trigger": "forced",
            },
        )

        # Update state
        if inhabitant.id in self._inhabitant_states:
            self._inhabitant_states[inhabitant.id]["current_activity"] = activity
            self._inhabitant_states[inhabitant.id]["activity_start"] = current_time
            self._inhabitant_states[inhabitant.id]["next_transition"] = \
                self._calculate_next_transition(activity, current_time)

        # Update inhabitant
        inhabitant.current_activity = activity
        if room_id:
            inhabitant.current_room_id = room_id

        return event

    def get_activity_state(self, inhabitant_id: str) -> Optional[dict]:
        """Get the current activity state for an inhabitant."""
        return self._inhabitant_states.get(inhabitant_id)


# Import at the end to avoid circular imports
from datetime import timedelta
