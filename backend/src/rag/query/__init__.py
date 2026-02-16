"""
Query Module - Advanced RAG query capabilities.

This module provides:
- Multi-step query orchestration with decomposition
- Hybrid search (semantic + keyword with RRF fusion)
- Provenance tracking for document → chunk → response tracing
- Confidence scoring
"""

from src.rag.query.query_orchestrator import (
    AggregatedResult,
    ProvenanceRecord,
    QueryPlan,
    QueryStep,
    RAGQueryOrchestrator,
    get_query_orchestrator,
    initialize_query_orchestrator,
)
from src.rag.query.hybrid_search import (
    BM25Index,
    FusionMethod,
    HybridSearch,
    HybridSearchResult,
    QueryExpander,
    SearchMode,
    SearchResult,
    get_hybrid_search,
)

__all__ = [
    # Query Orchestrator
    "AggregatedResult",
    "ProvenanceRecord",
    "QueryPlan",
    "QueryStep",
    "RAGQueryOrchestrator",
    "get_query_orchestrator",
    "initialize_query_orchestrator",
    # Hybrid Search
    "BM25Index",
    "FusionMethod",
    "HybridSearch",
    "HybridSearchResult",
    "QueryExpander",
    "SearchMode",
    "SearchResult",
    "get_hybrid_search",
]
