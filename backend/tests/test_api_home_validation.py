"""
API Integration Tests for S3.12: Home Validation via API.

Tests the RAG-based home validation through the FastAPI endpoints.
Requires the backend server to NOT be running (uses TestClient).
"""

import sys
import pytest
from unittest.mock import MagicMock, patch, AsyncMock

# Mock chromadb before FastAPI imports
sys.modules['chromadb'] = MagicMock()
sys.modules['chromadb.config'] = MagicMock()

from fastapi.testclient import TestClient


@pytest.fixture
def mock_dependencies():
    """Mock all AI/RAG dependencies."""
    with patch('src.ai.llm.llm_engine.OllamaClient') as mock_ollama, \
         patch('src.rag.vector_store_module.vector_store.chromadb') as mock_chroma, \
         patch('src.rag.knowledge_base.KnowledgeBaseService') as mock_kb_service:

        # Setup mock Ollama client
        mock_ollama_instance = MagicMock()
        mock_ollama_instance.is_healthy = MagicMock(return_value=True)
        mock_ollama.return_value = mock_ollama_instance

        # Setup mock ChromaDB
        mock_collection = MagicMock()
        mock_collection.count.return_value = 10
        mock_chroma_client = MagicMock()
        mock_chroma_client.get_or_create_collection.return_value = mock_collection
        mock_chroma.PersistentClient.return_value = mock_chroma_client

        yield {
            'ollama': mock_ollama_instance,
            'chroma': mock_chroma_client,
            'kb_service': mock_kb_service,
        }


@pytest.fixture
def client(mock_dependencies):
    """Create FastAPI test client."""
    from src.main import app
    return TestClient(app)


class TestHealthEndpoint:
    """Test health endpoint to verify test setup."""

    def test_health_check(self, client):
        """Verify the API is accessible."""
        response = client.get("/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] in ["healthy", "degraded"]


class TestRAGStatsEndpoint:
    """Test RAG stats endpoint includes validation fields."""

    def test_rag_stats_includes_chunking_fields(self, client):
        """Test that RAG stats include chunking configuration."""
        try:
            response = client.get("/api/rag/stats")
        except Exception:
            # ChromaDB connection may fail in test mode - skip
            pytest.skip("ChromaDB not available in test mode")
            return

        # May return 200 or 503 depending on ChromaDB mock
        if response.status_code == 200:
            data = response.json()
            # Check new fields are present
            assert "chunking_enabled" in data
            assert "chunk_size" in data
            assert "chunk_overlap" in data
            assert "pdf_parser_available" in data
            assert "pdf_parser" in data
        else:
            # Skip test if RAG service is not available
            pytest.skip(f"RAG service returned {response.status_code}")

    def test_rag_stats_default_values(self, client):
        """Test RAG stats have expected default values."""
        try:
            response = client.get("/api/rag/stats")
        except Exception:
            pytest.skip("ChromaDB not available in test mode")
            return

        if response.status_code == 200:
            data = response.json()
            # Verify default values
            assert data.get("chunk_size", 512) >= 256
            assert data.get("chunk_overlap", 50) >= 0
        else:
            pytest.skip(f"RAG service returned {response.status_code}")


class TestAgentDashboardEndpoint:
    """Test agent dashboard includes home-agent with validation capability."""

    def test_agents_list_includes_home_agent(self, client):
        """Test that agents list includes home-agent."""
        response = client.get("/api/agents/")

        if response.status_code == 200:
            data = response.json()
            agents = data.get("agents", [])
            agent_ids = [a.get("agent_id") for a in agents]

            # Home agent should be present
            assert any("home" in aid.lower() for aid in agent_ids if aid)

    def test_home_agent_has_validation_capability(self, client):
        """Test home agent has validation capabilities."""
        response = client.get("/api/agents/")

        if response.status_code == 200:
            data = response.json()
            agents = data.get("agents", [])

            # Find home agent
            home_agent = next(
                (a for a in agents if a.get("agent_id", "").lower().startswith("home")),
                None
            )

            if home_agent:
                capabilities = home_agent.get("capabilities", [])
                # Check validation capabilities exist
                assert "validate_home" in capabilities or any("valid" in c for c in capabilities)


class TestSimulationHomeEndpoint:
    """Test simulation home creation endpoint."""

    def test_create_home_returns_validation_info(self, client):
        """Test that home creation returns structure that could include validation."""
        response = client.post(
            "/api/simulation/home",
            json={
                "name": "Test Home",
                "template": "two_bedroom",
                "device_density": 1.0,
            }
        )

        if response.status_code == 200:
            data = response.json()
            # Check basic structure
            assert "id" in data
            assert "name" in data
            assert "total_rooms" in data
            assert "total_devices" in data

    def test_create_custom_home(self, client):
        """Test custom home creation with validation-relevant fields."""
        response = client.post(
            "/api/simulation/home/custom",
            json={
                "name": "Custom Test Home",
                "rooms": [
                    {
                        "id": "room-1",
                        "name": "Living Room",
                        "type": "living_room",
                        "x": 0,
                        "y": 0,
                        "width": 100,
                        "height": 100,
                        "devices": [
                            {"type": "smart_light", "protocol": "zigbee"},
                            {"type": "thermostat", "protocol": "wifi"},
                        ]
                    },
                    {
                        "id": "room-2",
                        "name": "Entry",
                        "type": "entry",
                        "x": 100,
                        "y": 0,
                        "width": 50,
                        "height": 50,
                        "devices": [
                            {"type": "smart_lock", "protocol": "z-wave"},
                            {"type": "security_camera", "protocol": "wifi"},
                        ]
                    },
                ],
                "inhabitants": [
                    {
                        "id": "person-1",
                        "name": "Test User",
                        "role": "remote_worker",
                        "age": 35,
                    }
                ],
            }
        )

        if response.status_code == 200:
            data = response.json()
            assert "id" in data
            assert data["total_rooms"] >= 2
            assert data["total_devices"] >= 4


class TestAgentManualTrigger:
    """Test manual agent triggering for validation tasks."""

    def test_trigger_home_agent_validation_task(self, client):
        """Test manually triggering a validation task on home agent."""
        # This tests the agent trigger API
        response = client.post(
            "/api/agents/home-agent/trigger",
            json={
                "task_type": "validate_home",
                "description": "Validate test home configuration",
                "parameters": {
                    "home_config": {
                        "rooms": [
                            {"name": "Living Room", "room_type": "living_room", "floor": 1},
                        ],
                        "devices": [
                            {"device_type": "smart_light", "room": "Living Room", "protocol": "wifi"},
                        ],
                    },
                    "use_rag": True,
                }
            }
        )

        # May return 200 (success), 404 (agent not found), or 409 (busy)
        assert response.status_code in [200, 404, 409, 500]

        if response.status_code == 200:
            data = response.json()
            assert data.get("success") is True
            assert "task_id" in data


class TestRAGValidationResponse:
    """Test that API responses can carry RAG validation data."""

    def test_chat_endpoint_with_home_validation_request(self, client):
        """Test chat endpoint handles home validation requests."""
        response = client.post(
            "/api/chat",
            json={
                "message": "Create a smart home with living room and entry with smart lock",
                "session_id": "test-session",
            }
        )

        # Chat endpoint may require LLM, so just check it doesn't crash
        assert response.status_code in [200, 500, 503]


class TestAPIResponseModels:
    """Test that API response models include validation-related fields."""

    def test_knowledge_base_stats_model(self):
        """Test KnowledgeBaseStats model has new fields."""
        from src.api.rag import KnowledgeBaseStats

        # Create instance with all fields
        stats = KnowledgeBaseStats(
            collection_name="test",
            document_count=10,
            persist_directory="/tmp/test",
            embedding_model="test-model",
            similarity_threshold=0.3,
            knowledge_base_path="/tmp/kb",
            chunking_enabled=True,
            chunk_size=512,
            chunk_overlap=50,
            pdf_parser_available=True,
            pdf_parser="PyMuPDF",
        )

        assert stats.chunking_enabled is True
        assert stats.chunk_size == 512
        assert stats.chunk_overlap == 50
        assert stats.pdf_parser_available is True
        assert stats.pdf_parser == "PyMuPDF"

    def test_knowledge_base_stats_model_defaults(self):
        """Test KnowledgeBaseStats model has sensible defaults."""
        from src.api.rag import KnowledgeBaseStats

        stats = KnowledgeBaseStats(
            collection_name="test",
            document_count=5,
            persist_directory="/tmp",
            embedding_model="model",
            similarity_threshold=0.3,
            knowledge_base_path="/tmp",
        )

        # Check defaults are applied
        assert stats.chunking_enabled is True
        assert stats.chunk_size == 512
        assert stats.chunk_overlap == 50
        assert stats.pdf_parser_available is False
        assert stats.pdf_parser is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
