"""
Agent Orchestrator for the Smart-HES Agent Framework.

Coordinates multiple specialized agents to handle complex user requests.
Manages task distribution, agent communication, and result aggregation.
"""

import asyncio
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional
from uuid import uuid4

from loguru import logger

from src.ai.agents.base_agent import (
    AbstractAgent,
    AgentMessage,
    AgentResult,
    AgentState,
    AgentTask,
    MessageType,
)
from src.ai.orchestrator.task_decomposer import (
    DecomposedTask,
    TaskDecomposer,
    TaskPlan,
    TaskStatus,
    get_task_decomposer,
)


class OrchestratorState(str, Enum):
    """States the orchestrator can be in."""
    IDLE = "idle"
    PLANNING = "planning"
    EXECUTING = "executing"
    AGGREGATING = "aggregating"
    ERROR = "error"


@dataclass
class ExecutionContext:
    """Context for a request execution."""
    context_id: str
    original_request: str
    plan: Optional[TaskPlan] = None
    results: dict = field(default_factory=dict)  # task_id -> result
    start_time: datetime = field(default_factory=datetime.utcnow)
    end_time: Optional[datetime] = None
    status: str = "pending"
    error: Optional[str] = None

    @classmethod
    def create(cls, request: str) -> "ExecutionContext":
        return cls(
            context_id=str(uuid4()),
            original_request=request,
        )


class AgentOrchestrator:
    """
    Orchestrates multiple AI agents to handle user requests.

    Features:
    - Agent registration and management
    - Task decomposition and distribution
    - Parallel task execution
    - Result aggregation
    - Error handling and recovery
    """

    def __init__(
        self,
        task_decomposer: Optional[TaskDecomposer] = None,
        max_parallel_tasks: int = 3,
    ):
        self.task_decomposer = task_decomposer or get_task_decomposer()
        self.max_parallel_tasks = max_parallel_tasks
        self.state = OrchestratorState.IDLE

        # Agent registry
        self._agents: dict[str, AbstractAgent] = {}
        self._agent_by_type: dict[str, list[str]] = {}  # type -> [agent_ids]

        # Execution tracking
        self._active_contexts: dict[str, ExecutionContext] = {}
        self._execution_history: list[ExecutionContext] = []

        # Statistics
        self._stats = {
            "total_requests": 0,
            "successful_requests": 0,
            "failed_requests": 0,
            "total_tasks_executed": 0,
            "average_execution_time_ms": 0.0,
        }

        logger.info(f"AgentOrchestrator initialized (max_parallel={max_parallel_tasks})")

    def register_agent(self, agent: AbstractAgent) -> None:
        """
        Register an agent with the orchestrator.

        Args:
            agent: The agent to register
        """
        self._agents[agent.agent_id] = agent

        # Index by type
        agent_type = agent.agent_type
        if agent_type not in self._agent_by_type:
            self._agent_by_type[agent_type] = []
        self._agent_by_type[agent_type].append(agent.agent_id)

        logger.info(f"Registered agent: {agent.name} ({agent.agent_type})")

    def unregister_agent(self, agent_id: str) -> bool:
        """Unregister an agent."""
        if agent_id not in self._agents:
            return False

        agent = self._agents[agent_id]
        agent_type = agent.agent_type

        # Remove from type index
        if agent_type in self._agent_by_type:
            self._agent_by_type[agent_type] = [
                aid for aid in self._agent_by_type[agent_type]
                if aid != agent_id
            ]

        del self._agents[agent_id]
        logger.info(f"Unregistered agent: {agent.name}")
        return True

    def get_agent(self, agent_id: str) -> Optional[AbstractAgent]:
        """Get an agent by ID."""
        return self._agents.get(agent_id)

    def get_agents_by_type(self, agent_type: str) -> list[AbstractAgent]:
        """Get all agents of a specific type."""
        agent_ids = self._agent_by_type.get(agent_type, [])
        return [self._agents[aid] for aid in agent_ids if aid in self._agents]

    def _select_agent_for_task(self, task: DecomposedTask) -> Optional[AbstractAgent]:
        """Select the best agent for a task."""
        candidates = self.get_agents_by_type(task.task_type)

        if not candidates:
            logger.warning(f"No agents available for task type: {task.task_type}")
            return None

        # Select agent with lowest load (simplest strategy)
        # Could be enhanced with more sophisticated load balancing
        best_agent = None
        lowest_queue = float("inf")

        for agent in candidates:
            if agent.state in [AgentState.IDLE, AgentState.WAITING]:
                queue_size = len(agent._message_queue)
                if queue_size < lowest_queue:
                    lowest_queue = queue_size
                    best_agent = agent

        # If no idle agent, use the first one
        return best_agent or candidates[0]

    async def process_request(
        self,
        user_request: str,
        use_llm_decomposition: bool = False,
        llm_engine: Any = None,
        context: dict = None,
    ) -> ExecutionContext:
        """
        Process a user request end-to-end.

        Args:
            user_request: The user's natural language request
            use_llm_decomposition: Whether to use LLM for complex decomposition
            llm_engine: LLMEngine instance (required if use_llm_decomposition)
            context: Optional context for task decomposition

        Returns:
            ExecutionContext with results
        """
        self.state = OrchestratorState.PLANNING
        self._stats["total_requests"] += 1

        # Create execution context
        exec_context = ExecutionContext.create(user_request)
        self._active_contexts[exec_context.context_id] = exec_context

        try:
            # Decompose the request into tasks
            if use_llm_decomposition and llm_engine:
                plan = await self.task_decomposer.decompose_with_llm(
                    user_request, llm_engine, context
                )
            else:
                plan = self.task_decomposer.decompose_simple(user_request)

            exec_context.plan = plan

            # Execute the plan
            self.state = OrchestratorState.EXECUTING
            await self._execute_plan(exec_context)

            # Aggregate results
            self.state = OrchestratorState.AGGREGATING
            self._aggregate_results(exec_context)

            exec_context.status = "completed"
            exec_context.end_time = datetime.utcnow()
            self._stats["successful_requests"] += 1

        except Exception as e:
            logger.error(f"Request processing failed: {e}")
            exec_context.status = "failed"
            exec_context.error = str(e)
            exec_context.end_time = datetime.utcnow()
            self._stats["failed_requests"] += 1

        finally:
            self.state = OrchestratorState.IDLE
            self._execution_history.append(exec_context)
            del self._active_contexts[exec_context.context_id]

        return exec_context

    async def _execute_plan(self, exec_context: ExecutionContext) -> None:
        """Execute all tasks in a plan respecting dependencies."""
        plan = exec_context.plan
        if not plan:
            return

        # Keep executing until all tasks are done
        while True:
            # Get tasks ready to execute
            ready_tasks = plan.get_ready_tasks()
            if not ready_tasks:
                # Check if any tasks are still in progress
                in_progress = [t for t in plan.tasks if t.status == TaskStatus.IN_PROGRESS]
                if not in_progress:
                    break
                # Wait for in-progress tasks
                await asyncio.sleep(0.1)
                continue

            # Execute ready tasks (up to max_parallel)
            tasks_to_execute = ready_tasks[:self.max_parallel_tasks]

            # Execute in parallel
            execution_coroutines = [
                self._execute_task(task, exec_context)
                for task in tasks_to_execute
            ]
            await asyncio.gather(*execution_coroutines)

            plan.update_progress()

    async def _execute_task(
        self,
        task: DecomposedTask,
        exec_context: ExecutionContext,
    ) -> None:
        """Execute a single task."""
        start_time = time.perf_counter()

        # Mark as in progress
        task.status = TaskStatus.IN_PROGRESS
        task.started_at = datetime.utcnow()

        # Select an agent
        agent = self._select_agent_for_task(task)
        if not agent:
            task.status = TaskStatus.FAILED
            task.error = f"No agent available for task type: {task.task_type}"
            return

        task.assigned_agent = agent.agent_id

        try:
            # Create agent task
            agent_task = AgentTask.create(
                task_type=task.action,
                description=task.description,
                parameters=task.parameters,
                priority=task.priority.value,
            )

            # Execute
            result = await agent.execute_task(agent_task)

            # Update task status
            if result.success:
                task.status = TaskStatus.COMPLETED
                task.result = result.to_dict()
            else:
                task.status = TaskStatus.FAILED
                task.error = result.error

            # Store result
            exec_context.results[task.task_id] = result

        except Exception as e:
            logger.error(f"Task execution failed: {e}")
            task.status = TaskStatus.FAILED
            task.error = str(e)

        finally:
            task.completed_at = datetime.utcnow()
            execution_time = (time.perf_counter() - start_time) * 1000
            self._stats["total_tasks_executed"] += 1
            logger.debug(f"Task {task.action} completed in {execution_time:.1f}ms")

    def _aggregate_results(self, exec_context: ExecutionContext) -> None:
        """Aggregate results from all tasks."""
        # Simple aggregation - combine all results
        aggregated = {
            "context_id": exec_context.context_id,
            "request": exec_context.original_request,
            "task_results": [],
            "summary": {},
        }

        for task_id, result in exec_context.results.items():
            aggregated["task_results"].append({
                "task_id": task_id,
                "success": result.success,
                "data": result.data,
                "error": result.error,
            })

        # Add summary statistics
        total_tasks = len(exec_context.results)
        successful_tasks = sum(1 for r in exec_context.results.values() if r.success)
        aggregated["summary"] = {
            "total_tasks": total_tasks,
            "successful_tasks": successful_tasks,
            "failed_tasks": total_tasks - successful_tasks,
            "success_rate": successful_tasks / total_tasks if total_tasks > 0 else 0,
        }

        exec_context.results["_aggregated"] = aggregated

    async def send_message(
        self,
        from_agent_id: str,
        to_agent_id: str,
        message_type: MessageType,
        content: dict,
    ) -> Optional[AgentMessage]:
        """Send a message between agents."""
        target_agent = self._agents.get(to_agent_id)
        if not target_agent:
            logger.warning(f"Target agent not found: {to_agent_id}")
            return None

        message = AgentMessage.create(
            sender=from_agent_id,
            receiver=to_agent_id,
            message_type=message_type,
            content=content,
        )

        target_agent.queue_message(message)
        logger.debug(f"Message sent: {from_agent_id} -> {to_agent_id}")

        return message

    async def broadcast_message(
        self,
        from_agent_id: str,
        message_type: MessageType,
        content: dict,
        agent_type: Optional[str] = None,
    ) -> list[AgentMessage]:
        """Broadcast a message to multiple agents."""
        messages = []

        if agent_type:
            targets = self.get_agents_by_type(agent_type)
        else:
            targets = list(self._agents.values())

        for agent in targets:
            if agent.agent_id != from_agent_id:
                msg = await self.send_message(
                    from_agent_id, agent.agent_id, message_type, content
                )
                if msg:
                    messages.append(msg)

        return messages

    def get_status(self) -> dict:
        """Get orchestrator status."""
        return {
            "state": self.state.value,
            "registered_agents": len(self._agents),
            "agents_by_type": {
                t: len(ids) for t, ids in self._agent_by_type.items()
            },
            "active_contexts": len(self._active_contexts),
            "stats": self._stats.copy(),
        }

    def get_agent_statuses(self) -> list[dict]:
        """Get status of all registered agents."""
        return [agent.get_status() for agent in self._agents.values()]


# Global instance
_orchestrator: Optional[AgentOrchestrator] = None


def get_orchestrator() -> AgentOrchestrator:
    """Get or create the global orchestrator instance."""
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = AgentOrchestrator()
    return _orchestrator


async def initialize_orchestrator(
    max_parallel_tasks: int = 3,
) -> AgentOrchestrator:
    """Initialize and return the orchestrator."""
    global _orchestrator
    _orchestrator = AgentOrchestrator(max_parallel_tasks=max_parallel_tasks)
    return _orchestrator
