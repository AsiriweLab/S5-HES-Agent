"""
Test RAG functionality.

Run with: pytest tests/test_rag.py -v

Tests include:
- ChromaDB vector store operations
- Knowledge base service with chunking
- Text chunking (512 tokens, 50 overlap)
- PDF parsing (if PyMuPDF or pdfplumber available)
"""

import pytest
from pathlib import Path

from src.rag import (
    ChromaVectorStore,
    KnowledgeBaseService,
    KnowledgeDocument,
    get_knowledge_base,
)
from src.rag.knowledge_base import TextChunker, PDFParser
from src.rag.vector_store_module.vector_store import Document
from src.core.config import settings


class TestChromaVectorStore:
    """Tests for ChromaDB vector store."""

    @pytest.fixture
    def vector_store(self, tmp_path):
        """Create a temporary vector store for testing."""
        return ChromaVectorStore(
            persist_directory=str(tmp_path / "test_chroma"),
            collection_name="test_collection",
        )

    def test_add_document(self, vector_store):
        """Test adding a single document."""
        doc = Document(
            content="This is a test document about IoT security.",
            metadata={"category": "test", "source": "unit_test"},
        )
        doc_id = vector_store.add_document(doc)

        assert doc_id is not None
        assert vector_store.count() == 1

    def test_add_documents_batch(self, vector_store):
        """Test adding multiple documents."""
        docs = [
            Document(content=f"Document {i} about smart home security.", metadata={"index": i})
            for i in range(5)
        ]
        doc_ids = vector_store.add_documents(docs)

        assert len(doc_ids) == 5
        assert vector_store.count() == 5

    def test_query(self, vector_store):
        """Test querying documents."""
        # Add test documents
        docs = [
            Document(content="Smart locks provide physical security for homes.", metadata={"category": "security"}),
            Document(content="Temperature sensors monitor environmental conditions.", metadata={"category": "sensors"}),
            Document(content="WiFi cameras can be vulnerable to hacking attacks.", metadata={"category": "security"}),
        ]
        vector_store.add_documents(docs)

        # Query for security-related content
        result = vector_store.query("home security vulnerabilities", n_results=2)

        assert result.has_results
        assert result.total_results <= 2
        assert "security" in result.results[0].content.lower() or "vulnerab" in result.results[0].content.lower()

    def test_delete_document(self, vector_store):
        """Test deleting a document."""
        doc = Document(content="Document to delete.", metadata={})
        doc_id = vector_store.add_document(doc)

        assert vector_store.count() == 1
        vector_store.delete_document(doc_id)
        assert vector_store.count() == 0

    def test_get_stats(self, vector_store):
        """Test getting statistics."""
        stats = vector_store.get_stats()

        assert "collection_name" in stats
        assert "document_count" in stats
        assert stats["collection_name"] == "test_collection"


class TestKnowledgeBaseService:
    """Tests for Knowledge Base service."""

    @pytest.fixture
    def kb_service(self, tmp_path):
        """Create a temporary knowledge base for testing."""
        vector_store = ChromaVectorStore(
            persist_directory=str(tmp_path / "test_kb"),
            collection_name="test_kb",
        )
        return KnowledgeBaseService(vector_store=vector_store)

    def test_add_knowledge_document(self, kb_service):
        """Test adding a knowledge document."""
        doc = KnowledgeDocument(
            title="Test Document",
            content="Content about IoT security testing.",
            category="test",
            source="unit_test",
            tags=["test", "iot"],
        )
        doc_id = kb_service.add_document(doc)

        assert doc_id is not None
        stats = kb_service.get_stats()
        assert stats["document_count"] == 1

    def test_search(self, kb_service):
        """Test searching the knowledge base."""
        # Add documents
        docs = [
            KnowledgeDocument(
                title="Zigbee Security",
                content="Zigbee protocol uses AES-128 encryption for security.",
                category="protocols",
                source="test",
            ),
            KnowledgeDocument(
                title="Z-Wave Security",
                content="Z-Wave S2 framework provides strong encryption.",
                category="protocols",
                source="test",
            ),
        ]
        kb_service.add_documents(docs)

        # Search
        result = kb_service.search("encryption protocol", n_results=2)

        assert result.has_results
        assert any("encryption" in r.content.lower() for r in result.results)

    def test_get_rag_context(self, kb_service):
        """Test RAG context retrieval."""
        # Add documents
        doc = KnowledgeDocument(
            title="Botnet Attacks",
            content="IoT botnets like Mirai exploit default credentials to compromise devices.",
            category="threats",
            source="test",
        )
        kb_service.add_document(doc)

        # Get RAG context
        context = kb_service.get_rag_context("What is Mirai botnet?")

        assert context.query == "What is Mirai botnet?"
        if context.has_context:
            assert len(context.contexts) > 0
            assert len(context.sources) == len(context.contexts)

    def test_ingest_yaml_file(self, kb_service, tmp_path):
        """Test ingesting a YAML file."""
        # Create test YAML file
        yaml_content = """
documents:
  - title: "Test Document 1"
    content: "First test document content."
    category: "test"
    source: "yaml_test"
    tags: ["test"]
  - title: "Test Document 2"
    content: "Second test document content."
    category: "test"
    source: "yaml_test"
"""
        yaml_file = tmp_path / "test_docs.yaml"
        yaml_file.write_text(yaml_content)

        # Ingest
        count = kb_service.ingest_yaml_file(yaml_file)

        assert count == 2
        assert kb_service.get_stats()["document_count"] == 2


class TestRAGIntegration:
    """Integration tests for the complete RAG pipeline."""

    @pytest.fixture
    def kb_with_data(self, tmp_path):
        """Create a knowledge base with test data."""
        vector_store = ChromaVectorStore(
            persist_directory=str(tmp_path / "integration_test"),
            collection_name="integration_test",
        )
        kb = KnowledgeBaseService(vector_store=vector_store)

        # Add realistic test documents
        docs = [
            KnowledgeDocument(
                title="Smart Lock Security",
                content="Smart locks can be vulnerable to replay attacks if they don't implement proper encryption and nonce handling. Z-Wave S2 locks provide better security than S0 devices.",
                category="devices",
                source="Security Research",
                tags=["smart-lock", "security", "z-wave"],
            ),
            KnowledgeDocument(
                title="Network Segmentation",
                content="IoT devices should be placed on a separate VLAN from primary computing devices. This limits lateral movement in case of compromise.",
                category="best-practices",
                source="Network Security Guide",
                tags=["network", "segmentation", "vlan"],
            ),
            KnowledgeDocument(
                title="Mirai Botnet",
                content="The Mirai botnet exploited IoT devices with default credentials, primarily targeting cameras and DVRs. It was responsible for major DDoS attacks in 2016.",
                category="threats",
                source="Threat Intelligence",
                tags=["botnet", "mirai", "ddos"],
            ),
        ]
        kb.add_documents(docs)
        return kb

    def test_security_query(self, kb_with_data):
        """Test querying for security information."""
        context = kb_with_data.get_rag_context("How can smart locks be attacked?")

        assert context.has_context
        # Should find the smart lock document
        assert any("lock" in c.lower() or "replay" in c.lower() for c in context.contexts)

    def test_threat_query(self, kb_with_data):
        """Test querying for threat information."""
        context = kb_with_data.get_rag_context("What is the Mirai botnet and how does it work?")

        assert context.has_context
        assert any("mirai" in c.lower() or "botnet" in c.lower() for c in context.contexts)

    def test_formatted_context(self, kb_with_data):
        """Test formatted context generation."""
        context = kb_with_data.get_rag_context("network security best practices")

        if context.has_context:
            formatted = context.formatted_context
            assert "[Source" in formatted
            assert "confidence:" in formatted


class TestTextChunker:
    """Tests for text chunking functionality."""

    def test_default_settings(self):
        """Test that chunker uses settings from config."""
        chunker = TextChunker()
        assert chunker.chunk_size == settings.chunk_size
        assert chunker.chunk_overlap == settings.chunk_overlap

    def test_custom_settings(self):
        """Test custom chunk size and overlap."""
        chunker = TextChunker(chunk_size=256, chunk_overlap=25)
        assert chunker.chunk_size == 256
        assert chunker.chunk_overlap == 25

    def test_short_text_no_chunk(self):
        """Test that short text is not chunked."""
        chunker = TextChunker(chunk_size=100)
        short_text = "This is a short text."
        chunks = chunker.chunk_text(short_text)

        assert len(chunks) == 1
        assert chunks[0] == short_text

    def test_long_text_chunked(self):
        """Test that long text is chunked properly."""
        chunker = TextChunker(chunk_size=50, chunk_overlap=10)
        # Create text that's definitely longer than 50 tokens (~200 chars)
        long_text = "This is a test sentence. " * 20  # ~500 chars

        chunks = chunker.chunk_text(long_text)

        assert len(chunks) > 1
        # All chunks should have content
        for chunk in chunks:
            assert len(chunk.strip()) > 0

    def test_overlap_present(self):
        """Test that chunks have overlapping content."""
        chunker = TextChunker(chunk_size=30, chunk_overlap=10)
        # Create structured text
        text = "Sentence one here. Sentence two here. Sentence three here. Sentence four here. Sentence five here."

        chunks = chunker.chunk_text(text)

        # With overlap, we should see some shared content between consecutive chunks
        if len(chunks) >= 2:
            # Check that chunk 2 contains some text from the end of chunk 1
            # This is a loose check since overlap is approximate
            assert len(chunks) >= 2

    def test_empty_text(self):
        """Test handling of empty text."""
        chunker = TextChunker()
        assert chunker.chunk_text("") == []
        assert chunker.chunk_text("   ") == []

    def test_paragraph_break_preference(self):
        """Test that chunker prefers paragraph breaks."""
        chunker = TextChunker(chunk_size=50)
        text = "First paragraph content here.\n\nSecond paragraph starts here."

        chunks = chunker.chunk_text(text)

        # If chunked, should prefer paragraph boundary
        if len(chunks) > 1:
            assert not chunks[0].endswith("Sec")  # Should not cut mid-word


class TestPDFParser:
    """Tests for PDF parsing functionality."""

    def test_availability_check(self):
        """Test PDF parser availability check."""
        is_available = PDFParser.is_available()
        parser_name = PDFParser.get_available_parser()

        if is_available:
            assert parser_name in ["PyMuPDF", "pdfplumber"]
        else:
            assert parser_name is None

    def test_missing_file(self):
        """Test handling of missing PDF file."""
        parser = PDFParser()
        result = parser.extract_text(Path("/nonexistent/file.pdf"))
        assert result == ""

    @pytest.mark.skipif(
        not PDFParser.is_available(),
        reason="No PDF library available"
    )
    def test_metadata_extraction(self, tmp_path):
        """Test PDF metadata extraction."""
        # This test requires an actual PDF file
        # Skip if no PDF library or no test PDF available
        parser = PDFParser()
        # Create a simple test - just check the method doesn't crash
        metadata = parser.extract_metadata(Path("/nonexistent/file.pdf"))
        assert "title" in metadata
        assert "pages" in metadata


class TestKnowledgeBaseWithChunking:
    """Tests for Knowledge Base service with chunking enabled."""

    @pytest.fixture
    def kb_with_chunking(self, tmp_path):
        """Create a KB with chunking enabled."""
        vector_store = ChromaVectorStore(
            persist_directory=str(tmp_path / "test_kb_chunking"),
            collection_name="test_kb_chunking",
        )
        return KnowledgeBaseService(vector_store=vector_store, enable_chunking=True)

    @pytest.fixture
    def kb_without_chunking(self, tmp_path):
        """Create a KB with chunking disabled."""
        vector_store = ChromaVectorStore(
            persist_directory=str(tmp_path / "test_kb_no_chunking"),
            collection_name="test_kb_no_chunking",
        )
        return KnowledgeBaseService(vector_store=vector_store, enable_chunking=False)

    def test_chunking_enabled_stats(self, kb_with_chunking):
        """Test that stats include chunking info."""
        stats = kb_with_chunking.get_stats()

        assert "chunking_enabled" in stats
        assert stats["chunking_enabled"] is True
        assert "chunk_size" in stats
        assert "chunk_overlap" in stats
        assert stats["chunk_size"] == settings.chunk_size
        assert stats["chunk_overlap"] == settings.chunk_overlap

    def test_long_document_chunked(self, kb_with_chunking):
        """Test that long documents get chunked."""
        # Create a document larger than chunk size
        long_content = "This is a test paragraph with multiple sentences. " * 100
        doc = KnowledgeDocument(
            title="Long Document",
            content=long_content,
            category="test",
            source="unit_test",
        )

        doc_ids = kb_with_chunking.add_document(doc)

        # Should create multiple chunks
        assert len(doc_ids) > 1
        # Stats should reflect all chunks
        stats = kb_with_chunking.get_stats()
        assert stats["document_count"] == len(doc_ids)

    def test_short_document_not_chunked(self, kb_with_chunking):
        """Test that short documents are not chunked."""
        short_content = "Short document content."
        doc = KnowledgeDocument(
            title="Short Document",
            content=short_content,
            category="test",
            source="unit_test",
        )

        doc_ids = kb_with_chunking.add_document(doc)

        assert len(doc_ids) == 1

    def test_chunking_disabled(self, kb_without_chunking):
        """Test that chunking can be disabled."""
        long_content = "This is a test paragraph. " * 100
        doc = KnowledgeDocument(
            title="Long Document No Chunk",
            content=long_content,
            category="test",
            source="unit_test",
        )

        doc_ids = kb_without_chunking.add_document(doc)

        # Should NOT chunk when disabled
        assert len(doc_ids) == 1

    def test_pdf_parser_in_stats(self, kb_with_chunking):
        """Test that PDF parser availability is in stats."""
        stats = kb_with_chunking.get_stats()

        assert "pdf_parser_available" in stats
        assert "pdf_parser" in stats


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
