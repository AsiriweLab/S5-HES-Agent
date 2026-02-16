"""
MQTT Protocol Handler - Implementation for MQTT messaging.

Sprint 11 - S11.2: Implement MQTTHandler
Sprint 11 - S11.3: Add MQTT QoS levels (0, 1, 2)

Features:
- Full QoS 0, 1, 2 support
- Retain messages
- Last Will and Testament (LWT)
- Automatic reconnection
- Topic wildcards (+ and #)
"""

import asyncio
import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional
from loguru import logger

from .base_handler import (
    AbstractProtocolHandler,
    ProtocolType,
    ProtocolConfig,
    ProtocolMessage,
    ConnectionState,
    QoSLevel,
    MessageCallback,
    AsyncMessageCallback,
)


@dataclass
class MQTTConfig(ProtocolConfig):
    """MQTT-specific configuration."""
    port: int = 1883
    clean_session: bool = True
    # Last Will and Testament
    lwt_topic: Optional[str] = None
    lwt_payload: Optional[str] = None
    lwt_qos: QoSLevel = QoSLevel.AT_LEAST_ONCE
    lwt_retain: bool = False
    # Protocol version (3.1.1 = 4, 5.0 = 5)
    protocol_version: int = 4
    # Subscription settings
    max_inflight_messages: int = 20
    message_retry_interval: float = 5.0


class MQTTHandler(AbstractProtocolHandler):
    """
    MQTT Protocol Handler with full QoS support.

    Simulates MQTT client behavior for IoT device communication.
    Can connect to real MQTT brokers (Mosquitto, HiveMQ, etc.) or
    operate in simulation mode.
    """

    def __init__(self, config: MQTTConfig):
        """
        Initialize MQTT handler.

        Args:
            config: MQTT configuration
        """
        super().__init__(config)
        self.mqtt_config = config

        # Message tracking for QoS 1 and 2
        self._pending_acks: dict[str, ProtocolMessage] = {}
        self._pending_rec: dict[str, ProtocolMessage] = {}  # QoS 2 PUBREC
        self._pending_comp: dict[str, ProtocolMessage] = {}  # QoS 2 PUBCOMP

        # Internal state
        self._client = None
        self._message_loop_task: Optional[asyncio.Task] = None

        # Simulation mode flag (no real broker)
        self._simulation_mode = config.extra_config.get("simulation_mode", True)

        # Message buffer for simulation mode
        self._message_buffer: list[ProtocolMessage] = []
        self._retained_messages: dict[str, ProtocolMessage] = {}

    @property
    def protocol_type(self) -> ProtocolType:
        return ProtocolType.MQTT

    async def connect(self) -> bool:
        """
        Connect to MQTT broker.

        Returns:
            True if connection successful
        """
        if self.state == ConnectionState.CONNECTED:
            logger.warning("Already connected to MQTT broker")
            return True

        self.state = ConnectionState.CONNECTING
        logger.info(f"Connecting to MQTT broker at {self.config.host}:{self.config.port}")

        try:
            if self._simulation_mode:
                # Simulation mode - no real broker connection
                await asyncio.sleep(0.1)  # Simulate connection delay
                self.state = ConnectionState.CONNECTED
                self.stats.connected_since = datetime.now()
                logger.info("MQTT handler connected (simulation mode)")

                # Start message processing loop
                self._message_loop_task = asyncio.create_task(self._process_messages())
                return True

            else:
                # Real broker connection using paho-mqtt
                # This would require paho-mqtt-python package
                # For now, we simulate the connection
                try:
                    import paho.mqtt.client as mqtt

                    def on_connect(client, userdata, flags, rc):
                        if rc == 0:
                            logger.info("Connected to MQTT broker")
                            self.state = ConnectionState.CONNECTED
                            self.stats.connected_since = datetime.now()
                        else:
                            logger.error(f"MQTT connection failed with code: {rc}")
                            self.state = ConnectionState.ERROR

                    def on_disconnect(client, userdata, rc):
                        logger.warning(f"Disconnected from MQTT broker (rc={rc})")
                        self.state = ConnectionState.DISCONNECTED
                        if self._running and rc != 0:
                            asyncio.create_task(self._start_reconnect_loop())

                    def on_message(client, userdata, msg):
                        message = ProtocolMessage(
                            topic=msg.topic,
                            payload=self._decode_payload(msg.payload),
                            qos=QoSLevel(msg.qos),
                            retain=msg.retain,
                            timestamp=datetime.now(),
                        )
                        asyncio.create_task(self._handle_message(message))

                    def on_publish(client, userdata, mid):
                        # Handle QoS 1/2 acknowledgments
                        msg_id = str(mid)
                        if msg_id in self._pending_acks:
                            del self._pending_acks[msg_id]

                    self._client = mqtt.Client(
                        client_id=self.config.client_id,
                        clean_session=self.mqtt_config.clean_session,
                        protocol=mqtt.MQTTv311 if self.mqtt_config.protocol_version == 4 else mqtt.MQTTv5,
                    )

                    self._client.on_connect = on_connect
                    self._client.on_disconnect = on_disconnect
                    self._client.on_message = on_message
                    self._client.on_publish = on_publish

                    # Authentication
                    if self.config.username and self.config.password:
                        self._client.username_pw_set(self.config.username, self.config.password)

                    # TLS
                    if self.config.use_tls:
                        self._client.tls_set(
                            ca_certs=self.config.tls_ca_path,
                            certfile=self.config.tls_cert_path,
                            keyfile=self.config.tls_key_path,
                        )

                    # Last Will and Testament
                    if self.mqtt_config.lwt_topic:
                        self._client.will_set(
                            self.mqtt_config.lwt_topic,
                            self.mqtt_config.lwt_payload,
                            qos=self.mqtt_config.lwt_qos.value,
                            retain=self.mqtt_config.lwt_retain,
                        )

                    # Connect
                    self._client.connect_async(
                        self.config.host,
                        self.config.port,
                        keepalive=self.config.keep_alive,
                    )
                    self._client.loop_start()

                    # Wait for connection
                    for _ in range(int(self.config.connection_timeout)):
                        if self.state == ConnectionState.CONNECTED:
                            return True
                        await asyncio.sleep(1)

                    raise TimeoutError("Connection timeout")

                except ImportError:
                    logger.warning("paho-mqtt not installed, using simulation mode")
                    self._simulation_mode = True
                    return await self.connect()

        except Exception as e:
            logger.error(f"MQTT connection error: {e}")
            self.state = ConnectionState.ERROR
            self.stats.record_error()
            return False

    async def disconnect(self) -> None:
        """Disconnect from MQTT broker."""
        logger.info("Disconnecting from MQTT broker")

        if self._message_loop_task:
            self._message_loop_task.cancel()
            try:
                await self._message_loop_task
            except asyncio.CancelledError:
                pass

        if self._client and not self._simulation_mode:
            self._client.loop_stop()
            self._client.disconnect()

        self.state = ConnectionState.DISCONNECTED
        logger.info("MQTT handler disconnected")

    async def publish(self, message: ProtocolMessage) -> bool:
        """
        Publish a message to MQTT broker.

        Implements full QoS support:
        - QoS 0: Fire and forget
        - QoS 1: At least once (waits for PUBACK)
        - QoS 2: Exactly once (PUBREC -> PUBREL -> PUBCOMP)

        Args:
            message: Message to publish

        Returns:
            True if publish successful
        """
        if not self.is_connected:
            logger.error("Cannot publish: not connected")
            return False

        try:
            logger.debug(f"Publishing to {message.topic} with QoS {message.qos.value}")

            if self._simulation_mode:
                return await self._simulate_publish(message)
            else:
                return await self._real_publish(message)

        except Exception as e:
            logger.error(f"Publish error: {e}")
            self.stats.record_error()
            return False

    async def _simulate_publish(self, message: ProtocolMessage) -> bool:
        """Simulate message publishing."""
        # Encode payload
        payload_bytes = self._encode_payload(message.payload)

        # Simulate QoS handling
        if message.qos == QoSLevel.AT_MOST_ONCE:
            # QoS 0: No acknowledgment needed
            pass

        elif message.qos == QoSLevel.AT_LEAST_ONCE:
            # QoS 1: Simulate PUBACK
            self._pending_acks[message.id] = message
            await asyncio.sleep(0.01)  # Simulate network delay
            del self._pending_acks[message.id]

        elif message.qos == QoSLevel.EXACTLY_ONCE:
            # QoS 2: Simulate full handshake
            # Step 1: PUBLISH sent, wait for PUBREC
            self._pending_rec[message.id] = message
            await asyncio.sleep(0.01)

            # Step 2: PUBREC received, send PUBREL, wait for PUBCOMP
            del self._pending_rec[message.id]
            self._pending_comp[message.id] = message
            await asyncio.sleep(0.01)

            # Step 3: PUBCOMP received, complete
            del self._pending_comp[message.id]

        # Handle retained messages
        if message.retain:
            self._retained_messages[message.topic] = message

        # Add to buffer for subscribers
        self._message_buffer.append(message)

        # In simulation mode, immediately notify subscribers for synchronous testing
        await self._handle_message(message)

        self.stats.record_sent(len(payload_bytes))
        logger.debug(f"Message published successfully: {message.id}")
        return True

    async def _real_publish(self, message: ProtocolMessage) -> bool:
        """Publish to real MQTT broker."""
        payload_bytes = self._encode_payload(message.payload)

        result = self._client.publish(
            message.topic,
            payload_bytes,
            qos=message.qos.value,
            retain=message.retain,
        )

        if message.qos > QoSLevel.AT_MOST_ONCE:
            self._pending_acks[str(result.mid)] = message

            # Wait for acknowledgment
            timeout = self.mqtt_config.message_retry_interval * 3
            start = asyncio.get_event_loop().time()

            while str(result.mid) in self._pending_acks:
                if asyncio.get_event_loop().time() - start > timeout:
                    logger.warning(f"Publish timeout for message {message.id}")
                    self.stats.record_error()
                    return False
                await asyncio.sleep(0.1)

        self.stats.record_sent(len(payload_bytes))
        return True

    async def subscribe(
        self,
        topic: str,
        callback: MessageCallback | AsyncMessageCallback,
        qos: QoSLevel = QoSLevel.AT_LEAST_ONCE,
    ) -> bool:
        """
        Subscribe to a topic.

        Args:
            topic: Topic pattern (supports + and # wildcards)
            callback: Callback for received messages
            qos: Maximum QoS level for subscription

        Returns:
            True if subscription successful
        """
        if not self.is_connected:
            logger.error("Cannot subscribe: not connected")
            return False

        try:
            if topic not in self._subscriptions:
                self._subscriptions[topic] = []

            self._subscriptions[topic].append(callback)

            if not self._simulation_mode and self._client:
                self._client.subscribe(topic, qos.value)

            # Send retained messages for this topic
            if self._simulation_mode:
                for retained_topic, msg in self._retained_messages.items():
                    if self._topic_matches(topic, retained_topic):
                        await self._handle_message(msg)

            logger.info(f"Subscribed to topic: {topic}")
            return True

        except Exception as e:
            logger.error(f"Subscribe error: {e}")
            self.stats.record_error()
            return False

    async def unsubscribe(self, topic: str) -> bool:
        """
        Unsubscribe from a topic.

        Args:
            topic: Topic to unsubscribe from

        Returns:
            True if unsubscription successful
        """
        if topic in self._subscriptions:
            del self._subscriptions[topic]

            if not self._simulation_mode and self._client:
                self._client.unsubscribe(topic)

            logger.info(f"Unsubscribed from topic: {topic}")
            return True

        return False

    async def _process_messages(self) -> None:
        """Process incoming messages in simulation mode."""
        while self._running and self.is_connected:
            try:
                # Check for messages in buffer
                while self._message_buffer:
                    message = self._message_buffer.pop(0)
                    await self._handle_message(message)

                await asyncio.sleep(0.01)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Message processing error: {e}")
                self.stats.record_error()

    def _encode_payload(self, payload: Any) -> bytes:
        """Encode payload to bytes."""
        if isinstance(payload, bytes):
            return payload
        elif isinstance(payload, str):
            return payload.encode("utf-8")
        else:
            return json.dumps(payload).encode("utf-8")

    def _decode_payload(self, payload: bytes) -> Any:
        """Decode payload from bytes."""
        try:
            return json.loads(payload.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            return payload.decode("utf-8", errors="replace")

    async def publish_device_telemetry(
        self,
        device_id: str,
        data: dict[str, Any],
        qos: QoSLevel = QoSLevel.AT_LEAST_ONCE,
    ) -> bool:
        """
        Convenience method to publish device telemetry.

        Args:
            device_id: Device identifier
            data: Telemetry data
            qos: QoS level

        Returns:
            True if successful
        """
        topic = f"devices/{device_id}/telemetry"
        message = ProtocolMessage(
            topic=topic,
            payload={
                "device_id": device_id,
                "timestamp": datetime.now().isoformat(),
                "data": data,
            },
            qos=qos,
        )
        return await self.publish(message)

    async def publish_device_status(
        self,
        device_id: str,
        status: str,
        retain: bool = True,
    ) -> bool:
        """
        Publish device status (retained message).

        Args:
            device_id: Device identifier
            status: Device status
            retain: Whether to retain message

        Returns:
            True if successful
        """
        topic = f"devices/{device_id}/status"
        message = ProtocolMessage(
            topic=topic,
            payload={"device_id": device_id, "status": status, "timestamp": datetime.now().isoformat()},
            qos=QoSLevel.AT_LEAST_ONCE,
            retain=retain,
        )
        return await self.publish(message)

    async def subscribe_device_commands(
        self,
        device_id: str,
        callback: MessageCallback | AsyncMessageCallback,
    ) -> bool:
        """
        Subscribe to device commands.

        Args:
            device_id: Device identifier (use '+' for all devices)
            callback: Callback for commands

        Returns:
            True if successful
        """
        topic = f"devices/{device_id}/commands"
        return await self.subscribe(topic, callback)

    def get_stats(self) -> dict[str, Any]:
        """Get MQTT-specific statistics."""
        stats = super().get_stats()
        stats.update({
            "pending_acks": len(self._pending_acks),
            "pending_rec": len(self._pending_rec),
            "pending_comp": len(self._pending_comp),
            "retained_messages": len(self._retained_messages),
            "simulation_mode": self._simulation_mode,
            "broker": f"{self.config.host}:{self.config.port}",
        })
        return stats
