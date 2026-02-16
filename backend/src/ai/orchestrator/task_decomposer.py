"""
Task Decomposer for the Smart-HES Agent Framework.

Breaks down complex user requests into manageable sub-tasks
that can be assigned to specialized agents.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional
from uuid import uuid4

from loguru import logger


class TaskPriority(int, Enum):
    """Task priority levels."""
    CRITICAL = 1
    HIGH = 2
    MEDIUM = 3
    LOW = 4
    BACKGROUND = 5


class TaskStatus(str, Enum):
    """Task execution status."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    BLOCKED = "blocked"  # Waiting for dependencies


@dataclass
class DecomposedTask:
    """A task that has been decomposed from a user request."""
    task_id: str
    task_type: str  # e.g., "home_builder", "device_manager", "threat_injector"
    action: str     # e.g., "create_home", "add_device", "inject_threat"
    description: str
    parameters: dict = field(default_factory=dict)
    priority: TaskPriority = TaskPriority.MEDIUM
    status: TaskStatus = TaskStatus.PENDING
    dependencies: list[str] = field(default_factory=list)  # Task IDs this depends on
    assigned_agent: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    result: Optional[dict] = None
    error: Optional[str] = None
    parent_task_id: Optional[str] = None  # For hierarchical decomposition

    @classmethod
    def create(
        cls,
        task_type: str,
        action: str,
        description: str,
        parameters: dict = None,
        priority: TaskPriority = TaskPriority.MEDIUM,
        dependencies: list[str] = None,
    ) -> "DecomposedTask":
        """Factory method to create a new task."""
        return cls(
            task_id=str(uuid4()),
            task_type=task_type,
            action=action,
            description=description,
            parameters=parameters or {},
            priority=priority,
            dependencies=dependencies or [],
        )

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "task_id": self.task_id,
            "task_type": self.task_type,
            "action": self.action,
            "description": self.description,
            "parameters": self.parameters,
            "priority": self.priority.value,
            "status": self.status.value,
            "dependencies": self.dependencies,
            "assigned_agent": self.assigned_agent,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "result": self.result,
            "error": self.error,
        }


@dataclass
class TaskPlan:
    """A plan containing decomposed tasks from a user request."""
    plan_id: str
    original_request: str
    tasks: list[DecomposedTask] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)
    status: str = "pending"
    total_tasks: int = 0
    completed_tasks: int = 0

    @classmethod
    def create(cls, original_request: str) -> "TaskPlan":
        """Factory method to create a new plan."""
        return cls(
            plan_id=str(uuid4()),
            original_request=original_request,
        )

    def add_task(self, task: DecomposedTask) -> None:
        """Add a task to the plan."""
        task.parent_task_id = self.plan_id
        self.tasks.append(task)
        self.total_tasks = len(self.tasks)

    def get_ready_tasks(self) -> list[DecomposedTask]:
        """Get tasks that are ready to execute (no unmet dependencies)."""
        completed_ids = {t.task_id for t in self.tasks if t.status == TaskStatus.COMPLETED}

        return [
            task for task in self.tasks
            if task.status == TaskStatus.PENDING
            and all(dep in completed_ids for dep in task.dependencies)
        ]

    def update_progress(self) -> None:
        """Update the completion progress."""
        self.completed_tasks = sum(
            1 for t in self.tasks if t.status == TaskStatus.COMPLETED
        )
        if self.completed_tasks == self.total_tasks and self.total_tasks > 0:
            self.status = "completed"
        elif any(t.status == TaskStatus.FAILED for t in self.tasks):
            self.status = "failed"
        elif any(t.status == TaskStatus.IN_PROGRESS for t in self.tasks):
            self.status = "in_progress"

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "plan_id": self.plan_id,
            "original_request": self.original_request,
            "tasks": [t.to_dict() for t in self.tasks],
            "created_at": self.created_at.isoformat(),
            "status": self.status,
            "total_tasks": self.total_tasks,
            "completed_tasks": self.completed_tasks,
            "progress_percent": (self.completed_tasks / self.total_tasks * 100) if self.total_tasks > 0 else 0,
        }


# Task type mappings for decomposition
TASK_PATTERNS = {
    # Home building patterns
    "create_home": {
        "keywords": ["create", "build", "generate", "make", "new home", "new house", "smart home"],
        "agent_type": "home_builder",
        "action": "create_home",
    },
    "modify_home": {
        "keywords": ["modify", "change", "update", "edit home", "reconfigure"],
        "agent_type": "home_builder",
        "action": "modify_home",
    },

    # Device management patterns
    "add_device": {
        "keywords": ["add device", "install", "place", "put"],
        "agent_type": "device_manager",
        "action": "add_device",
    },
    "remove_device": {
        "keywords": ["remove device", "delete device", "uninstall"],
        "agent_type": "device_manager",
        "action": "remove_device",
    },
    "configure_device": {
        "keywords": ["configure", "set up", "settings", "device config"],
        "agent_type": "device_manager",
        "action": "configure_device",
    },

    # Threat injection patterns
    "inject_threat": {
        "keywords": ["attack", "threat", "inject", "simulate attack", "security test"],
        "agent_type": "threat_injector",
        "action": "inject_threat",
    },
    # Composite scenario creation (home + threat + simulation)
    "create_scenario": {
        "keywords": [
            "scenario with",       # "create scenario with apartment and botnet"
            "scenario for",        # "create scenario for small home"
            "test scenario",       # "test scenario with attack"
            "security scenario",   # "security scenario"
            "simulation scenario", # "simulation scenario with threats"
            "create a scenario",   # "create a scenario"
            "create scenario",     # "create scenario" (without "a")
            "build a scenario",    # "build a scenario"
            "build scenario",      # "build scenario" (without "a")
            "make a scenario",     # "make a scenario"
            "make scenario",       # "make scenario"
            "set up scenario",     # "set up scenario"
            "setup scenario",      # "setup scenario"
            "home and threat",     # "build home and threat"
            "home and attack",     # "build home and attack"
            "home with threat",    # "create home with threat"
            "home with attack",    # "create home with attack"
            "a threat to",         # "scenario with a threat to camera" - more specific
            "and a threat",        # "home and a threat to"
            "and threat",          # "home and threat to"
        ],
        "agent_type": "composite",
        "action": "create_scenario",
    },

    # Simulation patterns
    "run_simulation": {
        "keywords": ["simulate", "run", "start simulation", "execute"],
        "agent_type": "simulation_controller",
        "action": "run_simulation",
    },
    "export_data": {
        "keywords": ["export", "download", "save data", "generate dataset"],
        "agent_type": "data_exporter",
        "action": "export_data",
    },
}


class TaskDecomposer:
    """
    Decomposes user requests into executable tasks for agents.

    Features:
    - Pattern-based task identification
    - LLM-assisted complex decomposition
    - Dependency graph generation
    - Priority assignment
    """

    def __init__(self):
        self._plans: dict[str, TaskPlan] = {}
        logger.info("TaskDecomposer initialized")

    def decompose_simple(self, user_request: str) -> TaskPlan:
        """
        Decompose a user request using pattern matching.

        This is a fast, rule-based decomposition for simple requests.
        For complex requests, use decompose_with_llm().

        Args:
            user_request: The user's natural language request

        Returns:
            TaskPlan with decomposed tasks
        """
        plan = TaskPlan.create(user_request)
        request_lower = user_request.lower()

        # Find matching patterns
        matched_patterns = []
        for task_name, pattern in TASK_PATTERNS.items():
            for keyword in pattern["keywords"]:
                if keyword in request_lower:
                    matched_patterns.append((task_name, pattern))
                    break

        # Create tasks for matched patterns
        for task_name, pattern in matched_patterns:
            task = DecomposedTask.create(
                task_type=pattern["agent_type"],
                action=pattern["action"],
                description=f"{task_name}: {user_request}",
                parameters={"original_request": user_request},
            )
            plan.add_task(task)

        # If no patterns matched, create a general conversation task
        if not matched_patterns:
            task = DecomposedTask.create(
                task_type="conversation",
                action="respond",
                description=f"Respond to: {user_request}",
                parameters={"original_request": user_request},
            )
            plan.add_task(task)

        self._plans[plan.plan_id] = plan
        logger.info(f"Decomposed request into {len(plan.tasks)} tasks: {[t.action for t in plan.tasks]}")

        return plan

    async def decompose_with_llm(
        self,
        user_request: str,
        llm_engine: Any,  # Avoid circular import
        context: dict = None,
    ) -> TaskPlan:
        """
        Decompose a complex request using LLM assistance.

        Args:
            user_request: The user's natural language request
            llm_engine: LLMEngine instance for complex decomposition
            context: Optional context (current home, devices, etc.)

        Returns:
            TaskPlan with decomposed tasks
        """
        plan = TaskPlan.create(user_request)

        # Build context for LLM
        context_str = ""
        if context:
            if "current_home" in context:
                context_str += f"\nCurrent home: {context['current_home']}"
            if "available_devices" in context:
                context_str += f"\nAvailable devices: {context['available_devices']}"

        # Prompt for task decomposition
        decomposition_prompt = f"""Analyze this user request and break it down into specific tasks.

User Request: "{user_request}"
{context_str}

For each task, provide:
1. task_type: One of [home_builder, device_manager, threat_injector, simulation_controller, conversation]
2. action: Specific action to take
3. description: What needs to be done
4. priority: 1 (critical) to 5 (low)
5. dependencies: List of task numbers this depends on (empty if none)

Think step by step about what needs to happen in order."""

        try:
            result = await llm_engine.generate_json(
                prompt=decomposition_prompt,
                schema={
                    "type": "object",
                    "required": ["tasks"],
                    "properties": {
                        "tasks": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "required": ["task_type", "action", "description"],
                                "properties": {
                                    "task_type": {"type": "string"},
                                    "action": {"type": "string"},
                                    "description": {"type": "string"},
                                    "priority": {"type": "integer", "minimum": 1, "maximum": 5},
                                    "parameters": {"type": "object"},
                                    "depends_on": {"type": "array", "items": {"type": "integer"}},
                                }
                            }
                        }
                    }
                },
                system_prompt="You are a task decomposition assistant. Break down requests into specific, actionable tasks.",
            )

            # Create tasks from LLM response
            task_id_map = {}  # Map index to task_id for dependency resolution
            for i, task_data in enumerate(result.get("tasks", [])):
                task = DecomposedTask.create(
                    task_type=task_data.get("task_type", "conversation"),
                    action=task_data.get("action", "respond"),
                    description=task_data.get("description", ""),
                    parameters=task_data.get("parameters", {}),
                    priority=TaskPriority(task_data.get("priority", 3)),
                )
                task_id_map[i] = task.task_id
                plan.add_task(task)

            # Resolve dependencies
            for i, task_data in enumerate(result.get("tasks", [])):
                depends_on = task_data.get("depends_on", [])
                if depends_on and i < len(plan.tasks):
                    plan.tasks[i].dependencies = [
                        task_id_map[dep] for dep in depends_on
                        if dep in task_id_map and dep != i
                    ]

        except Exception as e:
            logger.error(f"LLM decomposition failed: {e}, falling back to simple decomposition")
            return self.decompose_simple(user_request)

        self._plans[plan.plan_id] = plan
        logger.info(f"LLM decomposed request into {len(plan.tasks)} tasks")

        return plan

    def get_plan(self, plan_id: str) -> Optional[TaskPlan]:
        """Get a plan by ID."""
        return self._plans.get(plan_id)

    def get_all_plans(self) -> list[TaskPlan]:
        """Get all plans."""
        return list(self._plans.values())

    def clear_completed_plans(self) -> int:
        """Remove completed plans from memory."""
        completed = [
            pid for pid, plan in self._plans.items()
            if plan.status == "completed"
        ]
        for pid in completed:
            del self._plans[pid]
        return len(completed)


# Global instance
_task_decomposer: Optional[TaskDecomposer] = None


def get_task_decomposer() -> TaskDecomposer:
    """Get or create the global task decomposer."""
    global _task_decomposer
    if _task_decomposer is None:
        _task_decomposer = TaskDecomposer()
    return _task_decomposer
