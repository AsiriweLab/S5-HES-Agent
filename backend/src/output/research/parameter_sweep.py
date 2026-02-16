"""
Parameter Sweep Engine

Automates running multiple simulation experiments with varying parameters
for research and analysis purposes.
"""

import asyncio
import itertools
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Optional

from pydantic import BaseModel, Field


class SweepStatus(str, Enum):
    """Status of a parameter sweep."""
    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ParameterType(str, Enum):
    """Type of parameter variation."""
    DISCRETE = "discrete"  # Specific values: [low, medium, high]
    RANGE = "range"  # Numeric range: [10, 20, 30, 40, 50]
    LINSPACE = "linspace"  # Linear space: start=0, end=1, steps=5
    LOGSPACE = "logspace"  # Log space: start=1, end=100, steps=5


class ParameterDefinition(BaseModel):
    """Definition of a parameter to sweep."""
    name: str
    param_type: ParameterType = ParameterType.DISCRETE
    values: list[Any] = Field(default_factory=list)
    # For range types
    start: Optional[float] = None
    end: Optional[float] = None
    steps: Optional[int] = None
    # Metadata
    description: Optional[str] = None
    unit: Optional[str] = None

    def get_values(self) -> list[Any]:
        """Get the list of values for this parameter."""
        if self.param_type == ParameterType.DISCRETE:
            return self.values
        elif self.param_type == ParameterType.RANGE:
            if self.start is not None and self.end is not None and self.steps:
                step_size = (self.end - self.start) / (self.steps - 1) if self.steps > 1 else 0
                return [self.start + i * step_size for i in range(self.steps)]
            return self.values
        elif self.param_type == ParameterType.LINSPACE:
            import numpy as np
            if self.start is not None and self.end is not None and self.steps:
                return list(np.linspace(self.start, self.end, self.steps))
            return self.values
        elif self.param_type == ParameterType.LOGSPACE:
            import numpy as np
            if self.start is not None and self.end is not None and self.steps:
                return list(np.logspace(np.log10(self.start), np.log10(self.end), self.steps))
            return self.values
        return self.values


class SweepConfiguration(BaseModel):
    """Configuration for a parameter sweep."""
    sweep_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    description: Optional[str] = None
    base_config: dict[str, Any] = Field(default_factory=dict)
    parameters: list[ParameterDefinition] = Field(default_factory=list)
    parallel_workers: int = Field(default=4, ge=1, le=16)
    repetitions: int = Field(default=1, ge=1, le=100)
    random_seed: Optional[int] = None
    tags: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.now)


class ExperimentResult(BaseModel):
    """Result of a single experiment in the sweep."""
    experiment_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    sweep_id: str
    parameter_values: dict[str, Any]
    repetition: int = 0
    status: SweepStatus = SweepStatus.PENDING
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    duration_seconds: Optional[float] = None
    # Results
    metrics: dict[str, Any] = Field(default_factory=dict)
    events_count: int = 0
    threats_detected: int = 0
    threats_blocked: int = 0
    error_message: Optional[str] = None


class SweepProgress(BaseModel):
    """Progress information for a parameter sweep."""
    sweep_id: str
    status: SweepStatus
    total_experiments: int
    completed_experiments: int
    failed_experiments: int
    running_experiments: int
    pending_experiments: int
    progress_percent: float
    estimated_remaining_seconds: Optional[float] = None
    start_time: Optional[datetime] = None
    current_time: datetime = Field(default_factory=datetime.now)


class SweepResults(BaseModel):
    """Aggregated results of a parameter sweep."""
    sweep_id: str
    configuration: SweepConfiguration
    status: SweepStatus
    experiments: list[ExperimentResult]
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    total_duration_seconds: Optional[float] = None
    # Aggregated metrics
    summary_statistics: dict[str, dict[str, float]] = Field(default_factory=dict)
    parameter_effects: dict[str, dict[str, Any]] = Field(default_factory=dict)


@dataclass
class ParameterSweepEngine:
    """
    Engine for running parameter sweep experiments.

    Supports:
    - Multi-dimensional parameter grids
    - Parallel experiment execution
    - Progress tracking
    - Result aggregation
    """

    max_workers: int = 4
    _sweeps: dict[str, SweepResults] = field(default_factory=dict)
    _executor: Optional[ThreadPoolExecutor] = None
    _running: bool = False

    def __post_init__(self):
        self._executor = ThreadPoolExecutor(max_workers=self.max_workers)

    def create_sweep(self, config: SweepConfiguration) -> SweepResults:
        """Create a new parameter sweep."""
        # Generate all parameter combinations
        param_names = [p.name for p in config.parameters]
        param_values = [p.get_values() for p in config.parameters]

        # Create cartesian product of all parameters
        combinations = list(itertools.product(*param_values))

        # Create experiment entries for each combination and repetition
        experiments: list[ExperimentResult] = []
        for combo in combinations:
            param_dict = dict(zip(param_names, combo))
            for rep in range(config.repetitions):
                experiment = ExperimentResult(
                    sweep_id=config.sweep_id,
                    parameter_values=param_dict,
                    repetition=rep,
                    status=SweepStatus.PENDING,
                )
                experiments.append(experiment)

        sweep_results = SweepResults(
            sweep_id=config.sweep_id,
            configuration=config,
            status=SweepStatus.PENDING,
            experiments=experiments,
        )

        self._sweeps[config.sweep_id] = sweep_results
        return sweep_results

    def get_sweep(self, sweep_id: str) -> Optional[SweepResults]:
        """Get a sweep by ID."""
        return self._sweeps.get(sweep_id)

    def list_sweeps(self) -> list[SweepResults]:
        """List all sweeps."""
        return list(self._sweeps.values())

    def get_progress(self, sweep_id: str) -> Optional[SweepProgress]:
        """Get progress information for a sweep."""
        sweep = self._sweeps.get(sweep_id)
        if not sweep:
            return None

        completed = sum(1 for e in sweep.experiments if e.status == SweepStatus.COMPLETED)
        failed = sum(1 for e in sweep.experiments if e.status == SweepStatus.FAILED)
        running = sum(1 for e in sweep.experiments if e.status == SweepStatus.RUNNING)
        pending = sum(1 for e in sweep.experiments if e.status == SweepStatus.PENDING)
        total = len(sweep.experiments)

        progress = (completed + failed) / total * 100 if total > 0 else 0

        # Estimate remaining time based on average duration
        completed_experiments = [e for e in sweep.experiments if e.duration_seconds is not None]
        avg_duration = (
            sum(e.duration_seconds for e in completed_experiments) / len(completed_experiments)
            if completed_experiments else None
        )
        estimated_remaining = avg_duration * pending if avg_duration else None

        return SweepProgress(
            sweep_id=sweep_id,
            status=sweep.status,
            total_experiments=total,
            completed_experiments=completed,
            failed_experiments=failed,
            running_experiments=running,
            pending_experiments=pending,
            progress_percent=progress,
            estimated_remaining_seconds=estimated_remaining,
            start_time=sweep.start_time,
        )

    async def run_sweep(
        self,
        sweep_id: str,
        experiment_runner: Callable[[dict[str, Any], dict[str, Any]], dict[str, Any]],
    ) -> SweepResults:
        """
        Run all experiments in a sweep.

        Args:
            sweep_id: ID of the sweep to run
            experiment_runner: Function that takes (base_config, param_values) and returns metrics

        Returns:
            Updated SweepResults with all experiment results
        """
        sweep = self._sweeps.get(sweep_id)
        if not sweep:
            raise ValueError(f"Sweep {sweep_id} not found")

        sweep.status = SweepStatus.RUNNING
        sweep.start_time = datetime.now()
        self._running = True

        # Run experiments with parallel workers
        config = sweep.configuration
        pending_experiments = [e for e in sweep.experiments if e.status == SweepStatus.PENDING]

        # Process in batches for parallel execution
        batch_size = config.parallel_workers

        for i in range(0, len(pending_experiments), batch_size):
            if not self._running:
                sweep.status = SweepStatus.PAUSED
                break

            batch = pending_experiments[i:i + batch_size]
            tasks = []

            for experiment in batch:
                experiment.status = SweepStatus.RUNNING
                experiment.start_time = datetime.now()

                # Create task for each experiment
                task = asyncio.get_event_loop().run_in_executor(
                    self._executor,
                    self._run_single_experiment,
                    experiment,
                    config.base_config,
                    experiment_runner,
                )
                tasks.append((experiment, task))

            # Wait for batch to complete
            for experiment, task in tasks:
                try:
                    result = await task
                    experiment.metrics = result.get("metrics", {})
                    experiment.events_count = result.get("events_count", 0)
                    experiment.threats_detected = result.get("threats_detected", 0)
                    experiment.threats_blocked = result.get("threats_blocked", 0)
                    experiment.status = SweepStatus.COMPLETED
                except Exception as e:
                    experiment.status = SweepStatus.FAILED
                    experiment.error_message = str(e)
                finally:
                    experiment.end_time = datetime.now()
                    if experiment.start_time:
                        experiment.duration_seconds = (
                            experiment.end_time - experiment.start_time
                        ).total_seconds()

        # Update sweep status
        if self._running:
            failed_count = sum(1 for e in sweep.experiments if e.status == SweepStatus.FAILED)
            sweep.status = SweepStatus.FAILED if failed_count == len(sweep.experiments) else SweepStatus.COMPLETED

        sweep.end_time = datetime.now()
        if sweep.start_time:
            sweep.total_duration_seconds = (sweep.end_time - sweep.start_time).total_seconds()

        # Calculate summary statistics
        sweep.summary_statistics = self._calculate_summary_statistics(sweep)
        sweep.parameter_effects = self._calculate_parameter_effects(sweep)

        return sweep

    def _run_single_experiment(
        self,
        experiment: ExperimentResult,
        base_config: dict[str, Any],
        runner: Callable,
    ) -> dict[str, Any]:
        """Run a single experiment synchronously."""
        # Merge base config with parameter values
        merged_config = {**base_config, **experiment.parameter_values}
        return runner(base_config, experiment.parameter_values)

    def pause_sweep(self, sweep_id: str) -> bool:
        """Pause a running sweep."""
        sweep = self._sweeps.get(sweep_id)
        if sweep and sweep.status == SweepStatus.RUNNING:
            self._running = False
            sweep.status = SweepStatus.PAUSED
            return True
        return False

    def cancel_sweep(self, sweep_id: str) -> bool:
        """Cancel a sweep."""
        sweep = self._sweeps.get(sweep_id)
        if sweep and sweep.status in [SweepStatus.RUNNING, SweepStatus.PAUSED, SweepStatus.PENDING]:
            self._running = False
            sweep.status = SweepStatus.CANCELLED
            return True
        return False

    def delete_sweep(self, sweep_id: str) -> bool:
        """Delete a sweep."""
        if sweep_id in self._sweeps:
            del self._sweeps[sweep_id]
            return True
        return False

    def _calculate_summary_statistics(self, sweep: SweepResults) -> dict[str, dict[str, float]]:
        """Calculate summary statistics for each metric."""
        import statistics

        completed = [e for e in sweep.experiments if e.status == SweepStatus.COMPLETED]
        if not completed:
            return {}

        # Collect all metric names
        all_metrics: set[str] = set()
        for exp in completed:
            all_metrics.update(exp.metrics.keys())

        # Standard numeric metrics
        all_metrics.update(["events_count", "threats_detected", "threats_blocked", "duration_seconds"])

        summary: dict[str, dict[str, float]] = {}

        for metric_name in all_metrics:
            values: list[float] = []
            for exp in completed:
                if metric_name in ["events_count", "threats_detected", "threats_blocked"]:
                    values.append(float(getattr(exp, metric_name, 0)))
                elif metric_name == "duration_seconds":
                    if exp.duration_seconds is not None:
                        values.append(exp.duration_seconds)
                else:
                    val = exp.metrics.get(metric_name)
                    if isinstance(val, (int, float)):
                        values.append(float(val))

            if values:
                summary[metric_name] = {
                    "count": len(values),
                    "mean": statistics.mean(values),
                    "median": statistics.median(values),
                    "std_dev": statistics.stdev(values) if len(values) > 1 else 0,
                    "min": min(values),
                    "max": max(values),
                    "sum": sum(values),
                }

        return summary

    def _calculate_parameter_effects(self, sweep: SweepResults) -> dict[str, dict[str, Any]]:
        """Calculate the effect of each parameter on metrics."""
        import statistics

        completed = [e for e in sweep.experiments if e.status == SweepStatus.COMPLETED]
        if not completed:
            return {}

        effects: dict[str, dict[str, Any]] = {}

        for param in sweep.configuration.parameters:
            param_name = param.name
            param_values = param.get_values()

            effects[param_name] = {
                "values": param_values,
                "metrics_by_value": {},
            }

            for value in param_values:
                # Get experiments with this parameter value
                matching = [
                    e for e in completed
                    if e.parameter_values.get(param_name) == value
                ]

                if matching:
                    # Calculate mean metrics for this parameter value
                    threats_detected = [e.threats_detected for e in matching]
                    threats_blocked = [e.threats_blocked for e in matching]
                    events_count = [e.events_count for e in matching]

                    effects[param_name]["metrics_by_value"][str(value)] = {
                        "experiment_count": len(matching),
                        "mean_threats_detected": statistics.mean(threats_detected) if threats_detected else 0,
                        "mean_threats_blocked": statistics.mean(threats_blocked) if threats_blocked else 0,
                        "mean_events_count": statistics.mean(events_count) if events_count else 0,
                    }

        return effects

    def export_results(self, sweep_id: str, format: str = "json") -> Optional[str]:
        """Export sweep results to a string format."""
        import json

        sweep = self._sweeps.get(sweep_id)
        if not sweep:
            return None

        if format == "json":
            return sweep.model_dump_json(indent=2)
        elif format == "csv":
            # CSV export for experiments
            lines = ["experiment_id,sweep_id,status,duration_seconds,events_count,threats_detected,threats_blocked"]
            for exp in sweep.experiments:
                lines.append(
                    f"{exp.experiment_id},{exp.sweep_id},{exp.status.value},"
                    f"{exp.duration_seconds or ''},{exp.events_count},"
                    f"{exp.threats_detected},{exp.threats_blocked}"
                )
            return "\n".join(lines)

        return None


# Singleton instance
_sweep_engine: Optional[ParameterSweepEngine] = None


def get_parameter_sweep_engine() -> ParameterSweepEngine:
    """Get the global parameter sweep engine instance."""
    global _sweep_engine
    if _sweep_engine is None:
        _sweep_engine = ParameterSweepEngine()
    return _sweep_engine