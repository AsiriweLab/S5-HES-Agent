"""
Abstract Base Agent for the Smart-HES Agent Framework.

Provides the foundation for all specialized agents with:
- Common interface for agent operations
- State management
- Message handling
- Tool execution framework
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional
from uuid import uuid4

from loguru import logger


class AgentState(str, Enum):
    """States an agent can be in."""
    IDLE = "idle"           # Ready for tasks
    THINKING = "thinking"   # Processing/planning
    EXECUTING = "executing" # Running a task
    WAITING = "waiting"     # Waiting for input/response
    ERROR = "error"         # Error state
    COMPLETED = "completed" # Task completed


class MessageType(str, Enum):
    """Types of messages agents can exchange."""
    REQUEST = "request"       # Request for action
    RESPONSE = "response"     # Response to request
    NOTIFICATION = "notification"  # Informational
    ERROR = "error"           # Error message
    STATUS = "status"         # Status update


@dataclass
class AgentMessage:
    """A message between agents or from the orchestrator."""
    message_id: str
    sender: str
    receiver: str
    message_type: MessageType
    content: dict
    timestamp: datetime = field(default_factory=datetime.utcnow)
    correlation_id: Optional[str] = None  # For request-response tracking
    metadata: dict = field(default_factory=dict)

    @classmethod
    def create(
        cls,
        sender: str,
        receiver: str,
        message_type: MessageType,
        content: dict,
        correlation_id: Optional[str] = None,
    ) -> "AgentMessage":
        """Factory method to create a new message."""
        return cls(
            message_id=str(uuid4()),
            sender=sender,
            receiver=receiver,
            message_type=message_type,
            content=content,
            correlation_id=correlation_id,
        )

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "message_id": self.message_id,
            "sender": self.sender,
            "receiver": self.receiver,
            "message_type": self.message_type.value,
            "content": self.content,
            "timestamp": self.timestamp.isoformat(),
            "correlation_id": self.correlation_id,
            "metadata": self.metadata,
        }


@dataclass
class AgentTask:
    """A task assigned to an agent."""
    task_id: str
    task_type: str
    description: str
    parameters: dict = field(default_factory=dict)
    priority: int = 1  # 1=highest, 5=lowest
    created_at: datetime = field(default_factory=datetime.utcnow)
    deadline: Optional[datetime] = None
    parent_task_id: Optional[str] = None  # For sub-tasks
    status: str = "pending"
    result: Optional[dict] = None

    @classmethod
    def create(
        cls,
        task_type: str,
        description: str,
        parameters: dict = None,
        priority: int = 1,
    ) -> "AgentTask":
        """Factory method to create a new task."""
        return cls(
            task_id=str(uuid4()),
            task_type=task_type,
            description=description,
            parameters=parameters or {},
            priority=priority,
        )


@dataclass
class AgentResult:
    """Result of an agent action."""
    success: bool
    data: Any = None
    error: Optional[str] = None
    confidence: float = 1.0
    sources: list[str] = field(default_factory=list)
    execution_time_ms: float = 0.0
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "success": self.success,
            "data": self.data,
            "error": self.error,
            "confidence": self.confidence,
            "sources": self.sources,
            "execution_time_ms": self.execution_time_ms,
            "metadata": self.metadata,
        }


class AbstractAgent(ABC):
    """
    Abstract base class for all Smart-HES agents.

    Features:
    - Unified interface for agent operations
    - State management and tracking
    - Message queue handling
    - Tool registration and execution
    """

    def __init__(
        self,
        agent_id: Optional[str] = None,
        name: str = "Agent",
        description: str = "",
    ):
        self.agent_id = agent_id or str(uuid4())
        self.name = name
        self.description = description
        self.state = AgentState.IDLE

        # Message handling
        self._message_queue: list[AgentMessage] = []
        self._message_handlers: dict[MessageType, callable] = {}

        # Tool registry
        self._tools: dict[str, callable] = {}

        # Task tracking
        self._current_task: Optional[AgentTask] = None
        self._task_history: list[AgentTask] = []

        # Statistics
        self._stats = {
            "tasks_completed": 0,
            "tasks_failed": 0,
            "messages_sent": 0,
            "messages_received": 0,
            "total_execution_time_ms": 0.0,
        }

        logger.info(f"Agent initialized: {self.name} ({self.agent_id})")

    @property
    @abstractmethod
    def agent_type(self) -> str:
        """Return the type of this agent."""
        pass

    @property
    @abstractmethod
    def capabilities(self) -> list[str]:
        """Return the list of capabilities this agent has."""
        pass

    @abstractmethod
    async def execute_task(self, task: AgentTask) -> AgentResult:
        """
        Execute a task assigned to this agent.

        Args:
            task: The task to execute

        Returns:
            AgentResult with the outcome
        """
        pass

    @abstractmethod
    async def handle_message(self, message: AgentMessage) -> Optional[AgentMessage]:
        """
        Handle an incoming message.

        Args:
            message: The incoming message

        Returns:
            Optional response message
        """
        pass

    def register_tool(self, name: str, func: callable, description: str = "") -> None:
        """Register a tool that this agent can use."""
        self._tools[name] = {
            "function": func,
            "description": description,
        }
        logger.debug(f"Agent {self.name}: Registered tool '{name}'")

    async def use_tool(self, tool_name: str, **kwargs) -> Any:
        """Use a registered tool."""
        if tool_name not in self._tools:
            raise ValueError(f"Tool '{tool_name}' not registered")

        tool = self._tools[tool_name]
        func = tool["function"]

        # Check if async
        import asyncio
        if asyncio.iscoroutinefunction(func):
            return await func(**kwargs)
        return func(**kwargs)

    def get_available_tools(self) -> list[dict]:
        """Get list of available tools."""
        return [
            {"name": name, "description": tool["description"]}
            for name, tool in self._tools.items()
        ]

    def set_state(self, state: AgentState) -> None:
        """Update the agent's state."""
        old_state = self.state
        self.state = state
        logger.debug(f"Agent {self.name}: State changed {old_state.value} -> {state.value}")

    def queue_message(self, message: AgentMessage) -> None:
        """Add a message to the agent's queue."""
        self._message_queue.append(message)
        self._stats["messages_received"] += 1

    def get_pending_messages(self) -> list[AgentMessage]:
        """Get all pending messages."""
        messages = self._message_queue.copy()
        self._message_queue.clear()
        return messages

    async def process_messages(self) -> list[AgentMessage]:
        """Process all pending messages and return responses."""
        responses = []
        for message in self.get_pending_messages():
            response = await self.handle_message(message)
            if response:
                responses.append(response)
                self._stats["messages_sent"] += 1
        return responses

    def get_status(self) -> dict:
        """Get the current status of the agent."""
        return {
            "agent_id": self.agent_id,
            "name": self.name,
            "type": self.agent_type,
            "state": self.state.value,
            "capabilities": self.capabilities,
            "current_task": self._current_task.task_id if self._current_task else None,
            "pending_messages": len(self._message_queue),
            "stats": self._stats.copy(),
        }

    def get_task_history(self, limit: int = 10) -> list[dict]:
        """Get recent task history."""
        return [
            {
                "task_id": t.task_id,
                "task_type": t.task_type,
                "status": t.status,
                "created_at": t.created_at.isoformat(),
            }
            for t in self._task_history[-limit:]
        ]

    def _record_task_completion(self, task: AgentTask, result: AgentResult) -> None:
        """Record task completion in history and stats."""
        task.status = "completed" if result.success else "failed"
        task.result = result.to_dict()
        self._task_history.append(task)

        if result.success:
            self._stats["tasks_completed"] += 1
        else:
            self._stats["tasks_failed"] += 1
        self._stats["total_execution_time_ms"] += result.execution_time_ms

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}(id={self.agent_id}, name={self.name}, state={self.state.value})>"
