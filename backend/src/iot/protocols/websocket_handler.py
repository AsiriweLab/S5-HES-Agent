"""
WebSocket Protocol Handler - Implementation for full-duplex communication.

Sprint 11 - S11.6: Implement WebSocketHandler

Features:
- Full-duplex bidirectional communication
- Automatic reconnection
- Heartbeat/ping-pong
- JSON and binary message support
- Room/channel subscriptions
- Frame fragmentation for large messages (RFC 6455)
"""

import asyncio
import json
import struct
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional
from uuid import uuid4
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


class WSMessageType(str, Enum):
    """WebSocket message types."""
    TEXT = "text"
    BINARY = "binary"
    PING = "ping"
    PONG = "pong"
    CLOSE = "close"


@dataclass
class WSConfig(ProtocolConfig):
    """WebSocket-specific configuration."""
    port: int = 8080
    path: str = "/ws"
    # Heartbeat settings
    ping_interval: float = 30.0
    ping_timeout: float = 10.0
    # Message settings
    max_message_size: int = 1024 * 1024  # 1MB
    compression: bool = True
    # Reconnection
    reconnect_on_close: bool = True


@dataclass
class WSMessage:
    """WebSocket message container."""
    type: WSMessageType
    data: Any
    timestamp: datetime = field(default_factory=datetime.now)

    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps({
            "type": self.type.value,
            "data": self.data,
            "timestamp": self.timestamp.isoformat(),
        })

    @classmethod
    def from_json(cls, text: str) -> "WSMessage":
        """Create from JSON string."""
        data = json.loads(text)
        return cls(
            type=WSMessageType(data.get("type", "text")),
            data=data.get("data"),
            timestamp=datetime.fromisoformat(data["timestamp"]) if "timestamp" in data else datetime.now(),
        )


class WebSocketHandler(AbstractProtocolHandler):
    """
    WebSocket Protocol Handler for real-time IoT communication.

    Used for:
    - Dashboard real-time updates
    - Device streaming data
    - Command/control channels
    """

    def __init__(self, config: WSConfig):
        """
        Initialize WebSocket handler.

        Args:
            config: WebSocket configuration
        """
        super().__init__(config)
        self.ws_config = config
        self._ws = None

        # Message handlers by channel/room
        self._channels: dict[str, list[MessageCallback | AsyncMessageCallback]] = {}

        # Pending messages (when disconnected)
        self._pending_messages: list[ProtocolMessage] = []

        # Heartbeat task
        self._heartbeat_task: Optional[asyncio.Task] = None

        # Receive task
        self._receive_task: Optional[asyncio.Task] = None

        # Build WebSocket URL
        protocol = "wss" if config.use_tls else "ws"
        self._ws_url = f"{protocol}://{config.host}:{config.port}{config.path}"

        # Simulation mode
        self._simulation_mode = config.extra_config.get("simulation_mode", True)

        # Simulated message buffer
        self._sim_buffer: asyncio.Queue[WSMessage] = asyncio.Queue()

        # Frame fragmentation support (RFC 6455 Section 5.4)
        self._default_fragment_size: int = 65536  # 64KB default
        self._fragment_reassembly: dict[str, "FragmentedMessage"] = {}
        self._fragmentation_stats: Optional["FragmentationStats"] = None  # Lazy init

    @property
    def protocol_type(self) -> ProtocolType:
        return ProtocolType.WEBSOCKET

    async def connect(self) -> bool:
        """
        Establish WebSocket connection.
        """
        if self.state == ConnectionState.CONNECTED:
            return True

        self.state = ConnectionState.CONNECTING
        logger.info(f"Connecting to WebSocket at {self._ws_url}")

        try:
            if self._simulation_mode:
                await asyncio.sleep(0.05)
                self.state = ConnectionState.CONNECTED
                self.stats.connected_since = datetime.now()

                # Start receive loop for simulation
                self._receive_task = asyncio.create_task(self._sim_receive_loop())

                logger.info("WebSocket connected (simulation mode)")
                return True
            else:
                try:
                    import websockets

                    # Build connection parameters
                    extra_headers = {}
                    if self.config.username and self.config.password:
                        import base64
                        credentials = base64.b64encode(
                            f"{self.config.username}:{self.config.password}".encode()
                        ).decode()
                        extra_headers["Authorization"] = f"Basic {credentials}"

                    self._ws = await websockets.connect(
                        self._ws_url,
                        extra_headers=extra_headers,
                        ping_interval=self.ws_config.ping_interval,
                        ping_timeout=self.ws_config.ping_timeout,
                        max_size=self.ws_config.max_message_size,
                        compression="deflate" if self.ws_config.compression else None,
                    )

                    self.state = ConnectionState.CONNECTED
                    self.stats.connected_since = datetime.now()

                    # Start receive loop
                    self._receive_task = asyncio.create_task(self._receive_loop())

                    # Send pending messages
                    await self._flush_pending_messages()

                    logger.info("WebSocket connected")
                    return True

                except ImportError:
                    logger.warning("websockets library not available, using simulation mode")
                    self._simulation_mode = True
                    return await self.connect()

        except Exception as e:
            logger.error(f"WebSocket connection error: {e}")
            self.state = ConnectionState.ERROR
            self.stats.record_error()
            return False

    async def disconnect(self) -> None:
        """Close WebSocket connection."""
        logger.info("Closing WebSocket connection")

        if self._heartbeat_task:
            self._heartbeat_task.cancel()

        if self._receive_task:
            self._receive_task.cancel()

        if self._ws and not self._simulation_mode:
            await self._ws.close()
            self._ws = None

        self.state = ConnectionState.DISCONNECTED
        logger.info("WebSocket disconnected")

    async def publish(self, message: ProtocolMessage) -> bool:
        """
        Send a message through WebSocket.

        Args:
            message: Message to send (topic used as channel)

        Returns:
            True if sent successfully
        """
        if not self.is_connected:
            if self.ws_config.reconnect_on_close:
                self._pending_messages.append(message)
                logger.debug(f"Message queued for later delivery: {message.id}")
                return True
            return False

        try:
            ws_message = {
                "id": message.id,
                "channel": message.topic,
                "payload": message.payload,
                "timestamp": message.timestamp.isoformat(),
                "metadata": message.metadata,
            }

            data = json.dumps(ws_message)

            if self._simulation_mode:
                # Put in simulation buffer for local subscribers
                await self._sim_buffer.put(WSMessage(
                    type=WSMessageType.TEXT,
                    data=ws_message,
                ))
            else:
                await self._ws.send(data)

            self.stats.record_sent(len(data))
            logger.debug(f"WebSocket message sent to channel: {message.topic}")
            return True

        except Exception as e:
            logger.error(f"WebSocket send error: {e}")
            self.stats.record_error()
            return False

    async def subscribe(
        self,
        topic: str,
        callback: MessageCallback | AsyncMessageCallback,
    ) -> bool:
        """
        Subscribe to a WebSocket channel.

        Args:
            topic: Channel name to subscribe to
            callback: Callback for messages on this channel

        Returns:
            True if subscribed
        """
        if topic not in self._subscriptions:
            self._subscriptions[topic] = []

        self._subscriptions[topic].append(callback)

        # Also track in channels
        if topic not in self._channels:
            self._channels[topic] = []
        self._channels[topic].append(callback)

        # Send subscribe message to server
        if self.is_connected and not self._simulation_mode:
            await self.send_json({
                "action": "subscribe",
                "channel": topic,
            })

        logger.info(f"Subscribed to WebSocket channel: {topic}")
        return True

    async def unsubscribe(self, topic: str) -> bool:
        """Unsubscribe from a channel."""
        if topic in self._subscriptions:
            del self._subscriptions[topic]

        if topic in self._channels:
            del self._channels[topic]

        if self.is_connected and not self._simulation_mode:
            await self.send_json({
                "action": "unsubscribe",
                "channel": topic,
            })

        logger.info(f"Unsubscribed from WebSocket channel: {topic}")
        return True

    async def send_json(self, data: dict[str, Any]) -> bool:
        """Send JSON data directly."""
        message = ProtocolMessage(
            topic="__direct__",
            payload=data,
        )
        return await self.publish(message)

    async def send_binary(self, data: bytes, channel: str = "") -> bool:
        """Send binary data."""
        if not self.is_connected:
            return False

        try:
            if self._simulation_mode:
                await self._sim_buffer.put(WSMessage(
                    type=WSMessageType.BINARY,
                    data={"channel": channel, "binary": data.hex()},
                ))
            else:
                await self._ws.send(data)

            self.stats.record_sent(len(data))
            return True

        except Exception as e:
            logger.error(f"WebSocket binary send error: {e}")
            self.stats.record_error()
            return False

    async def _receive_loop(self) -> None:
        """Receive messages from WebSocket."""
        try:
            async for message in self._ws:
                await self._process_incoming(message)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"WebSocket receive error: {e}")
            self.stats.record_error()

            if self.ws_config.reconnect_on_close and self._running:
                asyncio.create_task(self._start_reconnect_loop())

    async def _sim_receive_loop(self) -> None:
        """Simulated receive loop."""
        while self._running and self.is_connected:
            try:
                # Check for messages in simulation buffer
                try:
                    ws_msg = await asyncio.wait_for(self._sim_buffer.get(), timeout=0.1)
                    await self._process_incoming_sim(ws_msg)
                except asyncio.TimeoutError:
                    pass

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Simulation receive error: {e}")

    async def _process_incoming(self, raw_message: str | bytes) -> None:
        """Process incoming WebSocket message."""
        try:
            if isinstance(raw_message, bytes):
                # Binary message
                message = ProtocolMessage(
                    topic="__binary__",
                    payload=raw_message,
                )
            else:
                # Text/JSON message
                data = json.loads(raw_message)
                channel = data.get("channel", "__default__")

                message = ProtocolMessage(
                    id=data.get("id", ""),
                    topic=channel,
                    payload=data.get("payload", data),
                    timestamp=datetime.fromisoformat(data["timestamp"]) if "timestamp" in data else datetime.now(),
                    metadata=data.get("metadata", {}),
                )

            self.stats.record_received(len(raw_message) if isinstance(raw_message, (str, bytes)) else 0)
            await self._handle_message(message)

        except json.JSONDecodeError:
            # Plain text message
            message = ProtocolMessage(
                topic="__text__",
                payload=raw_message,
            )
            await self._handle_message(message)

    async def _process_incoming_sim(self, ws_msg: WSMessage) -> None:
        """Process simulated incoming message."""
        if ws_msg.type == WSMessageType.TEXT:
            data = ws_msg.data
            channel = data.get("channel", "__default__")

            message = ProtocolMessage(
                id=data.get("id", ""),
                topic=channel,
                payload=data.get("payload", data),
                timestamp=ws_msg.timestamp,
                metadata=data.get("metadata", {}),
            )

            self.stats.record_received()
            await self._handle_message(message)

    async def _flush_pending_messages(self) -> None:
        """Send all pending messages."""
        while self._pending_messages:
            message = self._pending_messages.pop(0)
            await self.publish(message)

    # Convenience methods for IoT

    async def broadcast_device_update(
        self,
        device_id: str,
        update: dict[str, Any],
    ) -> bool:
        """Broadcast device update to subscribers."""
        return await self.publish(ProtocolMessage(
            topic=f"devices/{device_id}",
            payload={
                "event": "update",
                "device_id": device_id,
                "data": update,
                "timestamp": datetime.now().isoformat(),
            },
        ))

    async def send_command(
        self,
        device_id: str,
        command: str,
        params: Optional[dict] = None,
    ) -> bool:
        """Send command to device."""
        return await self.publish(ProtocolMessage(
            topic=f"devices/{device_id}/commands",
            payload={
                "command": command,
                "params": params or {},
                "timestamp": datetime.now().isoformat(),
            },
        ))

    async def subscribe_device_events(
        self,
        device_id: str,
        callback: MessageCallback | AsyncMessageCallback,
    ) -> bool:
        """Subscribe to device events."""
        return await self.subscribe(f"devices/{device_id}", callback)

    async def join_room(self, room: str) -> bool:
        """Join a room/channel."""
        return await self.send_json({
            "action": "join",
            "room": room,
        })

    async def leave_room(self, room: str) -> bool:
        """Leave a room/channel."""
        return await self.send_json({
            "action": "leave",
            "room": room,
        })

    def get_stats(self) -> dict[str, Any]:
        """Get WebSocket-specific statistics."""
        stats = super().get_stats()
        stats.update({
            "url": self._ws_url,
            "channels": list(self._channels.keys()),
            "pending_messages": len(self._pending_messages),
            "simulation_mode": self._simulation_mode,
            "fragmentation": self.get_fragmentation_stats(),
        })
        return stats

    # ========== Frame Fragmentation (RFC 6455 Section 5.4) ==========

    async def send_fragmented(
        self,
        data: bytes | str,
        channel: str = "",
        fragment_size: Optional[int] = None,
    ) -> bool:
        """
        Send a large message using frame fragmentation (RFC 6455 Section 5.4).

        Large messages are split into multiple frames:
        - First frame: opcode = text/binary, FIN = 0
        - Continuation frames: opcode = 0 (continuation), FIN = 0
        - Final frame: opcode = 0 (continuation), FIN = 1

        Args:
            data: Data to send (bytes or string)
            channel: Optional channel for the message
            fragment_size: Size of each fragment (default: 64KB)

        Returns:
            True if all fragments sent successfully
        """
        if not self.is_connected:
            return False

        fragment_size = fragment_size or self._default_fragment_size
        is_binary = isinstance(data, bytes)

        if isinstance(data, str):
            data = data.encode('utf-8')

        total_size = len(data)
        num_fragments = (total_size + fragment_size - 1) // fragment_size

        if num_fragments <= 1:
            # No fragmentation needed
            if is_binary:
                return await self.send_binary(data, channel)
            else:
                return await self.send_json({"channel": channel, "data": data.decode('utf-8')})

        # Initialize fragmentation stats if not already initialized
        if self._fragmentation_stats is None:
            self._fragmentation_stats = FragmentationStats()

        message_id = str(uuid4())
        logger.debug(f"Fragmenting message {message_id}: {total_size} bytes into {num_fragments} fragments")

        try:
            for i in range(num_fragments):
                start = i * fragment_size
                end = min(start + fragment_size, total_size)
                fragment_data = data[start:end]

                is_first = (i == 0)
                is_last = (i == num_fragments - 1)

                frame = WSFrame(
                    fin=is_last,
                    opcode=WSOpcode.BINARY if is_binary and is_first else (
                        WSOpcode.TEXT if not is_binary and is_first else WSOpcode.CONTINUATION
                    ),
                    payload=fragment_data,
                    fragment_index=i,
                    total_fragments=num_fragments,
                    message_id=message_id,
                )

                if self._simulation_mode:
                    # Simulate fragmented send
                    await self._sim_buffer.put(WSMessage(
                        type=WSMessageType.BINARY if is_binary else WSMessageType.TEXT,
                        data={
                            "channel": channel,
                            "fragment": True,
                            "message_id": message_id,
                            "index": i,
                            "total": num_fragments,
                            "fin": is_last,
                            "data": fragment_data.hex() if is_binary else fragment_data.decode('utf-8'),
                        },
                    ))
                else:
                    # Real WebSocket send
                    await self._ws.send(frame.to_bytes())

                self.stats.record_sent(len(fragment_data))

            self._fragmentation_stats.messages_fragmented += 1
            self._fragmentation_stats.fragments_sent += num_fragments
            logger.debug(f"Successfully sent {num_fragments} fragments for message {message_id}")
            return True

        except Exception as e:
            logger.error(f"Fragmented send error: {e}")
            self.stats.record_error()
            return False

    async def receive_fragment(self, frame: "WSFrame") -> Optional[bytes]:
        """
        Process a received fragment and reassemble if complete.

        Args:
            frame: Received WebSocket frame

        Returns:
            Complete message bytes if reassembly complete, None otherwise
        """
        if not hasattr(self, '_fragment_reassembly'):
            self._fragment_reassembly = {}
        if not hasattr(self, '_fragmentation_stats'):
            self._fragmentation_stats = FragmentationStats()

        message_id = frame.message_id

        if frame.opcode != WSOpcode.CONTINUATION and not frame.fin:
            # First fragment of a new message
            self._fragment_reassembly[message_id] = FragmentedMessage(
                message_id=message_id,
                is_binary=(frame.opcode == WSOpcode.BINARY),
                fragments=[],
                total_expected=frame.total_fragments,
            )

        if message_id not in self._fragment_reassembly:
            # Orphan continuation frame
            logger.warning(f"Received continuation frame without initial frame: {message_id}")
            self._fragmentation_stats.reassembly_errors += 1
            return None

        fragmented = self._fragment_reassembly[message_id]
        fragmented.fragments.append(frame.payload)
        fragmented.bytes_received += len(frame.payload)
        fragmented.last_fragment_time = datetime.now()
        self._fragmentation_stats.fragments_received += 1

        if frame.fin:
            # Message complete
            complete_data = b''.join(fragmented.fragments)
            del self._fragment_reassembly[message_id]
            self._fragmentation_stats.messages_reassembled += 1
            logger.debug(f"Reassembled message {message_id}: {len(complete_data)} bytes from {len(fragmented.fragments)} fragments")
            return complete_data

        return None

    def set_fragment_size(self, size: int) -> None:
        """
        Set the default fragment size for outgoing messages.

        Args:
            size: Fragment size in bytes (must be >= 1024)
        """
        if size < 1024:
            raise ValueError("Fragment size must be at least 1024 bytes")
        self._default_fragment_size = size

    def get_fragmentation_stats(self) -> dict[str, Any]:
        """Get fragmentation statistics."""
        if not hasattr(self, '_fragmentation_stats'):
            return {
                "messages_fragmented": 0,
                "messages_reassembled": 0,
                "fragments_sent": 0,
                "fragments_received": 0,
                "reassembly_errors": 0,
                "pending_reassembly": 0,
            }

        pending = len(self._fragment_reassembly) if hasattr(self, '_fragment_reassembly') else 0
        return {
            **self._fragmentation_stats.to_dict(),
            "pending_reassembly": pending,
        }

    async def send_large_binary(
        self,
        data: bytes,
        channel: str = "",
        progress_callback: Optional[callable] = None,
    ) -> bool:
        """
        Send large binary data with optional progress callback.

        Args:
            data: Binary data to send
            channel: Channel for the message
            progress_callback: Optional callback(bytes_sent, total_bytes)

        Returns:
            True if successful
        """
        if len(data) <= self._default_fragment_size:
            return await self.send_binary(data, channel)

        total = len(data)
        sent = 0
        fragment_size = self._default_fragment_size
        num_fragments = (total + fragment_size - 1) // fragment_size
        message_id = str(uuid4())

        for i in range(num_fragments):
            start = i * fragment_size
            end = min(start + fragment_size, total)
            fragment = data[start:end]

            success = await self._send_fragment(
                fragment,
                is_first=(i == 0),
                is_last=(i == num_fragments - 1),
                is_binary=True,
                message_id=message_id,
                channel=channel,
            )

            if not success:
                return False

            sent += len(fragment)
            if progress_callback:
                progress_callback(sent, total)

        return True

    async def _send_fragment(
        self,
        data: bytes,
        is_first: bool,
        is_last: bool,
        is_binary: bool,
        message_id: str,
        channel: str,
    ) -> bool:
        """Send a single fragment."""
        try:
            if self._simulation_mode:
                await self._sim_buffer.put(WSMessage(
                    type=WSMessageType.BINARY if is_binary else WSMessageType.TEXT,
                    data={
                        "channel": channel,
                        "fragment": True,
                        "message_id": message_id,
                        "first": is_first,
                        "last": is_last,
                        "data": data.hex() if is_binary else data.decode('utf-8'),
                    },
                ))
            else:
                # Build frame header manually
                opcode = (WSOpcode.BINARY if is_binary else WSOpcode.TEXT) if is_first else WSOpcode.CONTINUATION
                frame = WSFrame(
                    fin=is_last,
                    opcode=opcode,
                    payload=data,
                    message_id=message_id,
                )
                await self._ws.send(frame.to_bytes())

            self.stats.record_sent(len(data))
            return True

        except Exception as e:
            logger.error(f"Fragment send error: {e}")
            return False

    def cleanup_stale_fragments(self, max_age_seconds: float = 60.0) -> int:
        """
        Clean up stale fragment reassembly buffers.

        Args:
            max_age_seconds: Maximum age for incomplete messages

        Returns:
            Number of stale messages cleaned up
        """
        if not hasattr(self, '_fragment_reassembly'):
            return 0

        now = datetime.now()
        stale_ids = []

        for msg_id, fragmented in self._fragment_reassembly.items():
            age = (now - fragmented.last_fragment_time).total_seconds()
            if age > max_age_seconds:
                stale_ids.append(msg_id)

        for msg_id in stale_ids:
            del self._fragment_reassembly[msg_id]
            if hasattr(self, '_fragmentation_stats'):
                self._fragmentation_stats.reassembly_errors += 1

        if stale_ids:
            logger.warning(f"Cleaned up {len(stale_ids)} stale fragmented messages")

        return len(stale_ids)


# ========== Frame Fragmentation Data Classes ==========

class WSOpcode(Enum):
    """WebSocket frame opcodes (RFC 6455 Section 5.2)."""
    CONTINUATION = 0x0
    TEXT = 0x1
    BINARY = 0x2
    CLOSE = 0x8
    PING = 0x9
    PONG = 0xA


@dataclass
class WSFrame:
    """
    WebSocket frame for fragmentation support (RFC 6455).

    Frame format:
      0                   1                   2                   3
      0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
     +-+-+-+-+-------+-+-------------+-------------------------------+
     |F|R|R|R| opcode|M| Payload len |    Extended payload length    |
     |I|S|S|S|  (4)  |A|     (7)     |             (16/64)           |
     |N|V|V|V|       |S|             |   (if payload len==126/127)   |
     | |1|2|3|       |K|             |                               |
     +-+-+-+-+-------+-+-------------+ - - - - - - - - - - - - - - - +
    """
    fin: bool = True  # Final fragment
    opcode: WSOpcode = WSOpcode.TEXT
    payload: bytes = field(default_factory=bytes)
    mask: bool = True  # Client frames must be masked
    rsv1: bool = False  # Reserved for extensions
    rsv2: bool = False
    rsv3: bool = False
    # Fragmentation tracking
    fragment_index: int = 0
    total_fragments: int = 1
    message_id: str = ""

    def to_bytes(self) -> bytes:
        """Serialize frame to bytes."""
        # First byte: FIN + RSV + opcode
        first_byte = (
            (0x80 if self.fin else 0) |
            (0x40 if self.rsv1 else 0) |
            (0x20 if self.rsv2 else 0) |
            (0x10 if self.rsv3 else 0) |
            self.opcode.value
        )

        # Second byte: MASK + payload length
        payload_len = len(self.payload)
        if payload_len <= 125:
            second_byte = (0x80 if self.mask else 0) | payload_len
            header = struct.pack('!BB', first_byte, second_byte)
        elif payload_len <= 65535:
            second_byte = (0x80 if self.mask else 0) | 126
            header = struct.pack('!BBH', first_byte, second_byte, payload_len)
        else:
            second_byte = (0x80 if self.mask else 0) | 127
            header = struct.pack('!BBQ', first_byte, second_byte, payload_len)

        # Add masking key and mask payload if needed
        if self.mask:
            import os
            mask_key = os.urandom(4)
            masked_payload = bytes(
                b ^ mask_key[i % 4] for i, b in enumerate(self.payload)
            )
            return header + mask_key + masked_payload
        else:
            return header + self.payload

    @classmethod
    def from_bytes(cls, data: bytes) -> tuple["WSFrame", int]:
        """
        Deserialize frame from bytes.

        Returns:
            Tuple of (WSFrame, bytes_consumed)
        """
        if len(data) < 2:
            raise ValueError("Insufficient data for frame header")

        first_byte = data[0]
        second_byte = data[1]

        fin = bool(first_byte & 0x80)
        rsv1 = bool(first_byte & 0x40)
        rsv2 = bool(first_byte & 0x20)
        rsv3 = bool(first_byte & 0x10)
        opcode = WSOpcode(first_byte & 0x0F)

        mask = bool(second_byte & 0x80)
        payload_len = second_byte & 0x7F

        offset = 2
        if payload_len == 126:
            if len(data) < 4:
                raise ValueError("Insufficient data for extended length")
            payload_len = struct.unpack('!H', data[2:4])[0]
            offset = 4
        elif payload_len == 127:
            if len(data) < 10:
                raise ValueError("Insufficient data for extended length")
            payload_len = struct.unpack('!Q', data[2:10])[0]
            offset = 10

        if mask:
            if len(data) < offset + 4:
                raise ValueError("Insufficient data for mask key")
            mask_key = data[offset:offset + 4]
            offset += 4

        if len(data) < offset + payload_len:
            raise ValueError("Insufficient data for payload")

        payload = data[offset:offset + payload_len]

        if mask:
            payload = bytes(b ^ mask_key[i % 4] for i, b in enumerate(payload))

        frame = cls(
            fin=fin,
            opcode=opcode,
            payload=payload,
            mask=mask,
            rsv1=rsv1,
            rsv2=rsv2,
            rsv3=rsv3,
        )

        return frame, offset + payload_len


@dataclass
class FragmentedMessage:
    """State for a message being reassembled from fragments."""
    message_id: str
    is_binary: bool
    fragments: list[bytes] = field(default_factory=list)
    total_expected: int = 0
    bytes_received: int = 0
    start_time: datetime = field(default_factory=datetime.now)
    last_fragment_time: datetime = field(default_factory=datetime.now)


@dataclass
class FragmentationStats:
    """Statistics for frame fragmentation."""
    messages_fragmented: int = 0
    messages_reassembled: int = 0
    fragments_sent: int = 0
    fragments_received: int = 0
    reassembly_errors: int = 0

    def to_dict(self) -> dict[str, int]:
        """Convert to dictionary."""
        return {
            "messages_fragmented": self.messages_fragmented,
            "messages_reassembled": self.messages_reassembled,
            "fragments_sent": self.fragments_sent,
            "fragments_received": self.fragments_received,
            "reassembly_errors": self.reassembly_errors,
        }
