"""
Daily and Weekly Behavior Patterns

Defines templates for realistic human behavior patterns including:
- Daily routines (morning, work, evening, night)
- Weekly variations (weekday vs weekend)
- Lifestyle-based pattern libraries
"""

from dataclasses import dataclass, field
from datetime import time
from enum import Enum
from typing import Optional

from src.simulation.models import ActivityType, InhabitantType, RoomType


class TimeOfDay(str, Enum):
    """Time periods within a day."""
    EARLY_MORNING = "early_morning"  # 5:00-7:00
    MORNING = "morning"              # 7:00-9:00
    LATE_MORNING = "late_morning"    # 9:00-12:00
    AFTERNOON = "afternoon"          # 12:00-17:00
    EVENING = "evening"              # 17:00-21:00
    NIGHT = "night"                  # 21:00-23:00
    LATE_NIGHT = "late_night"        # 23:00-5:00


class DayType(str, Enum):
    """Types of days affecting behavior."""
    WEEKDAY = "weekday"
    WEEKEND = "weekend"
    HOLIDAY = "holiday"
    WORK_FROM_HOME = "work_from_home"


@dataclass
class ActivitySlot:
    """A time slot with associated activity probabilities."""
    start_time: time
    end_time: time
    primary_activity: ActivityType
    primary_probability: float = 0.7
    secondary_activities: dict[ActivityType, float] = field(default_factory=dict)
    preferred_rooms: list[RoomType] = field(default_factory=list)
    device_interactions: list[str] = field(default_factory=list)  # Device type names


@dataclass
class DailyPattern:
    """A complete daily behavior pattern."""
    name: str
    description: str
    inhabitant_type: InhabitantType
    day_type: DayType
    wake_time: time = time(7, 0)
    sleep_time: time = time(23, 0)
    activity_slots: list[ActivitySlot] = field(default_factory=list)

    def get_activity_for_time(self, current_time: time) -> Optional[ActivitySlot]:
        """Get the activity slot for a given time."""
        for slot in self.activity_slots:
            if slot.start_time <= current_time < slot.end_time:
                return slot
            # Handle overnight slots
            if slot.start_time > slot.end_time:
                if current_time >= slot.start_time or current_time < slot.end_time:
                    return slot
        return None


@dataclass
class WeeklyPattern:
    """Weekly behavior pattern combining daily patterns."""
    name: str
    description: str
    inhabitant_type: InhabitantType
    weekday_pattern: DailyPattern
    weekend_pattern: DailyPattern
    work_from_home_pattern: Optional[DailyPattern] = None

    def get_pattern_for_day(self, day_of_week: int, is_holiday: bool = False) -> DailyPattern:
        """Get the appropriate pattern for a day (0=Monday, 6=Sunday)."""
        if is_holiday or day_of_week >= 5:  # Weekend
            return self.weekend_pattern
        return self.weekday_pattern


class PatternLibrary:
    """Library of predefined behavior patterns."""

    @staticmethod
    def get_adult_weekday_pattern() -> DailyPattern:
        """Standard working adult weekday pattern."""
        return DailyPattern(
            name="adult_weekday",
            description="Standard working adult weekday routine",
            inhabitant_type=InhabitantType.ADULT,
            day_type=DayType.WEEKDAY,
            wake_time=time(6, 30),
            sleep_time=time(22, 30),
            activity_slots=[
                ActivitySlot(
                    start_time=time(6, 30),
                    end_time=time(7, 30),
                    primary_activity=ActivityType.PERSONAL_CARE,
                    preferred_rooms=[RoomType.BATHROOM, RoomType.BEDROOM],
                    device_interactions=["smart_light", "smart_speaker"],
                ),
                ActivitySlot(
                    start_time=time(7, 30),
                    end_time=time(8, 0),
                    primary_activity=ActivityType.EATING,
                    preferred_rooms=[RoomType.KITCHEN, RoomType.DINING_ROOM],
                    device_interactions=["smart_plug", "smart_speaker"],
                ),
                ActivitySlot(
                    start_time=time(8, 0),
                    end_time=time(8, 30),
                    primary_activity=ActivityType.LEAVING,
                    preferred_rooms=[RoomType.ENTRANCE, RoomType.GARAGE],
                    device_interactions=["smart_lock", "security_camera", "thermostat"],
                ),
                ActivitySlot(
                    start_time=time(8, 30),
                    end_time=time(17, 30),
                    primary_activity=ActivityType.AWAY,
                    preferred_rooms=[],
                    device_interactions=[],
                ),
                ActivitySlot(
                    start_time=time(17, 30),
                    end_time=time(18, 0),
                    primary_activity=ActivityType.ARRIVING,
                    preferred_rooms=[RoomType.ENTRANCE, RoomType.GARAGE],
                    device_interactions=["smart_lock", "smart_light", "thermostat"],
                ),
                ActivitySlot(
                    start_time=time(18, 0),
                    end_time=time(19, 0),
                    primary_activity=ActivityType.COOKING,
                    preferred_rooms=[RoomType.KITCHEN],
                    device_interactions=["smart_plug", "smart_light"],
                ),
                ActivitySlot(
                    start_time=time(19, 0),
                    end_time=time(20, 0),
                    primary_activity=ActivityType.EATING,
                    preferred_rooms=[RoomType.DINING_ROOM, RoomType.LIVING_ROOM],
                    device_interactions=["smart_light", "smart_tv"],
                ),
                ActivitySlot(
                    start_time=time(20, 0),
                    end_time=time(22, 0),
                    primary_activity=ActivityType.RELAXING,
                    secondary_activities={
                        ActivityType.ENTERTAINMENT: 0.2,
                        ActivityType.WORKING: 0.1,
                    },
                    preferred_rooms=[RoomType.LIVING_ROOM, RoomType.OFFICE],
                    device_interactions=["smart_tv", "smart_speaker", "smart_light"],
                ),
                ActivitySlot(
                    start_time=time(22, 0),
                    end_time=time(22, 30),
                    primary_activity=ActivityType.PERSONAL_CARE,
                    preferred_rooms=[RoomType.BATHROOM, RoomType.BEDROOM],
                    device_interactions=["smart_light"],
                ),
                ActivitySlot(
                    start_time=time(22, 30),
                    end_time=time(6, 30),
                    primary_activity=ActivityType.SLEEPING,
                    preferred_rooms=[RoomType.BEDROOM],
                    device_interactions=["smart_light", "thermostat", "smart_lock"],
                ),
            ],
        )

    @staticmethod
    def get_adult_weekend_pattern() -> DailyPattern:
        """Standard adult weekend pattern."""
        return DailyPattern(
            name="adult_weekend",
            description="Standard adult weekend routine",
            inhabitant_type=InhabitantType.ADULT,
            day_type=DayType.WEEKEND,
            wake_time=time(8, 30),
            sleep_time=time(23, 30),
            activity_slots=[
                ActivitySlot(
                    start_time=time(8, 30),
                    end_time=time(9, 30),
                    primary_activity=ActivityType.SLEEPING,
                    secondary_activities={ActivityType.PERSONAL_CARE: 0.3},
                    preferred_rooms=[RoomType.BEDROOM],
                ),
                ActivitySlot(
                    start_time=time(9, 30),
                    end_time=time(10, 30),
                    primary_activity=ActivityType.PERSONAL_CARE,
                    preferred_rooms=[RoomType.BATHROOM, RoomType.BEDROOM],
                    device_interactions=["smart_light", "smart_speaker"],
                ),
                ActivitySlot(
                    start_time=time(10, 30),
                    end_time=time(11, 30),
                    primary_activity=ActivityType.EATING,
                    preferred_rooms=[RoomType.KITCHEN, RoomType.DINING_ROOM],
                    device_interactions=["smart_plug", "smart_speaker"],
                ),
                ActivitySlot(
                    start_time=time(11, 30),
                    end_time=time(14, 0),
                    primary_activity=ActivityType.RELAXING,
                    secondary_activities={
                        ActivityType.LEAVING: 0.3,
                        ActivityType.ENTERTAINMENT: 0.2,
                    },
                    preferred_rooms=[RoomType.LIVING_ROOM, RoomType.GARDEN],
                    device_interactions=["smart_tv", "smart_speaker"],
                ),
                ActivitySlot(
                    start_time=time(14, 0),
                    end_time=time(18, 0),
                    primary_activity=ActivityType.RELAXING,
                    secondary_activities={
                        ActivityType.AWAY: 0.4,
                        ActivityType.ENTERTAINMENT: 0.2,
                        ActivityType.EXERCISING: 0.1,
                    },
                    preferred_rooms=[RoomType.LIVING_ROOM, RoomType.GARDEN],
                    device_interactions=["smart_tv", "smart_speaker", "smart_blinds"],
                ),
                ActivitySlot(
                    start_time=time(18, 0),
                    end_time=time(20, 0),
                    primary_activity=ActivityType.COOKING,
                    secondary_activities={ActivityType.EATING: 0.3},
                    preferred_rooms=[RoomType.KITCHEN, RoomType.DINING_ROOM],
                    device_interactions=["smart_plug", "smart_light"],
                ),
                ActivitySlot(
                    start_time=time(20, 0),
                    end_time=time(23, 0),
                    primary_activity=ActivityType.ENTERTAINMENT,
                    secondary_activities={ActivityType.RELAXING: 0.3},
                    preferred_rooms=[RoomType.LIVING_ROOM],
                    device_interactions=["smart_tv", "smart_speaker", "smart_light"],
                ),
                ActivitySlot(
                    start_time=time(23, 0),
                    end_time=time(8, 30),
                    primary_activity=ActivityType.SLEEPING,
                    preferred_rooms=[RoomType.BEDROOM],
                    device_interactions=["smart_light", "thermostat"],
                ),
            ],
        )

    @staticmethod
    def get_work_from_home_pattern() -> DailyPattern:
        """Work from home pattern."""
        return DailyPattern(
            name="adult_wfh",
            description="Work from home routine",
            inhabitant_type=InhabitantType.ADULT,
            day_type=DayType.WORK_FROM_HOME,
            wake_time=time(7, 0),
            sleep_time=time(23, 0),
            activity_slots=[
                ActivitySlot(
                    start_time=time(7, 0),
                    end_time=time(8, 0),
                    primary_activity=ActivityType.PERSONAL_CARE,
                    preferred_rooms=[RoomType.BATHROOM, RoomType.BEDROOM],
                    device_interactions=["smart_light", "smart_speaker"],
                ),
                ActivitySlot(
                    start_time=time(8, 0),
                    end_time=time(8, 30),
                    primary_activity=ActivityType.EATING,
                    preferred_rooms=[RoomType.KITCHEN],
                    device_interactions=["smart_plug"],
                ),
                ActivitySlot(
                    start_time=time(8, 30),
                    end_time=time(12, 0),
                    primary_activity=ActivityType.WORKING,
                    preferred_rooms=[RoomType.OFFICE, RoomType.LIVING_ROOM],
                    device_interactions=["smart_light", "smart_plug", "thermostat"],
                ),
                ActivitySlot(
                    start_time=time(12, 0),
                    end_time=time(13, 0),
                    primary_activity=ActivityType.EATING,
                    preferred_rooms=[RoomType.KITCHEN, RoomType.DINING_ROOM],
                    device_interactions=["smart_plug", "smart_speaker"],
                ),
                ActivitySlot(
                    start_time=time(13, 0),
                    end_time=time(17, 30),
                    primary_activity=ActivityType.WORKING,
                    preferred_rooms=[RoomType.OFFICE, RoomType.LIVING_ROOM],
                    device_interactions=["smart_light", "smart_plug"],
                ),
                ActivitySlot(
                    start_time=time(17, 30),
                    end_time=time(18, 30),
                    primary_activity=ActivityType.EXERCISING,
                    secondary_activities={ActivityType.RELAXING: 0.3},
                    preferred_rooms=[RoomType.LIVING_ROOM, RoomType.GARDEN],
                    device_interactions=["smart_speaker"],
                ),
                ActivitySlot(
                    start_time=time(18, 30),
                    end_time=time(19, 30),
                    primary_activity=ActivityType.COOKING,
                    preferred_rooms=[RoomType.KITCHEN],
                    device_interactions=["smart_plug", "smart_light"],
                ),
                ActivitySlot(
                    start_time=time(19, 30),
                    end_time=time(22, 30),
                    primary_activity=ActivityType.RELAXING,
                    secondary_activities={ActivityType.ENTERTAINMENT: 0.3},
                    preferred_rooms=[RoomType.LIVING_ROOM],
                    device_interactions=["smart_tv", "smart_speaker"],
                ),
                ActivitySlot(
                    start_time=time(22, 30),
                    end_time=time(7, 0),
                    primary_activity=ActivityType.SLEEPING,
                    preferred_rooms=[RoomType.BEDROOM],
                    device_interactions=["smart_light", "thermostat"],
                ),
            ],
        )

    @staticmethod
    def get_child_weekday_pattern() -> DailyPattern:
        """School-age child weekday pattern."""
        return DailyPattern(
            name="child_weekday",
            description="School-age child weekday routine",
            inhabitant_type=InhabitantType.CHILD,
            day_type=DayType.WEEKDAY,
            wake_time=time(7, 0),
            sleep_time=time(21, 0),
            activity_slots=[
                ActivitySlot(
                    start_time=time(7, 0),
                    end_time=time(7, 45),
                    primary_activity=ActivityType.PERSONAL_CARE,
                    preferred_rooms=[RoomType.BATHROOM, RoomType.BEDROOM],
                    device_interactions=["smart_light"],
                ),
                ActivitySlot(
                    start_time=time(7, 45),
                    end_time=time(8, 15),
                    primary_activity=ActivityType.EATING,
                    preferred_rooms=[RoomType.KITCHEN, RoomType.DINING_ROOM],
                ),
                ActivitySlot(
                    start_time=time(8, 15),
                    end_time=time(15, 30),
                    primary_activity=ActivityType.AWAY,  # At school
                    preferred_rooms=[],
                ),
                ActivitySlot(
                    start_time=time(15, 30),
                    end_time=time(17, 0),
                    primary_activity=ActivityType.RELAXING,
                    secondary_activities={ActivityType.ENTERTAINMENT: 0.4},
                    preferred_rooms=[RoomType.LIVING_ROOM, RoomType.BEDROOM],
                    device_interactions=["smart_tv", "smart_speaker"],
                ),
                ActivitySlot(
                    start_time=time(17, 0),
                    end_time=time(18, 30),
                    primary_activity=ActivityType.WORKING,  # Homework
                    preferred_rooms=[RoomType.BEDROOM, RoomType.OFFICE],
                    device_interactions=["smart_light"],
                ),
                ActivitySlot(
                    start_time=time(18, 30),
                    end_time=time(19, 30),
                    primary_activity=ActivityType.EATING,
                    preferred_rooms=[RoomType.DINING_ROOM, RoomType.KITCHEN],
                ),
                ActivitySlot(
                    start_time=time(19, 30),
                    end_time=time(20, 30),
                    primary_activity=ActivityType.ENTERTAINMENT,
                    preferred_rooms=[RoomType.LIVING_ROOM, RoomType.BEDROOM],
                    device_interactions=["smart_tv", "smart_speaker"],
                ),
                ActivitySlot(
                    start_time=time(20, 30),
                    end_time=time(21, 0),
                    primary_activity=ActivityType.PERSONAL_CARE,
                    preferred_rooms=[RoomType.BATHROOM],
                ),
                ActivitySlot(
                    start_time=time(21, 0),
                    end_time=time(7, 0),
                    primary_activity=ActivityType.SLEEPING,
                    preferred_rooms=[RoomType.BEDROOM],
                    device_interactions=["smart_light"],
                ),
            ],
        )

    @staticmethod
    def get_elderly_pattern() -> DailyPattern:
        """Elderly/retired person daily pattern."""
        return DailyPattern(
            name="elderly_daily",
            description="Elderly/retired person daily routine",
            inhabitant_type=InhabitantType.ELDERLY,
            day_type=DayType.WEEKDAY,  # Same for weekday/weekend
            wake_time=time(6, 0),
            sleep_time=time(21, 30),
            activity_slots=[
                ActivitySlot(
                    start_time=time(6, 0),
                    end_time=time(7, 0),
                    primary_activity=ActivityType.PERSONAL_CARE,
                    preferred_rooms=[RoomType.BATHROOM, RoomType.BEDROOM],
                    device_interactions=["smart_light"],
                ),
                ActivitySlot(
                    start_time=time(7, 0),
                    end_time=time(8, 0),
                    primary_activity=ActivityType.EATING,
                    preferred_rooms=[RoomType.KITCHEN, RoomType.DINING_ROOM],
                    device_interactions=["smart_plug"],
                ),
                ActivitySlot(
                    start_time=time(8, 0),
                    end_time=time(10, 0),
                    primary_activity=ActivityType.RELAXING,
                    secondary_activities={ActivityType.EXERCISING: 0.2},
                    preferred_rooms=[RoomType.LIVING_ROOM, RoomType.GARDEN],
                    device_interactions=["smart_tv", "smart_speaker"],
                ),
                ActivitySlot(
                    start_time=time(10, 0),
                    end_time=time(12, 0),
                    primary_activity=ActivityType.RELAXING,
                    secondary_activities={ActivityType.AWAY: 0.3},
                    preferred_rooms=[RoomType.LIVING_ROOM, RoomType.GARDEN],
                    device_interactions=["smart_tv"],
                ),
                ActivitySlot(
                    start_time=time(12, 0),
                    end_time=time(13, 0),
                    primary_activity=ActivityType.EATING,
                    preferred_rooms=[RoomType.KITCHEN, RoomType.DINING_ROOM],
                ),
                ActivitySlot(
                    start_time=time(13, 0),
                    end_time=time(15, 0),
                    primary_activity=ActivityType.SLEEPING,  # Nap
                    secondary_activities={ActivityType.RELAXING: 0.4},
                    preferred_rooms=[RoomType.BEDROOM, RoomType.LIVING_ROOM],
                ),
                ActivitySlot(
                    start_time=time(15, 0),
                    end_time=time(18, 0),
                    primary_activity=ActivityType.RELAXING,
                    secondary_activities={ActivityType.AWAY: 0.2},
                    preferred_rooms=[RoomType.LIVING_ROOM, RoomType.GARDEN],
                    device_interactions=["smart_tv", "smart_speaker"],
                ),
                ActivitySlot(
                    start_time=time(18, 0),
                    end_time=time(19, 0),
                    primary_activity=ActivityType.EATING,
                    preferred_rooms=[RoomType.KITCHEN, RoomType.DINING_ROOM],
                ),
                ActivitySlot(
                    start_time=time(19, 0),
                    end_time=time(21, 0),
                    primary_activity=ActivityType.ENTERTAINMENT,
                    preferred_rooms=[RoomType.LIVING_ROOM],
                    device_interactions=["smart_tv", "smart_light"],
                ),
                ActivitySlot(
                    start_time=time(21, 0),
                    end_time=time(21, 30),
                    primary_activity=ActivityType.PERSONAL_CARE,
                    preferred_rooms=[RoomType.BATHROOM],
                ),
                ActivitySlot(
                    start_time=time(21, 30),
                    end_time=time(6, 0),
                    primary_activity=ActivityType.SLEEPING,
                    preferred_rooms=[RoomType.BEDROOM],
                    device_interactions=["smart_light", "thermostat"],
                ),
            ],
        )

    @classmethod
    def get_weekly_pattern(cls, inhabitant_type: InhabitantType) -> WeeklyPattern:
        """Get a complete weekly pattern for an inhabitant type."""
        if inhabitant_type == InhabitantType.ADULT:
            return WeeklyPattern(
                name="adult_weekly",
                description="Standard adult weekly pattern",
                inhabitant_type=InhabitantType.ADULT,
                weekday_pattern=cls.get_adult_weekday_pattern(),
                weekend_pattern=cls.get_adult_weekend_pattern(),
                work_from_home_pattern=cls.get_work_from_home_pattern(),
            )
        elif inhabitant_type == InhabitantType.CHILD:
            child_weekday = cls.get_child_weekday_pattern()
            child_weekend = DailyPattern(
                name="child_weekend",
                description="Child weekend routine",
                inhabitant_type=InhabitantType.CHILD,
                day_type=DayType.WEEKEND,
                wake_time=time(8, 30),
                sleep_time=time(21, 30),
                activity_slots=[
                    ActivitySlot(
                        start_time=time(8, 30),
                        end_time=time(9, 30),
                        primary_activity=ActivityType.SLEEPING,
                        secondary_activities={ActivityType.PERSONAL_CARE: 0.3},
                        preferred_rooms=[RoomType.BEDROOM],
                    ),
                    ActivitySlot(
                        start_time=time(9, 30),
                        end_time=time(10, 30),
                        primary_activity=ActivityType.EATING,
                        preferred_rooms=[RoomType.KITCHEN],
                    ),
                    ActivitySlot(
                        start_time=time(10, 30),
                        end_time=time(12, 30),
                        primary_activity=ActivityType.ENTERTAINMENT,
                        preferred_rooms=[RoomType.LIVING_ROOM, RoomType.BEDROOM],
                        device_interactions=["smart_tv", "smart_speaker"],
                    ),
                    ActivitySlot(
                        start_time=time(12, 30),
                        end_time=time(13, 30),
                        primary_activity=ActivityType.EATING,
                        preferred_rooms=[RoomType.KITCHEN, RoomType.DINING_ROOM],
                    ),
                    ActivitySlot(
                        start_time=time(13, 30),
                        end_time=time(18, 0),
                        primary_activity=ActivityType.ENTERTAINMENT,
                        secondary_activities={ActivityType.AWAY: 0.3},
                        preferred_rooms=[RoomType.LIVING_ROOM, RoomType.GARDEN],
                        device_interactions=["smart_tv", "smart_speaker"],
                    ),
                    ActivitySlot(
                        start_time=time(18, 0),
                        end_time=time(19, 0),
                        primary_activity=ActivityType.EATING,
                        preferred_rooms=[RoomType.DINING_ROOM],
                    ),
                    ActivitySlot(
                        start_time=time(19, 0),
                        end_time=time(21, 0),
                        primary_activity=ActivityType.ENTERTAINMENT,
                        preferred_rooms=[RoomType.LIVING_ROOM],
                        device_interactions=["smart_tv"],
                    ),
                    ActivitySlot(
                        start_time=time(21, 0),
                        end_time=time(8, 30),
                        primary_activity=ActivityType.SLEEPING,
                        preferred_rooms=[RoomType.BEDROOM],
                    ),
                ],
            )
            return WeeklyPattern(
                name="child_weekly",
                description="Child weekly pattern",
                inhabitant_type=InhabitantType.CHILD,
                weekday_pattern=child_weekday,
                weekend_pattern=child_weekend,
            )
        elif inhabitant_type == InhabitantType.ELDERLY:
            elderly_pattern = cls.get_elderly_pattern()
            return WeeklyPattern(
                name="elderly_weekly",
                description="Elderly weekly pattern (same daily)",
                inhabitant_type=InhabitantType.ELDERLY,
                weekday_pattern=elderly_pattern,
                weekend_pattern=elderly_pattern,  # Same pattern
            )
        else:
            # Default to adult pattern for other types
            return cls.get_weekly_pattern(InhabitantType.ADULT)

    @classmethod
    def get_all_patterns(cls) -> dict[str, DailyPattern]:
        """Get all available daily patterns."""
        return {
            "adult_weekday": cls.get_adult_weekday_pattern(),
            "adult_weekend": cls.get_adult_weekend_pattern(),
            "adult_wfh": cls.get_work_from_home_pattern(),
            "child_weekday": cls.get_child_weekday_pattern(),
            "elderly_daily": cls.get_elderly_pattern(),
        }
