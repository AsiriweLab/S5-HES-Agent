"""
RAG Layer - Agentic RAG Intelligence components.

This module provides:
- Vector storage with ChromaDB
- Embedding services
- Knowledge base management
- Multi-step query orchestration
- Hybrid search (semantic + keyword)
- Multi-source adapters (academic, threat intel, device specs)
"""

from .vector_store_module import ChromaVectorStore, get_vector_store
from .embeddings import EmbeddingService, get_embedding_service
from .knowledge_base import (
    CollectionType,
    KnowledgeBaseService,
    KnowledgeDocument,
    RAGContext,
    get_knowledge_base,
)

# Query module exports
from .query import (
    AggregatedResult,
    BM25Index,
    FusionMethod,
    HybridSearch,
    HybridSearchResult,
    ProvenanceRecord,
    QueryExpander,
    QueryPlan,
    QueryStep,
    RAGQueryOrchestrator,
    SearchMode,
    SearchResult,
    get_hybrid_search,
    get_query_orchestrator,
    initialize_query_orchestrator,
)

# Adapter exports
from .adapters import (
    # Academic
    AcademicPaper,
    AcademicPaperAdapter,
    AcademicSource,
    get_academic_adapter,
    # Threat Intel
    CVEEntry,
    CWEEntry,
    MitreAttackTechnique,
    ThreatIntelAdapter,
    ThreatSource,
    get_threat_intel_adapter,
    # Device Specs
    CommunicationProtocol,
    DeviceCategory,
    DeviceSpecAdapter,
    DeviceSpecification,
    ProtocolSpecification,
    SecurityAdvisory,
    get_device_spec_adapter,
)

__all__ = [
    # Core RAG
    "ChromaVectorStore",
    "get_vector_store",
    "EmbeddingService",
    "get_embedding_service",
    "CollectionType",
    "KnowledgeBaseService",
    "KnowledgeDocument",
    "RAGContext",
    "get_knowledge_base",
    # Query Orchestration
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
    # Academic Adapter
    "AcademicPaper",
    "AcademicPaperAdapter",
    "AcademicSource",
    "get_academic_adapter",
    # Threat Intel Adapter
    "CVEEntry",
    "CWEEntry",
    "MitreAttackTechnique",
    "ThreatIntelAdapter",
    "ThreatSource",
    "get_threat_intel_adapter",
    # Device Spec Adapter
    "CommunicationProtocol",
    "DeviceCategory",
    "DeviceSpecAdapter",
    "DeviceSpecification",
    "ProtocolSpecification",
    "SecurityAdvisory",
    "get_device_spec_adapter",
]
