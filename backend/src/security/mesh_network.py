"""
Mesh Network Simulator - Zigbee and BLE mesh network simulation.

Sprint 12 - S12.7: Build MeshNetworkSimulator (Zigbee/BLE)

Features:
- Zigbee network topology simulation
- BLE mesh network simulation
- Node discovery and pairing
- Message routing (flooding, routing tables)
- Network health monitoring
- Interference and signal strength simulation
"""

import asyncio
import math
import random
import secrets
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Optional, Callable, Coroutine
from loguru import logger


class MeshProtocol(str, Enum):
    """Supported mesh network protocols."""
    ZIGBEE = "zigbee"
    BLE_MESH = "ble_mesh"
    THREAD = "thread"
    ZWAVE = "zwave"


class NodeRole(str, Enum):
    """Mesh network node roles."""
    COORDINATOR = "coordinator"  # Network coordinator (Zigbee)
    ROUTER = "router"  # Message routing node
    END_DEVICE = "end_device"  # Leaf node
    RELAY = "relay"  # BLE Mesh relay
    FRIEND = "friend"  # BLE Mesh friend node
    LOW_POWER = "low_power"  # Low power node


class NodeState(str, Enum):
    """Node operational state."""
    OFFLINE = "offline"
    DISCOVERING = "discovering"
    PAIRING = "pairing"
    ONLINE = "online"
    ERROR = "error"
    LOW_BATTERY = "low_battery"


class MessageType(str, Enum):
    """Mesh network message types."""
    DATA = "data"
    ACK = "ack"
    BEACON = "beacon"
    ROUTE_REQUEST = "route_request"
    ROUTE_REPLY = "route_reply"
    HEARTBEAT = "heartbeat"
    COMMAND = "command"
    BROADCAST = "broadcast"


@dataclass
class Position:
    """3D position for signal simulation."""
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0

    def distance_to(self, other: "Position") -> float:
        """Calculate distance to another position."""
        return math.sqrt(
            (self.x - other.x) ** 2 +
            (self.y - other.y) ** 2 +
            (self.z - other.z) ** 2
        )


@dataclass
class MeshNode:
    """A node in the mesh network."""
    node_id: str
    protocol: MeshProtocol
    role: NodeRole = NodeRole.END_DEVICE
    state: NodeState = NodeState.OFFLINE
    address: str = ""  # Network address
    position: Position = field(default_factory=Position)

    # Network properties
    parent_id: Optional[str] = None  # For tree topology
    children: list[str] = field(default_factory=list)
    neighbors: list[str] = field(default_factory=list)

    # Device properties
    device_type: str = "generic"
    manufacturer: str = "Unknown"
    firmware_version: str = "1.0.0"

    # Radio properties
    tx_power_dbm: float = 0.0  # Transmit power
    rx_sensitivity_dbm: float = -100.0  # Receive sensitivity
    max_range_meters: float = 30.0

    # State
    battery_level: float = 100.0
    last_seen: datetime = field(default_factory=datetime.now)
    messages_sent: int = 0
    messages_received: int = 0
    messages_relayed: int = 0

    # Routing
    routing_table: dict[str, str] = field(default_factory=dict)  # dest -> next_hop

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "node_id": self.node_id,
            "protocol": self.protocol.value,
            "role": self.role.value,
            "state": self.state.value,
            "address": self.address,
            "position": {"x": self.position.x, "y": self.position.y, "z": self.position.z},
            "parent_id": self.parent_id,
            "children": self.children,
            "neighbors": self.neighbors,
            "device_type": self.device_type,
            "battery_level": self.battery_level,
            "last_seen": self.last_seen.isoformat(),
            "messages_sent": self.messages_sent,
            "messages_received": self.messages_received,
            "messages_relayed": self.messages_relayed,
        }


@dataclass
class MeshMessage:
    """Message transmitted through the mesh network."""
    message_id: str
    source_id: str
    destination_id: str
    message_type: MessageType
    payload: Any = None
    ttl: int = 10  # Time to live (hop count)
    timestamp: datetime = field(default_factory=datetime.now)
    hops: list[str] = field(default_factory=list)
    acknowledged: bool = False

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "message_id": self.message_id,
            "source_id": self.source_id,
            "destination_id": self.destination_id,
            "message_type": self.message_type.value,
            "payload": self.payload,
            "ttl": self.ttl,
            "timestamp": self.timestamp.isoformat(),
            "hops": self.hops,
            "acknowledged": self.acknowledged,
        }


@dataclass
class NetworkStats:
    """Mesh network statistics."""
    total_messages: int = 0
    delivered_messages: int = 0
    dropped_messages: int = 0
    total_hops: int = 0
    avg_latency_ms: float = 0.0
    packet_loss_rate: float = 0.0
    network_uptime: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "total_messages": self.total_messages,
            "delivered_messages": self.delivered_messages,
            "dropped_messages": self.dropped_messages,
            "delivery_rate": self.delivered_messages / max(1, self.total_messages),
            "total_hops": self.total_hops,
            "avg_hops": self.total_hops / max(1, self.delivered_messages),
            "avg_latency_ms": self.avg_latency_ms,
            "packet_loss_rate": self.packet_loss_rate,
            "network_uptime": self.network_uptime,
        }


@dataclass
class MeshNetworkConfig:
    """Mesh network simulation configuration."""
    protocol: MeshProtocol = MeshProtocol.ZIGBEE
    max_nodes: int = 100
    beacon_interval_seconds: float = 30.0
    heartbeat_interval_seconds: float = 60.0
    message_timeout_seconds: float = 5.0

    # Zigbee specific
    zigbee_channel: int = 11  # 11-26
    pan_id: str = "0x1234"

    # BLE specific
    ble_network_id: str = ""
    ble_provisioning_timeout: float = 60.0

    # Simulation parameters
    enable_interference: bool = True
    base_packet_loss: float = 0.01  # 1% base packet loss
    interference_zones: list[dict[str, Any]] = field(default_factory=list)

    # Signal propagation
    path_loss_exponent: float = 2.5  # Free space = 2, indoor = 2.5-3.5


# Type aliases for callbacks
MessageHandler = Callable[[MeshMessage, MeshNode], Coroutine[Any, Any, None]]


class MeshNetworkSimulator:
    """
    Mesh Network Simulator for Zigbee and BLE mesh networks.

    Simulates realistic mesh network behavior including:
    - Network formation and device pairing
    - Message routing with multiple strategies
    - Signal propagation and interference
    - Network health and statistics
    """

    def __init__(self, config: Optional[MeshNetworkConfig] = None):
        """
        Initialize mesh network simulator.

        Args:
            config: Network configuration
        """
        self.config = config or MeshNetworkConfig()

        # Network state
        self._nodes: dict[str, MeshNode] = {}
        self._coordinator_id: Optional[str] = None
        self._pending_messages: dict[str, MeshMessage] = {}
        self._message_history: list[MeshMessage] = []

        # Statistics
        self._stats = NetworkStats()
        self._latencies: list[float] = []

        # Callbacks
        self._message_handlers: list[MessageHandler] = []

        # Background tasks
        self._running = False
        self._beacon_task: Optional[asyncio.Task] = None
        self._heartbeat_task: Optional[asyncio.Task] = None
        self._cleanup_task: Optional[asyncio.Task] = None

        logger.info(f"MeshNetworkSimulator initialized ({self.config.protocol.value})")

    async def start(self) -> None:
        """Start the mesh network simulation."""
        self._running = True
        self._stats.network_uptime = 0

        # Start background tasks
        self._beacon_task = asyncio.create_task(self._beacon_loop())
        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())

        logger.info("MeshNetworkSimulator started")

    async def stop(self) -> None:
        """Stop the mesh network simulation."""
        self._running = False

        # Cancel tasks
        for task in [self._beacon_task, self._heartbeat_task, self._cleanup_task]:
            if task:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

        logger.info("MeshNetworkSimulator stopped")

    # ========== Node Management ==========

    async def add_node(
        self,
        node_id: str,
        role: NodeRole = NodeRole.END_DEVICE,
        position: Optional[Position] = None,
        device_type: str = "generic",
        **kwargs: Any,
    ) -> MeshNode:
        """
        Add a node to the mesh network.

        Args:
            node_id: Unique node identifier
            role: Node role in the network
            position: Physical position for signal simulation
            device_type: Type of device
            **kwargs: Additional node properties

        Returns:
            Created node
        """
        if len(self._nodes) >= self.config.max_nodes:
            raise ValueError(f"Maximum nodes ({self.config.max_nodes}) reached")

        # Generate network address
        address = self._generate_address()

        node = MeshNode(
            node_id=node_id,
            protocol=self.config.protocol,
            role=role,
            address=address,
            position=position or Position(
                x=random.uniform(0, 50),
                y=random.uniform(0, 50),
                z=random.uniform(0, 3),
            ),
            device_type=device_type,
            state=NodeState.DISCOVERING,
        )

        # Apply additional properties
        for key, value in kwargs.items():
            if hasattr(node, key):
                setattr(node, key, value)

        self._nodes[node_id] = node

        # Set coordinator if first node or coordinator role
        if role == NodeRole.COORDINATOR:
            self._coordinator_id = node_id
            node.state = NodeState.ONLINE
        elif not self._coordinator_id and role != NodeRole.END_DEVICE:
            self._coordinator_id = node_id

        # Start discovery process
        asyncio.create_task(self._discover_neighbors(node_id))

        logger.debug(f"Added mesh node: {node_id} ({role.value})")
        return node

    async def remove_node(self, node_id: str) -> bool:
        """
        Remove a node from the network.

        Args:
            node_id: Node to remove

        Returns:
            True if removed
        """
        if node_id not in self._nodes:
            return False

        node = self._nodes[node_id]

        # Remove from neighbors' lists
        for neighbor_id in node.neighbors:
            if neighbor_id in self._nodes:
                neighbor = self._nodes[neighbor_id]
                if node_id in neighbor.neighbors:
                    neighbor.neighbors.remove(node_id)

        # Remove from parent's children
        if node.parent_id and node.parent_id in self._nodes:
            parent = self._nodes[node.parent_id]
            if node_id in parent.children:
                parent.children.remove(node_id)

        # Orphan children
        for child_id in node.children:
            if child_id in self._nodes:
                self._nodes[child_id].parent_id = None
                asyncio.create_task(self._rejoin_network(child_id))

        del self._nodes[node_id]
        logger.debug(f"Removed mesh node: {node_id}")
        return True

    def get_node(self, node_id: str) -> Optional[MeshNode]:
        """Get a node by ID."""
        return self._nodes.get(node_id)

    def list_nodes(
        self,
        role: Optional[NodeRole] = None,
        state: Optional[NodeState] = None,
    ) -> list[MeshNode]:
        """List nodes with optional filters."""
        nodes = list(self._nodes.values())

        if role:
            nodes = [n for n in nodes if n.role == role]
        if state:
            nodes = [n for n in nodes if n.state == state]

        return nodes

    # ========== Message Routing ==========

    async def send_message(
        self,
        source_id: str,
        destination_id: str,
        payload: Any,
        message_type: MessageType = MessageType.DATA,
    ) -> tuple[Optional[MeshMessage], Optional[str]]:
        """
        Send a message through the mesh network.

        Args:
            source_id: Source node ID
            destination_id: Destination node ID
            payload: Message payload
            message_type: Type of message

        Returns:
            Tuple of (message, error_message)
        """
        source = self._nodes.get(source_id)
        if not source:
            return None, f"Source node not found: {source_id}"

        if source.state != NodeState.ONLINE:
            return None, f"Source node not online: {source.state.value}"

        message = MeshMessage(
            message_id=f"msg_{secrets.token_hex(8)}",
            source_id=source_id,
            destination_id=destination_id,
            message_type=message_type,
            payload=payload,
            hops=[source_id],
        )

        self._stats.total_messages += 1
        source.messages_sent += 1

        # Route the message
        delivered = await self._route_message(message)

        if delivered:
            self._stats.delivered_messages += 1
            self._stats.total_hops += len(message.hops) - 1
            return message, None
        else:
            self._stats.dropped_messages += 1
            return message, "Message delivery failed"

    async def broadcast(
        self,
        source_id: str,
        payload: Any,
        ttl: int = 3,
    ) -> tuple[int, int]:
        """
        Broadcast a message to all nodes.

        Args:
            source_id: Source node ID
            payload: Message payload
            ttl: Time to live

        Returns:
            Tuple of (nodes_reached, total_nodes)
        """
        source = self._nodes.get(source_id)
        if not source:
            return 0, 0

        message = MeshMessage(
            message_id=f"bcast_{secrets.token_hex(8)}",
            source_id=source_id,
            destination_id="broadcast",
            message_type=MessageType.BROADCAST,
            payload=payload,
            ttl=ttl,
            hops=[source_id],
        )

        # Flood to all reachable nodes
        reached = await self._flood_message(message, source_id)

        return len(reached), len(self._nodes) - 1

    async def _route_message(self, message: MeshMessage) -> bool:
        """
        Route a message to its destination.

        Uses routing table if available, falls back to flooding.
        """
        current_id = message.hops[-1]
        current = self._nodes.get(current_id)

        if not current:
            return False

        # Check if destination reached
        if current_id == message.destination_id:
            await self._deliver_message(message, current)
            return True

        # Check TTL
        if message.ttl <= 0:
            logger.debug(f"Message {message.message_id} TTL expired")
            return False

        # Check routing table
        dest = message.destination_id
        if dest in current.routing_table:
            next_hop = current.routing_table[dest]
            return await self._forward_to_node(message, next_hop)

        # Fallback to flooding among neighbors
        for neighbor_id in current.neighbors:
            if neighbor_id not in message.hops:
                if await self._forward_to_node(message, neighbor_id):
                    return True

        return False

    async def _forward_to_node(self, message: MeshMessage, next_hop: str) -> bool:
        """Forward message to next hop."""
        current_id = message.hops[-1]
        current = self._nodes.get(current_id)
        next_node = self._nodes.get(next_hop)

        if not next_node or next_node.state != NodeState.ONLINE:
            return False

        # Simulate signal propagation
        if not self._can_communicate(current, next_node):
            return False

        # Simulate packet loss
        if random.random() < self._calculate_packet_loss(current, next_node):
            logger.debug(f"Packet lost between {current_id} and {next_hop}")
            return False

        # Forward
        message.ttl -= 1
        message.hops.append(next_hop)
        next_node.messages_relayed += 1

        # Simulate latency
        latency = self._calculate_latency(current, next_node)
        await asyncio.sleep(latency / 1000)
        self._latencies.append(latency)

        return await self._route_message(message)

    async def _flood_message(
        self,
        message: MeshMessage,
        exclude_id: str,
    ) -> set[str]:
        """Flood message to all reachable nodes."""
        reached = set()
        to_process = [exclude_id]
        processed = {exclude_id}

        while to_process and message.ttl > 0:
            current_id = to_process.pop(0)
            current = self._nodes.get(current_id)

            if not current:
                continue

            for neighbor_id in current.neighbors:
                if neighbor_id in processed:
                    continue

                neighbor = self._nodes.get(neighbor_id)
                if not neighbor or neighbor.state != NodeState.ONLINE:
                    continue

                if self._can_communicate(current, neighbor):
                    reached.add(neighbor_id)
                    processed.add(neighbor_id)
                    to_process.append(neighbor_id)

                    # Deliver to this node
                    neighbor.messages_received += 1
                    for handler in self._message_handlers:
                        asyncio.create_task(handler(message, neighbor))

            message.ttl -= 1

        return reached

    async def _deliver_message(self, message: MeshMessage, node: MeshNode) -> None:
        """Deliver message to final destination."""
        node.messages_received += 1
        message.acknowledged = True

        # Call handlers
        for handler in self._message_handlers:
            await handler(message, node)

        # Record for history
        self._message_history.append(message)
        if len(self._message_history) > 1000:
            self._message_history = self._message_history[-1000:]

        logger.debug(f"Message {message.message_id} delivered to {node.node_id}")

    # ========== Network Discovery ==========

    async def _discover_neighbors(self, node_id: str) -> None:
        """Discover neighboring nodes for a new node."""
        node = self._nodes.get(node_id)
        if not node:
            return

        await asyncio.sleep(0.5)  # Discovery delay

        for other_id, other in self._nodes.items():
            if other_id == node_id:
                continue

            if self._can_communicate(node, other):
                if other_id not in node.neighbors:
                    node.neighbors.append(other_id)
                if node_id not in other.neighbors:
                    other.neighbors.append(node_id)

        # Join network
        await self._join_network(node_id)

    async def _join_network(self, node_id: str) -> None:
        """Join the mesh network."""
        node = self._nodes.get(node_id)
        if not node:
            return

        node.state = NodeState.PAIRING

        # Find best parent (for tree topology)
        best_parent = None
        best_rssi = float('-inf')

        for neighbor_id in node.neighbors:
            neighbor = self._nodes.get(neighbor_id)
            if not neighbor:
                continue

            # Prefer routers/coordinators as parents
            if neighbor.role in (NodeRole.COORDINATOR, NodeRole.ROUTER, NodeRole.RELAY):
                rssi = self._calculate_rssi(node, neighbor)
                if rssi > best_rssi:
                    best_rssi = rssi
                    best_parent = neighbor_id

        if best_parent:
            node.parent_id = best_parent
            parent = self._nodes[best_parent]
            if node_id not in parent.children:
                parent.children.append(node_id)

            # Build routing table entry to coordinator
            if self._coordinator_id:
                node.routing_table[self._coordinator_id] = best_parent

        node.state = NodeState.ONLINE
        logger.debug(f"Node {node_id} joined network (parent: {best_parent})")

    async def _rejoin_network(self, node_id: str) -> None:
        """Rejoin network after losing parent."""
        node = self._nodes.get(node_id)
        if not node:
            return

        node.state = NodeState.DISCOVERING
        await self._discover_neighbors(node_id)

    # ========== Signal Propagation ==========

    def _can_communicate(self, node1: MeshNode, node2: MeshNode) -> bool:
        """Check if two nodes can communicate."""
        distance = node1.position.distance_to(node2.position)
        max_range = min(node1.max_range_meters, node2.max_range_meters)

        if distance > max_range:
            return False

        # Check signal strength
        rssi = self._calculate_rssi(node1, node2)
        return rssi >= node2.rx_sensitivity_dbm

    def _calculate_rssi(self, sender: MeshNode, receiver: MeshNode) -> float:
        """Calculate received signal strength indicator."""
        distance = sender.position.distance_to(receiver.position)
        if distance < 0.1:
            distance = 0.1

        # Path loss model: RSSI = Tx_power - path_loss
        # Path loss = 10 * n * log10(d) + constant
        path_loss = (
            10 * self.config.path_loss_exponent * math.log10(distance) +
            20 * math.log10(2400)  # Frequency factor for 2.4GHz
        ) - 27.55

        rssi = sender.tx_power_dbm - path_loss

        # Add interference
        if self.config.enable_interference:
            rssi -= self._calculate_interference(receiver.position)

        return rssi

    def _calculate_interference(self, position: Position) -> float:
        """Calculate interference at a position."""
        interference = 0.0

        for zone in self.config.interference_zones:
            zone_pos = Position(
                zone.get("x", 0),
                zone.get("y", 0),
                zone.get("z", 0),
            )
            distance = position.distance_to(zone_pos)
            radius = zone.get("radius", 5)
            strength = zone.get("strength", 10)

            if distance < radius:
                interference += strength * (1 - distance / radius)

        return interference

    def _calculate_packet_loss(self, sender: MeshNode, receiver: MeshNode) -> float:
        """Calculate packet loss probability."""
        base_loss = self.config.base_packet_loss

        # Signal-based loss
        rssi = self._calculate_rssi(sender, receiver)
        margin = rssi - receiver.rx_sensitivity_dbm

        if margin < 0:
            return 1.0  # Below sensitivity
        elif margin < 10:
            signal_loss = 0.2 * (10 - margin) / 10
        else:
            signal_loss = 0

        # Battery-based loss (low battery = higher loss)
        battery_loss = 0
        if sender.battery_level < 20:
            battery_loss = 0.1 * (20 - sender.battery_level) / 20

        return min(1.0, base_loss + signal_loss + battery_loss)

    def _calculate_latency(self, sender: MeshNode, receiver: MeshNode) -> float:
        """Calculate message latency in milliseconds."""
        base_latency = 5.0  # Base processing latency

        # Distance-based latency
        distance = sender.position.distance_to(receiver.position)
        distance_latency = distance * 0.1  # ~0.1ms per meter

        # Random jitter
        jitter = random.uniform(-2, 2)

        return max(1, base_latency + distance_latency + jitter)

    # ========== Background Tasks ==========

    async def _beacon_loop(self) -> None:
        """Broadcast network beacons periodically."""
        while self._running:
            try:
                await asyncio.sleep(self.config.beacon_interval_seconds)

                if self._coordinator_id and self._coordinator_id in self._nodes:
                    coordinator = self._nodes[self._coordinator_id]
                    if coordinator.state == NodeState.ONLINE:
                        await self.broadcast(
                            self._coordinator_id,
                            {"type": "beacon", "pan_id": self.config.pan_id},
                            ttl=3,
                        )

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Beacon loop error: {e}")

    async def _heartbeat_loop(self) -> None:
        """Check node health periodically."""
        while self._running:
            try:
                await asyncio.sleep(self.config.heartbeat_interval_seconds)

                now = datetime.now()
                timeout = timedelta(seconds=self.config.heartbeat_interval_seconds * 3)

                for node in self._nodes.values():
                    if node.state == NodeState.ONLINE:
                        if now - node.last_seen > timeout:
                            node.state = NodeState.OFFLINE
                            logger.warning(f"Node {node.node_id} timed out")

                        # Battery drain simulation
                        node.battery_level = max(0, node.battery_level - 0.1)
                        if node.battery_level < 10:
                            node.state = NodeState.LOW_BATTERY

                self._stats.network_uptime += self.config.heartbeat_interval_seconds

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Heartbeat loop error: {e}")

    async def _cleanup_loop(self) -> None:
        """Clean up old data periodically."""
        while self._running:
            try:
                await asyncio.sleep(300)  # Every 5 minutes

                # Update average latency
                if self._latencies:
                    self._stats.avg_latency_ms = sum(self._latencies) / len(self._latencies)
                    self._latencies = self._latencies[-1000:]

                # Update packet loss rate
                if self._stats.total_messages > 0:
                    self._stats.packet_loss_rate = (
                        self._stats.dropped_messages / self._stats.total_messages
                    )

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Cleanup loop error: {e}")

    # ========== Utilities ==========

    def _generate_address(self) -> str:
        """Generate a network address."""
        if self.config.protocol == MeshProtocol.ZIGBEE:
            return f"0x{secrets.token_hex(2).upper()}"
        elif self.config.protocol == MeshProtocol.BLE_MESH:
            return f"{secrets.token_hex(2).upper()}:{secrets.token_hex(2).upper()}"
        else:
            return secrets.token_hex(4)

    def add_message_handler(self, handler: MessageHandler) -> None:
        """Add a message handler callback."""
        self._message_handlers.append(handler)

    def remove_message_handler(self, handler: MessageHandler) -> None:
        """Remove a message handler callback."""
        if handler in self._message_handlers:
            self._message_handlers.remove(handler)

    def add_interference_zone(
        self,
        x: float,
        y: float,
        z: float,
        radius: float,
        strength: float,
    ) -> None:
        """Add an interference zone."""
        self.config.interference_zones.append({
            "x": x,
            "y": y,
            "z": z,
            "radius": radius,
            "strength": strength,
        })

    def get_network_topology(self) -> dict[str, Any]:
        """Get network topology information."""
        edges = []
        for node in self._nodes.values():
            for neighbor_id in node.neighbors:
                if node.node_id < neighbor_id:  # Avoid duplicates
                    edges.append({
                        "source": node.node_id,
                        "target": neighbor_id,
                        "rssi": self._calculate_rssi(node, self._nodes[neighbor_id])
                        if neighbor_id in self._nodes else 0,
                    })

        return {
            "protocol": self.config.protocol.value,
            "coordinator": self._coordinator_id,
            "nodes": [n.to_dict() for n in self._nodes.values()],
            "edges": edges,
            "stats": self._stats.to_dict(),
        }

    def get_stats(self) -> dict[str, Any]:
        """Get network statistics."""
        online_nodes = len([n for n in self._nodes.values() if n.state == NodeState.ONLINE])
        return {
            **self._stats.to_dict(),
            "total_nodes": len(self._nodes),
            "online_nodes": online_nodes,
            "coordinator": self._coordinator_id,
            "protocol": self.config.protocol.value,
        }
