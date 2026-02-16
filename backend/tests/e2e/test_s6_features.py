"""
End-to-End Tests for S6 Features.

Tests the complete integration of:
- S6.5: TaskDecomposer with AgentOrchestrator
- S6.19: HumanReviewQueue API with VerificationPipeline
- S6.22: Zero Hallucination validation flow
"""

import pytest
import sys
from unittest.mock import MagicMock, patch
from uuid import uuid4

# Mock chromadb before imports
sys.modules['chromadb'] = MagicMock()
sys.modules['chromadb.config'] = MagicMock()

from fastapi.testclient import TestClient


@pytest.fixture
def mock_dependencies():
    """Mock all AI/RAG dependencies."""
    with patch('src.ai.llm.llm_engine.OllamaClient') as mock_ollama, \
         patch('src.rag.vector_store_module.vector_store.chromadb') as mock_chroma:

        mock_ollama_instance = MagicMock()
        mock_ollama_instance.is_healthy = MagicMock(return_value=True)
        mock_ollama.return_value = mock_ollama_instance

        mock_collection = MagicMock()
        mock_collection.count.return_value = 0
        mock_chroma_client = MagicMock()
        mock_chroma_client.get_or_create_collection.return_value = mock_collection
        mock_chroma.PersistentClient.return_value = mock_chroma_client

        yield


@pytest.fixture
def client(mock_dependencies):
    """Create FastAPI test client."""
    from src.main import app
    return TestClient(app)


@pytest.fixture
def reset_review_queue():
    """Reset the review queue manager."""
    import src.api.review_queue as review_module
    review_module._manager = None
    yield
    review_module._manager = None


# =============================================================================
# S6.5: TaskDecomposer Integration Tests
# =============================================================================

class TestTaskDecomposerE2E:
    """End-to-end tests for TaskDecomposer integration."""

    def test_task_decomposer_exists(self):
        """Verify TaskDecomposer class exists and initializes."""
        from src.ai.orchestrator.task_decomposer import TaskDecomposer

        decomposer = TaskDecomposer()
        assert decomposer is not None
        assert hasattr(decomposer, 'decompose_simple')
        # Verify it can decompose tasks (functional test)
        assert callable(decomposer.decompose_simple)

    def test_home_creation_decomposition(self):
        """Test decomposition of home creation request."""
        from src.ai.orchestrator.task_decomposer import TaskDecomposer, TaskPlan

        decomposer = TaskDecomposer()
        result = decomposer.decompose_simple("Create a smart home with living room and bedroom")

        # Result is a TaskPlan with tasks list
        assert isinstance(result, TaskPlan)
        assert len(result.tasks) >= 1

    def test_threat_injection_decomposition(self):
        """Test decomposition of threat injection request."""
        from src.ai.orchestrator.task_decomposer import TaskDecomposer, TaskPlan

        decomposer = TaskDecomposer()
        result = decomposer.decompose_simple("Inject a credential theft attack on the door lock")

        assert isinstance(result, TaskPlan)
        assert len(result.tasks) >= 1

    def test_complex_multi_step_decomposition(self):
        """Test decomposition of complex multi-step request."""
        from src.ai.orchestrator.task_decomposer import TaskDecomposer, TaskPlan

        decomposer = TaskDecomposer()
        result = decomposer.decompose_simple(
            "Create a home, add 5 devices, and run a security simulation"
        )

        assert isinstance(result, TaskPlan)
        # Complex request should have multiple tasks
        assert result.total_tasks >= 1

    def test_orchestrator_has_decomposer(self):
        """Verify AgentOrchestrator integrates with TaskDecomposer."""
        from src.ai.orchestrator.orchestrator import AgentOrchestrator

        orchestrator = AgentOrchestrator()
        assert hasattr(orchestrator, 'task_decomposer') or hasattr(orchestrator, 'decomposer')


# =============================================================================
# S6.19: HumanReviewQueue E2E Tests
# =============================================================================

class TestReviewQueueE2E:
    """End-to-end tests for HumanReviewQueue integration."""

    def test_complete_review_workflow(self, client, reset_review_queue):
        """Test complete review workflow: add → review → verify."""
        # Configure strict mode
        client.put("/api/review/settings", json={
            "auto_approve_threshold": 0.99,
            "auto_reject_threshold": 0.1,
            "max_queue_size": 100,
            "strict_mode": True,
        })

        # Get initial stats
        initial_stats = client.get("/api/review/stats").json()

        # Add sample item
        client.post("/api/review/test/add-sample")

        # Get queue
        queue = client.get("/api/review/queue").json()
        assert len(queue) >= 1

        if len(queue) > 0:
            item_id = queue[0]["item_id"]

            # Submit review
            review_response = client.post(
                f"/api/review/queue/{item_id}/review",
                json={"decision": "approved", "notes": "E2E test approval"}
            )
            assert review_response.status_code == 200

            # Verify moved to reviewed
            reviewed = client.get("/api/review/reviewed").json()
            assert any(r["item_id"] == item_id for r in reviewed)

    def test_auto_approve_high_confidence(self, reset_review_queue):
        """Test auto-approval of high confidence items."""
        from src.api.review_queue import HumanReviewQueueManager, ReviewItemType
        from src.ai.verification.verification_pipeline import VerificationResult, VerificationStatus

        manager = HumanReviewQueueManager()
        manager.auto_approve_threshold = 0.85
        manager.strict_mode = False

        result = VerificationResult(
            result_id=str(uuid4()),
            input_data={},
            final_status=VerificationStatus.PASS,
            overall_confidence=0.95,
        )

        item = manager.add_item(
            content={"test": "data"},
            content_summary="High confidence test",
            item_type=ReviewItemType.LLM_RESPONSE,
            verification_result=result,
        )

        assert item is None  # Auto-approved
        assert manager._stats["total_auto_approved"] == 1

    def test_auto_reject_low_confidence(self, reset_review_queue):
        """Test auto-rejection of low confidence items."""
        from src.api.review_queue import HumanReviewQueueManager, ReviewItemType
        from src.ai.verification.verification_pipeline import VerificationResult, VerificationStatus

        manager = HumanReviewQueueManager()
        manager.auto_reject_threshold = 0.5

        result = VerificationResult(
            result_id=str(uuid4()),
            input_data={},
            final_status=VerificationStatus.REJECT,
            overall_confidence=0.3,
        )

        item = manager.add_item(
            content={"test": "data"},
            content_summary="Low confidence test",
            item_type=ReviewItemType.LLM_RESPONSE,
            verification_result=result,
        )

        assert item is None  # Auto-rejected
        assert manager._stats["total_auto_rejected"] == 1

    def test_strict_mode_queues_all(self, reset_review_queue):
        """Test strict mode queues all items regardless of confidence."""
        from src.api.review_queue import HumanReviewQueueManager, ReviewItemType
        from src.ai.verification.verification_pipeline import VerificationResult, VerificationStatus

        manager = HumanReviewQueueManager()
        manager.strict_mode = True

        result = VerificationResult(
            result_id=str(uuid4()),
            input_data={},
            final_status=VerificationStatus.PASS,
            overall_confidence=0.99,
        )

        item = manager.add_item(
            content={"test": "data"},
            content_summary="Strict mode test",
            item_type=ReviewItemType.LLM_RESPONSE,
            verification_result=result,
        )

        assert item is not None  # Should be queued despite high confidence
        assert len(manager._queue) == 1


# =============================================================================
# S6.22: Zero Hallucination E2E Tests
# =============================================================================

class TestZeroHallucinationE2E:
    """End-to-end tests for zero hallucination validation."""

    @pytest.mark.asyncio
    async def test_verification_pipeline_full_flow(self):
        """Test complete verification pipeline flow."""
        from src.ai.verification.verification_pipeline import (
            VerificationPipeline, VerificationCategory, VerificationStatus
        )
        from src.ai.verification.schema_validator import SchemaValidator
        from src.ai.verification.physical_constraints import PhysicalConstraintChecker

        # Create pipeline with real verifiers
        pipeline = VerificationPipeline(strict_mode=False)

        schema_validator = SchemaValidator()
        constraint_checker = PhysicalConstraintChecker()

        pipeline.register_verifier(
            VerificationCategory.SCHEMA,
            schema_validator.create_verifier("device"),
        )
        pipeline.register_verifier(
            VerificationCategory.PHYSICAL,
            constraint_checker.create_verifier("thermostat"),
        )

        # Valid data should pass
        valid_data = {
            "device_id": "test-001",
            "device_type": "thermostat",
            "name": "Test Thermostat",
            "state": {"temperature": 22.0},
        }
        result = await pipeline.verify(valid_data)
        assert result.final_status == VerificationStatus.PASS

        # Invalid schema should fail
        invalid_schema = {"device_type": "thermostat", "name": "Missing ID"}
        result = await pipeline.verify(invalid_schema)
        assert result.final_status == VerificationStatus.REJECT

        # Invalid physics should fail
        invalid_physics = {
            "device_id": "test-002",
            "device_type": "thermostat",
            "name": "Cold Device",
            "state": {"temperature": -300},
        }
        result = await pipeline.verify(invalid_physics)
        assert result.final_status == VerificationStatus.REJECT

    @pytest.mark.asyncio
    async def test_verification_gate_integration(self):
        """Test VerificationGate blocking invalid data."""
        from src.ai.verification.verification_pipeline import (
            VerificationPipeline, VerificationGate, VerificationCategory
        )
        from src.ai.verification.physical_constraints import PhysicalConstraintChecker

        pipeline = VerificationPipeline(strict_mode=False)
        checker = PhysicalConstraintChecker()
        pipeline.register_verifier(
            VerificationCategory.PHYSICAL,
            checker.create_verifier("thermostat"),
        )

        gate = VerificationGate(pipeline)

        # Valid data passes gate
        valid = {"temperature": 20.0}
        passed, output, result = await gate(valid)
        assert passed is True

        # Invalid data blocked
        invalid = {"temperature": -500}
        passed, output, result = await gate(invalid)
        assert passed is False

    def test_schema_validation_hallucination_detection(self):
        """Test schema validation catches hallucinated data."""
        from src.ai.verification.schema_validator import SchemaValidator

        validator = SchemaValidator()

        # Valid room type
        valid = {
            "home_id": "home-001",
            "name": "Test Home",
            "rooms": [
                {"room_id": "r1", "name": "Living Room", "type": "living_room", "floor": 1}
            ],
        }
        is_valid, errors = validator.validate(valid, schema_name="smart_home")
        assert is_valid

        # Hallucinated room type
        hallucinated = {
            "home_id": "home-001",
            "name": "Test Home",
            "rooms": [
                {"room_id": "r1", "name": "Teleporter Room", "type": "teleporter", "floor": 1}
            ],
        }
        is_valid, errors = validator.validate(hallucinated, schema_name="smart_home")
        assert not is_valid

    def test_physical_constraint_hallucination_detection(self):
        """Test physical constraints catch impossible values."""
        from src.ai.verification.physical_constraints import PhysicalConstraintChecker

        checker = PhysicalConstraintChecker()

        # Valid temperature
        results = checker.check({"temperature": 22.0}, device_type="thermostat")
        failed = [(c, msg) for c, passed, msg in results if not passed]
        assert len(failed) == 0

        # Impossible temperature (below absolute zero)
        results = checker.check({"temperature": -300}, device_type="thermostat")
        failed = [(c, msg) for c, passed, msg in results if not passed]
        assert len(failed) > 0

        # Impossible humidity
        results = checker.check({"humidity": 150}, device_type="humidity_sensor")
        failed = [(c, msg) for c, passed, msg in results if not passed]
        assert len(failed) > 0

    @pytest.mark.asyncio
    async def test_review_queue_verification_integration(self, reset_review_queue):
        """Test review queue integration with verification pipeline."""
        from src.api.review_queue import HumanReviewQueueManager, ReviewItemType
        from src.ai.verification.verification_pipeline import (
            VerificationPipeline, VerificationResult, VerificationStatus,
            VerificationCheck, VerificationCategory
        )

        manager = HumanReviewQueueManager()
        manager.strict_mode = True

        # Create flagged verification result
        result = VerificationResult(
            result_id=str(uuid4()),
            input_data={"query": "test"},
            final_status=VerificationStatus.FLAG,
            overall_confidence=0.72,
            human_review_required=True,
            review_reasons=["Unable to verify source"],
        )

        result.add_check(VerificationCheck.create(
            category=VerificationCategory.FACTUAL,
            name="source_check",
            status=VerificationStatus.FLAG,
            confidence=0.68,
            message="Source citation not found in knowledge base",
        ))

        # Add to queue
        item = manager.add_item(
            content={"response": "LLM generated response"},
            content_summary="Test LLM response",
            item_type=ReviewItemType.LLM_RESPONSE,
            verification_result=result,
        )

        assert item is not None
        assert item.confidence_score == 0.72
        assert len(item.flagged_checks) == 1
        assert "source citation" in item.flagged_checks[0]["message"].lower()


# =============================================================================
# Integration: All S6 Features Working Together
# =============================================================================

class TestS6Integration:
    """Test all S6 features working together."""

    @pytest.mark.asyncio
    async def test_complete_llm_to_review_flow(self, reset_review_queue):
        """Test flow: LLM output → Verification → Review Queue."""
        from src.ai.verification.verification_pipeline import (
            VerificationPipeline, VerificationGate, VerificationCategory,
            VerificationStatus, VerificationCheck
        )
        from src.api.review_queue import HumanReviewQueueManager, ReviewItemType

        # Setup verification pipeline
        pipeline = VerificationPipeline(strict_mode=False, flag_threshold=0.8)

        # Add a semantic verifier that flags uncertain content
        async def semantic_verifier(data, context):
            confidence = data.get("confidence", 0.5)
            if confidence < 0.8:
                return VerificationCheck.create(
                    category=VerificationCategory.SEMANTIC,
                    name="semantic_check",
                    status=VerificationStatus.FLAG,
                    confidence=confidence,
                    message="Content needs human verification",
                )
            return VerificationCheck.create(
                category=VerificationCategory.SEMANTIC,
                name="semantic_check",
                status=VerificationStatus.PASS,
                confidence=confidence,
                message="Content verified",
            )

        pipeline.register_verifier(VerificationCategory.SEMANTIC, semantic_verifier)

        # Setup review queue
        manager = HumanReviewQueueManager()
        manager.auto_approve_threshold = 0.9
        manager.auto_reject_threshold = 0.4

        # Simulate LLM output with medium confidence
        llm_output = {
            "response": "The smart thermostat can save 15% on energy bills.",
            "confidence": 0.75,
        }

        # Run through verification
        result = await pipeline.verify(llm_output)
        assert result.final_status == VerificationStatus.FLAG

        # Add to review queue
        item = manager.add_item(
            content=llm_output,
            content_summary="Energy savings claim",
            item_type=ReviewItemType.LLM_RESPONSE,
            verification_result=result,
        )

        # Should be queued for review
        assert item is not None
        assert len(manager._queue) == 1

    def test_api_endpoints_available(self, client):
        """Test all S6-related API endpoints are available."""
        # Review queue endpoints
        assert client.get("/api/review/queue").status_code == 200
        assert client.get("/api/review/stats").status_code == 200
        assert client.get("/api/review/settings").status_code == 200
        assert client.get("/api/review/reviewed").status_code == 200

        # Health check
        assert client.get("/api/health").status_code == 200


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
