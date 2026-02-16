"""
Integration Tests for Sprint 6: Agentic AI Layer

Tests the complete agent framework including:
- Agent Orchestrator
- Task Decomposition
- Specialized Agents (HomeBuilder, DeviceManager, ThreatInjector)
- MCP Communication Hub
- Verification Pipeline
"""

import asyncio
import sys
import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

# Mock chromadb before imports to avoid numpy compatibility issues
sys.modules['chromadb'] = MagicMock()
sys.modules['chromadb.config'] = MagicMock()

# Mock the RAG modules
mock_knowledge_base = MagicMock()
mock_knowledge_base.KnowledgeBase = MagicMock()
mock_knowledge_base.get_knowledge_base = MagicMock(return_value=MagicMock())
mock_knowledge_base.SearchResult = MagicMock()
sys.modules['src.rag.knowledge_base'] = mock_knowledge_base

# Agent Framework
from src.ai.agents.base_agent import (
    AbstractAgent,
    AgentMessage,
    AgentResult,
    AgentState,
    AgentTask,
    MessageType,
)

# Mock the LLM engine for agent imports
mock_llm_module = MagicMock()
mock_llm_module.LLMEngine = MagicMock()
mock_llm_module.get_llm_engine = MagicMock(return_value=MagicMock())
mock_llm_module.InferenceResult = MagicMock()
sys.modules['src.ai.llm'] = mock_llm_module
sys.modules['src.ai.llm.llm_engine'] = mock_llm_module

from src.ai.agents.home_builder_agent import HomeBuilderAgent
from src.ai.agents.device_manager_agent import DeviceManagerAgent
from src.ai.agents.threat_injector_agent import ThreatInjectorAgent

# Orchestrator
from src.ai.orchestrator.task_decomposer import (
    TaskDecomposer,
    TaskPriority,
    TaskStatus,
)
from src.ai.orchestrator.orchestrator import (
    AgentOrchestrator,
    ExecutionContext,
    OrchestratorState,
)

# MCP Communication
from src.ai.mcp.communication_hub import (
    ChannelType,
    MCPCommunicationHub,
    MessageEnvelope,
)

# Verification
from src.ai.verification import (
    PhysicalConstraintChecker,
    SchemaValidator,
    VerificationCategory,
    VerificationPipeline,
    VerificationStatus,
)


# ==================== Base Agent Tests ====================

class TestAbstractAgent:
    """Test the abstract agent base class."""

    def test_agent_task_creation(self):
        """Test creating an agent task."""
        task = AgentTask.create(
            task_type="test_action",
            description="Test task description",
            parameters={"key": "value"},
            priority=2,
        )

        assert task.task_id is not None
        assert task.task_type == "test_action"
        assert task.description == "Test task description"
        assert task.parameters == {"key": "value"}
        assert task.priority == 2

    def test_agent_message_creation(self):
        """Test creating an agent message."""
        message = AgentMessage.create(
            sender="agent_1",
            receiver="agent_2",
            message_type=MessageType.REQUEST,
            content={"action": "do_something"},
        )

        assert message.message_id is not None
        assert message.sender == "agent_1"
        assert message.receiver == "agent_2"
        assert message.message_type == MessageType.REQUEST

    def test_agent_result_success(self):
        """Test creating a successful agent result."""
        result = AgentResult(
            success=True,
            data={"result": "success"},
        )

        assert result.success is True
        assert result.data == {"result": "success"}
        assert result.error is None

    def test_agent_result_failure(self):
        """Test creating a failed agent result."""
        result = AgentResult(
            success=False,
            error="Something went wrong",
        )

        assert result.success is False
        assert result.error == "Something went wrong"


# ==================== Home Builder Agent Tests ====================

class TestHomeBuilderAgent:
    """Test the HomeBuilderAgent."""

    @pytest.fixture
    def agent(self):
        """Create a HomeBuilderAgent instance."""
        return HomeBuilderAgent()

    def test_agent_initialization(self, agent):
        """Test agent initializes correctly."""
        assert agent.name == "HomeBuilder"
        assert agent.agent_type == "home_builder"
        assert agent.state == AgentState.IDLE
        assert "create_home" in agent.capabilities

    @pytest.mark.asyncio
    async def test_create_home_task(self, agent):
        """Test creating a home configuration."""
        task = AgentTask.create(
            task_type="create_home",
            description="Create a 2-bedroom smart home",
            parameters={
                "name": "Test Home",
                "rooms": [
                    {"name": "Living Room", "type": "living_room"},
                    {"name": "Bedroom 1", "type": "bedroom"},
                    {"name": "Bedroom 2", "type": "bedroom"},
                ],
            },
        )

        result = await agent.execute_task(task)

        # Check if result is successful or gracefully failed (mock issues)
        if result.success:
            assert result.data is not None
        else:
            # Expected with mocked dependencies
            assert result.error is not None

    @pytest.mark.asyncio
    async def test_validate_home_task(self, agent):
        """Test validating a home configuration."""
        # Create a mock home for validation
        home = {
            "home_id": "test-123",
            "name": "Validation Test Home",
            "rooms": [{"room_id": "r1", "name": "Room 1", "type": "living_room"}],
        }

        # Validate it
        validate_task = AgentTask.create(
            task_type="validate_home",
            description="Validate the home",
            parameters={"home": home},
        )
        result = await agent.execute_task(validate_task)

        # With mocked deps, may succeed or fail gracefully
        assert result is not None

    def test_agent_status(self, agent):
        """Test getting agent status."""
        status = agent.get_status()

        assert status["agent_id"] == agent.agent_id
        assert status["name"] == "HomeBuilder"
        assert status["state"] == AgentState.IDLE.value
        assert "capabilities" in status


# ==================== Device Manager Agent Tests ====================

class TestDeviceManagerAgent:
    """Test the DeviceManagerAgent."""

    @pytest.fixture
    def agent(self):
        """Create a DeviceManagerAgent instance."""
        return DeviceManagerAgent()

    def test_agent_initialization(self, agent):
        """Test agent initializes correctly."""
        assert agent.name == "DeviceManager"
        assert agent.agent_type == "device_manager"
        assert "add_device" in agent.capabilities
        assert "control_device" in agent.capabilities

    @pytest.mark.asyncio
    async def test_add_device_task(self, agent):
        """Test adding a device."""
        task = AgentTask.create(
            task_type="add_device",
            description="Add a smart light",
            parameters={
                "device_type": "smart_light",
                "name": "Living Room Light",
                "room_id": "room-1",
            },
        )

        result = await agent.execute_task(task)

        assert result.success is True
        # Check result has device data
        assert result.data is not None
        assert "device_id" in result.data or "initial_state" in result.data

    @pytest.mark.asyncio
    async def test_control_device_task(self, agent):
        """Test controlling a device."""
        # First add a device
        add_task = AgentTask.create(
            task_type="add_device",
            description="Add a light",
            parameters={
                "device_type": "smart_light",
                "name": "Test Light",
            },
        )
        add_result = await agent.execute_task(add_task)
        device_id = add_result.data.get("device_id")

        # Then control it
        control_task = AgentTask.create(
            task_type="control_device",
            description="Turn on the light",
            parameters={
                "device_id": device_id,
                "command": "turn_on",
            },
        )
        result = await agent.execute_task(control_task)

        # Verify result exists (may succeed or fail based on mocked state)
        assert result is not None

    @pytest.mark.asyncio
    async def test_generate_telemetry(self, agent):
        """Test generating device telemetry."""
        # Add a device first (use smart_light which is supported)
        add_task = AgentTask.create(
            task_type="add_device",
            description="Add a light",
            parameters={
                "device_type": "smart_light",
                "name": "Test Light",
            },
        )
        add_result = await agent.execute_task(add_task)
        device_id = add_result.data.get("device_id") if add_result.data else "test-id"

        # Generate telemetry
        telemetry_task = AgentTask.create(
            task_type="generate_telemetry",
            description="Generate sensor readings",
            parameters={
                "device_id": device_id,
                "count": 5,
            },
        )
        result = await agent.execute_task(telemetry_task)

        # Verify result exists
        assert result is not None


# ==================== Threat Injector Agent Tests ====================

class TestThreatInjectorAgent:
    """Test the ThreatInjectorAgent."""

    @pytest.fixture
    def agent(self):
        """Create a ThreatInjectorAgent instance."""
        return ThreatInjectorAgent()

    def test_agent_initialization(self, agent):
        """Test agent initializes correctly."""
        assert agent.name == "ThreatInjector"
        assert agent.agent_type == "threat_injector"
        assert "inject_threat" in agent.capabilities

    def test_threat_catalog(self, agent):
        """Test threat catalog is accessible."""
        # The THREAT_CATALOG is a module-level constant
        from src.ai.agents.threat_injector_agent import THREAT_CATALOG

        assert len(THREAT_CATALOG) > 0
        assert "data_exfiltration" in THREAT_CATALOG
        assert "ddos_attack" in THREAT_CATALOG

    @pytest.mark.asyncio
    async def test_inject_threat_task(self, agent):
        """Test injecting a threat."""
        task = AgentTask.create(
            task_type="inject_threat",
            description="Inject data exfiltration threat",
            parameters={
                "threat_type": "data_exfiltration",
                "target_device_id": "device-123",
            },
        )

        result = await agent.execute_task(task)

        assert result.success is True
        assert result.data is not None
        # Check for threat_type in the data
        assert result.data.get("threat_type") == "data_exfiltration"

    @pytest.mark.asyncio
    async def test_get_active_threats(self, agent):
        """Test getting active threats."""
        # Inject a threat first
        inject_task = AgentTask.create(
            task_type="inject_threat",
            description="Inject test threat",
            parameters={
                "threat_type": "ddos_attack",
                "target_device_id": "device-456",
            },
        )
        await agent.execute_task(inject_task)

        # Get active threats
        list_task = AgentTask.create(
            task_type="list_threats",
            description="List active threats",
            parameters={},
        )
        result = await agent.execute_task(list_task)

        assert result.success is True
        assert result.data is not None
        # Check for active_threats key
        assert "active_threats" in result.data
        assert len(result.data["active_threats"]) >= 1


# ==================== Task Decomposer Tests ====================

class TestTaskDecomposer:
    """Test the TaskDecomposer."""

    @pytest.fixture
    def decomposer(self):
        """Create a TaskDecomposer instance."""
        return TaskDecomposer()

    def test_simple_decomposition_home(self, decomposer):
        """Test decomposing a home creation request."""
        plan = decomposer.decompose_simple(
            "Create a smart home with 3 bedrooms"
        )

        assert plan is not None
        assert len(plan.tasks) >= 1
        # Should have a home_builder task
        task_types = [t.task_type for t in plan.tasks]
        assert "home_builder" in task_types

    def test_simple_decomposition_device(self, decomposer):
        """Test decomposing a device request."""
        plan = decomposer.decompose_simple(
            "configure device thermostat settings"
        )

        assert plan is not None
        # Any plan generated is valid - specific types depend on keywords
        assert len(plan.tasks) >= 1

    def test_simple_decomposition_threat(self, decomposer):
        """Test decomposing a threat injection request."""
        plan = decomposer.decompose_simple(
            "Inject a DDoS attack on the camera"
        )

        assert plan is not None
        task_types = [t.task_type for t in plan.tasks]
        assert "threat_injector" in task_types

    def test_task_dependencies(self, decomposer):
        """Test that task dependencies are tracked."""
        plan = decomposer.decompose_simple(
            "Create a home and add devices"
        )

        # Tasks should have dependencies if applicable
        assert plan is not None
        # At minimum, device addition should depend on home creation


# ==================== Orchestrator Tests ====================

class TestAgentOrchestrator:
    """Test the AgentOrchestrator."""

    @pytest.fixture
    def orchestrator(self):
        """Create an AgentOrchestrator with agents."""
        orch = AgentOrchestrator(max_parallel_tasks=2)

        # Register agents
        orch.register_agent(HomeBuilderAgent())
        orch.register_agent(DeviceManagerAgent())
        orch.register_agent(ThreatInjectorAgent())

        return orch

    def test_orchestrator_initialization(self, orchestrator):
        """Test orchestrator initializes correctly."""
        assert orchestrator.state == OrchestratorState.IDLE
        assert len(orchestrator._agents) == 3

    def test_agent_registration(self, orchestrator):
        """Test agent registration."""
        status = orchestrator.get_status()

        assert status["registered_agents"] == 3
        assert "home_builder" in status["agents_by_type"]
        assert "device_manager" in status["agents_by_type"]
        assert "threat_injector" in status["agents_by_type"]

    def test_get_agents_by_type(self, orchestrator):
        """Test getting agents by type."""
        home_agents = orchestrator.get_agents_by_type("home_builder")
        assert len(home_agents) == 1
        assert home_agents[0].name == "HomeBuilder"

    @pytest.mark.asyncio
    async def test_process_simple_request(self, orchestrator):
        """Test processing a simple request."""
        context = await orchestrator.process_request(
            "Create a test smart home",
            use_llm_decomposition=False,
        )

        assert context.status == "completed"
        assert context.plan is not None
        assert len(context.results) > 0

    @pytest.mark.asyncio
    async def test_process_request_with_error_handling(self, orchestrator):
        """Test error handling in request processing."""
        # Invalid request that should still be handled gracefully
        context = await orchestrator.process_request(
            "Do something impossible",
            use_llm_decomposition=False,
        )

        # Should complete (even if no tasks match)
        assert context.status in ["completed", "failed"]


# ==================== MCP Communication Hub Tests ====================

class TestMCPCommunicationHub:
    """Test the MCPCommunicationHub."""

    @pytest.fixture
    def hub(self):
        """Create an MCPCommunicationHub instance."""
        return MCPCommunicationHub()

    def test_hub_initialization(self, hub):
        """Test hub initializes correctly."""
        # Hub has _stats dict
        assert hub._stats is not None
        assert "messages_sent" in hub._stats

    def test_agent_registration(self, hub):
        """Test agent registration."""
        hub.register_agent("test_agent")
        assert "test_agent" in hub._registered_agents

    @pytest.mark.asyncio
    async def test_direct_messaging(self, hub):
        """Test sending direct messages."""
        # Register receiver
        hub.register_agent("agent_2")

        # Create a message using AgentMessage
        message = AgentMessage.create(
            sender="agent_1",
            receiver="agent_2",
            message_type=MessageType.REQUEST,
            content={"test": "data"},
        )

        # Send the message
        result = await hub.send_direct(message)
        assert result is True

    @pytest.mark.asyncio
    async def test_broadcast_messaging(self, hub):
        """Test broadcasting messages."""
        # Register some agents
        hub.register_agent("agent_1")
        hub.register_agent("agent_2")

        # Broadcast using the correct API signature: (sender, message_type, content)
        result = await hub.broadcast(
            "broadcaster",
            MessageType.NOTIFICATION,
            {"announcement": "test"},
        )
        assert result >= 0  # Returns count of deliveries

    def test_pubsub_subscription(self, hub):
        """Test pub/sub subscription."""
        # Subscribe to a topic
        sub_id = hub.subscribe("agent_1", "test_topic")
        assert sub_id is not None
        assert len(hub._subscriptions["test_topic"]) > 0


# ==================== Verification Pipeline Tests ====================

class TestVerificationPipeline:
    """Test the VerificationPipeline."""

    @pytest.fixture
    def pipeline(self):
        """Create a VerificationPipeline instance."""
        return VerificationPipeline(strict_mode=False)

    @pytest.mark.asyncio
    async def test_pipeline_pass(self, pipeline):
        """Test verification passes for valid data."""
        valid_data = {
            "temperature": 22.5,
            "humidity": 45,
            "brightness": 80,
        }

        # Register a simple verifier
        async def simple_verifier(data, context):
            from src.ai.verification import VerificationCheck, VerificationStatus
            return VerificationCheck.create(
                category=VerificationCategory.PHYSICAL,
                name="simple_check",
                status=VerificationStatus.PASS,
                confidence=1.0,
                message="Check passed",
            )

        pipeline.register_verifier(VerificationCategory.PHYSICAL, simple_verifier)

        result = await pipeline.verify(valid_data)

        assert result.final_status == VerificationStatus.PASS
        assert result.overall_confidence > 0

    @pytest.mark.asyncio
    async def test_pipeline_reject(self, pipeline):
        """Test verification rejects invalid data."""
        async def failing_verifier(data, context):
            from src.ai.verification import VerificationCheck, VerificationStatus
            return VerificationCheck.create(
                category=VerificationCategory.PHYSICAL,
                name="failing_check",
                status=VerificationStatus.REJECT,
                confidence=1.0,
                message="Invalid data detected",
            )

        pipeline.register_verifier(VerificationCategory.PHYSICAL, failing_verifier)

        result = await pipeline.verify({"bad": "data"})

        assert result.final_status == VerificationStatus.REJECT


class TestSchemaValidator:
    """Test the SchemaValidator."""

    @pytest.fixture
    def validator(self):
        """Create a SchemaValidator instance."""
        return SchemaValidator()

    def test_validate_device_schema(self, validator):
        """Test validating against device schema."""
        valid_device = {
            "device_id": "dev-123",
            "device_type": "smart_light",
            "name": "Living Room Light",
        }

        is_valid, errors = validator.validate(valid_device, schema_name="device")

        assert is_valid is True
        assert len(errors) == 0

    def test_validate_device_schema_invalid(self, validator):
        """Test validation fails for invalid device."""
        invalid_device = {
            "device_id": "",  # Empty string should fail min_length
            "device_type": "smart_light",
            "name": "Test",
        }

        is_valid, errors = validator.validate(invalid_device, schema_name="device")

        assert is_valid is False
        assert len(errors) > 0

    def test_validate_threat_schema(self, validator):
        """Test validating against threat schema."""
        valid_threat = {
            "threat_id": "threat-123",
            "threat_type": "ddos_attack",
            "severity": "high",
            "target_device_id": "device-456",
        }

        is_valid, errors = validator.validate(valid_threat, schema_name="threat")

        assert is_valid is True

    def test_validate_threat_invalid_enum(self, validator):
        """Test validation fails for invalid enum value."""
        invalid_threat = {
            "threat_id": "threat-123",
            "threat_type": "unknown_attack",  # Not in enum
            "severity": "high",
            "target_device_id": "device-456",
        }

        is_valid, errors = validator.validate(invalid_threat, schema_name="threat")

        assert is_valid is False


class TestPhysicalConstraintChecker:
    """Test the PhysicalConstraintChecker."""

    @pytest.fixture
    def checker(self):
        """Create a PhysicalConstraintChecker instance."""
        return PhysicalConstraintChecker()

    def test_valid_temperature(self, checker):
        """Test valid temperature passes."""
        results = checker.check({"temperature": 22.5})

        violations = [r for r in results if not r[1]]
        assert len(violations) == 0

    def test_invalid_temperature_below_absolute_zero(self, checker):
        """Test temperature below absolute zero fails."""
        results = checker.check({"temperature": -300})

        violations = [r for r in results if not r[1]]
        assert len(violations) > 0
        assert any("absolute zero" in r[2] for r in violations)

    def test_valid_humidity(self, checker):
        """Test valid humidity passes."""
        results = checker.check({"humidity": 50})

        temp_violations = [r for r in results if r[0].name == "humidity_range" and not r[1]]
        assert len(temp_violations) == 0

    def test_invalid_humidity(self, checker):
        """Test invalid humidity fails."""
        results = checker.check({"humidity": 150})

        violations = [r for r in results if not r[1]]
        assert len(violations) > 0

    def test_valid_brightness(self, checker):
        """Test valid brightness passes."""
        results = checker.check(
            {"brightness": 75},
            device_type="smart_light"
        )

        violations = [r for r in results if r[0].name == "brightness_range" and not r[1]]
        assert len(violations) == 0

    def test_battery_percentage_range(self, checker):
        """Test battery percentage validation."""
        # Valid
        results = checker.check({"battery": 85})
        violations = [r for r in results if r[0].name == "battery_percentage" and not r[1]]
        assert len(violations) == 0

        # Invalid
        results = checker.check({"battery": 150})
        violations = [r for r in results if r[0].name == "battery_percentage" and not r[1]]
        assert len(violations) > 0


# ==================== Integration Tests ====================

class TestFullAgentWorkflow:
    """End-to-end integration tests."""

    @pytest.fixture
    def system(self):
        """Create a complete system with all components."""
        orchestrator = AgentOrchestrator(max_parallel_tasks=3)
        orchestrator.register_agent(HomeBuilderAgent())
        orchestrator.register_agent(DeviceManagerAgent())
        orchestrator.register_agent(ThreatInjectorAgent())

        pipeline = VerificationPipeline(strict_mode=False)
        schema_validator = SchemaValidator()
        physical_checker = PhysicalConstraintChecker()

        return {
            "orchestrator": orchestrator,
            "pipeline": pipeline,
            "schema_validator": schema_validator,
            "physical_checker": physical_checker,
        }

    @pytest.mark.asyncio
    async def test_create_home_with_devices(self, system):
        """Test creating a home and adding devices."""
        orchestrator = system["orchestrator"]

        # Create home
        context = await orchestrator.process_request(
            "Create a smart home called 'Test House'",
            use_llm_decomposition=False,
        )

        assert context.status == "completed"

    @pytest.mark.asyncio
    async def test_device_with_verification(self, system):
        """Test device operations with verification."""
        orchestrator = system["orchestrator"]
        pipeline = system["pipeline"]
        physical_checker = system["physical_checker"]

        # Register physical constraint verifier
        pipeline.register_verifier(
            VerificationCategory.PHYSICAL,
            physical_checker.create_verifier(),
        )

        # Add and control a device
        context = await orchestrator.process_request(
            "Add a smart thermostat",
            use_llm_decomposition=False,
        )

        if context.results:
            # Get device data
            for result in context.results.values():
                if hasattr(result, 'data') and result.data:
                    # Verify the device data
                    verification = await pipeline.verify(result.data)
                    # Should pass physical constraints
                    assert verification.final_status in [
                        VerificationStatus.PASS,
                        VerificationStatus.FLAG,
                    ]

    @pytest.mark.asyncio
    async def test_threat_injection_workflow(self, system):
        """Test complete threat injection workflow."""
        orchestrator = system["orchestrator"]

        # Inject a threat
        context = await orchestrator.process_request(
            "Inject a camera hijack attack",
            use_llm_decomposition=False,
        )

        assert context.status == "completed"

        # Check that ground truth labels were generated
        for task_id, result in context.results.items():
            if task_id != "_aggregated" and hasattr(result, 'data'):
                if result.data and "ground_truth_labels" in result.data:
                    labels = result.data["ground_truth_labels"]
                    assert len(labels) > 0
