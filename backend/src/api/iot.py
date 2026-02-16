"""
IoT Communication Layer API - Protocol management and testing endpoints.

Provides API for:
- Protocol configuration
- Connection testing
- Message sending/receiving
- Edge node management
"""

from datetime import datetime
from enum import Enum
from typing import Any, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from loguru import logger

from src.core.config import settings

from ..iot.protocols import (
    ProtocolType,
    ProtocolMessage,
    QoSLevel,
    MQTTHandler,
    MQTTConfig,
    CoAPHandler,
    CoAPConfig,
    HTTPRESTHandler,
    HTTPConfig,
    WebSocketHandler,
    WSConfig,
)
from ..iot.cloud import (
    CloudPlatform,
    CloudAdapterFactory,
)
from ..iot.edge import (
    EdgeConfig,
    EdgeNodeType,
    AggregationType,
    FogNodeSimulator,
    GatewaySimulator,
    EdgeComputingManager,
)


router = APIRouter(prefix="/iot", tags=["IoT Communication"])

# Global instances for demonstration
_protocol_handlers: dict[str, Any] = {}
_edge_manager = EdgeComputingManager()


# =============================================================================
# Request/Response Models
# =============================================================================

class ProtocolConfigRequest(BaseModel):
    """Protocol configuration request."""
    protocol_type: ProtocolType
    host: str = "localhost"
    port: int
    client_id: str = ""
    use_tls: bool = False
    username: Optional[str] = None
    password: Optional[str] = None
    # MQTT specific
    qos: int = 1
    clean_session: bool = True
    keep_alive: int = 60
    # HTTP specific
    base_url: Optional[str] = None
    auth_type: str = "none"
    api_key: Optional[str] = None
    bearer_token: Optional[str] = None
    # WebSocket specific
    path: str = "/ws"
    ping_interval: float = 30.0
    # General
    simulation_mode: bool = True


class MessageRequest(BaseModel):
    """Message send request."""
    handler_id: str
    topic: str
    payload: dict[str, Any]
    qos: int = 1
    retain: bool = False


class CloudConfigRequest(BaseModel):
    """Cloud platform configuration request."""
    platform: CloudPlatform
    device_id: str
    # Platform-specific settings
    endpoint: Optional[str] = None
    region: Optional[str] = None
    hub_name: Optional[str] = None
    project_id: Optional[str] = None
    registry_id: Optional[str] = None
    simulation_mode: bool = True


class EdgeNodeRequest(BaseModel):
    """Edge node configuration request."""
    node_id: str
    node_name: str = ""
    node_type: str = "fog_node"
    aggregation_window: float = 60.0
    aggregation_type: str = "average"
    buffer_size: int = 1000


class ProtocolStatsResponse(BaseModel):
    """Protocol statistics response."""
    handler_id: str
    protocol: str
    state: str
    messages_sent: int
    messages_received: int
    errors: int
    connected_since: Optional[str] = None


# =============================================================================
# Protocol Endpoints
# =============================================================================

@router.post("/protocols/create")
async def create_protocol_handler(config: ProtocolConfigRequest) -> dict[str, Any]:
    """
    Create and initialize a protocol handler.

    Args:
        config: Protocol configuration

    Returns:
        Handler ID and status
    """
    try:
        handler_id = f"{config.protocol_type.value}-{datetime.now().strftime('%Y%m%d%H%M%S')}"

        if config.protocol_type == ProtocolType.MQTT:
            mqtt_config = MQTTConfig(
                host=config.host,
                port=config.port,
                client_id=config.client_id or handler_id,
                use_tls=config.use_tls,
                username=config.username,
                password=config.password,
                clean_session=config.clean_session,
                keep_alive=config.keep_alive,
                extra_config={"simulation_mode": config.simulation_mode},
            )
            handler = MQTTHandler(mqtt_config)

        elif config.protocol_type == ProtocolType.COAP:
            coap_config = CoAPConfig(
                host=config.host,
                port=config.port,
                extra_config={"simulation_mode": config.simulation_mode},
            )
            handler = CoAPHandler(coap_config)

        elif config.protocol_type == ProtocolType.HTTP:
            http_config = HTTPConfig(
                host=config.host,
                port=config.port,
                base_url=config.base_url or f"http://{config.host}:{config.port}",
                auth_type=config.auth_type,
                api_key=config.api_key,
                bearer_token=config.bearer_token,
                extra_config={"simulation_mode": config.simulation_mode},
            )
            handler = HTTPRESTHandler(http_config)

        elif config.protocol_type == ProtocolType.WEBSOCKET:
            ws_config = WSConfig(
                host=config.host,
                port=config.port,
                path=config.path,
                ping_interval=config.ping_interval,
                use_tls=config.use_tls,
                extra_config={"simulation_mode": config.simulation_mode},
            )
            handler = WebSocketHandler(ws_config)

        else:
            raise HTTPException(status_code=400, detail=f"Unsupported protocol: {config.protocol_type}")

        # Connect
        connected = await handler.connect()

        _protocol_handlers[handler_id] = handler

        return {
            "handler_id": handler_id,
            "protocol": config.protocol_type.value,
            "connected": connected,
            "host": config.host,
            "port": config.port,
            "simulation_mode": config.simulation_mode,
        }

    except Exception as e:
        logger.error(f"Failed to create protocol handler: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/protocols/{handler_id}/send")
async def send_message(handler_id: str, request: MessageRequest) -> dict[str, Any]:
    """
    Send a message through a protocol handler.

    Args:
        handler_id: Handler identifier
        request: Message details

    Returns:
        Send status
    """
    if handler_id not in _protocol_handlers:
        raise HTTPException(status_code=404, detail=f"Handler not found: {handler_id}")

    handler = _protocol_handlers[handler_id]

    try:
        message = ProtocolMessage(
            topic=request.topic,
            payload=request.payload,
            qos=QoSLevel(request.qos),
            retain=request.retain,
        )

        success = await handler.publish(message)

        return {
            "success": success,
            "message_id": message.id,
            "topic": request.topic,
            "handler_id": handler_id,
        }

    except Exception as e:
        logger.error(f"Failed to send message: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/protocols/{handler_id}/stats")
async def get_protocol_stats(handler_id: str) -> dict[str, Any]:
    """
    Get protocol handler statistics.

    Args:
        handler_id: Handler identifier

    Returns:
        Handler statistics
    """
    if handler_id not in _protocol_handlers:
        raise HTTPException(status_code=404, detail=f"Handler not found: {handler_id}")

    handler = _protocol_handlers[handler_id]
    return handler.get_stats()


@router.delete("/protocols/{handler_id}")
async def delete_protocol_handler(handler_id: str) -> dict[str, Any]:
    """
    Disconnect and remove a protocol handler.

    Args:
        handler_id: Handler identifier

    Returns:
        Deletion status
    """
    if handler_id not in _protocol_handlers:
        raise HTTPException(status_code=404, detail=f"Handler not found: {handler_id}")

    handler = _protocol_handlers[handler_id]
    await handler.disconnect()
    del _protocol_handlers[handler_id]

    return {"deleted": True, "handler_id": handler_id}


@router.get("/protocols")
async def list_protocol_handlers() -> list[dict[str, Any]]:
    """
    List all active protocol handlers.

    Returns:
        List of handler summaries
    """
    return [
        {
            "handler_id": handler_id,
            "protocol": handler.protocol_type.value,
            "state": handler.state.value,
            "is_connected": handler.is_connected,
        }
        for handler_id, handler in _protocol_handlers.items()
    ]


# =============================================================================
# Cloud Platform Endpoints
# =============================================================================

@router.post("/cloud/test")
async def test_cloud_connection(config: CloudConfigRequest) -> dict[str, Any]:
    """
    Test connection to a cloud IoT platform.

    Args:
        config: Cloud platform configuration

    Returns:
        Connection test results

    Note:
        This endpoint is only available in development environment.
        It sends test telemetry which should not be used in production.
    """
    # INTEGRITY GATE: Only allow in development environment
    # This endpoint emits test telemetry ({"test": True, ...}) which violates
    # integrity constraints if used in production/evaluation contexts.
    if settings.environment != "development":
        raise HTTPException(
            status_code=403,
            detail="Test endpoint disabled. Cloud connection testing is only available in development environment.",
        )

    try:
        adapter_config = {
            "simulation_mode": config.simulation_mode,
        }

        if config.platform == CloudPlatform.AWS_IOT_CORE:
            adapter_config["endpoint"] = config.endpoint or ""
            adapter_config["region"] = config.region or "us-east-1"

        elif config.platform == CloudPlatform.AZURE_IOT_HUB:
            adapter_config["hub_name"] = config.hub_name or ""

        elif config.platform == CloudPlatform.GOOGLE_CLOUD_IOT:
            adapter_config["project_id"] = config.project_id or ""
            adapter_config["registry_id"] = config.registry_id or ""
            adapter_config["device_id"] = config.device_id

        adapter = CloudAdapterFactory.create(config.platform, adapter_config)
        connected = await adapter.connect()

        # Send test telemetry
        if connected:
            await adapter.send_telemetry(
                config.device_id,
                {"test": True, "timestamp": datetime.now().isoformat()}
            )

        await adapter.disconnect()

        return {
            "platform": config.platform.value,
            "connected": connected,
            "device_id": config.device_id,
            "simulation_mode": config.simulation_mode,
        }

    except Exception as e:
        logger.error(f"Cloud connection test failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# Edge Computing Endpoints
# =============================================================================

@router.post("/edge/nodes")
async def create_edge_node(config: EdgeNodeRequest) -> dict[str, Any]:
    """
    Create an edge computing node (fog node or gateway).

    Args:
        config: Edge node configuration

    Returns:
        Node creation status
    """
    try:
        edge_config = EdgeConfig(
            node_id=config.node_id,
            node_name=config.node_name or config.node_id,
            node_type=EdgeNodeType(config.node_type),
            aggregation_window=config.aggregation_window,
            aggregation_type=AggregationType(config.aggregation_type),
            buffer_size=config.buffer_size,
        )

        if config.node_type == "fog_node":
            node = await _edge_manager.create_fog_node(edge_config)
        else:
            node = await _edge_manager.create_gateway(edge_config)

        return {
            "node_id": config.node_id,
            "node_type": config.node_type,
            "is_running": node.is_running,
        }

    except Exception as e:
        logger.error(f"Failed to create edge node: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/edge/nodes/{node_id}/stats")
async def get_edge_node_stats(node_id: str) -> dict[str, Any]:
    """
    Get statistics for an edge node.

    Args:
        node_id: Node identifier

    Returns:
        Node statistics
    """
    node = _edge_manager.get_fog_node(node_id) or _edge_manager.get_gateway(node_id)

    if not node:
        raise HTTPException(status_code=404, detail=f"Edge node not found: {node_id}")

    return node.get_stats()


@router.get("/edge/stats")
async def get_all_edge_stats() -> dict[str, Any]:
    """
    Get statistics for all edge nodes.

    Returns:
        Combined statistics
    """
    return _edge_manager.get_all_stats()


@router.get("/protocols/supported")
async def get_supported_protocols() -> dict[str, Any]:
    """
    Get list of supported protocols and their features.

    Returns:
        Protocol information
    """
    return {
        "protocols": [
            {
                "id": "mqtt",
                "name": "MQTT",
                "description": "Message Queuing Telemetry Transport",
                "default_port": 1883,
                "tls_port": 8883,
                "features": ["QoS 0/1/2", "Retain", "LWT", "Wildcards"],
                "cloud_support": ["AWS IoT Core", "Azure IoT Hub", "Google Cloud IoT"],
            },
            {
                "id": "coap",
                "name": "CoAP",
                "description": "Constrained Application Protocol",
                "default_port": 5683,
                "tls_port": 5684,
                "features": ["Observe", "Blockwise", "Confirmable/Non-confirmable"],
                "cloud_support": ["Generic"],
            },
            {
                "id": "http",
                "name": "HTTP/REST",
                "description": "REST API Communication",
                "default_port": 80,
                "tls_port": 443,
                "features": ["GET/POST/PUT/DELETE", "Basic/Bearer/API Key Auth"],
                "cloud_support": ["All platforms"],
            },
            {
                "id": "websocket",
                "name": "WebSocket",
                "description": "Full-duplex Communication",
                "default_port": 8080,
                "tls_port": 8443,
                "features": ["Bidirectional", "Real-time", "Channels/Rooms"],
                "cloud_support": ["Dashboard"],
            },
        ],
        "cloud_platforms": [
            {"id": "aws", "name": "AWS IoT Core"},
            {"id": "azure", "name": "Azure IoT Hub"},
            {"id": "gcp", "name": "Google Cloud IoT (Deprecated)"},
        ],
    }
