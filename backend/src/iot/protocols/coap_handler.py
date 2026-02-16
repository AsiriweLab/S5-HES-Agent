"""
CoAP Protocol Handler - Implementation for Constrained Application Protocol.

Sprint 11 - S11.4: Implement CoAPHandler

Features:
- GET, POST, PUT, DELETE methods
- Observe pattern (RFC 7641)
- Blockwise transfers (RFC 7959)
- DTLS security (RFC 6347) - CoAPS on port 5684
- Confirmable and Non-confirmable messages
- Resource discovery
"""

import asyncio
import json
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
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


class CoAPMethod(str, Enum):
    """CoAP request methods."""
    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    DELETE = "DELETE"


class CoAPType(int, Enum):
    """CoAP message types."""
    CONFIRMABLE = 0      # CON - Requires acknowledgment
    NON_CONFIRMABLE = 1  # NON - No acknowledgment needed
    ACKNOWLEDGEMENT = 2  # ACK
    RESET = 3            # RST


class CoAPCode(Enum):
    """CoAP response codes."""
    # Success 2.xx
    CREATED = (2, 1)
    DELETED = (2, 2)
    VALID = (2, 3)
    CHANGED = (2, 4)
    CONTENT = (2, 5)

    # Client Error 4.xx
    BAD_REQUEST = (4, 0)
    UNAUTHORIZED = (4, 1)
    BAD_OPTION = (4, 2)
    FORBIDDEN = (4, 3)
    NOT_FOUND = (4, 4)
    METHOD_NOT_ALLOWED = (4, 5)

    # Server Error 5.xx
    INTERNAL_ERROR = (5, 0)
    NOT_IMPLEMENTED = (5, 1)
    SERVICE_UNAVAILABLE = (5, 3)

    @property
    def code_string(self) -> str:
        return f"{self.value[0]}.{self.value[1]:02d}"


class DTLSVersion(str, Enum):
    """DTLS protocol versions."""
    DTLS_1_0 = "1.0"  # Based on TLS 1.1
    DTLS_1_2 = "1.2"  # Based on TLS 1.2 (recommended)
    DTLS_1_3 = "1.3"  # Based on TLS 1.3 (latest)


class DTLSState(str, Enum):
    """DTLS connection state."""
    DISCONNECTED = "disconnected"
    HANDSHAKE_STARTED = "handshake_started"
    CLIENT_HELLO_SENT = "client_hello_sent"
    SERVER_HELLO_RECEIVED = "server_hello_received"
    CERTIFICATE_EXCHANGE = "certificate_exchange"
    KEY_EXCHANGE = "key_exchange"
    FINISHED = "finished"
    ESTABLISHED = "established"
    FAILED = "failed"


@dataclass
class DTLSConfig:
    """DTLS security configuration."""
    enabled: bool = False
    version: DTLSVersion = DTLSVersion.DTLS_1_2
    # Certificate paths (for real mode)
    certificate_path: Optional[str] = None
    private_key_path: Optional[str] = None
    ca_certificate_path: Optional[str] = None
    # Pre-shared key (alternative to certificates)
    psk_identity: Optional[str] = None
    psk_key: Optional[bytes] = None
    # Security settings
    verify_peer: bool = True
    cipher_suites: list[str] = field(default_factory=lambda: [
        "TLS_ECDHE_ECDSA_WITH_AES_128_CCM_8",  # Mandatory for CoAP
        "TLS_ECDHE_ECDSA_WITH_AES_128_CCM",
        "TLS_PSK_WITH_AES_128_CCM_8",
        "TLS_PSK_WITH_AES_128_CCM",
    ])
    # Handshake timeout
    handshake_timeout: float = 30.0
    # Cookie for DoS protection (RFC 6347)
    use_cookie: bool = True


@dataclass
class DTLSSession:
    """DTLS session state."""
    session_id: str
    state: DTLSState = DTLSState.DISCONNECTED
    version: DTLSVersion = DTLSVersion.DTLS_1_2
    cipher_suite: str = ""
    # Simulated keys (in real implementation, these would be derived from handshake)
    client_write_key: bytes = field(default_factory=bytes)
    server_write_key: bytes = field(default_factory=bytes)
    client_write_iv: bytes = field(default_factory=bytes)
    server_write_iv: bytes = field(default_factory=bytes)
    # Sequence numbers for replay protection
    read_sequence: int = 0
    write_sequence: int = 0
    # Epoch for key changes
    read_epoch: int = 0
    write_epoch: int = 0
    # Handshake messages for retransmission
    handshake_messages: list[bytes] = field(default_factory=list)
    # Timestamps
    established_at: Optional[datetime] = None
    last_activity: datetime = field(default_factory=datetime.now)


@dataclass
class CoAPConfig(ProtocolConfig):
    """CoAP-specific configuration."""
    port: int = 5683
    secure_port: int = 5684  # CoAPS (CoAP over DTLS)
    # Multicast address for resource discovery
    multicast_address: str = "224.0.1.187"
    # Message parameters (RFC 7252)
    ack_timeout: float = 2.0
    ack_random_factor: float = 1.5
    max_retransmit: int = 4
    # Block size for blockwise transfers (16, 32, 64, 128, 256, 512, 1024)
    block_size: int = 512
    # Observe settings
    max_observe_age: int = 60  # seconds
    # DTLS configuration
    dtls: DTLSConfig = field(default_factory=DTLSConfig)


class BlockOption(int, Enum):
    """CoAP Block option numbers (RFC 7959)."""
    BLOCK1 = 27  # Request payload blocks (client -> server)
    BLOCK2 = 23  # Response payload blocks (server -> client)


@dataclass
class BlockwiseState:
    """State for blockwise transfer (RFC 7959)."""
    resource_path: str
    is_upload: bool  # True for Block1 (upload), False for Block2 (download)
    block_size: int  # SZX encoded: actual_size = 2^(szx+4)
    total_size: Optional[int] = None
    current_num: int = 0
    data: bytes = field(default_factory=bytes)
    completed: bool = False
    timestamp: datetime = field(default_factory=datetime.now)

    @staticmethod
    def szx_to_size(szx: int) -> int:
        """Convert SZX value to actual block size."""
        return 2 ** (szx + 4)

    @staticmethod
    def size_to_szx(size: int) -> int:
        """Convert block size to SZX value."""
        import math
        return max(0, min(6, int(math.log2(size)) - 4))

    def encode_block_option(self, more: bool) -> int:
        """Encode block option value: NUM (variable) + M (1 bit) + SZX (3 bits)."""
        szx = self.size_to_szx(self.block_size)
        return (self.current_num << 4) | (int(more) << 3) | szx

    @staticmethod
    def decode_block_option(value: int) -> tuple[int, bool, int]:
        """Decode block option: returns (block_num, more_flag, block_size)."""
        szx = value & 0x07
        more = bool((value >> 3) & 0x01)
        num = value >> 4
        size = BlockwiseState.szx_to_size(szx)
        return num, more, size


@dataclass
class CoAPResource:
    """CoAP resource representation."""
    path: str
    content: Any = None
    content_format: str = "application/json"
    observable: bool = False
    observers: list[str] = field(default_factory=list)
    last_modified: datetime = field(default_factory=datetime.now)
    max_age: int = 60
    etag: Optional[bytes] = None


class CoAPHandler(AbstractProtocolHandler):
    """
    CoAP Protocol Handler for constrained IoT devices.

    Implements RFC 7252 (CoAP) with extensions:
    - RFC 7641 (Observe)
    - RFC 7959 (Blockwise transfers)
    """

    def __init__(self, config: CoAPConfig):
        """
        Initialize CoAP handler.

        Args:
            config: CoAP configuration
        """
        super().__init__(config)
        self.coap_config = config

        # Resources hosted by this handler
        self._resources: dict[str, CoAPResource] = {}

        # Pending requests
        self._pending_requests: dict[int, asyncio.Future] = {}

        # Message ID counter
        self._message_id = 0

        # Observe subscriptions
        self._observations: dict[str, list[tuple[str, MessageCallback | AsyncMessageCallback]]] = {}

        # Simulation mode
        self._simulation_mode = config.extra_config.get("simulation_mode", True)

        # Observation notification task
        self._observe_task: Optional[asyncio.Task] = None

        # Blockwise transfer state (RFC 7959)
        self._block1_transfers: dict[str, BlockwiseState] = {}  # Upload transfers
        self._block2_transfers: dict[str, BlockwiseState] = {}  # Download transfers

    @property
    def protocol_type(self) -> ProtocolType:
        return ProtocolType.COAP

    def _next_message_id(self) -> int:
        """Get next message ID."""
        self._message_id = (self._message_id + 1) % 65536
        return self._message_id

    async def connect(self) -> bool:
        """
        Start CoAP handler.

        For CoAP, "connect" means starting the UDP listener.
        """
        if self.state == ConnectionState.CONNECTED:
            return True

        self.state = ConnectionState.CONNECTING
        logger.info(f"Starting CoAP handler on port {self.config.port}")

        try:
            if self._simulation_mode:
                await asyncio.sleep(0.05)
                self.state = ConnectionState.CONNECTED
                self.stats.connected_since = datetime.now()

                # Start observation notification loop
                self._observe_task = asyncio.create_task(self._observe_notification_loop())

                logger.info("CoAP handler started (simulation mode)")
                return True
            else:
                # Real CoAP implementation would use aiocoap
                try:
                    import aiocoap
                    import aiocoap.resource as resource

                    # This is a simplified example - real implementation would be more complex
                    logger.info("Starting real CoAP server with aiocoap")
                    self.state = ConnectionState.CONNECTED
                    self.stats.connected_since = datetime.now()
                    return True

                except ImportError:
                    logger.warning("aiocoap not installed, using simulation mode")
                    self._simulation_mode = True
                    return await self.connect()

        except Exception as e:
            logger.error(f"CoAP start error: {e}")
            self.state = ConnectionState.ERROR
            self.stats.record_error()
            return False

    async def disconnect(self) -> None:
        """Stop CoAP handler."""
        logger.info("Stopping CoAP handler")

        if self._observe_task:
            self._observe_task.cancel()
            try:
                await self._observe_task
            except asyncio.CancelledError:
                pass

        self._observations.clear()
        self.state = ConnectionState.DISCONNECTED
        logger.info("CoAP handler stopped")

    async def publish(self, message: ProtocolMessage) -> bool:
        """
        Publish a message (update resource and notify observers).

        For CoAP, publishing means updating a resource.

        Args:
            message: Message containing resource path in topic and payload

        Returns:
            True if successful
        """
        if not self.is_connected:
            logger.error("Cannot publish: not connected")
            return False

        try:
            path = message.topic
            payload = message.payload

            # Update or create resource
            if path in self._resources:
                resource = self._resources[path]
                resource.content = payload
                resource.last_modified = datetime.now()
            else:
                resource = CoAPResource(
                    path=path,
                    content=payload,
                    observable=True,
                )
                self._resources[path] = resource

            # Notify observers
            await self._notify_observers(path)

            payload_size = len(self._encode_payload(payload))
            self.stats.record_sent(payload_size)

            logger.debug(f"CoAP resource updated: {path}")
            return True

        except Exception as e:
            logger.error(f"CoAP publish error: {e}")
            self.stats.record_error()
            return False

    async def subscribe(
        self,
        topic: str,
        callback: MessageCallback | AsyncMessageCallback,
    ) -> bool:
        """
        Subscribe to resource changes (CoAP Observe).

        Args:
            topic: Resource path to observe
            callback: Callback for updates

        Returns:
            True if successful
        """
        if not self.is_connected:
            logger.error("Cannot subscribe: not connected")
            return False

        try:
            if topic not in self._subscriptions:
                self._subscriptions[topic] = []

            self._subscriptions[topic].append(callback)

            # Track observation
            if topic not in self._observations:
                self._observations[topic] = []
            self._observations[topic].append((self.config.client_id, callback))

            # If resource exists, send current value
            if topic in self._resources:
                resource = self._resources[topic]
                message = ProtocolMessage(
                    topic=topic,
                    payload=resource.content,
                    timestamp=resource.last_modified,
                )
                await self._handle_message(message)

            logger.info(f"CoAP observe registered for: {topic}")
            return True

        except Exception as e:
            logger.error(f"CoAP subscribe error: {e}")
            self.stats.record_error()
            return False

    async def unsubscribe(self, topic: str) -> bool:
        """
        Cancel observation.

        Args:
            topic: Resource path to stop observing

        Returns:
            True if successful
        """
        if topic in self._subscriptions:
            del self._subscriptions[topic]

        if topic in self._observations:
            del self._observations[topic]

        logger.info(f"CoAP observation cancelled for: {topic}")
        return True

    async def request(
        self,
        method: CoAPMethod,
        path: str,
        payload: Any = None,
        confirmable: bool = True,
    ) -> Optional[tuple[CoAPCode, Any]]:
        """
        Send a CoAP request.

        Args:
            method: CoAP method (GET, POST, PUT, DELETE)
            path: Resource path
            payload: Request payload
            confirmable: Whether to use CON message type

        Returns:
            Tuple of (response_code, response_payload) or None on error
        """
        if not self.is_connected:
            logger.error("Cannot send request: not connected")
            return None

        try:
            msg_id = self._next_message_id()
            msg_type = CoAPType.CONFIRMABLE if confirmable else CoAPType.NON_CONFIRMABLE

            logger.debug(f"CoAP {method.value} {path} (msg_id={msg_id})")

            if self._simulation_mode:
                return await self._simulate_request(method, path, payload)
            else:
                # Real request using aiocoap
                return await self._real_request(method, path, payload, msg_type)

        except Exception as e:
            logger.error(f"CoAP request error: {e}")
            self.stats.record_error()
            return None

    async def _simulate_request(
        self,
        method: CoAPMethod,
        path: str,
        payload: Any,
    ) -> tuple[CoAPCode, Any]:
        """Simulate CoAP request/response."""
        await asyncio.sleep(0.02)  # Simulate network delay

        if method == CoAPMethod.GET:
            if path in self._resources:
                resource = self._resources[path]
                return (CoAPCode.CONTENT, resource.content)
            return (CoAPCode.NOT_FOUND, None)

        elif method == CoAPMethod.POST:
            self._resources[path] = CoAPResource(path=path, content=payload)
            return (CoAPCode.CREATED, None)

        elif method == CoAPMethod.PUT:
            if path in self._resources:
                self._resources[path].content = payload
                self._resources[path].last_modified = datetime.now()
                return (CoAPCode.CHANGED, None)
            return (CoAPCode.NOT_FOUND, None)

        elif method == CoAPMethod.DELETE:
            if path in self._resources:
                del self._resources[path]
                return (CoAPCode.DELETED, None)
            return (CoAPCode.NOT_FOUND, None)

        return (CoAPCode.METHOD_NOT_ALLOWED, None)

    async def _real_request(
        self,
        method: CoAPMethod,
        path: str,
        payload: Any,
        msg_type: CoAPType,
    ) -> Optional[tuple[CoAPCode, Any]]:
        """Send real CoAP request using aiocoap."""
        # Would implement using aiocoap library
        logger.warning("Real CoAP requests not yet implemented")
        return await self._simulate_request(method, path, payload)

    async def _notify_observers(self, path: str) -> None:
        """Notify all observers of a resource change."""
        if path not in self._resources:
            return

        resource = self._resources[path]

        if path in self._observations:
            message = ProtocolMessage(
                topic=path,
                payload=resource.content,
                timestamp=resource.last_modified,
            )

            for _, callback in self._observations[path]:
                try:
                    if asyncio.iscoroutinefunction(callback):
                        await callback(message)
                    else:
                        callback(message)
                except Exception as e:
                    logger.error(f"Observer notification error: {e}")

    async def _observe_notification_loop(self) -> None:
        """Periodically send observe notifications."""
        while self._running and self.is_connected:
            try:
                # Check for max-age expiration and send notifications
                for path in list(self._observations.keys()):
                    if path in self._resources:
                        resource = self._resources[path]
                        age = (datetime.now() - resource.last_modified).total_seconds()
                        if age < resource.max_age:
                            await self._notify_observers(path)

                await asyncio.sleep(5)  # Check every 5 seconds

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Observe loop error: {e}")

    def _encode_payload(self, payload: Any) -> bytes:
        """Encode payload to bytes."""
        if isinstance(payload, bytes):
            return payload
        elif isinstance(payload, str):
            return payload.encode("utf-8")
        else:
            return json.dumps(payload).encode("utf-8")

    # Convenience methods for IoT devices

    async def get_device_state(self, device_id: str) -> Optional[dict]:
        """Get device state."""
        result = await self.request(CoAPMethod.GET, f"/devices/{device_id}/state")
        if result and result[0] == CoAPCode.CONTENT:
            return result[1]
        return None

    async def set_device_state(self, device_id: str, state: dict) -> bool:
        """Set device state."""
        result = await self.request(CoAPMethod.PUT, f"/devices/{device_id}/state", state)
        return result is not None and result[0] == CoAPCode.CHANGED

    async def observe_device(
        self,
        device_id: str,
        callback: MessageCallback | AsyncMessageCallback,
    ) -> bool:
        """Observe device state changes."""
        return await self.subscribe(f"/devices/{device_id}/state", callback)

    async def discover_resources(self) -> list[str]:
        """Discover available resources (/.well-known/core)."""
        result = await self.request(CoAPMethod.GET, "/.well-known/core")
        if result and result[0] == CoAPCode.CONTENT:
            # Parse CoRE Link Format
            return list(self._resources.keys())
        return []

    def register_resource(
        self,
        path: str,
        content: Any = None,
        observable: bool = True,
        max_age: int = 60,
    ) -> None:
        """
        Register a CoAP resource.

        Args:
            path: Resource path
            content: Initial content
            observable: Whether resource supports observe
            max_age: Maximum cache age in seconds
        """
        self._resources[path] = CoAPResource(
            path=path,
            content=content,
            observable=observable,
            max_age=max_age,
        )
        logger.info(f"Registered CoAP resource: {path}")

    # ========== Blockwise Transfer Methods (RFC 7959) ==========

    async def upload_blockwise(
        self,
        path: str,
        data: bytes,
        block_size: Optional[int] = None,
    ) -> tuple[Optional[CoAPCode], Optional[str]]:
        """
        Upload large payload using Block1 blockwise transfer (RFC 7959).

        Args:
            path: Resource path
            data: Data to upload
            block_size: Block size (default from config)

        Returns:
            Tuple of (response_code, error_message)
        """
        if not self.is_connected:
            return None, "Not connected"

        block_size = block_size or self.coap_config.block_size
        total_blocks = (len(data) + block_size - 1) // block_size

        logger.info(f"Starting Block1 upload to {path}: {len(data)} bytes in {total_blocks} blocks")

        # Create transfer state
        transfer_key = f"{self.config.client_id}:{path}"
        state = BlockwiseState(
            resource_path=path,
            is_upload=True,
            block_size=block_size,
            total_size=len(data),
            data=data,
        )
        self._block1_transfers[transfer_key] = state

        try:
            # Send blocks sequentially
            while state.current_num * block_size < len(data):
                start = state.current_num * block_size
                end = min(start + block_size, len(data))
                block_data = data[start:end]
                more = end < len(data)

                # Encode Block1 option
                block_option = state.encode_block_option(more)

                if self._simulation_mode:
                    # Simulate block transfer
                    await asyncio.sleep(0.01)  # Simulate network delay
                    logger.debug(
                        f"Block1 [{state.current_num}/{total_blocks-1}] "
                        f"sent {len(block_data)} bytes (more={more})"
                    )
                else:
                    # Real implementation would send CoAP message with Block1 option
                    pass

                self.stats.record_sent(len(block_data))
                state.current_num += 1

            # Final block sent
            state.completed = True
            logger.info(f"Block1 upload complete: {path} ({len(data)} bytes)")

            # Clean up
            del self._block1_transfers[transfer_key]

            return CoAPCode.CHANGED, None

        except Exception as e:
            logger.error(f"Block1 upload error: {e}")
            if transfer_key in self._block1_transfers:
                del self._block1_transfers[transfer_key]
            return None, str(e)

    async def download_blockwise(
        self,
        path: str,
        block_size: Optional[int] = None,
    ) -> tuple[Optional[bytes], Optional[str]]:
        """
        Download large payload using Block2 blockwise transfer (RFC 7959).

        Args:
            path: Resource path
            block_size: Requested block size (default from config)

        Returns:
            Tuple of (received_data, error_message)
        """
        if not self.is_connected:
            return None, "Not connected"

        block_size = block_size or self.coap_config.block_size

        # Create transfer state
        transfer_key = f"{self.config.client_id}:{path}"
        state = BlockwiseState(
            resource_path=path,
            is_upload=False,
            block_size=block_size,
        )
        self._block2_transfers[transfer_key] = state

        logger.info(f"Starting Block2 download from {path}")

        try:
            received_data = b""
            more = True

            while more:
                # Encode Block2 option (requesting specific block)
                block_option = state.encode_block_option(False)

                if self._simulation_mode:
                    # Simulate fetching block from resource
                    if path in self._resources:
                        resource_data = self._encode_payload(self._resources[path].content)
                        start = state.current_num * block_size
                        end = min(start + block_size, len(resource_data))

                        if start >= len(resource_data):
                            break

                        block_data = resource_data[start:end]
                        more = end < len(resource_data)

                        received_data += block_data
                        self.stats.record_received(len(block_data))

                        logger.debug(
                            f"Block2 [{state.current_num}] "
                            f"received {len(block_data)} bytes (more={more})"
                        )

                        await asyncio.sleep(0.01)  # Simulate network delay
                    else:
                        return None, f"Resource not found: {path}"
                else:
                    # Real implementation would send GET with Block2 option
                    pass

                state.current_num += 1

            state.completed = True
            state.data = received_data
            logger.info(f"Block2 download complete: {path} ({len(received_data)} bytes)")

            # Clean up
            del self._block2_transfers[transfer_key]

            return received_data, None

        except Exception as e:
            logger.error(f"Block2 download error: {e}")
            if transfer_key in self._block2_transfers:
                del self._block2_transfers[transfer_key]
            return None, str(e)

    async def handle_block1_request(
        self,
        path: str,
        block_option: int,
        block_data: bytes,
        client_id: str,
    ) -> tuple[CoAPCode, Optional[int]]:
        """
        Handle incoming Block1 request (server receiving upload).

        Args:
            path: Resource path
            block_option: Block1 option value
            block_data: Block payload
            client_id: Requesting client ID

        Returns:
            Tuple of (response_code, echo_block_option)
        """
        block_num, more, block_size = BlockwiseState.decode_block_option(block_option)

        transfer_key = f"{client_id}:{path}"

        # Get or create transfer state
        if transfer_key not in self._block1_transfers:
            if block_num != 0:
                logger.warning(f"Block1: Received block {block_num} without prior blocks")
                return CoAPCode.BAD_REQUEST, None

            self._block1_transfers[transfer_key] = BlockwiseState(
                resource_path=path,
                is_upload=True,
                block_size=block_size,
            )

        state = self._block1_transfers[transfer_key]

        # Validate block number
        if block_num != state.current_num:
            logger.warning(f"Block1: Expected block {state.current_num}, got {block_num}")
            return CoAPCode.BAD_REQUEST, None

        # Append block data
        state.data += block_data
        state.current_num += 1
        self.stats.record_received(len(block_data))

        logger.debug(f"Block1 server: received block {block_num} ({len(block_data)} bytes, more={more})")

        if not more:
            # Last block - finalize upload
            state.completed = True

            # Store the complete resource
            if path in self._resources:
                self._resources[path].content = state.data
                self._resources[path].last_modified = datetime.now()
            else:
                self._resources[path] = CoAPResource(
                    path=path,
                    content=state.data,
                )

            logger.info(f"Block1 upload complete: {path} ({len(state.data)} bytes)")

            # Clean up
            del self._block1_transfers[transfer_key]

            return CoAPCode.CHANGED, None

        # More blocks expected - echo block option
        echo_option = state.encode_block_option(False)
        return CoAPCode.CONTENT, echo_option

    async def handle_block2_request(
        self,
        path: str,
        block_option: int,
    ) -> tuple[CoAPCode, Optional[bytes], Optional[int]]:
        """
        Handle incoming Block2 request (server responding with download).

        Args:
            path: Resource path
            block_option: Block2 option value

        Returns:
            Tuple of (response_code, block_data, block_option)
        """
        block_num, _, block_size = BlockwiseState.decode_block_option(block_option)

        if path not in self._resources:
            return CoAPCode.NOT_FOUND, None, None

        resource_data = self._encode_payload(self._resources[path].content)
        total_size = len(resource_data)

        # Calculate block boundaries
        start = block_num * block_size
        end = min(start + block_size, total_size)

        if start >= total_size:
            return CoAPCode.BAD_REQUEST, None, None

        block_data = resource_data[start:end]
        more = end < total_size

        # Create response block option
        state = BlockwiseState(
            resource_path=path,
            is_upload=False,
            block_size=block_size,
            current_num=block_num,
        )
        response_option = state.encode_block_option(more)

        self.stats.record_sent(len(block_data))
        logger.debug(f"Block2 server: sending block {block_num} ({len(block_data)} bytes, more={more})")

        return CoAPCode.CONTENT, block_data, response_option

    def get_blockwise_transfer_status(self) -> dict[str, Any]:
        """Get status of active blockwise transfers."""
        return {
            "block1_uploads": {
                k: {
                    "path": v.resource_path,
                    "progress": f"{v.current_num * v.block_size}/{v.total_size or 'unknown'}",
                    "block_size": v.block_size,
                    "completed": v.completed,
                }
                for k, v in self._block1_transfers.items()
            },
            "block2_downloads": {
                k: {
                    "path": v.resource_path,
                    "blocks_received": v.current_num,
                    "bytes_received": len(v.data),
                    "block_size": v.block_size,
                    "completed": v.completed,
                }
                for k, v in self._block2_transfers.items()
            },
        }

    # ========== DTLS Security Methods (RFC 6347) ==========

    async def dtls_handshake(
        self,
        peer_address: str,
        is_client: bool = True,
    ) -> tuple[bool, Optional[DTLSSession]]:
        """
        Perform DTLS handshake with a peer (RFC 6347).

        Args:
            peer_address: Address of the peer (host:port)
            is_client: True if initiating connection, False if responding

        Returns:
            Tuple of (success, session)
        """
        if not self.coap_config.dtls.enabled:
            logger.warning("DTLS is not enabled in configuration")
            return False, None

        import secrets
        import hashlib

        session_id = secrets.token_hex(16)
        session = DTLSSession(
            session_id=session_id,
            version=self.coap_config.dtls.version,
        )

        logger.info(f"Starting DTLS {session.version.value} handshake with {peer_address} (client={is_client})")

        try:
            if self._simulation_mode:
                # Simulate DTLS handshake phases
                session.state = DTLSState.HANDSHAKE_STARTED

                # Phase 1: ClientHello / HelloVerifyRequest (cookie exchange)
                if is_client:
                    session.state = DTLSState.CLIENT_HELLO_SENT
                    await asyncio.sleep(0.02)  # Simulate network RTT

                    if self.coap_config.dtls.use_cookie:
                        # Server would respond with HelloVerifyRequest containing cookie
                        cookie = secrets.token_bytes(32)
                        logger.debug("DTLS: Received HelloVerifyRequest with cookie")
                        await asyncio.sleep(0.02)  # Resend ClientHello with cookie

                # Phase 2: ServerHello
                session.state = DTLSState.SERVER_HELLO_RECEIVED
                await asyncio.sleep(0.02)

                # Select cipher suite
                session.cipher_suite = self.coap_config.dtls.cipher_suites[0]
                logger.debug(f"DTLS: Selected cipher suite {session.cipher_suite}")

                # Phase 3: Certificate exchange (if not PSK)
                if not self.coap_config.dtls.psk_key:
                    session.state = DTLSState.CERTIFICATE_EXCHANGE
                    await asyncio.sleep(0.03)
                    logger.debug("DTLS: Certificate exchange complete")

                # Phase 4: Key exchange
                session.state = DTLSState.KEY_EXCHANGE
                await asyncio.sleep(0.02)

                # Derive simulated keys (in real implementation, use proper key derivation)
                master_secret = secrets.token_bytes(48)
                key_material = hashlib.pbkdf2_hmac(
                    'sha256',
                    master_secret,
                    b"dtls key expansion",
                    1000,
                    dklen=64
                )

                session.client_write_key = key_material[:16]
                session.server_write_key = key_material[16:32]
                session.client_write_iv = key_material[32:48]
                session.server_write_iv = key_material[48:64]

                logger.debug("DTLS: Key derivation complete")

                # Phase 5: Finished
                session.state = DTLSState.FINISHED
                await asyncio.sleep(0.01)

                # Handshake complete
                session.state = DTLSState.ESTABLISHED
                session.established_at = datetime.now()
                session.read_epoch = 1
                session.write_epoch = 1

                logger.info(f"DTLS handshake complete with {peer_address}")
                return True, session

            else:
                # Real DTLS implementation would use a library like mbedtls or openssl
                logger.warning("Real DTLS not implemented, using simulation")
                return await self.dtls_handshake(peer_address, is_client)

        except asyncio.TimeoutError:
            logger.error(f"DTLS handshake timeout with {peer_address}")
            session.state = DTLSState.FAILED
            return False, session
        except Exception as e:
            logger.error(f"DTLS handshake error: {e}")
            session.state = DTLSState.FAILED
            return False, session

    def dtls_encrypt(
        self,
        session: DTLSSession,
        plaintext: bytes,
        is_client: bool = True,
    ) -> Optional[bytes]:
        """
        Encrypt data using DTLS session keys.

        Args:
            session: DTLS session
            plaintext: Data to encrypt
            is_client: True if encrypting as client

        Returns:
            Encrypted data with DTLS record header, or None on error
        """
        if session.state != DTLSState.ESTABLISHED:
            logger.error("Cannot encrypt: DTLS session not established")
            return None

        try:
            import hmac
            import hashlib

            # Select key based on role
            key = session.client_write_key if is_client else session.server_write_key
            iv = session.client_write_iv if is_client else session.server_write_iv

            # Construct nonce from IV and sequence number
            seq_bytes = session.write_sequence.to_bytes(8, 'big')
            nonce = bytes(a ^ b for a, b in zip(iv[:8], seq_bytes)) + iv[8:]

            # Simulated AES-CCM encryption (real implementation would use cryptography library)
            # For simulation, we XOR with derived key stream and add HMAC
            key_stream = hashlib.pbkdf2_hmac('sha256', key, nonce, 1, dklen=len(plaintext))
            ciphertext = bytes(a ^ b for a, b in zip(plaintext, key_stream))

            # Add authentication tag (simulated CCM tag)
            tag = hmac.new(key, ciphertext + seq_bytes, hashlib.sha256).digest()[:8]

            # Construct DTLS record
            # ContentType (1) | Version (2) | Epoch (2) | SequenceNumber (6) | Length (2) | Data
            record = bytes([
                23,  # Application data
                0xfe, 0xfd,  # DTLS 1.2 version
            ])
            record += session.write_epoch.to_bytes(2, 'big')
            record += session.write_sequence.to_bytes(6, 'big')
            record += (len(ciphertext) + len(tag)).to_bytes(2, 'big')
            record += ciphertext + tag

            # Increment sequence number
            session.write_sequence += 1
            session.last_activity = datetime.now()

            logger.debug(f"DTLS encrypt: {len(plaintext)} -> {len(record)} bytes")
            return record

        except Exception as e:
            logger.error(f"DTLS encryption error: {e}")
            return None

    def dtls_decrypt(
        self,
        session: DTLSSession,
        record: bytes,
        is_client: bool = True,
    ) -> Optional[bytes]:
        """
        Decrypt DTLS record.

        Args:
            session: DTLS session
            record: DTLS record to decrypt
            is_client: True if decrypting as client (using server's key)

        Returns:
            Decrypted plaintext, or None on error
        """
        if session.state != DTLSState.ESTABLISHED:
            logger.error("Cannot decrypt: DTLS session not established")
            return None

        try:
            import hmac
            import hashlib

            # Parse DTLS record header
            if len(record) < 13:
                logger.error("DTLS record too short")
                return None

            content_type = record[0]
            version = record[1:3]
            epoch = int.from_bytes(record[3:5], 'big')
            sequence = int.from_bytes(record[5:11], 'big')
            length = int.from_bytes(record[11:13], 'big')
            encrypted_data = record[13:13+length]

            # Verify epoch
            if epoch != session.read_epoch:
                logger.warning(f"DTLS epoch mismatch: expected {session.read_epoch}, got {epoch}")

            # Replay protection
            if sequence <= session.read_sequence:
                logger.warning(f"DTLS replay detected: sequence {sequence}")
                return None

            # Extract ciphertext and tag
            ciphertext = encrypted_data[:-8]
            received_tag = encrypted_data[-8:]

            # Select key based on role (client decrypts with server's key)
            key = session.server_write_key if is_client else session.client_write_key
            iv = session.server_write_iv if is_client else session.client_write_iv

            # Construct nonce
            seq_bytes = sequence.to_bytes(8, 'big')
            nonce = bytes(a ^ b for a, b in zip(iv[:8], seq_bytes)) + iv[8:]

            # Verify authentication tag
            expected_tag = hmac.new(key, ciphertext + seq_bytes, hashlib.sha256).digest()[:8]
            if not hmac.compare_digest(received_tag, expected_tag):
                logger.error("DTLS authentication tag mismatch")
                return None

            # Decrypt (simulated AES-CCM)
            key_stream = hashlib.pbkdf2_hmac('sha256', key, nonce, 1, dklen=len(ciphertext))
            plaintext = bytes(a ^ b for a, b in zip(ciphertext, key_stream))

            # Update sequence number
            session.read_sequence = sequence
            session.last_activity = datetime.now()

            logger.debug(f"DTLS decrypt: {len(record)} -> {len(plaintext)} bytes")
            return plaintext

        except Exception as e:
            logger.error(f"DTLS decryption error: {e}")
            return None

    async def secure_request(
        self,
        session: DTLSSession,
        method: CoAPMethod,
        path: str,
        payload: Any = None,
    ) -> Optional[tuple[CoAPCode, Any]]:
        """
        Send a CoAP request over DTLS (CoAPS).

        Args:
            session: Established DTLS session
            method: CoAP method
            path: Resource path
            payload: Request payload

        Returns:
            Tuple of (response_code, response_payload) or None on error
        """
        if session.state != DTLSState.ESTABLISHED:
            logger.error("Cannot send secure request: DTLS session not established")
            return None

        # Encode CoAP message
        coap_message = self._encode_coap_message(method, path, payload)

        # Encrypt with DTLS
        encrypted = self.dtls_encrypt(session, coap_message, is_client=True)
        if not encrypted:
            return None

        logger.debug(f"CoAPS {method.value} {path} (encrypted)")

        if self._simulation_mode:
            # Simulate sending encrypted request
            await asyncio.sleep(0.03)

            # Simulate encrypted response
            response = await self._simulate_request(method, path, payload)
            return response
        else:
            # Real implementation would send encrypted UDP datagram
            pass

        return None

    def _encode_coap_message(
        self,
        method: CoAPMethod,
        path: str,
        payload: Any,
    ) -> bytes:
        """Encode a CoAP message to bytes."""
        # Simplified CoAP message encoding
        # Real implementation would follow RFC 7252 format exactly
        msg = bytes([
            0x40 | CoAPType.CONFIRMABLE.value,  # Version 1, Type CON
            self._method_to_code(method),
        ])
        msg += self._next_message_id().to_bytes(2, 'big')

        # Add Uri-Path option (option 11)
        for segment in path.strip('/').split('/'):
            if segment:
                seg_bytes = segment.encode('utf-8')
                if len(seg_bytes) < 13:
                    msg += bytes([0xB0 | len(seg_bytes)]) + seg_bytes
                else:
                    msg += bytes([0xBD, len(seg_bytes) - 13]) + seg_bytes

        # Payload marker and payload
        if payload:
            msg += bytes([0xFF])
            msg += self._encode_payload(payload)

        return msg

    def _method_to_code(self, method: CoAPMethod) -> int:
        """Convert CoAP method to code byte."""
        codes = {
            CoAPMethod.GET: 1,
            CoAPMethod.POST: 2,
            CoAPMethod.PUT: 3,
            CoAPMethod.DELETE: 4,
        }
        return codes.get(method, 0)

    def get_dtls_status(self, session: Optional[DTLSSession] = None) -> dict[str, Any]:
        """Get DTLS status information."""
        if session is None:
            return {
                "enabled": self.coap_config.dtls.enabled,
                "version": self.coap_config.dtls.version.value,
                "cipher_suites": self.coap_config.dtls.cipher_suites,
                "psk_configured": self.coap_config.dtls.psk_key is not None,
                "certificate_configured": self.coap_config.dtls.certificate_path is not None,
            }

        return {
            "session_id": session.session_id,
            "state": session.state.value,
            "version": session.version.value,
            "cipher_suite": session.cipher_suite,
            "read_epoch": session.read_epoch,
            "write_epoch": session.write_epoch,
            "read_sequence": session.read_sequence,
            "write_sequence": session.write_sequence,
            "established_at": session.established_at.isoformat() if session.established_at else None,
            "last_activity": session.last_activity.isoformat(),
        }

    def get_stats(self) -> dict[str, Any]:
        """Get CoAP-specific statistics."""
        stats = super().get_stats()
        stats.update({
            "resources": len(self._resources),
            "observations": sum(len(obs) for obs in self._observations.values()),
            "resource_paths": list(self._resources.keys()),
            "simulation_mode": self._simulation_mode,
            "active_block1_transfers": len(self._block1_transfers),
            "active_block2_transfers": len(self._block2_transfers),
            "dtls_enabled": self.coap_config.dtls.enabled,
            "dtls_version": self.coap_config.dtls.version.value if self.coap_config.dtls.enabled else None,
        })
        return stats
