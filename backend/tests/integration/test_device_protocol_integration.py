"""
Integration Tests: Device → Protocol → Output Flow

Sprint 11 - S11.13: Integration test suite for the complete data path.

Tests:
1. Device data generation → MQTT protocol → message output
2. Device data generation → CoAP protocol → message output
3. Device data generation → HTTP REST → API output
4. Device data generation → WebSocket → real-time output
5. Multi-protocol routing
6. Edge computing integration (FogNode, Gateway)
7. Security integration (TLS, encryption)
8. Protocol translation verification

Run tests:
    pytest tests/integration/test_device_protocol_integration.py -v
"""

import asyncio
import pytest
import json
from datetime import datetime, timedelta
from typing import Any, Optional
from uuid import uuid4


# =============================================================================
# Test Fixtures
# =============================================================================

@pytest.fixture
def sample_home():
    """Create a sample home for testing."""
    from src.simulation.models import Home, Room, Device, RoomType, DeviceType

    living_room = Room(
        id="room_living",
        name="Living Room",
        room_type=RoomType.LIVING_ROOM,
        area_sqm=25.0,
    )

    bedroom = Room(
        id="room_bedroom",
        name="Bedroom",
        room_type=RoomType.BEDROOM,
        area_sqm=15.0,
    )

    thermostat = Device(
        id="thermostat_1",
        name="Smart Thermostat",
        device_type=DeviceType.THERMOSTAT,
        room_id="room_living",
    )

    motion_sensor = Device(
        id="motion_1",
        name="Motion Sensor",
        device_type=DeviceType.MOTION_SENSOR,
        room_id="room_living",
    )

    smart_light = Device(
        id="light_1",
        name="Smart Light",
        device_type=DeviceType.SMART_LIGHT,
        room_id="room_bedroom",
    )

    door_lock = Device(
        id="lock_1",
        name="Smart Door Lock",
        device_type=DeviceType.SMART_LOCK,
        room_id="room_living",
    )

    return Home(
        id="test_home",
        name="Test Home",
        rooms=[living_room, bedroom],
        devices=[thermostat, motion_sensor, smart_light, door_lock],
    )


@pytest.fixture
def mqtt_handler():
    """Create MQTT handler for testing."""
    from src.iot.protocols.mqtt_handler import MQTTHandler, MQTTConfig

    config = MQTTConfig(
        host="localhost",
        port=1883,
        client_id="integration_test_mqtt",
        extra_config={"simulation_mode": True},
    )
    return MQTTHandler(config)


@pytest.fixture
def coap_handler():
    """Create CoAP handler for testing."""
    from src.iot.protocols.coap_handler import CoAPHandler, CoAPConfig

    config = CoAPConfig(
        host="localhost",
        port=5683,
        client_id="integration_test_coap",
        block_size=256,
        extra_config={"simulation_mode": True},
    )
    return CoAPHandler(config)


@pytest.fixture
def http_handler():
    """Create HTTP handler for testing."""
    from src.iot.protocols.http_handler import HTTPRESTHandler, HTTPConfig

    config = HTTPConfig(
        host="localhost",
        port=8080,
        client_id="integration_test_http",
        extra_config={"simulation_mode": True},
    )
    return HTTPRESTHandler(config)


@pytest.fixture
def websocket_handler():
    """Create WebSocket handler for testing."""
    from src.iot.protocols.websocket_handler import WebSocketHandler, WSConfig

    config = WSConfig(
        host="localhost",
        port=8081,
        client_id="integration_test_ws",
        path="/ws",
        extra_config={"simulation_mode": True},
    )
    return WebSocketHandler(config)


# =============================================================================
# 1. Device → MQTT Protocol Tests
# =============================================================================

class TestDeviceToMQTT:
    """Test device data flow through MQTT protocol."""

    @pytest.mark.asyncio
    async def test_device_telemetry_to_mqtt(self, sample_home, mqtt_handler):
        """Test device telemetry data published via MQTT."""
        await mqtt_handler.connect()

        # Collect messages
        received_messages = []

        async def message_callback(msg):
            received_messages.append(msg)

        # Subscribe to device topics
        await mqtt_handler.subscribe("devices/+/telemetry", message_callback)

        # Publish device telemetry
        thermostat = sample_home.devices[0]
        telemetry_data = {
            "device_id": thermostat.id,
            "timestamp": datetime.now().isoformat(),
            "temperature": 22.5,
            "humidity": 45.0,
            "mode": "heating",
        }

        success = await mqtt_handler.publish_dict(
            f"devices/{thermostat.id}/telemetry",
            telemetry_data,
        )

        assert success
        await asyncio.sleep(0.1)  # Allow message processing

        # Verify message was received
        assert len(received_messages) >= 1
        assert received_messages[-1].payload["device_id"] == thermostat.id

        await mqtt_handler.disconnect()

    @pytest.mark.asyncio
    async def test_device_state_change_mqtt(self, sample_home, mqtt_handler):
        """Test device state change events via MQTT."""
        await mqtt_handler.connect()

        received_events = []

        async def event_callback(msg):
            received_events.append(msg)

        await mqtt_handler.subscribe("devices/+/state", event_callback)

        # Simulate state change
        light = sample_home.devices[2]  # Smart light
        state_change = {
            "device_id": light.id,
            "timestamp": datetime.now().isoformat(),
            "previous_state": {"on": False, "brightness": 0},
            "new_state": {"on": True, "brightness": 80},
            "trigger": "user_action",
        }

        await mqtt_handler.publish_dict(f"devices/{light.id}/state", state_change)
        await asyncio.sleep(0.1)

        assert len(received_events) >= 1
        assert received_events[-1].payload["new_state"]["on"] == True

        await mqtt_handler.disconnect()

    @pytest.mark.asyncio
    async def test_mqtt_qos_levels(self, mqtt_handler):
        """Test MQTT QoS level handling."""
        from src.iot.protocols.base_handler import QoSLevel, ProtocolMessage

        await mqtt_handler.connect()

        # Test QoS 0 (at most once)
        msg_qos0 = ProtocolMessage(
            topic="test/qos0",
            payload={"test": "qos0"},
            qos=QoSLevel.AT_MOST_ONCE,
        )
        assert await mqtt_handler.publish(msg_qos0)

        # Test QoS 1 (at least once)
        msg_qos1 = ProtocolMessage(
            topic="test/qos1",
            payload={"test": "qos1"},
            qos=QoSLevel.AT_LEAST_ONCE,
        )
        assert await mqtt_handler.publish(msg_qos1)

        # Test QoS 2 (exactly once)
        msg_qos2 = ProtocolMessage(
            topic="test/qos2",
            payload={"test": "qos2"},
            qos=QoSLevel.EXACTLY_ONCE,
        )
        assert await mqtt_handler.publish(msg_qos2)

        await mqtt_handler.disconnect()


# =============================================================================
# 2. Device → CoAP Protocol Tests
# =============================================================================

class TestDeviceToCoAP:
    """Test device data flow through CoAP protocol."""

    @pytest.mark.asyncio
    async def test_device_resource_creation(self, sample_home, coap_handler):
        """Test creating device resources via CoAP."""
        await coap_handler.connect()

        # Register device resource
        sensor = sample_home.devices[1]  # Motion sensor
        resource_path = f"/devices/{sensor.id}"

        coap_handler.register_resource(
            path=resource_path,
            content=sensor.state,
        )

        # Verify resource exists
        assert resource_path in coap_handler._resources

        await coap_handler.disconnect()

    @pytest.mark.asyncio
    async def test_coap_observe_pattern(self, coap_handler):
        """Test CoAP observe pattern for real-time updates."""
        await coap_handler.connect()

        # Create observable resource
        coap_handler.register_resource(
            path="/sensor/temperature",
            content={"value": 22.0},
            observable=True,
        )

        # Simulate observe subscription
        observed_values = []

        async def observe_callback(msg):
            observed_values.append(msg)

        # In simulation mode, this registers the callback via subscribe (CoAP observe)
        await coap_handler.subscribe("/sensor/temperature", observe_callback)

        # Simulate temperature updates
        for temp in [22.5, 23.0, 22.8]:
            coap_handler._resources["/sensor/temperature"].content = {"value": temp}
            await asyncio.sleep(0.05)

        await coap_handler.disconnect()

    @pytest.mark.asyncio
    async def test_coap_blockwise_large_payload(self, coap_handler):
        """Test CoAP blockwise transfer for large device data."""
        await coap_handler.connect()

        # Create large device data (history/logs)
        large_data = {
            "device_id": "thermostat_1",
            "history": [
                {"timestamp": f"2024-01-{i:02d}T12:00:00", "temp": 20 + i * 0.1}
                for i in range(1, 100)
            ],
        }

        # Upload using blockwise transfer
        data_bytes = json.dumps(large_data).encode()
        code, error = await coap_handler.upload_blockwise(
            path="/devices/thermostat_1/history",
            data=data_bytes,
            block_size=64,
        )

        assert error is None

        await coap_handler.disconnect()


# =============================================================================
# 3. Device → HTTP REST Tests
# =============================================================================

class TestDeviceToHTTP:
    """Test device data flow through HTTP REST protocol."""

    @pytest.mark.asyncio
    async def test_device_api_crud(self, sample_home, http_handler):
        """Test device CRUD operations via HTTP REST."""
        from src.iot.protocols.http_handler import HTTPMethod

        await http_handler.connect()

        device = sample_home.devices[3]  # Door lock

        # Create (POST) - convert DeviceState to dict for JSON serialization
        response = await http_handler.request(
            method=HTTPMethod.POST,
            path="/api/devices",
            body={
                "id": device.id,
                "name": device.name,
                "status": device.state.status.value if hasattr(device.state.status, 'value') else str(device.state.status),
            },
        )
        assert response is not None

        # Read (GET)
        response = await http_handler.request(
            method=HTTPMethod.GET,
            path=f"/api/devices/{device.id}",
        )
        assert response is not None

        # Update (PUT)
        response = await http_handler.request(
            method=HTTPMethod.PUT,
            path=f"/api/devices/{device.id}",
            body={"state": {"locked": False}},
        )
        assert response is not None

        # Delete (DELETE)
        response = await http_handler.request(
            method=HTTPMethod.DELETE,
            path=f"/api/devices/{device.id}",
        )
        assert response is not None

        await http_handler.disconnect()

    @pytest.mark.asyncio
    async def test_webhook_device_events(self, http_handler):
        """Test webhook delivery for device events."""
        await http_handler.connect()

        # Register webhook
        subscription = await http_handler.webhook_register(
            webhook_id="device_events_hook",
            url="https://example.com/webhook",
            events=["device.state_changed", "device.alert"],
            secret="test_secret_key",
        )

        assert subscription is not None
        assert subscription.id == "device_events_hook"

        # Deliver device event
        results = await http_handler.webhook_deliver(
            event_type="device.state_changed",
            payload={
                "device_id": "light_1",
                "change": {"on": True},
            },
        )

        assert len(results) == 1
        assert results[0].success

        await http_handler.disconnect()

    @pytest.mark.asyncio
    async def test_http_oauth_protected_endpoint(self, http_handler):
        """Test OAuth-protected device API endpoints."""
        from src.iot.protocols.http_handler import OAuthConfig, OAuthGrantType, HTTPMethod

        # Configure OAuth
        http_handler.http_config.oauth = OAuthConfig(
            enabled=True,
            client_id="test_client",
            client_secret="test_secret",
            token_url="https://auth.example.com/token",
            grant_type=OAuthGrantType.CLIENT_CREDENTIALS,
        )

        await http_handler.connect()

        # Authenticate
        token, error = await http_handler.oauth_authenticate()
        assert error is None
        assert token is not None

        # Access protected endpoint
        response = await http_handler.request(
            method=HTTPMethod.GET,
            path="/api/devices",
        )

        # In simulation mode, should succeed
        assert response is not None

        await http_handler.disconnect()


# =============================================================================
# 4. Device → WebSocket Tests
# =============================================================================

class TestDeviceToWebSocket:
    """Test device data flow through WebSocket protocol."""

    @pytest.mark.asyncio
    async def test_websocket_realtime_telemetry(self, sample_home, websocket_handler):
        """Test real-time device telemetry via WebSocket."""
        await websocket_handler.connect()

        received_messages = []

        async def ws_callback(msg):
            received_messages.append(msg)

        # Join device telemetry channel (using subscribe method)
        await websocket_handler.subscribe("devices/telemetry", ws_callback)

        # Send telemetry updates
        for i in range(5):
            await websocket_handler.send_json({
                "channel": "devices/telemetry",
                "device_id": "thermostat_1",
                "temperature": 22.0 + i * 0.1,
                "timestamp": datetime.now().isoformat(),
            })
            await asyncio.sleep(0.05)

        await websocket_handler.disconnect()

    @pytest.mark.asyncio
    async def test_websocket_fragmentation(self, websocket_handler):
        """Test WebSocket frame fragmentation for large messages."""
        await websocket_handler.connect()

        # Create large payload (device history)
        large_payload = json.dumps({
            "device_id": "sensor_array",
            "readings": [
                {"sensor_id": f"sensor_{i}", "value": i * 1.5}
                for i in range(1000)
            ],
        })

        # Send fragmented
        success = await websocket_handler.send_fragmented(
            data=large_payload,
            channel="devices/bulk",
            fragment_size=1024,
        )

        assert success

        # Check fragmentation stats
        stats = websocket_handler.get_fragmentation_stats()
        assert stats["messages_fragmented"] >= 1

        await websocket_handler.disconnect()

    @pytest.mark.asyncio
    async def test_websocket_binary_data(self, websocket_handler):
        """Test WebSocket binary data transmission."""
        await websocket_handler.connect()

        # Simulate binary sensor data (e.g., image from camera)
        binary_data = bytes([i % 256 for i in range(1000)])

        success = await websocket_handler.send_binary(
            data=binary_data,
            channel="devices/camera/frame",
        )

        assert success

        await websocket_handler.disconnect()


# =============================================================================
# 5. Multi-Protocol Routing Tests
# =============================================================================

class TestMultiProtocolRouting:
    """Test routing device data across multiple protocols."""

    @pytest.mark.asyncio
    async def test_device_data_multi_protocol_broadcast(
        self, sample_home, mqtt_handler, http_handler, websocket_handler
    ):
        """Test broadcasting device data to multiple protocols."""
        from src.iot.protocols.http_handler import HTTPMethod

        # Connect all handlers
        await mqtt_handler.connect()
        await http_handler.connect()
        await websocket_handler.connect()

        device_data = {
            "device_id": sample_home.devices[0].id,
            "timestamp": datetime.now().isoformat(),
            "event": "temperature_changed",
            "value": 23.5,
        }

        # Broadcast to all protocols
        mqtt_success = await mqtt_handler.publish_dict(
            "devices/events", device_data
        )

        http_response = await http_handler.request(
            method=HTTPMethod.POST,
            path="/api/events",
            body=device_data,
        )

        ws_success = await websocket_handler.send_json({
            "channel": "events",
            **device_data,
        })

        assert mqtt_success
        assert http_response is not None
        assert ws_success

        # Disconnect all
        await mqtt_handler.disconnect()
        await http_handler.disconnect()
        await websocket_handler.disconnect()


# =============================================================================
# 6. Edge Computing Integration Tests
# =============================================================================

class TestEdgeComputingIntegration:
    """Test edge computing components with device data."""

    @pytest.mark.asyncio
    async def test_fog_node_data_processing(self):
        """Test FogNode processing of device data."""
        from src.iot.edge.edge_computing import (
            EnhancedFogNodeSimulator, EdgeConfig,
            AnomalyType, AdvancedAnomalyDetector, EdgeNodeType,
        )
        from src.iot.protocols.base_handler import ProtocolMessage

        config = EdgeConfig(
            node_id="fog_node_1",
            node_type=EdgeNodeType.FOG_NODE,
            upstream_url="mqtt://broker:1883",
            anomaly_detection=True,
        )

        fog_node = EnhancedFogNodeSimulator(config)

        # Configure anomaly detection thresholds
        fog_node.set_metric_threshold("temperature", 15.0, 30.0)

        # Process normal message
        normal_msg = ProtocolMessage(
            topic="sensors/temp",
            payload={"temperature": 22.0},
            metadata={"device_id": "thermostat_1"},
        )

        processed = await fog_node.process_message(normal_msg)
        assert processed is not None
        assert "anomaly_detected" not in processed.metadata or not processed.metadata.get("anomaly_detected")

        # Process anomalous message
        anomaly_msg = ProtocolMessage(
            topic="sensors/temp",
            payload={"temperature": 45.0},  # Outside threshold
            metadata={"device_id": "thermostat_1"},
        )

        processed = await fog_node.process_message(anomaly_msg)
        assert processed is not None
        assert processed.metadata.get("anomaly_detected") == True

    @pytest.mark.asyncio
    async def test_gateway_protocol_translation(self):
        """Test Gateway protocol translation."""
        from src.iot.edge.edge_computing import (
            EnhancedGatewaySimulator, EdgeConfig,
            AdvancedProtocolTranslator, ProtocolTranslationRule, EdgeNodeType,
        )
        from src.iot.protocols.base_handler import ProtocolMessage, ProtocolType

        config = EdgeConfig(
            node_id="gateway_1",
            node_type=EdgeNodeType.GATEWAY,
            upstream_url="mqtt://broker:1883",
        )

        gateway = EnhancedGatewaySimulator(config)

        # Test Zigbee to MQTT translation
        zigbee_msg = ProtocolMessage(
            topic="zigbee/sensor/1",
            payload={"temperature": 22.5, "humidity": 45},
            metadata={"protocol": "zigbee"},
        )

        translated = await gateway.process_message(zigbee_msg)
        assert translated is not None
        assert "original_protocol" in translated.metadata

        # Check translation stats
        stats = gateway.get_translation_stats()
        assert stats["translations"] >= 1


# =============================================================================
# 7. Security Integration Tests
# =============================================================================

class TestSecurityIntegration:
    """Test security features in device-protocol integration."""

    @pytest.mark.asyncio
    async def test_tls_secured_mqtt(self, mqtt_handler):
        """Test TLS-secured MQTT connection."""
        # Configure TLS
        mqtt_handler.config.use_tls = True
        mqtt_handler.config.tls_cert_path = "/path/to/cert.pem"  # Simulated

        # Connect (simulation mode handles TLS simulation)
        await mqtt_handler.connect()

        # Verify connection state
        assert mqtt_handler.is_connected

        await mqtt_handler.disconnect()

    @pytest.mark.asyncio
    async def test_encrypted_device_payload(self):
        """Test encrypted device payloads."""
        from src.security.encryption import EncryptionEngine

        engine = EncryptionEngine()

        # Generate key
        key = await engine.generate_symmetric_key()
        assert key is not None

        # Encrypt device data
        device_data = json.dumps({
            "device_id": "secure_sensor_1",
            "reading": 42.5,
            "timestamp": datetime.now().isoformat(),
        }).encode()

        encrypted, error = await engine.encrypt(device_data, key.key_id)
        assert encrypted is not None
        assert error is None
        assert encrypted.ciphertext != device_data

        # Decrypt
        decrypted, error = await engine.decrypt(encrypted)
        assert decrypted == device_data
        assert error is None

    @pytest.mark.asyncio
    async def test_device_authentication(self):
        """Test device authentication flow."""
        from src.security.auth_manager import (
            AuthenticationManager, AuthMethod,
        )

        auth_manager = AuthenticationManager()

        # Register device credentials
        device_id = "secure_device_1"
        api_key = "test_api_key_12345"
        auth_manager.register_credentials(
            subject_id=device_id,
            api_key=api_key,
            roles=["device"],
        )

        # Authenticate device
        session, error = await auth_manager.authenticate(
            method=AuthMethod.API_KEY,
            credentials={"api_key": api_key},
        )

        assert session is not None
        assert error is None
        assert session.access_token_id is not None


# =============================================================================
# 8. Complete Pipeline Tests
# =============================================================================

class TestCompletePipeline:
    """Test complete device → protocol → output pipeline."""

    @pytest.mark.asyncio
    async def test_simulation_to_mqtt_pipeline(self, sample_home):
        """Test complete simulation → device → MQTT pipeline."""
        from src.simulation.engine import SimulationEngine, SimulationConfig
        from src.iot.protocols.mqtt_handler import MQTTHandler, MQTTConfig

        # Create simulation engine
        config = SimulationConfig(
            duration_hours=0.001,  # Very short for testing
            time_compression=3600,  # 1 hour = 1 second
            tick_interval_ms=50,
        )
        engine = SimulationEngine(sample_home, config)

        # Create MQTT handler
        mqtt_config = MQTTConfig(
            host="localhost",
            port=1883,
            client_id="pipeline_test",
            extra_config={"simulation_mode": True},
        )
        mqtt_handler = MQTTHandler(mqtt_config)
        await mqtt_handler.connect()

        # Connect simulation events to MQTT
        published_messages = []

        def event_to_mqtt(event):
            asyncio.create_task(
                mqtt_handler.publish_dict(
                    f"simulation/events/{event.source_type}",
                    event.data if isinstance(event.data, dict) else {"data": event.data},
                )
            )
            published_messages.append(event)

        engine.add_event_handler(event_to_mqtt)

        # Run simulation
        stats = await engine.run()

        # Wait for async publishes
        await asyncio.sleep(0.2)

        assert stats.state.value in ["completed", "stopped"]
        assert len(published_messages) > 0

        await mqtt_handler.disconnect()

    @pytest.mark.asyncio
    async def test_device_event_to_webhook_pipeline(self, sample_home, http_handler):
        """Test device event → webhook delivery pipeline."""
        await http_handler.connect()

        # Register webhook for device events
        await http_handler.webhook_register(
            webhook_id="device_webhook",
            url="https://example.com/events",
            events=["device.*"],
        )

        # Simulate device events
        events = [
            ("device.state_changed", {"device_id": "light_1", "on": True}),
            ("device.alert", {"device_id": "sensor_1", "type": "battery_low"}),
            ("device.offline", {"device_id": "lock_1"}),
        ]

        all_results = []
        for event_type, payload in events:
            results = await http_handler.webhook_deliver(event_type, payload)
            all_results.extend(results)

        assert len(all_results) == 3
        assert all(r.success for r in all_results)

        await http_handler.disconnect()


# =============================================================================
# Run Tests
# =============================================================================

if __name__ == "__main__":
    import sys
    sys.exit(pytest.main([__file__, "-v"]))
