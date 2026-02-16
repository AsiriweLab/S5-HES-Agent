"""
RL Training Framework for Optimization Agent.

Provides training infrastructure for the optimization agent including:
- Training session management
- Metrics tracking
- Model checkpointing
- Hyperparameter management
"""

import asyncio
import json
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Optional

from loguru import logger

from src.ai.agents import OptimizationAgent
from src.ai.training.environment import (
    SimulationEnvironment,
    EnvironmentAction,
    EnvironmentState,
)


@dataclass
class TrainingConfig:
    """Configuration for RL training."""
    # Training parameters
    n_episodes: int = 100
    max_steps_per_episode: int = 100
    learning_rate: float = 0.1
    discount_factor: float = 0.95
    initial_epsilon: float = 1.0
    min_epsilon: float = 0.05
    epsilon_decay: float = 0.995

    # Environment parameters
    target_detection_rate: float = 0.85
    max_fp_rate: float = 0.15
    use_real_simulation: bool = False

    # Checkpointing
    checkpoint_interval: int = 10
    checkpoint_dir: str = "data/training/checkpoints"

    # Early stopping
    early_stopping_patience: int = 20
    min_improvement: float = 0.01

    # Logging
    log_interval: int = 5
    verbose: bool = True

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "n_episodes": self.n_episodes,
            "max_steps_per_episode": self.max_steps_per_episode,
            "learning_rate": self.learning_rate,
            "discount_factor": self.discount_factor,
            "initial_epsilon": self.initial_epsilon,
            "min_epsilon": self.min_epsilon,
            "epsilon_decay": self.epsilon_decay,
            "target_detection_rate": self.target_detection_rate,
            "max_fp_rate": self.max_fp_rate,
            "use_real_simulation": self.use_real_simulation,
            "checkpoint_interval": self.checkpoint_interval,
            "early_stopping_patience": self.early_stopping_patience,
        }


@dataclass
class TrainingMetrics:
    """Metrics from a training session."""
    episode_rewards: list[float] = field(default_factory=list)
    episode_lengths: list[int] = field(default_factory=list)
    detection_rates: list[float] = field(default_factory=list)
    fp_rates: list[float] = field(default_factory=list)
    epsilon_values: list[float] = field(default_factory=list)
    q_value_norms: list[float] = field(default_factory=list)
    training_times: list[float] = field(default_factory=list)

    @property
    def mean_reward(self) -> float:
        """Mean episode reward."""
        return sum(self.episode_rewards) / len(self.episode_rewards) if self.episode_rewards else 0

    @property
    def best_reward(self) -> float:
        """Best episode reward."""
        return max(self.episode_rewards) if self.episode_rewards else 0

    @property
    def mean_episode_length(self) -> float:
        """Mean episode length."""
        return sum(self.episode_lengths) / len(self.episode_lengths) if self.episode_lengths else 0

    @property
    def final_detection_rate(self) -> float:
        """Final detection rate achieved."""
        return self.detection_rates[-1] if self.detection_rates else 0

    @property
    def total_training_time(self) -> float:
        """Total training time in seconds."""
        return sum(self.training_times)

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "episodes": len(self.episode_rewards),
            "mean_reward": self.mean_reward,
            "best_reward": self.best_reward,
            "mean_episode_length": self.mean_episode_length,
            "final_detection_rate": self.final_detection_rate,
            "final_fp_rate": self.fp_rates[-1] if self.fp_rates else 0,
            "final_epsilon": self.epsilon_values[-1] if self.epsilon_values else 1.0,
            "total_training_time_s": self.total_training_time,
        }


@dataclass
class TrainingSession:
    """Represents a training session."""
    session_id: str
    config: TrainingConfig
    metrics: TrainingMetrics
    start_time: datetime
    end_time: Optional[datetime] = None
    status: str = "running"  # running, completed, stopped, failed
    best_checkpoint: Optional[str] = None
    final_model_path: Optional[str] = None

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "session_id": self.session_id,
            "config": self.config.to_dict(),
            "metrics": self.metrics.to_dict(),
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "status": self.status,
            "best_checkpoint": self.best_checkpoint,
            "final_model_path": self.final_model_path,
        }


class RLTrainer:
    """
    RL Training Manager for Optimization Agent.

    Handles:
    - Training loop execution
    - Progress tracking
    - Model checkpointing
    - Early stopping
    - Hyperparameter management
    """

    def __init__(
        self,
        agent: Optional[OptimizationAgent] = None,
        config: Optional[TrainingConfig] = None,
        data_dir: Path = None,
    ):
        """
        Initialize the trainer.

        Args:
            agent: Optimization agent to train (created if not provided)
            config: Training configuration
            data_dir: Directory for training artifacts
        """
        self.agent = agent or OptimizationAgent(agent_id="trainer-agent")
        self.config = config or TrainingConfig()
        self.data_dir = data_dir or Path("data/training")
        self.data_dir.mkdir(parents=True, exist_ok=True)

        # Training state
        self.current_session: Optional[TrainingSession] = None
        self.sessions: list[TrainingSession] = []

        # Callbacks
        self._callbacks: dict[str, list[Callable]] = {
            "on_episode_start": [],
            "on_episode_end": [],
            "on_step": [],
            "on_training_start": [],
            "on_training_end": [],
        }

        # Early stopping state
        self._best_reward = float("-inf")
        self._patience_counter = 0

        logger.info(f"RLTrainer initialized with agent {self.agent.agent_id}")

    def register_callback(self, event: str, callback: Callable) -> None:
        """Register a callback for training events."""
        if event in self._callbacks:
            self._callbacks[event].append(callback)

    def _fire_callbacks(self, event: str, **kwargs) -> None:
        """Fire callbacks for an event."""
        for callback in self._callbacks.get(event, []):
            try:
                callback(**kwargs)
            except Exception as e:
                logger.warning(f"Callback error for {event}: {e}")

    async def train(
        self,
        config: Optional[TrainingConfig] = None,
        resume_session: Optional[str] = None,
    ) -> TrainingSession:
        """
        Run a training session.

        Args:
            config: Training configuration (uses default if not provided)
            resume_session: Session ID to resume (if any)

        Returns:
            Completed training session
        """
        config = config or self.config

        # Create or resume session
        if resume_session:
            session = self._load_session(resume_session)
            if not session:
                raise ValueError(f"Session {resume_session} not found")
        else:
            session = TrainingSession(
                session_id=f"train_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}",
                config=config,
                metrics=TrainingMetrics(),
                start_time=datetime.utcnow(),
            )
            self.sessions.append(session)

        self.current_session = session

        # Create environment
        env = SimulationEnvironment(
            max_steps=config.max_steps_per_episode,
            target_detection_rate=config.target_detection_rate,
            max_fp_rate=config.max_fp_rate,
            use_real_simulation=config.use_real_simulation,
        )

        # Configure agent's optimizer
        self.agent.optimizer.learning_rate = config.learning_rate
        self.agent.optimizer.discount_factor = config.discount_factor
        self.agent.optimizer.epsilon = config.initial_epsilon
        self.agent.optimizer.epsilon_min = config.min_epsilon
        self.agent.optimizer.epsilon_decay = config.epsilon_decay

        self._fire_callbacks("on_training_start", session=session)

        try:
            # Training loop
            for episode in range(len(session.metrics.episode_rewards), config.n_episodes):
                episode_start = time.time()

                # Reset environment
                state = env.reset(seed=episode)
                self._update_agent_state(state)

                episode_reward = 0.0
                steps = 0

                self._fire_callbacks("on_episode_start", episode=episode)

                # Episode loop
                while True:
                    # Select action
                    action_str = self.agent.optimizer.select_action(
                        self.agent.current_state,
                        explore=True,
                    )
                    action = EnvironmentAction(action_str)

                    # Take step
                    next_state, reward, done, info = env.step(action)

                    # Update agent state
                    self._update_agent_state(next_state)

                    # Learn from experience
                    self.agent.optimizer.update(
                        state=self._state_to_optimization_state(state),
                        action=action_str,
                        reward=reward.total,
                        next_state=self.agent.current_state,
                        done=done,
                    )

                    episode_reward += reward.total
                    steps += 1
                    state = next_state

                    self._fire_callbacks(
                        "on_step",
                        episode=episode,
                        step=steps,
                        state=state,
                        action=action,
                        reward=reward,
                    )

                    if done:
                        break

                # Decay epsilon
                self.agent.optimizer.decay_epsilon()

                # Record metrics
                episode_time = time.time() - episode_start
                session.metrics.episode_rewards.append(episode_reward)
                session.metrics.episode_lengths.append(steps)
                session.metrics.detection_rates.append(state.detection_rate)
                session.metrics.fp_rates.append(state.false_positive_rate)
                session.metrics.epsilon_values.append(self.agent.optimizer.epsilon)
                session.metrics.training_times.append(episode_time)

                # Calculate Q-value norm for monitoring
                q_norm = sum(
                    sum(v ** 2 for v in actions.values())
                    for actions in self.agent.optimizer.q_table.values()
                ) ** 0.5
                session.metrics.q_value_norms.append(q_norm)

                self._fire_callbacks(
                    "on_episode_end",
                    episode=episode,
                    reward=episode_reward,
                    steps=steps,
                    metrics=session.metrics,
                )

                # Logging
                if config.verbose and (episode + 1) % config.log_interval == 0:
                    recent_rewards = session.metrics.episode_rewards[-config.log_interval:]
                    avg_reward = sum(recent_rewards) / len(recent_rewards)
                    logger.info(
                        f"Episode {episode + 1}/{config.n_episodes}: "
                        f"Reward={episode_reward:.2f}, Avg={avg_reward:.2f}, "
                        f"Detection={state.detection_rate:.2%}, "
                        f"Epsilon={self.agent.optimizer.epsilon:.3f}"
                    )

                # Checkpointing
                if (episode + 1) % config.checkpoint_interval == 0:
                    checkpoint_path = self._save_checkpoint(session, episode + 1)
                    if episode_reward > self._best_reward:
                        self._best_reward = episode_reward
                        session.best_checkpoint = checkpoint_path

                # Early stopping check
                if self._check_early_stopping(episode_reward, config):
                    logger.info(f"Early stopping triggered at episode {episode + 1}")
                    break

            # Training completed
            session.status = "completed"
            session.end_time = datetime.utcnow()

            # Save final model
            session.final_model_path = self._save_final_model(session)

        except Exception as e:
            session.status = "failed"
            session.end_time = datetime.utcnow()
            logger.error(f"Training failed: {e}", exc_info=True)
            raise

        finally:
            env.close()
            self._fire_callbacks("on_training_end", session=session)
            self._save_session(session)

        return session

    def _update_agent_state(self, env_state: EnvironmentState) -> None:
        """Update agent's internal state from environment state."""
        self.agent.current_state.detection_rate = env_state.detection_rate
        self.agent.current_state.false_positive_rate = env_state.false_positive_rate
        self.agent.current_state.threat_complexity = env_state.threat_complexity
        self.agent.current_state.device_coverage = env_state.device_coverage
        self.agent.current_state.behavior_diversity = env_state.behavior_diversity
        self.agent.current_state.simulation_realism_score = env_state.simulation_realism_score
        self.agent.current_state.avg_response_time_ms = env_state.avg_response_time_ms
        self.agent.current_state.resource_utilization = env_state.resource_utilization

    def _state_to_optimization_state(self, env_state: EnvironmentState):
        """Convert environment state to optimization state."""
        from src.ai.agents.optimization_agent import OptimizationState
        return OptimizationState(
            detection_rate=env_state.detection_rate,
            false_positive_rate=env_state.false_positive_rate,
            threat_complexity=env_state.threat_complexity,
            device_coverage=env_state.device_coverage,
            behavior_diversity=env_state.behavior_diversity,
            simulation_realism_score=env_state.simulation_realism_score,
            avg_response_time_ms=env_state.avg_response_time_ms,
            resource_utilization=env_state.resource_utilization,
        )

    def _check_early_stopping(self, episode_reward: float, config: TrainingConfig) -> bool:
        """Check if early stopping criteria is met."""
        if episode_reward > self._best_reward + config.min_improvement:
            self._best_reward = episode_reward
            self._patience_counter = 0
        else:
            self._patience_counter += 1

        return self._patience_counter >= config.early_stopping_patience

    def _save_checkpoint(self, session: TrainingSession, episode: int) -> str:
        """Save training checkpoint."""
        checkpoint_dir = self.data_dir / "checkpoints" / session.session_id
        checkpoint_dir.mkdir(parents=True, exist_ok=True)

        checkpoint_path = checkpoint_dir / f"checkpoint_ep{episode}.json"

        checkpoint = {
            "episode": episode,
            "agent_state": self.agent.current_state.to_dict(),
            "optimizer_state": {
                "epsilon": self.agent.optimizer.epsilon,
                "q_table_size": len(self.agent.optimizer.q_table),
                "episode_count": self.agent.optimizer.episode_count,
            },
            "metrics_summary": session.metrics.to_dict(),
            "timestamp": datetime.utcnow().isoformat(),
        }

        with open(checkpoint_path, "w") as f:
            json.dump(checkpoint, f, indent=2)

        # Also save Q-table
        self.agent.optimizer.save(checkpoint_dir / f"q_table_ep{episode}.json")

        logger.debug(f"Checkpoint saved: {checkpoint_path}")
        return str(checkpoint_path)

    def _save_final_model(self, session: TrainingSession) -> str:
        """Save final trained model."""
        model_dir = self.data_dir / "models" / session.session_id
        model_dir.mkdir(parents=True, exist_ok=True)

        # Save Q-table
        self.agent.optimizer.save(model_dir / "q_table.json")

        # Save agent state
        self.agent._save_state()

        # Save training summary
        summary = {
            "session_id": session.session_id,
            "config": session.config.to_dict(),
            "final_metrics": session.metrics.to_dict(),
            "training_duration_s": session.metrics.total_training_time,
            "timestamp": datetime.utcnow().isoformat(),
        }

        with open(model_dir / "training_summary.json", "w") as f:
            json.dump(summary, f, indent=2)

        logger.info(f"Final model saved: {model_dir}")
        return str(model_dir)

    def _save_session(self, session: TrainingSession) -> None:
        """Save session state."""
        session_path = self.data_dir / "sessions" / f"{session.session_id}.json"
        session_path.parent.mkdir(parents=True, exist_ok=True)

        with open(session_path, "w") as f:
            json.dump(session.to_dict(), f, indent=2)

    def _load_session(self, session_id: str) -> Optional[TrainingSession]:
        """Load a saved session."""
        session_path = self.data_dir / "sessions" / f"{session_id}.json"
        if not session_path.exists():
            return None

        with open(session_path) as f:
            data = json.load(f)

        # Reconstruct session
        config = TrainingConfig(**data["config"])
        metrics = TrainingMetrics(
            episode_rewards=data["metrics"].get("episode_rewards", []),
            episode_lengths=data["metrics"].get("episode_lengths", []),
            detection_rates=data["metrics"].get("detection_rates", []),
            fp_rates=data["metrics"].get("fp_rates", []),
            epsilon_values=data["metrics"].get("epsilon_values", []),
        )

        return TrainingSession(
            session_id=data["session_id"],
            config=config,
            metrics=metrics,
            start_time=datetime.fromisoformat(data["start_time"]),
            end_time=datetime.fromisoformat(data["end_time"]) if data.get("end_time") else None,
            status=data.get("status", "unknown"),
            best_checkpoint=data.get("best_checkpoint"),
            final_model_path=data.get("final_model_path"),
        )

    def evaluate(
        self,
        n_episodes: int = 10,
        render: bool = False,
    ) -> dict:
        """
        Evaluate the trained agent.

        Args:
            n_episodes: Number of evaluation episodes
            render: Whether to render environment

        Returns:
            Evaluation metrics
        """
        env = SimulationEnvironment(
            max_steps=self.config.max_steps_per_episode,
            target_detection_rate=self.config.target_detection_rate,
            max_fp_rate=self.config.max_fp_rate,
        )

        rewards = []
        detection_rates = []
        fp_rates = []
        successes = 0

        for episode in range(n_episodes):
            state = env.reset(seed=episode + 1000)
            self._update_agent_state(state)
            episode_reward = 0

            while True:
                # Use greedy policy (no exploration)
                action_str = self.agent.optimizer.select_action(
                    self.agent.current_state,
                    explore=False,
                )
                action = EnvironmentAction(action_str)

                state, reward, done, info = env.step(action)
                self._update_agent_state(state)
                episode_reward += reward.total

                if render:
                    print(env.render())

                if done:
                    break

            rewards.append(episode_reward)
            detection_rates.append(state.detection_rate)
            fp_rates.append(state.false_positive_rate)

            if (
                state.detection_rate >= self.config.target_detection_rate
                and state.false_positive_rate <= self.config.max_fp_rate
            ):
                successes += 1

        env.close()

        return {
            "mean_reward": sum(rewards) / len(rewards),
            "std_reward": (sum((r - sum(rewards)/len(rewards))**2 for r in rewards) / len(rewards)) ** 0.5,
            "success_rate": successes / n_episodes,
            "mean_detection_rate": sum(detection_rates) / len(detection_rates),
            "mean_fp_rate": sum(fp_rates) / len(fp_rates),
            "episodes": n_episodes,
        }

    def get_training_history(self) -> list[dict]:
        """Get history of all training sessions."""
        return [session.to_dict() for session in self.sessions]


# Global trainer instance
_trainer: Optional[RLTrainer] = None


def get_trainer(
    agent: Optional[OptimizationAgent] = None,
    config: Optional[TrainingConfig] = None,
) -> RLTrainer:
    """Get or create the global trainer instance."""
    global _trainer
    if _trainer is None:
        _trainer = RLTrainer(agent=agent, config=config)
    return _trainer
