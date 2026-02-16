"""
Hybrid Retriever

Combines semantic (dense) search with BM25 (sparse) keyword search
for improved retrieval quality.

Features:
- Configurable search modes: semantic_only, keyword_only, hybrid, auto
- Multiple fusion methods: RRF, weighted sum, max score, interleave
- Automatic BM25 index synchronization with ChromaDB
- Research integrity: Full provenance tracking
"""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional

from loguru import logger

from src.core.config import settings
from src.rag.vector_store_module import ChromaVectorStore, get_vector_store
from src.rag.vector_store_module.vector_store import QueryResult, RetrievalResult, ScoreType
from src.rag.query.hybrid_search import (
    BM25Index,
    HybridSearch,
    SearchMode,
    FusionMethod,
    SearchResult,
    HybridSearchResult,
)


@dataclass
class HybridQueryResult:
    """Result from hybrid retrieval combining semantic and keyword search."""

    query: str
    results: list[RetrievalResult]
    total_results: int
    query_time_ms: float
    search_mode: str
    fusion_method: str
    semantic_count: int
    keyword_count: int
    timestamp: datetime = field(default_factory=datetime.utcnow)

    @property
    def has_results(self) -> bool:
        return len(self.results) > 0

    @property
    def best_result(self) -> Optional[RetrievalResult]:
        return self.results[0] if self.results else None


class HybridRetriever:
    """
    Hybrid Retriever combining semantic and keyword search.

    This class provides:
    - Semantic search via ChromaDB vector store (GTE embeddings)
    - Keyword search via BM25 index
    - Multiple fusion strategies (RRF, weighted, max, interleave)
    - Automatic mode selection based on query characteristics

    Configuration (via settings):
    - search_mode: "semantic_only", "keyword_only", "hybrid", "auto"
    - hybrid_semantic_weight: Weight for semantic results (0-1)
    - hybrid_keyword_weight: Weight for keyword results (0-1)
    - hybrid_fusion_method: "rrf", "weighted", "max", "interleave"
    """

    def __init__(
        self,
        vector_store: Optional[ChromaVectorStore] = None,
        search_mode: Optional[str] = None,
        semantic_weight: Optional[float] = None,
        keyword_weight: Optional[float] = None,
        fusion_method: Optional[str] = None,
    ):
        """
        Initialize hybrid retriever.

        Args:
            vector_store: ChromaDB vector store (uses global if None)
            search_mode: Override default search mode from settings
            semantic_weight: Override semantic weight from settings
            keyword_weight: Override keyword weight from settings
            fusion_method: Override fusion method from settings
        """
        self.vector_store = vector_store or get_vector_store()

        # Configuration
        self.search_mode = search_mode or settings.search_mode
        self.semantic_weight = semantic_weight or settings.hybrid_semantic_weight
        self.keyword_weight = keyword_weight or settings.hybrid_keyword_weight
        self.fusion_method = fusion_method or settings.hybrid_fusion_method

        # Initialize BM25 index
        self.bm25_index = BM25Index()
        self._bm25_initialized = False

        # Initialize HybridSearch
        self.hybrid_search = HybridSearch(
            semantic_search_fn=self._semantic_search_async,
            semantic_weight=self.semantic_weight,
            keyword_weight=self.keyword_weight,
        )

        logger.info(
            f"HybridRetriever initialized: "
            f"mode={self.search_mode}, "
            f"semantic_weight={self.semantic_weight}, "
            f"keyword_weight={self.keyword_weight}, "
            f"fusion={self.fusion_method}"
        )

    def _map_search_mode(self, mode: str) -> SearchMode:
        """Map string mode to SearchMode enum."""
        mode_map = {
            "semantic_only": SearchMode.SEMANTIC_ONLY,
            "keyword_only": SearchMode.KEYWORD_ONLY,
            "hybrid": SearchMode.HYBRID,
            "auto": SearchMode.AUTO,
        }
        return mode_map.get(mode, SearchMode.HYBRID)

    def _map_fusion_method(self, method: str) -> FusionMethod:
        """Map string method to FusionMethod enum."""
        method_map = {
            "rrf": FusionMethod.RRF,
            "weighted": FusionMethod.WEIGHTED_SUM,
            "max": FusionMethod.MAX_SCORE,
            "interleave": FusionMethod.INTERLEAVE,
        }
        return method_map.get(method, FusionMethod.RRF)

    async def _semantic_search_async(
        self,
        query: str,
        collection: str = "default",
        n_results: int = 10,
        **kwargs,
    ) -> dict[str, Any]:
        """
        Async semantic search wrapper for HybridSearch.

        Returns results in ChromaDB format expected by HybridSearch.
        """
        # Use vector store query (which uses ChromaDB's built-in embedding)
        result = self.vector_store.query(
            query_text=query,
            n_results=n_results,
            include_below_threshold=True,  # Let hybrid search handle scoring
        )

        # Convert to ChromaDB-style dict format
        return {
            "ids": [[r.doc_id for r in result.results]],
            "documents": [[r.content for r in result.results]],
            "metadatas": [[r.metadata for r in result.results]],
            "distances": [[1 - r.similarity_score for r in result.results]],  # Convert similarity to distance
        }

    def _sync_bm25_index(self) -> int:
        """
        Synchronize BM25 index with ChromaDB documents.

        Returns:
            Number of documents indexed
        """
        if self._bm25_initialized:
            return self.bm25_index.total_docs

        logger.info("Synchronizing BM25 index with ChromaDB...")

        # Clear existing index
        self.bm25_index.clear()

        # Get all documents from ChromaDB
        try:
            collection = self.vector_store.collection
            doc_count = collection.count()

            if doc_count == 0:
                logger.info("No documents in ChromaDB to index")
                self._bm25_initialized = True
                return 0

            # Fetch all documents in batches
            batch_size = 1000
            total_indexed = 0

            for offset in range(0, doc_count, batch_size):
                result = collection.get(
                    limit=batch_size,
                    offset=offset,
                    include=["documents", "metadatas"],
                )

                for i, doc_id in enumerate(result["ids"]):
                    content = result["documents"][i] if result["documents"] else ""
                    metadata = result["metadatas"][i] if result["metadatas"] else {}

                    if content:
                        self.bm25_index.add_document(doc_id, content, metadata)
                        total_indexed += 1

            self._bm25_initialized = True
            logger.info(f"BM25 index synchronized: {total_indexed} documents indexed")
            return total_indexed

        except Exception as e:
            logger.error(f"Failed to sync BM25 index: {e}")
            self._bm25_initialized = True  # Avoid repeated failures
            return 0

    def index_document(
        self,
        doc_id: str,
        content: str,
        metadata: Optional[dict] = None,
    ) -> None:
        """
        Add a single document to BM25 index.

        Call this when adding new documents to ChromaDB.
        """
        if content:
            self.bm25_index.add_document(doc_id, content, metadata or {})

    def index_documents(self, documents: list[dict]) -> int:
        """
        Add multiple documents to BM25 index.

        Args:
            documents: List of dicts with 'id', 'content', and optional 'metadata'

        Returns:
            Number of documents indexed
        """
        count = 0
        for doc in documents:
            doc_id = doc.get("id", str(count))
            content = doc.get("content", "")
            metadata = doc.get("metadata", {})

            if content:
                self.bm25_index.add_document(doc_id, content, metadata)
                count += 1

        return count

    def query(
        self,
        query_text: str,
        n_results: Optional[int] = None,
        where: Optional[dict] = None,
        include_below_threshold: bool = False,
        search_mode: Optional[str] = None,
        fusion_method: Optional[str] = None,
    ) -> HybridQueryResult:
        """
        Query using hybrid retrieval.

        Args:
            query_text: The search query
            n_results: Number of results to return
            where: Optional metadata filter (applies to both semantic and BM25 search)
            include_below_threshold: Include results below similarity threshold
            search_mode: Override configured search mode
            fusion_method: Override configured fusion method

        Returns:
            HybridQueryResult with combined results
        """
        # Ensure BM25 index is synchronized
        if not self._bm25_initialized:
            self._sync_bm25_index()

        # Determine search parameters
        n_results = n_results or settings.rag_top_k
        mode = self._map_search_mode(search_mode or self.search_mode)
        fusion = self._map_fusion_method(fusion_method or self.fusion_method)

        # Run hybrid search (async wrapped in sync)
        hybrid_result = asyncio.get_event_loop().run_until_complete(
            self.hybrid_search.search(
                query=query_text,
                collection="default",
                top_k=n_results,
                mode=mode,
                fusion_method=fusion,
            )
        )

        # Convert to RetrievalResult format
        retrieval_results = []
        for sr in hybrid_result.results:
            similarity_score = sr.score

            result = RetrievalResult(
                doc_id=sr.document_id,
                content=sr.content,
                metadata=sr.metadata,
                similarity_score=similarity_score,
                source=sr.metadata.get("source"),
            )

            # Filter by threshold
            if include_below_threshold or result.is_above_threshold:
                retrieval_results.append(result)

        return HybridQueryResult(
            query=query_text,
            results=retrieval_results,
            total_results=len(retrieval_results),
            query_time_ms=hybrid_result.execution_time_ms,
            search_mode=hybrid_result.mode_used.value,
            fusion_method=hybrid_result.fusion_method.value,
            semantic_count=hybrid_result.semantic_count,
            keyword_count=hybrid_result.keyword_count,
        )

    def query_sync(
        self,
        query_text: str,
        n_results: Optional[int] = None,
        where: Optional[dict] = None,
        include_below_threshold: bool = False,
        search_mode: Optional[str] = None,
        fusion_method: Optional[str] = None,
    ) -> QueryResult:
        """
        Synchronous query returning standard QueryResult format.

        This is compatible with existing knowledge base interface.
        """
        # Ensure BM25 index is synchronized
        if not self._bm25_initialized:
            self._sync_bm25_index()

        import time
        start_time = time.perf_counter()

        # Determine search parameters
        n_results = n_results or settings.rag_top_k
        mode = self._map_search_mode(search_mode or self.search_mode)
        fusion = self._map_fusion_method(fusion_method or self.fusion_method)

        # For semantic_only mode, use vector store directly
        if mode == SearchMode.SEMANTIC_ONLY:
            return self.vector_store.query(
                query_text=query_text,
                n_results=n_results,
                where=where,
                include_below_threshold=include_below_threshold,
            )

        # For keyword_only mode, use BM25 directly
        if mode == SearchMode.KEYWORD_ONLY:
            bm25_results = self.bm25_index.search(query_text, top_k=n_results, where=where)

            # NOTE: BM25 scores are NOT similarity scores (0-1 range).
            # BM25 produces raw TF-IDF based scores. Don't apply similarity
            # threshold - the ranking already ensures quality.
            retrieval_results = []
            for sr in bm25_results:
                result = RetrievalResult(
                    doc_id=sr.document_id,
                    content=sr.content,
                    metadata=sr.metadata,
                    similarity_score=sr.score,  # BM25 score, not similarity
                    source=sr.metadata.get("source"),
                    score_type=ScoreType.BM25,  # Mark as BM25 for proper confidence calculation
                )
                retrieval_results.append(result)

            query_time_ms = (time.perf_counter() - start_time) * 1000

            return QueryResult(
                query=query_text,
                results=retrieval_results,
                total_results=len(retrieval_results),
                query_time_ms=query_time_ms,
            )

        # For hybrid/auto modes, perform both searches and fuse
        # Semantic search
        semantic_result = self.vector_store.query(
            query_text=query_text,
            n_results=n_results * 2,  # Fetch more for fusion
            where=where,
            include_below_threshold=True,
        )

        # BM25 search (apply same metadata filter as semantic search)
        bm25_results = self.bm25_index.search(query_text, top_k=n_results * 2, where=where)

        # Fuse results using RRF
        rrf_scores: dict[str, float] = {}
        doc_map: dict[str, RetrievalResult] = {}

        # Score semantic results
        for rank, result in enumerate(semantic_result.results, 1):
            rrf_scores[result.doc_id] = self.semantic_weight / (60 + rank)
            doc_map[result.doc_id] = result

        # Score keyword results
        for rank, sr in enumerate(bm25_results, 1):
            doc_id = sr.document_id
            rrf_scores[doc_id] = rrf_scores.get(doc_id, 0) + self.keyword_weight / (60 + rank)
            if doc_id not in doc_map:
                doc_map[doc_id] = RetrievalResult(
                    doc_id=doc_id,
                    content=sr.content,
                    metadata=sr.metadata,
                    similarity_score=sr.score,
                    source=sr.metadata.get("source"),
                )

        # Sort by RRF score
        sorted_ids = sorted(rrf_scores.keys(), key=lambda x: rrf_scores[x], reverse=True)

        # Build final results
        # NOTE: RRF scores are NOT comparable to similarity scores (0-1 range).
        # RRF scores are typically in 0.01-0.03 range. Don't apply similarity
        # threshold to RRF scores - the ranking already ensures quality.
        retrieval_results = []
        for doc_id in sorted_ids[:n_results]:
            result = doc_map[doc_id]
            # Update score to RRF score and mark score type
            result.similarity_score = rrf_scores[doc_id]
            result.score_type = ScoreType.RRF  # Mark as RRF for proper confidence calculation
            retrieval_results.append(result)

        query_time_ms = (time.perf_counter() - start_time) * 1000

        logger.debug(
            f"Hybrid query completed: {len(retrieval_results)} results in {query_time_ms:.2f}ms "
            f"(semantic={len(semantic_result.results)}, keyword={len(bm25_results)})"
        )

        return QueryResult(
            query=query_text,
            results=retrieval_results,
            total_results=len(retrieval_results),
            query_time_ms=query_time_ms,
        )

    def get_stats(self) -> dict[str, Any]:
        """Get hybrid retriever statistics."""
        vector_stats = self.vector_store.get_stats()

        return {
            **vector_stats,
            "search_mode": self.search_mode,
            "semantic_weight": self.semantic_weight,
            "keyword_weight": self.keyword_weight,
            "fusion_method": self.fusion_method,
            "bm25_initialized": self._bm25_initialized,
            "bm25_document_count": self.bm25_index.total_docs,
            "bm25_unique_terms": len(self.bm25_index.term_frequencies),
        }

    def reset_bm25_index(self) -> None:
        """Reset BM25 index (will be re-synced on next query)."""
        self.bm25_index.clear()
        self._bm25_initialized = False
        logger.info("BM25 index reset")


# Global instance management
_hybrid_retriever: Optional[HybridRetriever] = None


def get_hybrid_retriever() -> HybridRetriever:
    """Get or create the global hybrid retriever instance."""
    global _hybrid_retriever
    if _hybrid_retriever is None:
        _hybrid_retriever = HybridRetriever()
    return _hybrid_retriever


def reset_hybrid_retriever() -> None:
    """Reset the global hybrid retriever instance."""
    global _hybrid_retriever
    _hybrid_retriever = None
