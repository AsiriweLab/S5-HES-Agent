"""
Human Review Queue API

Provides endpoints for managing items that require human review
as part of the anti-hallucination verification pipeline.

Items are flagged for review when:
- Confidence score is below threshold but above rejection
- Verification pipeline flags semantic inconsistencies
- Source attribution cannot be verified
"""

from collections import deque
from datetime import datetime
from enum import Enum
from typing import Any, Optional
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from loguru import logger

from src.ai.verification.verification_pipeline import (
    VerificationResult,
)
from src.core.config import settings


router = APIRouter(prefix="/api/review")


# =============================================================================
# Models
# =============================================================================

class ReviewItemStatus(str, Enum):
    """Status of a review item."""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    MODIFIED = "modified"  # Approved with modifications


class ReviewItemType(str, Enum):
    """Type of content being reviewed."""
    LLM_RESPONSE = "llm_response"
    AGENT_OUTPUT = "agent_output"
    RAG_RESULT = "rag_result"
    HOME_CONFIG = "home_config"
    THREAT_SCENARIO = "threat_scenario"
    SIMULATION_RESULT = "simulation_result"


class ReviewItem(BaseModel):
    """An item in the human review queue."""
    item_id: str
    item_type: ReviewItemType
    status: ReviewItemStatus = ReviewItemStatus.PENDING

    # Content to review
    content: Any
    content_summary: str

    # Verification info
    confidence_score: float
    verification_status: str
    flagged_checks: list[dict] = Field(default_factory=list)
    review_reasons: list[str] = Field(default_factory=list)

    # Timestamps
    created_at: str
    reviewed_at: Optional[str] = None

    # Review result
    reviewer_notes: Optional[str] = None
    modified_content: Optional[Any] = None

    # Source tracking
    source_agent: Optional[str] = None
    session_id: Optional[str] = None
    request_context: Optional[str] = None


class ReviewDecision(BaseModel):
    """Decision made by human reviewer."""
    decision: ReviewItemStatus
    notes: Optional[str] = None
    modified_content: Optional[Any] = None


class ReviewQueueStats(BaseModel):
    """Statistics about the review queue."""
    total_items: int
    pending_items: int
    approved_items: int
    rejected_items: int
    modified_items: int
    avg_confidence: float
    oldest_pending_age_seconds: Optional[float] = None


class ReviewQueueSettings(BaseModel):
    """Settings for the review queue."""
    auto_approve_threshold: float = Field(
        default=0.85,
        ge=0.0,
        le=1.0,
        description="Auto-approve items above this confidence"
    )
    auto_reject_threshold: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Auto-reject items below this confidence"
    )
    max_queue_size: int = Field(
        default=100,
        ge=10,
        le=1000,
        description="Maximum items in queue"
    )
    strict_mode: bool = Field(
        default=False,
        description="Require review for ALL items"
    )


# =============================================================================
# Review Queue Manager
# =============================================================================

class HumanReviewQueueManager:
    """
    Manages the human review queue for verification flagged items.

    Integrates with VerificationPipeline to queue items that need
    human review before being returned to users.
    """

    def __init__(self, max_size: int = 100):
        self.max_size = max_size
        self._queue: deque[ReviewItem] = deque(maxlen=max_size)
        self._reviewed: deque[ReviewItem] = deque(maxlen=max_size * 2)

        # Settings
        self.auto_approve_threshold = settings.confidence_threshold_pass
        self.auto_reject_threshold = settings.confidence_threshold_flag
        self.strict_mode = settings.strict_verification_mode

        # Stats
        self._stats = {
            "total_added": 0,
            "total_approved": 0,
            "total_rejected": 0,
            "total_modified": 0,
            "total_auto_approved": 0,
            "total_auto_rejected": 0,
        }

        logger.info(
            f"HumanReviewQueueManager initialized "
            f"(max_size={max_size}, strict_mode={self.strict_mode})"
        )

    def add_item(
        self,
        content: Any,
        content_summary: str,
        item_type: ReviewItemType,
        verification_result: VerificationResult,
        source_agent: Optional[str] = None,
        session_id: Optional[str] = None,
        request_context: Optional[str] = None,
    ) -> Optional[ReviewItem]:
        """
        Add an item to the review queue.

        Returns the ReviewItem if queued, None if auto-approved/rejected.
        """
        confidence = verification_result.overall_confidence

        # Check for auto-approve (unless strict mode)
        if not self.strict_mode and confidence >= self.auto_approve_threshold:
            self._stats["total_auto_approved"] += 1
            logger.debug(f"Auto-approved item with confidence {confidence:.2f}")
            return None

        # Check for auto-reject
        if confidence < self.auto_reject_threshold:
            self._stats["total_auto_rejected"] += 1
            logger.debug(f"Auto-rejected item with confidence {confidence:.2f}")
            return None

        # Create review item
        item = ReviewItem(
            item_id=f"review-{uuid4().hex[:12]}",
            item_type=item_type,
            content=content,
            content_summary=content_summary[:200] if content_summary else "",
            confidence_score=confidence,
            verification_status=verification_result.final_status.value,
            flagged_checks=[
                {
                    "category": c.category.value,
                    "name": c.name,
                    "message": c.message,
                    "confidence": c.confidence,
                }
                for c in verification_result.get_flagged_checks()
            ],
            review_reasons=verification_result.review_reasons,
            created_at=datetime.utcnow().isoformat() + "Z",
            source_agent=source_agent,
            session_id=session_id,
            request_context=request_context,
        )

        self._queue.append(item)
        self._stats["total_added"] += 1

        logger.info(
            f"Added item to review queue: {item.item_id} "
            f"(confidence={confidence:.2f}, type={item_type.value})"
        )

        return item

    def get_pending_items(self, limit: int = 20) -> list[ReviewItem]:
        """Get pending items from the queue."""
        pending = [
            item for item in self._queue
            if item.status == ReviewItemStatus.PENDING
        ]
        return pending[:limit]

    def get_item(self, item_id: str) -> Optional[ReviewItem]:
        """Get a specific item by ID."""
        for item in list(self._queue) + list(self._reviewed):
            if item.item_id == item_id:
                return item
        return None

    def review_item(self, item_id: str, decision: ReviewDecision) -> ReviewItem:
        """
        Submit a review decision for an item.

        Args:
            item_id: The item to review
            decision: The review decision

        Returns:
            Updated ReviewItem

        Raises:
            HTTPException if item not found
        """
        # Find the item
        item = None
        for i, queued_item in enumerate(self._queue):
            if queued_item.item_id == item_id:
                item = queued_item
                break

        if not item:
            raise HTTPException(
                status_code=404,
                detail=f"Review item {item_id} not found"
            )

        # Update item
        item.status = decision.decision
        item.reviewed_at = datetime.utcnow().isoformat() + "Z"
        item.reviewer_notes = decision.notes

        if decision.modified_content is not None:
            item.modified_content = decision.modified_content
            item.status = ReviewItemStatus.MODIFIED

        # Update stats
        if decision.decision == ReviewItemStatus.APPROVED:
            self._stats["total_approved"] += 1
        elif decision.decision == ReviewItemStatus.REJECTED:
            self._stats["total_rejected"] += 1
        elif decision.decision == ReviewItemStatus.MODIFIED:
            self._stats["total_modified"] += 1

        # Move to reviewed list
        self._queue.remove(item)
        self._reviewed.append(item)

        logger.info(
            f"Reviewed item {item_id}: {decision.decision.value} "
            f"(notes: {decision.notes or 'none'})"
        )

        return item

    def get_stats(self) -> ReviewQueueStats:
        """Get queue statistics."""
        pending = [i for i in self._queue if i.status == ReviewItemStatus.PENDING]
        approved = self._stats["total_approved"]
        rejected = self._stats["total_rejected"]
        modified = self._stats["total_modified"]

        # Calculate average confidence
        all_items = list(self._queue) + list(self._reviewed)
        avg_confidence = (
            sum(i.confidence_score for i in all_items) / len(all_items)
            if all_items else 0.0
        )

        # Calculate oldest pending age
        oldest_age = None
        if pending:
            oldest = min(pending, key=lambda x: x.created_at)
            oldest_time = datetime.fromisoformat(oldest.created_at.replace("Z", "+00:00"))
            oldest_age = (datetime.utcnow().replace(tzinfo=oldest_time.tzinfo) - oldest_time).total_seconds()

        return ReviewQueueStats(
            total_items=len(self._queue) + len(self._reviewed),
            pending_items=len(pending),
            approved_items=approved,
            rejected_items=rejected,
            modified_items=modified,
            avg_confidence=round(avg_confidence, 3),
            oldest_pending_age_seconds=oldest_age,
        )

    def get_settings(self) -> ReviewQueueSettings:
        """Get current queue settings."""
        return ReviewQueueSettings(
            auto_approve_threshold=self.auto_approve_threshold,
            auto_reject_threshold=self.auto_reject_threshold,
            max_queue_size=self.max_size,
            strict_mode=self.strict_mode,
        )

    def update_settings(self, new_settings: ReviewQueueSettings) -> ReviewQueueSettings:
        """Update queue settings."""
        self.auto_approve_threshold = new_settings.auto_approve_threshold
        self.auto_reject_threshold = new_settings.auto_reject_threshold
        self.strict_mode = new_settings.strict_mode

        # Update max size (creates new deque if different)
        if new_settings.max_queue_size != self.max_size:
            self.max_size = new_settings.max_queue_size
            # Preserve existing items
            items = list(self._queue)
            self._queue = deque(items, maxlen=self.max_size)

        logger.info(f"Updated review queue settings: {new_settings}")
        return new_settings

    def clear_reviewed(self) -> int:
        """Clear all reviewed items. Returns count cleared."""
        count = len(self._reviewed)
        self._reviewed.clear()
        return count

    def get_recent_reviewed(self, limit: int = 20) -> list[ReviewItem]:
        """Get recently reviewed items."""
        return list(self._reviewed)[-limit:]


# =============================================================================
# Global Manager Instance
# =============================================================================

_manager: Optional[HumanReviewQueueManager] = None


def get_review_queue_manager() -> HumanReviewQueueManager:
    """Get or create the global review queue manager."""
    global _manager
    if _manager is None:
        _manager = HumanReviewQueueManager()
    return _manager


# =============================================================================
# API Endpoints
# =============================================================================

@router.get("/queue", response_model=list[ReviewItem])
async def get_review_queue(limit: int = 20):
    """
    Get pending items in the review queue.

    Items are sorted by creation time (oldest first).
    """
    manager = get_review_queue_manager()
    return manager.get_pending_items(limit=limit)


@router.get("/queue/{item_id}", response_model=ReviewItem)
async def get_review_item(item_id: str):
    """Get a specific review item by ID."""
    manager = get_review_queue_manager()
    item = manager.get_item(item_id)
    if not item:
        raise HTTPException(status_code=404, detail=f"Item {item_id} not found")
    return item


@router.post("/queue/{item_id}/review", response_model=ReviewItem)
async def submit_review(item_id: str, decision: ReviewDecision):
    """
    Submit a review decision for an item.

    - decision: approved, rejected, or modified
    - notes: Optional reviewer notes
    - modified_content: Required if decision is 'modified'
    """
    manager = get_review_queue_manager()
    return manager.review_item(item_id, decision)


@router.get("/stats", response_model=ReviewQueueStats)
async def get_queue_stats():
    """Get statistics about the review queue."""
    manager = get_review_queue_manager()
    return manager.get_stats()


@router.get("/settings", response_model=ReviewQueueSettings)
async def get_queue_settings():
    """Get current review queue settings."""
    manager = get_review_queue_manager()
    return manager.get_settings()


@router.put("/settings", response_model=ReviewQueueSettings)
async def update_queue_settings(new_settings: ReviewQueueSettings):
    """Update review queue settings."""
    manager = get_review_queue_manager()
    return manager.update_settings(new_settings)


@router.get("/reviewed", response_model=list[ReviewItem])
async def get_reviewed_items(limit: int = 20):
    """Get recently reviewed items."""
    manager = get_review_queue_manager()
    return manager.get_recent_reviewed(limit=limit)


@router.delete("/reviewed")
async def clear_reviewed_items():
    """Clear all reviewed items from history."""
    manager = get_review_queue_manager()
    count = manager.clear_reviewed()
    return {"message": f"Cleared {count} reviewed items"}
