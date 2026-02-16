"""
Differential Privacy Engine - Privacy-preserving data analysis for IoT.

Sprint 12 - S12.6: Add differential privacy (basic)

Features:
- Laplace mechanism for numeric queries
- Gaussian mechanism for advanced queries
- Exponential mechanism for categorical data
- Privacy budget tracking (epsilon accounting)
- Data anonymization utilities
- K-anonymity simulation
"""

import math
import random
import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Optional, Callable
from loguru import logger


class PrivacyMechanism(str, Enum):
    """Differential privacy mechanisms."""
    LAPLACE = "laplace"
    GAUSSIAN = "gaussian"
    EXPONENTIAL = "exponential"
    RANDOMIZED_RESPONSE = "randomized_response"


class AnonymizationMethod(str, Enum):
    """Data anonymization methods."""
    SUPPRESSION = "suppression"  # Remove identifying fields
    GENERALIZATION = "generalization"  # Reduce precision
    PSEUDONYMIZATION = "pseudonymization"  # Replace with pseudonyms
    PERTURBATION = "perturbation"  # Add noise
    AGGREGATION = "aggregation"  # Group data


@dataclass
class PrivacyBudget:
    """Privacy budget tracking per entity."""
    entity_id: str
    total_epsilon: float = 1.0  # Total privacy budget
    used_epsilon: float = 0.0
    total_delta: float = 1e-5  # For approximate DP
    used_delta: float = 0.0
    created_at: datetime = field(default_factory=datetime.now)
    reset_interval_hours: int = 24  # Budget reset interval
    last_reset: datetime = field(default_factory=datetime.now)
    query_count: int = 0

    @property
    def remaining_epsilon(self) -> float:
        """Get remaining epsilon budget."""
        return max(0, self.total_epsilon - self.used_epsilon)

    @property
    def remaining_delta(self) -> float:
        """Get remaining delta budget."""
        return max(0, self.total_delta - self.used_delta)

    def can_query(self, epsilon: float, delta: float = 0) -> bool:
        """Check if query can be made within budget."""
        return self.remaining_epsilon >= epsilon and self.remaining_delta >= delta

    def consume(self, epsilon: float, delta: float = 0) -> None:
        """Consume privacy budget."""
        self.used_epsilon += epsilon
        self.used_delta += delta
        self.query_count += 1

    def should_reset(self) -> bool:
        """Check if budget should be reset."""
        elapsed = datetime.now() - self.last_reset
        return elapsed > timedelta(hours=self.reset_interval_hours)

    def reset(self) -> None:
        """Reset the privacy budget."""
        self.used_epsilon = 0.0
        self.used_delta = 0.0
        self.query_count = 0
        self.last_reset = datetime.now()

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "entity_id": self.entity_id,
            "total_epsilon": self.total_epsilon,
            "used_epsilon": self.used_epsilon,
            "remaining_epsilon": self.remaining_epsilon,
            "total_delta": self.total_delta,
            "used_delta": self.used_delta,
            "remaining_delta": self.remaining_delta,
            "query_count": self.query_count,
            "created_at": self.created_at.isoformat(),
            "last_reset": self.last_reset.isoformat(),
        }


@dataclass
class PrivacyQuery:
    """Record of a privacy-preserving query."""
    query_id: str
    entity_id: str
    mechanism: PrivacyMechanism
    epsilon: float
    delta: float = 0.0
    sensitivity: float = 1.0
    original_result: Any = None  # Stored only for simulation/debugging
    noisy_result: Any = None
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class AnonymizedRecord:
    """An anonymized data record."""
    record_id: str
    original_id: str  # Hashed original ID
    method: AnonymizationMethod
    fields: dict[str, Any] = field(default_factory=dict)
    generalization_levels: dict[str, int] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class PrivacyConfig:
    """Differential privacy configuration."""
    default_epsilon: float = 0.1
    default_delta: float = 1e-5
    max_epsilon_per_query: float = 1.0
    global_budget_epsilon: float = 10.0
    global_budget_delta: float = 1e-4
    enable_budget_tracking: bool = True
    k_anonymity_k: int = 5  # Minimum group size for k-anonymity
    auto_reset_budgets: bool = True


class DifferentialPrivacy:
    """
    Differential Privacy engine for IoT data protection.

    Provides privacy-preserving mechanisms for querying sensitive
    smart home data while maintaining statistical utility.
    """

    def __init__(self, config: Optional[PrivacyConfig] = None):
        """
        Initialize differential privacy engine.

        Args:
            config: Privacy configuration
        """
        self.config = config or PrivacyConfig()

        # Budget tracking per entity
        self._budgets: dict[str, PrivacyBudget] = {}

        # Global budget
        self._global_budget = PrivacyBudget(
            entity_id="global",
            total_epsilon=self.config.global_budget_epsilon,
            total_delta=self.config.global_budget_delta,
        )

        # Query history
        self._queries: list[PrivacyQuery] = []

        # Pseudonym mappings
        self._pseudonyms: dict[str, str] = {}

        # Statistics
        self._stats = {
            "total_queries": 0,
            "laplace_queries": 0,
            "gaussian_queries": 0,
            "exponential_queries": 0,
            "budget_exceeded": 0,
            "anonymizations": 0,
        }

        logger.info("DifferentialPrivacy engine initialized")

    # ========== Core DP Mechanisms ==========

    def laplace_mechanism(
        self,
        value: float,
        sensitivity: float,
        epsilon: float,
        entity_id: Optional[str] = None,
    ) -> tuple[float, Optional[str]]:
        """
        Apply Laplace mechanism to a numeric value.

        Args:
            value: True value to protect
            sensitivity: Query sensitivity (max change from one record)
            epsilon: Privacy parameter (smaller = more private)
            entity_id: Entity to charge budget

        Returns:
            Tuple of (noisy_value, error_message)
        """
        if not self._check_and_consume_budget(entity_id, epsilon, 0):
            return value, "Privacy budget exceeded"

        # Laplace noise: scale = sensitivity / epsilon
        scale = sensitivity / epsilon
        noise = self._sample_laplace(scale)
        noisy_value = value + noise

        self._record_query(
            entity_id or "anonymous",
            PrivacyMechanism.LAPLACE,
            epsilon,
            0,
            sensitivity,
            value,
            noisy_value,
        )

        self._stats["laplace_queries"] += 1
        return noisy_value, None

    def gaussian_mechanism(
        self,
        value: float,
        sensitivity: float,
        epsilon: float,
        delta: float,
        entity_id: Optional[str] = None,
    ) -> tuple[float, Optional[str]]:
        """
        Apply Gaussian mechanism to a numeric value.

        Provides (epsilon, delta)-differential privacy.

        Args:
            value: True value to protect
            sensitivity: Query sensitivity
            epsilon: Privacy parameter
            delta: Probability of privacy failure
            entity_id: Entity to charge budget

        Returns:
            Tuple of (noisy_value, error_message)
        """
        if delta <= 0:
            return value, "Delta must be positive for Gaussian mechanism"

        if not self._check_and_consume_budget(entity_id, epsilon, delta):
            return value, "Privacy budget exceeded"

        # Gaussian noise: sigma = sensitivity * sqrt(2 * ln(1.25/delta)) / epsilon
        sigma = sensitivity * math.sqrt(2 * math.log(1.25 / delta)) / epsilon
        noise = random.gauss(0, sigma)
        noisy_value = value + noise

        self._record_query(
            entity_id or "anonymous",
            PrivacyMechanism.GAUSSIAN,
            epsilon,
            delta,
            sensitivity,
            value,
            noisy_value,
        )

        self._stats["gaussian_queries"] += 1
        return noisy_value, None

    def exponential_mechanism(
        self,
        candidates: list[Any],
        utility_function: Callable[[Any], float],
        sensitivity: float,
        epsilon: float,
        entity_id: Optional[str] = None,
    ) -> tuple[Any, Optional[str]]:
        """
        Apply exponential mechanism for categorical selection.

        Selects from candidates with probability proportional to
        exp(epsilon * utility / (2 * sensitivity)).

        Args:
            candidates: List of candidate values
            utility_function: Function returning utility score for each candidate
            sensitivity: Utility function sensitivity
            epsilon: Privacy parameter
            entity_id: Entity to charge budget

        Returns:
            Tuple of (selected_candidate, error_message)
        """
        if not candidates:
            return None, "No candidates provided"

        if not self._check_and_consume_budget(entity_id, epsilon, 0):
            return candidates[0], "Privacy budget exceeded"

        # Calculate selection probabilities
        utilities = [utility_function(c) for c in candidates]
        max_utility = max(utilities)

        # Compute weights (normalized for numerical stability)
        weights = []
        for u in utilities:
            weight = math.exp(epsilon * (u - max_utility) / (2 * sensitivity))
            weights.append(weight)

        # Normalize to probabilities
        total_weight = sum(weights)
        probabilities = [w / total_weight for w in weights]

        # Sample from distribution
        r = random.random()
        cumulative = 0
        selected = candidates[-1]
        for i, prob in enumerate(probabilities):
            cumulative += prob
            if r <= cumulative:
                selected = candidates[i]
                break

        self._record_query(
            entity_id or "anonymous",
            PrivacyMechanism.EXPONENTIAL,
            epsilon,
            0,
            sensitivity,
            utilities,
            selected,
        )

        self._stats["exponential_queries"] += 1
        return selected, None

    def randomized_response(
        self,
        true_value: bool,
        epsilon: float,
        entity_id: Optional[str] = None,
    ) -> tuple[bool, Optional[str]]:
        """
        Apply randomized response for binary queries.

        With probability p, report true value; otherwise report random.
        p = e^epsilon / (1 + e^epsilon)

        Args:
            true_value: True binary value
            epsilon: Privacy parameter
            entity_id: Entity to charge budget

        Returns:
            Tuple of (response, error_message)
        """
        if not self._check_and_consume_budget(entity_id, epsilon, 0):
            return true_value, "Privacy budget exceeded"

        # Probability of reporting truthfully
        p = math.exp(epsilon) / (1 + math.exp(epsilon))

        if random.random() < p:
            response = true_value
        else:
            response = random.choice([True, False])

        self._record_query(
            entity_id or "anonymous",
            PrivacyMechanism.RANDOMIZED_RESPONSE,
            epsilon,
            0,
            1.0,
            true_value,
            response,
        )

        return response, None

    # ========== Aggregate Queries ==========

    def private_count(
        self,
        data: list[Any],
        predicate: Callable[[Any], bool],
        epsilon: float,
        entity_id: Optional[str] = None,
    ) -> tuple[float, Optional[str]]:
        """
        Compute differentially private count.

        Args:
            data: Dataset
            predicate: Filter function
            epsilon: Privacy parameter
            entity_id: Entity to charge budget

        Returns:
            Tuple of (noisy_count, error_message)
        """
        true_count = sum(1 for item in data if predicate(item))
        # Sensitivity is 1 for counting queries
        return self.laplace_mechanism(true_count, 1.0, epsilon, entity_id)

    def private_sum(
        self,
        data: list[float],
        lower_bound: float,
        upper_bound: float,
        epsilon: float,
        entity_id: Optional[str] = None,
    ) -> tuple[float, Optional[str]]:
        """
        Compute differentially private sum.

        Args:
            data: Numeric dataset
            lower_bound: Minimum possible value
            upper_bound: Maximum possible value
            epsilon: Privacy parameter
            entity_id: Entity to charge budget

        Returns:
            Tuple of (noisy_sum, error_message)
        """
        # Clip values to bounds
        clipped = [max(lower_bound, min(upper_bound, v)) for v in data]
        true_sum = sum(clipped)
        # Sensitivity is the range
        sensitivity = upper_bound - lower_bound
        return self.laplace_mechanism(true_sum, sensitivity, epsilon, entity_id)

    def private_mean(
        self,
        data: list[float],
        lower_bound: float,
        upper_bound: float,
        epsilon: float,
        entity_id: Optional[str] = None,
    ) -> tuple[float, Optional[str]]:
        """
        Compute differentially private mean.

        Uses composition: splits epsilon between count and sum.

        Args:
            data: Numeric dataset
            lower_bound: Minimum possible value
            upper_bound: Maximum possible value
            epsilon: Privacy parameter
            entity_id: Entity to charge budget

        Returns:
            Tuple of (noisy_mean, error_message)
        """
        if not data:
            return 0.0, "Empty dataset"

        # Split epsilon between count and sum
        epsilon_count = epsilon / 2
        epsilon_sum = epsilon / 2

        noisy_count, err1 = self.laplace_mechanism(len(data), 1.0, epsilon_count, entity_id)
        if err1:
            return 0.0, err1

        noisy_sum, err2 = self.private_sum(data, lower_bound, upper_bound, epsilon_sum, entity_id)
        if err2:
            return 0.0, err2

        # Avoid division by very small numbers
        if abs(noisy_count) < 1:
            noisy_count = 1 if noisy_count >= 0 else -1

        return noisy_sum / noisy_count, None

    def private_histogram(
        self,
        data: list[Any],
        bins: list[Any],
        epsilon: float,
        entity_id: Optional[str] = None,
    ) -> tuple[dict[Any, float], Optional[str]]:
        """
        Compute differentially private histogram.

        Args:
            data: Dataset
            bins: Bin labels/values
            epsilon: Privacy parameter (divided among bins)
            entity_id: Entity to charge budget

        Returns:
            Tuple of (noisy_histogram, error_message)
        """
        # Per-bin epsilon (sequential composition)
        bin_epsilon = epsilon / len(bins)

        histogram = {}
        for bin_value in bins:
            true_count = sum(1 for item in data if item == bin_value)
            noisy_count, err = self.laplace_mechanism(true_count, 1.0, bin_epsilon, entity_id)
            if err:
                return {}, err
            histogram[bin_value] = max(0, noisy_count)  # Counts can't be negative

        return histogram, None

    # ========== Anonymization ==========

    def anonymize_record(
        self,
        record: dict[str, Any],
        sensitive_fields: list[str],
        quasi_identifiers: list[str],
        method: AnonymizationMethod = AnonymizationMethod.GENERALIZATION,
    ) -> AnonymizedRecord:
        """
        Anonymize a data record.

        Args:
            record: Original record
            sensitive_fields: Fields to suppress
            quasi_identifiers: Fields to generalize
            method: Anonymization method

        Returns:
            Anonymized record
        """
        import secrets

        # Create hashed ID
        original_id = str(record.get("id", secrets.token_hex(8)))
        hashed_id = hashlib.sha256(original_id.encode()).hexdigest()[:16]

        anonymized_fields = {}
        generalization_levels = {}

        for key, value in record.items():
            if key in sensitive_fields:
                # Suppress sensitive fields
                anonymized_fields[key] = None
            elif key in quasi_identifiers:
                # Generalize quasi-identifiers
                gen_value, gen_level = self._generalize_value(key, value)
                anonymized_fields[key] = gen_value
                generalization_levels[key] = gen_level
            else:
                # Keep other fields
                anonymized_fields[key] = value

        self._stats["anonymizations"] += 1

        return AnonymizedRecord(
            record_id=f"anon_{secrets.token_hex(8)}",
            original_id=hashed_id,
            method=method,
            fields=anonymized_fields,
            generalization_levels=generalization_levels,
        )

    def pseudonymize(
        self,
        identifier: str,
        domain: str = "default",
    ) -> str:
        """
        Create or retrieve a pseudonym for an identifier.

        Args:
            identifier: Original identifier
            domain: Pseudonym domain

        Returns:
            Pseudonym
        """
        key = f"{domain}:{identifier}"
        if key not in self._pseudonyms:
            # Create consistent pseudonym using hash
            hash_input = f"{key}:{self.config.default_epsilon}".encode()
            self._pseudonyms[key] = hashlib.sha256(hash_input).hexdigest()[:12]

        return self._pseudonyms[key]

    def check_k_anonymity(
        self,
        records: list[dict[str, Any]],
        quasi_identifiers: list[str],
        k: Optional[int] = None,
    ) -> tuple[bool, int]:
        """
        Check if dataset satisfies k-anonymity.

        Args:
            records: List of records
            quasi_identifiers: Fields forming quasi-identifier
            k: Minimum group size (uses config default if not specified)

        Returns:
            Tuple of (satisfies_k_anonymity, min_group_size)
        """
        k = k or self.config.k_anonymity_k

        # Group by quasi-identifiers
        groups: dict[tuple, int] = {}
        for record in records:
            qi_values = tuple(record.get(qi) for qi in quasi_identifiers)
            groups[qi_values] = groups.get(qi_values, 0) + 1

        if not groups:
            return True, 0

        min_group_size = min(groups.values())
        return min_group_size >= k, min_group_size

    # ========== Budget Management ==========

    def get_budget(self, entity_id: str) -> PrivacyBudget:
        """Get or create privacy budget for entity."""
        if entity_id not in self._budgets:
            self._budgets[entity_id] = PrivacyBudget(
                entity_id=entity_id,
                total_epsilon=self.config.default_epsilon * 10,  # Per-entity budget
                total_delta=self.config.default_delta * 10,
            )
        return self._budgets[entity_id]

    def set_budget(
        self,
        entity_id: str,
        epsilon: float,
        delta: float = 1e-5,
    ) -> PrivacyBudget:
        """Set privacy budget for entity."""
        budget = PrivacyBudget(
            entity_id=entity_id,
            total_epsilon=epsilon,
            total_delta=delta,
        )
        self._budgets[entity_id] = budget
        return budget

    def reset_budget(self, entity_id: str) -> bool:
        """Reset privacy budget for entity."""
        if entity_id in self._budgets:
            self._budgets[entity_id].reset()
            return True
        return False

    def get_global_budget(self) -> PrivacyBudget:
        """Get global privacy budget."""
        return self._global_budget

    # ========== Internal Methods ==========

    def _check_and_consume_budget(
        self,
        entity_id: Optional[str],
        epsilon: float,
        delta: float,
    ) -> bool:
        """Check and consume privacy budget."""
        if not self.config.enable_budget_tracking:
            return True

        # Check global budget
        if not self._global_budget.can_query(epsilon, delta):
            self._stats["budget_exceeded"] += 1
            logger.warning("Global privacy budget exceeded")
            return False

        # Check entity budget
        if entity_id:
            budget = self.get_budget(entity_id)

            # Auto-reset if needed
            if self.config.auto_reset_budgets and budget.should_reset():
                budget.reset()

            if not budget.can_query(epsilon, delta):
                self._stats["budget_exceeded"] += 1
                logger.warning(f"Privacy budget exceeded for entity: {entity_id}")
                return False

            budget.consume(epsilon, delta)

        self._global_budget.consume(epsilon, delta)
        self._stats["total_queries"] += 1
        return True

    def _record_query(
        self,
        entity_id: str,
        mechanism: PrivacyMechanism,
        epsilon: float,
        delta: float,
        sensitivity: float,
        original: Any,
        noisy: Any,
    ) -> None:
        """Record a privacy query for auditing."""
        import secrets

        query = PrivacyQuery(
            query_id=f"pq_{secrets.token_hex(8)}",
            entity_id=entity_id,
            mechanism=mechanism,
            epsilon=epsilon,
            delta=delta,
            sensitivity=sensitivity,
            original_result=original,
            noisy_result=noisy,
        )
        self._queries.append(query)

        # Keep only recent queries (last 1000)
        if len(self._queries) > 1000:
            self._queries = self._queries[-1000:]

    def _sample_laplace(self, scale: float) -> float:
        """Sample from Laplace distribution."""
        # Use inverse CDF method
        u = random.random() - 0.5
        return -scale * math.copysign(1, u) * math.log(1 - 2 * abs(u))

    def _generalize_value(
        self,
        field_name: str,
        value: Any,
    ) -> tuple[Any, int]:
        """
        Generalize a value based on its type.

        Returns tuple of (generalized_value, generalization_level).
        """
        if value is None:
            return None, 0

        # Age: generalize to ranges
        if field_name == "age" and isinstance(value, (int, float)):
            if value < 18:
                return "< 18", 1
            elif value < 30:
                return "18-29", 1
            elif value < 50:
                return "30-49", 1
            elif value < 70:
                return "50-69", 1
            else:
                return "70+", 1

        # Zip code: remove last digits
        if field_name in ("zip_code", "postal_code") and isinstance(value, str):
            if len(value) >= 3:
                return value[:3] + "**", 1
            return "***", 2

        # Date: generalize to month/year
        if field_name in ("date", "timestamp", "birth_date"):
            if isinstance(value, datetime):
                return value.strftime("%Y-%m"), 1
            elif isinstance(value, str) and len(value) >= 7:
                return value[:7], 1

        # Location: round coordinates
        if field_name in ("latitude", "longitude") and isinstance(value, (int, float)):
            return round(value, 1), 1

        # Default: return as-is
        return value, 0

    def get_stats(self) -> dict[str, Any]:
        """Get differential privacy statistics."""
        return {
            **self._stats,
            "entity_budgets": len(self._budgets),
            "global_budget": self._global_budget.to_dict(),
            "total_queries_logged": len(self._queries),
        }

    def get_recent_queries(
        self,
        entity_id: Optional[str] = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Get recent privacy queries."""
        queries = self._queries
        if entity_id:
            queries = [q for q in queries if q.entity_id == entity_id]

        return [
            {
                "query_id": q.query_id,
                "entity_id": q.entity_id,
                "mechanism": q.mechanism.value,
                "epsilon": q.epsilon,
                "delta": q.delta,
                "timestamp": q.timestamp.isoformat(),
            }
            for q in queries[-limit:]
        ]
