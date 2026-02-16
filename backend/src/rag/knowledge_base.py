"""
Knowledge Base Service

High-level service for managing the IoT security knowledge base.
Provides document ingestion, retrieval, and RAG query capabilities.

Features:
- Text chunking with configurable size (512 tokens) and overlap (50 tokens)
- PDF document parsing via PyMuPDF or pdfplumber
- YAML and Markdown file ingestion
- Semantic search with similarity scoring
"""

import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Optional

import yaml
from loguru import logger

from src.core.config import settings
from src.rag.vector_store_module import ChromaVectorStore, get_vector_store
from src.rag.vector_store_module.vector_store import Document, QueryResult
from src.rag.retriever.hybrid_retriever import HybridRetriever, get_hybrid_retriever


class TextChunker:
    """
    Text chunker for splitting documents into overlapping chunks.

    Uses token-based chunking with configurable size and overlap.
    Default: 512 tokens per chunk, 50 tokens overlap.
    """

    def __init__(
        self,
        chunk_size: Optional[int] = None,
        chunk_overlap: Optional[int] = None,
    ):
        """
        Initialize the text chunker.

        Args:
            chunk_size: Maximum tokens per chunk (default: settings.chunk_size = 512)
            chunk_overlap: Token overlap between chunks (default: settings.chunk_overlap = 50)
        """
        self.chunk_size = chunk_size or settings.chunk_size
        self.chunk_overlap = chunk_overlap or settings.chunk_overlap

        # Approximate characters per token (average for English text)
        self._chars_per_token = 4

        logger.debug(
            f"TextChunker initialized: chunk_size={self.chunk_size}, "
            f"chunk_overlap={self.chunk_overlap}"
        )

    def _estimate_tokens(self, text: str) -> int:
        """Estimate token count from character count."""
        return len(text) // self._chars_per_token

    def _tokens_to_chars(self, tokens: int) -> int:
        """Convert token count to approximate character count."""
        return tokens * self._chars_per_token

    def chunk_text(self, text: str) -> list[str]:
        """
        Split text into overlapping chunks.

        Args:
            text: The text to chunk

        Returns:
            List of text chunks
        """
        if not text or not text.strip():
            return []

        # Calculate character limits from token limits
        max_chars = self._tokens_to_chars(self.chunk_size)
        overlap_chars = self._tokens_to_chars(self.chunk_overlap)

        # If text is smaller than chunk size, return as single chunk
        if len(text) <= max_chars:
            return [text.strip()]

        chunks = []
        start = 0

        while start < len(text):
            # Calculate end position
            end = start + max_chars

            if end >= len(text):
                # Last chunk
                chunk = text[start:].strip()
                if chunk:
                    chunks.append(chunk)
                break

            # Try to find a natural break point (sentence or paragraph end)
            break_point = self._find_break_point(text, start, end)

            chunk = text[start:break_point].strip()
            if chunk:
                chunks.append(chunk)

            # Move start position with overlap
            start = break_point - overlap_chars
            if start < 0:
                start = 0

            # Avoid infinite loop
            if start >= break_point:
                start = break_point

        logger.debug(f"Chunked text into {len(chunks)} chunks")
        return chunks

    def _find_break_point(self, text: str, start: int, end: int) -> int:
        """
        Find a natural break point near the end position.

        Prefers: paragraph end > sentence end > word boundary
        """
        search_window = min(200, end - start)  # Look back up to 200 chars
        search_start = max(start, end - search_window)
        search_text = text[search_start:end]

        # Look for paragraph break
        para_match = search_text.rfind('\n\n')
        if para_match != -1:
            return search_start + para_match + 2

        # Look for sentence end
        sentence_patterns = ['. ', '! ', '? ', '.\n', '!\n', '?\n']
        best_break = -1
        for pattern in sentence_patterns:
            pos = search_text.rfind(pattern)
            if pos > best_break:
                best_break = pos

        if best_break != -1:
            return search_start + best_break + 2

        # Look for any newline
        newline_pos = search_text.rfind('\n')
        if newline_pos != -1:
            return search_start + newline_pos + 1

        # Fall back to word boundary
        space_pos = search_text.rfind(' ')
        if space_pos != -1:
            return search_start + space_pos + 1

        # No good break point found, use hard cut
        return end


class PDFParser:
    """
    PDF document parser with fallback support.

    Tries parsers in order: PyMuPDF (fitz) > pdfplumber > basic extraction
    """

    @staticmethod
    def is_available() -> bool:
        """Check if any PDF parsing library is available."""
        try:
            import fitz  # PyMuPDF
            return True
        except ImportError:
            pass

        try:
            import pdfplumber
            return True
        except ImportError:
            pass

        return False

    @staticmethod
    def get_available_parser() -> Optional[str]:
        """Get the name of the available PDF parser."""
        try:
            import fitz
            return "PyMuPDF"
        except ImportError:
            pass

        try:
            import pdfplumber
            return "pdfplumber"
        except ImportError:
            pass

        return None

    def extract_text(self, pdf_path: Path) -> str:
        """
        Extract text from a PDF file.

        Args:
            pdf_path: Path to the PDF file

        Returns:
            Extracted text content
        """
        if not pdf_path.exists():
            logger.error(f"PDF file not found: {pdf_path}")
            return ""

        # Try PyMuPDF first (fastest and most reliable)
        try:
            import fitz
            return self._extract_with_pymupdf(pdf_path)
        except ImportError:
            pass

        # Try pdfplumber as fallback
        try:
            import pdfplumber
            return self._extract_with_pdfplumber(pdf_path)
        except ImportError:
            pass

        logger.warning(
            f"No PDF library available. Install PyMuPDF (pip install pymupdf) "
            f"or pdfplumber (pip install pdfplumber) to parse PDFs."
        )
        return ""

    def _extract_with_pymupdf(self, pdf_path: Path) -> str:
        """Extract text using PyMuPDF."""
        import fitz

        try:
            doc = fitz.open(str(pdf_path))
            text_parts = []

            for page_num, page in enumerate(doc):
                page_text = page.get_text()
                if page_text.strip():
                    text_parts.append(f"[Page {page_num + 1}]\n{page_text}")

            doc.close()

            full_text = "\n\n".join(text_parts)
            logger.debug(f"Extracted {len(full_text)} chars from PDF using PyMuPDF")
            return full_text

        except Exception as e:
            logger.error(f"PyMuPDF extraction failed for {pdf_path}: {e}")
            return ""

    def _extract_with_pdfplumber(self, pdf_path: Path) -> str:
        """Extract text using pdfplumber."""
        import pdfplumber

        try:
            with pdfplumber.open(str(pdf_path)) as pdf:
                text_parts = []

                for page_num, page in enumerate(pdf.pages):
                    page_text = page.extract_text()
                    if page_text and page_text.strip():
                        text_parts.append(f"[Page {page_num + 1}]\n{page_text}")

                full_text = "\n\n".join(text_parts)
                logger.debug(f"Extracted {len(full_text)} chars from PDF using pdfplumber")
                return full_text

        except Exception as e:
            logger.error(f"pdfplumber extraction failed for {pdf_path}: {e}")
            return ""

    def extract_metadata(self, pdf_path: Path) -> dict:
        """
        Extract metadata from a PDF file.

        Args:
            pdf_path: Path to the PDF file

        Returns:
            Dictionary with PDF metadata
        """
        metadata = {
            "title": pdf_path.stem,
            "pages": 0,
            "author": None,
            "creation_date": None,
        }

        try:
            import fitz
            doc = fitz.open(str(pdf_path))
            metadata["pages"] = len(doc)

            pdf_meta = doc.metadata
            if pdf_meta:
                metadata["title"] = pdf_meta.get("title") or pdf_path.stem
                metadata["author"] = pdf_meta.get("author")
                metadata["creation_date"] = pdf_meta.get("creationDate")

            doc.close()

        except ImportError:
            try:
                import pdfplumber
                with pdfplumber.open(str(pdf_path)) as pdf:
                    metadata["pages"] = len(pdf.pages)
                    if pdf.metadata:
                        metadata["title"] = pdf.metadata.get("Title") or pdf_path.stem
                        metadata["author"] = pdf.metadata.get("Author")
            except ImportError:
                pass
        except Exception as e:
            logger.warning(f"Failed to extract PDF metadata: {e}")

        return metadata


class CollectionType(str, Enum):
    """Knowledge base collection types."""
    SECURITY_RESEARCH = "security_research"
    ATTACK_PATTERNS = "attack_patterns"
    DEVICE_MANUALS = "device_manuals"
    NETWORK_PROTOCOLS = "network_protocols"
    THREAT_INTELLIGENCE = "threat_intelligence"


@dataclass
class KnowledgeDocument:
    """A knowledge base document with rich metadata."""

    title: str
    content: str
    category: str
    source: str
    tags: list[str] = field(default_factory=list)
    doc_id: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.utcnow)

    def to_document(self) -> Document:
        """Convert to vector store Document."""
        return Document(
            content=self.content,
            metadata={
                "title": self.title,
                "category": self.category,
                "source": self.source,
                "tags": ",".join(self.tags),
                "created_at": self.created_at.isoformat(),
            },
            doc_id=self.doc_id,
        )


@dataclass
class RAGContext:
    """Context retrieved for RAG augmentation."""

    query: str
    contexts: list[str]
    sources: list[str]
    confidence_scores: list[float]
    retrieval_time_ms: float

    @property
    def has_context(self) -> bool:
        return len(self.contexts) > 0

    @property
    def formatted_context(self) -> str:
        """Format contexts for LLM prompt injection."""
        if not self.contexts:
            return ""

        formatted_parts = []
        for i, (ctx, src, score) in enumerate(
            zip(self.contexts, self.sources, self.confidence_scores), 1
        ):
            formatted_parts.append(
                f"[Source {i}: {src or 'Unknown'} (confidence: {score:.2f})]\n{ctx}"
            )

        return "\n\n".join(formatted_parts)


class KnowledgeBaseService:
    """
    Knowledge Base Service for IoT Security Research.

    Features:
    - Document ingestion from files and directories (YAML, Markdown, PDF)
    - Text chunking with 512 tokens and 50 token overlap
    - Semantic search with similarity scoring
    - RAG context generation for LLM augmentation
    - Research integrity: Source tracking and confidence scoring
    """

    def __init__(
        self,
        vector_store: Optional[ChromaVectorStore] = None,
        enable_chunking: bool = True,
        enable_hybrid_search: Optional[bool] = None,
    ):
        self.vector_store = vector_store or get_vector_store()
        self.knowledge_base_path = settings.knowledge_base_path
        self.enable_chunking = enable_chunking

        # Hybrid search configuration
        self.enable_hybrid_search = enable_hybrid_search
        if self.enable_hybrid_search is None:
            self.enable_hybrid_search = settings.search_mode in ("hybrid", "auto")

        # Initialize hybrid retriever if enabled
        self._hybrid_retriever: Optional[HybridRetriever] = None
        if self.enable_hybrid_search:
            self._hybrid_retriever = get_hybrid_retriever()

        # Initialize text chunker and PDF parser
        self.chunker = TextChunker()
        self.pdf_parser = PDFParser()

        logger.info(
            f"KnowledgeBaseService initialized "
            f"(chunking={'enabled' if enable_chunking else 'disabled'}, "
            f"chunk_size={settings.chunk_size}, overlap={settings.chunk_overlap}, "
            f"hybrid_search={'enabled' if self.enable_hybrid_search else 'disabled'})"
        )

    def add_document(self, doc: KnowledgeDocument, chunk: bool = None) -> list[str]:
        """
        Add a single knowledge document, optionally chunking it.

        Args:
            doc: The document to add
            chunk: Whether to chunk the document (default: self.enable_chunking)

        Returns:
            List of document/chunk IDs
        """
        should_chunk = chunk if chunk is not None else self.enable_chunking

        if should_chunk and len(doc.content) > self.chunker._tokens_to_chars(self.chunker.chunk_size):
            # Chunk the document
            chunks = self.chunker.chunk_text(doc.content)
            doc_ids = []

            for i, chunk_text in enumerate(chunks):
                chunk_metadata = {
                    "title": doc.title,
                    "category": doc.category,
                    "source": doc.source,
                    "tags": ",".join(doc.tags),
                    "created_at": doc.created_at.isoformat(),
                    "chunk_index": i,
                    "total_chunks": len(chunks),
                    "is_chunk": True,
                }
                chunk_doc = Document(
                    content=chunk_text,
                    metadata=chunk_metadata,
                )
                doc_id = self.vector_store.add_document(chunk_doc)
                doc_ids.append(doc_id)

                # Index in BM25 for hybrid search
                if self._hybrid_retriever:
                    self._hybrid_retriever.index_document(doc_id, chunk_text, chunk_metadata)

            logger.info(f"Added document: {doc.title} [{doc.category}] ({len(chunks)} chunks)")
            return doc_ids
        else:
            # Add as single document
            vector_doc = doc.to_document()
            doc_id = self.vector_store.add_document(vector_doc)

            # Index in BM25 for hybrid search
            if self._hybrid_retriever:
                self._hybrid_retriever.index_document(doc_id, doc.content, vector_doc.metadata)

            logger.info(f"Added document: {doc.title} [{doc.category}]")
            return [doc_id]

    def add_documents(self, docs: list[KnowledgeDocument], chunk: bool = None) -> list[str]:
        """
        Add multiple knowledge documents with optional chunking.

        Args:
            docs: List of documents to add
            chunk: Whether to chunk documents (default: self.enable_chunking)

        Returns:
            List of all document/chunk IDs
        """
        all_doc_ids = []
        for doc in docs:
            doc_ids = self.add_document(doc, chunk=chunk)
            all_doc_ids.extend(doc_ids)

        logger.info(f"Added {len(docs)} documents ({len(all_doc_ids)} total chunks) to knowledge base")
        return all_doc_ids

    def search(
        self,
        query: str,
        n_results: int = 5,
        category: Optional[str] = None,
        search_mode: Optional[str] = None,
    ) -> QueryResult:
        """
        Search the knowledge base.

        Args:
            query: Search query
            n_results: Number of results
            category: Optional category filter
            search_mode: Override search mode (semantic_only, keyword_only, hybrid, auto)

        Returns:
            QueryResult with matching documents
        """
        where_filter = {"category": category} if category else None

        # Use hybrid retriever if enabled
        if self._hybrid_retriever and (search_mode != "semantic_only"):
            return self._hybrid_retriever.query_sync(
                query_text=query,
                n_results=n_results,
                where=where_filter,
                search_mode=search_mode,
            )

        # Fall back to vector store (semantic only)
        return self.vector_store.query(
            query_text=query,
            n_results=n_results,
            where=where_filter,
        )

    def get_rag_context(
        self,
        query: str,
        n_results: Optional[int] = None,
        search_mode: Optional[str] = None,
    ) -> RAGContext:
        """
        Get RAG context for LLM augmentation.

        Args:
            query: The user's question
            n_results: Number of context chunks to retrieve
            search_mode: Override search mode (semantic_only, keyword_only, hybrid, auto)

        Returns:
            RAGContext with retrieved information
        """
        n_results = n_results or settings.rag_top_k

        # Use hybrid retriever if enabled
        if self._hybrid_retriever and (search_mode != "semantic_only"):
            result = self._hybrid_retriever.query_sync(
                query_text=query,
                n_results=n_results,
                include_below_threshold=False,
                search_mode=search_mode,
            )
        else:
            result = self.vector_store.query(
                query_text=query,
                n_results=n_results,
                include_below_threshold=False,
            )

        contexts = [r.content for r in result.results]
        sources = [r.metadata.get("source", r.metadata.get("title", "Unknown")) for r in result.results]
        # Use normalized confidence scores to handle different score types (similarity, BM25, RRF)
        # This ensures consistent 0-1 confidence values regardless of retrieval mode
        scores = [r.normalized_confidence for r in result.results]

        return RAGContext(
            query=query,
            contexts=contexts,
            sources=sources,
            confidence_scores=scores,
            retrieval_time_ms=result.query_time_ms,
        )

    def ingest_yaml_file(self, file_path: Path) -> int:
        """
        Ingest documents from a YAML file.

        Expected format:
        ```yaml
        documents:
          - title: "Document Title"
            content: "Document content..."
            category: "category_name"
            source: "source_reference"
            tags: ["tag1", "tag2"]
        ```

        Args:
            file_path: Path to YAML file

        Returns:
            Number of documents ingested
        """
        with open(file_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        if not data or "documents" not in data:
            logger.warning(f"No documents found in {file_path}")
            return 0

        docs = []
        for doc_data in data["documents"]:
            doc = KnowledgeDocument(
                title=doc_data.get("title", "Untitled"),
                content=doc_data["content"],
                category=doc_data.get("category", "general"),
                source=doc_data.get("source", str(file_path)),
                tags=doc_data.get("tags", []),
            )
            docs.append(doc)

        self.add_documents(docs)
        logger.info(f"Ingested {len(docs)} documents from {file_path}")
        return len(docs)

    def ingest_markdown_file(self, file_path: Path, category: str = "general") -> int:
        """
        Ingest a markdown file as a single document.

        Args:
            file_path: Path to markdown file
            category: Document category

        Returns:
            Number of documents ingested (1 if successful)
        """
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Extract title from first heading or filename
        title = file_path.stem
        lines = content.split("\n")
        for line in lines:
            if line.startswith("# "):
                title = line[2:].strip()
                break

        doc = KnowledgeDocument(
            title=title,
            content=content,
            category=category,
            source=str(file_path),
            tags=[category, "markdown"],
        )

        self.add_document(doc)
        return 1

    def ingest_pdf_file(
        self,
        file_path: Path,
        category: str = "general",
        metadata: Optional[dict] = None,
    ) -> int:
        """
        Ingest a PDF file with text extraction and chunking.

        Args:
            file_path: Path to PDF file
            category: Document category
            metadata: Optional additional metadata (title, author, etc.)

        Returns:
            Number of chunks ingested (0 if extraction failed)
        """
        if not PDFParser.is_available():
            logger.warning(
                f"Cannot ingest PDF {file_path}: No PDF library available. "
                f"Install PyMuPDF (pip install pymupdf) or pdfplumber."
            )
            return 0

        # Extract text from PDF
        content = self.pdf_parser.extract_text(file_path)
        if not content or not content.strip():
            logger.warning(f"No text extracted from PDF: {file_path}")
            return 0

        # Get PDF metadata
        pdf_metadata = self.pdf_parser.extract_metadata(file_path)
        if metadata:
            pdf_metadata.update(metadata)

        # Create document
        title = pdf_metadata.get("title", file_path.stem)
        doc = KnowledgeDocument(
            title=title,
            content=content,
            category=category,
            source=str(file_path),
            tags=[category, "pdf", f"pages:{pdf_metadata.get('pages', 0)}"],
        )

        # Add document (will be chunked automatically if enabled)
        doc_ids = self.add_document(doc)

        logger.info(
            f"Ingested PDF: {title} [{category}] "
            f"({pdf_metadata.get('pages', '?')} pages, {len(doc_ids)} chunks)"
        )
        return len(doc_ids)

    def ingest_directory(
        self,
        directory: Optional[Path] = None,
        recursive: bool = True,
        include_pdfs: bool = True,
    ) -> int:
        """
        Ingest all supported files from a directory.

        Supported formats: YAML, Markdown, PDF

        Args:
            directory: Directory path (default: knowledge_base_path)
            recursive: Whether to search recursively
            include_pdfs: Whether to include PDF files (requires PyMuPDF or pdfplumber)

        Returns:
            Total number of documents/chunks ingested
        """
        directory = directory or self.knowledge_base_path

        # Resolve relative paths to absolute
        if not directory.is_absolute():
            directory = directory.resolve()
            logger.debug(f"Resolved knowledge base path to: {directory}")

        if not directory.exists():
            logger.warning(f"Directory does not exist: {directory}")
            return 0

        total = 0
        pattern = "**/*" if recursive else "*"

        # Ingest YAML files
        for yaml_file in directory.glob(f"{pattern}.yaml"):
            total += self.ingest_yaml_file(yaml_file)

        for yml_file in directory.glob(f"{pattern}.yml"):
            total += self.ingest_yaml_file(yml_file)

        # Ingest Markdown files
        for md_file in directory.glob(f"{pattern}.md"):
            # Determine category from parent directory
            category = md_file.parent.name if md_file.parent != directory else "general"
            total += self.ingest_markdown_file(md_file, category)

        # Ingest PDF files
        if include_pdfs:
            if PDFParser.is_available():
                for pdf_file in directory.glob(f"{pattern}.pdf"):
                    # Determine category from parent directory
                    category = pdf_file.parent.name if pdf_file.parent != directory else "general"
                    total += self.ingest_pdf_file(pdf_file, category)
            else:
                pdf_count = len(list(directory.glob(f"{pattern}.pdf")))
                if pdf_count > 0:
                    logger.warning(
                        f"Found {pdf_count} PDF files but no PDF library available. "
                        f"Install PyMuPDF (pip install pymupdf) or pdfplumber."
                    )

        logger.info(f"Ingested {total} documents/chunks from {directory}")
        return total

    def get_stats(self) -> dict:
        """Get knowledge base statistics including chunking and hybrid search configuration."""
        # Get base stats from hybrid retriever or vector store
        if self._hybrid_retriever:
            base_stats = self._hybrid_retriever.get_stats()
        else:
            base_stats = self.vector_store.get_stats()

        return {
            **base_stats,
            "knowledge_base_path": str(self.knowledge_base_path),
            "chunking_enabled": self.enable_chunking,
            "chunk_size": settings.chunk_size,
            "chunk_overlap": settings.chunk_overlap,
            "pdf_parser_available": PDFParser.is_available(),
            "pdf_parser": PDFParser.get_available_parser(),
            "hybrid_search_enabled": self.enable_hybrid_search,
        }

    def get_collection_stats(self, collection_type: CollectionType) -> dict[str, Any]:
        """
        Get statistics for a specific collection.

        Args:
            collection_type: The collection to get stats for

        Returns:
            Dictionary with collection statistics
        """
        # Query the vector store for this collection's documents
        try:
            # Get all documents in this category/collection
            result = self.vector_store.query(
                query_text="",  # Empty query to match all
                n_results=1000,  # Get as many as possible
                where={"category": collection_type.value},
            )

            # Extract unique categories and sources
            categories = set()
            sources = set()
            dates = []

            for doc_result in result.results:
                if doc_result.metadata:
                    if "category" in doc_result.metadata:
                        categories.add(doc_result.metadata["category"])
                    if "source" in doc_result.metadata:
                        sources.add(doc_result.metadata["source"])
                    if "created_at" in doc_result.metadata:
                        dates.append(doc_result.metadata["created_at"])

            # Calculate date range
            date_range = None
            if dates:
                sorted_dates = sorted(dates)
                date_range = {
                    "earliest": sorted_dates[0],
                    "latest": sorted_dates[-1],
                }

            return {
                "document_count": result.total_results,
                "chunk_count": result.total_results,  # In this implementation, 1 doc = 1 chunk
                "categories": list(categories),
                "sources": list(sources),
                "date_range": date_range,
            }

        except Exception as e:
            logger.warning(f"Failed to get collection stats for {collection_type}: {e}")
            return {
                "document_count": 0,
                "chunk_count": 0,
                "categories": [],
                "sources": [],
                "date_range": None,
            }

    def clear(self) -> bool:
        """Clear all documents from the knowledge base."""
        return self.vector_store.reset()


# Global instance management
_knowledge_base: Optional[KnowledgeBaseService] = None


def get_knowledge_base() -> KnowledgeBaseService:
    """Get or create the global knowledge base instance."""
    global _knowledge_base
    if _knowledge_base is None:
        _knowledge_base = KnowledgeBaseService()
    return _knowledge_base
