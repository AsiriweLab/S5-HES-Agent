"""IoT Communication Layer - Protocol handlers and cloud integration."""

from .protocols import (
    AbstractProtocolHandler,
    ProtocolType,
    ProtocolConfig,
    ProtocolMessage,
    ProtocolStats,
    ConnectionState,
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

from .cloud import (
    CloudPlatform,
    AbstractCloudAdapter,
    AWSIoTCoreAdapter,
    AzureIoTHubAdapter,
    GoogleCloudIoTAdapter,
    CloudAdapterFactory,
)

from .edge import (
    EdgeNodeType,
    EdgeConfig,
    FogNodeSimulator,
    GatewaySimulator,
    EdgeComputingManager,
)

__all__ = [
    # Protocols
    "AbstractProtocolHandler",
    "ProtocolType",
    "ProtocolConfig",
    "ProtocolMessage",
    "ProtocolStats",
    "ConnectionState",
    "QoSLevel",
    "MQTTHandler",
    "MQTTConfig",
    "CoAPHandler",
    "CoAPConfig",
    "HTTPRESTHandler",
    "HTTPConfig",
    "WebSocketHandler",
    "WSConfig",
    # Cloud
    "CloudPlatform",
    "AbstractCloudAdapter",
    "AWSIoTCoreAdapter",
    "AzureIoTHubAdapter",
    "GoogleCloudIoTAdapter",
    "CloudAdapterFactory",
    # Edge
    "EdgeNodeType",
    "EdgeConfig",
    "FogNodeSimulator",
    "GatewaySimulator",
    "EdgeComputingManager",
]
