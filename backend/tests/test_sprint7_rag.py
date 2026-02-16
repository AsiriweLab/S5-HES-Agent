"""
Sprint 7: Advanced RAG & Knowledge Management Tests

Tests for:
- Multi-step query orchestration
- Hybrid search (semantic + keyword with RRF)
- Multi-source adapters (academic, threat intel, device specs)
- Provenance tracking and citation generation
- Confidence scoring

Note: Tests import modules directly to avoid chromadb/numpy compatibility issues.
"""

import asyncio
import sys
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Mock chromadb to avoid numpy compatibility issues
sys.modules['chromadb'] = MagicMock()
sys.modules['chromadb.config'] = MagicMock()
sys.modules['chromadb.utils.embedding_functions'] = MagicMock()

# ===========================================================================
# Query Orchestrator Tests
# ===========================================================================


class TestRAGQueryOrchestrator:
    """Tests for the RAGQueryOrchestrator."""

    def test_query_step_creation(self):
        """Test QueryStep dataclass creation using factory method."""
        from src.rag.query.query_orchestrator import CollectionType, QueryStep

        step = QueryStep.create(
            query="What is a botnet?",
            collection=CollectionType.ACADEMIC,
            depends_on=[],
        )

        assert step.query == "What is a botnet?"
        assert step.collection == CollectionType.ACADEMIC
        assert step.depends_on == []
        assert step.status == "pending"

    def test_query_plan_creation(self):
        """Test QueryPlan dataclass creation using factory method."""
        from src.rag.query.query_orchestrator import QueryPlan, QueryStep, QueryType

        plan = QueryPlan.create(
            query="test query",
            query_type=QueryType.MULTI_STEP,
        )

        step1 = QueryStep.create("query1")
        step2 = QueryStep.create("query2")

        plan.add_step(step1)
        plan.add_step(step2)

        assert plan.original_query == "test query"
        assert len(plan.steps) == 2
        assert plan.query_type == QueryType.MULTI_STEP

    def test_provenance_record_citation_generation(self):
        """Test ProvenanceRecord citation generation."""
        from src.rag.query.query_orchestrator import CollectionType, ProvenanceRecord

        record = ProvenanceRecord(
            record_id="rec123",
            source_collection=CollectionType.ACADEMIC,
            document_id="doc123",
            document_title="IoT Security Analysis",
            chunk_index=0,
            retrieval_query="test query",
            similarity_score=0.85,
        )

        # Test IEEE citation format
        ieee_citation = record.to_citation("ieee")
        assert "IoT Security Analysis" in ieee_citation

        # Test APA citation format
        apa_citation = record.to_citation("apa")
        assert "IoT Security Analysis" in apa_citation

    def test_aggregated_result_creation(self):
        """Test AggregatedResult dataclass."""
        from src.rag.query.query_orchestrator import (
            AggregatedResult,
            CollectionType,
            ProvenanceRecord,
        )

        prov = ProvenanceRecord(
            record_id="rec1",
            source_collection=CollectionType.ACADEMIC,
            document_id="doc1",
            document_title="Test Paper",
            similarity_score=0.9,
        )

        result = AggregatedResult(
            result_id="res123",
            original_query="test query",
            contexts=["result1"],
            provenance=[prov],
            confidence_score=0.85,
            collections_queried=[CollectionType.ACADEMIC],
            total_results=1,
            execution_time_ms=100.5,
        )

        assert result.original_query == "test query"
        assert result.confidence_score == 0.85
        assert result.has_results

    def test_query_type_enum(self):
        """Test QueryType enum values."""
        from src.rag.query.query_orchestrator import QueryType

        assert QueryType.SIMPLE.value == "simple"
        assert QueryType.MULTI_STEP.value == "multi_step"
        assert QueryType.AGGREGATED.value == "aggregated"
        assert QueryType.HYBRID.value == "hybrid"

    def test_collection_type_enum(self):
        """Test CollectionType enum in query_orchestrator."""
        from src.rag.query.query_orchestrator import CollectionType

        assert CollectionType.ACADEMIC.value == "academic"
        assert CollectionType.THREAT_INTEL.value == "threat_intel"
        assert CollectionType.DEVICE_SPECS.value == "device_specs"


# ===========================================================================
# Hybrid Search Tests
# ===========================================================================


class TestHybridSearch:
    """Tests for hybrid search combining semantic and keyword search."""

    def test_bm25_index_tokenization(self):
        """Test BM25 index tokenization."""
        from src.rag.query.hybrid_search import BM25Index

        index = BM25Index()
        tokens = index._tokenize("This is a test document about IoT security.")

        assert "test" in tokens
        assert "document" in tokens
        assert "iot" in tokens
        assert "security" in tokens
        # Stopwords should be removed
        assert "is" not in tokens
        assert "a" not in tokens

    def test_bm25_index_add_document(self):
        """Test adding documents to BM25 index."""
        from src.rag.query.hybrid_search import BM25Index

        index = BM25Index()
        index.add_document("doc1", "IoT security vulnerabilities", {"type": "paper"})
        index.add_document("doc2", "Smart home botnet attacks", {"type": "report"})

        assert index.total_docs == 2
        assert "doc1" in index.documents
        assert "doc2" in index.documents

    def test_bm25_search(self):
        """Test BM25 keyword search."""
        from src.rag.query.hybrid_search import BM25Index

        index = BM25Index()
        index.add_document("doc1", "IoT security vulnerabilities and threats")
        index.add_document("doc2", "Smart home botnet attacks on devices")
        index.add_document("doc3", "Network protocol analysis for IoT")

        results = index.search("IoT security", top_k=2)

        assert len(results) <= 2
        # doc1 should rank highest (contains both IoT and security)
        if results:
            assert results[0].document_id == "doc1"

    def test_bm25_idf_calculation(self):
        """Test IDF calculation in BM25."""
        from src.rag.query.hybrid_search import BM25Index

        index = BM25Index()
        index.add_document("doc1", "IoT IoT IoT security")
        index.add_document("doc2", "IoT security threats")
        index.add_document("doc3", "security threats only")

        # "threats" appears in 2 docs out of 3
        # "iot" appears in 2 docs out of 3
        # Both should have same IDF in this case
        idf_iot = index._idf("iot")
        idf_threats = index._idf("threats")

        # Both terms appear in 2/3 docs, so IDF should be equal
        assert idf_iot == idf_threats

    def test_search_mode_enum(self):
        """Test SearchMode enum values."""
        from src.rag.query.hybrid_search import SearchMode

        assert SearchMode.SEMANTIC_ONLY.value == "semantic_only"
        assert SearchMode.KEYWORD_ONLY.value == "keyword_only"
        assert SearchMode.HYBRID.value == "hybrid"
        assert SearchMode.AUTO.value == "auto"

    def test_fusion_method_enum(self):
        """Test FusionMethod enum values."""
        from src.rag.query.hybrid_search import FusionMethod

        assert FusionMethod.RRF.value == "rrf"
        assert FusionMethod.WEIGHTED_SUM.value == "weighted_sum"
        assert FusionMethod.MAX_SCORE.value == "max_score"
        assert FusionMethod.INTERLEAVE.value == "interleave"

    def test_hybrid_search_initialization(self):
        """Test HybridSearch initialization."""
        from src.rag.query.hybrid_search import HybridSearch

        hybrid = HybridSearch(
            semantic_search_fn=None,
            semantic_weight=0.7,
            keyword_weight=0.3,
        )

        assert hybrid.semantic_weight == 0.7
        assert hybrid.keyword_weight == 0.3
        assert hybrid.rrf_k == 60

    def test_rrf_fusion(self):
        """Test Reciprocal Rank Fusion."""
        from src.rag.query.hybrid_search import FusionMethod, HybridSearch, SearchResult

        hybrid = HybridSearch()

        semantic_results = [
            SearchResult("doc1", "content1", 0.9, source="semantic"),
            SearchResult("doc2", "content2", 0.8, source="semantic"),
        ]

        keyword_results = [
            SearchResult("doc2", "content2", 5.0, source="keyword"),
            SearchResult("doc3", "content3", 4.0, source="keyword"),
        ]

        fused = hybrid._fuse_results(
            semantic_results, keyword_results, FusionMethod.RRF, top_k=3
        )

        assert len(fused) <= 3
        # doc2 appears in both, should rank higher
        doc_ids = [r.document_id for r in fused]
        assert "doc2" in doc_ids

    def test_query_expander(self):
        """Test query expansion with synonyms and acronyms."""
        from src.rag.query.hybrid_search import QueryExpander

        expander = QueryExpander()

        # Test acronym expansion
        expansions = expander.expand_query("IoT security IDS")
        assert len(expansions) > 1

        # Test synonym expansion
        expansions = expander.expand_query("attack detection")
        assert any("threat" in e or "exploit" in e for e in expansions)

    @pytest.mark.asyncio
    async def test_hybrid_search_auto_mode_detection(self):
        """Test automatic mode selection based on query."""
        from src.rag.query.hybrid_search import HybridSearch, SearchMode

        hybrid = HybridSearch()

        # CVE pattern should use keyword search
        mode = hybrid._determine_mode("CVE-2023-12345", SearchMode.AUTO)
        assert mode == SearchMode.KEYWORD_ONLY

        # Question should use hybrid
        mode = hybrid._determine_mode("What is a botnet?", SearchMode.AUTO)
        assert mode == SearchMode.HYBRID


# ===========================================================================
# Academic Adapter Tests
# ===========================================================================


class TestAcademicAdapter:
    """Tests for the AcademicPaperAdapter."""

    def test_academic_source_enum(self):
        """Test AcademicSource enum."""
        from src.rag.adapters.academic_adapter import AcademicSource

        assert AcademicSource.ARXIV.value == "arxiv"
        assert AcademicSource.SEMANTIC_SCHOLAR.value == "semantic_scholar"
        assert AcademicSource.IEEE.value == "ieee"

    def test_academic_paper_dataclass(self):
        """Test AcademicPaper dataclass."""
        from src.rag.adapters.academic_adapter import AcademicPaper, AcademicSource

        paper = AcademicPaper(
            paper_id="arxiv:2301.00001",
            title="IoT Security Analysis",
            authors=["John Doe", "Jane Smith"],
            abstract="This paper analyzes IoT security...",
            year=2023,
            source=AcademicSource.ARXIV,
        )

        assert paper.paper_id == "arxiv:2301.00001"
        assert len(paper.authors) == 2
        assert paper.year == 2023

    def test_academic_paper_attributes(self):
        """Test AcademicPaper attributes."""
        from src.rag.adapters.academic_adapter import AcademicPaper, AcademicSource

        paper = AcademicPaper(
            paper_id="test123",
            title="Smart Home Security",
            authors=["Alice Brown", "Bob Wilson"],
            abstract="Abstract text about smart home security.",
            year=2024,
            source=AcademicSource.IEEE,
            venue="IEEE S&P",
        )

        # Test attributes directly
        assert paper.title == "Smart Home Security"
        assert "Alice Brown" in paper.authors
        assert paper.year == 2024
        assert paper.venue == "IEEE S&P"

    def test_arxiv_client_initialization(self):
        """Test ArxivClient initialization."""
        from src.rag.adapters.academic_adapter import ArxivClient

        client = ArxivClient()
        assert client is not None

    def test_semantic_scholar_client_initialization(self):
        """Test SemanticScholarClient initialization."""
        from src.rag.adapters.academic_adapter import SemanticScholarClient

        client = SemanticScholarClient()
        assert client is not None


# ===========================================================================
# Threat Intel Adapter Tests
# ===========================================================================


class TestThreatIntelAdapter:
    """Tests for the ThreatIntelAdapter."""

    def test_threat_source_enum(self):
        """Test ThreatSource enum."""
        from src.rag.adapters.threat_intel_adapter import ThreatSource

        assert ThreatSource.MITRE_ATTACK.value == "mitre_attack"
        assert ThreatSource.NVD.value == "nvd"
        assert ThreatSource.CWE.value == "cwe"

    def test_mitre_technique_dataclass(self):
        """Test MitreAttackTechnique dataclass."""
        from src.rag.adapters.threat_intel_adapter import MitreAttackTechnique

        technique = MitreAttackTechnique(
            technique_id="T1059",
            name="Command and Scripting Interpreter",
            description="Adversaries may abuse command interpreters...",
            tactics=["execution"],
            platforms=["Linux", "Windows", "macOS"],
        )

        assert technique.technique_id == "T1059"
        assert "execution" in technique.tactics
        assert len(technique.platforms) == 3

    def test_cve_entry_dataclass(self):
        """Test CVEEntry dataclass."""
        from src.rag.adapters.threat_intel_adapter import CVEEntry

        cve = CVEEntry(
            cve_id="CVE-2023-12345",
            description="A vulnerability in IoT devices...",
            severity="HIGH",
            cvss_v3_score=8.5,
            affected_products=["Smart Thermostat v1.0"],
        )

        assert cve.cve_id == "CVE-2023-12345"
        assert cve.severity == "HIGH"
        assert cve.cvss_v3_score == 8.5

    def test_cwe_entry_dataclass(self):
        """Test CWEEntry dataclass."""
        from src.rag.adapters.threat_intel_adapter import CWEEntry

        cwe = CWEEntry(
            cwe_id="CWE-79",
            name="Cross-site Scripting (XSS)",
            description="Improper neutralization of input...",
        )

        assert cwe.cwe_id == "CWE-79"
        assert "XSS" in cwe.name

    def test_nvd_client_initialization(self):
        """Test NVDClient initialization."""
        from src.rag.adapters.threat_intel_adapter import NVDClient

        client = NVDClient()
        assert client is not None


# ===========================================================================
# Device Spec Adapter Tests
# ===========================================================================


class TestDeviceSpecAdapter:
    """Tests for the DeviceSpecAdapter."""

    def test_device_category_enum(self):
        """Test DeviceCategory enum."""
        from src.rag.adapters.device_spec_adapter import DeviceCategory

        assert DeviceCategory.SMART_LIGHT.value == "smart_light"
        assert DeviceCategory.SMART_LOCK.value == "smart_lock"
        assert DeviceCategory.SMART_THERMOSTAT.value == "smart_thermostat"

    def test_communication_protocol_enum(self):
        """Test CommunicationProtocol enum."""
        from src.rag.adapters.device_spec_adapter import CommunicationProtocol

        assert CommunicationProtocol.ZIGBEE.value == "zigbee"
        assert CommunicationProtocol.ZWAVE.value == "zwave"
        assert CommunicationProtocol.MATTER.value == "matter"
        assert CommunicationProtocol.MQTT.value == "mqtt"

    def test_device_specification_dataclass(self):
        """Test DeviceSpecification dataclass."""
        from src.rag.adapters.device_spec_adapter import (
            CommunicationProtocol,
            DeviceCategory,
            DeviceSpecification,
        )

        spec = DeviceSpecification(
            device_id="philips_hue_bulb_001",
            manufacturer="Philips",
            model="Hue White A19",
            category=DeviceCategory.SMART_LIGHT,
            protocols=[CommunicationProtocol.ZIGBEE, CommunicationProtocol.BLUETOOTH_LE],
            encryption_supported=["AES-128"],
        )

        assert spec.manufacturer == "Philips"
        assert DeviceCategory.SMART_LIGHT in [spec.category]
        assert CommunicationProtocol.ZIGBEE in spec.protocols

    def test_device_specification_to_document(self):
        """Test converting DeviceSpecification to document text."""
        from src.rag.adapters.device_spec_adapter import (
            CommunicationProtocol,
            DeviceCategory,
            DeviceSpecification,
        )

        spec = DeviceSpecification(
            device_id="test_device",
            manufacturer="TestCorp",
            model="Device X",
            category=DeviceCategory.SMART_SENSOR,
            protocols=[CommunicationProtocol.WIFI],
            encryption_supported=["TLS 1.3"],
        )

        doc_text = spec.to_document_text()

        assert "TestCorp" in doc_text
        assert "Device X" in doc_text
        assert "smart_sensor" in doc_text

    def test_protocol_specification_dataclass(self):
        """Test ProtocolSpecification dataclass."""
        from src.rag.adapters.device_spec_adapter import (
            CommunicationProtocol,
            ProtocolSpecification,
        )

        spec = ProtocolSpecification(
            protocol=CommunicationProtocol.ZIGBEE,
            version="3.0",
            security_features=["AES-128 encryption", "Network key"],
            encryption_methods=["AES-128-CCM"],
            topology="Mesh",
            known_attacks=["Key sniffing during joining"],
        )

        assert spec.protocol == CommunicationProtocol.ZIGBEE
        assert spec.version == "3.0"
        assert "Mesh" in spec.topology

    def test_security_advisory_dataclass(self):
        """Test SecurityAdvisory dataclass."""
        from src.rag.adapters.device_spec_adapter import (
            CommunicationProtocol,
            SecurityAdvisory,
        )

        advisory = SecurityAdvisory(
            advisory_id="SA-2023-001",
            title="ZigBee Key Extraction Vulnerability",
            description="A vulnerability allowing key extraction...",
            severity="high",
            affected_devices=["Device A", "Device B"],
            affected_protocols=[CommunicationProtocol.ZIGBEE],
            cve_ids=["CVE-2023-99999"],
        )

        assert advisory.severity == "high"
        assert len(advisory.cve_ids) == 1

    @pytest.mark.asyncio
    async def test_local_device_database_initialization(self):
        """Test LocalDeviceDatabase initialization with default protocols."""
        from src.rag.adapters.device_spec_adapter import (
            CommunicationProtocol,
            LocalDeviceDatabase,
        )

        db = LocalDeviceDatabase()
        await db.initialize()

        # Should have default protocol specs
        assert len(db.protocols) > 0

        # Check Zigbee is present
        zigbee_spec = db.get_protocol_spec(CommunicationProtocol.ZIGBEE)
        assert zigbee_spec is not None
        assert zigbee_spec.version == "3.0"

    @pytest.mark.asyncio
    async def test_device_spec_adapter_get_protocol(self):
        """Test getting protocol specifications."""
        from src.rag.adapters.device_spec_adapter import (
            CommunicationProtocol,
            DeviceSpecAdapter,
        )

        adapter = DeviceSpecAdapter()
        await adapter.initialize()

        # Get Zigbee specification
        zigbee = adapter.get_protocol_specification(CommunicationProtocol.ZIGBEE)

        assert zigbee is not None
        assert zigbee.protocol == CommunicationProtocol.ZIGBEE
        assert "AES" in str(zigbee.encryption_methods)

    @pytest.mark.asyncio
    async def test_device_spec_adapter_security_recommendations(self):
        """Test security recommendations for protocols."""
        from src.rag.adapters.device_spec_adapter import (
            CommunicationProtocol,
            DeviceSpecAdapter,
        )

        adapter = DeviceSpecAdapter()
        await adapter.initialize()

        recommendations = adapter.get_security_recommendations(
            CommunicationProtocol.MQTT
        )

        assert len(recommendations) > 0
        # Should include TLS recommendation for MQTT
        assert any("TLS" in r for r in recommendations)


# ===========================================================================
# Collection Type Tests
# ===========================================================================


class TestCollectionType:
    """Tests for CollectionType enum from knowledge_base."""

    def test_collection_type_values(self):
        """Test CollectionType enum values."""
        from src.rag.knowledge_base import CollectionType

        assert CollectionType.SECURITY_RESEARCH.value == "security_research"
        assert CollectionType.ATTACK_PATTERNS.value == "attack_patterns"
        assert CollectionType.DEVICE_MANUALS.value == "device_manuals"
        assert CollectionType.NETWORK_PROTOCOLS.value == "network_protocols"
        assert CollectionType.THREAT_INTELLIGENCE.value == "threat_intelligence"


# ===========================================================================
# Integration Tests
# ===========================================================================


class TestRAGIntegration:
    """Integration tests for Sprint 7 RAG components."""

    @pytest.mark.asyncio
    async def test_full_hybrid_search_flow(self):
        """Test complete hybrid search flow."""
        from src.rag.query.hybrid_search import (
            FusionMethod,
            HybridSearch,
            SearchMode,
        )

        # Create hybrid search without semantic (keyword only for this test)
        hybrid = HybridSearch()

        # Index some documents
        hybrid.index_documents(
            [
                {"id": "doc1", "content": "IoT botnet Mirai attack patterns"},
                {"id": "doc2", "content": "Smart home security vulnerabilities"},
                {"id": "doc3", "content": "Zigbee protocol weaknesses"},
            ],
            collection="test",
        )

        # Search
        result = await hybrid.search(
            query="IoT security",
            collection="test",
            top_k=3,
            mode=SearchMode.KEYWORD_ONLY,
        )

        assert result.query == "IoT security"
        assert result.mode_used == SearchMode.KEYWORD_ONLY
        assert len(result.results) <= 3

    @pytest.mark.asyncio
    async def test_adapter_initialization(self):
        """Test that all adapters can be initialized."""
        from src.rag.adapters import (
            get_academic_adapter,
            get_device_spec_adapter,
            get_threat_intel_adapter,
        )

        academic = get_academic_adapter()
        threat = get_threat_intel_adapter()
        device = get_device_spec_adapter()

        assert academic is not None
        assert threat is not None
        assert device is not None

        # Initialize device adapter to load default protocols
        await device.initialize()
        protocols = device.get_all_protocols()
        assert len(protocols) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
