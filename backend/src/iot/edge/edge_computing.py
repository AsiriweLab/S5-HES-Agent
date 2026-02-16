"""
Edge Computing Simulators - Fog Nodes and IoT Gateways.

Sprint 11 - S11.10: Build FogNodeSimulator
Sprint 11 - S11.11: Implement GatewaySimulator

Features:
- Local data aggregation
- Edge analytics
- Protocol translation
- Caching and buffering
- Device management
- Advanced anomaly detection (statistical, rate-of-change, pattern-based)
- Comprehensive protocol translation rules
"""

import asyncio
import json
import math
from abc import ABC, abstractmethod
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Coroutine, Optional
from uuid import uuid4
from loguru import logger

from ..protocols.base_handler import (
    ProtocolMessage,
    ProtocolType,
    QoSLevel,
)


class EdgeNodeType(str, Enum):
    """Types of edge computing nodes."""
    FOG_NODE = "fog_node"
    GATEWAY = "gateway"
    EDGE_SERVER = "edge_server"


class AggregationType(str, Enum):
    """Data aggregation strategies."""
    NONE = "none"
    AVERAGE = "average"
    MIN = "min"
    MAX = "max"
    SUM = "sum"
    COUNT = "count"
    LAST = "last"
    FIRST = "first"


@dataclass
class EdgeConfig:
    """Edge node configuration."""
    node_id: str
    node_name: str = ""
    node_type: EdgeNodeType = EdgeNodeType.FOG_NODE
    # Aggregation settings
    aggregation_window: float = 60.0  # seconds
    aggregation_type: AggregationType = AggregationType.AVERAGE
    # Buffer settings
    buffer_size: int = 1000
    flush_interval: float = 30.0  # seconds
    # Processing settings
    filter_enabled: bool = True
    anomaly_detection: bool = True
    # Upstream settings
    upstream_url: str = ""
    upstream_batch_size: int = 100


@dataclass
class EdgeStats:
    """Statistics for edge node."""
    messages_received: int = 0
    messages_processed: int = 0
    messages_forwarded: int = 0
    messages_dropped: int = 0
    bytes_received: int = 0
    bytes_forwarded: int = 0
    anomalies_detected: int = 0
    aggregations_performed: int = 0
    uptime_seconds: float = 0.0
    start_time: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "messages_received": self.messages_received,
            "messages_processed": self.messages_processed,
            "messages_forwarded": self.messages_forwarded,
            "messages_dropped": self.messages_dropped,
            "bytes_received": self.bytes_received,
            "bytes_forwarded": self.bytes_forwarded,
            "anomalies_detected": self.anomalies_detected,
            "aggregations_performed": self.aggregations_performed,
            "uptime_seconds": (datetime.now() - self.start_time).total_seconds(),
        }


@dataclass
class DeviceRegistration:
    """Registered device information."""
    device_id: str
    device_type: str
    protocol: ProtocolType
    last_seen: datetime
    message_count: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)


# Type alias for message processors
MessageProcessor = Callable[[ProtocolMessage], Optional[ProtocolMessage]]


class AbstractEdgeNode(ABC):
    """
    Abstract base class for edge computing nodes.

    Provides:
    - Message buffering
    - Data aggregation
    - Protocol translation
    - Upstream forwarding
    """

    def __init__(self, config: EdgeConfig):
        """
        Initialize edge node.

        Args:
            config: Edge node configuration
        """
        self.config = config
        self.stats = EdgeStats()
        self._running = False

        # Message buffer
        self._buffer: list[ProtocolMessage] = []
        self._buffer_lock = asyncio.Lock()

        # Aggregation buckets: {device_id: {metric: [values]}}
        self._aggregation_buckets: dict[str, dict[str, list[float]]] = {}

        # Registered devices
        self._devices: dict[str, DeviceRegistration] = {}

        # Processing pipeline
        self._processors: list[MessageProcessor] = []

        # Upstream callback
        self._upstream_callback: Optional[Callable[[list[ProtocolMessage]], Coroutine[Any, Any, None]]] = None

        # Background tasks
        self._flush_task: Optional[asyncio.Task] = None
        self._aggregation_task: Optional[asyncio.Task] = None

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def device_count(self) -> int:
        return len(self._devices)

    @abstractmethod
    async def process_message(self, message: ProtocolMessage) -> Optional[ProtocolMessage]:
        """
        Process an incoming message.

        Args:
            message: Incoming message

        Returns:
            Processed message or None if filtered
        """
        pass

    async def start(self) -> None:
        """Start the edge node."""
        logger.info(f"Starting edge node: {self.config.node_id}")
        self._running = True
        self.stats.start_time = datetime.now()

        # Start background tasks
        self._flush_task = asyncio.create_task(self._flush_loop())
        self._aggregation_task = asyncio.create_task(self._aggregation_loop())

        logger.info(f"Edge node {self.config.node_id} started")

    async def stop(self) -> None:
        """Stop the edge node."""
        logger.info(f"Stopping edge node: {self.config.node_id}")
        self._running = False

        if self._flush_task:
            self._flush_task.cancel()
        if self._aggregation_task:
            self._aggregation_task.cancel()

        # Final flush
        await self._flush_buffer()

        logger.info(f"Edge node {self.config.node_id} stopped")

    async def receive(self, message: ProtocolMessage) -> bool:
        """
        Receive a message from a device.

        Args:
            message: Incoming message

        Returns:
            True if message was accepted
        """
        self.stats.messages_received += 1
        self.stats.bytes_received += len(str(message.payload))

        # Update device registration
        device_id = message.metadata.get("device_id", message.topic.split("/")[1] if "/" in message.topic else "unknown")
        self._update_device_registration(device_id, message)

        # Process message
        processed = await self.process_message(message)

        if processed:
            self.stats.messages_processed += 1

            # Add to buffer
            async with self._buffer_lock:
                if len(self._buffer) < self.config.buffer_size:
                    self._buffer.append(processed)
                else:
                    self.stats.messages_dropped += 1
                    logger.warning(f"Buffer full, dropping message from {device_id}")
                    return False

            # Add to aggregation buckets
            self._add_to_aggregation(device_id, processed)

            return True

        return False

    def _update_device_registration(self, device_id: str, message: ProtocolMessage) -> None:
        """Update device registration."""
        if device_id in self._devices:
            self._devices[device_id].last_seen = datetime.now()
            self._devices[device_id].message_count += 1
        else:
            self._devices[device_id] = DeviceRegistration(
                device_id=device_id,
                device_type=message.metadata.get("device_type", "unknown"),
                protocol=ProtocolType(message.metadata.get("protocol", "mqtt")),
                last_seen=datetime.now(),
                message_count=1,
                metadata=message.metadata,
            )
            logger.info(f"New device registered: {device_id}")

    def _add_to_aggregation(self, device_id: str, message: ProtocolMessage) -> None:
        """Add message to aggregation bucket."""
        if self.config.aggregation_type == AggregationType.NONE:
            return

        if device_id not in self._aggregation_buckets:
            self._aggregation_buckets[device_id] = {}

        payload = message.payload
        if isinstance(payload, dict):
            for key, value in payload.items():
                if isinstance(value, (int, float)):
                    if key not in self._aggregation_buckets[device_id]:
                        self._aggregation_buckets[device_id][key] = []
                    self._aggregation_buckets[device_id][key].append(float(value))

    def add_processor(self, processor: MessageProcessor) -> None:
        """Add a message processor to the pipeline."""
        self._processors.append(processor)

    def set_upstream_callback(
        self,
        callback: Callable[[list[ProtocolMessage]], Coroutine[Any, Any, None]],
    ) -> None:
        """Set callback for upstream forwarding."""
        self._upstream_callback = callback

    async def _flush_loop(self) -> None:
        """Periodically flush buffer to upstream."""
        while self._running:
            try:
                await asyncio.sleep(self.config.flush_interval)
                await self._flush_buffer()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Flush error: {e}")

    async def _flush_buffer(self) -> None:
        """Flush messages to upstream."""
        async with self._buffer_lock:
            if not self._buffer:
                return

            messages = self._buffer[:self.config.upstream_batch_size]
            self._buffer = self._buffer[self.config.upstream_batch_size:]

        if self._upstream_callback:
            try:
                await self._upstream_callback(messages)
                self.stats.messages_forwarded += len(messages)
                for msg in messages:
                    self.stats.bytes_forwarded += len(str(msg.payload))
                logger.debug(f"Forwarded {len(messages)} messages upstream")
            except Exception as e:
                logger.error(f"Upstream forwarding error: {e}")
                # Re-add messages to buffer
                async with self._buffer_lock:
                    self._buffer = messages + self._buffer
        else:
            # No upstream, just log
            logger.debug(f"No upstream configured, processed {len(messages)} messages locally")

    async def _aggregation_loop(self) -> None:
        """Periodically perform aggregation."""
        while self._running:
            try:
                await asyncio.sleep(self.config.aggregation_window)
                await self._perform_aggregation()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Aggregation error: {e}")

    async def _perform_aggregation(self) -> None:
        """Perform data aggregation."""
        if self.config.aggregation_type == AggregationType.NONE:
            return

        for device_id, metrics in self._aggregation_buckets.items():
            aggregated = {}

            for metric, values in metrics.items():
                if not values:
                    continue

                if self.config.aggregation_type == AggregationType.AVERAGE:
                    aggregated[metric] = sum(values) / len(values)
                elif self.config.aggregation_type == AggregationType.MIN:
                    aggregated[metric] = min(values)
                elif self.config.aggregation_type == AggregationType.MAX:
                    aggregated[metric] = max(values)
                elif self.config.aggregation_type == AggregationType.SUM:
                    aggregated[metric] = sum(values)
                elif self.config.aggregation_type == AggregationType.COUNT:
                    aggregated[metric] = len(values)
                elif self.config.aggregation_type == AggregationType.LAST:
                    aggregated[metric] = values[-1]
                elif self.config.aggregation_type == AggregationType.FIRST:
                    aggregated[metric] = values[0]

            if aggregated:
                self.stats.aggregations_performed += 1
                logger.debug(f"Aggregated data for {device_id}: {aggregated}")

        # Clear buckets
        self._aggregation_buckets.clear()

    def get_device_list(self) -> list[dict[str, Any]]:
        """Get list of registered devices."""
        return [
            {
                "device_id": d.device_id,
                "device_type": d.device_type,
                "protocol": d.protocol.value,
                "last_seen": d.last_seen.isoformat(),
                "message_count": d.message_count,
            }
            for d in self._devices.values()
        ]

    def get_stats(self) -> dict[str, Any]:
        """Get edge node statistics."""
        return {
            "node_id": self.config.node_id,
            "node_type": self.config.node_type.value,
            "is_running": self._running,
            "device_count": self.device_count,
            "buffer_size": len(self._buffer),
            "buffer_capacity": self.config.buffer_size,
            **self.stats.to_dict(),
        }


class FogNodeSimulator(AbstractEdgeNode):
    """
    Fog Node Simulator for edge computing.

    Features:
    - Data aggregation and filtering
    - Local analytics
    - Multi-protocol support
    - Cloud gateway functionality
    """

    def __init__(self, config: EdgeConfig):
        """
        Initialize fog node.

        Args:
            config: Fog node configuration
        """
        config.node_type = EdgeNodeType.FOG_NODE
        super().__init__(config)

        # Local storage for processed data
        self._local_cache: dict[str, Any] = {}

        # Anomaly detection thresholds
        self._anomaly_thresholds: dict[str, tuple[float, float]] = {}

    async def process_message(self, message: ProtocolMessage) -> Optional[ProtocolMessage]:
        """
        Process message through fog node pipeline.

        Args:
            message: Incoming message

        Returns:
            Processed message or None
        """
        # Run through processors
        processed = message
        for processor in self._processors:
            result = processor(processed)
            if result is None:
                return None  # Filtered out
            processed = result

        # Anomaly detection
        if self.config.anomaly_detection:
            if self._detect_anomaly(processed):
                self.stats.anomalies_detected += 1
                processed.metadata["anomaly_detected"] = True

        # Cache locally
        device_id = processed.metadata.get("device_id", "unknown")
        self._local_cache[device_id] = {
            "last_value": processed.payload,
            "timestamp": datetime.now().isoformat(),
        }

        return processed

    def _detect_anomaly(self, message: ProtocolMessage) -> bool:
        """Simple anomaly detection based on thresholds."""
        payload = message.payload
        if not isinstance(payload, dict):
            return False

        for key, value in payload.items():
            if isinstance(value, (int, float)) and key in self._anomaly_thresholds:
                min_val, max_val = self._anomaly_thresholds[key]
                if value < min_val or value > max_val:
                    logger.warning(f"Anomaly detected: {key}={value} out of range [{min_val}, {max_val}]")
                    return True

        return False

    def set_anomaly_threshold(self, metric: str, min_val: float, max_val: float) -> None:
        """Set anomaly detection threshold for a metric."""
        self._anomaly_thresholds[metric] = (min_val, max_val)

    def get_local_cache(self) -> dict[str, Any]:
        """Get local cache contents."""
        return dict(self._local_cache)


class GatewaySimulator(AbstractEdgeNode):
    """
    IoT Gateway Simulator.

    Features:
    - Protocol translation (Zigbee, Z-Wave, BLE → MQTT/HTTP)
    - Device management
    - Local rule execution
    - Buffering for offline operation
    """

    def __init__(self, config: EdgeConfig):
        """
        Initialize gateway.

        Args:
            config: Gateway configuration
        """
        config.node_type = EdgeNodeType.GATEWAY
        super().__init__(config)

        # Protocol handlers
        self._protocol_handlers: dict[ProtocolType, Any] = {}

        # Device groups
        self._device_groups: dict[str, list[str]] = {}

        # Local rules: {rule_id: rule_function}
        self._rules: dict[str, Callable[[ProtocolMessage], Optional[ProtocolMessage]]] = {}

        # Offline buffer
        self._offline_buffer: list[ProtocolMessage] = []
        self._is_online = True

    async def process_message(self, message: ProtocolMessage) -> Optional[ProtocolMessage]:
        """
        Process message through gateway.

        Args:
            message: Incoming message

        Returns:
            Processed/translated message
        """
        # Protocol translation
        source_protocol = ProtocolType(message.metadata.get("protocol", "mqtt"))
        translated = self._translate_protocol(message, source_protocol)

        # Run through processors
        for processor in self._processors:
            result = processor(translated)
            if result is None:
                return None
            translated = result

        # Execute local rules
        for rule_id, rule_func in self._rules.items():
            try:
                result = rule_func(translated)
                if result is None:
                    logger.debug(f"Rule {rule_id} filtered message")
                    return None
                translated = result
            except Exception as e:
                logger.error(f"Rule {rule_id} error: {e}")

        # Handle offline mode
        if not self._is_online:
            self._offline_buffer.append(translated)
            logger.debug("Gateway offline, message buffered")
            return None

        return translated

    def _translate_protocol(
        self,
        message: ProtocolMessage,
        source_protocol: ProtocolType,
    ) -> ProtocolMessage:
        """Translate message between protocols."""
        # Add translation metadata
        translated = ProtocolMessage(
            id=message.id,
            topic=self._translate_topic(message.topic, source_protocol),
            payload=message.payload,
            timestamp=message.timestamp,
            qos=message.qos,
            metadata={
                **message.metadata,
                "original_protocol": source_protocol.value,
                "translated_by": self.config.node_id,
            },
        )
        return translated

    def _translate_topic(self, topic: str, source_protocol: ProtocolType) -> str:
        """Translate topic format between protocols."""
        # Normalize to MQTT-style topics
        if source_protocol in (ProtocolType.ZIGBEE, ProtocolType.ZWAVE, ProtocolType.BLE):
            # Convert local device topics to cloud-friendly format
            return f"gateway/{self.config.node_id}/{topic}"
        return topic

    def register_protocol_handler(self, protocol: ProtocolType, handler: Any) -> None:
        """Register a protocol handler."""
        self._protocol_handlers[protocol] = handler
        logger.info(f"Registered protocol handler for {protocol.value}")

    def add_rule(
        self,
        rule_id: str,
        rule_func: Callable[[ProtocolMessage], Optional[ProtocolMessage]],
    ) -> None:
        """Add a local rule."""
        self._rules[rule_id] = rule_func
        logger.info(f"Added rule: {rule_id}")

    def remove_rule(self, rule_id: str) -> None:
        """Remove a local rule."""
        if rule_id in self._rules:
            del self._rules[rule_id]

    def create_device_group(self, group_name: str, device_ids: list[str]) -> None:
        """Create a device group."""
        self._device_groups[group_name] = device_ids

    def set_online(self, online: bool) -> None:
        """Set gateway online/offline status."""
        was_offline = not self._is_online
        self._is_online = online

        if online and was_offline:
            # Flush offline buffer
            asyncio.create_task(self._flush_offline_buffer())

    async def _flush_offline_buffer(self) -> None:
        """Flush offline buffer when coming back online."""
        logger.info(f"Flushing {len(self._offline_buffer)} offline messages")

        async with self._buffer_lock:
            self._buffer.extend(self._offline_buffer)
            self._offline_buffer.clear()

    def get_stats(self) -> dict[str, Any]:
        """Get gateway statistics."""
        stats = super().get_stats()
        stats.update({
            "is_online": self._is_online,
            "offline_buffer_size": len(self._offline_buffer),
            "protocol_handlers": list(self._protocol_handlers.keys()),
            "device_groups": list(self._device_groups.keys()),
            "rules_count": len(self._rules),
        })
        return stats


# =============================================================================
# Edge Computing Manager
# =============================================================================

class EdgeComputingManager:
    """
    Manager for edge computing infrastructure.

    Coordinates fog nodes and gateways in the simulation.
    """

    def __init__(self):
        """Initialize edge computing manager."""
        self._fog_nodes: dict[str, FogNodeSimulator] = {}
        self._gateways: dict[str, GatewaySimulator] = {}

    async def create_fog_node(self, config: EdgeConfig) -> FogNodeSimulator:
        """Create and start a fog node."""
        node = FogNodeSimulator(config)
        await node.start()
        self._fog_nodes[config.node_id] = node
        return node

    async def create_gateway(self, config: EdgeConfig) -> GatewaySimulator:
        """Create and start a gateway."""
        gateway = GatewaySimulator(config)
        await gateway.start()
        self._gateways[config.node_id] = gateway
        return gateway

    async def stop_all(self) -> None:
        """Stop all edge nodes."""
        for node in self._fog_nodes.values():
            await node.stop()
        for gateway in self._gateways.values():
            await gateway.stop()

    def get_fog_node(self, node_id: str) -> Optional[FogNodeSimulator]:
        """Get a fog node by ID."""
        return self._fog_nodes.get(node_id)

    def get_gateway(self, gateway_id: str) -> Optional[GatewaySimulator]:
        """Get a gateway by ID."""
        return self._gateways.get(gateway_id)

    def get_all_stats(self) -> dict[str, Any]:
        """Get statistics for all edge nodes."""
        return {
            "fog_nodes": {
                node_id: node.get_stats()
                for node_id, node in self._fog_nodes.items()
            },
            "gateways": {
                gw_id: gw.get_stats()
                for gw_id, gw in self._gateways.items()
            },
        }


# =============================================================================
# Enhanced Anomaly Detection (Task #11)
# =============================================================================

class AnomalyType(str, Enum):
    """Types of anomalies that can be detected."""
    THRESHOLD = "threshold"           # Value outside static bounds
    RATE_OF_CHANGE = "rate_of_change" # Rapid change in value
    STATISTICAL = "statistical"        # Z-score based outlier
    PATTERN = "pattern"               # Pattern deviation
    FREQUENCY = "frequency"           # Message frequency anomaly
    MISSING = "missing"               # Missing expected data


@dataclass
class AnomalyDetection:
    """Result of anomaly detection."""
    is_anomaly: bool
    anomaly_type: Optional[AnomalyType] = None
    metric: str = ""
    value: float = 0.0
    expected_range: Optional[tuple[float, float]] = None
    confidence: float = 0.0
    message: str = ""
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "is_anomaly": self.is_anomaly,
            "anomaly_type": self.anomaly_type.value if self.anomaly_type else None,
            "metric": self.metric,
            "value": self.value,
            "expected_range": self.expected_range,
            "confidence": self.confidence,
            "message": self.message,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class MetricHistory:
    """Historical data for a metric (used for statistical analysis)."""
    values: deque = field(default_factory=lambda: deque(maxlen=100))
    timestamps: deque = field(default_factory=lambda: deque(maxlen=100))
    mean: float = 0.0
    std_dev: float = 0.0
    last_value: Optional[float] = None
    last_timestamp: Optional[datetime] = None

    def add(self, value: float, timestamp: datetime) -> None:
        """Add a value to history and update statistics."""
        self.values.append(value)
        self.timestamps.append(timestamp)
        self.last_value = value
        self.last_timestamp = timestamp

        # Update statistics
        if len(self.values) >= 2:
            values_list = list(self.values)
            self.mean = sum(values_list) / len(values_list)
            variance = sum((x - self.mean) ** 2 for x in values_list) / len(values_list)
            self.std_dev = math.sqrt(variance)


class AdvancedAnomalyDetector:
    """
    Advanced Anomaly Detection Engine for FogNode.

    Implements multiple detection strategies:
    - Threshold-based: Static min/max bounds
    - Rate-of-change: Detects rapid value changes
    - Statistical (Z-score): Detects outliers based on historical data
    - Pattern-based: Detects deviation from expected patterns
    - Frequency-based: Detects unusual message frequencies
    """

    def __init__(
        self,
        z_score_threshold: float = 3.0,
        rate_of_change_threshold: float = 0.5,
        min_history_size: int = 10,
        message_frequency_window: float = 60.0,
    ):
        """
        Initialize anomaly detector.

        Args:
            z_score_threshold: Number of std deviations for statistical anomaly
            rate_of_change_threshold: Max allowed rate of change per second
            min_history_size: Minimum samples before statistical detection
            message_frequency_window: Window size for frequency analysis (seconds)
        """
        self.z_score_threshold = z_score_threshold
        self.rate_of_change_threshold = rate_of_change_threshold
        self.min_history_size = min_history_size
        self.message_frequency_window = message_frequency_window

        # Metric histories: {device_id: {metric: MetricHistory}}
        self._histories: dict[str, dict[str, MetricHistory]] = {}

        # Static thresholds: {metric: (min, max)}
        self._thresholds: dict[str, tuple[float, float]] = {}

        # Expected patterns: {device_id: {hour: expected_value}}
        self._patterns: dict[str, dict[int, float]] = {}

        # Message frequency tracking: {device_id: [timestamps]}
        self._message_times: dict[str, deque] = {}

        # Detection stats
        self.stats = {
            "threshold_anomalies": 0,
            "rate_of_change_anomalies": 0,
            "statistical_anomalies": 0,
            "pattern_anomalies": 0,
            "frequency_anomalies": 0,
            "total_checks": 0,
        }

    def set_threshold(self, metric: str, min_val: float, max_val: float) -> None:
        """Set static threshold for a metric."""
        self._thresholds[metric] = (min_val, max_val)

    def set_pattern(self, device_id: str, hourly_pattern: dict[int, float]) -> None:
        """
        Set expected hourly pattern for a device.

        Args:
            device_id: Device identifier
            hourly_pattern: {hour (0-23): expected_value}
        """
        self._patterns[device_id] = hourly_pattern

    def detect(
        self,
        device_id: str,
        metric: str,
        value: float,
        timestamp: Optional[datetime] = None,
    ) -> AnomalyDetection:
        """
        Run all anomaly detection methods on a value.

        Args:
            device_id: Device identifier
            metric: Metric name
            value: Value to check
            timestamp: Timestamp (defaults to now)

        Returns:
            AnomalyDetection result
        """
        timestamp = timestamp or datetime.now()
        self.stats["total_checks"] += 1

        # Initialize histories if needed
        if device_id not in self._histories:
            self._histories[device_id] = {}
        if metric not in self._histories[device_id]:
            self._histories[device_id][metric] = MetricHistory()

        history = self._histories[device_id][metric]

        # Track message frequency
        if device_id not in self._message_times:
            self._message_times[device_id] = deque(maxlen=1000)
        self._message_times[device_id].append(timestamp)

        # Run detection methods
        results = []

        # 1. Threshold check
        if metric in self._thresholds:
            result = self._check_threshold(metric, value)
            if result.is_anomaly:
                results.append(result)

        # 2. Rate of change check
        if history.last_value is not None and history.last_timestamp is not None:
            result = self._check_rate_of_change(metric, value, timestamp, history)
            if result.is_anomaly:
                results.append(result)

        # 3. Statistical check (Z-score)
        if len(history.values) >= self.min_history_size:
            result = self._check_statistical(metric, value, history)
            if result.is_anomaly:
                results.append(result)

        # 4. Pattern check
        if device_id in self._patterns:
            result = self._check_pattern(device_id, metric, value, timestamp)
            if result.is_anomaly:
                results.append(result)

        # 5. Frequency check
        result = self._check_frequency(device_id, timestamp)
        if result.is_anomaly:
            results.append(result)

        # Update history
        history.add(value, timestamp)

        # Return most severe anomaly or no anomaly
        if results:
            # Sort by confidence (highest first)
            results.sort(key=lambda x: x.confidence, reverse=True)
            return results[0]

        return AnomalyDetection(is_anomaly=False)

    def _check_threshold(self, metric: str, value: float) -> AnomalyDetection:
        """Check value against static thresholds."""
        min_val, max_val = self._thresholds[metric]

        if value < min_val or value > max_val:
            self.stats["threshold_anomalies"] += 1
            return AnomalyDetection(
                is_anomaly=True,
                anomaly_type=AnomalyType.THRESHOLD,
                metric=metric,
                value=value,
                expected_range=(min_val, max_val),
                confidence=1.0,
                message=f"{metric}={value} outside range [{min_val}, {max_val}]",
            )

        return AnomalyDetection(is_anomaly=False)

    def _check_rate_of_change(
        self,
        metric: str,
        value: float,
        timestamp: datetime,
        history: MetricHistory,
    ) -> AnomalyDetection:
        """Check for rapid rate of change."""
        time_delta = (timestamp - history.last_timestamp).total_seconds()
        if time_delta <= 0:
            return AnomalyDetection(is_anomaly=False)

        rate = abs(value - history.last_value) / time_delta

        # Normalize rate by expected value range
        if history.std_dev > 0:
            normalized_rate = rate / history.std_dev
        else:
            normalized_rate = rate

        if normalized_rate > self.rate_of_change_threshold:
            self.stats["rate_of_change_anomalies"] += 1
            confidence = min(normalized_rate / self.rate_of_change_threshold, 1.0)
            return AnomalyDetection(
                is_anomaly=True,
                anomaly_type=AnomalyType.RATE_OF_CHANGE,
                metric=metric,
                value=value,
                confidence=confidence,
                message=f"{metric} changed from {history.last_value:.2f} to {value:.2f} ({rate:.2f}/sec)",
            )

        return AnomalyDetection(is_anomaly=False)

    def _check_statistical(
        self,
        metric: str,
        value: float,
        history: MetricHistory,
    ) -> AnomalyDetection:
        """Check for statistical outlier using Z-score."""
        if history.std_dev == 0:
            return AnomalyDetection(is_anomaly=False)

        z_score = abs(value - history.mean) / history.std_dev

        if z_score > self.z_score_threshold:
            self.stats["statistical_anomalies"] += 1
            confidence = min(z_score / (self.z_score_threshold * 2), 1.0)
            expected_range = (
                history.mean - self.z_score_threshold * history.std_dev,
                history.mean + self.z_score_threshold * history.std_dev,
            )
            return AnomalyDetection(
                is_anomaly=True,
                anomaly_type=AnomalyType.STATISTICAL,
                metric=metric,
                value=value,
                expected_range=expected_range,
                confidence=confidence,
                message=f"{metric}={value:.2f} is {z_score:.1f} std devs from mean {history.mean:.2f}",
            )

        return AnomalyDetection(is_anomaly=False)

    def _check_pattern(
        self,
        device_id: str,
        metric: str,
        value: float,
        timestamp: datetime,
    ) -> AnomalyDetection:
        """Check for deviation from expected hourly pattern."""
        hour = timestamp.hour
        if hour not in self._patterns[device_id]:
            return AnomalyDetection(is_anomaly=False)

        expected = self._patterns[device_id][hour]
        deviation = abs(value - expected) / (expected if expected != 0 else 1)

        # Flag if more than 50% deviation from expected
        if deviation > 0.5:
            self.stats["pattern_anomalies"] += 1
            return AnomalyDetection(
                is_anomaly=True,
                anomaly_type=AnomalyType.PATTERN,
                metric=metric,
                value=value,
                expected_range=(expected * 0.5, expected * 1.5),
                confidence=min(deviation, 1.0),
                message=f"{metric}={value:.2f} deviates {deviation*100:.0f}% from expected {expected:.2f} at hour {hour}",
            )

        return AnomalyDetection(is_anomaly=False)

    def _check_frequency(
        self,
        device_id: str,
        timestamp: datetime,
    ) -> AnomalyDetection:
        """Check for unusual message frequency."""
        if device_id not in self._message_times:
            return AnomalyDetection(is_anomaly=False)

        times = self._message_times[device_id]
        if len(times) < 10:
            return AnomalyDetection(is_anomaly=False)

        # Count messages in recent window
        cutoff = timestamp - timedelta(seconds=self.message_frequency_window)
        recent_count = sum(1 for t in times if t > cutoff)

        # Calculate expected rate from history
        oldest = min(times)
        total_span = (timestamp - oldest).total_seconds()
        if total_span <= 0:
            return AnomalyDetection(is_anomaly=False)

        expected_rate = len(times) / total_span * self.message_frequency_window
        actual_rate = recent_count

        # Flag if more than 3x expected rate
        if actual_rate > expected_rate * 3:
            self.stats["frequency_anomalies"] += 1
            return AnomalyDetection(
                is_anomaly=True,
                anomaly_type=AnomalyType.FREQUENCY,
                metric="message_rate",
                value=actual_rate,
                expected_range=(0, expected_rate * 2),
                confidence=min((actual_rate / expected_rate) / 3, 1.0),
                message=f"Device {device_id} sent {actual_rate} messages in {self.message_frequency_window}s (expected ~{expected_rate:.0f})",
            )

        return AnomalyDetection(is_anomaly=False)

    def get_stats(self) -> dict[str, Any]:
        """Get detection statistics."""
        return dict(self.stats)


# =============================================================================
# Enhanced Protocol Translation (Task #12)
# =============================================================================

class ProtocolTranslationRule:
    """Rule for translating between protocols."""

    def __init__(
        self,
        source_protocol: ProtocolType,
        target_protocol: ProtocolType,
        topic_mapping: Optional[Callable[[str], str]] = None,
        payload_transformer: Optional[Callable[[Any], Any]] = None,
        metadata_enricher: Optional[Callable[[dict], dict]] = None,
    ):
        """
        Initialize translation rule.

        Args:
            source_protocol: Source protocol type
            target_protocol: Target protocol type
            topic_mapping: Function to transform topic
            payload_transformer: Function to transform payload
            metadata_enricher: Function to add metadata
        """
        self.source_protocol = source_protocol
        self.target_protocol = target_protocol
        self.topic_mapping = topic_mapping or (lambda t: t)
        self.payload_transformer = payload_transformer or (lambda p: p)
        self.metadata_enricher = metadata_enricher or (lambda m: m)

    def apply(self, message: ProtocolMessage) -> ProtocolMessage:
        """Apply the translation rule to a message."""
        return ProtocolMessage(
            id=message.id,
            topic=self.topic_mapping(message.topic),
            payload=self.payload_transformer(message.payload),
            timestamp=message.timestamp,
            qos=message.qos,
            metadata=self.metadata_enricher({
                **message.metadata,
                "original_protocol": self.source_protocol.value,
                "target_protocol": self.target_protocol.value,
            }),
        )


class AdvancedProtocolTranslator:
    """
    Advanced Protocol Translation Engine for Gateway.

    Provides comprehensive translation between IoT protocols:
    - Zigbee ↔ MQTT/HTTP
    - Z-Wave ↔ MQTT/HTTP
    - BLE ↔ MQTT/HTTP
    - CoAP ↔ HTTP
    - Thread ↔ MQTT

    Features:
    - Configurable topic mapping
    - Payload transformation
    - Metadata enrichment
    - QoS mapping
    - Protocol-specific handling
    """

    def __init__(self, gateway_id: str):
        """
        Initialize protocol translator.

        Args:
            gateway_id: Gateway identifier for namespacing
        """
        self.gateway_id = gateway_id
        self._rules: dict[tuple[ProtocolType, ProtocolType], ProtocolTranslationRule] = {}
        self._default_target = ProtocolType.MQTT
        self._stats = {
            "translations": 0,
            "by_source": {},
            "by_target": {},
        }

        # Initialize default rules
        self._initialize_default_rules()

    def _initialize_default_rules(self) -> None:
        """Set up default translation rules."""
        # Zigbee to MQTT
        self.add_rule(ProtocolTranslationRule(
            source_protocol=ProtocolType.ZIGBEE,
            target_protocol=ProtocolType.MQTT,
            topic_mapping=lambda t: f"zigbee/{self.gateway_id}/{t}",
            payload_transformer=self._zigbee_to_mqtt_payload,
            metadata_enricher=lambda m: {
                **m,
                "mesh_network": "zigbee",
                "gateway_id": self.gateway_id,
            },
        ))

        # Z-Wave to MQTT
        self.add_rule(ProtocolTranslationRule(
            source_protocol=ProtocolType.ZWAVE,
            target_protocol=ProtocolType.MQTT,
            topic_mapping=lambda t: f"zwave/{self.gateway_id}/{t}",
            payload_transformer=self._zwave_to_mqtt_payload,
            metadata_enricher=lambda m: {
                **m,
                "mesh_network": "zwave",
                "gateway_id": self.gateway_id,
            },
        ))

        # BLE to MQTT
        self.add_rule(ProtocolTranslationRule(
            source_protocol=ProtocolType.BLE,
            target_protocol=ProtocolType.MQTT,
            topic_mapping=lambda t: f"ble/{self.gateway_id}/{t}",
            payload_transformer=self._ble_to_mqtt_payload,
            metadata_enricher=lambda m: {
                **m,
                "connection_type": "bluetooth",
                "gateway_id": self.gateway_id,
            },
        ))

        # CoAP to HTTP
        self.add_rule(ProtocolTranslationRule(
            source_protocol=ProtocolType.COAP,
            target_protocol=ProtocolType.HTTP,
            topic_mapping=lambda t: f"/api/coap/{self.gateway_id}/{t.replace('/', '_')}",
            payload_transformer=self._coap_to_http_payload,
            metadata_enricher=lambda m: {
                **m,
                "content_type": "application/json",
                "gateway_id": self.gateway_id,
            },
        ))

        # Zigbee to HTTP
        self.add_rule(ProtocolTranslationRule(
            source_protocol=ProtocolType.ZIGBEE,
            target_protocol=ProtocolType.HTTP,
            topic_mapping=lambda t: f"/api/zigbee/{self.gateway_id}/{t.replace('/', '_')}",
            payload_transformer=self._zigbee_to_http_payload,
        ))

        # Z-Wave to HTTP
        self.add_rule(ProtocolTranslationRule(
            source_protocol=ProtocolType.ZWAVE,
            target_protocol=ProtocolType.HTTP,
            topic_mapping=lambda t: f"/api/zwave/{self.gateway_id}/{t.replace('/', '_')}",
            payload_transformer=self._zwave_to_http_payload,
        ))

        # MQTT to HTTP (webhook-style)
        self.add_rule(ProtocolTranslationRule(
            source_protocol=ProtocolType.MQTT,
            target_protocol=ProtocolType.HTTP,
            topic_mapping=lambda t: f"/api/mqtt/{self.gateway_id}/{t.replace('/', '_')}",
            payload_transformer=lambda p: {"event": "mqtt_message", "payload": p},
        ))

        # WebSocket to MQTT
        self.add_rule(ProtocolTranslationRule(
            source_protocol=ProtocolType.WEBSOCKET,
            target_protocol=ProtocolType.MQTT,
            topic_mapping=lambda t: f"ws/{self.gateway_id}/{t}",
        ))

    def add_rule(self, rule: ProtocolTranslationRule) -> None:
        """Add a translation rule."""
        key = (rule.source_protocol, rule.target_protocol)
        self._rules[key] = rule

    def translate(
        self,
        message: ProtocolMessage,
        source_protocol: ProtocolType,
        target_protocol: Optional[ProtocolType] = None,
    ) -> ProtocolMessage:
        """
        Translate a message between protocols.

        Args:
            message: Message to translate
            source_protocol: Source protocol
            target_protocol: Target protocol (defaults to MQTT)

        Returns:
            Translated message
        """
        target = target_protocol or self._default_target
        key = (source_protocol, target)

        self._stats["translations"] += 1
        source_name = source_protocol.value
        target_name = target.value
        self._stats["by_source"][source_name] = self._stats["by_source"].get(source_name, 0) + 1
        self._stats["by_target"][target_name] = self._stats["by_target"].get(target_name, 0) + 1

        if key in self._rules:
            return self._rules[key].apply(message)

        # Fallback: basic translation
        return ProtocolMessage(
            id=message.id,
            topic=f"{source_protocol.value}/{self.gateway_id}/{message.topic}",
            payload=message.payload,
            timestamp=message.timestamp,
            qos=message.qos,
            metadata={
                **message.metadata,
                "original_protocol": source_protocol.value,
                "target_protocol": target.value,
                "gateway_id": self.gateway_id,
            },
        )

    def _zigbee_to_mqtt_payload(self, payload: Any) -> dict[str, Any]:
        """Transform Zigbee payload to MQTT-friendly format."""
        if isinstance(payload, dict):
            return {
                "data": payload,
                "protocol": "zigbee",
                "format": "json",
            }
        elif isinstance(payload, bytes):
            return {
                "data": payload.hex(),
                "protocol": "zigbee",
                "format": "hex",
            }
        return {"data": payload, "protocol": "zigbee"}

    def _zwave_to_mqtt_payload(self, payload: Any) -> dict[str, Any]:
        """Transform Z-Wave payload to MQTT-friendly format."""
        if isinstance(payload, dict):
            # Z-Wave specific field normalization
            normalized = {}
            for key, value in payload.items():
                # Convert Z-Wave command class names to readable format
                if key.startswith("COMMAND_CLASS_"):
                    normalized_key = key.replace("COMMAND_CLASS_", "").lower()
                else:
                    normalized_key = key.lower().replace(" ", "_")
                normalized[normalized_key] = value
            return {
                "data": normalized,
                "protocol": "zwave",
                "format": "json",
            }
        return {"data": payload, "protocol": "zwave"}

    def _ble_to_mqtt_payload(self, payload: Any) -> dict[str, Any]:
        """Transform BLE payload to MQTT-friendly format."""
        if isinstance(payload, dict):
            # BLE GATT characteristic handling
            result = {"protocol": "ble", "format": "json"}
            if "characteristic" in payload:
                result["characteristic_uuid"] = payload.get("characteristic")
            if "value" in payload:
                value = payload["value"]
                if isinstance(value, bytes):
                    result["data"] = value.hex()
                    result["format"] = "hex"
                else:
                    result["data"] = value
            else:
                result["data"] = payload
            return result
        elif isinstance(payload, bytes):
            return {
                "data": payload.hex(),
                "protocol": "ble",
                "format": "hex",
            }
        return {"data": payload, "protocol": "ble"}

    def _coap_to_http_payload(self, payload: Any) -> dict[str, Any]:
        """Transform CoAP payload to HTTP-friendly format."""
        if isinstance(payload, dict):
            return {
                "body": payload,
                "content_type": "application/json",
                "protocol_version": "coap/1.0",
            }
        elif isinstance(payload, bytes):
            try:
                # Try to parse as JSON
                return {
                    "body": json.loads(payload.decode()),
                    "content_type": "application/json",
                    "protocol_version": "coap/1.0",
                }
            except (json.JSONDecodeError, UnicodeDecodeError):
                return {
                    "body": payload.hex(),
                    "content_type": "application/octet-stream",
                    "protocol_version": "coap/1.0",
                }
        return {"body": payload, "content_type": "text/plain"}

    def _zigbee_to_http_payload(self, payload: Any) -> dict[str, Any]:
        """Transform Zigbee payload to HTTP-friendly format."""
        result = self._zigbee_to_mqtt_payload(payload)
        return {
            "event_type": "zigbee_message",
            "timestamp": datetime.now().isoformat(),
            **result,
        }

    def _zwave_to_http_payload(self, payload: Any) -> dict[str, Any]:
        """Transform Z-Wave payload to HTTP-friendly format."""
        result = self._zwave_to_mqtt_payload(payload)
        return {
            "event_type": "zwave_message",
            "timestamp": datetime.now().isoformat(),
            **result,
        }

    def get_supported_translations(self) -> list[tuple[str, str]]:
        """Get list of supported source → target translations."""
        return [(k[0].value, k[1].value) for k in self._rules.keys()]

    def get_stats(self) -> dict[str, Any]:
        """Get translation statistics."""
        return dict(self._stats)

    def set_default_target(self, protocol: ProtocolType) -> None:
        """Set the default target protocol."""
        self._default_target = protocol


# =============================================================================
# Enhanced FogNode with Advanced Anomaly Detection
# =============================================================================

class EnhancedFogNodeSimulator(FogNodeSimulator):
    """
    Enhanced Fog Node with advanced anomaly detection capabilities.

    Extends FogNodeSimulator with:
    - Statistical anomaly detection (Z-score)
    - Rate of change monitoring
    - Pattern-based detection
    - Message frequency analysis
    """

    def __init__(self, config: EdgeConfig):
        """Initialize enhanced fog node."""
        super().__init__(config)
        self._anomaly_detector = AdvancedAnomalyDetector()
        self._recent_anomalies: deque = deque(maxlen=100)

    async def process_message(self, message: ProtocolMessage) -> Optional[ProtocolMessage]:
        """Process message with enhanced anomaly detection."""
        # Run through processors
        processed = message
        for processor in self._processors:
            result = processor(processed)
            if result is None:
                return None
            processed = result

        # Enhanced anomaly detection
        if self.config.anomaly_detection:
            device_id = processed.metadata.get("device_id", "unknown")
            payload = processed.payload

            if isinstance(payload, dict):
                for metric, value in payload.items():
                    if isinstance(value, (int, float)):
                        detection = self._anomaly_detector.detect(
                            device_id, metric, float(value)
                        )
                        if detection.is_anomaly:
                            self.stats.anomalies_detected += 1
                            processed.metadata["anomaly_detected"] = True
                            processed.metadata["anomaly_details"] = detection.to_dict()
                            self._recent_anomalies.append(detection)
                            logger.warning(
                                f"Anomaly detected: {detection.message}"
                            )

        # Cache locally
        device_id = processed.metadata.get("device_id", "unknown")
        self._local_cache[device_id] = {
            "last_value": processed.payload,
            "timestamp": datetime.now().isoformat(),
        }

        return processed

    def configure_anomaly_detection(
        self,
        z_score_threshold: float = 3.0,
        rate_of_change_threshold: float = 0.5,
    ) -> None:
        """Configure anomaly detection parameters."""
        self._anomaly_detector.z_score_threshold = z_score_threshold
        self._anomaly_detector.rate_of_change_threshold = rate_of_change_threshold

    def set_metric_threshold(self, metric: str, min_val: float, max_val: float) -> None:
        """Set static threshold for a metric."""
        self._anomaly_detector.set_threshold(metric, min_val, max_val)

    def set_device_pattern(self, device_id: str, hourly_pattern: dict[int, float]) -> None:
        """Set expected hourly pattern for a device."""
        self._anomaly_detector.set_pattern(device_id, hourly_pattern)

    def get_recent_anomalies(self) -> list[dict[str, Any]]:
        """Get recent anomaly detections."""
        return [a.to_dict() for a in self._recent_anomalies]

    def get_anomaly_stats(self) -> dict[str, Any]:
        """Get anomaly detection statistics."""
        return self._anomaly_detector.get_stats()


# =============================================================================
# Enhanced Gateway with Advanced Protocol Translation
# =============================================================================

class EnhancedGatewaySimulator(GatewaySimulator):
    """
    Enhanced Gateway with comprehensive protocol translation.

    Extends GatewaySimulator with:
    - Advanced protocol translation rules
    - Payload transformation
    - Topic mapping
    - Protocol-specific handling
    """

    def __init__(self, config: EdgeConfig):
        """Initialize enhanced gateway."""
        super().__init__(config)
        self._translator = AdvancedProtocolTranslator(config.node_id)

    async def process_message(self, message: ProtocolMessage) -> Optional[ProtocolMessage]:
        """Process message with enhanced protocol translation."""
        source_protocol = ProtocolType(message.metadata.get("protocol", "mqtt"))

        # Use advanced translator
        translated = self._translator.translate(
            message, source_protocol
        )

        # Run through processors
        for processor in self._processors:
            result = processor(translated)
            if result is None:
                return None
            translated = result

        # Execute local rules
        for rule_id, rule_func in self._rules.items():
            try:
                result = rule_func(translated)
                if result is None:
                    return None
                translated = result
            except Exception as e:
                logger.error(f"Rule {rule_id} error: {e}")

        # Handle offline mode
        if not self._is_online:
            self._offline_buffer.append(translated)
            return None

        return translated

    def add_translation_rule(self, rule: ProtocolTranslationRule) -> None:
        """Add a custom translation rule."""
        self._translator.add_rule(rule)

    def set_default_target_protocol(self, protocol: ProtocolType) -> None:
        """Set the default target protocol for translations."""
        self._translator.set_default_target(protocol)

    def get_supported_translations(self) -> list[tuple[str, str]]:
        """Get list of supported protocol translations."""
        return self._translator.get_supported_translations()

    def get_translation_stats(self) -> dict[str, Any]:
        """Get protocol translation statistics."""
        return self._translator.get_stats()

    def get_stats(self) -> dict[str, Any]:
        """Get gateway statistics including translation stats."""
        stats = super().get_stats()
        stats["translation_stats"] = self.get_translation_stats()
        return stats
