"""
Real Data Ingestion Script for Smart-HES Knowledge Base.

Ingests REAL open-access data from:
- MITRE ATT&CK (STIX format, ~700+ techniques)
- NVD CVEs (IoT-related vulnerabilities)
- arXiv Papers (IoT security research)
- Semantic Scholar (Academic papers)

NO synthetic data - ensures research integrity and avoids hallucination/fallback issues.
"""

import asyncio
import sys
from pathlib import Path
from datetime import datetime

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from loguru import logger

from src.rag.adapters.academic_adapter import (
    AcademicPaperAdapter,
    AcademicSource,
    CrossRefClient,
    OpenAlexClient,
    COREClient,
    get_academic_adapter,
)
from src.rag.adapters.threat_intel_adapter import (
    ThreatIntelAdapter,
    ThreatSource,
    get_threat_intel_adapter,
)
from src.rag.knowledge_base import (
    KnowledgeBaseService,
    KnowledgeDocument,
    get_knowledge_base,
)


# IoT Security Search Queries for arXiv and Semantic Scholar
IOT_SECURITY_QUERIES = [
    "IoT security vulnerabilities smart home",
    "smart home device attacks",
    "IoT botnet malware analysis",
    "Zigbee Z-Wave security protocol",
    "smart thermostat security",
    "IP camera vulnerability exploitation",
    "MQTT protocol security IoT",
    "firmware analysis embedded systems",
    "wireless sensor network attacks",
    "home automation security",
    "smart lock vulnerabilities",
    "voice assistant security privacy",
    "edge computing IoT security",
    "machine learning IoT intrusion detection",
    "blockchain IoT security",
]

# NVD CVE search keywords for IoT
IOT_CVE_KEYWORDS = [
    "smart home",
    "IoT",
    "router",
    "IP camera",
    "thermostat",
    "smart lock",
    "Z-Wave",
    "Zigbee",
    "Matter protocol",
    "home assistant",
]


async def ingest_mitre_attack(
    threat_adapter: ThreatIntelAdapter,
    kb_service: KnowledgeBaseService,
) -> int:
    """
    Ingest MITRE ATT&CK techniques.

    Downloads from official MITRE STIX repository (~700+ techniques).
    This is authoritative, real data maintained by MITRE.
    """
    logger.info("=== Ingesting MITRE ATT&CK Data ===")

    # Initialize loads the ATT&CK data
    await threat_adapter.initialize()

    # Get all techniques
    all_techniques = threat_adapter.mitre.get_all_techniques()
    logger.info(f"Loaded {len(all_techniques)} MITRE ATT&CK techniques")

    # Get IoT-relevant subset for focused indexing
    iot_techniques = threat_adapter.get_iot_related_techniques()
    logger.info(f"Found {len(iot_techniques)} IoT-relevant techniques")

    # Convert to knowledge documents
    docs = []
    for technique in all_techniques:
        doc_data = technique.to_document()
        doc = KnowledgeDocument(
            title=doc_data["metadata"]["title"],
            content=doc_data["content"],
            category="threat_intel",
            source=f"MITRE ATT&CK: {technique.technique_id}",
            tags=[
                "mitre",
                "attack",
                technique.technique_id,
                *[t.value for t in technique.tactics],
            ],
        )
        docs.append(doc)

    # Batch add to knowledge base
    if docs:
        kb_service.add_documents(docs)
        logger.info(f"Indexed {len(docs)} MITRE ATT&CK techniques")

    return len(docs)


async def ingest_nvd_cves(
    threat_adapter: ThreatIntelAdapter,
    kb_service: KnowledgeBaseService,
    max_per_keyword: int = 20,
) -> int:
    """
    Ingest IoT-related CVEs from NVD.

    Uses the official NIST NVD API (free, no key required for basic usage).
    """
    logger.info("=== Ingesting NVD CVE Data ===")

    all_cves = []
    seen_ids = set()

    for keyword in IOT_CVE_KEYWORDS:
        logger.info(f"Searching NVD for: {keyword}")
        try:
            cves = await threat_adapter.nvd.search_cves(
                keyword=keyword,
                results_per_page=max_per_keyword,
            )

            for cve in cves:
                if cve.cve_id not in seen_ids:
                    seen_ids.add(cve.cve_id)
                    all_cves.append(cve)

            logger.info(f"  Found {len(cves)} CVEs for '{keyword}'")

            # Rate limiting - NVD has rate limits
            await asyncio.sleep(1.0)

        except Exception as e:
            logger.warning(f"Failed to fetch CVEs for '{keyword}': {e}")
            continue

    logger.info(f"Total unique CVEs: {len(all_cves)}")

    # Convert to knowledge documents
    docs = []
    for cve in all_cves:
        doc_data = cve.to_document()
        doc = KnowledgeDocument(
            title=cve.cve_id,
            content=doc_data["content"],
            category="threat_intel",
            source=f"NVD: {cve.cve_id}",
            tags=[
                "cve",
                "vulnerability",
                cve.severity.lower() if cve.severity else "unknown",
                *cve.cwe_ids,
            ],
        )
        docs.append(doc)

    # Batch add to knowledge base
    if docs:
        kb_service.add_documents(docs)
        logger.info(f"Indexed {len(docs)} CVEs")

    return len(docs)


async def ingest_arxiv_papers(
    academic_adapter: AcademicPaperAdapter,
    kb_service: KnowledgeBaseService,
    papers_per_query: int = 10,
) -> int:
    """
    Ingest IoT security papers from arXiv.

    arXiv is a free, open-access repository of scientific papers.
    No API key required.
    """
    logger.info("=== Ingesting arXiv Papers ===")

    all_papers = []
    seen_ids = set()

    for query in IOT_SECURITY_QUERIES:
        logger.info(f"Searching arXiv for: {query}")
        try:
            papers = await academic_adapter.arxiv.search(
                query=query,
                limit=papers_per_query,
                categories=["cs.CR", "cs.NI", "cs.DC"],  # Security, Networks, Distributed
            )

            for paper in papers:
                if paper.paper_id not in seen_ids:
                    seen_ids.add(paper.paper_id)
                    all_papers.append(paper)

            logger.info(f"  Found {len(papers)} papers for '{query}'")

            # arXiv rate limiting
            await asyncio.sleep(0.5)

        except Exception as e:
            logger.warning(f"Failed to fetch arXiv papers for '{query}': {e}")
            continue

    logger.info(f"Total unique arXiv papers: {len(all_papers)}")

    # Convert to knowledge documents
    docs = []
    for paper in all_papers:
        doc_data = paper.to_document()
        doc = KnowledgeDocument(
            title=paper.title,
            content=doc_data["content"],
            category="academic",
            source=f"arXiv: {paper.arxiv_id or paper.paper_id}",
            tags=[
                "arxiv",
                "academic",
                "research",
                *paper.keywords[:5],
            ],
        )
        docs.append(doc)

    # Batch add to knowledge base
    if docs:
        kb_service.add_documents(docs)
        logger.info(f"Indexed {len(docs)} arXiv papers")

    return len(docs)


async def ingest_semantic_scholar_papers(
    academic_adapter: AcademicPaperAdapter,
    kb_service: KnowledgeBaseService,
    papers_per_query: int = 10,
) -> int:
    """
    Ingest IoT security papers from Semantic Scholar.

    Semantic Scholar provides free API access (rate limited).
    No API key required for basic usage.
    """
    logger.info("=== Ingesting Semantic Scholar Papers ===")

    all_papers = []
    seen_ids = set()

    for query in IOT_SECURITY_QUERIES:
        logger.info(f"Searching Semantic Scholar for: {query}")
        try:
            papers = await academic_adapter.semantic_scholar.search(
                query=query,
                limit=papers_per_query,
                fields_of_study=["Computer Science"],
            )

            for paper in papers:
                if paper.paper_id not in seen_ids:
                    seen_ids.add(paper.paper_id)
                    all_papers.append(paper)

            logger.info(f"  Found {len(papers)} papers for '{query}'")

            # Semantic Scholar rate limiting (100 requests/5 minutes without key)
            await asyncio.sleep(3.0)

        except Exception as e:
            logger.warning(f"Failed to fetch papers for '{query}': {e}")
            continue

    logger.info(f"Total unique Semantic Scholar papers: {len(all_papers)}")

    # Convert to knowledge documents
    docs = []
    for paper in all_papers:
        doc_data = paper.to_document()
        doc = KnowledgeDocument(
            title=paper.title,
            content=doc_data["content"],
            category="academic",
            source=f"Semantic Scholar: {paper.paper_id}",
            tags=[
                "semantic_scholar",
                "academic",
                "research",
                str(paper.year) if paper.year else "unknown",
            ],
        )
        docs.append(doc)

    # Batch add to knowledge base
    if docs:
        kb_service.add_documents(docs)
        logger.info(f"Indexed {len(docs)} Semantic Scholar papers")

    return len(docs)


async def ingest_openalex_papers(
    academic_adapter: AcademicPaperAdapter,
    kb_service: KnowledgeBaseService,
    papers_per_query: int = 15,
) -> int:
    """
    Ingest IoT security papers from OpenAlex.

    OpenAlex is a free, open catalog with 250M+ works.
    No API key required (email for polite pool recommended).
    """
    logger.info("=== Ingesting OpenAlex Papers ===")

    all_papers = []
    seen_ids = set()

    for query in IOT_SECURITY_QUERIES:
        logger.info(f"Searching OpenAlex for: {query}")
        try:
            papers = await academic_adapter.openalex.search(
                query=query,
                limit=papers_per_query,
                from_year=2015,  # Focus on recent research
            )

            for paper in papers:
                if paper.paper_id not in seen_ids:
                    seen_ids.add(paper.paper_id)
                    all_papers.append(paper)

            logger.info(f"  Found {len(papers)} papers for '{query}'")

            # OpenAlex is generous but be polite
            await asyncio.sleep(0.5)

        except Exception as e:
            logger.warning(f"Failed to fetch OpenAlex papers for '{query}': {e}")
            continue

    logger.info(f"Total unique OpenAlex papers: {len(all_papers)}")

    # Convert to knowledge documents
    docs = []
    for paper in all_papers:
        doc_data = paper.to_document()
        source_name = paper.source.value.replace("_", " ").title()
        doc = KnowledgeDocument(
            title=paper.title,
            content=doc_data["content"],
            category="academic",
            source=f"{source_name}: {paper.doi or paper.paper_id}",
            tags=[
                "openalex",
                paper.source.value,
                "academic",
                "research",
                str(paper.year) if paper.year else "unknown",
            ],
        )
        docs.append(doc)

    # Batch add to knowledge base
    if docs:
        kb_service.add_documents(docs)
        logger.info(f"Indexed {len(docs)} OpenAlex papers")

    return len(docs)


async def ingest_crossref_papers(
    academic_adapter: AcademicPaperAdapter,
    kb_service: KnowledgeBaseService,
    papers_per_query: int = 10,
) -> int:
    """
    Ingest IoT security papers from CrossRef.

    CrossRef aggregates metadata from major publishers:
    Springer, Elsevier, Nature, IEEE, ACM, Wiley, Taylor & Francis, etc.
    Free API, no key required.
    """
    logger.info("=== Ingesting CrossRef Papers (Springer, Elsevier, Nature, etc.) ===")

    all_papers = []
    seen_dois = set()

    # Search specific publishers for higher quality results
    publishers = ["Springer", "Elsevier", "IEEE", "ACM", "Wiley"]

    for publisher in publishers:
        for query in IOT_SECURITY_QUERIES[:8]:  # Use subset for each publisher
            logger.info(f"Searching CrossRef ({publisher}) for: {query}")
            try:
                papers = await academic_adapter.crossref.search(
                    query=query,
                    limit=papers_per_query,
                    publisher=publisher,
                    from_year=2015,
                )

                for paper in papers:
                    if paper.doi and paper.doi not in seen_dois:
                        seen_dois.add(paper.doi)
                        all_papers.append(paper)

                logger.info(f"  Found {len(papers)} papers from {publisher}")

                # CrossRef rate limiting
                await asyncio.sleep(1.0)

            except Exception as e:
                logger.warning(f"Failed to fetch CrossRef papers from {publisher}: {e}")
                continue

    logger.info(f"Total unique CrossRef papers: {len(all_papers)}")

    # Convert to knowledge documents
    docs = []
    for paper in all_papers:
        doc_data = paper.to_document()
        source_name = paper.source.value.replace("_", " ").title()
        doc = KnowledgeDocument(
            title=paper.title,
            content=doc_data["content"],
            category="academic",
            source=f"{source_name}: {paper.doi}",
            tags=[
                "crossref",
                paper.source.value,
                "academic",
                "peer_reviewed",
                str(paper.year) if paper.year else "unknown",
            ],
        )
        docs.append(doc)

    # Batch add to knowledge base
    if docs:
        kb_service.add_documents(docs)
        logger.info(f"Indexed {len(docs)} CrossRef papers")

    return len(docs)


async def ingest_core_papers(
    academic_adapter: AcademicPaperAdapter,
    kb_service: KnowledgeBaseService,
    papers_per_query: int = 10,
) -> int:
    """
    Ingest open access papers from CORE.

    CORE is the world's largest collection of open access research.
    Free API, optional API key for higher rate limits.
    """
    logger.info("=== Ingesting CORE Open Access Papers ===")

    all_papers = []
    seen_ids = set()

    for query in IOT_SECURITY_QUERIES:
        logger.info(f"Searching CORE for: {query}")
        try:
            papers = await academic_adapter.core.search(
                query=query,
                limit=papers_per_query,
                from_year=2015,
            )

            for paper in papers:
                if paper.paper_id not in seen_ids:
                    seen_ids.add(paper.paper_id)
                    all_papers.append(paper)

            logger.info(f"  Found {len(papers)} papers for '{query}'")

            # CORE rate limiting
            await asyncio.sleep(1.5)

        except Exception as e:
            logger.warning(f"Failed to fetch CORE papers for '{query}': {e}")
            continue

    logger.info(f"Total unique CORE papers: {len(all_papers)}")

    # Convert to knowledge documents
    docs = []
    for paper in all_papers:
        doc_data = paper.to_document()
        doc = KnowledgeDocument(
            title=paper.title,
            content=doc_data["content"],
            category="academic",
            source=f"CORE: {paper.doi or paper.paper_id}",
            tags=[
                "core",
                "open_access",
                "academic",
                "research",
                str(paper.year) if paper.year else "unknown",
            ],
        )
        docs.append(doc)

    # Batch add to knowledge base
    if docs:
        kb_service.add_documents(docs)
        logger.info(f"Indexed {len(docs)} CORE papers")

    return len(docs)


async def run_full_ingestion(
    skip_mitre: bool = False,
    skip_nvd: bool = False,
    skip_arxiv: bool = False,
    skip_semantic_scholar: bool = False,
    skip_openalex: bool = False,
    skip_crossref: bool = False,
    skip_core: bool = False,
) -> dict:
    """
    Run full data ingestion from all real sources.

    Args:
        skip_mitre: Skip MITRE ATT&CK ingestion
        skip_nvd: Skip NVD CVE ingestion
        skip_arxiv: Skip arXiv paper ingestion
        skip_semantic_scholar: Skip Semantic Scholar ingestion
        skip_openalex: Skip OpenAlex ingestion
        skip_crossref: Skip CrossRef (Springer, Elsevier, IEEE, etc.) ingestion
        skip_core: Skip CORE open access ingestion

    Returns:
        Statistics dict with ingestion counts
    """
    logger.info("=" * 60)
    logger.info("REAL DATA INGESTION - Smart-HES Knowledge Base")
    logger.info("Extended Publisher Support: Springer, Elsevier, Nature, IEEE, ACM, Wiley")
    logger.info(f"Started at: {datetime.now().isoformat()}")
    logger.info("=" * 60)

    # Initialize services
    kb_service = get_knowledge_base()
    threat_adapter = get_threat_intel_adapter()
    academic_adapter = get_academic_adapter()

    stats = {
        "mitre_techniques": 0,
        "nvd_cves": 0,
        "arxiv_papers": 0,
        "semantic_scholar_papers": 0,
        "openalex_papers": 0,
        "crossref_papers": 0,
        "core_papers": 0,
        "total_documents": 0,
        "started_at": datetime.now().isoformat(),
        "completed_at": None,
    }

    try:
        # 1. MITRE ATT&CK (~700+ techniques)
        if not skip_mitre:
            stats["mitre_techniques"] = await ingest_mitre_attack(
                threat_adapter, kb_service
            )

        # 2. NVD CVEs (~100-200 IoT-related)
        if not skip_nvd:
            stats["nvd_cves"] = await ingest_nvd_cves(
                threat_adapter, kb_service
            )

        # 3. arXiv Papers (~100-150 IoT security preprints)
        if not skip_arxiv:
            stats["arxiv_papers"] = await ingest_arxiv_papers(
                academic_adapter, kb_service
            )

        # 4. Semantic Scholar (~100-150 papers)
        if not skip_semantic_scholar:
            stats["semantic_scholar_papers"] = await ingest_semantic_scholar_papers(
                academic_adapter, kb_service
            )

        # 5. OpenAlex (~150-200 papers from all publishers)
        if not skip_openalex:
            stats["openalex_papers"] = await ingest_openalex_papers(
                academic_adapter, kb_service
            )

        # 6. CrossRef (Springer, Elsevier, IEEE, ACM, Wiley - ~200-300 papers)
        if not skip_crossref:
            stats["crossref_papers"] = await ingest_crossref_papers(
                academic_adapter, kb_service
            )

        # 7. CORE Open Access (~100-150 papers)
        if not skip_core:
            stats["core_papers"] = await ingest_core_papers(
                academic_adapter, kb_service
            )

        stats["total_documents"] = (
            stats["mitre_techniques"] +
            stats["nvd_cves"] +
            stats["arxiv_papers"] +
            stats["semantic_scholar_papers"] +
            stats["openalex_papers"] +
            stats["crossref_papers"] +
            stats["core_papers"]
        )
        stats["completed_at"] = datetime.now().isoformat()

        # Final stats
        logger.info("=" * 60)
        logger.info("INGESTION COMPLETE")
        logger.info(f"MITRE ATT&CK Techniques: {stats['mitre_techniques']}")
        logger.info(f"NVD CVEs: {stats['nvd_cves']}")
        logger.info(f"arXiv Papers: {stats['arxiv_papers']}")
        logger.info(f"Semantic Scholar Papers: {stats['semantic_scholar_papers']}")
        logger.info(f"OpenAlex Papers: {stats['openalex_papers']}")
        logger.info(f"CrossRef Papers (Springer/Elsevier/IEEE/etc.): {stats['crossref_papers']}")
        logger.info(f"CORE Open Access Papers: {stats['core_papers']}")
        logger.info(f"TOTAL DOCUMENTS: {stats['total_documents']}")
        logger.info("=" * 60)

        # Verify knowledge base
        kb_stats = kb_service.get_stats()
        logger.info(f"Knowledge Base Stats: {kb_stats}")

    except Exception as e:
        logger.error(f"Ingestion failed: {e}")
        stats["error"] = str(e)

    return stats


async def quick_test_ingestion() -> dict:
    """
    Quick test with minimal data for verification.
    """
    logger.info("Running quick test ingestion...")

    kb_service = get_knowledge_base()
    threat_adapter = get_threat_intel_adapter()
    academic_adapter = get_academic_adapter()

    stats = {"mitre": 0, "arxiv": 0, "nvd": 0}

    # Test MITRE (downloads once, then uses cache)
    await threat_adapter.initialize()
    techniques = threat_adapter.mitre.get_all_techniques()[:10]
    for tech in techniques:
        doc_data = tech.to_document()
        doc = KnowledgeDocument(
            title=doc_data["metadata"]["title"],
            content=doc_data["content"],
            category="threat_intel",
            source=f"MITRE: {tech.technique_id}",
            tags=["mitre", "test"],
        )
        kb_service.add_document(doc)
        stats["mitre"] += 1

    # Test arXiv (1 query)
    papers = await academic_adapter.arxiv.search("IoT security", limit=5)
    for paper in papers:
        doc_data = paper.to_document()
        doc = KnowledgeDocument(
            title=paper.title,
            content=doc_data["content"],
            category="academic",
            source=f"arXiv: {paper.arxiv_id}",
            tags=["arxiv", "test"],
        )
        kb_service.add_document(doc)
        stats["arxiv"] += 1

    logger.info(f"Quick test stats: {stats}")
    return stats


# CLI interface
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Ingest real data into Smart-HES knowledge base")
    parser.add_argument("--quick", action="store_true", help="Run quick test with minimal data")
    parser.add_argument("--skip-mitre", action="store_true", help="Skip MITRE ATT&CK ingestion")
    parser.add_argument("--skip-nvd", action="store_true", help="Skip NVD CVE ingestion")
    parser.add_argument("--skip-arxiv", action="store_true", help="Skip arXiv ingestion")
    parser.add_argument("--skip-semantic-scholar", action="store_true", help="Skip Semantic Scholar")
    parser.add_argument("--skip-openalex", action="store_true", help="Skip OpenAlex ingestion")
    parser.add_argument("--skip-crossref", action="store_true", help="Skip CrossRef (Springer/Elsevier/IEEE/etc.)")
    parser.add_argument("--skip-core", action="store_true", help="Skip CORE open access")
    parser.add_argument("--academic-only", action="store_true", help="Only ingest academic papers (skip MITRE/NVD)")

    args = parser.parse_args()

    if args.quick:
        asyncio.run(quick_test_ingestion())
    elif args.academic_only:
        asyncio.run(run_full_ingestion(
            skip_mitre=True,
            skip_nvd=True,
            skip_arxiv=args.skip_arxiv,
            skip_semantic_scholar=args.skip_semantic_scholar,
            skip_openalex=args.skip_openalex,
            skip_crossref=args.skip_crossref,
            skip_core=args.skip_core,
        ))
    else:
        asyncio.run(run_full_ingestion(
            skip_mitre=args.skip_mitre,
            skip_nvd=args.skip_nvd,
            skip_arxiv=args.skip_arxiv,
            skip_semantic_scholar=args.skip_semantic_scholar,
            skip_openalex=args.skip_openalex,
            skip_crossref=args.skip_crossref,
            skip_core=args.skip_core,
        ))
