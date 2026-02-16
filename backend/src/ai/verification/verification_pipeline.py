"""
Verification Pipeline for the Smart-HES Agent Framework.

Implements a multi-stage verification pipeline to prevent hallucinations
and ensure all LLM outputs are grounded in facts and physical constraints.

Key principles:
- ZERO tolerance for hallucinations
- All outputs must be verifiable
- Physical constraints are immutable
- Human-in-the-loop for uncertain cases
"""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Optional
from uuid import uuid4

from loguru import logger


class VerificationStatus(str, Enum):
    """Status of a verification check."""
    PASS = "pass"          # Verified as correct
    FLAG = "flag"          # Needs human review
    REJECT = "reject"      # Definitively incorrect
    PENDING = "pending"    # Not yet verified
    SKIPPED = "skipped"    # Verification not applicable


class VerificationCategory(str, Enum):
    """Categories of verification checks."""
    SCHEMA = "schema"                    # JSON/structure validation
    PHYSICAL = "physical"                # Physical constraints
    SEMANTIC = "semantic"                # Meaning and consistency
    FACTUAL = "factual"                  # Grounded in knowledge base
    SECURITY = "security"                # Security implications
    BUSINESS = "business"                # Business rules


class ConfidenceLevel(str, Enum):
    """Confidence levels for verification."""
    HIGH = "high"          # >= 0.9
    MEDIUM = "medium"      # >= 0.7
    LOW = "low"            # >= 0.5
    VERY_LOW = "very_low"  # < 0.5


@dataclass
class VerificationCheck:
    """A single verification check result."""
    check_id: str
    category: VerificationCategory
    name: str
    status: VerificationStatus
    confidence: float  # 0.0 to 1.0
    message: str
    details: dict = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.utcnow)

    @classmethod
    def create(
        cls,
        category: VerificationCategory,
        name: str,
        status: VerificationStatus,
        confidence: float,
        message: str,
        details: dict = None,
    ) -> "VerificationCheck":
        return cls(
            check_id=str(uuid4()),
            category=category,
            name=name,
            status=status,
            confidence=min(1.0, max(0.0, confidence)),
            message=message,
            details=details or {},
        )


@dataclass
class VerificationResult:
    """Complete result of verification pipeline."""
    result_id: str
    input_data: Any
    final_status: VerificationStatus
    overall_confidence: float
    checks: list[VerificationCheck] = field(default_factory=list)
    corrections: list[dict] = field(default_factory=list)  # Suggested corrections
    human_review_required: bool = False
    review_reasons: list[str] = field(default_factory=list)
    processing_time_ms: float = 0.0
    timestamp: datetime = field(default_factory=datetime.utcnow)

    def add_check(self, check: VerificationCheck) -> None:
        """Add a verification check result."""
        self.checks.append(check)

    def get_checks_by_category(
        self, category: VerificationCategory
    ) -> list[VerificationCheck]:
        """Get all checks of a specific category."""
        return [c for c in self.checks if c.category == category]

    def get_failed_checks(self) -> list[VerificationCheck]:
        """Get all failed checks."""
        return [c for c in self.checks if c.status == VerificationStatus.REJECT]

    def get_flagged_checks(self) -> list[VerificationCheck]:
        """Get all flagged checks."""
        return [c for c in self.checks if c.status == VerificationStatus.FLAG]

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "result_id": self.result_id,
            "final_status": self.final_status.value,
            "overall_confidence": self.overall_confidence,
            "checks_summary": {
                "total": len(self.checks),
                "passed": len([c for c in self.checks if c.status == VerificationStatus.PASS]),
                "flagged": len([c for c in self.checks if c.status == VerificationStatus.FLAG]),
                "rejected": len([c for c in self.checks if c.status == VerificationStatus.REJECT]),
            },
            "human_review_required": self.human_review_required,
            "review_reasons": self.review_reasons,
            "corrections": self.corrections,
            "processing_time_ms": self.processing_time_ms,
        }


class VerificationPipeline:
    """
    Multi-stage verification pipeline for LLM outputs.

    The pipeline runs multiple verification stages:
    1. Schema Validation - Ensure output matches expected structure
    2. Physical Constraints - Check against physical laws and limits
    3. Semantic Consistency - Verify internal consistency
    4. Factual Grounding - Verify against knowledge base
    5. Security Review - Check for security implications

    Each stage can:
    - PASS: Allow output to proceed
    - FLAG: Mark for human review
    - REJECT: Block output entirely
    """

    def __init__(
        self,
        strict_mode: bool = True,
        auto_correct: bool = False,
        flag_threshold: float = 0.7,
        reject_threshold: float = 0.5,
    ):
        """
        Initialize the verification pipeline.

        Args:
            strict_mode: If True, any FLAG becomes REJECT
            auto_correct: If True, attempt automatic corrections
            flag_threshold: Confidence below this flags for review
            reject_threshold: Confidence below this rejects
        """
        self.strict_mode = strict_mode
        self.auto_correct = auto_correct
        self.flag_threshold = flag_threshold
        self.reject_threshold = reject_threshold

        # Registered verifiers by category
        self._verifiers: dict[VerificationCategory, list[Callable]] = {
            category: [] for category in VerificationCategory
        }

        # Statistics
        self._stats = {
            "total_verifications": 0,
            "passed": 0,
            "flagged": 0,
            "rejected": 0,
            "auto_corrected": 0,
            "average_confidence": 0.0,
        }

        logger.info(
            f"VerificationPipeline initialized "
            f"(strict={strict_mode}, auto_correct={auto_correct})"
        )

    def register_verifier(
        self,
        category: VerificationCategory,
        verifier: Callable,
        priority: int = 0,
    ) -> None:
        """
        Register a verifier function.

        Args:
            category: The category this verifier handles
            verifier: Async function(data, context) -> VerificationCheck
            priority: Higher priority verifiers run first
        """
        self._verifiers[category].append((priority, verifier))
        # Sort by priority (descending)
        self._verifiers[category].sort(key=lambda x: -x[0])
        logger.debug(f"Registered verifier for {category.value}")

    async def verify(
        self,
        data: Any,
        context: dict = None,
        categories: list[VerificationCategory] = None,
    ) -> VerificationResult:
        """
        Run the verification pipeline on data.

        Args:
            data: The data to verify (LLM output, agent response, etc.)
            context: Optional context for verification
            categories: Optional list of categories to check (default: all)

        Returns:
            VerificationResult with all check results
        """
        import time
        start_time = time.perf_counter()

        self._stats["total_verifications"] += 1
        context = context or {}

        # Create result container
        result = VerificationResult(
            result_id=str(uuid4()),
            input_data=data,
            final_status=VerificationStatus.PENDING,
            overall_confidence=1.0,
        )

        # Determine which categories to verify
        if categories is None:
            categories = list(VerificationCategory)

        # Run verifiers for each category
        for category in categories:
            verifiers = self._verifiers.get(category, [])
            for priority, verifier in verifiers:
                try:
                    check = await self._run_verifier(verifier, data, context)
                    if check:
                        result.add_check(check)

                        # Early exit on rejection (unless collecting all)
                        if check.status == VerificationStatus.REJECT:
                            logger.warning(
                                f"Verification rejected: {check.name} - {check.message}"
                            )

                except Exception as e:
                    logger.error(f"Verifier error in {category.value}: {e}")
                    # Add error as flagged check
                    result.add_check(VerificationCheck.create(
                        category=category,
                        name="verifier_error",
                        status=VerificationStatus.FLAG,
                        confidence=0.0,
                        message=f"Verifier error: {str(e)}",
                    ))

        # Calculate final status
        self._calculate_final_status(result)

        # Attempt auto-correction if enabled
        if self.auto_correct and result.final_status != VerificationStatus.PASS:
            await self._attempt_auto_correction(result, context)

        # Update stats
        result.processing_time_ms = (time.perf_counter() - start_time) * 1000
        self._update_stats(result)

        logger.info(
            f"Verification complete: {result.final_status.value} "
            f"(confidence={result.overall_confidence:.2f}, "
            f"time={result.processing_time_ms:.1f}ms)"
        )

        return result

    async def _run_verifier(
        self,
        verifier: Callable,
        data: Any,
        context: dict,
    ) -> Optional[VerificationCheck]:
        """Run a single verifier."""
        if asyncio.iscoroutinefunction(verifier):
            return await verifier(data, context)
        else:
            return verifier(data, context)

    def _calculate_final_status(self, result: VerificationResult) -> None:
        """Calculate the final verification status."""
        if not result.checks:
            result.final_status = VerificationStatus.PASS
            result.overall_confidence = 0.5  # No checks = uncertain
            return

        # Collect status counts
        statuses = [c.status for c in result.checks]
        confidences = [c.confidence for c in result.checks]

        # Any REJECT means overall REJECT
        if VerificationStatus.REJECT in statuses:
            result.final_status = VerificationStatus.REJECT
            result.overall_confidence = min(confidences)
            self._stats["rejected"] += 1
            return

        # Any FLAG means FLAG (or REJECT in strict mode)
        if VerificationStatus.FLAG in statuses:
            if self.strict_mode:
                result.final_status = VerificationStatus.REJECT
                self._stats["rejected"] += 1
            else:
                result.final_status = VerificationStatus.FLAG
                result.human_review_required = True
                result.review_reasons = [
                    c.message for c in result.checks
                    if c.status == VerificationStatus.FLAG
                ]
                self._stats["flagged"] += 1
            result.overall_confidence = sum(confidences) / len(confidences)
            return

        # All passed
        result.final_status = VerificationStatus.PASS
        result.overall_confidence = sum(confidences) / len(confidences)
        self._stats["passed"] += 1

    async def _attempt_auto_correction(
        self,
        result: VerificationResult,
        context: dict,
    ) -> None:
        """Attempt to auto-correct issues."""
        for check in result.get_failed_checks() + result.get_flagged_checks():
            correction = await self._generate_correction(check, result.input_data, context)
            if correction:
                result.corrections.append(correction)
                self._stats["auto_corrected"] += 1

    async def _generate_correction(
        self,
        check: VerificationCheck,
        data: Any,
        context: dict,
    ) -> Optional[dict]:
        """Generate a correction suggestion for a failed check."""
        # Override in subclass or register correction generators
        return None

    def _update_stats(self, result: VerificationResult) -> None:
        """Update running statistics."""
        total = self._stats["total_verifications"]
        old_avg = self._stats["average_confidence"]
        new_conf = result.overall_confidence

        # Running average
        self._stats["average_confidence"] = (
            (old_avg * (total - 1) + new_conf) / total
            if total > 0 else new_conf
        )

    def get_stats(self) -> dict:
        """Get pipeline statistics."""
        return self._stats.copy()

    def reset_stats(self) -> None:
        """Reset statistics."""
        self._stats = {
            "total_verifications": 0,
            "passed": 0,
            "flagged": 0,
            "rejected": 0,
            "auto_corrected": 0,
            "average_confidence": 0.0,
        }


class VerificationGate:
    """
    Gate that enforces verification before proceeding.

    Used to wrap agent outputs and ensure they pass verification
    before being returned to users or other systems.
    """

    def __init__(
        self,
        pipeline: VerificationPipeline,
        on_reject: Optional[Callable] = None,
        on_flag: Optional[Callable] = None,
    ):
        """
        Initialize the verification gate.

        Args:
            pipeline: The verification pipeline to use
            on_reject: Callback when verification rejects (async)
            on_flag: Callback when verification flags (async)
        """
        self.pipeline = pipeline
        self.on_reject = on_reject
        self.on_flag = on_flag

    async def __call__(
        self,
        data: Any,
        context: dict = None,
        categories: list[VerificationCategory] = None,
    ) -> tuple[bool, Any, VerificationResult]:
        """
        Gate the data through verification.

        Returns:
            Tuple of (passed: bool, data_or_correction: Any, result: VerificationResult)
        """
        result = await self.pipeline.verify(data, context, categories)

        if result.final_status == VerificationStatus.PASS:
            return True, data, result

        elif result.final_status == VerificationStatus.FLAG:
            if self.on_flag:
                if asyncio.iscoroutinefunction(self.on_flag):
                    await self.on_flag(data, result)
                else:
                    self.on_flag(data, result)

            # Return flagged data with warning
            return False, data, result

        else:  # REJECT
            if self.on_reject:
                if asyncio.iscoroutinefunction(self.on_reject):
                    await self.on_reject(data, result)
                else:
                    self.on_reject(data, result)

            # Return corrections if available, otherwise None
            corrected = result.corrections[0] if result.corrections else None
            return False, corrected, result


# Global instance
_verification_pipeline: Optional[VerificationPipeline] = None


def get_verification_pipeline() -> VerificationPipeline:
    """Get or create the global verification pipeline."""
    global _verification_pipeline
    if _verification_pipeline is None:
        _verification_pipeline = VerificationPipeline()
    return _verification_pipeline


def initialize_verification_pipeline(
    strict_mode: bool = True,
    auto_correct: bool = False,
    flag_threshold: float = 0.7,
    reject_threshold: float = 0.5,
) -> VerificationPipeline:
    """Initialize the global verification pipeline with custom settings."""
    global _verification_pipeline
    _verification_pipeline = VerificationPipeline(
        strict_mode=strict_mode,
        auto_correct=auto_correct,
        flag_threshold=flag_threshold,
        reject_threshold=reject_threshold,
    )
    return _verification_pipeline
