"""
Simulation Environment Interface for RL Training.

Provides a standard RL environment interface (similar to OpenAI Gym)
for the smart home security simulation.
"""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Optional
import json
import random

from loguru import logger


class EnvironmentAction(str, Enum):
    """Actions available in the simulation environment."""
    INCREASE_THREAT_COMPLEXITY = "increase_threat_complexity"
    DECREASE_THREAT_COMPLEXITY = "decrease_threat_complexity"
    INCREASE_DEVICE_COVERAGE = "increase_device_coverage"
    DECREASE_DEVICE_COVERAGE = "decrease_device_coverage"
    INCREASE_BEHAVIOR_DIVERSITY = "increase_behavior_diversity"
    DECREASE_BEHAVIOR_DIVERSITY = "decrease_behavior_diversity"
    BALANCE_DETECTION_FP = "balance_detection_fp"
    OPTIMIZE_PERFORMANCE = "optimize_performance"
    MAINTAIN_CURRENT = "maintain_current"


@dataclass
class EnvironmentState:
    """Current state of the simulation environment."""
    # Detection metrics
    detection_rate: float = 0.5
    false_positive_rate: float = 0.1
    true_positive_count: int = 0
    false_positive_count: int = 0
    missed_threats: int = 0

    # Simulation parameters
    threat_complexity: float = 0.5
    device_coverage: float = 0.5
    behavior_diversity: float = 0.5

    # Performance metrics
    simulation_realism_score: float = 0.5
    avg_response_time_ms: float = 100.0
    resource_utilization: float = 0.5

    # Session info
    step_count: int = 0
    episode_count: int = 0
    timestamp: datetime = field(default_factory=datetime.utcnow)

    def to_vector(self) -> list[float]:
        """Convert state to numeric vector for ML models."""
        return [
            self.detection_rate,
            self.false_positive_rate,
            self.threat_complexity,
            self.device_coverage,
            self.behavior_diversity,
            self.simulation_realism_score,
            min(self.avg_response_time_ms / 1000.0, 1.0),  # Normalize to 0-1
            self.resource_utilization,
        ]

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "detection_rate": self.detection_rate,
            "false_positive_rate": self.false_positive_rate,
            "true_positive_count": self.true_positive_count,
            "false_positive_count": self.false_positive_count,
            "missed_threats": self.missed_threats,
            "threat_complexity": self.threat_complexity,
            "device_coverage": self.device_coverage,
            "behavior_diversity": self.behavior_diversity,
            "simulation_realism_score": self.simulation_realism_score,
            "avg_response_time_ms": self.avg_response_time_ms,
            "resource_utilization": self.resource_utilization,
            "step_count": self.step_count,
            "episode_count": self.episode_count,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "EnvironmentState":
        """Create from dictionary."""
        return cls(
            detection_rate=data.get("detection_rate", 0.5),
            false_positive_rate=data.get("false_positive_rate", 0.1),
            true_positive_count=data.get("true_positive_count", 0),
            false_positive_count=data.get("false_positive_count", 0),
            missed_threats=data.get("missed_threats", 0),
            threat_complexity=data.get("threat_complexity", 0.5),
            device_coverage=data.get("device_coverage", 0.5),
            behavior_diversity=data.get("behavior_diversity", 0.5),
            simulation_realism_score=data.get("simulation_realism_score", 0.5),
            avg_response_time_ms=data.get("avg_response_time_ms", 100.0),
            resource_utilization=data.get("resource_utilization", 0.5),
            step_count=data.get("step_count", 0),
            episode_count=data.get("episode_count", 0),
        )


@dataclass
class EnvironmentReward:
    """Reward signal from the environment."""
    total: float
    detection_component: float
    fp_penalty_component: float
    realism_component: float
    performance_component: float
    info: dict = field(default_factory=dict)


class SimulationEnvironment:
    """
    RL Environment interface for the smart home security simulation.

    Provides gym-like interface with:
    - reset(): Initialize new episode
    - step(action): Take action and receive (state, reward, done, info)
    - render(): Visualize current state (optional)
    """

    def __init__(
        self,
        max_steps: int = 100,
        target_detection_rate: float = 0.85,
        max_fp_rate: float = 0.15,
        use_real_simulation: bool = False,
    ):
        """
        Initialize the simulation environment.

        Args:
            max_steps: Maximum steps per episode
            target_detection_rate: Target detection rate for optimal rewards
            max_fp_rate: Maximum acceptable false positive rate
            use_real_simulation: Whether to use actual simulation engine
        """
        self.max_steps = max_steps
        self.target_detection_rate = target_detection_rate
        self.max_fp_rate = max_fp_rate
        self.use_real_simulation = use_real_simulation

        # Current state
        self.state = EnvironmentState()
        self.episode_rewards: list[float] = []
        self.step_in_episode = 0

        # Action space
        self.action_space = list(EnvironmentAction)
        self.n_actions = len(self.action_space)

        # State space dimensions
        self.state_dim = len(self.state.to_vector())

        # Statistics
        self._stats = {
            "total_episodes": 0,
            "total_steps": 0,
            "best_episode_reward": float("-inf"),
            "avg_episode_reward": 0.0,
        }

        logger.info(f"SimulationEnvironment initialized: {self.n_actions} actions, {self.state_dim}D state")

    def reset(self, seed: Optional[int] = None) -> EnvironmentState:
        """
        Reset environment for new episode.

        Args:
            seed: Random seed for reproducibility

        Returns:
            Initial state
        """
        if seed is not None:
            random.seed(seed)

        # Record episode stats
        if self.episode_rewards:
            episode_total = sum(self.episode_rewards)
            self._stats["total_episodes"] += 1
            if episode_total > self._stats["best_episode_reward"]:
                self._stats["best_episode_reward"] = episode_total

            # Update running average
            n = self._stats["total_episodes"]
            self._stats["avg_episode_reward"] = (
                self._stats["avg_episode_reward"] * (n - 1) + episode_total
            ) / n

        # Reset state
        self.state = EnvironmentState(
            detection_rate=random.uniform(0.3, 0.7),
            false_positive_rate=random.uniform(0.05, 0.25),
            threat_complexity=random.uniform(0.3, 0.7),
            device_coverage=random.uniform(0.3, 0.7),
            behavior_diversity=random.uniform(0.3, 0.7),
            simulation_realism_score=random.uniform(0.4, 0.6),
            avg_response_time_ms=random.uniform(50, 200),
            resource_utilization=random.uniform(0.3, 0.7),
            episode_count=self._stats["total_episodes"],
        )

        self.episode_rewards = []
        self.step_in_episode = 0

        return self.state

    def step(
        self,
        action: EnvironmentAction | str | int,
    ) -> tuple[EnvironmentState, EnvironmentReward, bool, dict]:
        """
        Execute action and return new state.

        Args:
            action: Action to take (enum, string, or index)

        Returns:
            Tuple of (state, reward, done, info)
        """
        # Convert action
        if isinstance(action, int):
            action = self.action_space[action]
        elif isinstance(action, str):
            action = EnvironmentAction(action)

        # Apply action to simulation parameters
        self._apply_action(action)

        # Simulate effects (or use real simulation if enabled)
        if self.use_real_simulation:
            self._run_real_simulation()
        else:
            self._simulate_effects(action)

        # Calculate reward
        reward = self._calculate_reward()
        self.episode_rewards.append(reward.total)

        # Update counters
        self.step_in_episode += 1
        self.state.step_count = self.step_in_episode
        self._stats["total_steps"] += 1

        # Check if episode is done
        done = self._is_done()

        # Build info dict
        info = {
            "action_taken": action.value,
            "step_in_episode": self.step_in_episode,
            "episode_reward_so_far": sum(self.episode_rewards),
            "reward_breakdown": {
                "detection": reward.detection_component,
                "fp_penalty": reward.fp_penalty_component,
                "realism": reward.realism_component,
                "performance": reward.performance_component,
            },
        }

        return self.state, reward, done, info

    def _apply_action(self, action: EnvironmentAction) -> None:
        """Apply action to modify simulation parameters."""
        step = 0.1

        if action == EnvironmentAction.INCREASE_THREAT_COMPLEXITY:
            self.state.threat_complexity = min(1.0, self.state.threat_complexity + step)
        elif action == EnvironmentAction.DECREASE_THREAT_COMPLEXITY:
            self.state.threat_complexity = max(0.0, self.state.threat_complexity - step)
        elif action == EnvironmentAction.INCREASE_DEVICE_COVERAGE:
            self.state.device_coverage = min(1.0, self.state.device_coverage + step)
        elif action == EnvironmentAction.DECREASE_DEVICE_COVERAGE:
            self.state.device_coverage = max(0.0, self.state.device_coverage - step)
        elif action == EnvironmentAction.INCREASE_BEHAVIOR_DIVERSITY:
            self.state.behavior_diversity = min(1.0, self.state.behavior_diversity + step)
        elif action == EnvironmentAction.DECREASE_BEHAVIOR_DIVERSITY:
            self.state.behavior_diversity = max(0.0, self.state.behavior_diversity - step)
        elif action == EnvironmentAction.BALANCE_DETECTION_FP:
            # Adjust both detection and FP rates
            if self.state.detection_rate < 0.7:
                self.state.detection_rate = min(1.0, self.state.detection_rate + 0.05)
            if self.state.false_positive_rate > 0.1:
                self.state.false_positive_rate = max(0.0, self.state.false_positive_rate - 0.03)
        elif action == EnvironmentAction.OPTIMIZE_PERFORMANCE:
            self.state.avg_response_time_ms = max(50, self.state.avg_response_time_ms * 0.9)
            self.state.resource_utilization = max(0.2, self.state.resource_utilization - 0.05)

    def _simulate_effects(self, action: EnvironmentAction) -> None:
        """Simulate the effects of parameter changes on detection metrics."""
        # Higher threat complexity makes detection harder
        complexity_penalty = self.state.threat_complexity * 0.3

        # Higher device coverage improves detection
        coverage_bonus = self.state.device_coverage * 0.2

        # Higher behavior diversity makes anomaly detection more challenging
        diversity_penalty = (self.state.behavior_diversity - 0.5) * 0.1

        # Base detection rate influenced by parameters
        base_detection = 0.6 + coverage_bonus - complexity_penalty - diversity_penalty

        # Add some randomness
        noise = random.gauss(0, 0.05)
        self.state.detection_rate = max(0.0, min(1.0, base_detection + noise))

        # False positive rate influenced by coverage and diversity
        base_fp = 0.1 + self.state.device_coverage * 0.05 + self.state.behavior_diversity * 0.05
        fp_noise = random.gauss(0, 0.02)
        self.state.false_positive_rate = max(0.0, min(0.5, base_fp + fp_noise))

        # Realism score based on diversity and complexity
        self.state.simulation_realism_score = (
            0.4 + self.state.behavior_diversity * 0.3 + self.state.threat_complexity * 0.2
        ) + random.gauss(0, 0.05)
        self.state.simulation_realism_score = max(0.0, min(1.0, self.state.simulation_realism_score))

        # Update response time based on coverage
        self.state.avg_response_time_ms = (
            80 + self.state.device_coverage * 50 + self.state.threat_complexity * 30
        ) + random.gauss(0, 10)
        self.state.avg_response_time_ms = max(50, self.state.avg_response_time_ms)

    def _run_real_simulation(self) -> None:
        """Run actual simulation and update state with results."""
        # This would interface with the actual simulation engine
        # For now, use simulated effects
        self._simulate_effects(EnvironmentAction.MAINTAIN_CURRENT)

    def _calculate_reward(self) -> EnvironmentReward:
        """Calculate reward based on current state."""
        # Detection component: reward for high detection rate
        detection_reward = (self.state.detection_rate - 0.5) * 2.0

        # FP penalty: penalize high false positive rates
        fp_penalty = -max(0, self.state.false_positive_rate - self.max_fp_rate) * 5.0

        # Realism component: reward realistic simulations
        realism_reward = (self.state.simulation_realism_score - 0.5) * 0.5

        # Performance component: small penalty for slow response times
        perf_penalty = -max(0, (self.state.avg_response_time_ms - 200) / 500) * 0.2

        # Bonus for reaching target
        target_bonus = 0.0
        if self.state.detection_rate >= self.target_detection_rate:
            if self.state.false_positive_rate <= self.max_fp_rate:
                target_bonus = 1.0

        total = detection_reward + fp_penalty + realism_reward + perf_penalty + target_bonus

        return EnvironmentReward(
            total=total,
            detection_component=detection_reward,
            fp_penalty_component=fp_penalty,
            realism_component=realism_reward,
            performance_component=perf_penalty,
            info={"target_bonus": target_bonus},
        )

    def _is_done(self) -> bool:
        """Check if episode should terminate."""
        # Maximum steps reached
        if self.step_in_episode >= self.max_steps:
            return True

        # Achieved optimal state (early termination bonus)
        if (
            self.state.detection_rate >= self.target_detection_rate
            and self.state.false_positive_rate <= self.max_fp_rate
        ):
            return True

        return False

    def render(self, mode: str = "text") -> Optional[str]:
        """
        Render current state.

        Args:
            mode: Rendering mode ('text' or 'json')

        Returns:
            String representation of state
        """
        if mode == "json":
            return json.dumps(self.state.to_dict(), indent=2)

        return (
            f"Step {self.step_in_episode}/{self.max_steps}\n"
            f"Detection: {self.state.detection_rate:.2%} | FP: {self.state.false_positive_rate:.2%}\n"
            f"Complexity: {self.state.threat_complexity:.2f} | Coverage: {self.state.device_coverage:.2f}\n"
            f"Realism: {self.state.simulation_realism_score:.2f} | Response: {self.state.avg_response_time_ms:.0f}ms"
        )

    def get_stats(self) -> dict:
        """Get environment statistics."""
        return {
            **self._stats,
            "current_episode_reward": sum(self.episode_rewards) if self.episode_rewards else 0,
            "current_step": self.step_in_episode,
        }

    def close(self) -> None:
        """Clean up environment resources."""
        logger.info(f"Environment closed. Total: {self._stats['total_episodes']} episodes, {self._stats['total_steps']} steps")
