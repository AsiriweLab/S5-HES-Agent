#!/usr/bin/env python3
"""
RAG Knowledge Base Organization and Ingestion Script

This script:
1. Organizes papers from the flat papers/ directory into category folders
2. Runs ingestion for each category
3. Validates the ingestion

Usage:
    cd s5-hes-agent/backend
    python -m knowledge_base.scripts.organize_and_ingest --organize
    python -m knowledge_base.scripts.organize_and_ingest --ingest
    python -m knowledge_base.scripts.organize_and_ingest --validate
"""

import shutil
import yaml
from pathlib import Path
from typing import Optional
import argparse
import sys

# Add backend to path for imports
SCRIPT_DIR = Path(__file__).resolve().parent
KB_DIR = SCRIPT_DIR.parent
BACKEND_DIR = KB_DIR.parent / "backend"
sys.path.insert(0, str(BACKEND_DIR / "src"))

# File mappings based on manifest analysis
# Format: (filename_pattern, target_category, target_subfolder)
FILE_MAPPINGS = {
    # === HIGH PRIORITY: Baseline Datasets ===
    "T-001_N_BaIoT": ("academic", "datasets"),
    "T-003_TON_IoT": ("academic", "datasets"),
    "T-005_Bot_IoT": ("academic", "datasets"),
    "T-006_UNSW_NB15": ("academic", "datasets"),
    "T008_SDHAR_HOME": ("academic", "datasets"),
    "T011_IoT_Building": ("academic", "datasets"),
    "sensors-22-08109": ("academic", "datasets"),
    "S2352340924001379": ("academic", "datasets"),  # Energy dataset

    # === HIGH PRIORITY: Mirai/Botnet Analysis ===
    "sec17-antonakakis": ("threat_intel", "botnets"),
    "An_In-Depth_Analysis_of_the_Mirai": ("threat_intel", "botnets"),
    "2508.01909": ("threat_intel", "botnets"),
    "2020-Choo-IoT-botnet-forensics": ("threat_intel", "botnets"),
    "evolution-of-Mirai-botnet": ("threat_intel", "botnets"),
    "DetectingBotnetsbyModelingtheirNetworkBehaviors": ("threat_intel", "botnets"),
    "ransomware": ("threat_intel", "botnets"),
    "malware": ("threat_intel", "botnets"),

    # === HIGH PRIORITY: Security Surveys ===
    "Smart_Home_IoT_Cybersecurity_Survey": ("academic", "surveys"),
    "IoT  of Smart Homes  Privacy and": ("academic", "surveys"),
    "electronics-13-03601": ("academic", "surveys"),
    "Morshedi": ("academic", "surveys"),  # Deep learning anomaly detection
    "s13677-018-0123-6": ("academic", "surveys"),
    "s40507-025-00414-6": ("academic", "surveys"),
    "2111.04418": ("academic", "surveys"),  # HAR survey
    "survey-on-intrusion-detection": ("academic", "surveys"),
    "Survey-of-deep-learning": ("academic", "surveys"),
    "survey-on-security-in-internet-of-things": ("academic", "surveys"),
    "IoT-anomaly-detection-methods-and-applications": ("academic", "surveys"),

    # === MEDIUM PRIORITY: Methods ===
    "2412.20574": ("academic", "methods"),  # Time series distance
    "s41598-025-29331-5": ("academic", "methods"),  # DTW
    "S2352711023002236": ("academic", "methods"),  # SimilarityTS
    "2406.10928": ("academic", "methods"),  # Smart home anomaly
    "behavioural-hierarchical-analysis": ("academic", "methods"),
    "3317549.3323413": ("academic", "methods"),  # Hestia network
    "3708282.3708283": ("academic", "methods"),
    "3725899.3725918": ("academic", "methods"),

    # === IDS Methods ===
    "intrusion-detection": ("academic", "methods"),
    "Federated-learning": ("academic", "methods"),
    "ensemble": ("academic", "methods"),

    # === DDoS/Network ===
    "DDoS": ("academic", "methods"),
    "DoS-attack": ("academic", "methods"),

    # === IoT Security ===
    "Securing-IoT": ("academic", "methods"),
    "Privacy-preserving": ("academic", "methods"),
}


def get_target_path(filename: str) -> Optional[tuple[str, str]]:
    """Determine target category and subfolder for a file."""
    for pattern, (category, subfolder) in FILE_MAPPINGS.items():
        if pattern.lower() in filename.lower():
            return (category, subfolder)
    return None


def organize_files(dry_run: bool = True):
    """
    Organize files from papers/ into category folders.

    Args:
        dry_run: If True, only print what would be done without copying
    """
    papers_dir = KB_DIR / "papers"
    if not papers_dir.exists():
        print(f"ERROR: papers directory not found: {papers_dir}")
        return

    # Track statistics
    stats = {
        "copied": 0,
        "skipped": 0,
        "unmapped": 0,
    }
    unmapped_files = []

    # Process PDFs in papers/ (not in subdirectories like baselines/ or www.stratosphereips.org/)
    for pdf_file in papers_dir.glob("*.pdf"):
        target = get_target_path(pdf_file.name)

        if target is None:
            stats["unmapped"] += 1
            unmapped_files.append(pdf_file.name)
            continue

        category, subfolder = target
        target_dir = KB_DIR / category / subfolder
        target_path = target_dir / pdf_file.name

        if target_path.exists():
            if not dry_run:
                print(f"  SKIP (exists): {pdf_file.name}")
            stats["skipped"] += 1
            continue

        if dry_run:
            print(f"  COPY: {pdf_file.name} -> {category}/{subfolder}/")
        else:
            target_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(pdf_file, target_path)
            print(f"  COPIED: {pdf_file.name} -> {category}/{subfolder}/")

        stats["copied"] += 1

    # Process baselines separately
    baselines_dir = papers_dir / "baselines"
    if baselines_dir.exists():
        for pdf_file in baselines_dir.glob("*.pdf"):
            target_dir = KB_DIR / "academic" / "datasets"
            target_path = target_dir / pdf_file.name

            if target_path.exists():
                stats["skipped"] += 1
                continue

            if dry_run:
                print(f"  COPY: baselines/{pdf_file.name} -> academic/datasets/")
            else:
                target_dir.mkdir(parents=True, exist_ok=True)
                shutil.copy2(pdf_file, target_path)
                print(f"  COPIED: baselines/{pdf_file.name} -> academic/datasets/")

            stats["copied"] += 1

    # Process ScienceDirect folders (Cyber Security and Applications, etc.)
    for sd_dir in papers_dir.glob("ScienceDirect_*"):
        if sd_dir.is_dir():
            for pdf_file in sd_dir.rglob("*.pdf"):
                target = get_target_path(pdf_file.name)

                if target is None:
                    # Default: categorize based on content type from filename
                    if any(kw in pdf_file.name.lower() for kw in ["survey", "review", "comprehensive"]):
                        target = ("academic", "surveys")
                    elif any(kw in pdf_file.name.lower() for kw in ["malware", "ransomware", "botnet", "attack"]):
                        target = ("threat_intel", "botnets")
                    elif any(kw in pdf_file.name.lower() for kw in ["detection", "intrusion", "ids"]):
                        target = ("academic", "methods")
                    else:
                        # Default to methods for uncategorized security papers
                        target = ("academic", "methods")

                category, subfolder = target
                target_dir = KB_DIR / category / subfolder
                target_path = target_dir / pdf_file.name

                if target_path.exists():
                    stats["skipped"] += 1
                    continue

                if dry_run:
                    print(f"  COPY: {sd_dir.name}/{pdf_file.name[:50]}... -> {category}/{subfolder}/")
                else:
                    target_dir.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(pdf_file, target_path)
                    print(f"  COPIED: {pdf_file.name} -> {category}/{subfolder}/")

                stats["copied"] += 1

    # Print summary
    print("\n" + "=" * 60)
    print("ORGANIZATION SUMMARY")
    print("=" * 60)
    print(f"Files to copy:  {stats['copied']}")
    print(f"Already exist:  {stats['skipped']}")
    print(f"Unmapped:       {stats['unmapped']}")

    if unmapped_files and len(unmapped_files) <= 20:
        print("\nUnmapped files (need manual categorization):")
        for f in unmapped_files:
            print(f"  - {f}")
    elif unmapped_files:
        print(f"\nUnmapped files: {len(unmapped_files)} (too many to list)")

    if dry_run:
        print("\n[DRY RUN - no files were copied. Use --execute to copy files]")


def ingest_category(category: str, subfolder: Optional[str] = None):
    """
    Ingest documents from a category folder.

    Requires backend to be running or imports to work.
    """
    try:
        from src.ai.rag import get_knowledge_service
        import asyncio
    except ImportError:
        print("ERROR: Cannot import RAG service. Make sure you're running from backend/")
        print("Usage: cd backend && python -m knowledge_base.scripts.organize_and_ingest --ingest")
        return

    if subfolder:
        ingest_path = KB_DIR / category / subfolder
    else:
        ingest_path = KB_DIR / category

    if not ingest_path.exists():
        print(f"ERROR: Path does not exist: {ingest_path}")
        return

    print(f"\nIngesting: {ingest_path}")

    async def run_ingest():
        ks = get_knowledge_service()
        result = await ks.ingest_directory(str(ingest_path))
        return result

    result = asyncio.run(run_ingest())
    print(f"Ingested {result.get('documents_processed', 0)} documents")
    print(f"Created {result.get('chunks_created', 0)} chunks")


def validate_ingestion():
    """
    Validate ingestion by running test queries.
    """
    try:
        from src.ai.rag import get_knowledge_service
        import asyncio
    except ImportError:
        print("ERROR: Cannot import RAG service.")
        return

    test_queries = [
        ("What is the Mirai botnet?", "threat_intel"),
        ("SDHAR-HOME dataset", "academic"),
        ("IoT intrusion detection survey", "academic"),
        ("N-BaIoT dataset", "academic"),
    ]

    async def run_validation():
        ks = get_knowledge_service()

        print("\n" + "=" * 60)
        print("VALIDATION QUERIES")
        print("=" * 60)

        for query, expected_category in test_queries:
            print(f"\nQuery: {query}")
            print(f"Expected category: {expected_category}")

            results = await ks.search(query, top_k=3)

            if not results:
                print("  NO RESULTS")
                continue

            for i, result in enumerate(results[:3]):
                source = result.get("metadata", {}).get("source", "Unknown")
                category = result.get("metadata", {}).get("category", "Unknown")
                score = result.get("score", 0)
                print(f"  {i+1}. [{category}] {source[:50]}... (score: {score:.3f})")

    asyncio.run(run_validation())


def main():
    parser = argparse.ArgumentParser(
        description="Organize and ingest knowledge base documents"
    )
    parser.add_argument(
        "--organize", action="store_true",
        help="Organize files into category folders (dry run)"
    )
    parser.add_argument(
        "--execute", action="store_true",
        help="Actually execute file organization (use with --organize)"
    )
    parser.add_argument(
        "--ingest", type=str, nargs="?", const="all",
        help="Ingest documents. Optionally specify category (e.g., 'academic/datasets')"
    )
    parser.add_argument(
        "--validate", action="store_true",
        help="Run validation queries"
    )

    args = parser.parse_args()

    if args.organize:
        organize_files(dry_run=not args.execute)

    if args.ingest:
        if args.ingest == "all":
            # Ingest in order of priority
            for cat_sub in [
                ("academic", "datasets"),
                ("academic", "surveys"),
                ("threat_intel", "botnets"),
                ("academic", "methods"),
            ]:
                ingest_category(*cat_sub)
        else:
            parts = args.ingest.split("/")
            if len(parts) == 2:
                ingest_category(parts[0], parts[1])
            else:
                ingest_category(parts[0])

    if args.validate:
        validate_ingestion()

    if not any([args.organize, args.ingest, args.validate]):
        parser.print_help()


if __name__ == "__main__":
    main()
