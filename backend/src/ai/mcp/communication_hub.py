"""
MCP Communication Hub for the Smart-HES Agent Framework.

Implements a Model Context Protocol inspired communication system
for agent-to-agent messaging and coordination.
"""

import asyncio
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Optional
from uuid import uuid4

from loguru import logger

from src.ai.agents.base_agent import AgentMessage, MessageType


class ChannelType(str, Enum):
    """Types of communication channels."""
    DIRECT = "direct"       # Point-to-point
    BROADCAST = "broadcast" # One-to-many
    TOPIC = "topic"         # Pub/sub by topic


@dataclass
class MessageEnvelope:
    """Wrapper for messages with routing metadata."""
    envelope_id: str
    message: AgentMessage
    channel_type: ChannelType
    topic: Optional[str] = None
    priority: int = 5  # 1=highest, 10=lowest
    ttl_seconds: int = 300  # Time to live
    created_at: datetime = field(default_factory=datetime.utcnow)
    delivered: bool = False
    delivery_attempts: int = 0

    @property
    def is_expired(self) -> bool:
        """Check if message has expired."""
        age = (datetime.utcnow() - self.created_at).total_seconds()
        return age > self.ttl_seconds


@dataclass
class Subscription:
    """A topic subscription."""
    subscription_id: str
    agent_id: str
    topic: str
    callback: Optional[Callable] = None
    filter_fn: Optional[Callable] = None  # Optional filter function
    created_at: datetime = field(default_factory=datetime.utcnow)


class MCPCommunicationHub:
    """
    Central communication hub for agent messaging.

    Features:
    - Direct agent-to-agent messaging
    - Broadcast messaging
    - Topic-based pub/sub
    - Message queuing and delivery
    - Message history and tracing
    """

    def __init__(
        self,
        max_queue_size: int = 1000,
        enable_persistence: bool = False,
    ):
        # Message queues by agent
        self._agent_queues: dict[str, asyncio.Queue] = {}

        # Topic subscriptions
        self._subscriptions: dict[str, list[Subscription]] = defaultdict(list)
        self._agent_subscriptions: dict[str, list[str]] = defaultdict(list)

        # Message history
        self._message_history: list[MessageEnvelope] = []
        self._max_history = 1000

        # Registered agents
        self._registered_agents: set[str] = set()

        # Configuration
        self.max_queue_size = max_queue_size
        self.enable_persistence = enable_persistence

        # Statistics
        self._stats = {
            "messages_sent": 0,
            "messages_delivered": 0,
            "messages_dropped": 0,
            "broadcast_messages": 0,
            "topic_messages": 0,
        }

        logger.info("MCPCommunicationHub initialized")

    def register_agent(self, agent_id: str) -> None:
        """Register an agent with the hub."""
        if agent_id not in self._registered_agents:
            self._registered_agents.add(agent_id)
            self._agent_queues[agent_id] = asyncio.Queue(maxsize=self.max_queue_size)
            logger.debug(f"Agent registered with MCP hub: {agent_id}")

    def unregister_agent(self, agent_id: str) -> None:
        """Unregister an agent from the hub."""
        if agent_id in self._registered_agents:
            self._registered_agents.remove(agent_id)

            # Remove queue
            if agent_id in self._agent_queues:
                del self._agent_queues[agent_id]

            # Remove subscriptions
            for topic, subs in self._subscriptions.items():
                self._subscriptions[topic] = [s for s in subs if s.agent_id != agent_id]

            if agent_id in self._agent_subscriptions:
                del self._agent_subscriptions[agent_id]

            logger.debug(f"Agent unregistered from MCP hub: {agent_id}")

    async def send_direct(
        self,
        message: AgentMessage,
        priority: int = 5,
        ttl_seconds: int = 300,
    ) -> bool:
        """
        Send a direct message to a specific agent.

        Args:
            message: The message to send
            priority: Message priority (1=highest)
            ttl_seconds: Time to live in seconds

        Returns:
            True if queued successfully
        """
        receiver = message.receiver

        if receiver not in self._registered_agents:
            logger.warning(f"Cannot send to unregistered agent: {receiver}")
            self._stats["messages_dropped"] += 1
            return False

        envelope = MessageEnvelope(
            envelope_id=str(uuid4()),
            message=message,
            channel_type=ChannelType.DIRECT,
            priority=priority,
            ttl_seconds=ttl_seconds,
        )

        try:
            queue = self._agent_queues[receiver]
            await asyncio.wait_for(
                queue.put(envelope),
                timeout=1.0,
            )
            self._stats["messages_sent"] += 1
            self._add_to_history(envelope)
            return True

        except asyncio.TimeoutError:
            logger.warning(f"Queue full for agent: {receiver}")
            self._stats["messages_dropped"] += 1
            return False

    async def broadcast(
        self,
        sender: str,
        message_type: MessageType,
        content: dict,
        exclude: list[str] = None,
    ) -> int:
        """
        Broadcast a message to all registered agents.

        Args:
            sender: Sender agent ID
            message_type: Type of message
            content: Message content
            exclude: Agents to exclude from broadcast

        Returns:
            Number of agents the message was sent to
        """
        exclude = exclude or []
        exclude.append(sender)  # Don't send to self

        sent_count = 0

        for agent_id in self._registered_agents:
            if agent_id in exclude:
                continue

            message = AgentMessage.create(
                sender=sender,
                receiver=agent_id,
                message_type=message_type,
                content=content,
            )

            envelope = MessageEnvelope(
                envelope_id=str(uuid4()),
                message=message,
                channel_type=ChannelType.BROADCAST,
            )

            try:
                queue = self._agent_queues.get(agent_id)
                if queue:
                    await asyncio.wait_for(queue.put(envelope), timeout=0.5)
                    sent_count += 1
            except (asyncio.TimeoutError, asyncio.QueueFull):
                pass

        self._stats["broadcast_messages"] += 1
        self._stats["messages_sent"] += sent_count

        return sent_count

    def subscribe(
        self,
        agent_id: str,
        topic: str,
        callback: Optional[Callable] = None,
        filter_fn: Optional[Callable] = None,
    ) -> str:
        """
        Subscribe an agent to a topic.

        Args:
            agent_id: Agent to subscribe
            topic: Topic name
            callback: Optional callback for immediate delivery
            filter_fn: Optional filter function

        Returns:
            Subscription ID
        """
        subscription = Subscription(
            subscription_id=str(uuid4()),
            agent_id=agent_id,
            topic=topic,
            callback=callback,
            filter_fn=filter_fn,
        )

        self._subscriptions[topic].append(subscription)
        self._agent_subscriptions[agent_id].append(subscription.subscription_id)

        logger.debug(f"Agent {agent_id} subscribed to topic: {topic}")

        return subscription.subscription_id

    def unsubscribe(self, subscription_id: str) -> bool:
        """Unsubscribe from a topic."""
        for topic, subs in self._subscriptions.items():
            for sub in subs:
                if sub.subscription_id == subscription_id:
                    subs.remove(sub)

                    # Remove from agent subscriptions
                    if sub.agent_id in self._agent_subscriptions:
                        agent_subs = self._agent_subscriptions[sub.agent_id]
                        if subscription_id in agent_subs:
                            agent_subs.remove(subscription_id)

                    return True
        return False

    async def publish(
        self,
        sender: str,
        topic: str,
        content: dict,
        message_type: MessageType = MessageType.NOTIFICATION,
    ) -> int:
        """
        Publish a message to a topic.

        Args:
            sender: Sender agent ID
            topic: Topic to publish to
            content: Message content
            message_type: Type of message

        Returns:
            Number of subscribers notified
        """
        subscribers = self._subscriptions.get(topic, [])
        notified = 0

        for sub in subscribers:
            # Apply filter if present
            if sub.filter_fn and not sub.filter_fn(content):
                continue

            message = AgentMessage.create(
                sender=sender,
                receiver=sub.agent_id,
                message_type=message_type,
                content={"topic": topic, "data": content},
            )

            envelope = MessageEnvelope(
                envelope_id=str(uuid4()),
                message=message,
                channel_type=ChannelType.TOPIC,
                topic=topic,
            )

            # Use callback if available
            if sub.callback:
                try:
                    if asyncio.iscoroutinefunction(sub.callback):
                        await sub.callback(message)
                    else:
                        sub.callback(message)
                    notified += 1
                except Exception as e:
                    logger.error(f"Callback error for subscription {sub.subscription_id}: {e}")
            else:
                # Queue the message
                queue = self._agent_queues.get(sub.agent_id)
                if queue:
                    try:
                        await asyncio.wait_for(queue.put(envelope), timeout=0.5)
                        notified += 1
                    except (asyncio.TimeoutError, asyncio.QueueFull):
                        pass

        self._stats["topic_messages"] += 1
        self._stats["messages_sent"] += notified

        return notified

    async def receive(
        self,
        agent_id: str,
        timeout: float = None,
    ) -> Optional[MessageEnvelope]:
        """
        Receive a message for an agent.

        Args:
            agent_id: Agent ID to receive for
            timeout: Optional timeout in seconds

        Returns:
            MessageEnvelope if available, None otherwise
        """
        queue = self._agent_queues.get(agent_id)
        if not queue:
            return None

        try:
            if timeout:
                envelope = await asyncio.wait_for(queue.get(), timeout=timeout)
            else:
                envelope = queue.get_nowait()

            # Check expiration
            if envelope.is_expired:
                self._stats["messages_dropped"] += 1
                return None

            envelope.delivered = True
            self._stats["messages_delivered"] += 1

            return envelope

        except (asyncio.TimeoutError, asyncio.QueueEmpty):
            return None

    async def receive_all(self, agent_id: str) -> list[MessageEnvelope]:
        """Receive all pending messages for an agent."""
        messages = []
        while True:
            envelope = await self.receive(agent_id)
            if envelope is None:
                break
            messages.append(envelope)
        return messages

    def get_queue_size(self, agent_id: str) -> int:
        """Get the current queue size for an agent."""
        queue = self._agent_queues.get(agent_id)
        return queue.qsize() if queue else 0

    def get_topics(self) -> list[str]:
        """Get all active topics."""
        return list(self._subscriptions.keys())

    def get_topic_subscribers(self, topic: str) -> list[str]:
        """Get all subscribers for a topic."""
        return [s.agent_id for s in self._subscriptions.get(topic, [])]

    def get_stats(self) -> dict:
        """Get hub statistics."""
        return {
            **self._stats.copy(),
            "registered_agents": len(self._registered_agents),
            "active_topics": len(self._subscriptions),
            "total_subscriptions": sum(len(s) for s in self._subscriptions.values()),
            "history_size": len(self._message_history),
        }

    def get_message_history(
        self,
        agent_id: Optional[str] = None,
        limit: int = 100,
    ) -> list[dict]:
        """Get message history."""
        history = self._message_history[-limit:]

        if agent_id:
            history = [
                h for h in history
                if h.message.sender == agent_id or h.message.receiver == agent_id
            ]

        return [
            {
                "envelope_id": h.envelope_id,
                "sender": h.message.sender,
                "receiver": h.message.receiver,
                "type": h.message.message_type.value,
                "channel": h.channel_type.value,
                "topic": h.topic,
                "delivered": h.delivered,
                "created_at": h.created_at.isoformat(),
            }
            for h in history
        ]

    def _add_to_history(self, envelope: MessageEnvelope) -> None:
        """Add message to history."""
        self._message_history.append(envelope)
        if len(self._message_history) > self._max_history:
            self._message_history = self._message_history[-self._max_history:]


# Global instance
_mcp_hub: Optional[MCPCommunicationHub] = None


def get_mcp_hub() -> MCPCommunicationHub:
    """Get or create the global MCP hub."""
    global _mcp_hub
    if _mcp_hub is None:
        _mcp_hub = MCPCommunicationHub()
    return _mcp_hub


def initialize_mcp_hub(
    max_queue_size: int = 1000,
    enable_persistence: bool = False,
) -> MCPCommunicationHub:
    """Initialize the MCP hub with custom settings."""
    global _mcp_hub
    _mcp_hub = MCPCommunicationHub(
        max_queue_size=max_queue_size,
        enable_persistence=enable_persistence,
    )
    return _mcp_hub
