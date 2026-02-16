"""
Optimization Agent for the Smart-HES Agent Framework.

Provides reinforcement learning-based parameter optimization for:
- Threat scenario complexity tuning based on detection rates
- Device placement optimization based on coverage analysis
- Behavior pattern learning from simulation runs
- Agent configuration adaptation based on performance feedback

This agent implements FR-13.04: Agent-based simulation parameter optimization.
"""

import time
import random
import json
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional
from pathlib import Path

from loguru import logger

from src.ai.agents.base_agent import (
    AbstractAgent,
    AgentMessage,
    AgentResult,
    AgentState,
    AgentTask,
    MessageType,
)


@dataclass
class Experience:
    """A single experience tuple for RL learning."""
    state: dict
    action: str
    reward: float
    next_state: dict
    done: bool
    timestamp: datetime = field(default_factory=datetime.utcnow)
    metadata: dict = field(default_factory=dict)


@dataclass
class OptimizationState:
    """Current state representation for RL optimization."""
    # Simulation metrics
    detection_rate: float = 0.0  # 0-1, threats detected / total threats
    false_positive_rate: float = 0.0  # 0-1, false alarms / total alarms
    simulation_realism_score: float = 0.5  # 0-1, how realistic the simulation

    # Configuration metrics
    threat_complexity: float = 0.5  # 0-1, current threat difficulty
    device_coverage: float = 0.5  # 0-1, sensor/device coverage
    behavior_diversity: float = 0.5  # 0-1, inhabitant behavior variety

    # Performance metrics
    avg_response_time_ms: float = 100.0  # Average system response time
    resource_utilization: float = 0.5  # 0-1, CPU/memory usage

    def to_dict(self) -> dict:
        return {
            "detection_rate": self.detection_rate,
            "false_positive_rate": self.false_positive_rate,
            "simulation_realism_score": self.simulation_realism_score,
            "threat_complexity": self.threat_complexity,
            "device_coverage": self.device_coverage,
            "behavior_diversity": self.behavior_diversity,
            "avg_response_time_ms": self.avg_response_time_ms,
            "resource_utilization": self.resource_utilization,
        }

    def to_tuple(self) -> tuple:
        """Convert to discretized state tuple for Q-table lookup."""
        # Discretize each dimension to 10 bins
        def discretize(val: float, bins: int = 10) -> int:
            return min(bins - 1, max(0, int(val * bins)))

        return (
            discretize(self.detection_rate),
            discretize(self.false_positive_rate),
            discretize(self.simulation_realism_score),
            discretize(self.threat_complexity),
            discretize(self.device_coverage),
        )

    @classmethod
    def from_dict(cls, data: dict) -> "OptimizationState":
        return cls(**{k: v for k, v in data.items() if hasattr(cls, k)})


class ReplayBuffer:
    """Experience replay buffer for RL training."""

    def __init__(self, max_size: int = 10000):
        self.buffer: list[Experience] = []
        self.max_size = max_size
        self.position = 0

    def add(self, experience: Experience) -> None:
        """Add experience to buffer."""
        if len(self.buffer) < self.max_size:
            self.buffer.append(experience)
        else:
            self.buffer[self.position] = experience
        self.position = (self.position + 1) % self.max_size

    def sample(self, batch_size: int) -> list[Experience]:
        """Sample a random batch of experiences."""
        batch_size = min(batch_size, len(self.buffer))
        return random.sample(self.buffer, batch_size)

    def __len__(self) -> int:
        return len(self.buffer)

    def save(self, path: Path) -> None:
        """Save buffer to disk."""
        data = [
            {
                "state": e.state,
                "action": e.action,
                "reward": e.reward,
                "next_state": e.next_state,
                "done": e.done,
                "timestamp": e.timestamp.isoformat(),
                "metadata": e.metadata,
            }
            for e in self.buffer
        ]
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            json.dump(data, f, indent=2)

    def load(self, path: Path) -> None:
        """Load buffer from disk."""
        if not path.exists():
            return
        with open(path) as f:
            data = json.load(f)
        self.buffer = [
            Experience(
                state=d["state"],
                action=d["action"],
                reward=d["reward"],
                next_state=d["next_state"],
                done=d["done"],
                timestamp=datetime.fromisoformat(d["timestamp"]),
                metadata=d.get("metadata", {}),
            )
            for d in data
        ]
        self.position = len(self.buffer) % self.max_size


class QLearningOptimizer:
    """
    Tabular Q-Learning optimizer for simulation parameter tuning.

    Uses epsilon-greedy exploration with decaying epsilon.
    """

    # Available actions for parameter adjustment
    ACTIONS = [
        "increase_threat_complexity",
        "decrease_threat_complexity",
        "increase_device_coverage",
        "decrease_device_coverage",
        "increase_behavior_diversity",
        "decrease_behavior_diversity",
        "balance_detection_fp",  # Balance detection vs false positives
        "optimize_performance",  # Reduce response time
        "maintain_current",  # No change
    ]

    def __init__(
        self,
        learning_rate: float = 0.1,
        discount_factor: float = 0.95,
        epsilon_start: float = 1.0,
        epsilon_end: float = 0.1,
        epsilon_decay: float = 0.995,
    ):
        self.lr = learning_rate
        self.gamma = discount_factor
        self.epsilon = epsilon_start
        self.epsilon_end = epsilon_end
        self.epsilon_decay = epsilon_decay

        # Q-table: state -> action -> value
        self.q_table: dict[tuple, dict[str, float]] = defaultdict(
            lambda: {a: 0.0 for a in self.ACTIONS}
        )

        # Training statistics
        self.episode_count = 0
        self.total_reward = 0.0
        self.reward_history: list[float] = []

    def select_action(self, state: OptimizationState, explore: bool = True) -> str:
        """Select action using epsilon-greedy policy."""
        if explore and random.random() < self.epsilon:
            return random.choice(self.ACTIONS)

        state_key = state.to_tuple()
        q_values = self.q_table[state_key]
        max_q = max(q_values.values())
        best_actions = [a for a, q in q_values.items() if q == max_q]
        return random.choice(best_actions)

    def update(
        self,
        state: OptimizationState,
        action: str,
        reward: float,
        next_state: OptimizationState,
        done: bool,
    ) -> float:
        """Update Q-value using Q-learning update rule."""
        state_key = state.to_tuple()
        next_state_key = next_state.to_tuple()

        current_q = self.q_table[state_key][action]

        if done:
            target = reward
        else:
            next_max_q = max(self.q_table[next_state_key].values())
            target = reward + self.gamma * next_max_q

        # Q-learning update
        new_q = current_q + self.lr * (target - current_q)
        self.q_table[state_key][action] = new_q

        return new_q - current_q  # Return TD error

    def decay_epsilon(self) -> None:
        """Decay exploration rate."""
        self.epsilon = max(self.epsilon_end, self.epsilon * self.epsilon_decay)

    def end_episode(self, episode_reward: float) -> None:
        """Mark end of episode and update statistics."""
        self.episode_count += 1
        self.total_reward += episode_reward
        self.reward_history.append(episode_reward)
        self.decay_epsilon()

    def get_statistics(self) -> dict:
        """Get training statistics."""
        recent_rewards = self.reward_history[-100:] if self.reward_history else []
        return {
            "episode_count": self.episode_count,
            "total_reward": self.total_reward,
            "average_reward": sum(recent_rewards) / len(recent_rewards) if recent_rewards else 0,
            "epsilon": self.epsilon,
            "q_table_size": len(self.q_table),
        }

    def save(self, path: Path) -> None:
        """Save Q-table and statistics to disk."""
        data = {
            "q_table": {str(k): v for k, v in self.q_table.items()},
            "epsilon": self.epsilon,
            "episode_count": self.episode_count,
            "total_reward": self.total_reward,
            "reward_history": self.reward_history[-1000:],  # Keep last 1000
        }
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            json.dump(data, f, indent=2)

    def load(self, path: Path) -> None:
        """Load Q-table and statistics from disk."""
        if not path.exists():
            return
        with open(path) as f:
            data = json.load(f)

        # Restore Q-table with proper default dict behavior
        for k, v in data.get("q_table", {}).items():
            state_key = eval(k)  # Convert string back to tuple
            self.q_table[state_key] = v

        self.epsilon = data.get("epsilon", self.epsilon)
        self.episode_count = data.get("episode_count", 0)
        self.total_reward = data.get("total_reward", 0.0)
        self.reward_history = data.get("reward_history", [])


class OptimizationAgent(AbstractAgent):
    """
    Agent responsible for RL-based parameter optimization.

    Capabilities:
    - Optimize simulation parameters based on feedback
    - Learn from simulation results to improve realism
    - Adapt threat complexity based on detection performance
    - Provide parameter recommendations to other agents
    """

    def __init__(
        self,
        agent_id: Optional[str] = None,
        data_dir: Optional[Path] = None,
    ):
        super().__init__(
            agent_id=agent_id,
            name="Optimizer",
            description="RL-based parameter optimization for simulation tuning",
        )

        self.data_dir = data_dir or Path("data/optimization")
        self.data_dir.mkdir(parents=True, exist_ok=True)

        # RL components
        self.optimizer = QLearningOptimizer()
        self.replay_buffer = ReplayBuffer(max_size=10000)

        # Current state tracking
        self.current_state = OptimizationState()
        self.episode_reward = 0.0
        self.episode_steps = 0

        # Feedback tracking from other agents
        self.pending_feedback: list[dict] = []

        # Register tools
        self._register_tools()

        # Try to load saved state
        self._load_state()

        logger.info(f"OptimizationAgent initialized: {self.agent_id}")

    @property
    def agent_type(self) -> str:
        return "optimization"

    @property
    def capabilities(self) -> list[str]:
        return [
            "optimize_parameters",
            "analyze_performance",
            "suggest_improvements",
            "adapt_threat_scenarios",
            "evaluate_strategy",
            "learn_from_feedback",
            "get_recommendations",
            "reset_learning",
        ]

    def _register_tools(self) -> None:
        """Register available tools for this agent."""
        self.register_tool(
            "calculate_reward",
            self._calculate_reward,
            "Calculate reward signal from simulation metrics",
        )
        self.register_tool(
            "apply_action",
            self._apply_action,
            "Apply parameter adjustment action",
        )
        self.register_tool(
            "get_optimal_params",
            self._get_optimal_params,
            "Get optimal parameters based on learned policy",
        )

    async def execute_task(self, task: AgentTask) -> AgentResult:
        """Execute an optimization task."""
        start_time = time.perf_counter()
        self.set_state(AgentState.EXECUTING)
        self._current_task = task

        try:
            result = None

            if task.task_type == "optimize_parameters":
                result = await self._optimize_parameters(task.parameters)
            elif task.task_type == "analyze_performance":
                result = await self._analyze_performance(task.parameters)
            elif task.task_type == "suggest_improvements":
                result = await self._suggest_improvements(task.parameters)
            elif task.task_type == "adapt_threat_scenarios":
                result = await self._adapt_threat_scenarios(task.parameters)
            elif task.task_type == "evaluate_strategy":
                result = await self._evaluate_strategy(task.parameters)
            elif task.task_type == "learn_from_feedback":
                result = await self._learn_from_feedback(task.parameters)
            elif task.task_type == "get_recommendations":
                result = await self._get_recommendations(task.parameters)
            elif task.task_type == "reset_learning":
                result = await self._reset_learning(task.parameters)
            else:
                result = {
                    "error": f"Unknown task type: {task.task_type}",
                    "available_tasks": self.capabilities,
                }

            execution_time = (time.perf_counter() - start_time) * 1000
            self.set_state(AgentState.IDLE)

            agent_result = AgentResult(
                success=True,
                data=result,
                execution_time_ms=execution_time,
            )
            self._record_task_completion(task, agent_result)
            return agent_result

        except Exception as e:
            logger.error(f"OptimizationAgent task failed: {e}", exc_info=True)
            execution_time = (time.perf_counter() - start_time) * 1000
            self.set_state(AgentState.ERROR)

            agent_result = AgentResult(
                success=False,
                error=str(e),
                execution_time_ms=execution_time,
            )
            self._record_task_completion(task, agent_result)
            return agent_result

    async def handle_message(self, message: AgentMessage) -> Optional[AgentMessage]:
        """Handle incoming messages from other agents."""
        if message.message_type == MessageType.REQUEST:
            action = message.content.get("action")
            params = message.content.get("parameters", {})

            task = AgentTask.create(
                task_type=action,
                description=f"Request from {message.sender}",
                parameters=params,
            )

            result = await self.execute_task(task)

            return AgentMessage.create(
                sender=self.agent_id,
                receiver=message.sender,
                message_type=MessageType.RESPONSE,
                content=result.to_dict(),
                correlation_id=message.message_id,
            )

        elif message.message_type == MessageType.NOTIFICATION:
            # Handle feedback notifications from other agents
            feedback_type = message.content.get("type")

            if feedback_type == "simulation_result":
                # Store simulation result for learning
                self.pending_feedback.append({
                    "source": message.sender,
                    "type": "simulation_result",
                    "data": message.content.get("data", {}),
                    "timestamp": datetime.utcnow(),
                })

            elif feedback_type == "detection_result":
                # Store detection performance feedback
                self.pending_feedback.append({
                    "source": message.sender,
                    "type": "detection_result",
                    "data": message.content.get("data", {}),
                    "timestamp": datetime.utcnow(),
                })

            return None

        return None

    # ========== Core Optimization Methods ==========

    async def _optimize_parameters(self, params: dict) -> dict:
        """
        Main optimization loop - select and apply action based on current state.
        """
        # Update state from provided metrics
        if "metrics" in params:
            self._update_state_from_metrics(params["metrics"])

        # Select action using RL policy
        action = self.optimizer.select_action(self.current_state, explore=True)

        # Apply action to get parameter adjustments
        adjustments = self._apply_action(action)

        # If we have feedback, calculate reward and learn
        if self.pending_feedback:
            reward = self._calculate_reward_from_feedback()
            next_state = OptimizationState.from_dict(self.current_state.to_dict())

            # Store experience
            experience = Experience(
                state=self.current_state.to_dict(),
                action=action,
                reward=reward,
                next_state=next_state.to_dict(),
                done=False,
            )
            self.replay_buffer.add(experience)

            # Learn from experience
            self.optimizer.update(
                self.current_state,
                action,
                reward,
                next_state,
                done=False,
            )

            self.episode_reward += reward
            self.episode_steps += 1
            self.pending_feedback.clear()

        return {
            "action": action,
            "adjustments": adjustments,
            "current_state": self.current_state.to_dict(),
            "episode_reward": self.episode_reward,
            "episode_steps": self.episode_steps,
            "optimizer_stats": self.optimizer.get_statistics(),
        }

    async def _analyze_performance(self, params: dict) -> dict:
        """Analyze current simulation performance."""
        metrics = params.get("metrics", {})
        self._update_state_from_metrics(metrics)

        # Calculate various performance scores
        detection_score = self.current_state.detection_rate
        fp_penalty = self.current_state.false_positive_rate * 0.5
        realism_score = self.current_state.simulation_realism_score

        overall_score = (
            detection_score * 0.4 +
            (1 - fp_penalty) * 0.3 +
            realism_score * 0.3
        )

        # Identify bottlenecks
        bottlenecks = []
        if self.current_state.detection_rate < 0.6:
            bottlenecks.append("low_detection_rate")
        if self.current_state.false_positive_rate > 0.3:
            bottlenecks.append("high_false_positive_rate")
        if self.current_state.simulation_realism_score < 0.5:
            bottlenecks.append("low_realism")
        if self.current_state.avg_response_time_ms > 500:
            bottlenecks.append("slow_response_time")

        return {
            "overall_score": overall_score,
            "detection_score": detection_score,
            "false_positive_penalty": fp_penalty,
            "realism_score": realism_score,
            "bottlenecks": bottlenecks,
            "current_state": self.current_state.to_dict(),
        }

    async def _suggest_improvements(self, params: dict) -> dict:
        """Suggest parameter improvements based on learned policy."""
        # Get best action from policy (no exploration)
        best_action = self.optimizer.select_action(self.current_state, explore=False)

        # Get Q-values for all actions
        state_key = self.current_state.to_tuple()
        q_values = dict(self.optimizer.q_table[state_key])

        # Sort actions by Q-value
        sorted_actions = sorted(q_values.items(), key=lambda x: x[1], reverse=True)

        suggestions = []
        for action, q_value in sorted_actions[:3]:
            suggestion = {
                "action": action,
                "expected_value": q_value,
                "description": self._get_action_description(action),
                "adjustments": self._apply_action(action),
            }
            suggestions.append(suggestion)

        return {
            "best_action": best_action,
            "suggestions": suggestions,
            "confidence": q_values.get(best_action, 0),
            "exploration_rate": self.optimizer.epsilon,
        }

    async def _adapt_threat_scenarios(self, params: dict) -> dict:
        """Adapt threat complexity based on detection performance."""
        detection_rate = params.get("detection_rate", self.current_state.detection_rate)
        false_positive_rate = params.get("false_positive_rate", self.current_state.false_positive_rate)

        # Update state
        self.current_state.detection_rate = detection_rate
        self.current_state.false_positive_rate = false_positive_rate

        # Determine adjustment
        if detection_rate > 0.9 and false_positive_rate < 0.1:
            # Too easy - increase complexity
            adjustment = "increase"
            new_complexity = min(1.0, self.current_state.threat_complexity + 0.1)
        elif detection_rate < 0.5:
            # Too hard - decrease complexity
            adjustment = "decrease"
            new_complexity = max(0.0, self.current_state.threat_complexity - 0.1)
        else:
            # Balanced - maintain
            adjustment = "maintain"
            new_complexity = self.current_state.threat_complexity

        self.current_state.threat_complexity = new_complexity

        return {
            "adjustment": adjustment,
            "previous_complexity": params.get("current_complexity", 0.5),
            "new_complexity": new_complexity,
            "detection_rate": detection_rate,
            "false_positive_rate": false_positive_rate,
            "recommendation": self._get_complexity_recommendation(new_complexity),
        }

    async def _evaluate_strategy(self, params: dict) -> dict:
        """Evaluate current optimization strategy effectiveness."""
        stats = self.optimizer.get_statistics()

        # Calculate strategy metrics
        recent_rewards = self.optimizer.reward_history[-50:]
        if len(recent_rewards) > 10:
            early_avg = sum(recent_rewards[:len(recent_rewards)//2]) / (len(recent_rewards)//2)
            late_avg = sum(recent_rewards[len(recent_rewards)//2:]) / (len(recent_rewards)//2)
            improvement = late_avg - early_avg
        else:
            improvement = 0.0

        return {
            "episode_count": stats["episode_count"],
            "average_reward": stats["average_reward"],
            "improvement_trend": improvement,
            "exploration_rate": stats["epsilon"],
            "learned_states": stats["q_table_size"],
            "buffer_size": len(self.replay_buffer),
            "convergence_status": "converging" if improvement > 0 else "exploring",
        }

    async def _learn_from_feedback(self, params: dict) -> dict:
        """Process pending feedback and update policy."""
        if not self.pending_feedback:
            return {"message": "No pending feedback to process"}

        processed = 0
        total_reward = 0.0

        for feedback in self.pending_feedback:
            metrics = feedback.get("data", {})
            self._update_state_from_metrics(metrics)

            reward = self._calculate_reward_from_metrics(metrics)
            total_reward += reward
            processed += 1

        self.pending_feedback.clear()

        return {
            "processed_feedback": processed,
            "total_reward": total_reward,
            "average_reward": total_reward / processed if processed > 0 else 0,
            "current_state": self.current_state.to_dict(),
        }

    async def _get_recommendations(self, params: dict) -> dict:
        """Get parameter recommendations for other agents."""
        target_agent = params.get("target_agent", "all")

        recommendations = {}

        if target_agent in ["all", "threat_injector"]:
            recommendations["threat_injector"] = {
                "complexity": self.current_state.threat_complexity,
                "suggested_threats": self._suggest_threat_types(),
            }

        if target_agent in ["all", "device_manager"]:
            recommendations["device_manager"] = {
                "coverage_target": self.current_state.device_coverage,
                "suggested_placement": self._suggest_device_placement(),
            }

        if target_agent in ["all", "home_builder"]:
            recommendations["home_builder"] = {
                "behavior_diversity": self.current_state.behavior_diversity,
                "suggested_profiles": self._suggest_inhabitant_profiles(),
            }

        return {
            "recommendations": recommendations,
            "confidence": 1.0 - self.optimizer.epsilon,
            "based_on_episodes": self.optimizer.episode_count,
        }

    async def _reset_learning(self, params: dict) -> dict:
        """Reset learning state (optionally keeping Q-table)."""
        keep_knowledge = params.get("keep_knowledge", False)

        if not keep_knowledge:
            self.optimizer = QLearningOptimizer()
            self.replay_buffer = ReplayBuffer()

        self.current_state = OptimizationState()
        self.episode_reward = 0.0
        self.episode_steps = 0
        self.pending_feedback.clear()

        return {
            "message": "Learning state reset",
            "kept_knowledge": keep_knowledge,
            "new_state": self.current_state.to_dict(),
        }

    # ========== Helper Methods ==========

    def _update_state_from_metrics(self, metrics: dict) -> None:
        """Update current state from provided metrics."""
        if "detection_rate" in metrics:
            self.current_state.detection_rate = metrics["detection_rate"]
        if "false_positive_rate" in metrics:
            self.current_state.false_positive_rate = metrics["false_positive_rate"]
        if "realism_score" in metrics:
            self.current_state.simulation_realism_score = metrics["realism_score"]
        if "response_time_ms" in metrics:
            self.current_state.avg_response_time_ms = metrics["response_time_ms"]
        if "resource_utilization" in metrics:
            self.current_state.resource_utilization = metrics["resource_utilization"]

    def _calculate_reward(self, metrics: dict | OptimizationState) -> float:
        """Calculate reward signal from metrics.

        Args:
            metrics: Either a dict with metric values or an OptimizationState object.
                    If OptimizationState is provided, it will be converted to dict.

        Returns:
            Calculated reward value in range [-1, 1].
        """
        if isinstance(metrics, OptimizationState):
            metrics = metrics.to_dict()
        return self._calculate_reward_from_metrics(metrics)

    def _calculate_reward_from_metrics(self, metrics: dict) -> float:
        """Calculate reward from simulation metrics."""
        detection_rate = metrics.get("detection_rate", 0.5)
        fp_rate = metrics.get("false_positive_rate", 0.5)
        realism = metrics.get("realism_score", 0.5)

        # Reward function: maximize detection, minimize FP, maintain realism
        reward = (
            detection_rate * 0.4 +  # Reward good detection
            (1 - fp_rate) * 0.3 +   # Penalize false positives
            realism * 0.3           # Reward realistic simulation
        )

        # Normalize to [-1, 1] range
        return (reward - 0.5) * 2

    def _calculate_reward_from_feedback(self) -> float:
        """Calculate reward from pending feedback."""
        if not self.pending_feedback:
            return 0.0

        total_reward = 0.0
        for feedback in self.pending_feedback:
            metrics = feedback.get("data", {})
            total_reward += self._calculate_reward_from_metrics(metrics)

        return total_reward / len(self.pending_feedback)

    def _apply_action(self, action: str) -> dict:
        """Apply action and return parameter adjustments."""
        adjustments = {}
        step = 0.1  # Adjustment step size

        if action == "increase_threat_complexity":
            self.current_state.threat_complexity = min(1.0, self.current_state.threat_complexity + step)
            adjustments["threat_complexity"] = self.current_state.threat_complexity

        elif action == "decrease_threat_complexity":
            self.current_state.threat_complexity = max(0.0, self.current_state.threat_complexity - step)
            adjustments["threat_complexity"] = self.current_state.threat_complexity

        elif action == "increase_device_coverage":
            self.current_state.device_coverage = min(1.0, self.current_state.device_coverage + step)
            adjustments["device_coverage"] = self.current_state.device_coverage

        elif action == "decrease_device_coverage":
            self.current_state.device_coverage = max(0.0, self.current_state.device_coverage - step)
            adjustments["device_coverage"] = self.current_state.device_coverage

        elif action == "increase_behavior_diversity":
            self.current_state.behavior_diversity = min(1.0, self.current_state.behavior_diversity + step)
            adjustments["behavior_diversity"] = self.current_state.behavior_diversity

        elif action == "decrease_behavior_diversity":
            self.current_state.behavior_diversity = max(0.0, self.current_state.behavior_diversity - step)
            adjustments["behavior_diversity"] = self.current_state.behavior_diversity

        elif action == "balance_detection_fp":
            # Try to balance detection rate and false positive rate
            if self.current_state.detection_rate < 0.7:
                adjustments["sensitivity"] = "increase"
            elif self.current_state.false_positive_rate > 0.2:
                adjustments["sensitivity"] = "decrease"

        elif action == "optimize_performance":
            adjustments["optimize_response_time"] = True

        elif action == "maintain_current":
            adjustments["no_change"] = True

        return adjustments

    def _get_action_description(self, action: str) -> str:
        """Get human-readable description of action."""
        descriptions = {
            "increase_threat_complexity": "Make threats more sophisticated and harder to detect",
            "decrease_threat_complexity": "Simplify threats for better baseline detection",
            "increase_device_coverage": "Add more sensors/monitoring devices",
            "decrease_device_coverage": "Reduce device density to test minimal configurations",
            "increase_behavior_diversity": "Add more varied inhabitant behavior patterns",
            "decrease_behavior_diversity": "Standardize behavior for consistent baselines",
            "balance_detection_fp": "Adjust detection sensitivity to balance accuracy",
            "optimize_performance": "Reduce system response time and resource usage",
            "maintain_current": "Keep current configuration (exploitation)",
        }
        return descriptions.get(action, "Unknown action")

    def _get_complexity_recommendation(self, complexity: float) -> str:
        """Get threat type recommendations based on complexity level."""
        if complexity < 0.3:
            return "Focus on basic threats: port scanning, default credentials"
        elif complexity < 0.6:
            return "Include intermediate threats: MITM, credential theft"
        elif complexity < 0.8:
            return "Add advanced threats: APT, multi-stage attacks"
        else:
            return "Full complexity: APT, ransomware, lateral movement"

    def _suggest_threat_types(self) -> list[str]:
        """Suggest threat types based on current state."""
        complexity = self.current_state.threat_complexity

        threats = ["reconnaissance", "credential_brute_force"]

        if complexity > 0.3:
            threats.extend(["mitm", "data_exfiltration"])
        if complexity > 0.5:
            threats.extend(["botnet_recruitment", "device_tampering"])
        if complexity > 0.7:
            threats.extend(["ransomware", "apt_simulation"])

        return threats

    def _suggest_device_placement(self) -> dict:
        """Suggest device placement strategy."""
        coverage = self.current_state.device_coverage

        if coverage < 0.3:
            return {
                "strategy": "minimal",
                "focus": ["entry_points", "high_value_devices"],
            }
        elif coverage < 0.6:
            return {
                "strategy": "balanced",
                "focus": ["all_rooms", "network_segments"],
            }
        else:
            return {
                "strategy": "comprehensive",
                "focus": ["per_device_monitoring", "behavioral_analysis"],
            }

    def _suggest_inhabitant_profiles(self) -> list[dict]:
        """Suggest inhabitant profiles based on diversity setting."""
        diversity = self.current_state.behavior_diversity

        profiles = [
            {"type": "adult", "schedule": "regular_work"},
        ]

        if diversity > 0.3:
            profiles.append({"type": "adult", "schedule": "work_from_home"})
        if diversity > 0.5:
            profiles.append({"type": "child", "schedule": "school"})
        if diversity > 0.7:
            profiles.append({"type": "elderly", "schedule": "retired"})

        return profiles

    def _get_optimal_params(self, params: dict = None) -> dict:
        """Get optimal parameters based on learned policy (tool interface)."""
        # Get best action from policy
        best_action = self.optimizer.select_action(self.current_state, explore=False)

        # Apply action to get optimal adjustments
        adjustments = self._apply_action(best_action)

        # Get Q-values for confidence estimation
        state_key = self.current_state.to_tuple()
        q_values = dict(self.optimizer.q_table[state_key])
        best_q_value = q_values.get(best_action, 0)

        return {
            "optimal_action": best_action,
            "adjustments": adjustments,
            "confidence": best_q_value,
            "current_state": self.current_state.to_dict(),
            "exploration_rate": self.optimizer.epsilon,
        }

    def _save_state(self) -> None:
        """Save agent state to disk."""
        self.optimizer.save(self.data_dir / "q_table.json")
        self.replay_buffer.save(self.data_dir / "replay_buffer.json")

        state_data = {
            "current_state": self.current_state.to_dict(),
            "episode_reward": self.episode_reward,
            "episode_steps": self.episode_steps,
        }
        with open(self.data_dir / "agent_state.json", "w") as f:
            json.dump(state_data, f, indent=2)

    def _load_state(self) -> None:
        """Load agent state from disk."""
        self.optimizer.load(self.data_dir / "q_table.json")
        self.replay_buffer.load(self.data_dir / "replay_buffer.json")

        state_path = self.data_dir / "agent_state.json"
        if state_path.exists():
            with open(state_path) as f:
                data = json.load(f)
            self.current_state = OptimizationState.from_dict(data.get("current_state", {}))
            self.episode_reward = data.get("episode_reward", 0.0)
            self.episode_steps = data.get("episode_steps", 0)

    def __del__(self):
        """Save state on destruction."""
        try:
            self._save_state()
        except Exception:
            pass  # Ignore errors during cleanup
