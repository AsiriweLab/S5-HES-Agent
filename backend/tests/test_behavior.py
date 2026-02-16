"""
Tests for Human Behavior Simulation

Unit tests for activity scheduling, occupancy modeling, and behavior engine.
"""

from datetime import datetime, time, timedelta

import pytest

from src.simulation.behavior.activity_scheduler import (
    ActivityScheduler,
    ActivityTransition,
    MarkovActivityModel,
)
from src.simulation.behavior.behavior_engine import (
    BehaviorConfig,
    HumanBehaviorEngine,
)
from src.simulation.behavior.occupancy import (
    OccupancyModel,
    OccupancyState,
)
from src.simulation.behavior.patterns import (
    DailyPattern,
    DayType,
    PatternLibrary,
    WeeklyPattern,
)
from src.simulation.home import HomeGenerator
from src.simulation.models import (
    ActivityType,
    Home,
    HomeTemplate,
    Inhabitant,
    InhabitantType,
    RoomType,
)


# =============================================================================
# Pattern Library Tests
# =============================================================================


class TestPatternLibrary:
    """Tests for pattern library."""

    def test_get_adult_weekday_pattern(self):
        """Test adult weekday pattern."""
        pattern = PatternLibrary.get_adult_weekday_pattern()

        assert pattern is not None
        assert pattern.name == "adult_weekday"
        assert pattern.inhabitant_type == InhabitantType.ADULT
        assert pattern.day_type == DayType.WEEKDAY
        assert len(pattern.activity_slots) > 0

    def test_get_adult_weekend_pattern(self):
        """Test adult weekend pattern."""
        pattern = PatternLibrary.get_adult_weekend_pattern()

        assert pattern is not None
        assert pattern.day_type == DayType.WEEKEND
        # Weekend wake time should be later
        assert pattern.wake_time > time(7, 0)

    def test_get_child_weekday_pattern(self):
        """Test child weekday pattern."""
        pattern = PatternLibrary.get_child_weekday_pattern()

        assert pattern.inhabitant_type == InhabitantType.CHILD
        # Children sleep earlier
        assert pattern.sleep_time < time(22, 0)

    def test_get_elderly_pattern(self):
        """Test elderly pattern."""
        pattern = PatternLibrary.get_elderly_pattern()

        assert pattern.inhabitant_type == InhabitantType.ELDERLY
        # Elderly wake earlier
        assert pattern.wake_time <= time(6, 30)

    def test_get_weekly_pattern_adult(self):
        """Test weekly pattern for adults."""
        weekly = PatternLibrary.get_weekly_pattern(InhabitantType.ADULT)

        assert weekly.weekday_pattern is not None
        assert weekly.weekend_pattern is not None
        assert weekly.work_from_home_pattern is not None

    def test_get_weekly_pattern_child(self):
        """Test weekly pattern for children."""
        weekly = PatternLibrary.get_weekly_pattern(InhabitantType.CHILD)

        assert weekly.inhabitant_type == InhabitantType.CHILD
        assert weekly.weekday_pattern.day_type == DayType.WEEKDAY
        assert weekly.weekend_pattern.day_type == DayType.WEEKEND

    def test_pattern_for_day(self):
        """Test getting pattern for specific day."""
        weekly = PatternLibrary.get_weekly_pattern(InhabitantType.ADULT)

        # Monday (0) should return weekday pattern
        monday_pattern = weekly.get_pattern_for_day(0)
        assert monday_pattern.day_type == DayType.WEEKDAY

        # Saturday (5) should return weekend pattern
        saturday_pattern = weekly.get_pattern_for_day(5)
        assert saturday_pattern.day_type == DayType.WEEKEND

    def test_activity_slot_lookup(self):
        """Test looking up activity for time."""
        pattern = PatternLibrary.get_adult_weekday_pattern()

        # Morning should be personal care or eating
        morning_slot = pattern.get_activity_for_time(time(7, 30))
        assert morning_slot is not None

        # Afternoon should be away (at work)
        afternoon_slot = pattern.get_activity_for_time(time(14, 0))
        assert afternoon_slot is not None
        # For weekday adult, should be AWAY during work hours
        assert afternoon_slot.primary_activity in [ActivityType.AWAY, ActivityType.WORKING]


# =============================================================================
# Markov Activity Model Tests
# =============================================================================


class TestMarkovActivityModel:
    """Tests for Markov activity model."""

    def test_model_initialization(self):
        """Test model initialization."""
        model = MarkovActivityModel(seed=42)

        assert model.morning_matrix is not None
        assert model.daytime_matrix is not None
        assert model.evening_matrix is not None
        assert model.night_matrix is not None

    def test_get_next_activity(self):
        """Test activity transition."""
        model = MarkovActivityModel(seed=42)

        # Test morning transition from sleeping
        next_activity, prob = model.get_next_activity(
            ActivityType.SLEEPING,
            time(7, 0),
            InhabitantType.ADULT,
        )

        assert next_activity is not None
        assert 0 <= prob <= 1

    def test_matrix_selection_by_time(self):
        """Test correct matrix selection for time of day."""
        model = MarkovActivityModel(seed=42)

        # Morning
        morning_matrix = model.get_matrix_for_time(time(7, 30))
        assert morning_matrix is model.morning_matrix

        # Daytime
        day_matrix = model.get_matrix_for_time(time(12, 0))
        assert day_matrix is model.daytime_matrix

        # Evening
        evening_matrix = model.get_matrix_for_time(time(19, 0))
        assert evening_matrix is model.evening_matrix

        # Night
        night_matrix = model.get_matrix_for_time(time(23, 0))
        assert night_matrix is model.night_matrix

    def test_reproducibility(self):
        """Test that same seed produces same results."""
        model1 = MarkovActivityModel(seed=12345)
        model2 = MarkovActivityModel(seed=12345)

        results1 = [
            model1.get_next_activity(ActivityType.SLEEPING, time(7, 0))
            for _ in range(10)
        ]
        results2 = [
            model2.get_next_activity(ActivityType.SLEEPING, time(7, 0))
            for _ in range(10)
        ]

        assert results1 == results2


# =============================================================================
# Activity Scheduler Tests
# =============================================================================


class TestActivityScheduler:
    """Tests for activity scheduler."""

    @pytest.fixture
    def simple_home(self) -> Home:
        """Create a simple home for testing."""
        generator = HomeGenerator(seed=42)
        return generator.generate_from_template(HomeTemplate.TWO_BEDROOM)

    def test_scheduler_initialization(self, simple_home):
        """Test scheduler initialization."""
        scheduler = ActivityScheduler(seed=42)

        for inhabitant in simple_home.inhabitants:
            scheduler.initialize_inhabitant(inhabitant, datetime.utcnow())

        # Check all inhabitants are tracked
        for inhabitant in simple_home.inhabitants:
            state = scheduler.get_activity_state(inhabitant.id)
            assert state is not None

    def test_activity_update(self, simple_home):
        """Test activity updates."""
        scheduler = ActivityScheduler(seed=42)
        current_time = datetime.utcnow()

        # Initialize
        inhabitant = simple_home.inhabitants[0]
        scheduler.initialize_inhabitant(inhabitant, current_time)

        # Create room type mapping
        room_types = {room.id: room.room_type for room in simple_home.rooms}
        room_ids = [room.id for room in simple_home.rooms]

        # Advance time significantly to trigger transition
        future_time = current_time + timedelta(hours=2)
        events = scheduler.update(inhabitant, future_time, room_ids, room_types)

        # Should generate activity events
        assert isinstance(events, list)

    def test_force_activity(self, simple_home):
        """Test forcing activity change."""
        scheduler = ActivityScheduler(seed=42)
        current_time = datetime.utcnow()
        inhabitant = simple_home.inhabitants[0]

        scheduler.initialize_inhabitant(inhabitant, current_time)

        # Force activity change
        event = scheduler.force_activity(
            inhabitant,
            ActivityType.SLEEPING,
            current_time,
            simple_home.rooms[0].id,
        )

        assert event is not None
        assert event.data["to_activity"] == "sleeping"
        assert event.data["trigger"] == "forced"


# =============================================================================
# Occupancy Model Tests
# =============================================================================


class TestOccupancyModel:
    """Tests for occupancy model."""

    @pytest.fixture
    def simple_home(self) -> Home:
        """Create a simple home for testing."""
        generator = HomeGenerator(seed=42)
        return generator.generate_from_template(HomeTemplate.TWO_BEDROOM)

    def test_model_initialization(self, simple_home):
        """Test occupancy model initialization."""
        model = OccupancyModel(simple_home, seed=42)

        assert len(model.room_occupancy) == len(simple_home.rooms)
        assert len(model.inhabitant_locations) == len(simple_home.inhabitants)

    def test_home_state_detection(self, simple_home):
        """Test home state detection."""
        model = OccupancyModel(simple_home, seed=42)

        # All inhabitants start at home
        state = model.get_home_state()
        assert state in [OccupancyState.FULL, OccupancyState.PARTIAL]

    def test_move_inhabitant(self, simple_home):
        """Test moving inhabitant between rooms."""
        model = OccupancyModel(simple_home, seed=42)
        current_time = datetime.utcnow()

        inhabitant_id = simple_home.inhabitants[0].id
        target_room = simple_home.rooms[0].id

        events = model.move_inhabitant(inhabitant_id, target_room, current_time)

        # Should generate movement event
        assert isinstance(events, list)

        # Inhabitant should be in new room
        occupants = model.get_room_occupants(target_room)
        assert inhabitant_id in occupants

    def test_inhabitant_leaves_home(self, simple_home):
        """Test inhabitant leaving home."""
        model = OccupancyModel(simple_home, seed=42)
        current_time = datetime.utcnow()

        inhabitant_id = simple_home.inhabitants[0].id
        events = model.inhabitant_leaves_home(inhabitant_id, current_time)

        # Check inhabitant is marked as away
        location = model.inhabitant_locations[inhabitant_id]
        assert not location.is_home

    def test_room_availability(self, simple_home):
        """Test room availability checking."""
        model = OccupancyModel(simple_home, seed=42)

        room_id = simple_home.rooms[0].id

        # Room should be available initially
        assert model.is_room_available(room_id)

    def test_select_room_for_activity(self, simple_home):
        """Test room selection for activity."""
        model = OccupancyModel(simple_home, seed=42)
        inhabitant_id = simple_home.inhabitants[0].id

        # Select room for sleeping
        room_id = model.select_room_for_activity(
            ActivityType.SLEEPING,
            inhabitant_id,
            [RoomType.BEDROOM, RoomType.MASTER_BEDROOM],
        )

        # Should find a bedroom
        assert room_id is not None or len([
            r for r in simple_home.rooms
            if r.room_type in [RoomType.BEDROOM, RoomType.MASTER_BEDROOM]
        ]) == 0


# =============================================================================
# Human Behavior Engine Tests
# =============================================================================


class TestHumanBehaviorEngine:
    """Tests for the human behavior engine."""

    @pytest.fixture
    def simple_home(self) -> Home:
        """Create a simple home for testing."""
        generator = HomeGenerator(seed=42)
        return generator.generate_from_template(HomeTemplate.TWO_BEDROOM)

    def test_engine_initialization(self, simple_home):
        """Test engine initialization."""
        config = BehaviorConfig(random_seed=42)
        engine = HumanBehaviorEngine(simple_home, config)

        assert len(engine.inhabitant_states) == len(simple_home.inhabitants)
        assert engine.occupancy_model is not None
        assert engine.activity_scheduler is not None

    def test_engine_update(self, simple_home):
        """Test engine update tick."""
        config = BehaviorConfig(
            random_seed=42,
            enable_device_interactions=True,
        )
        engine = HumanBehaviorEngine(simple_home, config)

        current_time = datetime.utcnow()
        events = engine.update(current_time, 60.0)

        assert isinstance(events, list)

    def test_get_occupancy_state(self, simple_home):
        """Test getting occupancy state."""
        engine = HumanBehaviorEngine(simple_home)

        state = engine.get_occupancy_state()
        assert isinstance(state, OccupancyState)

    def test_get_inhabitant_activity(self, simple_home):
        """Test getting inhabitant activity."""
        engine = HumanBehaviorEngine(simple_home)

        inhabitant_id = simple_home.inhabitants[0].id
        activity = engine.get_inhabitant_activity(inhabitant_id)

        assert activity is not None
        assert isinstance(activity, ActivityType)

    def test_force_activity(self, simple_home):
        """Test forcing activity through engine."""
        engine = HumanBehaviorEngine(simple_home)
        current_time = datetime.utcnow()

        inhabitant_id = simple_home.inhabitants[0].id
        event = engine.force_activity(
            inhabitant_id,
            ActivityType.LEAVING,
            current_time,
        )

        assert event is not None

    def test_behavior_stats(self, simple_home):
        """Test behavior statistics."""
        engine = HumanBehaviorEngine(simple_home)

        stats = engine.get_behavior_stats()

        assert "total_events_generated" in stats
        assert "device_interactions" in stats
        assert "occupancy" in stats
        assert "inhabitant_states" in stats
