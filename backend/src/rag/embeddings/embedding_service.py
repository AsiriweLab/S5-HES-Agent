"""
Embedding Service

Provides text embedding using sentence-transformers.
Supports batching and caching for performance.

Features:
- Local model storage within project directory
- Dimension validation to prevent ChromaDB mismatches
- Lazy loading for memory efficiency
"""

from pathlib import Path
from typing import Optional, Dict, Any

import numpy as np
from loguru import logger
from sentence_transformers import SentenceTransformer

from src.core.config import settings


# Known model dimensions for validation
MODEL_DIMENSIONS: Dict[str, int] = {
    "all-MiniLM-L6-v2": 384,
    "gte-large": 1024,
    "e5-large": 1024,
    "bge-large": 1024,
}


class EmbeddingDimensionMismatchError(Exception):
    """Raised when embedding dimensions don't match existing database."""
    pass


class EmbeddingService:
    """
    Embedding service using sentence-transformers.

    Features:
    - Lazy model loading
    - Batch embedding support
    - Configurable model selection
    - Shared model path support (for multi-project setups)
    """

    def __init__(self, model_name: Optional[str] = None):
        self.model_name = model_name or settings.embedding_model
        self._model: Optional[SentenceTransformer] = None
        self._model_path = self._resolve_model_path()
        logger.info(f"EmbeddingService configured with model: {self._model_path}")

    def _resolve_model_path(self) -> str:
        """
        Resolve the model path, preferring shared local models over HuggingFace cache.

        Returns:
            Path to model (local path if exists, otherwise model name for download)
        """
        # Check if shared models path is configured and model exists there
        shared_path = settings.shared_models_path / "embeddings" / self.model_name
        if shared_path.exists():
            logger.info(f"Using shared model from: {shared_path}")
            return str(shared_path)

        # Fall back to model name (will use HuggingFace cache or download)
        logger.info(f"Using model from HuggingFace cache: {self.model_name}")
        return self.model_name

    @property
    def model(self) -> SentenceTransformer:
        """Lazy-load the embedding model."""
        if self._model is None:
            logger.info(f"Loading embedding model: {self._model_path}")
            self._model = SentenceTransformer(self._model_path)
            logger.info(
                f"Embedding model loaded. Dimension: {self._model.get_sentence_embedding_dimension()}"
            )
        return self._model

    @property
    def embedding_dimension(self) -> int:
        """Get the embedding dimension."""
        return self.model.get_sentence_embedding_dimension()

    def embed_text(self, text: str) -> np.ndarray:
        """
        Embed a single text string.

        Args:
            text: Text to embed

        Returns:
            Embedding vector as numpy array
        """
        return self.model.encode(text, convert_to_numpy=True)

    def embed_texts(self, texts: list[str], batch_size: int = 32) -> np.ndarray:
        """
        Embed multiple texts in batches.

        Args:
            texts: List of texts to embed
            batch_size: Batch size for encoding

        Returns:
            Array of embedding vectors (n_texts x dimension)
        """
        if not texts:
            return np.array([])

        embeddings = self.model.encode(
            texts,
            batch_size=batch_size,
            convert_to_numpy=True,
            show_progress_bar=len(texts) > 100,
        )

        logger.debug(f"Embedded {len(texts)} texts")
        return embeddings

    def similarity(self, text1: str, text2: str) -> float:
        """
        Calculate cosine similarity between two texts.

        Args:
            text1: First text
            text2: Second text

        Returns:
            Cosine similarity score (0-1)
        """
        emb1 = self.embed_text(text1)
        emb2 = self.embed_text(text2)

        # Cosine similarity
        similarity = np.dot(emb1, emb2) / (np.linalg.norm(emb1) * np.linalg.norm(emb2))
        return float(similarity)

    def get_info(self) -> dict:
        """Get embedding service information."""
        return {
            "model_name": self.model_name,
            "model_path": self._model_path,
            "embedding_dimension": self.embedding_dimension,
            "model_loaded": self._model is not None,
            "using_shared_models": str(settings.shared_models_path) in self._model_path,
        }

    def validate_chromadb_compatibility(self, chroma_path: Optional[Path] = None) -> Dict[str, Any]:
        """
        Validate that current model is compatible with existing ChromaDB data.

        This prevents dimension mismatch errors when the database contains
        embeddings from a different model.

        Args:
            chroma_path: Path to ChromaDB directory (uses config default if None)

        Returns:
            Dict with validation results:
                - compatible: True if compatible or empty database
                - current_dimension: Current model's embedding dimension
                - stored_dimension: Stored dimension in database (if any)
                - document_count: Number of documents in database
                - message: Human-readable status message

        Raises:
            EmbeddingDimensionMismatchError: If dimensions don't match and
                database is not empty (critical error requiring migration)
        """
        import chromadb

        chroma_path = chroma_path or settings.chroma_persist_directory
        current_dim = self.embedding_dimension

        result = {
            "compatible": True,
            "current_dimension": current_dim,
            "stored_dimension": None,
            "stored_model": None,
            "document_count": 0,
            "message": "OK",
        }

        # Check if ChromaDB exists
        if not chroma_path.exists():
            result["message"] = "ChromaDB not found - will be created fresh"
            return result

        try:
            # Connect to existing ChromaDB
            client = chromadb.PersistentClient(path=str(chroma_path))

            # Try to get the collection
            try:
                collection = client.get_collection(name=settings.chroma_collection_name)
            except Exception:
                result["message"] = "Collection not found - will be created fresh"
                return result

            # Get document count
            doc_count = collection.count()
            result["document_count"] = doc_count

            if doc_count == 0:
                result["message"] = "Collection exists but empty - compatible"
                return result

            # Get stored metadata
            metadata = collection.metadata or {}
            stored_model = metadata.get("embedding_model")
            stored_dim = metadata.get("embedding_dimension")

            result["stored_model"] = stored_model
            result["stored_dimension"] = stored_dim

            # Check for dimension mismatch
            if stored_dim is not None and stored_dim != current_dim:
                result["compatible"] = False
                result["message"] = (
                    f"DIMENSION MISMATCH: Database has {stored_dim}D embeddings "
                    f"(from {stored_model}), but current model produces {current_dim}D. "
                    f"Migration required before use."
                )
                raise EmbeddingDimensionMismatchError(result["message"])

            # Check model name mismatch (warning, not error)
            if stored_model and stored_model != self.model_name:
                logger.warning(
                    f"Model name changed from '{stored_model}' to '{self.model_name}'. "
                    f"Dimensions match ({current_dim}D), but results may differ."
                )
                result["message"] = (
                    f"Model changed ({stored_model} -> {self.model_name}) but dimensions match"
                )
            else:
                result["message"] = f"Compatible: {doc_count} documents with {current_dim}D embeddings"

            return result

        except EmbeddingDimensionMismatchError:
            raise
        except Exception as e:
            logger.warning(f"Could not validate ChromaDB compatibility: {e}")
            result["message"] = f"Validation skipped due to error: {e}"
            return result


# Global instance management
_embedding_service: Optional[EmbeddingService] = None


def get_embedding_service() -> EmbeddingService:
    """Get or create the global embedding service instance."""
    global _embedding_service
    if _embedding_service is None:
        _embedding_service = EmbeddingService()
    return _embedding_service
