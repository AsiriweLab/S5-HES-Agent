"""
Comprehensive Tests for S3.12: HomeBuilderAgent RAG Validation.

Tests the RAG-based home validation functionality including:
- RAG validation enabled/disabled modes
- Security recommendations from knowledge base
- Protocol-specific warnings (Z-Wave S0, Zigbee)
- Device-specific security recommendations
- Integration with KnowledgeBaseService
"""

import sys
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from dataclasses import dataclass

# Mock chromadb before imports
sys.modules['chromadb'] = MagicMock()
sys.modules['chromadb.config'] = MagicMock()


@dataclass
class MockRAGContext:
    """Mock RAG context for testing."""
    contexts: list
    sources: list
    has_context: bool = True
    query: str = ""


# ==================== Fixtures ====================

@pytest.fixture
def mock_knowledge_base():
    """Create a mock knowledge base for testing."""
    kb = MagicMock()
    kb.get_rag_context = MagicMock(return_value=MockRAGContext(
        contexts=["IoT devices should be on a separate VLAN for network segmentation."],
        sources=["Network Security Guide"],
        has_context=True,
    ))
    return kb


@pytest.fixture
def sample_home_config():
    """Sample home configuration for testing."""
    return {
        "name": "Test Home",
        "rooms": [
            {"name": "Living Room", "room_type": "living_room", "floor": 1},
            {"name": "Bedroom", "room_type": "bedroom", "floor": 1},
            {"name": "Kitchen", "room_type": "kitchen", "floor": 1},
            {"name": "Front Entry", "room_type": "entry", "floor": 1},
        ],
        "devices": [
            {"device_type": "smart_light", "room": "Living Room", "protocol": "zigbee"},
            {"device_type": "thermostat", "room": "Living Room", "protocol": "wifi"},
            {"device_type": "smart_lock", "room": "Front Entry", "protocol": "z-wave"},
            {"device_type": "smoke_detector", "room": "Kitchen", "protocol": "zigbee"},
            {"device_type": "security_camera", "room": "Front Entry", "protocol": "wifi"},
        ],
        "inhabitants": [
            {"name": "User 1", "age": 35, "occupation": "remote_worker"},
        ],
    }


@pytest.fixture
def minimal_home_config():
    """Minimal home configuration for edge case testing."""
    return {
        "name": "Minimal Home",
        "rooms": [
            {"name": "Living Room", "room_type": "living_room", "floor": 1},
        ],
        "devices": [
            {"device_type": "smart_light", "room": "Living Room", "protocol": "wifi"},
        ],
    }


@pytest.fixture
def insecure_home_config():
    """Home configuration with security issues for testing warnings."""
    return {
        "name": "Insecure Home",
        "rooms": [
            {"name": "Living Room", "room_type": "living_room", "floor": 1},
            {"name": "Entry", "room_type": "entry", "floor": 1},
        ],
        "devices": [
            # No smoke detector or smart lock (essential devices)
            {"device_type": "smart_light", "room": "Living Room", "protocol": "zigbee"},
            # No security camera at entry point
        ],
    }


@pytest.fixture
def zwave_s0_home_config():
    """Home configuration with Z-Wave devices for protocol testing."""
    return {
        "name": "Z-Wave Home",
        "rooms": [
            {"name": "Living Room", "room_type": "living_room", "floor": 1},
            {"name": "Entry", "room_type": "entry", "floor": 1},
        ],
        "devices": [
            {"device_type": "smart_lock", "room": "Entry", "protocol": "z-wave"},
            {"device_type": "thermostat", "room": "Living Room", "protocol": "z-wave"},
            {"device_type": "smoke_detector", "room": "Living Room", "protocol": "z-wave"},
        ],
    }


# ==================== Unit Tests ====================

class TestHomeBuilderAgentRAGValidation:
    """Tests for HomeBuilderAgent RAG validation."""

    @pytest.fixture
    def agent_with_rag(self, mock_knowledge_base):
        """Create HomeBuilderAgent with mocked RAG."""
        with patch('src.ai.agents.home_builder_agent.get_knowledge_base') as mock_get_kb, \
             patch('src.ai.agents.home_builder_agent.get_llm_engine') as mock_get_llm, \
             patch('src.ai.agents.home_builder_agent.get_prompt_manager') as mock_get_pm:

            mock_get_kb.return_value = mock_knowledge_base
            mock_get_llm.return_value = MagicMock()
            mock_get_pm.return_value = MagicMock()

            from src.ai.agents.home_builder_agent import HomeBuilderAgent
            agent = HomeBuilderAgent(enable_rag_validation=True)
            agent.knowledge_base = mock_knowledge_base
            return agent

    @pytest.fixture
    def agent_without_rag(self):
        """Create HomeBuilderAgent without RAG."""
        with patch('src.ai.agents.home_builder_agent.get_knowledge_base') as mock_get_kb, \
             patch('src.ai.agents.home_builder_agent.get_llm_engine') as mock_get_llm, \
             patch('src.ai.agents.home_builder_agent.get_prompt_manager') as mock_get_pm:

            mock_get_llm.return_value = MagicMock()
            mock_get_pm.return_value = MagicMock()

            from src.ai.agents.home_builder_agent import HomeBuilderAgent
            agent = HomeBuilderAgent(enable_rag_validation=False)
            return agent

    def test_agent_initialization_with_rag(self, agent_with_rag):
        """Test agent initializes with RAG enabled."""
        assert agent_with_rag.enable_rag_validation is True
        assert agent_with_rag.knowledge_base is not None

    def test_agent_initialization_without_rag(self, agent_without_rag):
        """Test agent initializes with RAG disabled."""
        assert agent_without_rag.enable_rag_validation is False
        assert agent_without_rag.knowledge_base is None

    def test_agent_capabilities_include_rag(self, agent_with_rag):
        """Test that agent capabilities include RAG validation."""
        capabilities = agent_with_rag.capabilities
        assert "validate_home" in capabilities
        assert "validate_home_with_rag" in capabilities

    @pytest.mark.asyncio
    async def test_validate_home_structural(self, agent_with_rag, sample_home_config):
        """Test structural validation of home configuration."""
        result = await agent_with_rag._validate_home({
            "home_config": sample_home_config,
            "use_rag": False,  # Disable RAG for this test
        })

        assert result["valid"] is True
        assert result["room_count"] == 4
        assert result["device_count"] == 5
        assert len(result["issues"]) == 0

    @pytest.mark.asyncio
    async def test_validate_home_empty_config(self, agent_with_rag):
        """Test validation with empty configuration."""
        result = await agent_with_rag._validate_home({
            "home_config": {},
            "use_rag": False,
        })

        assert result["valid"] is False
        assert "No rooms defined" in result["issues"]
        assert "No devices defined" in result["issues"]

    @pytest.mark.asyncio
    async def test_validate_home_missing_essential_devices(self, agent_with_rag, insecure_home_config):
        """Test validation warns about missing essential devices."""
        result = await agent_with_rag._validate_home({
            "home_config": insecure_home_config,
            "use_rag": False,
        })

        # Should have warnings about missing essential devices
        warnings_text = " ".join(result["warnings"])
        assert "smoke_detector" in warnings_text or "smart_lock" in warnings_text

    @pytest.mark.asyncio
    async def test_validate_home_invalid_device_room(self, agent_with_rag):
        """Test validation catches devices in non-existent rooms."""
        invalid_config = {
            "rooms": [{"name": "Living Room", "room_type": "living_room", "floor": 1}],
            "devices": [{"device_type": "smart_light", "room": "Non-Existent Room", "protocol": "wifi"}],
        }

        result = await agent_with_rag._validate_home({
            "home_config": invalid_config,
            "use_rag": False,
        })

        assert result["valid"] is False
        assert any("non-existent room" in issue.lower() for issue in result["issues"])

    @pytest.mark.asyncio
    async def test_validate_home_unknown_room_type(self, agent_with_rag):
        """Test validation warns about unknown room types."""
        config = {
            "rooms": [{"name": "Mystery Room", "room_type": "mystery", "floor": 1}],
            "devices": [{"device_type": "smart_light", "room": "Mystery Room", "protocol": "wifi"}],
        }

        result = await agent_with_rag._validate_home({
            "home_config": config,
            "use_rag": False,
        })

        assert any("unknown room type" in w.lower() for w in result["warnings"])


class TestRAGValidationIntegration:
    """Tests for RAG-based validation functionality."""

    @pytest.fixture
    def mock_kb_with_security_context(self):
        """Create mock KB that returns security-related contexts."""
        kb = MagicMock()

        def mock_get_context(query, n_results=3):
            if "security best practices" in query.lower():
                return MockRAGContext(
                    contexts=[
                        "IoT devices should be placed on a separate VLAN for network segmentation.",
                        "Default credentials are a major attack vector - always change defaults.",
                    ],
                    sources=["Network Security Guide", "IoT Best Practices"],
                    has_context=True,
                    query=query,
                )
            elif "protocol" in query.lower():
                return MockRAGContext(
                    contexts=[
                        "Z-Wave S0 uses weak legacy encryption and should be avoided.",
                        "Zigbee network key sharing means compromise of one device affects all.",
                    ],
                    sources=["Protocol Security Research"],
                    has_context=True,
                    query=query,
                )
            elif "smart_lock" in query.lower() or "security_camera" in query.lower():
                return MockRAGContext(
                    contexts=[
                        "Smart locks are vulnerable to replay attacks without proper nonce handling.",
                        "RTSP camera streams should be encrypted to prevent eavesdropping.",
                    ],
                    sources=["Device Security Analysis"],
                    has_context=True,
                    query=query,
                )
            return MockRAGContext(contexts=[], sources=[], has_context=False)

        kb.get_rag_context = MagicMock(side_effect=mock_get_context)
        return kb

    @pytest.fixture
    def agent_with_full_rag(self, mock_kb_with_security_context):
        """Create agent with full RAG mock."""
        with patch('src.ai.agents.home_builder_agent.get_knowledge_base') as mock_get_kb, \
             patch('src.ai.agents.home_builder_agent.get_llm_engine') as mock_get_llm, \
             patch('src.ai.agents.home_builder_agent.get_prompt_manager') as mock_get_pm:

            mock_get_kb.return_value = mock_kb_with_security_context
            mock_get_llm.return_value = MagicMock()
            mock_get_pm.return_value = MagicMock()

            from src.ai.agents.home_builder_agent import HomeBuilderAgent
            agent = HomeBuilderAgent(enable_rag_validation=True)
            agent.knowledge_base = mock_kb_with_security_context
            return agent

    @pytest.mark.asyncio
    async def test_rag_validation_network_segmentation(self, agent_with_full_rag, sample_home_config):
        """Test RAG validation recommends network segmentation."""
        result = await agent_with_full_rag._validate_home({
            "home_config": sample_home_config,
            "use_rag": True,
        })

        # Should have network segmentation recommendation
        recommendations_text = " ".join(result["recommendations"]).lower()
        assert "vlan" in recommendations_text or "segmentation" in recommendations_text

    @pytest.mark.asyncio
    async def test_rag_validation_zwave_warning(self, agent_with_full_rag, zwave_s0_home_config):
        """Test RAG validation warns about Z-Wave S0."""
        result = await agent_with_full_rag._validate_home({
            "home_config": zwave_s0_home_config,
            "use_rag": True,
        })

        # Should have Z-Wave S0 warning
        warnings_text = " ".join(result["warnings"]).lower()
        assert "z-wave" in warnings_text or "s0" in warnings_text or "weak" in warnings_text

    @pytest.mark.asyncio
    async def test_rag_validation_zigbee_warning(self, agent_with_full_rag, sample_home_config):
        """Test RAG validation warns about Zigbee key sharing."""
        result = await agent_with_full_rag._validate_home({
            "home_config": sample_home_config,  # Has zigbee devices
            "use_rag": True,
        })

        # Should have Zigbee key sharing recommendation
        all_text = " ".join(result["recommendations"] + result["warnings"]).lower()
        assert "zigbee" in all_text or "key" in all_text

    @pytest.mark.asyncio
    async def test_rag_validation_smart_lock_recommendation(self, agent_with_full_rag, sample_home_config):
        """Test RAG validation provides smart lock recommendations."""
        result = await agent_with_full_rag._validate_home({
            "home_config": sample_home_config,  # Has smart_lock
            "use_rag": True,
        })

        # Should have smart lock security recommendation
        recommendations_text = " ".join(result["recommendations"]).lower()
        assert "lock" in recommendations_text or "replay" in recommendations_text

    @pytest.mark.asyncio
    async def test_rag_validation_camera_recommendation(self, agent_with_full_rag, sample_home_config):
        """Test RAG validation provides camera recommendations."""
        result = await agent_with_full_rag._validate_home({
            "home_config": sample_home_config,  # Has security_camera
            "use_rag": True,
        })

        # Should have camera security recommendation
        recommendations_text = " ".join(result["recommendations"]).lower()
        assert "camera" in recommendations_text or "stream" in recommendations_text or "rtsp" in recommendations_text

    @pytest.mark.asyncio
    async def test_rag_validation_returns_sources(self, agent_with_full_rag, sample_home_config):
        """Test RAG validation returns source references."""
        result = await agent_with_full_rag._validate_home({
            "home_config": sample_home_config,
            "use_rag": True,
        })

        assert result["rag_validation"] is not None
        assert "sources" in result["rag_validation"]
        assert len(result["rag_validation"]["sources"]) > 0
        assert result["rag_validation"]["knowledge_base_consulted"] is True

    @pytest.mark.asyncio
    async def test_rag_validation_queries_executed(self, agent_with_full_rag, sample_home_config):
        """Test RAG validation executes multiple queries."""
        result = await agent_with_full_rag._validate_home({
            "home_config": sample_home_config,
            "use_rag": True,
        })

        assert result["rag_validation"]["queries_executed"] == 3


class TestRAGValidationDisabled:
    """Tests for when RAG validation is disabled."""

    @pytest.fixture
    def agent_rag_disabled(self):
        """Create agent with RAG disabled."""
        with patch('src.ai.agents.home_builder_agent.get_knowledge_base') as mock_get_kb, \
             patch('src.ai.agents.home_builder_agent.get_llm_engine') as mock_get_llm, \
             patch('src.ai.agents.home_builder_agent.get_prompt_manager') as mock_get_pm:

            mock_get_llm.return_value = MagicMock()
            mock_get_pm.return_value = MagicMock()

            from src.ai.agents.home_builder_agent import HomeBuilderAgent
            agent = HomeBuilderAgent(enable_rag_validation=False)
            return agent

    @pytest.mark.asyncio
    async def test_no_rag_validation_when_disabled(self, agent_rag_disabled, sample_home_config):
        """Test that RAG validation is skipped when disabled."""
        result = await agent_rag_disabled._validate_home({
            "home_config": sample_home_config,
        })

        # Should still validate structure
        assert result["valid"] is True
        # But no RAG validation
        assert result["rag_validation"] is None

    @pytest.mark.asyncio
    async def test_use_rag_param_override(self, agent_rag_disabled, sample_home_config):
        """Test use_rag param cannot enable RAG when KB is None."""
        result = await agent_rag_disabled._validate_home({
            "home_config": sample_home_config,
            "use_rag": True,  # Try to enable
        })

        # Still no RAG since KB is None
        assert result["rag_validation"] is None


class TestRAGValidationEdgeCases:
    """Edge case tests for RAG validation."""

    @pytest.fixture
    def mock_failing_kb(self):
        """Create mock KB that raises exceptions."""
        kb = MagicMock()
        kb.get_rag_context = MagicMock(side_effect=Exception("KB connection failed"))
        return kb

    @pytest.fixture
    def agent_with_failing_kb(self, mock_failing_kb):
        """Create agent with failing KB."""
        with patch('src.ai.agents.home_builder_agent.get_knowledge_base') as mock_get_kb, \
             patch('src.ai.agents.home_builder_agent.get_llm_engine') as mock_get_llm, \
             patch('src.ai.agents.home_builder_agent.get_prompt_manager') as mock_get_pm:

            mock_get_kb.return_value = mock_failing_kb
            mock_get_llm.return_value = MagicMock()
            mock_get_pm.return_value = MagicMock()

            from src.ai.agents.home_builder_agent import HomeBuilderAgent
            agent = HomeBuilderAgent(enable_rag_validation=True)
            agent.knowledge_base = mock_failing_kb
            return agent

    @pytest.mark.asyncio
    async def test_rag_failure_graceful_handling(self, agent_with_failing_kb, sample_home_config):
        """Test that RAG failures are handled gracefully."""
        # Should not raise exception
        result = await agent_with_failing_kb._validate_home({
            "home_config": sample_home_config,
            "use_rag": True,
        })

        # Structural validation should still work
        assert result["valid"] is True
        # RAG validation returns but with empty recommendations
        assert result["rag_validation"] is not None

    @pytest.mark.asyncio
    async def test_empty_protocols_handling(self, agent_with_failing_kb):
        """Test handling of config with no protocols."""
        config = {
            "rooms": [{"name": "Room", "room_type": "living_room", "floor": 1}],
            "devices": [{"device_type": "smart_light", "room": "Room"}],  # No protocol
        }

        # Should not crash
        result = await agent_with_failing_kb._validate_home({
            "home_config": config,
            "use_rag": False,
        })

        assert result["valid"] is True


class TestValidateWithRAGTool:
    """Tests for the _validate_security_with_rag tool."""

    @pytest.fixture
    def mock_kb_simple(self):
        """Simple mock KB for tool tests."""
        kb = MagicMock()
        kb.get_rag_context = MagicMock(return_value=MockRAGContext(
            contexts=["Test security context"],
            sources=["Test Source"],
            has_context=True,
        ))
        return kb

    @pytest.fixture
    def agent_with_tool(self, mock_kb_simple):
        """Create agent with tool registered."""
        with patch('src.ai.agents.home_builder_agent.get_knowledge_base') as mock_get_kb, \
             patch('src.ai.agents.home_builder_agent.get_llm_engine') as mock_get_llm, \
             patch('src.ai.agents.home_builder_agent.get_prompt_manager') as mock_get_pm:

            mock_get_kb.return_value = mock_kb_simple
            mock_get_llm.return_value = MagicMock()
            mock_get_pm.return_value = MagicMock()

            from src.ai.agents.home_builder_agent import HomeBuilderAgent
            agent = HomeBuilderAgent(enable_rag_validation=True)
            agent.knowledge_base = mock_kb_simple
            return agent

    def test_validate_security_tool_registered(self, agent_with_tool):
        """Test that validate_security_config tool is registered."""
        assert "validate_security_config" in agent_with_tool._tools


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
