"""
Cloud Platform Adapters - AWS IoT Core, Azure IoT Hub, Google Cloud IoT.

Sprint 11 - S11.7: Create AWSIoTCoreAdapter
Sprint 11 - S11.8: Create AzureIoTHubAdapter
Sprint 11 - S11.9: Create GoogleCloudIoTAdapter

These adapters format messages according to each cloud platform's requirements
and handle platform-specific authentication and topics.
"""

import json
import hashlib
import hmac
import base64
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional
from urllib.parse import quote_plus
from loguru import logger

from ..protocols.mqtt_handler import MQTTHandler, MQTTConfig
from ..protocols.http_handler import HTTPRESTHandler, HTTPConfig
from ..protocols.base_handler import ProtocolMessage, QoSLevel


class CloudPlatform(str, Enum):
    """Supported cloud IoT platforms."""
    AWS_IOT_CORE = "aws_iot_core"
    AZURE_IOT_HUB = "azure_iot_hub"
    GOOGLE_CLOUD_IOT = "google_cloud_iot"


@dataclass
class CloudDeviceConfig:
    """Common device configuration for cloud platforms."""
    device_id: str
    device_name: str = ""
    device_type: str = "smart_device"
    metadata: dict[str, str] = field(default_factory=dict)


class AbstractCloudAdapter(ABC):
    """
    Abstract base class for cloud IoT platform adapters.

    Handles:
    - Platform-specific message formatting
    - Topic structure
    - Authentication
    - Device twin/shadow operations
    """

    def __init__(self, platform: CloudPlatform):
        """
        Initialize cloud adapter.

        Args:
            platform: Cloud platform type
        """
        self.platform = platform
        self._simulation_mode = True
        self._connected = False

    @property
    def is_connected(self) -> bool:
        return self._connected

    @abstractmethod
    async def connect(self) -> bool:
        """Connect to cloud platform."""
        pass

    @abstractmethod
    async def disconnect(self) -> None:
        """Disconnect from cloud platform."""
        pass

    @abstractmethod
    async def send_telemetry(
        self,
        device_id: str,
        data: dict[str, Any],
    ) -> bool:
        """Send telemetry data."""
        pass

    @abstractmethod
    async def update_device_state(
        self,
        device_id: str,
        state: dict[str, Any],
    ) -> bool:
        """Update device state/shadow/twin."""
        pass

    @abstractmethod
    async def receive_commands(
        self,
        device_id: str,
        callback: Any,
    ) -> bool:
        """Subscribe to device commands."""
        pass

    @abstractmethod
    def format_message(
        self,
        device_id: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        """Format message according to platform requirements."""
        pass


# =============================================================================
# AWS IoT Core Adapter
# =============================================================================

@dataclass
class AWSConfig:
    """AWS IoT Core configuration."""
    endpoint: str = ""  # xxx.iot.region.amazonaws.com
    region: str = "us-east-1"
    access_key_id: str = ""
    secret_access_key: str = ""
    # Certificate-based auth (preferred)
    certificate_path: Optional[str] = None
    private_key_path: Optional[str] = None
    root_ca_path: Optional[str] = None
    # Settings
    client_id: str = ""
    simulation_mode: bool = True


class AWSIoTCoreAdapter(AbstractCloudAdapter):
    """
    AWS IoT Core adapter.

    Features:
    - MQTT over TLS (port 8883)
    - Device Shadows
    - Rules Engine integration
    - Certificate-based authentication
    """

    def __init__(self, config: AWSConfig):
        """
        Initialize AWS IoT Core adapter.

        Args:
            config: AWS configuration
        """
        super().__init__(CloudPlatform.AWS_IOT_CORE)
        self.aws_config = config
        self._simulation_mode = config.simulation_mode
        self._mqtt_handler: Optional[MQTTHandler] = None

        # AWS IoT specific topic prefixes
        self.TELEMETRY_TOPIC = "dt/smart-hes/{device_id}/telemetry"
        self.SHADOW_UPDATE_TOPIC = "$aws/things/{device_id}/shadow/update"
        self.SHADOW_GET_TOPIC = "$aws/things/{device_id}/shadow/get"
        self.SHADOW_DELTA_TOPIC = "$aws/things/{device_id}/shadow/update/delta"
        self.COMMANDS_TOPIC = "cmd/smart-hes/{device_id}/+"

    async def connect(self) -> bool:
        """Connect to AWS IoT Core."""
        logger.info(f"Connecting to AWS IoT Core at {self.aws_config.endpoint}")

        try:
            if self._simulation_mode:
                self._connected = True
                logger.info("AWS IoT Core connected (simulation mode)")
                return True

            # Create MQTT handler with AWS IoT settings
            mqtt_config = MQTTConfig(
                host=self.aws_config.endpoint,
                port=8883,
                client_id=self.aws_config.client_id,
                use_tls=True,
                tls_cert_path=self.aws_config.certificate_path,
                tls_key_path=self.aws_config.private_key_path,
                tls_ca_path=self.aws_config.root_ca_path,
                extra_config={"simulation_mode": False},
            )

            self._mqtt_handler = MQTTHandler(mqtt_config)
            if await self._mqtt_handler.connect():
                self._connected = True
                return True
            return False

        except Exception as e:
            logger.error(f"AWS IoT Core connection error: {e}")
            return False

    async def disconnect(self) -> None:
        """Disconnect from AWS IoT Core."""
        if self._mqtt_handler:
            await self._mqtt_handler.disconnect()
        self._connected = False
        logger.info("AWS IoT Core disconnected")

    async def send_telemetry(
        self,
        device_id: str,
        data: dict[str, Any],
    ) -> bool:
        """
        Send telemetry to AWS IoT Core.

        Args:
            device_id: Thing name
            data: Telemetry data

        Returns:
            True if successful
        """
        if not self.is_connected:
            return False

        topic = self.TELEMETRY_TOPIC.format(device_id=device_id)
        message = self.format_message(device_id, data)

        if self._simulation_mode:
            logger.debug(f"AWS telemetry (sim): {topic} -> {message}")
            return True

        return await self._mqtt_handler.publish(ProtocolMessage(
            topic=topic,
            payload=message,
            qos=QoSLevel.AT_LEAST_ONCE,
        ))

    async def update_device_state(
        self,
        device_id: str,
        state: dict[str, Any],
    ) -> bool:
        """
        Update device shadow.

        Args:
            device_id: Thing name
            state: Reported state

        Returns:
            True if successful
        """
        if not self.is_connected:
            return False

        topic = self.SHADOW_UPDATE_TOPIC.format(device_id=device_id)
        payload = {
            "state": {
                "reported": state
            }
        }

        if self._simulation_mode:
            logger.debug(f"AWS shadow update (sim): {topic} -> {payload}")
            return True

        return await self._mqtt_handler.publish(ProtocolMessage(
            topic=topic,
            payload=payload,
            qos=QoSLevel.AT_LEAST_ONCE,
        ))

    async def receive_commands(
        self,
        device_id: str,
        callback: Any,
    ) -> bool:
        """Subscribe to device commands."""
        if not self.is_connected:
            return False

        topic = self.COMMANDS_TOPIC.format(device_id=device_id)

        if self._simulation_mode:
            logger.debug(f"AWS commands subscription (sim): {topic}")
            return True

        return await self._mqtt_handler.subscribe(topic, callback)

    def format_message(
        self,
        device_id: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        """Format message for AWS IoT Core."""
        return {
            "deviceId": device_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "data": payload,
            "metadata": {
                "platform": "smart-hes",
                "version": "1.0",
            }
        }


# =============================================================================
# Azure IoT Hub Adapter
# =============================================================================

@dataclass
class AzureConfig:
    """Azure IoT Hub configuration."""
    hub_name: str = ""
    connection_string: str = ""
    # SAS token auth
    sas_token: str = ""
    sas_ttl: int = 3600  # Token TTL in seconds
    # Device settings
    device_id: str = ""
    simulation_mode: bool = True


class AzureIoTHubAdapter(AbstractCloudAdapter):
    """
    Azure IoT Hub adapter.

    Features:
    - MQTT and AMQP support
    - Device Twins
    - Direct Methods
    - Cloud-to-Device messaging
    """

    def __init__(self, config: AzureConfig):
        """
        Initialize Azure IoT Hub adapter.

        Args:
            config: Azure configuration
        """
        super().__init__(CloudPlatform.AZURE_IOT_HUB)
        self.azure_config = config
        self._simulation_mode = config.simulation_mode
        self._mqtt_handler: Optional[MQTTHandler] = None

        # Azure IoT Hub topics
        self.TELEMETRY_TOPIC = "devices/{device_id}/messages/events/"
        self.TWIN_REPORTED_TOPIC = "$iothub/twin/PATCH/properties/reported/?$rid={rid}"
        self.TWIN_DESIRED_TOPIC = "$iothub/twin/PATCH/properties/desired/#"
        self.METHODS_TOPIC = "$iothub/methods/POST/#"
        self.C2D_TOPIC = "devices/{device_id}/messages/devicebound/#"

    async def connect(self) -> bool:
        """Connect to Azure IoT Hub."""
        logger.info(f"Connecting to Azure IoT Hub: {self.azure_config.hub_name}")

        try:
            if self._simulation_mode:
                self._connected = True
                logger.info("Azure IoT Hub connected (simulation mode)")
                return True

            # Parse connection string
            # Format: HostName=xxx.azure-devices.net;DeviceId=xxx;SharedAccessKey=xxx
            parts = dict(p.split("=", 1) for p in self.azure_config.connection_string.split(";") if "=" in p)

            hostname = parts.get("HostName", "")
            device_id = parts.get("DeviceId", self.azure_config.device_id)
            sas_key = parts.get("SharedAccessKey", "")

            # Generate SAS token
            sas_token = self._generate_sas_token(hostname, device_id, sas_key)

            mqtt_config = MQTTConfig(
                host=hostname,
                port=8883,
                client_id=device_id,
                username=f"{hostname}/{device_id}/?api-version=2021-04-12",
                password=sas_token,
                use_tls=True,
                extra_config={"simulation_mode": False},
            )

            self._mqtt_handler = MQTTHandler(mqtt_config)
            if await self._mqtt_handler.connect():
                self._connected = True
                return True
            return False

        except Exception as e:
            logger.error(f"Azure IoT Hub connection error: {e}")
            return False

    async def disconnect(self) -> None:
        """Disconnect from Azure IoT Hub."""
        if self._mqtt_handler:
            await self._mqtt_handler.disconnect()
        self._connected = False
        logger.info("Azure IoT Hub disconnected")

    async def send_telemetry(
        self,
        device_id: str,
        data: dict[str, Any],
    ) -> bool:
        """
        Send telemetry to Azure IoT Hub.

        Args:
            device_id: Device ID
            data: Telemetry data

        Returns:
            True if successful
        """
        if not self.is_connected:
            return False

        topic = self.TELEMETRY_TOPIC.format(device_id=device_id)
        message = self.format_message(device_id, data)

        if self._simulation_mode:
            logger.debug(f"Azure telemetry (sim): {topic} -> {message}")
            return True

        return await self._mqtt_handler.publish(ProtocolMessage(
            topic=topic,
            payload=message,
            qos=QoSLevel.AT_LEAST_ONCE,
        ))

    async def update_device_state(
        self,
        device_id: str,
        state: dict[str, Any],
    ) -> bool:
        """
        Update device twin reported properties.

        Args:
            device_id: Device ID
            state: Reported properties

        Returns:
            True if successful
        """
        if not self.is_connected:
            return False

        import uuid
        rid = str(uuid.uuid4())[:8]
        topic = self.TWIN_REPORTED_TOPIC.format(rid=rid)

        if self._simulation_mode:
            logger.debug(f"Azure twin update (sim): {topic} -> {state}")
            return True

        return await self._mqtt_handler.publish(ProtocolMessage(
            topic=topic,
            payload=state,
            qos=QoSLevel.AT_LEAST_ONCE,
        ))

    async def receive_commands(
        self,
        device_id: str,
        callback: Any,
    ) -> bool:
        """Subscribe to direct methods and C2D messages."""
        if not self.is_connected:
            return False

        if self._simulation_mode:
            logger.debug(f"Azure commands subscription (sim) for {device_id}")
            return True

        # Subscribe to direct methods
        await self._mqtt_handler.subscribe(self.METHODS_TOPIC, callback)
        # Subscribe to cloud-to-device messages
        await self._mqtt_handler.subscribe(
            self.C2D_TOPIC.format(device_id=device_id),
            callback
        )
        return True

    def format_message(
        self,
        device_id: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        """Format message for Azure IoT Hub."""
        return {
            "deviceId": device_id,
            "enqueuedTime": datetime.now(timezone.utc).isoformat(),
            "body": payload,
            "properties": {
                "source": "smart-hes",
            }
        }

    def _generate_sas_token(
        self,
        hostname: str,
        device_id: str,
        key: str,
    ) -> str:
        """Generate SAS token for Azure IoT Hub."""
        import time

        uri = f"{hostname}/devices/{device_id}"
        uri_encoded = quote_plus(uri)
        expiry = int(time.time()) + self.azure_config.sas_ttl

        sign_key = f"{uri_encoded}\n{expiry}"
        signature = base64.b64encode(
            hmac.new(
                base64.b64decode(key),
                sign_key.encode("utf-8"),
                hashlib.sha256
            ).digest()
        ).decode("utf-8")

        return f"SharedAccessSignature sr={uri_encoded}&sig={quote_plus(signature)}&se={expiry}"


# =============================================================================
# Google Cloud IoT Core Adapter
# =============================================================================

@dataclass
class GCPConfig:
    """Google Cloud IoT configuration."""
    project_id: str = ""
    region: str = "us-central1"
    registry_id: str = ""
    device_id: str = ""
    # JWT auth
    private_key_path: str = ""
    algorithm: str = "RS256"  # RS256 or ES256
    jwt_exp_minutes: int = 60
    # Simulation
    simulation_mode: bool = True


class GoogleCloudIoTAdapter(AbstractCloudAdapter):
    """
    Google Cloud IoT Core adapter.

    Note: Google Cloud IoT Core was deprecated in August 2023.
    This adapter is provided for legacy support and simulation purposes.

    Features:
    - MQTT with JWT authentication
    - Device state and configuration
    - Commands
    """

    def __init__(self, config: GCPConfig):
        """
        Initialize Google Cloud IoT adapter.

        Args:
            config: GCP configuration
        """
        super().__init__(CloudPlatform.GOOGLE_CLOUD_IOT)
        self.gcp_config = config
        self._simulation_mode = config.simulation_mode
        self._mqtt_handler: Optional[MQTTHandler] = None

        # Google Cloud IoT topics
        self.TELEMETRY_TOPIC = "/devices/{device_id}/events"
        self.STATE_TOPIC = "/devices/{device_id}/state"
        self.CONFIG_TOPIC = "/devices/{device_id}/config"
        self.COMMANDS_TOPIC = "/devices/{device_id}/commands/#"

    async def connect(self) -> bool:
        """Connect to Google Cloud IoT Core."""
        logger.info(f"Connecting to Google Cloud IoT: {self.gcp_config.project_id}")

        try:
            if self._simulation_mode:
                self._connected = True
                logger.info("Google Cloud IoT connected (simulation mode)")
                return True

            # Build client ID
            # projects/{project_id}/locations/{region}/registries/{registry_id}/devices/{device_id}
            client_id = (
                f"projects/{self.gcp_config.project_id}/"
                f"locations/{self.gcp_config.region}/"
                f"registries/{self.gcp_config.registry_id}/"
                f"devices/{self.gcp_config.device_id}"
            )

            # Generate JWT token
            jwt_token = self._create_jwt()

            mqtt_config = MQTTConfig(
                host="mqtt.googleapis.com",
                port=8883,
                client_id=client_id,
                username="unused",  # GCP uses JWT in password
                password=jwt_token,
                use_tls=True,
                extra_config={"simulation_mode": False},
            )

            self._mqtt_handler = MQTTHandler(mqtt_config)
            if await self._mqtt_handler.connect():
                self._connected = True
                return True
            return False

        except Exception as e:
            logger.error(f"Google Cloud IoT connection error: {e}")
            return False

    async def disconnect(self) -> None:
        """Disconnect from Google Cloud IoT Core."""
        if self._mqtt_handler:
            await self._mqtt_handler.disconnect()
        self._connected = False
        logger.info("Google Cloud IoT disconnected")

    async def send_telemetry(
        self,
        device_id: str,
        data: dict[str, Any],
        subfolder: str = "",
    ) -> bool:
        """
        Send telemetry to Google Cloud IoT Core.

        Args:
            device_id: Device ID
            data: Telemetry data
            subfolder: Optional subfolder for events

        Returns:
            True if successful
        """
        if not self.is_connected:
            return False

        topic = self.TELEMETRY_TOPIC.format(device_id=device_id)
        if subfolder:
            topic = f"{topic}/{subfolder}"

        message = self.format_message(device_id, data)

        if self._simulation_mode:
            logger.debug(f"GCP telemetry (sim): {topic} -> {message}")
            return True

        return await self._mqtt_handler.publish(ProtocolMessage(
            topic=topic,
            payload=message,
            qos=QoSLevel.AT_LEAST_ONCE,
        ))

    async def update_device_state(
        self,
        device_id: str,
        state: dict[str, Any],
    ) -> bool:
        """
        Update device state.

        Args:
            device_id: Device ID
            state: Device state

        Returns:
            True if successful
        """
        if not self.is_connected:
            return False

        topic = self.STATE_TOPIC.format(device_id=device_id)

        if self._simulation_mode:
            logger.debug(f"GCP state update (sim): {topic} -> {state}")
            return True

        return await self._mqtt_handler.publish(ProtocolMessage(
            topic=topic,
            payload=state,
            qos=QoSLevel.AT_LEAST_ONCE,
        ))

    async def receive_commands(
        self,
        device_id: str,
        callback: Any,
    ) -> bool:
        """Subscribe to device commands and config updates."""
        if not self.is_connected:
            return False

        if self._simulation_mode:
            logger.debug(f"GCP commands subscription (sim) for {device_id}")
            return True

        # Subscribe to commands
        await self._mqtt_handler.subscribe(
            self.COMMANDS_TOPIC.format(device_id=device_id),
            callback
        )
        # Subscribe to config updates
        await self._mqtt_handler.subscribe(
            self.CONFIG_TOPIC.format(device_id=device_id),
            callback
        )
        return True

    def format_message(
        self,
        device_id: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        """Format message for Google Cloud IoT Core."""
        return {
            "deviceId": device_id,
            "publishTime": datetime.now(timezone.utc).isoformat(),
            "data": payload,
        }

    def _create_jwt(self) -> str:
        """Create JWT token for authentication."""
        # In production, this would use PyJWT library
        # For simulation, return a placeholder
        if self._simulation_mode:
            return "simulated_jwt_token"

        try:
            import jwt
            import time

            now = int(time.time())

            payload = {
                "iat": now,
                "exp": now + (self.gcp_config.jwt_exp_minutes * 60),
                "aud": self.gcp_config.project_id,
            }

            with open(self.gcp_config.private_key_path, "r") as f:
                private_key = f.read()

            return jwt.encode(payload, private_key, algorithm=self.gcp_config.algorithm)

        except ImportError:
            logger.warning("PyJWT not available, using simulation mode")
            return "simulated_jwt_token"


# =============================================================================
# Cloud Adapter Factory
# =============================================================================

class CloudAdapterFactory:
    """Factory for creating cloud platform adapters."""

    @staticmethod
    def create(
        platform: CloudPlatform,
        config: dict[str, Any],
    ) -> AbstractCloudAdapter:
        """
        Create a cloud adapter for the specified platform.

        Args:
            platform: Target cloud platform
            config: Platform-specific configuration

        Returns:
            Cloud adapter instance
        """
        if platform == CloudPlatform.AWS_IOT_CORE:
            return AWSIoTCoreAdapter(AWSConfig(**config))
        elif platform == CloudPlatform.AZURE_IOT_HUB:
            return AzureIoTHubAdapter(AzureConfig(**config))
        elif platform == CloudPlatform.GOOGLE_CLOUD_IOT:
            return GoogleCloudIoTAdapter(GCPConfig(**config))
        else:
            raise ValueError(f"Unknown cloud platform: {platform}")
