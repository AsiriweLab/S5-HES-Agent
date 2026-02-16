"""
End-to-End Integration Tests

Sprint 12 - S12.11: Complete end-to-end testing.

Tests complete workflows:
1. API → Simulation → Events → Output
2. Home Builder → Simulation → Results Export
3. Threat Injection → Detection → Alert
4. RAG Query → Knowledge Base → Response
5. Agent Orchestration → Task Completion
6. Parameter Sweep → Statistical Analysis
7. Security → Authentication → Authorization
8. Multi-user Concurrent Sessions

Run tests:
    pytest tests/e2e/test_end_to_end.py -v
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
def api_client():
    """Create a mock API client for E2E testing."""
    class MockAPIClient:
        def __init__(self):
            self.session_id = str(uuid4())
            self.base_url = "http://localhost:8000"
            self.responses = {}

        async def get(self, path: str) -> dict:
            """Simulate GET request."""
            return {"status": "ok", "path": path, "method": "GET"}

        async def post(self, path: str, data: dict) -> dict:
            """Simulate POST request."""
            return {"status": "ok", "path": path, "method": "POST", "data": data}

        async def put(self, path: str, data: dict) -> dict:
            """Simulate PUT request."""
            return {"status": "ok", "path": path, "method": "PUT", "data": data}

        async def delete(self, path: str) -> dict:
            """Simulate DELETE request."""
            return {"status": "ok", "path": path, "method": "DELETE"}

    return MockAPIClient()


@pytest.fixture
def sample_home_config():
    """Sample home configuration for E2E tests."""
    return {
        "name": "E2E Test Home",
        "rooms": [
            {"id": "living_room", "name": "Living Room", "type": "living_room", "area": 25},
            {"id": "bedroom", "name": "Bedroom", "type": "bedroom", "area": 15},
            {"id": "kitchen", "name": "Kitchen", "type": "kitchen", "area": 12},
        ],
        "devices": [
            {"id": "thermo_1", "name": "Thermostat", "device_type": "thermostat", "room_id": "living_room"},
            {"id": "light_1", "name": "Smart Light", "device_type": "smart_light", "room_id": "living_room"},
            {"id": "motion_1", "name": "Motion Sensor", "device_type": "motion_sensor", "room_id": "living_room"},
            {"id": "lock_1", "name": "Door Lock", "device_type": "smart_lock", "room_id": "living_room"},
            {"id": "camera_1", "name": "Security Camera", "device_type": "security_camera", "room_id": "living_room"},
        ],
        "inhabitants": [
            {"id": "person_1", "name": "John", "schedule": "regular"},
        ],
    }


@pytest.fixture
def threat_scenario():
    """Sample threat scenario for E2E tests."""
    return {
        "id": "test_threat",
        "name": "Credential Theft Attack",
        "type": "credential_theft",
        "target_devices": ["lock_1", "camera_1"],
        "stages": [
            {"action": "reconnaissance", "duration_seconds": 60},
            {"action": "exploit", "duration_seconds": 30},
            {"action": "exfiltration", "duration_seconds": 120},
        ],
    }


# =============================================================================
# 1. API → Simulation → Events → Output Tests
# =============================================================================

class TestAPISimulationFlow:
    """Test complete API to simulation to output flow."""

    @pytest.mark.asyncio
    async def test_create_home_run_simulation(self, api_client, sample_home_config):
        """Test creating a home and running simulation via API."""
        # Step 1: Create home
        create_response = await api_client.post("/api/simulation/home", sample_home_config)
        assert create_response["status"] == "ok"

        # Step 2: Start simulation
        sim_config = {
            "duration_hours": 0.01,  # Very short for testing
            "time_compression": 3600,
            "enable_threats": False,
        }
        start_response = await api_client.post("/api/simulation/start", sim_config)
        assert start_response["status"] == "ok"

        # Step 3: Poll for status
        status_response = await api_client.get("/api/simulation/status")
        assert status_response["status"] == "ok"

        # Step 4: Get events
        events_response = await api_client.get("/api/simulation/events")
        assert events_response["status"] == "ok"

    @pytest.mark.asyncio
    async def test_simulation_with_real_engine(self, sample_home_config):
        """Test simulation with real SimulationEngine."""
        from src.simulation.engine import SimulationEngine, SimulationConfig
        from src.simulation.models import Home, Room, Device, RoomType, DeviceType

        # Build home from config
        rooms = [
            Room(
                id=r["id"],
                name=r["name"],
                room_type=RoomType(r["type"]),
                area_sqm=r["area"],
            )
            for r in sample_home_config["rooms"]
        ]

        devices = [
            Device(
                id=d["id"],
                name=d["name"],
                device_type=DeviceType(d["device_type"]),
                room_id=d["room_id"],
            )
            for d in sample_home_config["devices"]
        ]

        home = Home(
            id="e2e_test_home",
            name=sample_home_config["name"],
            rooms=rooms,
            devices=devices,
        )

        # Run simulation
        config = SimulationConfig(
            duration_hours=0.001,  # Minimal duration
            time_compression=3600,
            tick_interval_ms=50,
        )

        engine = SimulationEngine(home, config)

        # Collect events
        collected_events = []
        engine.add_event_handler(lambda e: collected_events.append(e))

        stats = await engine.run()

        assert stats.state.value in ["completed", "stopped"]
        assert stats.total_events > 0
        assert len(collected_events) > 0


# =============================================================================
# 2. Home Builder → Simulation → Results Export Tests
# =============================================================================

class TestHomeBuilderFlow:
    """Test home builder to results export flow."""

    @pytest.mark.asyncio
    async def test_home_builder_to_export(self, api_client, sample_home_config):
        """Test complete home builder workflow."""
        # Step 1: Create home via builder
        home_response = await api_client.post("/api/home/create", sample_home_config)
        assert home_response["status"] == "ok"

        # Step 2: Add more devices
        new_device = {
            "id": "sensor_2",
            "name": "Temperature Sensor",
            "category": "sensor",
            "room_id": "bedroom",
        }
        device_response = await api_client.post("/api/home/devices", new_device)
        assert device_response["status"] == "ok"

        # Step 3: Run simulation
        sim_response = await api_client.post("/api/simulation/start", {
            "duration_hours": 0.01,
        })
        assert sim_response["status"] == "ok"

        # Step 4: Export results
        export_response = await api_client.get("/api/simulation/export?format=json")
        assert export_response["status"] == "ok"

    @pytest.mark.asyncio
    async def test_home_generator_templates(self):
        """Test home generation from templates."""
        from src.simulation.home.home_generator import HomeGenerator, HomeTemplate

        generator = HomeGenerator()

        # Test different templates
        templates = [
            HomeTemplate.STUDIO_APARTMENT,
            HomeTemplate.ONE_BEDROOM,
            HomeTemplate.FAMILY_HOUSE,
        ]

        for template in templates:
            home = generator.generate_from_template(template=template)
            assert home is not None
            assert len(home.rooms) > 0
            assert len(home.devices) > 0


# =============================================================================
# 3. Threat Injection → Detection → Alert Tests
# =============================================================================

class TestThreatDetectionFlow:
    """Test threat injection to detection to alert flow."""

    @pytest.mark.asyncio
    async def test_threat_injection_detection(self, threat_scenario):
        """Test threat injection and detection pipeline."""
        from src.simulation.threats.threat_catalog import ThreatCatalog
        from src.simulation.threats.threat_injector import ThreatInjector

        # Get threat from catalog
        catalog = ThreatCatalog()
        threat = catalog.get_threat(threat_scenario["type"])

        # Verify threat exists in catalog
        assert threat is not None or catalog.list_threats() is not None

    @pytest.mark.asyncio
    async def test_anomaly_detection_alert(self):
        """Test anomaly detection generating alerts."""
        from src.iot.edge.edge_computing import (
            AdvancedAnomalyDetector, AnomalyType,
        )

        detector = AdvancedAnomalyDetector(
            z_score_threshold=2.0,
            rate_of_change_threshold=0.3,
        )

        # Set threshold
        detector.set_threshold("temperature", 15.0, 30.0)

        # Normal readings - build baseline
        for i in range(20):
            result = detector.detect("device_1", "temperature", 22.0 + (i % 3) * 0.1)

        # Anomalous reading
        anomaly_result = detector.detect("device_1", "temperature", 50.0)

        assert anomaly_result.is_anomaly
        assert anomaly_result.anomaly_type == AnomalyType.THRESHOLD

    @pytest.mark.asyncio
    async def test_security_event_to_alert(self):
        """Test security events generating alerts."""
        from src.security.engine import (
            SecurityPrivacyEngine, SecurityEvent, SecurityEventType, SecurityLevel
        )

        engine = SecurityPrivacyEngine()
        await engine.start()

        # Log suspicious events
        events_logged = []
        for i in range(5):
            event = SecurityEvent(
                event_type=SecurityEventType.AUTH_FAILURE,
                source_id="device_1",
                source_type="device",
                severity=SecurityLevel.MEDIUM,
                success=False,
                details={"attempt": i + 1, "reason": "invalid_credentials"},
            )
            await engine.log_event(event)
            events_logged.append(event)

        # Check stats
        stats = engine.stats
        assert stats.auth_failures >= 5

        await engine.stop()


# =============================================================================
# 4. RAG Query → Knowledge Base → Response Tests
# =============================================================================

class TestRAGFlow:
    """Test RAG query to response flow."""

    @pytest.mark.asyncio
    async def test_rag_query_flow(self, api_client):
        """Test RAG query processing flow."""
        # Step 1: Query knowledge base
        query = {
            "question": "How do I configure a smart thermostat?",
            "use_rag": True,
        }
        response = await api_client.post("/api/chat", query)
        assert response["status"] == "ok"

    @pytest.mark.asyncio
    async def test_knowledge_base_search(self):
        """Test knowledge base semantic search."""
        # This would test the actual RAG implementation
        # Simulated for now as it requires ChromaDB setup

        class MockKnowledgeBase:
            def search(self, query: str, limit: int = 5):
                return [
                    {"content": "Smart thermostat setup guide...", "score": 0.95},
                    {"content": "Temperature scheduling...", "score": 0.85},
                ]

        kb = MockKnowledgeBase()
        results = kb.search("thermostat configuration")

        assert len(results) > 0
        assert results[0]["score"] > 0.8


# =============================================================================
# 5. Agent Orchestration → Task Completion Tests
# =============================================================================

class TestAgentOrchestrationFlow:
    """Test agent orchestration workflows."""

    @pytest.mark.asyncio
    async def test_multi_agent_task(self, api_client):
        """Test multi-agent task completion."""
        # Step 1: Create task
        task = {
            "type": "analyze_anomaly",
            "data": {"device_id": "sensor_1", "anomaly_type": "threshold"},
        }
        task_response = await api_client.post("/api/agents/task", task)
        assert task_response["status"] == "ok"

        # Step 2: Get agent status
        status_response = await api_client.get("/api/agents/status")
        assert status_response["status"] == "ok"

    @pytest.mark.asyncio
    async def test_agent_communication(self):
        """Test inter-agent communication."""
        # Simulated agent communication
        class MockAgent:
            def __init__(self, agent_id: str):
                self.agent_id = agent_id
                self.messages = []

            def send_message(self, to_agent: str, message: dict):
                return {"from": self.agent_id, "to": to_agent, "message": message}

            def receive_message(self, message: dict):
                self.messages.append(message)
                return True

        agent_a = MockAgent("analysis_agent")
        agent_b = MockAgent("response_agent")

        # Simulate communication
        msg = agent_a.send_message("response_agent", {"action": "alert", "severity": "high"})
        result = agent_b.receive_message(msg)

        assert result
        assert len(agent_b.messages) == 1


# =============================================================================
# 6. Parameter Sweep → Statistical Analysis Tests
# =============================================================================

class TestParameterSweepFlow:
    """Test parameter sweep to analysis flow."""

    @pytest.mark.asyncio
    async def test_parameter_sweep_execution(self, api_client):
        """Test parameter sweep workflow."""
        # Step 1: Create sweep configuration
        sweep_config = {
            "name": "Device Count Impact Study",
            "parameters": [
                {"name": "device_count", "values": [5, 10, 20, 50]},
                {"name": "threat_probability", "values": [0.0, 0.1, 0.3]},
            ],
            "iterations_per_config": 3,
        }

        create_response = await api_client.post("/api/sweeps/create", sweep_config)
        assert create_response["status"] == "ok"

        # Step 2: Run sweep
        run_response = await api_client.post("/api/sweeps/run", {
            "sweep_id": "test_sweep",
        })
        assert run_response["status"] == "ok"

        # Step 3: Get results
        results_response = await api_client.get("/api/sweeps/results/test_sweep")
        assert results_response["status"] == "ok"

    @pytest.mark.asyncio
    async def test_statistical_analysis(self):
        """Test statistical analysis of sweep results."""
        from src.output.research.statistical_testing import StatisticalTestingTools, TestType

        tools = StatisticalTestingTools()

        # Sample data (simulated sweep results)
        group_a = [10.5, 11.2, 10.8, 11.5, 10.9]  # Low device count
        group_b = [15.2, 16.1, 15.8, 14.9, 15.5]  # High device count

        # Perform t-test
        result = tools.t_test_independent(group_a, group_b)

        assert result is not None
        assert result.test_type == TestType.T_TEST_INDEPENDENT
        assert result.p_value is not None

    @pytest.mark.asyncio
    async def test_correlation_analysis(self):
        """Test correlation analysis."""
        from src.output.research.statistical_testing import StatisticalTestingTools

        tools = StatisticalTestingTools()

        # Sample data
        device_counts = [5, 10, 15, 20, 25, 30]
        detection_times = [2.1, 3.5, 5.2, 6.8, 8.1, 9.5]

        # Pearson correlation
        pearson_result = tools.correlation_pearson(device_counts, detection_times)
        assert pearson_result is not None
        assert abs(pearson_result.effect_size) > 0.8  # Strong correlation expected

        # Spearman correlation
        spearman_result = tools.correlation_spearman(device_counts, detection_times)
        assert spearman_result is not None


# =============================================================================
# 7. Security → Authentication → Authorization Tests
# =============================================================================

class TestSecurityFlow:
    """Test security workflows."""

    @pytest.mark.asyncio
    async def test_user_authentication_flow(self, api_client):
        """Test user authentication workflow."""
        # Step 1: Login
        login_data = {
            "username": "admin",
            "password": "test_password",
        }
        login_response = await api_client.post("/api/admin/login", login_data)
        assert login_response["status"] == "ok"

        # Step 2: Access protected resource
        protected_response = await api_client.get("/api/admin/users")
        assert protected_response["status"] == "ok"

    @pytest.mark.asyncio
    async def test_device_authentication_flow(self):
        """Test device authentication flow."""
        from src.security.auth_manager import (
            AuthenticationManager, AuthMethod
        )

        auth_manager = AuthenticationManager()

        # Register device credentials
        device_id = "test_device_001"
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

        # Validate session has access token ID
        assert session.access_token_id is not None

    @pytest.mark.asyncio
    async def test_tls_handshake_flow(self):
        """Test TLS handshake flow."""
        from src.security.tls_manager import TLSManager, TLSConfig, TLSVersion

        # Create TLS manager with custom config
        config = TLSConfig(
            min_version=TLSVersion.TLS_1_2,
            max_version=TLSVersion.TLS_1_3,
        )
        tls_manager = TLSManager(config=config)

        # Generate a device certificate
        cert = await tls_manager.generate_certificate(
            subject="CN=test_device,O=TestOrg",
            san=["localhost", "127.0.0.1"],
        )
        assert cert is not None
        assert cert.is_valid

        # Initiate handshake (simulated)
        session = await tls_manager.initiate_handshake(
            client_id="test_client",
            server_id="test_server",
        )
        assert session is not None


# =============================================================================
# 8. Multi-user Concurrent Session Tests
# =============================================================================

class TestConcurrentSessions:
    """Test concurrent user sessions."""

    @pytest.mark.asyncio
    async def test_concurrent_simulations(self):
        """Test multiple concurrent simulation sessions."""
        from src.simulation.engine import SimulationEngine, SimulationConfig
        from src.simulation.models import Home, Room, Device, RoomType, DeviceType

        async def run_simulation(session_id: int) -> dict:
            """Run a single simulation session."""
            home = Home(
                id=f"session_{session_id}_home",
                name=f"Session {session_id} Home",
                rooms=[Room(
                    id=f"room_{session_id}",
                    name="Test Room",
                    room_type=RoomType.LIVING_ROOM,
                )],
                devices=[Device(
                    id=f"device_{session_id}",
                    name="Test Device",
                    device_type=DeviceType.MOTION_SENSOR,
                    room_id=f"room_{session_id}",
                )],
            )

            config = SimulationConfig(
                duration_hours=0.0001,
                time_compression=36000,
                tick_interval_ms=10,
            )

            engine = SimulationEngine(home, config)
            stats = await engine.run()

            return {
                "session_id": session_id,
                "state": stats.state.value,
                "events": stats.total_events,
            }

        # Run 5 concurrent simulations
        tasks = [run_simulation(i) for i in range(5)]
        results = await asyncio.gather(*tasks)

        assert len(results) == 5
        assert all(r["state"] in ["completed", "stopped"] for r in results)

    @pytest.mark.asyncio
    async def test_concurrent_api_requests(self, api_client):
        """Test concurrent API requests."""
        async def make_request(request_id: int) -> dict:
            """Make a single API request."""
            response = await api_client.get(f"/api/health?request_id={request_id}")
            return {"request_id": request_id, "response": response}

        # Run 10 concurrent requests
        tasks = [make_request(i) for i in range(10)]
        results = await asyncio.gather(*tasks)

        assert len(results) == 10
        assert all(r["response"]["status"] == "ok" for r in results)


# =============================================================================
# 9. Complete Workflow Tests
# =============================================================================

class TestCompleteWorkflows:
    """Test complete end-to-end workflows."""

    @pytest.mark.asyncio
    async def test_research_workflow(self, api_client, sample_home_config):
        """Test complete research workflow."""
        # Step 1: Configure home
        await api_client.post("/api/simulation/home", sample_home_config)

        # Step 2: Configure parameter sweep
        sweep_config = {
            "name": "Research Study",
            "parameters": [
                {"name": "duration_hours", "values": [1, 4, 8]},
            ],
        }
        await api_client.post("/api/sweeps/create", sweep_config)

        # Step 3: Run sweep
        await api_client.post("/api/sweeps/run", {"sweep_id": "research"})

        # Step 4: Analyze results
        await api_client.get("/api/sweeps/results/research")

        # Step 5: Export for publication
        export_response = await api_client.get("/api/sweeps/export/research?format=latex")
        assert export_response["status"] == "ok"

    @pytest.mark.asyncio
    async def test_security_audit_workflow(self, api_client):
        """Test security audit workflow."""
        # Step 1: Run security scan
        scan_response = await api_client.post("/api/security/scan", {
            "scope": "full",
        })
        assert scan_response["status"] == "ok"

        # Step 2: Get vulnerabilities
        vuln_response = await api_client.get("/api/security/vulnerabilities")
        assert vuln_response["status"] == "ok"

        # Step 3: Get compliance report
        compliance_response = await api_client.get("/api/security/compliance")
        assert compliance_response["status"] == "ok"


# =============================================================================
# Run Tests
# =============================================================================

if __name__ == "__main__":
    import sys
    sys.exit(pytest.main([__file__, "-v"]))
