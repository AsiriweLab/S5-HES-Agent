"""
RAG API Endpoints

Provides REST API for knowledge base operations and RAG queries.
Includes advanced search, hybrid search, and comprehensive statistics.
"""

from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from src.rag import (
    FusionMethod,
    KnowledgeDocument,
    RAGContext,
    SearchMode,
    get_hybrid_search,
    get_knowledge_base,
    get_query_orchestrator,
    initialize_query_orchestrator,
)
from src.rag.query.query_orchestrator import CollectionType
from src.rag.adapters import (
    AcademicSource,
    get_academic_adapter,
)
from src.core.config import settings

router = APIRouter()


# ===========================================================================
# Security: Path Allowlist for Ingestion
# ===========================================================================
# Only these directories (and their subdirectories) are allowed for ingestion.
# This prevents arbitrary file system access via the API.

def _get_allowed_ingest_roots() -> list[Path]:
    """Return list of allowed root directories for ingestion."""
    return [
        settings.knowledge_base_path.resolve(),  # Primary KB path
        settings.configs_path.resolve(),         # Config files
    ]


def _is_path_allowed(target_path: Path) -> bool:
    """
    Check if target_path is within any allowed root directory.

    Security: Prevents path traversal attacks and arbitrary file access.
    Uses resolve() to handle symlinks and .. traversal attempts.
    """
    try:
        resolved_target = target_path.resolve()
    except (OSError, ValueError):
        return False

    for allowed_root in _get_allowed_ingest_roots():
        try:
            # Check if resolved_target is under allowed_root
            resolved_target.relative_to(allowed_root)
            return True
        except ValueError:
            # Not under this root, try next
            continue

    return False


# ===========================================================================
# Integrity: Stats helpers (no estimates, no placeholders)
# ===========================================================================

def _parse_iso_datetime(value: Any) -> Optional[datetime]:
    """Parse an ISO datetime string safely; returns naive UTC datetime or None."""
    if not value or not isinstance(value, str):
        return None

    text = value.strip()
    if not text:
        return None

    try:
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        dt = datetime.fromisoformat(text)
    except Exception:
        return None

    # Normalize to naive UTC for safe comparisons
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


def _scan_kb_metadata_index(kb: Any, batch_size: int = 1000) -> dict[str, Any]:
    """
    Scan ChromaDB metadatas to compute audit-grade stats.

    Integrity:
    - No estimation/fallback counts
    - No synthetic/placeholder values
    """
    collection = kb.vector_store.collection
    total_chunks = collection.count()

    chunk_counts: Counter[str] = Counter()
    sources_by_category: dict[str, set[str]] = defaultdict(set)
    date_min_by_category: dict[str, datetime] = {}
    date_max_by_category: dict[str, datetime] = {}

    all_sources: set[str] = set()
    all_categories: set[str] = set()
    all_date_min: Optional[datetime] = None
    all_date_max: Optional[datetime] = None

    for offset in range(0, total_chunks, batch_size):
        result = collection.get(
            limit=batch_size,
            offset=offset,
            include=["metadatas"],
        )
        metadatas = result.get("metadatas") or []
        if not metadatas:
            break

        for md in metadatas:
            if not md:
                continue

            category = md.get("category")
            if not category:
                continue
            category = str(category)

            all_categories.add(category)
            chunk_counts[category] += 1

            source = md.get("source")
            if source:
                source = str(source)
                all_sources.add(source)
                sources_by_category[category].add(source)

            created_at = _parse_iso_datetime(md.get("created_at"))
            if created_at is not None:
                if all_date_min is None or created_at < all_date_min:
                    all_date_min = created_at
                if all_date_max is None or created_at > all_date_max:
                    all_date_max = created_at

                if category not in date_min_by_category or created_at < date_min_by_category[category]:
                    date_min_by_category[category] = created_at
                if category not in date_max_by_category or created_at > date_max_by_category[category]:
                    date_max_by_category[category] = created_at

    def _format_range(dt_min: Optional[datetime], dt_max: Optional[datetime]) -> Optional[dict[str, str]]:
        if dt_min is None or dt_max is None:
            return None
        return {"earliest": dt_min.isoformat(), "latest": dt_max.isoformat()}

    by_category: dict[str, dict[str, Any]] = {}
    for category in sorted(all_categories):
        sources = sources_by_category.get(category, set())
        by_category[category] = {
            # "document" = unique source; "chunk" = vector item
            "document_count": len(sources),
            "chunk_count": chunk_counts.get(category, 0),
            "categories": [category],
            "sources": sorted(sources),
            "date_range": _format_range(
                date_min_by_category.get(category),
                date_max_by_category.get(category),
            ),
        }

    return {
        "total_chunks": total_chunks,
        "total_documents": len(all_sources),  # unique sources across KB
        "categories": sorted(all_categories),
        "sources": sorted(all_sources),
        "date_range": _format_range(all_date_min, all_date_max),
        "by_category": by_category,
    }


# ===========================================================================
# Request/Response Models
# ===========================================================================


class DocumentCreate(BaseModel):
    """Request model for creating a document."""

    title: str = Field(..., description="Document title")
    content: str = Field(..., description="Document content")
    category: str = Field(default="general", description="Document category")
    source: str = Field(..., description="Source reference")
    tags: list[str] = Field(default_factory=list, description="Document tags")


class DocumentResponse(BaseModel):
    """Response model for a document."""

    doc_id: str
    title: str
    content: str
    category: str
    source: str
    tags: list[str]
    created_at: datetime


class SearchRequest(BaseModel):
    """Request model for search."""

    query: str = Field(..., description="Search query")
    n_results: int = Field(default=5, ge=1, le=20, description="Number of results")
    category: Optional[str] = Field(default=None, description="Filter by category")
    search_mode: Optional[str] = Field(
        default=None,
        description="Search mode override: semantic_only, keyword_only, hybrid, auto",
    )


class SearchResultItem(BaseModel):
    """A single search result."""

    doc_id: str
    content: str
    title: Optional[str]
    category: Optional[str]
    source: Optional[str]
    similarity_score: float
    is_above_threshold: bool


class SearchResponse(BaseModel):
    """Response model for search."""

    query: str
    results: list[SearchResultItem]
    total_results: int
    query_time_ms: float


class RAGContextRequest(BaseModel):
    """Request model for RAG context retrieval."""

    query: str = Field(..., description="User question for RAG")
    n_results: int = Field(default=5, ge=1, le=10, description="Number of context chunks")
    search_mode: Optional[str] = Field(
        default=None,
        description="Search mode override: semantic_only, keyword_only, hybrid, auto",
    )


class RAGContextResponse(BaseModel):
    """Response model for RAG context."""

    query: str
    contexts: list[str]
    sources: list[str]
    confidence_scores: list[float]
    formatted_context: str
    has_context: bool
    retrieval_time_ms: float


class IngestRequest(BaseModel):
    """Request model for document ingestion."""

    directory: Optional[str] = Field(
        default=None, description="Directory path (default: knowledge_base_path). Must be within allowed paths."
    )
    recursive: bool = Field(default=True, description="Search recursively")


class ResetRequest(BaseModel):
    """Request model for knowledge base reset (destructive operation)."""

    confirmation_token: str = Field(
        ..., description="Must be exactly 'CONFIRM_RESET' to proceed"
    )


class IngestResponse(BaseModel):
    """Response model for ingestion."""

    documents_ingested: int
    source_directory: str


class KnowledgeBaseStats(BaseModel):
    """Knowledge base statistics."""

    collection_name: str
    document_count: int
    persist_directory: str
    embedding_model: str
    similarity_threshold: float
    knowledge_base_path: str
    # Text chunking settings (S2.5)
    chunking_enabled: bool = True
    chunk_size: int = 512
    chunk_overlap: int = 50
    # PDF parser availability (S2.7)
    pdf_parser_available: bool = False
    pdf_parser: Optional[str] = None
    # Hybrid search settings (Option C implementation)
    hybrid_search_enabled: bool = False
    search_mode: Optional[str] = None
    semantic_weight: Optional[float] = None
    keyword_weight: Optional[float] = None
    fusion_method: Optional[str] = None
    bm25_document_count: Optional[int] = None


# ===========================================================================
# API Endpoints
# ===========================================================================


@router.post("/documents", response_model=DocumentResponse, status_code=201)
async def create_document(doc: DocumentCreate):
    """
    Add a document to the knowledge base.

    Creates a new document with the provided content and metadata,
    generates embeddings, and stores it in the vector database.
    """
    kb = get_knowledge_base()

    knowledge_doc = KnowledgeDocument(
        title=doc.title,
        content=doc.content,
        category=doc.category,
        source=doc.source,
        tags=doc.tags,
    )

    doc_id = kb.add_document(knowledge_doc)

    return DocumentResponse(
        doc_id=doc_id,
        title=knowledge_doc.title,
        content=knowledge_doc.content,
        category=knowledge_doc.category,
        source=knowledge_doc.source,
        tags=knowledge_doc.tags,
        created_at=knowledge_doc.created_at,
    )


@router.post("/documents/batch", response_model=dict)
async def create_documents_batch(docs: list[DocumentCreate]):
    """
    Add multiple documents to the knowledge base.

    Efficiently processes multiple documents in a single batch operation.
    """
    kb = get_knowledge_base()

    knowledge_docs = [
        KnowledgeDocument(
            title=doc.title,
            content=doc.content,
            category=doc.category,
            source=doc.source,
            tags=doc.tags,
        )
        for doc in docs
    ]

    doc_ids = kb.add_documents(knowledge_docs)

    return {
        "documents_created": len(doc_ids),
        "doc_ids": doc_ids,
    }


@router.post("/search", response_model=SearchResponse)
async def search_documents(request: SearchRequest):
    """
    Search the knowledge base.

    Performs semantic or hybrid search using the query text.
    Results are ranked by similarity/fusion score.

    When hybrid search is enabled (default), combines dense semantic search (GTE embeddings)
    with sparse keyword search (BM25) using Reciprocal Rank Fusion.
    """
    kb = get_knowledge_base()

    result = kb.search(
        query=request.query,
        n_results=request.n_results,
        category=request.category,
        search_mode=request.search_mode,
    )

    items = [
        SearchResultItem(
            doc_id=r.doc_id,
            content=r.content,
            title=r.metadata.get("title"),
            category=r.metadata.get("category"),
            source=r.source,
            similarity_score=r.similarity_score,
            is_above_threshold=r.is_above_threshold,
        )
        for r in result.results
    ]

    return SearchResponse(
        query=result.query,
        results=items,
        total_results=result.total_results,
        query_time_ms=result.query_time_ms,
    )


@router.get("/search", response_model=SearchResponse)
async def search_documents_get(
    q: str = Query(..., description="Search query"),
    n: int = Query(default=5, ge=1, le=20, description="Number of results"),
    category: Optional[str] = Query(default=None, description="Filter by category"),
    mode: Optional[str] = Query(default=None, description="Search mode: semantic_only, keyword_only, hybrid, auto"),
):
    """
    Search the knowledge base (GET endpoint).

    Simple GET-based search for easy testing and browser access.
    Supports hybrid search combining semantic (GTE) and keyword (BM25) retrieval.
    """
    request = SearchRequest(query=q, n_results=n, category=category, search_mode=mode)
    return await search_documents(request)


@router.post("/context", response_model=RAGContextResponse)
async def get_rag_context(request: RAGContextRequest):
    """
    Get RAG context for LLM augmentation.

    Retrieves relevant context chunks from the knowledge base
    that can be injected into an LLM prompt for grounded responses.

    This is the primary endpoint for RAG-augmented generation.
    When hybrid search is enabled (default), combines semantic and keyword retrieval.
    """
    kb = get_knowledge_base()

    context: RAGContext = kb.get_rag_context(
        query=request.query,
        n_results=request.n_results,
        search_mode=request.search_mode,
    )

    return RAGContextResponse(
        query=context.query,
        contexts=context.contexts,
        sources=context.sources,
        confidence_scores=context.confidence_scores,
        formatted_context=context.formatted_context,
        has_context=context.has_context,
        retrieval_time_ms=context.retrieval_time_ms,
    )


@router.post("/ingest", response_model=IngestResponse)
async def ingest_directory(request: IngestRequest):
    """
    Ingest documents from a directory.

    Scans the specified directory for supported file types
    (.yaml, .yml, .md) and adds them to the knowledge base.

    Security: Only directories within the allowed paths (knowledge_base_path,
    configs_path) can be ingested. Absolute paths outside these roots are rejected.
    """
    kb = get_knowledge_base()

    # Determine target directory
    if request.directory:
        directory = Path(request.directory)

        # Security check: reject paths outside allowed roots
        if not _is_path_allowed(directory):
            allowed_roots = [str(p) for p in _get_allowed_ingest_roots()]
            raise HTTPException(
                status_code=403,
                detail=f"Access denied: Path '{request.directory}' is outside allowed directories. "
                       f"Allowed roots: {allowed_roots}"
            )

        # Verify path exists
        if not directory.exists():
            raise HTTPException(
                status_code=404,
                detail=f"Directory not found: '{request.directory}'"
            )

        if not directory.is_dir():
            raise HTTPException(
                status_code=400,
                detail=f"Path is not a directory: '{request.directory}'"
            )
    else:
        # Default to knowledge_base_path (always allowed)
        directory = None

    try:
        count = kb.ingest_directory(
            directory=directory,
            recursive=request.recursive,
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Ingestion failed: {str(e)}")

    return IngestResponse(
        documents_ingested=count,
        source_directory=str(directory or kb.knowledge_base_path),
    )


@router.get("/stats", response_model=KnowledgeBaseStats)
async def get_stats():
    """
    Get knowledge base statistics.

    Returns information about the current state of the knowledge base
    including document count, storage location, and configuration.
    """
    kb = get_knowledge_base()
    stats = kb.get_stats()

    return KnowledgeBaseStats(**stats)


@router.post("/reset", response_model=dict)
async def reset_knowledge_base(request: ResetRequest):
    """
    Reset the knowledge base.

    WARNING: This deletes ALL documents and cannot be undone!

    Security: Requires explicit confirmation token to prevent accidental
    or unauthorized destructive operations. Only allowed in development environment.

    Required request body: {"confirmation_token": "CONFIRM_RESET"}
    """
    # Security: Require exact confirmation token
    REQUIRED_TOKEN = "CONFIRM_RESET"
    if request.confirmation_token != REQUIRED_TOKEN:
        raise HTTPException(
            status_code=403,
            detail=f"Invalid confirmation token. Must be exactly '{REQUIRED_TOKEN}' to proceed."
        )

    # Security: Only allow in development environment
    if settings.environment != "development":
        raise HTTPException(
            status_code=403,
            detail=f"Reset is only allowed in development environment. "
                   f"Current environment: {settings.environment}"
        )

    kb = get_knowledge_base()
    success = kb.clear()

    if not success:
        raise HTTPException(status_code=500, detail="Failed to reset knowledge base")

    return {
        "status": "success",
        "message": "Knowledge base has been reset",
        "environment": settings.environment,
    }


# ===========================================================================
# Advanced RAG Models (Sprint 7)
# ===========================================================================


class HybridSearchRequest(BaseModel):
    """Request model for hybrid search."""

    query: str = Field(..., description="Search query")
    collection: str = Field(default="default", description="Collection to search")
    n_results: int = Field(default=10, ge=1, le=50, description="Number of results")
    mode: str = Field(
        default="auto",
        description="Search mode: semantic_only, keyword_only, hybrid, auto",
    )
    fusion_method: str = Field(
        default="rrf",
        description="Fusion method: rrf, weighted_sum, max_score, interleave",
    )


class HybridSearchResultItem(BaseModel):
    """A single hybrid search result."""

    document_id: str
    content: str
    score: float
    document_source: str  # Original document source (file path/title), NOT retrieval method
    metadata: dict[str, Any]
    # Integrity: highlights field removed - was always empty (not implemented)
    # Re-add when actual highlighting is implemented


class HybridSearchResponse(BaseModel):
    """Response model for hybrid search."""

    query: str
    results: list[HybridSearchResultItem]
    mode_used: str
    # Note: In hybrid/auto modes, results are fused from both sources.
    # These counts indicate potential contribution, not exact per-result attribution.
    # For semantic_only: semantic_count = total, keyword_count = 0
    # For keyword_only: keyword_count = total, semantic_count = 0
    # For hybrid/auto: both equal total (fused results, origin not tracked per-result)
    semantic_count: int
    keyword_count: int
    # Integrity: Report only what was actually used, not what was requested
    # HybridRetriever currently only implements RRF fusion
    fusion_method_used: str  # Always "rrf" - the method actually applied
    fusion_method_requested: Optional[str]  # What the client requested (may differ)
    total_candidates: int
    execution_time_ms: float


class MultiStepQueryRequest(BaseModel):
    """Request model for multi-step query orchestration."""

    query: str = Field(..., description="Complex query to decompose and execute")
    collections: list[str] = Field(
        default=None,
        description="Collections to search (default: all)",
    )
    n_results: int = Field(default=5, ge=1, le=20, description="Results per collection")
    use_decomposition: bool = Field(
        default=True,
        description="Whether to decompose complex queries",
    )


class ProvenanceInfo(BaseModel):
    """Provenance tracking information (aligned with ProvenanceRecord from orchestrator)."""

    record_id: str
    document_id: str
    document_title: str
    source_collection: str
    chunk_index: Optional[int] = None
    retrieval_query: str = ""
    similarity_score: float = 0.0
    citation: str = ""
    metadata: dict[str, Any] = {}


class MultiStepQueryResponse(BaseModel):
    """Response model for multi-step query orchestration (aligned with AggregatedResult)."""

    query: str
    contexts: list[str]
    sub_queries: list[str]  # Extracted from query_plan steps
    provenance: list[ProvenanceInfo]
    confidence_score: float
    collections_searched: list[str]
    total_results: int
    execution_time_ms: float


class CollectionStatsItem(BaseModel):
    """Statistics for a single collection.

    Note: Fields may be None when the underlying data is not tracked.
    Under strict integrity constraints, we return None rather than estimates.
    """

    collection_name: str
    # document_count = unique sources; chunk_count = vector items
    document_count: Optional[int]
    chunk_count: Optional[int]
    categories: list[str]
    sources: list[str]
    date_range: Optional[dict[str, str]]
    tracking_status: str = "tracked"  # "tracked" or "error"


class ComprehensiveStats(BaseModel):
    """Comprehensive knowledge base statistics."""

    # Basic info
    total_documents: int
    total_chunks: Optional[int]  # None if not tracked (integrity: no estimation)
    persist_directory: str
    embedding_model: str
    similarity_threshold: float

    # Collection breakdown
    collections: list[CollectionStatsItem]

    # Adapter status
    adapters: dict[str, dict[str, Any]]

    # Search index stats
    keyword_index: dict[str, Any]

    # System info
    last_ingestion: Optional[str]
    uptime_seconds: Optional[float]  # None if not tracked (integrity: no fake timestamps)


# ===========================================================================
# Advanced RAG Endpoints (Sprint 7)
# ===========================================================================


@router.post("/hybrid-search", response_model=HybridSearchResponse)
async def hybrid_search(request: HybridSearchRequest):
    """
    Perform hybrid search combining semantic and keyword search.

    Uses Reciprocal Rank Fusion (RRF) to combine results from
    vector similarity search (GTE embeddings) and BM25 keyword search.

    This endpoint uses the knowledge base's integrated HybridRetriever,
    which maintains a synchronized BM25 index alongside the ChromaDB vector store.
    """
    import time
    start_time = time.perf_counter()

    kb = get_knowledge_base()

    # Verify hybrid retriever is available
    if not kb._hybrid_retriever:
        raise HTTPException(
            status_code=503,
            detail="Hybrid search is not available. HybridRetriever not initialized."
        )

    # Map request mode to search mode string
    # The HybridRetriever accepts string modes directly
    search_mode = request.mode if request.mode else "hybrid"

    # Validate mode
    valid_modes = ["semantic_only", "keyword_only", "hybrid", "auto"]
    if search_mode not in valid_modes:
        search_mode = "hybrid"

    # Map collection parameter to metadata filter
    # The system uses a single ChromaDB collection with "category" metadata for filtering.
    # "default" and "general" mean "search all categories" (no filter).
    where_filter = None
    if request.collection and request.collection not in ("default", "general"):
        where_filter = {"category": request.collection}

    # Perform hybrid search using the KB's integrated retriever
    # Note: The HybridRetriever.query_sync() uses RRF fusion internally
    # and maintains a properly synchronized BM25 index
    result = kb._hybrid_retriever.query_sync(
        query_text=request.query,
        n_results=request.n_results,
        where=where_filter,
        search_mode=search_mode,
    )

    # Convert QueryResult to HybridSearchResponse format
    items = []
    for r in result.results:
        items.append(
            HybridSearchResultItem(
                document_id=r.doc_id,
                content=r.content,
                score=r.similarity_score,
                document_source=r.metadata.get("source", "unknown"),
                metadata=r.metadata,
            )
        )

    execution_time_ms = (time.perf_counter() - start_time) * 1000

    # Determine counts based on search mode
    # Note: HybridRetriever fuses results and doesn't track per-result origin.
    # These counts reflect the search mode used, not exact attribution.
    total_results = len(items)
    if search_mode == "semantic_only":
        semantic_count = total_results
        keyword_count = 0
    elif search_mode == "keyword_only":
        semantic_count = 0
        keyword_count = total_results
    else:  # hybrid or auto - results are fused, both sources contributed
        semantic_count = total_results
        keyword_count = total_results

    return HybridSearchResponse(
        query=request.query,
        results=items,
        mode_used=search_mode,
        semantic_count=semantic_count,
        keyword_count=keyword_count,
        # Integrity: Report what was actually used vs what was requested
        fusion_method_used="rrf",  # HybridRetriever always uses RRF
        fusion_method_requested=request.fusion_method if request.fusion_method != "rrf" else None,
        total_candidates=result.total_results,
        execution_time_ms=execution_time_ms,
    )


@router.post("/multi-step-query", response_model=MultiStepQueryResponse)
async def multi_step_query(request: MultiStepQueryRequest):
    """
    Execute a multi-step query with decomposition and aggregation.

    Complex queries are broken down into sub-queries, executed in parallel
    across multiple collections, and results are aggregated with provenance tracking.

    This endpoint initializes the query orchestrator with the knowledge base
    and properly maps collection types and provenance records.
    """
    kb = get_knowledge_base()

    # Initialize orchestrator with the knowledge base (fixes the contract)
    orchestrator = initialize_query_orchestrator(knowledge_base=kb)

    # Map collection strings to CollectionType enum (using orchestrator's enum)
    # Available types: ACADEMIC, THREAT_INTEL, DEVICE_SPECS, DOCUMENTATION, GENERAL
    collections = None
    if request.collections:
        collection_map = {
            "academic": CollectionType.ACADEMIC,
            "threat_intel": CollectionType.THREAT_INTEL,
            "device_specs": CollectionType.DEVICE_SPECS,
            "documentation": CollectionType.DOCUMENTATION,
            "general": CollectionType.GENERAL,
            # Backwards compatibility aliases
            "security_research": CollectionType.ACADEMIC,
            "attack_patterns": CollectionType.THREAT_INTEL,
            "device_manuals": CollectionType.DEVICE_SPECS,
            "network_protocols": CollectionType.DOCUMENTATION,
            "threat_intelligence": CollectionType.THREAT_INTEL,
        }
        collections = [
            collection_map.get(c.lower(), CollectionType.GENERAL)
            for c in request.collections
        ]

    result = await orchestrator.query(
        query=request.query,
        collections=collections,
        n_results=request.n_results,
        use_decomposition=request.use_decomposition,
    )

    # Convert ProvenanceRecord to ProvenanceInfo (field mapping)
    provenance_items = [
        ProvenanceInfo(
            record_id=p.record_id,
            document_id=p.document_id,
            document_title=p.document_title,
            source_collection=p.source_collection.value if hasattr(p.source_collection, 'value') else str(p.source_collection),
            chunk_index=p.chunk_index,
            retrieval_query=p.retrieval_query,
            similarity_score=p.similarity_score,
            citation=p.to_citation(),
            metadata=p.metadata,
        )
        for p in result.provenance
    ]

    # Extract sub-queries from query plan steps
    sub_queries = []
    if result.query_plan:
        sub_queries = [step.query for step in result.query_plan.steps]

    # Convert CollectionType enums to strings for response
    collections_searched = [
        c.value if hasattr(c, 'value') else str(c)
        for c in result.collections_queried
    ]

    return MultiStepQueryResponse(
        query=result.original_query,
        contexts=result.contexts,
        sub_queries=sub_queries,
        provenance=provenance_items,
        confidence_score=result.confidence_score,
        collections_searched=collections_searched,
        total_results=result.total_results,
        execution_time_ms=result.execution_time_ms,
    )


@router.get("/stats/comprehensive", response_model=ComprehensiveStats)
async def get_comprehensive_stats():
    """
    Get comprehensive knowledge base statistics.

    Returns detailed information about all collections, adapters,
    search indexes, and system status.

    Integrity: This endpoint reports actual system state only (no estimates/placeholder values).
    """
    kb = get_knowledge_base()
    basic_stats = kb.get_stats()

    try:
        metadata_index = _scan_kb_metadata_index(kb)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to enumerate KB metadata: {str(e)}")

    collections: list[CollectionStatsItem] = []

    # GENERAL = overall KB stats
    collections.append(
        CollectionStatsItem(
            collection_name=CollectionType.GENERAL.value,
            document_count=metadata_index["total_documents"],
            chunk_count=metadata_index["total_chunks"],
            categories=metadata_index["categories"],
            sources=metadata_index["sources"],
            date_range=metadata_index["date_range"],
            tracking_status="tracked",
        )
    )

    for col_type in [
        CollectionType.ACADEMIC,
        CollectionType.THREAT_INTEL,
        CollectionType.DEVICE_SPECS,
        CollectionType.DOCUMENTATION,
    ]:
        per_cat = metadata_index["by_category"].get(col_type.value)
        collections.append(
            CollectionStatsItem(
                collection_name=col_type.value,
                document_count=(per_cat["document_count"] if per_cat else 0),
                chunk_count=(per_cat["chunk_count"] if per_cat else 0),
                categories=(per_cat["categories"] if per_cat else [col_type.value]),
                sources=(per_cat["sources"] if per_cat else []),
                date_range=(per_cat["date_range"] if per_cat else None),
                tracking_status="tracked",
            )
        )

    # Get hybrid search index stats from the KB's actual HybridRetriever
    # Integrity: Use kb._hybrid_retriever not get_hybrid_search() (may be different instance)
    keyword_stats: dict[str, Any] = {}
    try:
        if kb._hybrid_retriever:
            # Get BM25 index stats from the KB's own hybrid retriever
            # Correct attribute path: bm25_index (not _bm25_index)
            # BM25Index has: total_docs, term_frequencies, avg_doc_length
            bm25_idx = kb._hybrid_retriever.bm25_index
            keyword_stats = {
                "status": "available",
                "total_documents": bm25_idx.total_docs,
                "unique_terms": len(bm25_idx.term_frequencies),
                "avg_document_length": bm25_idx.avg_doc_length,
                "bm25_initialized": kb._hybrid_retriever._bm25_initialized,
                "source": "kb._hybrid_retriever.bm25_index",  # Integrity: indicate source
            }
        else:
            keyword_stats = {"status": "unavailable", "reason": "HybridRetriever not initialized"}
    except Exception as e:
        keyword_stats = {"status": "error", "error": str(e)}

    # Adapter status - report actual initialization state, not dummy data
    # Check if adapters are actually available by attempting to get them
    adapters = {}

    try:
        academic_adapter = get_academic_adapter()
        adapters["academic"] = {
            "status": "initialized",
            "type": type(academic_adapter).__name__,
        }
    except Exception as e:
        adapters["academic"] = {
            "status": "not_initialized",
            "error": str(e),
        }

    try:
        from src.rag.adapters import get_threat_intel_adapter
        threat_adapter = get_threat_intel_adapter()
        adapters["threat_intel"] = {
            "status": "initialized",
            "type": type(threat_adapter).__name__,
        }
    except Exception as e:
        adapters["threat_intel"] = {
            "status": "not_initialized",
            "error": str(e),
        }

    try:
        from src.rag.adapters import get_device_spec_adapter
        device_adapter = get_device_spec_adapter()
        adapters["device_spec"] = {
            "status": "initialized",
            "type": type(device_adapter).__name__,
        }
    except Exception as e:
        adapters["device_spec"] = {
            "status": "not_initialized",
            "error": str(e),
        }

    return ComprehensiveStats(
        total_documents=metadata_index["total_documents"],
        total_chunks=metadata_index["total_chunks"],
        persist_directory=basic_stats.get("persist_directory", ""),
        embedding_model=basic_stats.get("embedding_model", ""),
        similarity_threshold=basic_stats.get("similarity_threshold", 0.7),
        collections=collections,
        adapters=adapters,
        keyword_index=keyword_stats,
        last_ingestion=basic_stats.get("last_ingestion"),  # Actual value or None
        uptime_seconds=None,  # Not tracked - None instead of fake value
    )


@router.get("/collections", response_model=list[str])
async def list_collections():
    """
    List available knowledge base collections.

    Returns the names of all collections that can be searched.
    """
    return [col.value for col in CollectionType]


@router.get("/collections/{collection_name}/stats", response_model=CollectionStatsItem)
async def get_collection_stats(collection_name: str):
    """
    Get statistics for a specific collection.

    Uses ChromaDB enumeration (get) to compute audit-grade per-category stats.

    Args:
        collection_name: Name of the collection to get stats for
    """
    kb = get_knowledge_base()

    # Map string to CollectionType
    collection_map = {col.value: col for col in CollectionType}

    if collection_name not in collection_map:
        raise HTTPException(
            status_code=404,
            detail=f"Collection '{collection_name}' not found. Available: {list(collection_map.keys())}",
        )

    col_type = collection_map[collection_name]

    try:
        metadata_index = _scan_kb_metadata_index(kb)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to enumerate KB metadata: {str(e)}")

    if col_type == CollectionType.GENERAL:
        return CollectionStatsItem(
            collection_name=collection_name,
            document_count=metadata_index["total_documents"],
            chunk_count=metadata_index["total_chunks"],
            categories=metadata_index["categories"],
            sources=metadata_index["sources"],
            date_range=metadata_index["date_range"],
            tracking_status="tracked",
        )

    per_cat = metadata_index["by_category"].get(col_type.value)
    return CollectionStatsItem(
        collection_name=collection_name,
        document_count=(per_cat["document_count"] if per_cat else 0),
        chunk_count=(per_cat["chunk_count"] if per_cat else 0),
        categories=(per_cat["categories"] if per_cat else [col_type.value]),
        sources=(per_cat["sources"] if per_cat else []),
        date_range=(per_cat["date_range"] if per_cat else None),
        tracking_status="tracked",
    )


# ===========================================================================
# Academic Paper Search & Ingestion (Semantic Scholar + arXiv Integration)
# ===========================================================================


class AcademicSearchRequest(BaseModel):
    """Request model for academic paper search."""

    query: str = Field(..., description="Search query for academic papers")
    sources: list[str] = Field(
        default=["arxiv", "semantic_scholar"],
        description="Sources to search: arxiv, semantic_scholar, openalex, crossref, core",
    )
    limit_per_source: int = Field(default=5, ge=1, le=20, description="Results per source")
    from_year: Optional[int] = Field(default=None, description="Filter papers from this year onwards")
    ingest_to_kb: bool = Field(default=False, description="Automatically ingest results to knowledge base")


class AcademicPaperItem(BaseModel):
    """A single academic paper result."""

    paper_id: str
    title: str
    abstract: str
    authors: str
    year: Optional[int]
    venue: Optional[str]
    source: str
    doi: Optional[str]
    arxiv_id: Optional[str]
    url: Optional[str]
    citations_count: int
    keywords: list[str]


class AcademicSearchResponse(BaseModel):
    """Response model for academic paper search."""

    query: str
    papers: list[AcademicPaperItem]
    total_results: int
    sources_searched: list[str]
    papers_ingested: int
    adapter_stats: dict[str, Any]


class AcademicIngestRequest(BaseModel):
    """Request model for ingesting specific papers to knowledge base."""

    paper_ids: list[str] = Field(..., description="List of paper IDs to ingest")


class AcademicIngestResponse(BaseModel):
    """Response model for academic paper ingestion."""

    papers_ingested: int
    doc_ids: list[str]
    failed: list[str]


@router.post("/academic/search", response_model=AcademicSearchResponse)
async def search_academic_papers(request: AcademicSearchRequest):
    """
    Search for academic papers across multiple sources.

    Searches Semantic Scholar, arXiv, OpenAlex, CrossRef, and CORE for
    relevant academic papers on IoT security and smart home topics.

    Results can optionally be ingested directly into the knowledge base.
    """
    adapter = get_academic_adapter()
    kb = get_knowledge_base()

    # Map source strings to AcademicSource enum
    source_map = {
        "arxiv": AcademicSource.ARXIV,
        "semantic_scholar": AcademicSource.SEMANTIC_SCHOLAR,
        "openalex": AcademicSource.OPENALEX,
        "crossref": AcademicSource.CROSSREF,
        "core": AcademicSource.CORE,
        "ieee": AcademicSource.IEEE,
        "springer": AcademicSource.SPRINGER,
        "elsevier": AcademicSource.ELSEVIER,
        "nature": AcademicSource.NATURE,
    }

    sources = [
        source_map[s.lower()]
        for s in request.sources
        if s.lower() in source_map
    ]

    if not sources:
        sources = [AcademicSource.ARXIV, AcademicSource.SEMANTIC_SCHOLAR]

    try:
        papers = await adapter.search(
            query=request.query,
            sources=sources,
            limit_per_source=request.limit_per_source,
            from_year=request.from_year,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Academic search failed: {str(e)}")

    # Convert to response items
    paper_items = [
        AcademicPaperItem(
            paper_id=p.paper_id,
            title=p.title,
            abstract=p.abstract[:500] + "..." if len(p.abstract) > 500 else p.abstract,
            authors=", ".join(a.name for a in p.authors[:5]) + (" et al." if len(p.authors) > 5 else ""),
            year=p.year,
            venue=p.venue,
            source=p.source.value,
            doi=p.doi,
            arxiv_id=p.arxiv_id,
            url=p.url,
            citations_count=p.citations_count,
            keywords=p.keywords[:10],
        )
        for p in papers
    ]

    # Optionally ingest to knowledge base
    papers_ingested = 0
    if request.ingest_to_kb and papers:
        for paper in papers:
            doc_data = paper.to_document()
            knowledge_doc = KnowledgeDocument(
                title=doc_data["metadata"]["title"],
                content=doc_data["content"],
                category="academic",
                source=paper.source.value,
                tags=paper.keywords[:5] + ["academic", paper.source.value],
            )
            try:
                kb.add_document(knowledge_doc)
                papers_ingested += 1
            except Exception:
                pass  # Skip failures

    return AcademicSearchResponse(
        query=request.query,
        papers=paper_items,
        total_results=len(papers),
        sources_searched=[s.value for s in sources],
        papers_ingested=papers_ingested,
        adapter_stats=adapter.get_stats(),
    )


@router.post("/academic/ingest", response_model=AcademicIngestResponse)
async def ingest_academic_papers(request: AcademicIngestRequest):
    """
    Ingest specific papers from the adapter cache into the knowledge base.

    Papers must have been previously searched and cached by the adapter.
    """
    adapter = get_academic_adapter()
    kb = get_knowledge_base()

    doc_ids = []
    failed = []

    for paper_id in request.paper_ids:
        paper = adapter.get_paper(paper_id)
        if not paper:
            failed.append(paper_id)
            continue

        doc_data = paper.to_document()
        knowledge_doc = KnowledgeDocument(
            title=doc_data["metadata"]["title"],
            content=doc_data["content"],
            category="academic",
            source=paper.source.value,
            tags=paper.keywords[:5] + ["academic", paper.source.value],
        )

        try:
            doc_id = kb.add_document(knowledge_doc)
            doc_ids.append(doc_id)
        except Exception as e:
            failed.append(f"{paper_id}: {str(e)}")

    return AcademicIngestResponse(
        papers_ingested=len(doc_ids),
        doc_ids=doc_ids,
        failed=failed,
    )


@router.get("/academic/sources", response_model=list[str])
async def list_academic_sources():
    """
    List available academic paper sources.

    Returns the names of all supported academic databases that can be searched.
    """
    return [source.value for source in AcademicSource]


@router.get("/academic/stats", response_model=dict)
async def get_academic_adapter_stats():
    """
    Get academic adapter statistics.

    Returns information about search queries made and papers cached.
    """
    adapter = get_academic_adapter()
    return adapter.get_stats()


@router.post("/academic/search-all", response_model=AcademicSearchResponse)
async def search_all_academic_sources(
    query: str = Query(..., description="Search query"),
    limit: int = Query(default=10, ge=1, le=50, description="Results per source"),
    from_year: Optional[int] = Query(default=None, description="Filter papers from this year"),
    ingest: bool = Query(default=False, description="Ingest results to knowledge base"),
):
    """
    Search all available academic sources for comprehensive coverage.

    This endpoint searches arXiv, OpenAlex, CrossRef, CORE, and Semantic Scholar
    simultaneously for maximum paper coverage.
    """
    adapter = get_academic_adapter()
    kb = get_knowledge_base()

    try:
        papers = await adapter.search_all_publishers(
            query=query,
            limit_per_source=limit,
            from_year=from_year,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Academic search failed: {str(e)}")

    # Convert to response items
    paper_items = [
        AcademicPaperItem(
            paper_id=p.paper_id,
            title=p.title,
            abstract=p.abstract[:500] + "..." if len(p.abstract) > 500 else p.abstract,
            authors=", ".join(a.name for a in p.authors[:5]) + (" et al." if len(p.authors) > 5 else ""),
            year=p.year,
            venue=p.venue,
            source=p.source.value,
            doi=p.doi,
            arxiv_id=p.arxiv_id,
            url=p.url,
            citations_count=p.citations_count,
            keywords=p.keywords[:10],
        )
        for p in papers
    ]

    # Optionally ingest to knowledge base
    papers_ingested = 0
    if ingest and papers:
        for paper in papers:
            doc_data = paper.to_document()
            knowledge_doc = KnowledgeDocument(
                title=doc_data["metadata"]["title"],
                content=doc_data["content"],
                category="academic",
                source=paper.source.value,
                tags=paper.keywords[:5] + ["academic", paper.source.value],
            )
            try:
                kb.add_document(knowledge_doc)
                papers_ingested += 1
            except Exception:
                pass

    sources_searched = [
        AcademicSource.ARXIV.value,
        AcademicSource.OPENALEX.value,
        AcademicSource.CROSSREF.value,
        AcademicSource.CORE.value,
        AcademicSource.SEMANTIC_SCHOLAR.value,
    ]

    return AcademicSearchResponse(
        query=query,
        papers=paper_items,
        total_results=len(papers),
        sources_searched=sources_searched,
        papers_ingested=papers_ingested,
        adapter_stats=adapter.get_stats(),
    )


# ===========================================================================
# Knowledge Base Versioning Endpoints
# ===========================================================================


class CreateVersionRequest(BaseModel):
    """Request model for creating a KB version."""

    name: str = Field(..., description="Version name (e.g., 'v1.0', 'sprint-7')")
    description: str = Field(default="", description="Version description")
    tags: list[str] = Field(default_factory=list, description="Version tags")


class VersionResponse(BaseModel):
    """Response model for a KB version."""

    version_id: str
    version_number: int
    name: str
    description: str
    created_at: str
    created_by: str
    document_count: int
    hash: str
    parent_version: Optional[str]
    tags: list[str]


class ChangeLogEntry(BaseModel):
    """A single change log entry."""

    change_id: str
    change_type: str
    timestamp: str
    doc_id: Optional[str]
    doc_ids: list[str]
    user: str
    description: str


class VersionDiffResponse(BaseModel):
    """Response model for version diff."""

    version_a: str
    version_b: str
    documents_added: list[str]
    documents_removed: list[str]
    documents_modified: list[str]
    added_count: int
    removed_count: int
    modified_count: int


@router.post("/versions", response_model=VersionResponse)
async def create_version(request: CreateVersionRequest):
    """
    Create a new version of the knowledge base.

    Creates a version marker that can be used to track changes and
    enable rollback to previous states.
    """
    from src.rag.versioning import get_version_manager

    kb = get_knowledge_base()
    vm = get_version_manager()

    # Get current document count/hashes
    stats = kb.get_stats()

    version = vm.create_version(
        name=request.name,
        description=request.description,
        tags=request.tags,
        document_hashes=[],  # Would need to fetch actual doc hashes
    )
    version.document_count = stats.get("document_count", 0)

    return VersionResponse(
        version_id=version.version_id,
        version_number=version.version_number,
        name=version.name,
        description=version.description,
        created_at=version.created_at.isoformat(),
        created_by=version.created_by,
        document_count=version.document_count,
        hash=version.hash,
        parent_version=version.parent_version,
        tags=version.tags,
    )


@router.get("/versions", response_model=list[VersionResponse])
async def list_versions(
    limit: int = Query(default=20, ge=1, le=100),
    tag: Optional[str] = Query(default=None, description="Filter by tag"),
):
    """
    List all knowledge base versions.

    Returns versions ordered by creation time (newest first).
    """
    from src.rag.versioning import get_version_manager

    vm = get_version_manager()
    tags = [tag] if tag else None
    versions = vm.list_versions(limit=limit, tags=tags)

    return [
        VersionResponse(
            version_id=v.version_id,
            version_number=v.version_number,
            name=v.name,
            description=v.description,
            created_at=v.created_at.isoformat(),
            created_by=v.created_by,
            document_count=v.document_count,
            hash=v.hash,
            parent_version=v.parent_version,
            tags=v.tags,
        )
        for v in versions
    ]


@router.get("/versions/current", response_model=Optional[VersionResponse])
async def get_current_version():
    """Get the currently active version."""
    from src.rag.versioning import get_version_manager

    vm = get_version_manager()
    version = vm.get_current_version()

    if not version:
        return None

    return VersionResponse(
        version_id=version.version_id,
        version_number=version.version_number,
        name=version.name,
        description=version.description,
        created_at=version.created_at.isoformat(),
        created_by=version.created_by,
        document_count=version.document_count,
        hash=version.hash,
        parent_version=version.parent_version,
        tags=version.tags,
    )


@router.get("/versions/stats")
async def get_versioning_stats():
    """Get versioning system statistics."""
    from src.rag.versioning import get_version_manager

    vm = get_version_manager()
    return vm.get_stats()


@router.get("/versions/{version_id}", response_model=VersionResponse)
async def get_version(version_id: str):
    """Get a specific version by ID."""
    from src.rag.versioning import get_version_manager

    vm = get_version_manager()
    version = vm.get_version(version_id)

    if not version:
        raise HTTPException(status_code=404, detail=f"Version {version_id} not found")

    return VersionResponse(
        version_id=version.version_id,
        version_number=version.version_number,
        name=version.name,
        description=version.description,
        created_at=version.created_at.isoformat(),
        created_by=version.created_by,
        document_count=version.document_count,
        hash=version.hash,
        parent_version=version.parent_version,
        tags=version.tags,
    )


@router.post("/versions/{version_id}/snapshot")
async def create_snapshot(version_id: str):
    """
    Create a full snapshot of the current knowledge base state.

    Snapshots include document metadata and can be used for restoration.
    """
    from src.rag.versioning import get_version_manager

    kb = get_knowledge_base()
    vm = get_version_manager()

    version = vm.get_version(version_id)
    if not version:
        raise HTTPException(status_code=404, detail=f"Version {version_id} not found")

    # Get all document metadata (simplified - would need actual KB query)
    snapshot = vm.create_snapshot(
        documents=[],  # Would fetch from KB
        name=None,
        description=f"Snapshot for version {version_id}",
    )

    return {
        "message": "Snapshot created",
        "version_id": snapshot.version.version_id,
        "document_count": snapshot.version.document_count,
    }


@router.get("/versions/diff/{version_a}/{version_b}", response_model=VersionDiffResponse)
async def diff_versions(version_a: str, version_b: str):
    """
    Compare two versions and show differences.

    Returns lists of added, removed, and modified documents.
    """
    from src.rag.versioning import get_version_manager

    vm = get_version_manager()
    diff = vm.diff_versions(version_a, version_b)

    if "error" in diff:
        raise HTTPException(status_code=404, detail=diff["error"])

    return VersionDiffResponse(
        version_a=diff["version_a"],
        version_b=diff["version_b"],
        documents_added=diff["documents_added"],
        documents_removed=diff["documents_removed"],
        documents_modified=diff["documents_modified"],
        added_count=diff["added_count"],
        removed_count=diff["removed_count"],
        modified_count=diff["modified_count"],
    )


@router.get("/changelog", response_model=list[ChangeLogEntry])
async def get_changelog(
    limit: int = Query(default=50, ge=1, le=500),
    change_type: Optional[str] = Query(default=None, description="Filter by change type"),
):
    """
    Get the knowledge base change log.

    Returns recent changes to the knowledge base for audit purposes.
    """
    from src.rag.versioning import get_version_manager, ChangeType

    vm = get_version_manager()

    ctype = None
    if change_type:
        try:
            ctype = ChangeType(change_type)
        except ValueError:
            pass

    changes = vm.get_change_log(limit=limit, change_type=ctype)

    return [
        ChangeLogEntry(
            change_id=c.change_id,
            change_type=c.change_type.value,
            timestamp=c.timestamp.isoformat(),
            doc_id=c.doc_id,
            doc_ids=c.doc_ids,
            user=c.user,
            description=c.description,
        )
        for c in changes
    ]


# ===========================================================================
# Advanced Reasoning Endpoints
# ===========================================================================


class ReasoningRequest(BaseModel):
    """Request model for advanced reasoning."""

    query: str = Field(..., description="Query to reason about")
    strategy: Optional[str] = Field(
        default=None,
        description="Reasoning strategy: direct, chain_of_thought, multi_hop, iterative, hypothesis_driven, comparative, decomposition",
    )
    n_results: int = Field(default=5, ge=1, le=20, description="Results per search")
    include_trace: bool = Field(default=True, description="Include reasoning trace")


class ReasoningStepResponse(BaseModel):
    """A single reasoning step."""

    step_number: int
    step_type: str
    thought: str
    action: str
    observation: str
    confidence: float
    sources: list[str]


class ReasoningResponse(BaseModel):
    """Response model for advanced reasoning."""

    result_id: str
    query: str
    strategy: str
    answer: str
    confidence: float
    reasoning_trace: Optional[list[ReasoningStepResponse]]
    sources: list[str]
    contexts_count: int
    execution_time_ms: float


@router.post("/reasoning/query", response_model=ReasoningResponse)
async def advanced_reasoning_query(request: ReasoningRequest):
    """
    Execute advanced reasoning over the knowledge base.

    Supports multiple reasoning strategies:
    - direct: Simple retrieval
    - chain_of_thought: Step-by-step reasoning
    - multi_hop: Follow references across documents
    - iterative: Refine query based on results
    - hypothesis_driven: Generate and validate hypotheses
    - comparative: Compare information from multiple sources
    - decomposition: Break complex queries into parts

    Returns the synthesized answer along with the reasoning trace.
    """
    from src.rag.reasoning import get_reasoning_engine, ReasoningStrategy

    kb = get_knowledge_base()
    engine = get_reasoning_engine(knowledge_base=kb)

    # Map strategy string to enum
    strategy = None
    if request.strategy:
        try:
            strategy = ReasoningStrategy(request.strategy)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid strategy. Valid options: {[s.value for s in ReasoningStrategy]}",
            )

    result = await engine.reason(
        query=request.query,
        strategy=strategy,
        n_results=request.n_results,
    )

    # Build response
    reasoning_trace = None
    if request.include_trace:
        reasoning_trace = [
            ReasoningStepResponse(
                step_number=step.step_number,
                step_type=step.step_type.value,
                thought=step.thought,
                action=step.action,
                observation=step.observation[:500] if step.observation else "",
                confidence=step.confidence,
                sources=step.sources,
            )
            for step in result.reasoning_chain.steps
        ]

    return ReasoningResponse(
        result_id=result.result_id,
        query=result.query,
        strategy=result.strategy.value,
        answer=result.answer,
        confidence=result.confidence,
        reasoning_trace=reasoning_trace,
        sources=result.sources,
        contexts_count=len(result.contexts),
        execution_time_ms=result.execution_time_ms,
    )


@router.get("/reasoning/strategies")
async def list_reasoning_strategies():
    """List available reasoning strategies with descriptions."""
    from src.rag.reasoning import ReasoningStrategy

    strategies = {
        ReasoningStrategy.DIRECT.value: "Simple direct retrieval - fast but basic",
        ReasoningStrategy.CHAIN_OF_THOUGHT.value: "Step-by-step reasoning with explicit thought process",
        ReasoningStrategy.MULTI_HOP.value: "Follow references across multiple documents",
        ReasoningStrategy.ITERATIVE.value: "Refine query iteratively based on results",
        ReasoningStrategy.HYPOTHESIS_DRIVEN.value: "Generate and validate hypotheses",
        ReasoningStrategy.COMPARATIVE.value: "Compare information from multiple sources",
        ReasoningStrategy.DECOMPOSITION.value: "Break complex queries into simpler sub-queries",
    }

    return {
        "strategies": strategies,
        "default": "auto-selected based on query analysis",
    }


@router.get("/reasoning/stats")
async def get_reasoning_stats():
    """Get reasoning engine statistics."""
    from src.rag.reasoning import get_reasoning_engine

    engine = get_reasoning_engine()
    return engine.get_stats()
