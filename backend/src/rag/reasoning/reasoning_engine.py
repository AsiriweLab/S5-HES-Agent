"""
Advanced Reasoning Engine for RAG.

Implements sophisticated reasoning strategies for knowledge retrieval:
- Chain-of-Thought (CoT) reasoning
- Multi-hop reasoning across documents
- Iterative query refinement
- Hypothesis generation and validation
- Confidence calibration
"""

import re
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Optional
from uuid import uuid4

from loguru import logger


class ReasoningStrategy(str, Enum):
    """Available reasoning strategies."""
    DIRECT = "direct"                    # Simple direct retrieval
    CHAIN_OF_THOUGHT = "chain_of_thought"  # Step-by-step reasoning
    MULTI_HOP = "multi_hop"              # Follow references across documents
    ITERATIVE = "iterative"              # Refine query based on results
    HYPOTHESIS_DRIVEN = "hypothesis_driven"  # Generate and test hypotheses
    COMPARATIVE = "comparative"          # Compare multiple sources
    DECOMPOSITION = "decomposition"      # Break complex queries into parts


class StepType(str, Enum):
    """Types of reasoning steps."""
    QUERY = "query"               # Perform a knowledge base query
    ANALYZE = "analyze"           # Analyze retrieved content
    SYNTHESIZE = "synthesize"     # Combine information
    VALIDATE = "validate"         # Check consistency
    REFINE = "refine"             # Refine understanding
    CONCLUDE = "conclude"         # Draw conclusions
    HYPOTHESIZE = "hypothesize"   # Generate hypothesis


@dataclass
class ReasoningStep:
    """A single step in a reasoning chain."""
    step_id: str
    step_number: int
    step_type: StepType
    thought: str                   # The reasoning thought for this step
    action: str                    # Action taken (e.g., "search for...")
    observation: str = ""          # Result of the action
    confidence: float = 0.5        # Confidence in this step's result
    sources: list[str] = field(default_factory=list)
    execution_time_ms: float = 0.0
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "step_id": self.step_id,
            "step_number": self.step_number,
            "step_type": self.step_type.value,
            "thought": self.thought,
            "action": self.action,
            "observation": self.observation,
            "confidence": self.confidence,
            "sources": self.sources,
            "execution_time_ms": self.execution_time_ms,
        }


@dataclass
class ReasoningChain:
    """A complete chain of reasoning steps."""
    chain_id: str
    query: str
    strategy: ReasoningStrategy
    steps: list[ReasoningStep] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)
    status: str = "pending"  # pending, running, completed, failed

    def add_step(self, step: ReasoningStep) -> None:
        """Add a step to the chain."""
        step.step_number = len(self.steps) + 1
        self.steps.append(step)

    def get_reasoning_trace(self) -> str:
        """Get a human-readable trace of the reasoning."""
        trace_parts = []
        for step in self.steps:
            trace_parts.append(
                f"Step {step.step_number} ({step.step_type.value}):\n"
                f"  Thought: {step.thought}\n"
                f"  Action: {step.action}\n"
                f"  Observation: {step.observation[:200]}{'...' if len(step.observation) > 200 else ''}\n"
                f"  Confidence: {step.confidence:.2f}"
            )
        return "\n\n".join(trace_parts)

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "chain_id": self.chain_id,
            "query": self.query,
            "strategy": self.strategy.value,
            "steps": [s.to_dict() for s in self.steps],
            "created_at": self.created_at.isoformat(),
            "status": self.status,
        }


@dataclass
class ReasoningResult:
    """Result of a reasoning process."""
    result_id: str
    query: str
    strategy: ReasoningStrategy
    answer: str                    # Final synthesized answer
    confidence: float              # Overall confidence score
    reasoning_chain: ReasoningChain
    sources: list[str]             # All sources used
    contexts: list[str]            # Retrieved contexts
    execution_time_ms: float
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "result_id": self.result_id,
            "query": self.query,
            "strategy": self.strategy.value,
            "answer": self.answer,
            "confidence": self.confidence,
            "reasoning_chain": self.reasoning_chain.to_dict(),
            "sources": self.sources,
            "contexts_count": len(self.contexts),
            "execution_time_ms": self.execution_time_ms,
        }


class ReasoningEngine:
    """
    Advanced Reasoning Engine for RAG.

    Implements multiple reasoning strategies to improve the quality
    and reliability of knowledge retrieval and synthesis.
    """

    def __init__(
        self,
        knowledge_base: Any = None,
        max_reasoning_steps: int = 10,
        min_confidence_threshold: float = 0.3,
    ):
        """
        Initialize the reasoning engine.

        Args:
            knowledge_base: Knowledge base service for retrieval
            max_reasoning_steps: Maximum steps in a reasoning chain
            min_confidence_threshold: Minimum confidence to continue
        """
        self.knowledge_base = knowledge_base
        self.max_reasoning_steps = max_reasoning_steps
        self.min_confidence_threshold = min_confidence_threshold

        # Strategy implementations
        self._strategies: dict[ReasoningStrategy, Callable] = {
            ReasoningStrategy.DIRECT: self._direct_reasoning,
            ReasoningStrategy.CHAIN_OF_THOUGHT: self._chain_of_thought_reasoning,
            ReasoningStrategy.MULTI_HOP: self._multi_hop_reasoning,
            ReasoningStrategy.ITERATIVE: self._iterative_reasoning,
            ReasoningStrategy.HYPOTHESIS_DRIVEN: self._hypothesis_reasoning,
            ReasoningStrategy.COMPARATIVE: self._comparative_reasoning,
            ReasoningStrategy.DECOMPOSITION: self._decomposition_reasoning,
        }

        # Statistics
        self._stats = {
            "total_reasoning_tasks": 0,
            "successful_tasks": 0,
            "average_steps": 0.0,
            "average_confidence": 0.0,
            "strategy_usage": {s.value: 0 for s in ReasoningStrategy},
        }

        logger.info("ReasoningEngine initialized")

    async def reason(
        self,
        query: str,
        strategy: ReasoningStrategy = None,
        n_results: int = 5,
        context: dict = None,
    ) -> ReasoningResult:
        """
        Execute reasoning for a query.

        Args:
            query: The query to reason about
            strategy: Reasoning strategy (auto-selected if None)
            n_results: Number of results to retrieve per query
            context: Additional context for reasoning

        Returns:
            ReasoningResult with answer and reasoning chain
        """
        start_time = time.perf_counter()
        self._stats["total_reasoning_tasks"] += 1

        # Auto-select strategy if not specified
        if strategy is None:
            strategy = self._select_strategy(query)

        self._stats["strategy_usage"][strategy.value] += 1

        # Create reasoning chain
        chain = ReasoningChain(
            chain_id=str(uuid4())[:12],
            query=query,
            strategy=strategy,
            status="running",
        )

        try:
            # Execute strategy
            strategy_fn = self._strategies[strategy]
            answer, confidence, contexts, sources = await strategy_fn(
                query=query,
                chain=chain,
                n_results=n_results,
                context=context or {},
            )

            chain.status = "completed"
            self._stats["successful_tasks"] += 1

        except Exception as e:
            logger.error(f"Reasoning failed: {e}", exc_info=True)
            chain.status = "failed"
            answer = f"Reasoning failed: {str(e)}"
            confidence = 0.0
            contexts = []
            sources = []

        execution_time = (time.perf_counter() - start_time) * 1000

        # Update stats
        self._update_stats(chain, confidence)

        result = ReasoningResult(
            result_id=str(uuid4())[:12],
            query=query,
            strategy=strategy,
            answer=answer,
            confidence=confidence,
            reasoning_chain=chain,
            sources=sources,
            contexts=contexts,
            execution_time_ms=execution_time,
        )

        logger.info(
            f"Reasoning completed: {strategy.value}, "
            f"{len(chain.steps)} steps, confidence={confidence:.2f}"
        )

        return result

    async def query(
        self,
        query: str,
        strategy: ReasoningStrategy = None,
        n_results: int = 5,
        context: dict = None,
    ) -> ReasoningResult:
        """
        Execute reasoning for a query. Alias for reason().

        This is an alias for the reason() method, provided for API consistency.

        Args:
            query: The query to reason about
            strategy: Reasoning strategy (auto-selected if None)
            n_results: Number of results to retrieve per query
            context: Additional context for reasoning

        Returns:
            ReasoningResult with answer and reasoning chain
        """
        return await self.reason(
            query=query,
            strategy=strategy,
            n_results=n_results,
            context=context,
        )

    def _select_strategy(self, query: str) -> ReasoningStrategy:
        """Auto-select the best reasoning strategy for a query."""
        query_lower = query.lower()

        # Multi-hop indicators
        if any(w in query_lower for w in ["which led to", "resulting in", "that caused", "chain"]):
            return ReasoningStrategy.MULTI_HOP

        # Comparison indicators
        if any(w in query_lower for w in ["compare", "versus", "vs", "difference between", "better"]):
            return ReasoningStrategy.COMPARATIVE

        # Complex/decomposable queries
        if " and " in query_lower and len(query.split()) > 10:
            return ReasoningStrategy.DECOMPOSITION

        # Step-by-step queries
        if any(w in query_lower for w in ["how", "explain", "why", "step", "process"]):
            return ReasoningStrategy.CHAIN_OF_THOUGHT

        # Hypothesis queries
        if any(w in query_lower for w in ["what if", "hypothetically", "predict", "might"]):
            return ReasoningStrategy.HYPOTHESIS_DRIVEN

        # Default to direct for simple queries
        return ReasoningStrategy.DIRECT

    async def _direct_reasoning(
        self,
        query: str,
        chain: ReasoningChain,
        n_results: int,
        context: dict,
    ) -> tuple[str, float, list[str], list[str]]:
        """Direct retrieval with minimal reasoning."""
        step = ReasoningStep(
            step_id=str(uuid4())[:8],
            step_number=1,
            step_type=StepType.QUERY,
            thought="Performing direct retrieval for the query",
            action=f"Search knowledge base for: {query}",
        )

        # Execute search
        contexts, sources = await self._search_kb(query, n_results)

        step.observation = f"Found {len(contexts)} relevant documents"
        step.confidence = 0.8 if contexts else 0.2
        step.sources = sources

        chain.add_step(step)

        # Synthesize answer
        if contexts:
            answer = self._synthesize_answer(query, contexts)
            confidence = 0.7
        else:
            answer = "No relevant information found in the knowledge base."
            confidence = 0.1

        return answer, confidence, contexts, sources

    async def _chain_of_thought_reasoning(
        self,
        query: str,
        chain: ReasoningChain,
        n_results: int,
        context: dict,
    ) -> tuple[str, float, list[str], list[str]]:
        """Chain-of-thought reasoning with explicit steps."""
        all_contexts = []
        all_sources = []

        # Step 1: Understand the query
        step1 = ReasoningStep(
            step_id=str(uuid4())[:8],
            step_number=1,
            step_type=StepType.ANALYZE,
            thought="First, I need to understand what information is needed",
            action=f"Analyzing query: {query}",
        )
        key_concepts = self._extract_key_concepts(query)
        step1.observation = f"Key concepts identified: {', '.join(key_concepts)}"
        step1.confidence = 0.8
        chain.add_step(step1)

        # Step 2: Search for each concept
        for i, concept in enumerate(key_concepts[:3]):
            step = ReasoningStep(
                step_id=str(uuid4())[:8],
                step_number=2 + i,
                step_type=StepType.QUERY,
                thought=f"Now searching for information about: {concept}",
                action=f"Search for: {concept}",
            )

            contexts, sources = await self._search_kb(concept, n_results)
            all_contexts.extend(contexts)
            all_sources.extend(sources)

            step.observation = f"Found {len(contexts)} results for '{concept}'"
            step.confidence = 0.7 if contexts else 0.3
            step.sources = sources

            chain.add_step(step)

        # Step 3: Synthesize
        synth_step = ReasoningStep(
            step_id=str(uuid4())[:8],
            step_number=len(key_concepts) + 2,
            step_type=StepType.SYNTHESIZE,
            thought="Now I'll combine the information to form a complete answer",
            action="Synthesizing findings",
        )

        answer = self._synthesize_answer(query, all_contexts)
        synth_step.observation = f"Synthesized answer from {len(all_contexts)} sources"
        synth_step.confidence = 0.75

        chain.add_step(synth_step)

        # Calculate overall confidence
        step_confidences = [s.confidence for s in chain.steps]
        confidence = sum(step_confidences) / len(step_confidences) if step_confidences else 0.5

        return answer, confidence, all_contexts, list(set(all_sources))

    async def _multi_hop_reasoning(
        self,
        query: str,
        chain: ReasoningChain,
        n_results: int,
        context: dict,
    ) -> tuple[str, float, list[str], list[str]]:
        """Multi-hop reasoning following references across documents."""
        all_contexts = []
        all_sources = []
        hop_count = 0
        max_hops = 3

        current_query = query

        while hop_count < max_hops and len(chain.steps) < self.max_reasoning_steps:
            hop_count += 1

            # Query step
            step = ReasoningStep(
                step_id=str(uuid4())[:8],
                step_number=len(chain.steps) + 1,
                step_type=StepType.QUERY,
                thought=f"Hop {hop_count}: Searching for information",
                action=f"Search: {current_query[:100]}",
            )

            contexts, sources = await self._search_kb(current_query, n_results)
            all_contexts.extend(contexts)
            all_sources.extend(sources)

            step.observation = f"Found {len(contexts)} results"
            step.sources = sources
            chain.add_step(step)

            if not contexts:
                break

            # Analyze step - look for follow-up queries
            analyze_step = ReasoningStep(
                step_id=str(uuid4())[:8],
                step_number=len(chain.steps) + 1,
                step_type=StepType.ANALYZE,
                thought="Analyzing results for referenced concepts",
                action="Extract references and related concepts",
            )

            references = self._extract_references(contexts)
            analyze_step.observation = f"Found {len(references)} references to follow"
            analyze_step.confidence = 0.6
            chain.add_step(analyze_step)

            if not references:
                break

            # Generate next query from references
            current_query = references[0]
            step.confidence = 0.7

        # Final synthesis
        synth_step = ReasoningStep(
            step_id=str(uuid4())[:8],
            step_number=len(chain.steps) + 1,
            step_type=StepType.CONCLUDE,
            thought=f"Completed {hop_count} hops of reasoning",
            action="Synthesize final answer",
        )

        answer = self._synthesize_answer(query, all_contexts)
        synth_step.observation = f"Answer synthesized from {len(all_contexts)} sources across {hop_count} hops"
        synth_step.confidence = 0.8 if hop_count > 1 else 0.6

        chain.add_step(synth_step)

        confidence = min(0.9, 0.5 + hop_count * 0.1)
        return answer, confidence, all_contexts, list(set(all_sources))

    async def _iterative_reasoning(
        self,
        query: str,
        chain: ReasoningChain,
        n_results: int,
        context: dict,
    ) -> tuple[str, float, list[str], list[str]]:
        """Iteratively refine the query based on results."""
        all_contexts = []
        all_sources = []
        iteration = 0
        max_iterations = 3
        current_query = query
        prev_confidence = 0.0

        while iteration < max_iterations:
            iteration += 1

            # Search step
            step = ReasoningStep(
                step_id=str(uuid4())[:8],
                step_number=len(chain.steps) + 1,
                step_type=StepType.QUERY,
                thought=f"Iteration {iteration}: Searching with refined query",
                action=f"Search: {current_query[:100]}",
            )

            contexts, sources = await self._search_kb(current_query, n_results)
            all_contexts.extend(contexts)
            all_sources.extend(sources)

            # Assess quality
            confidence = self._assess_result_quality(query, contexts)
            step.observation = f"Found {len(contexts)} results (confidence: {confidence:.2f})"
            step.confidence = confidence
            step.sources = sources
            chain.add_step(step)

            # Check if we should stop
            if confidence >= 0.8 or abs(confidence - prev_confidence) < 0.05:
                break

            # Refine query
            refine_step = ReasoningStep(
                step_id=str(uuid4())[:8],
                step_number=len(chain.steps) + 1,
                step_type=StepType.REFINE,
                thought="Results not satisfactory, refining query",
                action="Expand and refine search terms",
            )

            current_query = self._refine_query(query, contexts)
            refine_step.observation = f"Refined query to: {current_query[:100]}"
            refine_step.confidence = 0.5
            chain.add_step(refine_step)

            prev_confidence = confidence

        answer = self._synthesize_answer(query, all_contexts)
        return answer, confidence, all_contexts, list(set(all_sources))

    async def _hypothesis_reasoning(
        self,
        query: str,
        chain: ReasoningChain,
        n_results: int,
        context: dict,
    ) -> tuple[str, float, list[str], list[str]]:
        """Generate and validate hypotheses."""
        all_contexts = []
        all_sources = []

        # Step 1: Generate hypotheses
        hyp_step = ReasoningStep(
            step_id=str(uuid4())[:8],
            step_number=1,
            step_type=StepType.HYPOTHESIZE,
            thought="Generating hypotheses based on the query",
            action=f"Generate hypotheses for: {query}",
        )

        hypotheses = self._generate_hypotheses(query)
        hyp_step.observation = f"Generated {len(hypotheses)} hypotheses"
        hyp_step.confidence = 0.6
        chain.add_step(hyp_step)

        # Step 2: Test each hypothesis
        hypothesis_results = []
        for i, hypothesis in enumerate(hypotheses[:3]):
            test_step = ReasoningStep(
                step_id=str(uuid4())[:8],
                step_number=len(chain.steps) + 1,
                step_type=StepType.VALIDATE,
                thought=f"Testing hypothesis: {hypothesis}",
                action=f"Search for evidence",
            )

            contexts, sources = await self._search_kb(hypothesis, n_results)
            all_contexts.extend(contexts)
            all_sources.extend(sources)

            support_score = self._evaluate_hypothesis_support(hypothesis, contexts)
            test_step.observation = f"Support score: {support_score:.2f}"
            test_step.confidence = support_score
            test_step.sources = sources
            chain.add_step(test_step)

            hypothesis_results.append((hypothesis, support_score))

        # Step 3: Conclude based on best supported hypothesis
        best_hypothesis, best_score = max(hypothesis_results, key=lambda x: x[1])

        conclude_step = ReasoningStep(
            step_id=str(uuid4())[:8],
            step_number=len(chain.steps) + 1,
            step_type=StepType.CONCLUDE,
            thought=f"Best supported hypothesis: {best_hypothesis}",
            action="Form conclusion",
        )

        answer = self._synthesize_answer(query, all_contexts, best_hypothesis)
        conclude_step.observation = f"Conclusion based on hypothesis with {best_score:.2f} support"
        conclude_step.confidence = best_score
        chain.add_step(conclude_step)

        return answer, best_score, all_contexts, list(set(all_sources))

    async def _comparative_reasoning(
        self,
        query: str,
        chain: ReasoningChain,
        n_results: int,
        context: dict,
    ) -> tuple[str, float, list[str], list[str]]:
        """Compare information from multiple sources."""
        all_contexts = []
        all_sources = []

        # Extract comparison targets
        targets = self._extract_comparison_targets(query)

        # Search for each target
        target_contexts = {}
        for target in targets[:3]:
            step = ReasoningStep(
                step_id=str(uuid4())[:8],
                step_number=len(chain.steps) + 1,
                step_type=StepType.QUERY,
                thought=f"Gathering information about: {target}",
                action=f"Search for: {target}",
            )

            contexts, sources = await self._search_kb(target, n_results)
            target_contexts[target] = contexts
            all_contexts.extend(contexts)
            all_sources.extend(sources)

            step.observation = f"Found {len(contexts)} results for '{target}'"
            step.sources = sources
            step.confidence = 0.7 if contexts else 0.3
            chain.add_step(step)

        # Compare and synthesize
        compare_step = ReasoningStep(
            step_id=str(uuid4())[:8],
            step_number=len(chain.steps) + 1,
            step_type=StepType.SYNTHESIZE,
            thought="Comparing information across sources",
            action="Generate comparison",
        )

        answer = self._synthesize_comparison(targets, target_contexts)
        compare_step.observation = f"Comparison completed for {len(targets)} items"
        compare_step.confidence = 0.75
        chain.add_step(compare_step)

        return answer, 0.75, all_contexts, list(set(all_sources))

    async def _decomposition_reasoning(
        self,
        query: str,
        chain: ReasoningChain,
        n_results: int,
        context: dict,
    ) -> tuple[str, float, list[str], list[str]]:
        """Decompose complex query into sub-queries."""
        all_contexts = []
        all_sources = []

        # Decompose query
        decomp_step = ReasoningStep(
            step_id=str(uuid4())[:8],
            step_number=1,
            step_type=StepType.ANALYZE,
            thought="Breaking down complex query into sub-questions",
            action="Decompose query",
        )

        sub_queries = self._decompose_query(query)
        decomp_step.observation = f"Generated {len(sub_queries)} sub-queries"
        decomp_step.confidence = 0.8
        chain.add_step(decomp_step)

        # Answer each sub-query
        sub_answers = []
        for sub_query in sub_queries[:5]:
            step = ReasoningStep(
                step_id=str(uuid4())[:8],
                step_number=len(chain.steps) + 1,
                step_type=StepType.QUERY,
                thought=f"Answering sub-question",
                action=f"Search: {sub_query[:80]}",
            )

            contexts, sources = await self._search_kb(sub_query, n_results)
            all_contexts.extend(contexts)
            all_sources.extend(sources)

            sub_answer = self._synthesize_answer(sub_query, contexts)
            sub_answers.append((sub_query, sub_answer))

            step.observation = f"Sub-answer generated"
            step.sources = sources
            step.confidence = 0.7 if contexts else 0.3
            chain.add_step(step)

        # Combine sub-answers
        synth_step = ReasoningStep(
            step_id=str(uuid4())[:8],
            step_number=len(chain.steps) + 1,
            step_type=StepType.SYNTHESIZE,
            thought="Combining sub-answers into final answer",
            action="Synthesize",
        )

        answer = self._combine_sub_answers(query, sub_answers)
        synth_step.observation = f"Combined {len(sub_answers)} sub-answers"
        synth_step.confidence = 0.8
        chain.add_step(synth_step)

        return answer, 0.8, all_contexts, list(set(all_sources))

    # ========== Helper Methods ==========

    async def _search_kb(self, query: str, n_results: int) -> tuple[list[str], list[str]]:
        """Search the knowledge base."""
        if not self.knowledge_base:
            return [], []

        try:
            result = self.knowledge_base.search(query=query, n_results=n_results)
            contexts = [r.content for r in result.results]
            sources = [r.source for r in result.results]
            return contexts, sources
        except Exception as e:
            logger.warning(f"KB search failed: {e}")
            return [], []

    def _extract_key_concepts(self, query: str) -> list[str]:
        """Extract key concepts from a query."""
        # Remove common words and extract meaningful terms
        stop_words = {"what", "how", "why", "when", "where", "is", "are", "the", "a", "an", "in", "on", "for", "to", "of"}
        words = query.lower().split()
        concepts = [w for w in words if w not in stop_words and len(w) > 2]

        # Also look for multi-word phrases
        phrases = re.findall(r'"([^"]+)"', query)
        concepts.extend(phrases)

        return concepts[:5]

    def _extract_references(self, contexts: list[str]) -> list[str]:
        """Extract referenced concepts from contexts."""
        references = []
        combined = " ".join(contexts)

        # Look for "see also", "related to", etc.
        patterns = [
            r"see also[:\s]+([^.]+)",
            r"related to[:\s]+([^.]+)",
            r"similar to[:\s]+([^.]+)",
            r"as described in[:\s]+([^.]+)",
        ]

        for pattern in patterns:
            matches = re.findall(pattern, combined, re.IGNORECASE)
            references.extend(matches)

        return references[:3]

    def _generate_hypotheses(self, query: str) -> list[str]:
        """Generate hypotheses based on query."""
        # Simple hypothesis generation
        base_hypotheses = [
            f"The answer involves {query}",
            f"This is related to security concerns in IoT",
            f"The solution requires understanding device behavior",
        ]

        # Add query-specific hypotheses
        if "attack" in query.lower():
            base_hypotheses.append("This involves a known attack pattern")
        if "vulnerability" in query.lower():
            base_hypotheses.append("This is a documented CVE or weakness")

        return base_hypotheses

    def _evaluate_hypothesis_support(self, hypothesis: str, contexts: list[str]) -> float:
        """Evaluate how well contexts support a hypothesis."""
        if not contexts:
            return 0.0

        # Simple keyword overlap scoring
        hyp_words = set(hypothesis.lower().split())
        total_overlap = 0

        for context in contexts:
            ctx_words = set(context.lower().split())
            overlap = len(hyp_words & ctx_words) / len(hyp_words) if hyp_words else 0
            total_overlap += overlap

        return min(1.0, total_overlap / len(contexts))

    def _assess_result_quality(self, query: str, contexts: list[str]) -> float:
        """Assess the quality/relevance of results."""
        if not contexts:
            return 0.0

        query_words = set(query.lower().split())
        total_relevance = 0

        for context in contexts:
            ctx_words = set(context.lower().split())
            overlap = len(query_words & ctx_words)
            relevance = overlap / len(query_words) if query_words else 0
            total_relevance += relevance

        return min(1.0, total_relevance / len(contexts))

    def _refine_query(self, original_query: str, contexts: list[str]) -> str:
        """Refine query based on initial results."""
        # Extract additional terms from contexts
        combined = " ".join(contexts[:3])
        words = combined.lower().split()

        # Find frequent relevant terms
        term_freq = {}
        for word in words:
            if len(word) > 4 and word not in original_query.lower():
                term_freq[word] = term_freq.get(word, 0) + 1

        # Add top terms to query
        top_terms = sorted(term_freq.items(), key=lambda x: x[1], reverse=True)[:2]
        refinement = " ".join(term for term, _ in top_terms)

        return f"{original_query} {refinement}".strip()

    def _extract_comparison_targets(self, query: str) -> list[str]:
        """Extract items to compare from query."""
        # Look for patterns like "X vs Y", "X and Y", "compare X with Y"
        patterns = [
            r"compare\s+(\w+)\s+(?:and|with|vs|versus)\s+(\w+)",
            r"(\w+)\s+vs\.?\s+(\w+)",
            r"difference between\s+(\w+)\s+and\s+(\w+)",
        ]

        for pattern in patterns:
            match = re.search(pattern, query, re.IGNORECASE)
            if match:
                return list(match.groups())

        # Fallback: extract nouns
        words = query.split()
        return [w for w in words if len(w) > 3][:2]

    def _decompose_query(self, query: str) -> list[str]:
        """Decompose complex query into sub-queries."""
        sub_queries = []

        # Split on "and" or "also"
        if " and " in query.lower():
            parts = re.split(r"\s+and\s+", query, flags=re.IGNORECASE)
            sub_queries.extend(parts)

        # Generate what/how/why variations
        concepts = self._extract_key_concepts(query)
        for concept in concepts[:3]:
            sub_queries.append(f"What is {concept}?")

        return sub_queries[:5] if sub_queries else [query]

    def _synthesize_answer(
        self,
        query: str,
        contexts: list[str],
        hypothesis: str = None,
    ) -> str:
        """Synthesize an answer from contexts."""
        if not contexts:
            return "No relevant information found."

        # Simple synthesis: combine relevant excerpts
        combined = "\n\n".join(contexts[:5])

        if hypothesis:
            return f"Based on the hypothesis '{hypothesis}':\n\n{combined}"

        return f"Based on {len(contexts)} sources:\n\n{combined}"

    def _synthesize_comparison(
        self,
        targets: list[str],
        target_contexts: dict,
    ) -> str:
        """Synthesize a comparison from contexts."""
        parts = []
        for target in targets:
            contexts = target_contexts.get(target, [])
            if contexts:
                parts.append(f"**{target}**:\n{contexts[0][:300]}")
            else:
                parts.append(f"**{target}**: No information found.")

        return "\n\n".join(parts)

    def _combine_sub_answers(
        self,
        query: str,
        sub_answers: list[tuple[str, str]],
    ) -> str:
        """Combine sub-answers into final answer."""
        parts = []
        for sub_query, answer in sub_answers:
            parts.append(f"**Q**: {sub_query}\n**A**: {answer}")

        return f"Answer to: {query}\n\n" + "\n\n".join(parts)

    def _update_stats(self, chain: ReasoningChain, confidence: float) -> None:
        """Update reasoning statistics."""
        n = self._stats["total_reasoning_tasks"]
        step_count = len(chain.steps)

        # Update rolling averages
        self._stats["average_steps"] = (
            self._stats["average_steps"] * (n - 1) + step_count
        ) / n

        self._stats["average_confidence"] = (
            self._stats["average_confidence"] * (n - 1) + confidence
        ) / n

    def get_stats(self) -> dict:
        """Get reasoning statistics."""
        return self._stats.copy()


# Global instance
_reasoning_engine: Optional[ReasoningEngine] = None


def get_reasoning_engine(knowledge_base: Any = None) -> ReasoningEngine:
    """Get or create the global reasoning engine instance."""
    global _reasoning_engine
    if _reasoning_engine is None:
        _reasoning_engine = ReasoningEngine(knowledge_base=knowledge_base)
    return _reasoning_engine
