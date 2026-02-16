"""
Test Suite for Critical Code Fixes

This module provides tests for:
1. CoAP Blockwise Transfers (RFC 7959)
2. HTTP OAuth 2.0 Flow Execution
3. Monitoring API Real Data Connection

Run individual tests:
    pytest tests/test_critical_fixes.py::test_coap_blockwise -v
    pytest tests/test_critical_fixes.py::test_http_oauth -v
    pytest tests/test_critical_fixes.py::test_monitoring_events -v

Run all tests:
    pytest tests/test_critical_fixes.py -v
"""

import asyncio
import pytest
from datetime import datetime


# =============================================================================
# 1. CoAP Blockwise Transfer Tests (RFC 7959)
# =============================================================================

class TestCoAPBlockwise:
    """Test CoAP blockwise transfer implementation."""

    @pytest.fixture
    def coap_handler(self):
        """Create CoAP handler for testing."""
        from src.iot.protocols.coap_handler import CoAPHandler, CoAPConfig

        config = CoAPConfig(
            host="localhost",
            port=5683,
            client_id="test_client",
            block_size=64,  # Small block for testing
            extra_config={"simulation_mode": True},
        )
        return CoAPHandler(config)

    @pytest.mark.asyncio
    async def test_blockwise_state_encoding(self):
        """Test block option encoding/decoding (RFC 7959 Section 2.2)."""
        from src.iot.protocols.coap_handler import BlockwiseState

        # Test SZX to size conversion
        assert BlockwiseState.szx_to_size(0) == 16   # 2^4
        assert BlockwiseState.szx_to_size(2) == 64   # 2^6
        assert BlockwiseState.szx_to_size(6) == 1024 # 2^10

        # Test size to SZX conversion
        assert BlockwiseState.size_to_szx(16) == 0
        assert BlockwiseState.size_to_szx(64) == 2
        assert BlockwiseState.size_to_szx(512) == 5

        # Test encode/decode roundtrip
        state = BlockwiseState(
            resource_path="/test",
            is_upload=True,
            block_size=64,
            current_num=5,
        )

        encoded = state.encode_block_option(more=True)  # Block 5, more=1, SZX=2
        num, more, size = BlockwiseState.decode_block_option(encoded)

        assert num == 5
        assert more == True
        assert size == 64

    @pytest.mark.asyncio
    async def test_block1_upload(self, coap_handler):
        """Test Block1 (upload) blockwise transfer."""
        await coap_handler.connect()

        # Create test data larger than block size
        test_data = b"X" * 256  # 256 bytes, will be 4 blocks of 64 bytes

        # Upload using blockwise transfer
        code, error = await coap_handler.upload_blockwise(
            path="/devices/sensor1/config",
            data=test_data,
            block_size=64,
        )

        assert error is None
        assert code is not None
        assert code.value == (2, 4)  # 2.04 Changed

        # Verify resource was created
        assert "/devices/sensor1/config" in coap_handler._resources

        await coap_handler.disconnect()

    @pytest.mark.asyncio
    async def test_block2_download(self, coap_handler):
        """Test Block2 (download) blockwise transfer."""
        await coap_handler.connect()

        # First, create a resource with large content
        test_data = {"values": list(range(100))}
        coap_handler.register_resource(
            path="/devices/sensor1/data",
            content=test_data,
        )

        # Download using blockwise transfer
        data, error = await coap_handler.download_blockwise(
            path="/devices/sensor1/data",
            block_size=64,
        )

        assert error is None
        assert data is not None
        assert len(data) > 0

        await coap_handler.disconnect()

    @pytest.mark.asyncio
    async def test_block1_server_handler(self, coap_handler):
        """Test server-side Block1 handling."""
        from src.iot.protocols.coap_handler import BlockwiseState, CoAPCode

        await coap_handler.connect()

        # Simulate receiving blocks from a client
        test_data = b"Hello, World! This is test data."
        block_size = 16

        for i in range((len(test_data) + block_size - 1) // block_size):
            start = i * block_size
            end = min(start + block_size, len(test_data))
            block_data = test_data[start:end]
            more = end < len(test_data)

            state = BlockwiseState(
                resource_path="/upload",
                is_upload=True,
                block_size=block_size,
                current_num=i,
            )
            block_option = state.encode_block_option(more)

            code, echo = await coap_handler.handle_block1_request(
                path="/upload",
                block_option=block_option,
                block_data=block_data,
                client_id="test_client",
            )

            if more:
                assert code == CoAPCode.CONTENT  # Continue
            else:
                assert code == CoAPCode.CHANGED  # Completed

        # Verify complete resource was stored
        assert "/upload" in coap_handler._resources
        assert coap_handler._resources["/upload"].content == test_data

        await coap_handler.disconnect()


# =============================================================================
# 2. HTTP OAuth 2.0 Flow Tests
# =============================================================================

class TestHTTPOAuth:
    """Test HTTP OAuth 2.0 flow implementation."""

    @pytest.fixture
    def http_handler(self):
        """Create HTTP handler with OAuth config for testing."""
        from src.iot.protocols.http_handler import (
            HTTPRESTHandler, HTTPConfig, OAuthConfig, OAuthGrantType
        )

        oauth_config = OAuthConfig(
            enabled=True,
            client_id="test_client_id",
            client_secret="test_client_secret",
            authorization_url="https://auth.example.com/authorize",
            token_url="https://auth.example.com/token",
            redirect_uri="http://localhost:8080/callback",
            scope="read write",
            grant_type=OAuthGrantType.CLIENT_CREDENTIALS,
        )

        config = HTTPConfig(
            host="localhost",
            port=8080,
            client_id="test_client",
            auth_type="oauth2",
            oauth=oauth_config,
            extra_config={"simulation_mode": True},
        )
        return HTTPRESTHandler(config)

    @pytest.mark.asyncio
    async def test_client_credentials_flow(self, http_handler):
        """Test OAuth 2.0 Client Credentials flow."""
        await http_handler.connect()

        # Execute client credentials flow
        token, error = await http_handler.oauth_authenticate()

        assert error is None
        assert token is not None
        assert token.access_token.startswith("sim_access_")
        assert token.token_type == "Bearer"
        assert token.expires_in == 3600

        # Verify token was stored
        assert http_handler.oauth_is_token_valid()
        assert http_handler.http_config.auth_type == "bearer"

        await http_handler.disconnect()

    @pytest.mark.asyncio
    async def test_authorization_code_url_generation(self, http_handler):
        """Test OAuth 2.0 Authorization Code URL generation."""
        await http_handler.connect()

        # Generate authorization URL
        auth_url, state = http_handler.oauth_get_authorization_url()

        assert "https://auth.example.com/authorize" in auth_url
        assert "client_id=test_client_id" in auth_url
        assert "response_type=code" in auth_url
        assert f"state={state}" in auth_url
        assert "code_challenge=" in auth_url  # PKCE
        assert "code_challenge_method=S256" in auth_url

        # Verify PKCE state was stored
        assert hasattr(http_handler, "_oauth_pkce")
        assert http_handler._oauth_pkce["state"] == state

        await http_handler.disconnect()

    @pytest.mark.asyncio
    async def test_authorization_code_exchange(self, http_handler):
        """Test OAuth 2.0 Authorization Code exchange."""
        await http_handler.connect()

        # First generate URL to set up PKCE state
        _, state = http_handler.oauth_get_authorization_url()

        # Simulate code exchange
        token, error = await http_handler.oauth_exchange_code(
            code="test_auth_code",
            state=state,
        )

        assert error is None
        assert token is not None
        assert token.access_token.startswith("sim_authcode_")
        assert token.refresh_token.startswith("sim_refresh_")

        await http_handler.disconnect()

    @pytest.mark.asyncio
    async def test_refresh_token_flow(self, http_handler):
        """Test OAuth 2.0 Refresh Token flow."""
        await http_handler.connect()

        # First get initial token
        _, _ = await http_handler.oauth_authenticate()

        # Manually set refresh token for testing
        http_handler.http_config.oauth.refresh_token = "test_refresh_token"
        http_handler.http_config.oauth.grant_type = "refresh_token"

        # Refresh the token
        token, error = await http_handler._oauth_refresh_token()

        assert error is None
        assert token is not None
        assert token.access_token.startswith("sim_refreshed_")

        await http_handler.disconnect()

    @pytest.mark.asyncio
    async def test_token_validity_check(self, http_handler):
        """Test OAuth token validity checking."""
        from datetime import timedelta

        await http_handler.connect()
        oauth = http_handler.http_config.oauth

        # No token - should be invalid
        assert not http_handler.oauth_is_token_valid()

        # Get token
        await http_handler.oauth_authenticate()

        # Token should be valid
        assert http_handler.oauth_is_token_valid()

        # Simulate expired token
        oauth.token_expires_at = datetime.now() - timedelta(hours=1)
        assert not http_handler.oauth_is_token_valid()

        await http_handler.disconnect()

    @pytest.mark.asyncio
    async def test_oauth_status(self, http_handler):
        """Test OAuth status reporting."""
        await http_handler.connect()

        # Get initial status
        status = http_handler.get_oauth_status()
        assert status["enabled"] == True
        assert status["grant_type"] == "client_credentials"
        assert status["has_access_token"] == False

        # Authenticate
        await http_handler.oauth_authenticate()

        # Check updated status
        status = http_handler.get_oauth_status()
        assert status["has_access_token"] == True
        assert status["token_valid"] == True

        await http_handler.disconnect()


# =============================================================================
# 3. Monitoring API Real Data Connection Tests
# =============================================================================

class TestMonitoringRealData:
    """Test monitoring API real data connections."""

    @pytest.mark.asyncio
    async def test_security_engine_registration(self):
        """Test security engine can be registered with monitoring."""
        from src.api.monitoring import register_security_engine, get_security_engine
        from src.security import SecurityPrivacyEngine

        # Create and register engine
        engine = SecurityPrivacyEngine()
        await engine.start()
        register_security_engine(engine)

        # Verify registration
        assert get_security_engine() == engine
        assert get_security_engine().is_running

        await engine.stop()

    @pytest.mark.asyncio
    async def test_mesh_simulator_registration(self):
        """Test mesh simulator can be registered with monitoring."""
        from src.api.monitoring import register_mesh_simulator, get_mesh_simulator
        from src.security import MeshNetworkSimulator

        # Create and register simulator
        simulator = MeshNetworkSimulator()
        await simulator.start()
        register_mesh_simulator(simulator)

        # Verify registration
        assert get_mesh_simulator() == simulator
        assert get_mesh_simulator()._running

        await simulator.stop()

    @pytest.mark.asyncio
    async def test_security_events_from_engine(self):
        """Test security events are retrieved from real engine."""
        from src.api.monitoring import register_security_engine, get_security_events
        from src.security import SecurityPrivacyEngine
        from src.security.engine import SecurityEvent as EngineSecurityEvent, SecurityEventType, SecurityLevel

        # Create and register engine
        engine = SecurityPrivacyEngine()
        await engine.start()
        register_security_engine(engine)

        # Log some test events
        await engine.log_event(EngineSecurityEvent(
            event_type=SecurityEventType.AUTH_SUCCESS,
            source_id="device_1",
            source_type="device",
            severity=SecurityLevel.LOW,
            success=True,
            details={"message": "Test auth success"},
        ))

        await engine.log_event(EngineSecurityEvent(
            event_type=SecurityEventType.TLS_HANDSHAKE_SUCCESS,
            source_id="device_2",
            source_type="device",
            severity=SecurityLevel.LOW,
            success=True,
            details={"message": "Test TLS handshake"},
        ))

        # Retrieve events via API
        events = await get_security_events(limit=10)

        assert len(events) >= 2
        event_types = [e.type for e in events]
        assert "auth_success" in event_types
        assert "tls_handshake_success" in event_types

        await engine.stop()

    @pytest.mark.asyncio
    async def test_mesh_nodes_from_simulator(self):
        """Test mesh nodes are retrieved from real simulator."""
        from src.api.monitoring import register_mesh_simulator, get_mesh_network
        from src.security import MeshNetworkSimulator
        from src.security.mesh_network import NodeRole

        # Create and register simulator
        simulator = MeshNetworkSimulator()
        await simulator.start()
        register_mesh_simulator(simulator)

        # Add some test nodes
        await simulator.add_node("coordinator", role=NodeRole.COORDINATOR)
        await simulator.add_node("router1", role=NodeRole.ROUTER)
        await simulator.add_node("device1", role=NodeRole.END_DEVICE)

        # Give time for discovery
        await asyncio.sleep(0.5)

        # Retrieve nodes via API
        nodes = await get_mesh_network()

        assert len(nodes) >= 3
        node_ids = [n.id for n in nodes]
        assert "coordinator" in node_ids
        assert "router1" in node_ids
        assert "device1" in node_ids

        await simulator.stop()

    @pytest.mark.asyncio
    async def test_security_stats_from_engine(self):
        """Test security stats are retrieved from real engine."""
        from src.api.monitoring import register_security_engine, get_security_stats
        from src.security import SecurityPrivacyEngine
        from src.security.engine import SecurityEvent as EngineSecurityEvent, SecurityEventType, SecurityLevel

        # Create and register engine
        engine = SecurityPrivacyEngine()
        await engine.start()
        register_security_engine(engine)

        # Generate some events to update stats
        for _ in range(5):
            await engine.log_event(EngineSecurityEvent(
                event_type=SecurityEventType.AUTH_SUCCESS,
                source_id="test",
                source_type="device",
            ))

        for _ in range(2):
            await engine.log_event(EngineSecurityEvent(
                event_type=SecurityEventType.AUTH_FAILURE,
                source_id="test",
                source_type="device",
                success=False,
            ))

        # Get stats via API
        stats = await get_security_stats()

        assert stats.auth_success == 5
        assert stats.auth_failure == 2

        await engine.stop()


# =============================================================================
# Run Tests Individually
# =============================================================================

if __name__ == "__main__":
    # Quick test runner
    import sys

    print("=" * 60)
    print("Critical Code Fixes - Test Suite")
    print("=" * 60)
    print()
    print("Run specific tests:")
    print("  pytest tests/test_critical_fixes.py::TestCoAPBlockwise -v")
    print("  pytest tests/test_critical_fixes.py::TestHTTPOAuth -v")
    print("  pytest tests/test_critical_fixes.py::TestMonitoringRealData -v")
    print()
    print("Run all tests:")
    print("  pytest tests/test_critical_fixes.py -v")
    print()

    # Run pytest
    sys.exit(pytest.main([__file__, "-v"]))
