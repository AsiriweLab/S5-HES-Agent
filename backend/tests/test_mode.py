"""
Tests for Mode API and No-LLM Mode Functionality

Tests the dual-mode system including:
- Mode switching (LLM <-> No-LLM)
- Expert consultation requests and feedback
- Pre-loaded scenario management
- Mode enforcement middleware
"""

import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from fastapi.testclient import TestClient

from src.main import app
from src.api.mode import (
    InteractionMode,
    ConsultationStatus,
    _consultations,
    _current_mode,
    _preloaded_scenarios,
)


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


@pytest.fixture(autouse=True)
def reset_mode_state():
    """Reset mode state before each test."""
    import src.api.mode as mode_module
    mode_module._current_mode = InteractionMode.LLM
    mode_module._consultations.clear()
    yield
    mode_module._current_mode = InteractionMode.LLM
    mode_module._consultations.clear()


class TestModeManagement:
    """Test mode switching and status endpoints."""

    def test_get_mode_status(self, client):
        """Test getting mode status."""
        response = client.get("/api/mode/status")
        assert response.status_code == 200
        data = response.json()
        assert "mode" in data
        assert "pending_consultations" in data
        assert "available_scenarios" in data
        assert data["mode"] in ["llm", "no-llm"]

    def test_set_mode_to_no_llm(self, client):
        """Test switching to No-LLM mode."""
        response = client.post("/api/mode/set?mode=no-llm")
        assert response.status_code == 200
        data = response.json()
        assert data["current_mode"] == "no-llm"
        assert data["status"] == "success"

    def test_set_mode_to_llm(self, client):
        """Test switching to LLM mode."""
        # First set to no-llm
        client.post("/api/mode/set?mode=no-llm")

        # Then switch back
        response = client.post("/api/mode/set?mode=llm")
        assert response.status_code == 200
        data = response.json()
        assert data["current_mode"] == "llm"

    def test_get_current_mode(self, client):
        """Test getting current mode."""
        response = client.get("/api/mode/current")
        assert response.status_code == 200
        data = response.json()
        assert "mode" in data


class TestPreloadedScenarios:
    """Test pre-loaded scenario endpoints."""

    def test_list_scenarios(self, client):
        """Test listing all scenarios."""
        response = client.get("/api/mode/scenarios")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) > 0

        # Check scenario structure
        scenario = data[0]
        assert "id" in scenario
        assert "name" in scenario
        assert "description" in scenario
        assert "category" in scenario
        assert "difficulty" in scenario
        assert "tags" in scenario

    def test_filter_scenarios_by_category(self, client):
        """Test filtering scenarios by category."""
        response = client.get("/api/mode/scenarios?category=security")
        assert response.status_code == 200
        data = response.json()
        for scenario in data:
            assert scenario["category"] == "security"

    def test_filter_scenarios_by_difficulty(self, client):
        """Test filtering scenarios by difficulty."""
        response = client.get("/api/mode/scenarios?difficulty=beginner")
        assert response.status_code == 200
        data = response.json()
        for scenario in data:
            assert scenario["difficulty"] == "beginner"

    def test_get_scenario_by_id(self, client):
        """Test getting a specific scenario."""
        response = client.get("/api/mode/scenarios/basic-attack-detection")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "basic-attack-detection"
        assert data["name"] == "Basic Attack Detection"

    def test_get_nonexistent_scenario(self, client):
        """Test getting a scenario that doesn't exist."""
        response = client.get("/api/mode/scenarios/nonexistent-id")
        assert response.status_code == 404

    def test_get_scenario_categories(self, client):
        """Test getting scenario categories."""
        response = client.get("/api/mode/scenarios/categories")
        assert response.status_code == 200
        data = response.json()
        assert "categories" in data
        assert isinstance(data["categories"], list)

    def test_get_scenario_tags(self, client):
        """Test getting scenario tags."""
        response = client.get("/api/mode/scenarios/tags")
        assert response.status_code == 200
        data = response.json()
        assert "tags" in data
        assert isinstance(data["tags"], list)

    def test_execute_scenario(self, client):
        """Test executing a pre-loaded scenario."""
        response = client.post("/api/mode/scenarios/basic-attack-detection/execute")
        assert response.status_code == 200
        data = response.json()
        assert "execution_id" in data
        assert "scenario_id" in data
        assert data["scenario_name"] == "Basic Attack Detection"
        assert "results" in data

    def test_execute_nonexistent_scenario(self, client):
        """Test executing a scenario that doesn't exist."""
        response = client.post("/api/mode/scenarios/nonexistent-id/execute")
        assert response.status_code == 404


class TestExpertConsultations:
    """Test expert consultation endpoints."""

    @pytest.fixture
    def mock_llm_engine(self):
        """Mock the LLM engine for consultation tests."""
        with patch("src.api.mode.get_llm_engine") as mock:
            engine = MagicMock()
            engine.generate = AsyncMock(return_value=MagicMock(
                content="This is a mock response about IoT security.",
                model="mock-model",
                confidence=MagicMock(value="high"),
                sources=["Source 1", "Source 2"],
                rag_context=MagicMock(contexts=["context1", "context2"]),
                inference_time_ms=100.0,
            ))
            mock.return_value = engine
            yield engine

    def test_request_consultation(self, client, mock_llm_engine):
        """Test requesting expert consultation."""
        response = client.post(
            "/api/mode/expert-consultation",
            json={
                "question": "How do I detect botnet activity?",
                "context": "Testing consultation",
                "use_rag": True,
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert "id" in data
        assert data["question"] == "How do I detect botnet activity?"
        assert data["status"] == "pending"
        assert "response" in data
        assert "confidence" in data
        assert "sources" in data
        assert "verification_notes" in data

    def test_list_consultations(self, client, mock_llm_engine):
        """Test listing consultations."""
        # First create a consultation
        client.post(
            "/api/mode/expert-consultation",
            json={"question": "Test question 1"},
        )
        client.post(
            "/api/mode/expert-consultation",
            json={"question": "Test question 2"},
        )

        response = client.get("/api/mode/expert-consultation")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 2

    def test_filter_consultations_by_status(self, client, mock_llm_engine):
        """Test filtering consultations by status."""
        # Create consultation
        create_response = client.post(
            "/api/mode/expert-consultation",
            json={"question": "Test question"},
        )
        consultation_id = create_response.json()["id"]

        # Accept it
        client.post(
            f"/api/mode/expert-consultation/{consultation_id}/feedback",
            json={"accepted": True},
        )

        # Filter by accepted
        response = client.get("/api/mode/expert-consultation?status=accepted")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["status"] == "accepted"

    def test_get_consultation_by_id(self, client, mock_llm_engine):
        """Test getting a specific consultation."""
        # Create consultation
        create_response = client.post(
            "/api/mode/expert-consultation",
            json={"question": "Test question"},
        )
        consultation_id = create_response.json()["id"]

        response = client.get(f"/api/mode/expert-consultation/{consultation_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == consultation_id

    def test_get_nonexistent_consultation(self, client):
        """Test getting a consultation that doesn't exist."""
        response = client.get("/api/mode/expert-consultation/nonexistent-id")
        assert response.status_code == 404

    def test_accept_consultation(self, client, mock_llm_engine):
        """Test accepting a consultation."""
        # Create consultation
        create_response = client.post(
            "/api/mode/expert-consultation",
            json={"question": "Test question"},
        )
        consultation_id = create_response.json()["id"]

        # Accept it
        response = client.post(
            f"/api/mode/expert-consultation/{consultation_id}/feedback",
            json={"accepted": True, "reason": "Helpful response"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "accepted"
        assert data["feedback_recorded"] is True

    def test_reject_consultation(self, client, mock_llm_engine):
        """Test rejecting a consultation."""
        # Create consultation
        create_response = client.post(
            "/api/mode/expert-consultation",
            json={"question": "Test question"},
        )
        consultation_id = create_response.json()["id"]

        # Reject it
        response = client.post(
            f"/api/mode/expert-consultation/{consultation_id}/feedback",
            json={"accepted": False, "reason": "Not accurate"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "rejected"

    def test_feedback_nonexistent_consultation(self, client):
        """Test submitting feedback for nonexistent consultation."""
        response = client.post(
            "/api/mode/expert-consultation/nonexistent-id/feedback",
            json={"accepted": True},
        )
        assert response.status_code == 404


class TestModeStatistics:
    """Test mode statistics endpoint."""

    def test_get_statistics_empty(self, client):
        """Test getting statistics with no consultations."""
        response = client.get("/api/mode/statistics")
        assert response.status_code == 200
        data = response.json()
        assert data["total_consultations"] == 0
        assert data["acceptance_rate"] is None
        assert data["average_confidence"] is None

    def test_get_statistics_with_data(self, client):
        """Test getting statistics with consultations."""
        # Add some test consultations directly
        import src.api.mode as mode_module
        from datetime import datetime

        mode_module._consultations["test-1"] = {
            "id": "test-1",
            "question": "Q1",
            "context": "",
            "response": "R1",
            "sources": [],
            "confidence": "high",
            "confidence_score": 0.9,
            "status": ConsultationStatus.ACCEPTED,
            "timestamp": datetime.utcnow(),
            "rag_context_count": 2,
            "inference_time_ms": 100,
            "verification_notes": [],
        }
        mode_module._consultations["test-2"] = {
            "id": "test-2",
            "question": "Q2",
            "context": "",
            "response": "R2",
            "sources": [],
            "confidence": "medium",
            "confidence_score": 0.65,
            "status": ConsultationStatus.REJECTED,
            "timestamp": datetime.utcnow(),
            "rag_context_count": 1,
            "inference_time_ms": 150,
            "verification_notes": [],
        }

        response = client.get("/api/mode/statistics")
        assert response.status_code == 200
        data = response.json()
        assert data["total_consultations"] == 2
        assert data["acceptance_rate"] == 0.5  # 1 accepted, 1 rejected
        assert "average_confidence" in data
        assert "confidence_distribution" in data


class TestModeEnforcementMiddleware:
    """Test mode enforcement middleware functionality."""

    def test_llm_endpoint_blocked_in_no_llm_mode(self, client):
        """Test that LLM endpoints are blocked in No-LLM mode."""
        # Set to No-LLM mode
        client.post("/api/mode/set?mode=no-llm")

        # Try to access chat endpoint with No-LLM mode header
        response = client.post(
            "/api/chat/",
            json={"message": "Hello"},
            headers={"X-Interaction-Mode": "no-llm"},
        )
        assert response.status_code == 403
        data = response.json()
        assert data["error"] == "LLM_DISABLED"

    def test_llm_endpoint_allowed_in_llm_mode(self, client):
        """Test that LLM endpoints work in LLM mode."""
        # Should not be blocked (though may fail for other reasons like no LLM)
        response = client.post(
            "/api/chat/",
            json={"message": "Hello"},
            headers={"X-Interaction-Mode": "llm"},
        )
        # Should not be 403 - might be other error but not mode enforcement
        assert response.status_code != 403

    def test_consultation_endpoint_allowed_in_no_llm_mode(self, client):
        """Test that consultation endpoint is allowed in No-LLM mode."""
        # Set to No-LLM mode
        client.post("/api/mode/set?mode=no-llm")

        # Expert consultation should still work
        with patch("src.api.mode.get_llm_engine") as mock:
            engine = MagicMock()
            engine.generate = AsyncMock(return_value=MagicMock(
                content="Mock response",
                model="mock",
                confidence=MagicMock(value="high"),
                sources=[],
                rag_context=None,
                inference_time_ms=50,
            ))
            mock.return_value = engine

            response = client.post(
                "/api/mode/expert-consultation",
                json={"question": "Test"},
                headers={"X-Interaction-Mode": "no-llm"},
            )
            assert response.status_code == 200

    def test_simulation_endpoints_allowed_in_no_llm_mode(self, client):
        """Test that simulation endpoints work in No-LLM mode."""
        response = client.get(
            "/api/simulation/templates",
            headers={"X-Interaction-Mode": "no-llm"},
        )
        # Should not be blocked by mode enforcement
        assert response.status_code != 403


class TestScenarioExecution:
    """Test scenario execution produces valid output."""

    def test_execute_scenario_creates_home(self, client):
        """Test that scenario execution creates a home configuration."""
        response = client.post("/api/mode/scenarios/basic-attack-detection/execute")
        assert response.status_code == 200
        data = response.json()

        # Check home was created
        assert "results" in data
        results = data["results"]
        assert "home" in results
        home = results["home"]
        assert "id" in home
        assert "rooms" in home
        assert "devices" in home

    def test_execute_scenario_configures_threats(self, client):
        """Test that scenario execution configures threats."""
        response = client.post("/api/mode/scenarios/basic-attack-detection/execute")
        assert response.status_code == 200
        data = response.json()

        results = data["results"]
        assert "threats" in results
        threats = results["threats"]
        assert "configured_threats" in threats

    def test_execute_different_scenarios(self, client):
        """Test executing different scenarios produces different configs."""
        response1 = client.post("/api/mode/scenarios/basic-attack-detection/execute")
        response2 = client.post("/api/mode/scenarios/apt-simulation/execute")

        assert response1.status_code == 200
        assert response2.status_code == 200

        data1 = response1.json()
        data2 = response2.json()

        # Different scenarios should have different configurations
        assert data1["scenario_name"] != data2["scenario_name"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
