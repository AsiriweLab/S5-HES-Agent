"""
RAG Query Orchestrator for the Smart-HES Framework.

Implements multi-step RAG queries with:
- Query decomposition into sub-queries
- Parallel collection queries
- Result aggregation and ranking
- Provenance tracking
- Confidence scoring
"""

import asyncio
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Optional
from uuid import uuid4

from loguru import logger


class QueryType(str, Enum):
    """Types of queries."""
    SIMPLE = "simple"           # Single-step direct query
    MULTI_STEP = "multi_step"   # Decomposed into sub-queries
    AGGREGATED = "aggregated"   # Results from multiple collections
    HYBRID = "hybrid"           # Semantic + keyword search


class CollectionType(str, Enum):
    """Knowledge base collection types."""
    ACADEMIC = "academic"           # Academic papers
    THREAT_INTEL = "threat_intel"   # CVE, MITRE, NVD
    DEVICE_SPECS = "device_specs"   # Device specifications
    DOCUMENTATION = "documentation" # System documentation
    GENERAL = "general"             # General knowledge


@dataclass
class QueryStep:
    """A single step in a multi-step query."""
    step_id: str
    query: str
    collection: Optional[CollectionType] = None
    depends_on: list[str] = field(default_factory=list)
    status: str = "pending"  # pending, running, completed, failed
    results: list = field(default_factory=list)
    error: Optional[str] = None
    execution_time_ms: float = 0.0

    @classmethod
    def create(
        cls,
        query: str,
        collection: CollectionType = None,
        depends_on: list[str] = None,
    ) -> "QueryStep":
        return cls(
            step_id=str(uuid4())[:8],
            query=query,
            collection=collection,
            depends_on=depends_on or [],
        )


@dataclass
class QueryPlan:
    """A plan for executing a complex query."""
    plan_id: str
    original_query: str
    query_type: QueryType
    steps: list[QueryStep] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)

    @classmethod
    def create(cls, query: str, query_type: QueryType = QueryType.SIMPLE) -> "QueryPlan":
        return cls(
            plan_id=str(uuid4()),
            original_query=query,
            query_type=query_type,
        )

    def add_step(self, step: QueryStep) -> None:
        """Add a step to the plan."""
        self.steps.append(step)

    def get_ready_steps(self) -> list[QueryStep]:
        """Get steps that are ready to execute (all dependencies met)."""
        completed_ids = {s.step_id for s in self.steps if s.status == "completed"}
        return [
            s for s in self.steps
            if s.status == "pending" and all(d in completed_ids for d in s.depends_on)
        ]

    def is_complete(self) -> bool:
        """Check if all steps are complete."""
        return all(s.status in ["completed", "failed"] for s in self.steps)


@dataclass
class ProvenanceRecord:
    """Tracks the origin and path of retrieved information."""
    record_id: str
    source_collection: CollectionType
    document_id: str
    document_title: str
    chunk_index: Optional[int] = None
    retrieval_query: str = ""
    similarity_score: float = 0.0
    timestamp: datetime = field(default_factory=datetime.utcnow)
    metadata: dict = field(default_factory=dict)

    def to_citation(self, style: str = "ieee") -> str:
        """Generate a citation string."""
        if style == "ieee":
            return f'[{self.document_title}], Retrieved from {self.source_collection.value}'
        elif style == "apa":
            return f'{self.document_title}. ({self.timestamp.year}). {self.source_collection.value}.'
        else:
            return f'{self.document_title} ({self.source_collection.value})'


@dataclass
class AggregatedResult:
    """Aggregated result from multiple query steps."""
    result_id: str
    original_query: str
    contexts: list[str] = field(default_factory=list)
    provenance: list[ProvenanceRecord] = field(default_factory=list)
    confidence_score: float = 0.0
    total_results: int = 0
    collections_queried: list[CollectionType] = field(default_factory=list)
    execution_time_ms: float = 0.0
    query_plan: Optional[QueryPlan] = None

    @property
    def has_results(self) -> bool:
        return len(self.contexts) > 0

    def get_formatted_context(self, max_contexts: int = 5) -> str:
        """Format contexts for LLM prompt."""
        if not self.contexts:
            return ""

        parts = []
        for i, (ctx, prov) in enumerate(zip(self.contexts[:max_contexts], self.provenance[:max_contexts])):
            citation = prov.to_citation()
            parts.append(f"[{i+1}] {citation}\n{ctx}")

        return "\n\n".join(parts)

    def get_citations(self, style: str = "ieee") -> list[str]:
        """Get list of citations."""
        return [p.to_citation(style) for p in self.provenance]


class RAGQueryOrchestrator:
    """
    Orchestrates complex RAG queries across multiple knowledge sources.

    Features:
    - Query decomposition for complex questions
    - Parallel execution across collections
    - Result aggregation and ranking
    - Provenance tracking
    - Confidence scoring
    """

    def __init__(
        self,
        knowledge_base: Any = None,
        max_parallel_queries: int = 3,
        default_results_per_query: int = 5,
    ):
        self.knowledge_base = knowledge_base
        self.max_parallel_queries = max_parallel_queries
        self.default_results_per_query = default_results_per_query

        # Collection-specific query handlers
        self._collection_handlers: dict[CollectionType, Callable] = {}

        # Query decomposition patterns
        self._decomposition_patterns = self._build_decomposition_patterns()

        # Statistics
        self._stats = {
            "total_queries": 0,
            "multi_step_queries": 0,
            "total_steps_executed": 0,
            "average_execution_time_ms": 0.0,
            "cache_hits": 0,
        }

        logger.info("RAGQueryOrchestrator initialized")

    def _build_decomposition_patterns(self) -> dict:
        """Build patterns for query decomposition."""
        return {
            # Comparison queries
            "compare": {
                "keywords": ["compare", "difference", "vs", "versus", "between"],
                "decompose": self._decompose_comparison,
            },
            # Multi-aspect queries
            "multi_aspect": {
                "keywords": ["and", "also", "as well as", "both"],
                "decompose": self._decompose_multi_aspect,
            },
            # Cause-effect queries
            "cause_effect": {
                "keywords": ["why", "cause", "reason", "because", "result in"],
                "decompose": self._decompose_cause_effect,
            },
            # How-to queries
            "how_to": {
                "keywords": ["how to", "how do", "steps to", "procedure"],
                "decompose": self._decompose_how_to,
            },
            # Definition + example queries
            "definition_example": {
                "keywords": ["what is", "define", "example", "such as"],
                "decompose": self._decompose_definition_example,
            },
        }

    def register_collection_handler(
        self,
        collection: CollectionType,
        handler: Callable,
    ) -> None:
        """Register a handler for a specific collection."""
        self._collection_handlers[collection] = handler
        logger.debug(f"Registered handler for collection: {collection.value}")

    async def query(
        self,
        query: str,
        collections: list[CollectionType] = None,
        n_results: int = None,
        use_decomposition: bool = True,
    ) -> AggregatedResult:
        """
        Execute a query across knowledge sources.

        Args:
            query: The query string
            collections: Collections to search (default: all)
            n_results: Number of results per collection
            use_decomposition: Whether to decompose complex queries

        Returns:
            AggregatedResult with contexts and provenance
        """
        start_time = time.perf_counter()
        self._stats["total_queries"] += 1

        n_results = n_results or self.default_results_per_query
        collections = collections or list(CollectionType)

        # Create query plan
        if use_decomposition:
            plan = self._create_query_plan(query, collections)
        else:
            plan = self._create_simple_plan(query, collections)

        # Execute plan
        await self._execute_plan(plan, n_results)

        # Aggregate results
        result = self._aggregate_results(plan)
        result.execution_time_ms = (time.perf_counter() - start_time) * 1000

        # Update stats
        self._update_stats(result)

        logger.info(
            f"Query completed: {len(result.contexts)} results, "
            f"{result.execution_time_ms:.1f}ms"
        )

        return result

    async def query_collection(
        self,
        query: str,
        collection: CollectionType,
        n_results: int = None,
    ) -> AggregatedResult:
        """Query a specific collection."""
        return await self.query(
            query=query,
            collections=[collection],
            n_results=n_results,
            use_decomposition=False,
        )

    def _create_query_plan(
        self,
        query: str,
        collections: list[CollectionType],
    ) -> QueryPlan:
        """Create a query plan with decomposition if needed."""
        # Check if query matches decomposition patterns
        query_lower = query.lower()
        decomposed = False

        for pattern_name, pattern_info in self._decomposition_patterns.items():
            if any(kw in query_lower for kw in pattern_info["keywords"]):
                plan = pattern_info["decompose"](query, collections)
                if len(plan.steps) > 1:
                    self._stats["multi_step_queries"] += 1
                    decomposed = True
                    logger.debug(f"Query decomposed using {pattern_name} pattern")
                    return plan

        # Simple query - one step per collection
        return self._create_simple_plan(query, collections)

    def _create_simple_plan(
        self,
        query: str,
        collections: list[CollectionType],
    ) -> QueryPlan:
        """Create a simple plan querying all collections in parallel."""
        plan = QueryPlan.create(query, QueryType.SIMPLE)

        for collection in collections:
            step = QueryStep.create(
                query=query,
                collection=collection,
            )
            plan.add_step(step)

        return plan

    def _decompose_comparison(
        self,
        query: str,
        collections: list[CollectionType],
    ) -> QueryPlan:
        """Decompose comparison queries."""
        plan = QueryPlan.create(query, QueryType.MULTI_STEP)

        # Extract items being compared (simplified)
        # In production, use NLP for better extraction
        items = self._extract_comparison_items(query)

        if len(items) >= 2:
            # Query for each item separately
            for item in items[:2]:  # Limit to 2 items
                for collection in collections:
                    step = QueryStep.create(
                        query=f"What is {item}?",
                        collection=collection,
                    )
                    plan.add_step(step)

            # Add comparison step (depends on item queries)
            item_step_ids = [s.step_id for s in plan.steps]
            comparison_step = QueryStep.create(
                query=query,
                collection=CollectionType.GENERAL,
                depends_on=item_step_ids,
            )
            plan.add_step(comparison_step)
        else:
            # Fall back to simple plan
            return self._create_simple_plan(query, collections)

        return plan

    def _decompose_multi_aspect(
        self,
        query: str,
        collections: list[CollectionType],
    ) -> QueryPlan:
        """Decompose multi-aspect queries (A and B)."""
        plan = QueryPlan.create(query, QueryType.MULTI_STEP)

        # Split on 'and' or 'also'
        aspects = self._extract_aspects(query)

        for aspect in aspects:
            for collection in collections:
                step = QueryStep.create(
                    query=aspect.strip(),
                    collection=collection,
                )
                plan.add_step(step)

        return plan

    def _decompose_cause_effect(
        self,
        query: str,
        collections: list[CollectionType],
    ) -> QueryPlan:
        """Decompose cause-effect queries."""
        plan = QueryPlan.create(query, QueryType.MULTI_STEP)

        # First get the phenomenon
        phenomenon_step = QueryStep.create(
            query=query.replace("why", "what is").replace("cause", ""),
            collection=CollectionType.GENERAL,
        )
        plan.add_step(phenomenon_step)

        # Then get causes
        cause_step = QueryStep.create(
            query=query,
            collection=CollectionType.ACADEMIC,
            depends_on=[phenomenon_step.step_id],
        )
        plan.add_step(cause_step)

        return plan

    def _decompose_how_to(
        self,
        query: str,
        collections: list[CollectionType],
    ) -> QueryPlan:
        """Decompose how-to queries."""
        plan = QueryPlan.create(query, QueryType.MULTI_STEP)

        # Get overview/definition first
        overview_step = QueryStep.create(
            query=query.replace("how to", "what is").replace("how do", "what is"),
            collection=CollectionType.DOCUMENTATION,
        )
        plan.add_step(overview_step)

        # Get procedural information
        procedure_step = QueryStep.create(
            query=query,
            collection=CollectionType.DOCUMENTATION,
            depends_on=[overview_step.step_id],
        )
        plan.add_step(procedure_step)

        return plan

    def _decompose_definition_example(
        self,
        query: str,
        collections: list[CollectionType],
    ) -> QueryPlan:
        """Decompose definition + example queries."""
        plan = QueryPlan.create(query, QueryType.MULTI_STEP)

        # Get definition
        def_step = QueryStep.create(
            query=query,
            collection=CollectionType.DOCUMENTATION,
        )
        plan.add_step(def_step)

        # Get examples
        example_step = QueryStep.create(
            query=f"examples of {query.replace('what is', '').strip()}",
            collection=CollectionType.ACADEMIC,
            depends_on=[def_step.step_id],
        )
        plan.add_step(example_step)

        return plan

    def _extract_comparison_items(self, query: str) -> list[str]:
        """Extract items being compared."""
        # Simple extraction - in production use NLP
        query_lower = query.lower()
        for sep in [" vs ", " versus ", " and ", " compared to "]:
            if sep in query_lower:
                parts = query_lower.split(sep)
                return [p.strip() for p in parts if p.strip()]
        return []

    def _extract_aspects(self, query: str) -> list[str]:
        """Extract multiple aspects from a query."""
        query_lower = query.lower()
        for sep in [" and ", " also ", " as well as "]:
            if sep in query_lower:
                parts = query_lower.split(sep)
                return [p.strip() for p in parts if p.strip()]
        return [query]

    async def _execute_plan(self, plan: QueryPlan, n_results: int) -> None:
        """Execute a query plan."""
        while not plan.is_complete():
            ready_steps = plan.get_ready_steps()
            if not ready_steps:
                # Wait for dependencies or break if stuck
                await asyncio.sleep(0.01)
                continue

            # Execute ready steps in parallel (up to max)
            steps_to_run = ready_steps[:self.max_parallel_queries]
            tasks = [
                self._execute_step(step, n_results)
                for step in steps_to_run
            ]
            await asyncio.gather(*tasks)

    async def _execute_step(self, step: QueryStep, n_results: int) -> None:
        """Execute a single query step."""
        start_time = time.perf_counter()
        step.status = "running"
        self._stats["total_steps_executed"] += 1

        try:
            # Use collection handler if registered
            if step.collection and step.collection in self._collection_handlers:
                handler = self._collection_handlers[step.collection]
                results = await handler(step.query, n_results)
            elif self.knowledge_base:
                # Use default knowledge base search
                result = self.knowledge_base.search(
                    query=step.query,
                    n_results=n_results,
                    category=step.collection.value if step.collection else None,
                )
                results = result.results if hasattr(result, 'results') else []
            else:
                results = []

            step.results = results
            step.status = "completed"

        except Exception as e:
            logger.error(f"Step execution failed: {e}")
            step.status = "failed"
            step.error = str(e)
            step.results = []

        finally:
            step.execution_time_ms = (time.perf_counter() - start_time) * 1000

    def _aggregate_results(self, plan: QueryPlan) -> AggregatedResult:
        """Aggregate results from all steps."""
        result = AggregatedResult(
            result_id=str(uuid4()),
            original_query=plan.original_query,
            query_plan=plan,
        )

        seen_contents = set()

        for step in plan.steps:
            if step.status != "completed":
                continue

            if step.collection:
                result.collections_queried.append(step.collection)

            for r in step.results:
                # Get content
                content = r.content if hasattr(r, 'content') else str(r)

                # Deduplicate
                content_hash = hash(content[:200])
                if content_hash in seen_contents:
                    continue
                seen_contents.add(content_hash)

                result.contexts.append(content)

                # Create provenance record
                provenance = ProvenanceRecord(
                    record_id=str(uuid4())[:8],
                    source_collection=step.collection or CollectionType.GENERAL,
                    document_id=r.doc_id if hasattr(r, 'doc_id') else "",
                    document_title=r.metadata.get("title", "Unknown") if hasattr(r, 'metadata') else "Unknown",
                    retrieval_query=step.query,
                    similarity_score=r.similarity_score if hasattr(r, 'similarity_score') else 0.0,
                    metadata=r.metadata if hasattr(r, 'metadata') else {},
                )
                result.provenance.append(provenance)

        result.total_results = len(result.contexts)

        # Calculate aggregate confidence
        if result.provenance:
            scores = [p.similarity_score for p in result.provenance if p.similarity_score > 0]
            result.confidence_score = sum(scores) / len(scores) if scores else 0.0

        return result

    def _update_stats(self, result: AggregatedResult) -> None:
        """Update running statistics."""
        total = self._stats["total_queries"]
        old_avg = self._stats["average_execution_time_ms"]
        new_time = result.execution_time_ms

        self._stats["average_execution_time_ms"] = (
            (old_avg * (total - 1) + new_time) / total
            if total > 0 else new_time
        )

    def get_stats(self) -> dict:
        """Get orchestrator statistics."""
        return self._stats.copy()


# Global instance
_query_orchestrator: Optional[RAGQueryOrchestrator] = None


def get_query_orchestrator() -> RAGQueryOrchestrator:
    """Get or create the global query orchestrator."""
    global _query_orchestrator
    if _query_orchestrator is None:
        _query_orchestrator = RAGQueryOrchestrator()
    return _query_orchestrator


def initialize_query_orchestrator(
    knowledge_base: Any = None,
    max_parallel_queries: int = 3,
) -> RAGQueryOrchestrator:
    """Initialize the global query orchestrator."""
    global _query_orchestrator
    _query_orchestrator = RAGQueryOrchestrator(
        knowledge_base=knowledge_base,
        max_parallel_queries=max_parallel_queries,
    )
    return _query_orchestrator
