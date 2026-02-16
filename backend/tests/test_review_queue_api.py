"""
Tests for Human Review Queue API (S6.19).

Comprehensive tests for the review queue backend functionality including:
- Queue management
- Review submissions
- Settings management
- Statistics tracking
- Integration with verification pipeline
"""

import pytest
import sys
from unittest.mock import MagicMock, patch
from datetime import datetime

# Mock chromadb before imports
sys.modules['chromadb'] = MagicMock()
sys.modules['chromadb.config'] = MagicMock()

from fastapi.testclient import TestClient


@pytest.fixture
def mock_dependencies():
    """Mock all dependencies."""
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
def reset_queue():
    """Reset the review queue manager before each test."""
    from src.api.review_queue import _manager
    import src.api.review_queue as review_module
    review_module._manager = None
    yield
    review_module._manager = None


class TestReviewQueueEndpoints:
    """Test review queue API endpoints."""

    def test_get_empty_queue(self, client, reset_queue):
        """Get queue when empty should return empty list."""
        response = client.get("/api/review/queue")
        assert response.status_code == 200
        assert response.json() == []

    def test_get_queue_stats_initial(self, client, reset_queue):
        """Get initial stats should show zeros."""
        response = client.get("/api/review/stats")
        assert response.status_code == 200
        data = response.json()
        assert data["total_items"] == 0
        assert data["pending_items"] == 0
        assert data["approved_items"] == 0
        assert data["rejected_items"] == 0

    def test_get_default_settings(self, client, reset_queue):
        """Get default settings."""
        response = client.get("/api/review/settings")
        assert response.status_code == 200
        data = response.json()
        assert "auto_approve_threshold" in data
        assert "auto_reject_threshold" in data
        assert "max_queue_size" in data
        assert "strict_mode" in data

    def test_update_settings(self, client, reset_queue):
        """Update queue settings."""
        new_settings = {
            "auto_approve_threshold": 0.9,
            "auto_reject_threshold": 0.4,
            "max_queue_size": 50,
            "strict_mode": True,
        }
        response = client.put("/api/review/settings", json=new_settings)
        assert response.status_code == 200
        data = response.json()
        assert data["auto_approve_threshold"] == 0.9
        assert data["auto_reject_threshold"] == 0.4
        assert data["strict_mode"] is True

    def test_add_sample_item(self, client, reset_queue):
        """Add a sample review item for testing."""
        response = client.post("/api/review/test/add-sample")
        assert response.status_code == 200
        data = response.json()
        assert "message" in data

    def test_add_sample_and_get_queue(self, client, reset_queue):
        """Add sample item and verify it appears in queue."""
        # First enable strict mode to ensure item is queued
        client.put("/api/review/settings", json={
            "auto_approve_threshold": 0.99,
            "auto_reject_threshold": 0.1,
            "max_queue_size": 100,
            "strict_mode": True,
        })

        # Add sample item
        add_response = client.post("/api/review/test/add-sample")
        assert add_response.status_code == 200

        # Get queue
        queue_response = client.get("/api/review/queue")
        assert queue_response.status_code == 200
        items = queue_response.json()
        assert len(items) >= 1

    def test_get_specific_item(self, client, reset_queue):
        """Get a specific review item by ID."""
        # Enable strict mode and add sample
        client.put("/api/review/settings", json={
            "auto_approve_threshold": 0.99,
            "auto_reject_threshold": 0.1,
            "max_queue_size": 100,
            "strict_mode": True,
        })
        client.post("/api/review/test/add-sample")

        # Get queue to find item ID
        queue = client.get("/api/review/queue").json()
        if len(queue) > 0:
            item_id = queue[0]["item_id"]
            response = client.get(f"/api/review/queue/{item_id}")
            assert response.status_code == 200
            assert response.json()["item_id"] == item_id

    def test_get_nonexistent_item(self, client, reset_queue):
        """Get non-existent item should return 404."""
        response = client.get("/api/review/queue/nonexistent-id")
        assert response.status_code == 404

    def test_submit_review_approve(self, client, reset_queue):
        """Submit an approval review."""
        # Setup and add sample
        client.put("/api/review/settings", json={
            "auto_approve_threshold": 0.99,
            "auto_reject_threshold": 0.1,
            "max_queue_size": 100,
            "strict_mode": True,
        })
        client.post("/api/review/test/add-sample")

        # Get queue
        queue = client.get("/api/review/queue").json()
        if len(queue) > 0:
            item_id = queue[0]["item_id"]

            # Submit approval
            response = client.post(f"/api/review/queue/{item_id}/review", json={
                "decision": "approved",
                "notes": "Verified as accurate",
            })
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "approved"
            assert data["reviewer_notes"] == "Verified as accurate"

    def test_submit_review_reject(self, client, reset_queue):
        """Submit a rejection review."""
        client.put("/api/review/settings", json={
            "auto_approve_threshold": 0.99,
            "auto_reject_threshold": 0.1,
            "max_queue_size": 100,
            "strict_mode": True,
        })
        client.post("/api/review/test/add-sample")

        queue = client.get("/api/review/queue").json()
        if len(queue) > 0:
            item_id = queue[0]["item_id"]

            response = client.post(f"/api/review/queue/{item_id}/review", json={
                "decision": "rejected",
                "notes": "Contains factual errors",
            })
            assert response.status_code == 200
            assert response.json()["status"] == "rejected"

    def test_submit_review_modified(self, client, reset_queue):
        """Submit a modified review with corrections."""
        client.put("/api/review/settings", json={
            "auto_approve_threshold": 0.99,
            "auto_reject_threshold": 0.1,
            "max_queue_size": 100,
            "strict_mode": True,
        })
        client.post("/api/review/test/add-sample")

        queue = client.get("/api/review/queue").json()
        if len(queue) > 0:
            item_id = queue[0]["item_id"]

            response = client.post(f"/api/review/queue/{item_id}/review", json={
                "decision": "modified",
                "notes": "Corrected inaccurate claim",
                "modified_content": {"corrected": "response here"},
            })
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "modified"
            assert data["modified_content"] is not None

    def test_get_reviewed_items(self, client, reset_queue):
        """Get list of reviewed items."""
        response = client.get("/api/review/reviewed")
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_clear_reviewed_items(self, client, reset_queue):
        """Clear reviewed items."""
        response = client.delete("/api/review/reviewed")
        assert response.status_code == 200
        assert "Cleared" in response.json()["message"]

    def test_stats_update_after_review(self, client, reset_queue):
        """Stats should update after reviews."""
        # Setup
        client.put("/api/review/settings", json={
            "auto_approve_threshold": 0.99,
            "auto_reject_threshold": 0.1,
            "max_queue_size": 100,
            "strict_mode": True,
        })

        # Add and approve an item
        client.post("/api/review/test/add-sample")
        queue = client.get("/api/review/queue").json()

        if len(queue) > 0:
            item_id = queue[0]["item_id"]
            client.post(f"/api/review/queue/{item_id}/review", json={
                "decision": "approved",
                "notes": "OK",
            })

            # Check stats
            stats = client.get("/api/review/stats").json()
            assert stats["approved_items"] >= 1


class TestReviewQueueManager:
    """Test the HumanReviewQueueManager class directly."""

    def test_manager_initialization(self):
        """Manager should initialize with defaults."""
        from src.api.review_queue import HumanReviewQueueManager

        manager = HumanReviewQueueManager(max_size=50)
        assert manager.max_size == 50
        assert len(manager._queue) == 0

    def test_add_item_with_low_confidence(self):
        """Items with very low confidence should be auto-rejected."""
        from src.api.review_queue import (
            HumanReviewQueueManager,
            ReviewItemType,
        )
        from src.ai.verification.verification_pipeline import (
            VerificationResult,
            VerificationStatus,
        )
        from uuid import uuid4

        manager = HumanReviewQueueManager()
        manager.auto_reject_threshold = 0.5

        # Create low confidence result
        result = VerificationResult(
            result_id=str(uuid4()),
            input_data={"test": "data"},
            final_status=VerificationStatus.REJECT,
            overall_confidence=0.3,  # Below threshold
        )

        item = manager.add_item(
            content={"test": "content"},
            content_summary="Test item",
            item_type=ReviewItemType.LLM_RESPONSE,
            verification_result=result,
        )

        # Should be auto-rejected (returns None)
        assert item is None
        assert manager._stats["total_auto_rejected"] == 1

    def test_add_item_with_high_confidence(self):
        """Items with high confidence should be auto-approved."""
        from src.api.review_queue import (
            HumanReviewQueueManager,
            ReviewItemType,
        )
        from src.ai.verification.verification_pipeline import (
            VerificationResult,
            VerificationStatus,
        )
        from uuid import uuid4

        manager = HumanReviewQueueManager()
        manager.auto_approve_threshold = 0.85
        manager.strict_mode = False

        # Create high confidence result
        result = VerificationResult(
            result_id=str(uuid4()),
            input_data={"test": "data"},
            final_status=VerificationStatus.PASS,
            overall_confidence=0.95,  # Above threshold
        )

        item = manager.add_item(
            content={"test": "content"},
            content_summary="Test item",
            item_type=ReviewItemType.LLM_RESPONSE,
            verification_result=result,
        )

        # Should be auto-approved (returns None)
        assert item is None
        assert manager._stats["total_auto_approved"] == 1

    def test_add_item_medium_confidence_queued(self):
        """Items with medium confidence should be queued for review."""
        from src.api.review_queue import (
            HumanReviewQueueManager,
            ReviewItemType,
            ReviewItemStatus,
        )
        from src.ai.verification.verification_pipeline import (
            VerificationResult,
            VerificationStatus,
        )
        from uuid import uuid4

        manager = HumanReviewQueueManager()
        manager.auto_approve_threshold = 0.85
        manager.auto_reject_threshold = 0.5
        manager.strict_mode = False

        # Create medium confidence result
        result = VerificationResult(
            result_id=str(uuid4()),
            input_data={"test": "data"},
            final_status=VerificationStatus.FLAG,
            overall_confidence=0.72,  # Between thresholds
            human_review_required=True,
            review_reasons=["Uncertain about accuracy"],
        )

        item = manager.add_item(
            content={"test": "content"},
            content_summary="Test item",
            item_type=ReviewItemType.LLM_RESPONSE,
            verification_result=result,
        )

        # Should be queued
        assert item is not None
        assert item.status == ReviewItemStatus.PENDING
        assert item.confidence_score == 0.72
        assert len(manager._queue) == 1

    def test_strict_mode_queues_all(self):
        """In strict mode, all items should be queued."""
        from src.api.review_queue import (
            HumanReviewQueueManager,
            ReviewItemType,
        )
        from src.ai.verification.verification_pipeline import (
            VerificationResult,
            VerificationStatus,
        )
        from uuid import uuid4

        manager = HumanReviewQueueManager()
        manager.strict_mode = True

        # High confidence result
        result = VerificationResult(
            result_id=str(uuid4()),
            input_data={"test": "data"},
            final_status=VerificationStatus.PASS,
            overall_confidence=0.99,
        )

        item = manager.add_item(
            content={"test": "content"},
            content_summary="Test item",
            item_type=ReviewItemType.LLM_RESPONSE,
            verification_result=result,
        )

        # Should still be queued despite high confidence
        assert item is not None
        assert len(manager._queue) == 1

    def test_review_item_approve(self):
        """Review and approve an item."""
        from src.api.review_queue import (
            HumanReviewQueueManager,
            ReviewItemType,
            ReviewItemStatus,
            ReviewDecision,
        )
        from src.ai.verification.verification_pipeline import (
            VerificationResult,
            VerificationStatus,
        )
        from uuid import uuid4

        manager = HumanReviewQueueManager()
        manager.strict_mode = True

        result = VerificationResult(
            result_id=str(uuid4()),
            input_data={},
            final_status=VerificationStatus.FLAG,
            overall_confidence=0.75,
        )

        item = manager.add_item(
            content={"test": "content"},
            content_summary="Test",
            item_type=ReviewItemType.LLM_RESPONSE,
            verification_result=result,
        )

        # Review the item
        decision = ReviewDecision(
            decision=ReviewItemStatus.APPROVED,
            notes="Looks good",
        )
        reviewed = manager.review_item(item.item_id, decision)

        assert reviewed.status == ReviewItemStatus.APPROVED
        assert reviewed.reviewer_notes == "Looks good"
        assert reviewed.reviewed_at is not None
        assert len(manager._queue) == 0
        assert len(manager._reviewed) == 1

    def test_get_stats(self):
        """Get queue statistics."""
        from src.api.review_queue import HumanReviewQueueManager

        manager = HumanReviewQueueManager()
        stats = manager.get_stats()

        assert stats.total_items == 0
        assert stats.pending_items == 0
        assert stats.avg_confidence == 0.0


class TestReviewQueueModels:
    """Test Pydantic models for review queue."""

    def test_review_item_model(self):
        """ReviewItem model should validate correctly."""
        from src.api.review_queue import (
            ReviewItem,
            ReviewItemType,
            ReviewItemStatus,
        )

        item = ReviewItem(
            item_id="test-123",
            item_type=ReviewItemType.LLM_RESPONSE,
            status=ReviewItemStatus.PENDING,
            content={"data": "test"},
            content_summary="Test summary",
            confidence_score=0.75,
            verification_status="flag",
            created_at="2024-01-01T00:00:00Z",
        )

        assert item.item_id == "test-123"
        assert item.confidence_score == 0.75

    def test_review_decision_model(self):
        """ReviewDecision model should validate correctly."""
        from src.api.review_queue import (
            ReviewDecision,
            ReviewItemStatus,
        )

        decision = ReviewDecision(
            decision=ReviewItemStatus.APPROVED,
            notes="Verified",
        )

        assert decision.decision == ReviewItemStatus.APPROVED

    def test_review_queue_settings_validation(self):
        """ReviewQueueSettings should validate thresholds."""
        from src.api.review_queue import ReviewQueueSettings
        from pydantic import ValidationError

        # Valid settings
        settings = ReviewQueueSettings(
            auto_approve_threshold=0.9,
            auto_reject_threshold=0.4,
            max_queue_size=100,
            strict_mode=False,
        )
        assert settings.auto_approve_threshold == 0.9

        # Invalid threshold (over 1.0)
        with pytest.raises(ValidationError):
            ReviewQueueSettings(
                auto_approve_threshold=1.5,
                auto_reject_threshold=0.4,
                max_queue_size=100,
                strict_mode=False,
            )

        # Invalid queue size (too small)
        with pytest.raises(ValidationError):
            ReviewQueueSettings(
                auto_approve_threshold=0.9,
                auto_reject_threshold=0.4,
                max_queue_size=5,  # Below minimum of 10
                strict_mode=False,
            )


class TestVerificationIntegration:
    """Test integration with verification pipeline."""

    def test_flagged_checks_captured(self):
        """Flagged checks from verification should be captured."""
        from src.api.review_queue import (
            HumanReviewQueueManager,
            ReviewItemType,
        )
        from src.ai.verification.verification_pipeline import (
            VerificationResult,
            VerificationStatus,
            VerificationCheck,
            VerificationCategory,
        )
        from uuid import uuid4

        manager = HumanReviewQueueManager()
        manager.strict_mode = True

        result = VerificationResult(
            result_id=str(uuid4()),
            input_data={},
            final_status=VerificationStatus.FLAG,
            overall_confidence=0.72,
            human_review_required=True,
            review_reasons=["Uncertain source"],
        )

        # Add flagged check
        result.add_check(VerificationCheck.create(
            category=VerificationCategory.FACTUAL,
            name="source_check",
            status=VerificationStatus.FLAG,
            confidence=0.68,
            message="Unable to verify source",
        ))

        item = manager.add_item(
            content={"response": "test"},
            content_summary="Test response",
            item_type=ReviewItemType.LLM_RESPONSE,
            verification_result=result,
        )

        assert item is not None
        assert len(item.flagged_checks) == 1
        assert item.flagged_checks[0]["name"] == "source_check"
        assert item.review_reasons == ["Uncertain source"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
