"""
Sprint 7 Scale Tests - RAG with 1000+ Real Documents

Tests RAG functionality with real data from:
- MITRE ATT&CK (700+ techniques)
- NVD CVEs (IoT-related)
- arXiv Papers (IoT security research)

NO synthetic data - ensures research integrity.
"""

import asyncio
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Mock chromadb before imports
sys.modules['chromadb'] = MagicMock()
sys.modules['chromadb.config'] = MagicMock()

from src.rag.adapters.academic_adapter import (
    AcademicPaper,
    AcademicPaperAdapter,
    AcademicSource,
    ArxivClient,
    Author,
    SemanticScholarClient,
)
from src.rag.adapters.threat_intel_adapter import (
    AttackTactic,
    CVEEntry,
    MitreAttackClient,
    MitreAttackTechnique,
    NVDClient,
    ThreatIntelAdapter,
    ThreatSource,
)


class TestMitreAttackIntegration:
    """Test MITRE ATT&CK real data integration."""

    @pytest.fixture
    def mitre_client(self, tmp_path):
        """Create MITRE client with temp cache."""
        return MitreAttackClient(cache_dir=tmp_path / "mitre")

    @pytest.mark.asyncio
    async def test_load_attack_data_real(self, mitre_client):
        """Test loading real MITRE ATT&CK data."""
        count = await mitre_client.load_attack_data(use_cache=False)

        # Should have 600+ techniques (real ATT&CK has ~700)
        assert count >= 600, f"Expected 600+ techniques, got {count}"

        # Verify technique structure
        techniques = mitre_client.get_all_techniques()
        assert len(techniques) >= 600

        # Check technique has required fields
        tech = techniques[0]
        assert tech.technique_id
        assert tech.name
        assert tech.description

    @pytest.mark.asyncio
    async def test_iot_relevant_techniques(self, mitre_client):
        """Test finding IoT-relevant techniques."""
        await mitre_client.load_attack_data(use_cache=True)

        # Search for IoT-related keywords
        iot_keywords = ["network", "credential", "exploit", "firmware"]
        iot_techniques = []

        for tech in mitre_client.get_all_techniques():
            text = f"{tech.name} {tech.description}".lower()
            if any(kw in text for kw in iot_keywords):
                iot_techniques.append(tech)

        # Should find many IoT-relevant techniques
        assert len(iot_techniques) >= 50

    @pytest.mark.asyncio
    async def test_technique_search(self, mitre_client):
        """Test technique keyword search."""
        await mitre_client.load_attack_data(use_cache=True)

        # Search for "phishing"
        results = mitre_client.search_techniques("phishing", limit=10)
        assert len(results) > 0
        assert any("phishing" in t.name.lower() or "phishing" in t.description.lower()
                   for t in results)

    @pytest.mark.asyncio
    async def test_techniques_by_tactic(self, mitre_client):
        """Test getting techniques by tactic."""
        await mitre_client.load_attack_data(use_cache=True)

        # Get Initial Access techniques
        initial_access_techs = mitre_client.get_techniques_by_tactic(
            AttackTactic.INITIAL_ACCESS
        )

        assert len(initial_access_techs) >= 5
        for tech in initial_access_techs:
            assert AttackTactic.INITIAL_ACCESS in tech.tactics


class TestArxivIntegration:
    """Test arXiv real data integration."""

    @pytest.fixture
    def arxiv_client(self):
        """Create arXiv client."""
        return ArxivClient()

    @pytest.mark.asyncio
    async def test_search_iot_security_papers(self, arxiv_client):
        """Test searching for IoT security papers."""
        papers = await arxiv_client.search(
            query="IoT security vulnerability",
            limit=10,
            categories=["cs.CR"],  # Cryptography and Security
        )

        # Should find relevant papers
        assert len(papers) > 0

        for paper in papers:
            assert paper.title
            assert paper.abstract
            assert paper.arxiv_id

    @pytest.mark.asyncio
    async def test_paper_metadata(self, arxiv_client):
        """Test paper metadata extraction."""
        papers = await arxiv_client.search("smart home security", limit=5)

        for paper in papers:
            # Check paper structure
            assert isinstance(paper, AcademicPaper)
            assert paper.paper_id.startswith("arxiv:")
            assert paper.source == AcademicSource.ARXIV

            # Authors should be parsed
            assert isinstance(paper.authors, list)

            # Keywords (categories) should be present
            assert isinstance(paper.keywords, list)

    @pytest.mark.asyncio
    async def test_document_conversion(self, arxiv_client):
        """Test converting paper to knowledge document format."""
        papers = await arxiv_client.search("network intrusion detection", limit=1)

        if papers:
            paper = papers[0]
            doc = paper.to_document()

            assert "content" in doc
            assert "metadata" in doc
            assert "title" in doc["metadata"]
            assert doc["metadata"]["source"] == "arxiv"


class TestNVDIntegration:
    """Test NVD CVE real data integration."""

    @pytest.fixture
    def nvd_client(self):
        """Create NVD client (no API key)."""
        return NVDClient()

    @pytest.mark.asyncio
    async def test_search_iot_cves(self, nvd_client):
        """Test searching for IoT-related CVEs."""
        # Search for smart home CVEs
        cves = await nvd_client.search_cves(
            keyword="smart home",
            results_per_page=10,
        )

        # May or may not find results depending on API availability
        assert isinstance(cves, list)

        for cve in cves:
            assert isinstance(cve, CVEEntry)
            assert cve.cve_id.startswith("CVE-")
            assert cve.description

    @pytest.mark.asyncio
    async def test_cve_severity_parsing(self, nvd_client):
        """Test CVE severity information parsing."""
        cves = await nvd_client.search_cves(
            keyword="IoT",
            results_per_page=5,
        )

        for cve in cves:
            # Severity should be parsed when available
            if cve.cvss_v3_score:
                assert 0 <= cve.cvss_v3_score <= 10
                assert cve.severity in ["CRITICAL", "HIGH", "MEDIUM", "LOW", ""]

    @pytest.mark.asyncio
    async def test_cve_document_conversion(self, nvd_client):
        """Test converting CVE to knowledge document format."""
        cves = await nvd_client.search_cves(keyword="router", results_per_page=1)

        if cves:
            cve = cves[0]
            doc = cve.to_document()

            assert "content" in doc
            assert "metadata" in doc
            assert doc["metadata"]["source"] == "nvd"
            assert cve.cve_id in doc["content"]


class TestThreatIntelAdapter:
    """Test unified threat intelligence adapter."""

    @pytest.fixture
    def threat_adapter(self, tmp_path):
        """Create threat intel adapter."""
        return ThreatIntelAdapter(cache_dir=tmp_path / "threat_intel")

    @pytest.mark.asyncio
    async def test_initialize_loads_mitre(self, threat_adapter):
        """Test that initialize loads MITRE data."""
        await threat_adapter.initialize()

        stats = threat_adapter.get_stats()
        assert stats["mitre_techniques_loaded"] >= 600

    @pytest.mark.asyncio
    async def test_get_iot_techniques(self, threat_adapter):
        """Test getting IoT-relevant techniques."""
        await threat_adapter.initialize()

        iot_techniques = threat_adapter.get_iot_related_techniques()
        assert len(iot_techniques) >= 30

    @pytest.mark.asyncio
    async def test_search_threats(self, threat_adapter):
        """Test searching across threat sources."""
        await threat_adapter.initialize()

        results = await threat_adapter.search_threats(
            query="credential",
            sources=[ThreatSource.MITRE_ATTACK],
            limit_per_source=5,
        )

        assert ThreatSource.MITRE_ATTACK in results
        assert len(results[ThreatSource.MITRE_ATTACK]) > 0


class TestAcademicPaperAdapter:
    """Test unified academic paper adapter."""

    @pytest.fixture
    def academic_adapter(self):
        """Create academic paper adapter."""
        return AcademicPaperAdapter()

    @pytest.mark.asyncio
    async def test_search_multiple_sources(self, academic_adapter):
        """Test searching across sources."""
        papers = await academic_adapter.search(
            query="smart home attack",
            sources=[AcademicSource.ARXIV],
            limit_per_source=5,
        )

        assert len(papers) > 0
        assert all(isinstance(p, AcademicPaper) for p in papers)

    @pytest.mark.asyncio
    async def test_paper_caching(self, academic_adapter):
        """Test that papers are cached."""
        papers = await academic_adapter.search(
            query="IoT botnet",
            sources=[AcademicSource.ARXIV],
            limit_per_source=3,
        )

        for paper in papers:
            cached = academic_adapter.get_paper(paper.paper_id)
            assert cached is not None
            assert cached.title == paper.title


class TestScalePerformance:
    """Test RAG performance at scale."""

    @pytest.fixture
    def mitre_client(self, tmp_path):
        """Create MITRE client."""
        return MitreAttackClient(cache_dir=tmp_path / "mitre")

    @pytest.mark.asyncio
    async def test_bulk_document_generation(self, mitre_client):
        """Test generating 700+ documents from MITRE."""
        await mitre_client.load_attack_data(use_cache=True)

        techniques = mitre_client.get_all_techniques()
        documents = []

        for tech in techniques:
            doc = tech.to_document()
            documents.append(doc)

        # Should generate 600+ documents
        assert len(documents) >= 600

        # Verify document structure
        for doc in documents[:10]:
            assert "content" in doc
            assert "metadata" in doc
            assert len(doc["content"]) > 100

    @pytest.mark.asyncio
    async def test_technique_lookup_performance(self, mitre_client):
        """Test technique lookup is fast."""
        import time

        await mitre_client.load_attack_data(use_cache=True)

        # Time 100 lookups
        start = time.time()
        for i in range(100):
            mitre_client.search_techniques("credential", limit=5)
        elapsed = time.time() - start

        # Should complete in under 1 second
        assert elapsed < 1.0, f"100 searches took {elapsed:.2f}s"


class TestDataIntegrity:
    """Test data integrity and provenance."""

    @pytest.fixture
    def mitre_client(self, tmp_path):
        """Create MITRE client."""
        return MitreAttackClient(cache_dir=tmp_path / "mitre")

    @pytest.mark.asyncio
    async def test_technique_ids_valid(self, mitre_client):
        """Test all technique IDs follow MITRE format."""
        await mitre_client.load_attack_data(use_cache=True)

        for tech in mitre_client.get_all_techniques():
            # Format: T#### or T####.###
            assert tech.technique_id.startswith("T")
            parts = tech.technique_id[1:].split(".")
            assert parts[0].isdigit()

    @pytest.mark.asyncio
    async def test_no_empty_descriptions(self, mitre_client):
        """Test no techniques have empty descriptions."""
        await mitre_client.load_attack_data(use_cache=True)

        for tech in mitre_client.get_all_techniques():
            assert tech.description, f"Empty description for {tech.technique_id}"
            assert len(tech.description) >= 50

    @pytest.mark.asyncio
    async def test_technique_has_tactics(self, mitre_client):
        """Test most techniques have tactics assigned."""
        await mitre_client.load_attack_data(use_cache=True)

        with_tactics = 0
        total = 0

        for tech in mitre_client.get_all_techniques():
            total += 1
            if tech.tactics:
                with_tactics += 1

        # At least 80% should have tactics
        ratio = with_tactics / total
        assert ratio >= 0.8, f"Only {ratio*100:.1f}% have tactics"


# Run tests if executed directly
if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
