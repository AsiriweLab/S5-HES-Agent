"""Human Behavior Simulation Module.

Simulates realistic human behavior patterns in smart homes including:
- Activity scheduling (Markov-based transitions)
- Occupancy modeling
- Multi-person coordination
- Daily/weekly patterns
"""

from src.simulation.behavior.activity_scheduler import (
    ActivityScheduler,
    ActivityTransition,
    MarkovActivityModel,
)
from src.simulation.behavior.behavior_engine import (
    HumanBehaviorEngine,
    BehaviorConfig,
)
from src.simulation.behavior.occupancy import (
    OccupancyModel,
    OccupancyState,
)
from src.simulation.behavior.patterns import (
    DailyPattern,
    WeeklyPattern,
    PatternLibrary,
)

__all__ = [
    # Activity Scheduling
    "ActivityScheduler",
    "ActivityTransition",
    "MarkovActivityModel",
    # Behavior Engine
    "HumanBehaviorEngine",
    "BehaviorConfig",
    # Occupancy
    "OccupancyModel",
    "OccupancyState",
    # Patterns
    "DailyPattern",
    "WeeklyPattern",
    "PatternLibrary",
]
