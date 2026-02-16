"""
ChromaDB Vector Store Client

Provides vector storage and retrieval for RAG operations.
Designed for research integrity with full provenance tracking.

NOTE: After migration to GTE embeddings, this module uses the custom
EmbeddingService for all query operations to ensure dimension compatibility.
"""

import shutil
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Optional, TYPE_CHECKING
from uuid import uuid4

import chromadb
from chromadb import Settings as ChromaSettings
from loguru import logger

from src.core.config import settings

if TYPE_CHECKING:
    from src.rag.embeddings.embedding_service import EmbeddingService


def _check_chromadb_health(persist_directory: Path) -> dict:
    """
    Non-destructive ChromaDB health check.

    IMPORTANT: This function NEVER deletes data. It only reports status.
    Any migration or repair must be done manually with explicit user consent.

    Args:
        persist_directory: Path to ChromaDB persist directory

    Returns:
        dict with health status information
    """
    sqlite_file = persist_directory / "chroma.sqlite3"

    status = {
        "exists": sqlite_file.exists(),
        "embedding_count": 0,
        "collection_name": None,
        "healthy": False,
        "error": None,
    }

    if not sqlite_file.exists():
        status["healthy"] = True  # No database yet is OK
        return status

    try:
        import sqlite3
        conn = sqlite3.connect(str(sqlite_file))
        cursor = conn.cursor()

        # Get embedding count
        cursor.execute("SELECT COUNT(*) FROM embeddings")
        status["embedding_count"] = cursor.fetchone()[0]

        # Get collection name
        cursor.execute("SELECT name FROM collections LIMIT 1")
        row = cursor.fetchone()
        if row:
            status["collection_name"] = row[0]

        conn.close()
        status["healthy"] = True

        if status["embedding_count"] > 0:
            logger.info(
                f"ChromaDB health check: {status['embedding_count']} embeddings "
                f"in collection '{status['collection_name']}'"
            )
        else:
            logger.info("ChromaDB health check: database exists but is empty")

    except Exception as e:
        status["error"] = str(e)
        logger.warning(f"ChromaDB health check failed: {e}")

    return status


def _migrate_chromadb_if_needed(persist_directory: Path) -> bool:
    """
    DEPRECATED: This function previously performed destructive migrations.

    The original implementation incorrectly detected valid databases as
    "old format" based on missing '_type' field and deleted them,
    causing repeated data loss (13+ documented incidents).

    This function is now a NO-OP that only performs health checks.
    Any actual migration must be done manually with explicit user consent.

    See: evaluation/docs/utils/REPORT_CHROME_DB_ISSUES.md

    Args:
        persist_directory: Path to ChromaDB persist directory

    Returns:
        False (migration is never performed automatically)
    """
    # Perform non-destructive health check only
    status = _check_chromadb_health(persist_directory)

    if status["error"]:
        logger.warning(
            f"ChromaDB may need manual attention: {status['error']}. "
            "Data will NOT be automatically deleted. Please review manually."
        )

    # NEVER automatically delete data
    return False


@dataclass
class Document:
    """A document with metadata for RAG storage."""

    content: str
    metadata: dict = field(default_factory=dict)
    doc_id: Optional[str] = None

    def __post_init__(self):
        if self.doc_id is None:
            self.doc_id = str(uuid4())


class ScoreType(str, Enum):
    """Type of score in RetrievalResult - determines how to interpret the value."""
    SIMILARITY = "similarity"  # 0-1 range, higher = more similar (semantic search)
    BM25 = "bm25"              # Unbounded TF-IDF score (keyword search)
    RRF = "rrf"                # Reciprocal Rank Fusion score, typically 0.01-0.03 (hybrid)
    UNKNOWN = "unknown"        # Score type not specified


@dataclass
class RetrievalResult:
    """Result from a vector similarity search."""

    doc_id: str
    content: str
    metadata: dict
    similarity_score: float
    source: Optional[str] = None
    score_type: ScoreType = ScoreType.SIMILARITY  # Default for backwards compatibility

    @property
    def is_above_threshold(self) -> bool:
        """
        Check if result meets similarity threshold.

        Note: This property only makes sense for SIMILARITY score types.
        For RRF/BM25 scores, ranking position is more meaningful than threshold.
        """
        if self.score_type == ScoreType.SIMILARITY:
            return self.similarity_score >= settings.rag_similarity_threshold
        # For non-similarity scores, ranking already ensures quality
        return True

    @property
    def normalized_confidence(self) -> float:
        """
        Get a 0-1 normalized confidence value regardless of score type.

        This allows consistent confidence calculations across different
        retrieval modes (semantic, keyword, hybrid).
        """
        if self.score_type == ScoreType.SIMILARITY:
            # Already 0-1, just clamp
            return max(0.0, min(1.0, self.similarity_score))
        elif self.score_type == ScoreType.RRF:
            # RRF scores are typically 0.01-0.03 for good results
            # Normalize: 0.02 -> 0.8 (good), 0.01 -> 0.4 (moderate), 0.005 -> 0.2 (low)
            # Using sigmoid-like scaling: score * 40 clamped to 0-1
            return max(0.0, min(1.0, self.similarity_score * 40))
        elif self.score_type == ScoreType.BM25:
            # BM25 scores vary widely; use sigmoid normalization
            # Typical good BM25 scores are 5-20+
            import math
            return 1.0 / (1.0 + math.exp(-0.2 * (self.similarity_score - 10)))
        else:
            # Unknown score type - return raw score clamped
            return max(0.0, min(1.0, self.similarity_score))


@dataclass
class QueryResult:
    """Complete result from a RAG query."""

    query: str
    results: list[RetrievalResult]
    total_results: int
    query_time_ms: float
    timestamp: datetime = field(default_factory=datetime.utcnow)

    @property
    def has_results(self) -> bool:
        return len(self.results) > 0

    @property
    def best_result(self) -> Optional[RetrievalResult]:
        return self.results[0] if self.results else None


class ChromaVectorStore:
    """
    ChromaDB vector store for RAG retrieval.

    Features:
    - Persistent storage with automatic embedding
    - Research integrity: Full provenance tracking
    - Similarity threshold filtering
    - Batch operations support
    - Custom embedding service support for GTE/other models
    """

    def __init__(
        self,
        persist_directory: Optional[str] = None,
        collection_name: Optional[str] = None,
        embedding_service: Optional["EmbeddingService"] = None,
    ):
        self.persist_directory = Path(
            persist_directory or settings.chroma_persist_directory
        )
        self.collection_name = collection_name or settings.chroma_collection_name

        # Embedding service for custom embeddings (required for GTE)
        self._embedding_service = embedding_service

        # Ensure persist directory exists
        self.persist_directory.mkdir(parents=True, exist_ok=True)

        # DISABLED: Migration was destroying data due to false positive detection
        # The '_type' field check incorrectly triggered on valid databases
        # causing repeated data loss (13+ incidents documented).
        # See: evaluation/docs/utils/REPORT_CHROME_DB_ISSUES.md
        # Original: _migrate_chromadb_if_needed(self.persist_directory)
        logger.info("ChromaDB migration check disabled - preserving existing data")

        # Initialize ChromaDB client
        self._client: Optional[chromadb.PersistentClient] = None
        self._collection: Optional[chromadb.Collection] = None

        logger.info(
            f"ChromaDB initialized: {self.persist_directory}/{self.collection_name}"
        )

    @property
    def embedding_service(self) -> "EmbeddingService":
        """Lazy-load the embedding service."""
        if self._embedding_service is None:
            from src.rag.embeddings.embedding_service import get_embedding_service
            self._embedding_service = get_embedding_service()
        return self._embedding_service

    @property
    def client(self) -> chromadb.PersistentClient:
        """Lazy-load ChromaDB client."""
        if self._client is None:
            self._client = chromadb.PersistentClient(
                path=str(self.persist_directory),
                settings=ChromaSettings(
                    anonymized_telemetry=False,
                    allow_reset=True,
                ),
            )
        return self._client

    @property
    def collection(self) -> chromadb.Collection:
        """Get or create the collection."""
        if self._collection is None:
            # Get embedding dimension from the embedding service
            # This ensures the stored dimension matches the actual model output
            embedding_dim = self.embedding_service.embedding_dimension

            self._collection = self.client.get_or_create_collection(
                name=self.collection_name,
                metadata={
                    "description": "Smart-HES Agent Knowledge Base",
                    "created_at": datetime.utcnow().isoformat(),
                    "embedding_model": settings.embedding_model,
                    "embedding_dimension": embedding_dim,
                },
            )

            # Verify existing collection has matching dimension (integrity check)
            existing_meta = self._collection.metadata or {}
            stored_dim = existing_meta.get("embedding_dimension")
            if stored_dim is not None and stored_dim != embedding_dim:
                logger.error(
                    f"EMBEDDING DIMENSION MISMATCH: Collection has {stored_dim}D, "
                    f"but current model produces {embedding_dim}D. "
                    f"This will cause query failures. Migration required."
                )
            elif stored_dim is None and self._collection.count() > 0:
                # Existing collection without dimension metadata - log warning
                logger.warning(
                    f"Collection '{self.collection_name}' has {self._collection.count()} "
                    f"documents but no stored embedding_dimension. "
                    f"Current model uses {embedding_dim}D."
                )

        return self._collection

    def add_document(self, document: Document) -> str:
        """
        Add a single document to the vector store.

        Uses custom embedding service to ensure GTE compatibility.

        Args:
            document: Document to add

        Returns:
            Document ID
        """
        # Enrich metadata with provenance
        metadata = {
            **document.metadata,
            "ingested_at": datetime.utcnow().isoformat(),
            "content_length": len(document.content),
        }

        # Generate embedding using custom embedding service
        embedding = self.embedding_service.embed_text(document.content)

        self.collection.add(
            ids=[document.doc_id],
            documents=[document.content],
            embeddings=[embedding.tolist()],
            metadatas=[metadata],
        )

        logger.debug(f"Added document: {document.doc_id[:8]}...")
        return document.doc_id

    def add_documents(self, documents: list[Document]) -> list[str]:
        """
        Add multiple documents to the vector store.

        Uses custom embedding service to ensure GTE compatibility.

        Args:
            documents: List of documents to add

        Returns:
            List of document IDs
        """
        if not documents:
            return []

        ids = []
        contents = []
        metadatas = []

        for doc in documents:
            ids.append(doc.doc_id)
            contents.append(doc.content)
            metadatas.append(
                {
                    **doc.metadata,
                    "ingested_at": datetime.utcnow().isoformat(),
                    "content_length": len(doc.content),
                }
            )

        # Generate embeddings using custom embedding service (batch)
        embeddings = self.embedding_service.embed_texts(contents)

        self.collection.add(
            ids=ids,
            documents=contents,
            embeddings=embeddings.tolist(),
            metadatas=metadatas,
        )

        logger.info(f"Added {len(documents)} documents to vector store")
        return ids

    def query(
        self,
        query_text: str,
        n_results: Optional[int] = None,
        where: Optional[dict] = None,
        include_below_threshold: bool = False,
    ) -> QueryResult:
        """
        Query the vector store for similar documents.

        Uses the custom embedding service to generate query embeddings,
        ensuring compatibility with GTE and other models that differ
        from ChromaDB's default embedding function.

        Args:
            query_text: The query string
            n_results: Number of results to return (default: settings.rag_top_k)
            where: Optional metadata filter
            include_below_threshold: Include results below similarity threshold

        Returns:
            QueryResult with matching documents
        """
        import time

        start_time = time.perf_counter()

        n_results = n_results or settings.rag_top_k

        # Generate query embedding using custom embedding service
        # This ensures dimension compatibility with GTE (1024D) or other models
        query_embedding = self.embedding_service.embed_text(query_text)

        # Perform the query using pre-computed embedding
        results = self.collection.query(
            query_embeddings=[query_embedding.tolist()],
            n_results=n_results,
            where=where,
            include=["documents", "metadatas", "distances"],
        )

        # Convert distances to similarity scores (ChromaDB returns L2 distances)
        # Similarity = 1 / (1 + distance) for L2
        retrieval_results = []

        if results["ids"] and results["ids"][0]:
            for i, doc_id in enumerate(results["ids"][0]):
                distance = results["distances"][0][i] if results["distances"] else 0
                similarity = 1 / (1 + distance)

                result = RetrievalResult(
                    doc_id=doc_id,
                    content=results["documents"][0][i],
                    metadata=results["metadatas"][0][i] if results["metadatas"] else {},
                    similarity_score=similarity,
                    source=results["metadatas"][0][i].get("source")
                    if results["metadatas"]
                    else None,
                )

                # Filter by threshold unless explicitly included
                if include_below_threshold or result.is_above_threshold:
                    retrieval_results.append(result)

        query_time_ms = (time.perf_counter() - start_time) * 1000

        logger.debug(
            f"Query completed: {len(retrieval_results)} results in {query_time_ms:.2f}ms"
        )

        return QueryResult(
            query=query_text,
            results=retrieval_results,
            total_results=len(retrieval_results),
            query_time_ms=query_time_ms,
        )

    def delete_document(self, doc_id: str) -> bool:
        """Delete a document by ID."""
        try:
            self.collection.delete(ids=[doc_id])
            logger.debug(f"Deleted document: {doc_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete document {doc_id}: {e}")
            return False

    def delete_documents(self, doc_ids: list[str]) -> int:
        """Delete multiple documents by ID."""
        try:
            self.collection.delete(ids=doc_ids)
            logger.info(f"Deleted {len(doc_ids)} documents")
            return len(doc_ids)
        except Exception as e:
            logger.error(f"Failed to delete documents: {e}")
            return 0

    def get_document(self, doc_id: str) -> Optional[Document]:
        """Get a document by ID."""
        result = self.collection.get(ids=[doc_id], include=["documents", "metadatas"])

        if result["ids"]:
            return Document(
                doc_id=result["ids"][0],
                content=result["documents"][0],
                metadata=result["metadatas"][0] if result["metadatas"] else {},
            )
        return None

    def count(self) -> int:
        """Get the total number of documents in the collection."""
        return self.collection.count()

    def count_by_metadata(
        self,
        where: dict[str, Any],
        include_sources: bool = False,
    ) -> dict[str, Any]:
        """
        Count documents matching a metadata filter using proper enumeration.

        Uses ChromaDB's get() method (enumeration) instead of query() (similarity search)
        to get accurate document counts by category or other metadata fields.

        Args:
            where: Metadata filter dict (e.g., {"category": "academic"})
            include_sources: If True, collect unique source values

        Returns:
            Dict with document_count and optionally sources list
        """
        try:
            # Use get() with where filter - this is enumeration, not similarity search
            # ChromaDB get() can handle where filters without requiring embeddings
            result = self.collection.get(
                where=where,
                include=["metadatas"] if include_sources else [],
            )

            doc_count = len(result["ids"]) if result["ids"] else 0

            stats: dict[str, Any] = {
                "document_count": doc_count,
            }

            # Optionally collect unique sources
            if include_sources and result.get("metadatas"):
                sources = set()
                for meta in result["metadatas"]:
                    if meta and "source" in meta:
                        sources.add(meta["source"])
                stats["sources"] = list(sources)

            return stats

        except Exception as e:
            logger.error(f"Failed to count documents with filter {where}: {e}")
            return {"document_count": 0, "error": str(e)}

    def reset(self) -> bool:
        """
        Reset the collection (delete all documents).

        WARNING: This is destructive and cannot be undone!
        """
        try:
            self.client.delete_collection(self.collection_name)
            self._collection = None
            logger.warning(f"Collection '{self.collection_name}' has been reset")
            return True
        except Exception as e:
            logger.error(f"Failed to reset collection: {e}")
            return False

    def get_stats(self) -> dict:
        """Get collection statistics."""
        return {
            "collection_name": self.collection_name,
            "document_count": self.count(),
            "persist_directory": str(self.persist_directory),
            "embedding_model": settings.embedding_model,
            "similarity_threshold": settings.rag_similarity_threshold,
        }


# Global instance management
_vector_store: Optional[ChromaVectorStore] = None


def get_vector_store() -> ChromaVectorStore:
    """Get or create the global vector store instance."""
    global _vector_store
    if _vector_store is None:
        _vector_store = ChromaVectorStore()
    return _vector_store
