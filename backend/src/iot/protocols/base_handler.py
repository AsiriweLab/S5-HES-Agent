"""
Abstract Protocol Handler - Base class for all IoT protocol implementations.

Sprint 11 - S11.1: AbstractProtocolHandler base class
Provides common interface for MQTT, CoAP, HTTP/REST, and WebSocket handlers.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Coroutine, Optional
import asyncio
import uuid
from loguru import logger


class ProtocolType(str, Enum):
    """Supported IoT communication protocols."""
    MQTT = "mqtt"
    COAP = "coap"
    HTTP = "http"
    WEBSOCKET = "websocket"
    ZIGBEE = "zigbee"
    BLE = "ble"
    ZWAVE = "zwave"


class ConnectionState(str, Enum):
    """Protocol connection states."""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    RECONNECTING = "reconnecting"
    ERROR = "error"


class QoSLevel(int, Enum):
    """Quality of Service levels (primarily for MQTT)."""
    AT_MOST_ONCE = 0   # Fire and forget
    AT_LEAST_ONCE = 1  # Acknowledged delivery
    EXACTLY_ONCE = 2   # Assured delivery


@dataclass
class ProtocolMessage:
    """Standard message format for all protocols."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    topic: str = ""
    payload: Any = None
    timestamp: datetime = field(default_factory=datetime.now)
    qos: QoSLevel = QoSLevel.AT_MOST_ONCE
    retain: bool = False
    headers: dict[str, str] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert message to dictionary."""
        return {
            "id": self.id,
            "topic": self.topic,
            "payload": self.payload,
            "timestamp": self.timestamp.isoformat(),
            "qos": self.qos.value,
            "retain": self.retain,
            "headers": self.headers,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ProtocolMessage":
        """Create message from dictionary."""
        return cls(
            id=data.get("id", str(uuid.uuid4())),
            topic=data.get("topic", ""),
            payload=data.get("payload"),
            timestamp=datetime.fromisoformat(data["timestamp"]) if "timestamp" in data else datetime.now(),
            qos=QoSLevel(data.get("qos", 0)),
            retain=data.get("retain", False),
            headers=data.get("headers", {}),
            metadata=data.get("metadata", {}),
        )


@dataclass
class ProtocolConfig:
    """Base configuration for protocol handlers."""
    host: str = "localhost"
    port: int = 0
    username: Optional[str] = None
    password: Optional[str] = None
    use_tls: bool = False
    tls_cert_path: Optional[str] = None
    tls_key_path: Optional[str] = None
    tls_ca_path: Optional[str] = None
    connection_timeout: float = 30.0
    keep_alive: int = 60
    reconnect_interval: float = 5.0
    max_reconnect_attempts: int = 10
    client_id: str = field(default_factory=lambda: f"smart-hes-{uuid.uuid4().hex[:8]}")
    extra_config: dict[str, Any] = field(default_factory=dict)


@dataclass
class ProtocolStats:
    """Statistics for protocol handler."""
    messages_sent: int = 0
    messages_received: int = 0
    bytes_sent: int = 0
    bytes_received: int = 0
    errors: int = 0
    reconnects: int = 0
    last_activity: Optional[datetime] = None
    connected_since: Optional[datetime] = None

    def record_sent(self, size: int = 0) -> None:
        """Record a sent message."""
        self.messages_sent += 1
        self.bytes_sent += size
        self.last_activity = datetime.now()

    def record_received(self, size: int = 0) -> None:
        """Record a received message."""
        self.messages_received += 1
        self.bytes_received += size
        self.last_activity = datetime.now()

    def record_error(self) -> None:
        """Record an error."""
        self.errors += 1
        self.last_activity = datetime.now()

    def to_dict(self) -> dict[str, Any]:
        """Convert stats to dictionary."""
        return {
            "messages_sent": self.messages_sent,
            "messages_received": self.messages_received,
            "bytes_sent": self.bytes_sent,
            "bytes_received": self.bytes_received,
            "errors": self.errors,
            "reconnects": self.reconnects,
            "last_activity": self.last_activity.isoformat() if self.last_activity else None,
            "connected_since": self.connected_since.isoformat() if self.connected_since else None,
        }


# Type aliases for callbacks
MessageCallback = Callable[[ProtocolMessage], None]
AsyncMessageCallback = Callable[[ProtocolMessage], Coroutine[Any, Any, None]]


class AbstractProtocolHandler(ABC):
    """
    Abstract base class for all IoT protocol handlers.

    Provides common interface for:
    - Connection management
    - Message publishing/subscribing
    - Statistics tracking
    - Error handling
    """

    def __init__(self, config: ProtocolConfig):
        """
        Initialize protocol handler.

        Args:
            config: Protocol configuration
        """
        self.config = config
        self.state = ConnectionState.DISCONNECTED
        self.stats = ProtocolStats()
        self._subscriptions: dict[str, list[MessageCallback | AsyncMessageCallback]] = {}
        self._message_queue: asyncio.Queue[ProtocolMessage] = asyncio.Queue()
        self._running = False
        self._reconnect_task: Optional[asyncio.Task] = None

        logger.info(f"Initialized {self.protocol_type.value} handler with client_id: {config.client_id}")

    @property
    @abstractmethod
    def protocol_type(self) -> ProtocolType:
        """Return the protocol type."""
        pass

    @property
    def is_connected(self) -> bool:
        """Check if handler is connected."""
        return self.state == ConnectionState.CONNECTED

    @abstractmethod
    async def connect(self) -> bool:
        """
        Connect to the protocol endpoint.

        Returns:
            True if connection successful, False otherwise
        """
        pass

    @abstractmethod
    async def disconnect(self) -> None:
        """Disconnect from the protocol endpoint."""
        pass

    @abstractmethod
    async def publish(self, message: ProtocolMessage) -> bool:
        """
        Publish a message.

        Args:
            message: Message to publish

        Returns:
            True if publish successful, False otherwise
        """
        pass

    @abstractmethod
    async def subscribe(self, topic: str, callback: MessageCallback | AsyncMessageCallback) -> bool:
        """
        Subscribe to a topic.

        Args:
            topic: Topic pattern to subscribe to
            callback: Callback function for received messages

        Returns:
            True if subscription successful, False otherwise
        """
        pass

    @abstractmethod
    async def unsubscribe(self, topic: str) -> bool:
        """
        Unsubscribe from a topic.

        Args:
            topic: Topic to unsubscribe from

        Returns:
            True if unsubscription successful, False otherwise
        """
        pass

    async def publish_dict(
        self,
        topic: str,
        payload: dict[str, Any],
        qos: QoSLevel = QoSLevel.AT_MOST_ONCE,
        retain: bool = False,
    ) -> bool:
        """
        Convenience method to publish a dictionary payload.

        Args:
            topic: Topic to publish to
            payload: Dictionary payload
            qos: Quality of Service level
            retain: Whether to retain the message

        Returns:
            True if publish successful
        """
        message = ProtocolMessage(
            topic=topic,
            payload=payload,
            qos=qos,
            retain=retain,
        )
        return await self.publish(message)

    async def _handle_message(self, message: ProtocolMessage) -> None:
        """
        Handle received message by calling registered callbacks.

        Args:
            message: Received message
        """
        self.stats.record_received()

        # Find matching subscriptions
        for pattern, callbacks in self._subscriptions.items():
            if self._topic_matches(pattern, message.topic):
                for callback in callbacks:
                    try:
                        if asyncio.iscoroutinefunction(callback):
                            await callback(message)
                        else:
                            callback(message)
                    except Exception as e:
                        logger.error(f"Error in message callback: {e}")
                        self.stats.record_error()

    def _topic_matches(self, pattern: str, topic: str) -> bool:
        """
        Check if a topic matches a subscription pattern.
        Supports MQTT-style wildcards: + (single level) and # (multi-level).

        Args:
            pattern: Subscription pattern
            topic: Actual topic

        Returns:
            True if topic matches pattern
        """
        pattern_parts = pattern.split("/")
        topic_parts = topic.split("/")

        i = 0
        for i, part in enumerate(pattern_parts):
            if part == "#":
                return True
            if i >= len(topic_parts):
                return False
            if part != "+" and part != topic_parts[i]:
                return False

        return i + 1 == len(topic_parts)

    async def _start_reconnect_loop(self) -> None:
        """Start automatic reconnection loop."""
        attempts = 0

        while self._running and attempts < self.config.max_reconnect_attempts:
            self.state = ConnectionState.RECONNECTING
            logger.info(f"Attempting reconnection ({attempts + 1}/{self.config.max_reconnect_attempts})")

            try:
                if await self.connect():
                    self.stats.reconnects += 1
                    logger.info("Reconnection successful")
                    return
            except Exception as e:
                logger.warning(f"Reconnection failed: {e}")

            attempts += 1
            await asyncio.sleep(self.config.reconnect_interval)

        self.state = ConnectionState.ERROR
        logger.error("Max reconnection attempts reached")

    async def start(self) -> bool:
        """
        Start the protocol handler.

        Returns:
            True if started successfully
        """
        self._running = True
        return await self.connect()

    async def stop(self) -> None:
        """Stop the protocol handler."""
        self._running = False
        if self._reconnect_task:
            self._reconnect_task.cancel()
            try:
                await self._reconnect_task
            except asyncio.CancelledError:
                pass
        await self.disconnect()

    def get_stats(self) -> dict[str, Any]:
        """Get handler statistics."""
        return {
            "protocol": self.protocol_type.value,
            "state": self.state.value,
            "client_id": self.config.client_id,
            "subscriptions": list(self._subscriptions.keys()),
            **self.stats.to_dict(),
        }

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} protocol={self.protocol_type.value} state={self.state.value}>"
