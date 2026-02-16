#!/usr/bin/env python3
"""
Embedding Migration Script

Migrates ChromaDB from one embedding model to another.
Handles dimension changes by exporting documents, re-embedding, and re-ingesting.

This script is designed for research integrity - it creates backups,
validates results, and provides detailed logging.

Usage:
    # Dry run (export only, no changes)
    python migrate_embeddings.py --dry-run

    # Execute migration
    python migrate_embeddings.py --execute

    # Rollback to backup
    python migrate_embeddings.py --rollback <backup_name>

    # Validate current state
    python migrate_embeddings.py --validate
"""

import argparse
import json
import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple

# Add backend to path
SCRIPT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = SCRIPT_DIR.parent
PROJECT_ROOT = BACKEND_DIR.parent
sys.path.insert(0, str(BACKEND_DIR / "src"))

import chromadb
from loguru import logger
from tqdm import tqdm

from core.config import settings


class MigrationError(Exception):
    """Raised when migration fails."""
    pass


class EmbeddingMigration:
    """
    Handles migration of ChromaDB embeddings between models.

    This class provides:
    - Safe backup before any changes
    - Document export with full metadata
    - Re-embedding with new model
    - Validation of migrated data
    - Rollback capability
    """

    def __init__(self):
        self.chroma_path = settings.chroma_persist_directory
        self.collection_name = settings.chroma_collection_name
        self.model_name = settings.embedding_model
        self.models_path = settings.shared_models_path

        # Backup directory
        self.backups_path = PROJECT_ROOT / "chroma_data_backups"
        self.exports_path = PROJECT_ROOT / "migration_exports"

        logger.info(f"Migration configured:")
        logger.info(f"  ChromaDB path: {self.chroma_path}")
        logger.info(f"  Collection: {self.collection_name}")
        logger.info(f"  Target model: {self.model_name}")
        logger.info(f"  Models path: {self.models_path}")

    def get_current_state(self) -> Dict[str, Any]:
        """Get current state of ChromaDB."""
        state = {
            "exists": False,
            "collection_exists": False,
            "document_count": 0,
            "stored_model": None,
            "stored_dimension": None,
        }

        if not self.chroma_path.exists():
            return state

        state["exists"] = True

        try:
            client = chromadb.PersistentClient(path=str(self.chroma_path))
            try:
                collection = client.get_collection(name=self.collection_name)
                state["collection_exists"] = True
                state["document_count"] = collection.count()

                metadata = collection.metadata or {}
                state["stored_model"] = metadata.get("embedding_model", "unknown")
                state["stored_dimension"] = metadata.get("embedding_dimension", "unknown")
            except Exception:
                pass
        except Exception as e:
            logger.warning(f"Could not read ChromaDB state: {e}")

        return state

    def export_documents(self) -> Tuple[List[Dict[str, Any]], Path]:
        """
        Export all documents from ChromaDB.

        Returns:
            Tuple of (documents list, export file path)
        """
        logger.info("Exporting documents from ChromaDB...")

        if not self.chroma_path.exists():
            logger.warning("ChromaDB does not exist")
            return [], None

        client = chromadb.PersistentClient(path=str(self.chroma_path))

        try:
            collection = client.get_collection(name=self.collection_name)
        except Exception as e:
            logger.warning(f"Collection not found: {e}")
            return [], None

        doc_count = collection.count()
        if doc_count == 0:
            logger.info("Collection is empty")
            return [], None

        logger.info(f"Exporting {doc_count} documents...")

        # Get all documents (without embeddings - we'll re-create those)
        results = collection.get(
            include=["documents", "metadatas"]
        )

        documents = []
        for i in range(len(results["ids"])):
            doc = {
                "id": results["ids"][i],
                "content": results["documents"][i] if results["documents"] else "",
                "metadata": results["metadatas"][i] if results["metadatas"] else {},
            }
            documents.append(doc)

        # Save export to file
        self.exports_path.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        export_file = self.exports_path / f"export_{timestamp}.json"

        export_data = {
            "export_timestamp": datetime.now().isoformat(),
            "source_model": collection.metadata.get("embedding_model", "unknown") if collection.metadata else "unknown",
            "source_dimension": collection.metadata.get("embedding_dimension", "unknown") if collection.metadata else "unknown",
            "document_count": len(documents),
            "documents": documents,
        }

        with open(export_file, "w", encoding="utf-8") as f:
            json.dump(export_data, f, indent=2, ensure_ascii=False)

        logger.info(f"Exported {len(documents)} documents to {export_file}")
        return documents, export_file

    def create_backup(self) -> Optional[Path]:
        """
        Create a backup of the current ChromaDB.

        Returns:
            Path to backup directory, or None if nothing to backup
        """
        if not self.chroma_path.exists():
            logger.info("No ChromaDB to backup")
            return None

        self.backups_path.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_dir = self.backups_path / f"backup_{timestamp}"

        logger.info(f"Creating backup at {backup_dir}...")
        shutil.copytree(self.chroma_path, backup_dir)
        logger.info(f"Backup created: {backup_dir}")

        return backup_dir

    def clear_collection(self) -> None:
        """Clear all documents from the collection."""
        logger.warning("Clearing collection...")

        client = chromadb.PersistentClient(path=str(self.chroma_path))

        try:
            collection = client.get_collection(name=self.collection_name)
            all_ids = collection.get()["ids"]

            if all_ids:
                # Delete in batches to avoid issues with large collections
                batch_size = 1000
                for i in range(0, len(all_ids), batch_size):
                    batch = all_ids[i:i + batch_size]
                    collection.delete(ids=batch)
                    logger.info(f"Deleted batch {i // batch_size + 1}")

            logger.info(f"Cleared {len(all_ids)} documents from collection")
        except Exception as e:
            logger.info(f"Collection may not exist or is empty: {e}")

    def reembed_and_ingest(
        self,
        documents: List[Dict[str, Any]],
        batch_size: int = 50,
    ) -> int:
        """
        Re-embed documents with new model and ingest to ChromaDB.

        Args:
            documents: List of documents to ingest
            batch_size: Batch size for embedding (smaller = less memory)

        Returns:
            Number of documents ingested
        """
        if not documents:
            logger.info("No documents to ingest")
            return 0

        logger.info(f"Re-embedding {len(documents)} documents with {self.model_name}...")

        # Import embedding service
        from rag.embeddings.embedding_service import EmbeddingService

        # Initialize embedding service with new model
        embedding_service = EmbeddingService(model_name=self.model_name)
        dimension = embedding_service.embedding_dimension

        logger.info(f"Embedding dimension: {dimension}")

        # Initialize ChromaDB
        client = chromadb.PersistentClient(path=str(self.chroma_path))

        # Delete and recreate collection with new metadata
        try:
            client.delete_collection(name=self.collection_name)
        except Exception:
            pass

        collection = client.create_collection(
            name=self.collection_name,
            metadata={
                "description": "Smart-HES Agent Knowledge Base",
                "embedding_model": self.model_name,
                "embedding_dimension": dimension,
                "migrated_at": datetime.now().isoformat(),
                "hnsw:space": "l2",
            }
        )

        # Process in batches
        total_batches = (len(documents) + batch_size - 1) // batch_size
        ingested = 0

        for batch_idx in tqdm(range(total_batches), desc="Migrating"):
            start = batch_idx * batch_size
            end = min(start + batch_size, len(documents))
            batch = documents[start:end]

            # Extract content
            ids = [doc["id"] for doc in batch]
            contents = [doc["content"] for doc in batch]
            metadatas = [doc["metadata"] for doc in batch]

            # Generate embeddings
            embeddings = embedding_service.embed_texts(contents)

            # Ingest
            collection.add(
                ids=ids,
                documents=contents,
                embeddings=embeddings.tolist(),
                metadatas=metadatas,
            )

            ingested += len(batch)

        logger.info(f"Ingested {ingested} documents")
        return ingested

    def validate_migration(self, expected_count: int) -> Dict[str, Any]:
        """
        Validate that migration was successful.

        Args:
            expected_count: Expected number of documents

        Returns:
            Validation results dict
        """
        logger.info("Validating migration...")

        result = {
            "valid": False,
            "document_count": 0,
            "expected_count": expected_count,
            "model": None,
            "dimension": None,
            "sample_query_ok": False,
            "errors": [],
        }

        try:
            client = chromadb.PersistentClient(path=str(self.chroma_path))
            collection = client.get_collection(name=self.collection_name)

            # Check document count
            actual_count = collection.count()
            result["document_count"] = actual_count

            if actual_count != expected_count:
                result["errors"].append(
                    f"Document count mismatch: expected {expected_count}, got {actual_count}"
                )

            # Check metadata
            metadata = collection.metadata or {}
            result["model"] = metadata.get("embedding_model")
            result["dimension"] = metadata.get("embedding_dimension")

            if result["model"] != self.model_name:
                result["errors"].append(
                    f"Model mismatch: expected {self.model_name}, got {result['model']}"
                )

            # Test sample query
            from rag.embeddings.embedding_service import EmbeddingService
            embedding_service = EmbeddingService(model_name=self.model_name)

            test_query = "smart home automation"
            query_embedding = embedding_service.embed_text(test_query)

            results = collection.query(
                query_embeddings=[query_embedding.tolist()],
                n_results=min(5, actual_count),
            )

            if results["ids"] and results["ids"][0]:
                result["sample_query_ok"] = True
            else:
                result["errors"].append("Sample query returned no results")

            # Final verdict
            result["valid"] = (
                actual_count == expected_count and
                result["model"] == self.model_name and
                result["sample_query_ok"]
            )

        except Exception as e:
            result["errors"].append(f"Validation error: {e}")

        return result

    def rollback(self, backup_name: str) -> bool:
        """
        Rollback to a previous backup.

        Args:
            backup_name: Name of backup directory

        Returns:
            True if rollback successful
        """
        backup_path = self.backups_path / backup_name

        if not backup_path.exists():
            # Try with just the name
            matching = list(self.backups_path.glob(f"*{backup_name}*"))
            if matching:
                backup_path = matching[0]
            else:
                logger.error(f"Backup not found: {backup_name}")
                logger.info(f"Available backups:")
                for b in self.backups_path.iterdir():
                    logger.info(f"  - {b.name}")
                return False

        logger.warning(f"Rolling back to: {backup_path}")

        # Remove current ChromaDB
        if self.chroma_path.exists():
            shutil.rmtree(self.chroma_path)

        # Restore backup
        shutil.copytree(backup_path, self.chroma_path)

        logger.info(f"Rollback complete from {backup_path}")
        return True

    def execute(self, dry_run: bool = True) -> bool:
        """
        Execute the full migration.

        Args:
            dry_run: If True, export only without making changes

        Returns:
            True if successful
        """
        logger.info("=" * 70)
        logger.info("EMBEDDING MIGRATION")
        logger.info("=" * 70)

        # Get current state
        state = self.get_current_state()
        logger.info(f"Current state:")
        logger.info(f"  Documents: {state['document_count']}")
        logger.info(f"  Model: {state['stored_model']}")
        logger.info(f"  Dimension: {state['stored_dimension']}")
        logger.info(f"  Target model: {self.model_name}")
        logger.info(f"  Mode: {'DRY RUN' if dry_run else 'EXECUTE'}")
        logger.info("=" * 70)

        # Step 1: Export documents
        documents, export_file = self.export_documents()

        if not documents:
            logger.info("No documents to migrate - database is empty or missing")
            if not dry_run:
                logger.info("Creating fresh collection with new model...")
                # Just validate the new model works
                from rag.embeddings.embedding_service import EmbeddingService
                es = EmbeddingService(model_name=self.model_name)
                logger.info(f"New model ready: {self.model_name} ({es.embedding_dimension}D)")
            return True

        if dry_run:
            logger.info("")
            logger.info("DRY RUN COMPLETE")
            logger.info(f"Exported {len(documents)} documents to: {export_file}")
            logger.info("")
            logger.info("To execute the migration, run:")
            logger.info("  python migrate_embeddings.py --execute")
            return True

        # Step 2: Create backup
        backup_path = self.create_backup()

        try:
            # Step 3: Clear collection
            self.clear_collection()

            # Step 4: Re-embed and ingest
            ingested = self.reembed_and_ingest(documents)

            # Step 5: Validate
            validation = self.validate_migration(len(documents))

            logger.info("")
            logger.info("=" * 70)
            if validation["valid"]:
                logger.info("MIGRATION SUCCESSFUL")
                logger.info("=" * 70)
                logger.info(f"  Documents migrated: {validation['document_count']}")
                logger.info(f"  New model: {validation['model']}")
                logger.info(f"  New dimension: {validation['dimension']}")
                logger.info(f"  Sample query: OK")
                logger.info(f"  Backup: {backup_path}")
                return True
            else:
                logger.error("MIGRATION VALIDATION FAILED")
                logger.info("=" * 70)
                for error in validation["errors"]:
                    logger.error(f"  {error}")
                logger.warning(f"Backup available at: {backup_path}")
                logger.warning("Consider rolling back with: python migrate_embeddings.py --rollback <backup_name>")
                return False

        except Exception as e:
            logger.error(f"Migration failed: {e}")
            logger.exception("Full traceback:")
            if backup_path:
                logger.warning(f"Backup available at: {backup_path}")
                logger.warning("Rolling back automatically...")
                self.rollback(backup_path.name)
            return False


def main():
    parser = argparse.ArgumentParser(
        description="Migrate ChromaDB embeddings to new model"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Export documents only, don't modify database",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Execute the migration (creates backup first)",
    )
    parser.add_argument(
        "--validate",
        action="store_true",
        help="Validate current database state",
    )
    parser.add_argument(
        "--rollback",
        type=str,
        metavar="BACKUP_NAME",
        help="Rollback to a previous backup",
    )
    parser.add_argument(
        "--list-backups",
        action="store_true",
        help="List available backups",
    )

    args = parser.parse_args()

    migration = EmbeddingMigration()

    if args.list_backups:
        backups_path = PROJECT_ROOT / "chroma_data_backups"
        if backups_path.exists():
            logger.info("Available backups:")
            for b in sorted(backups_path.iterdir(), reverse=True):
                logger.info(f"  {b.name}")
        else:
            logger.info("No backups found")
        return

    if args.rollback:
        success = migration.rollback(args.rollback)
        sys.exit(0 if success else 1)

    if args.validate:
        state = migration.get_current_state()
        logger.info("Current database state:")
        for k, v in state.items():
            logger.info(f"  {k}: {v}")

        # Also run validation
        if state["document_count"] > 0:
            validation = migration.validate_migration(state["document_count"])
            logger.info("")
            logger.info("Validation results:")
            for k, v in validation.items():
                logger.info(f"  {k}: {v}")
        return

    if args.dry_run:
        success = migration.execute(dry_run=True)
        sys.exit(0 if success else 1)

    if args.execute:
        success = migration.execute(dry_run=False)
        sys.exit(0 if success else 1)

    # No arguments - show help
    parser.print_help()


if __name__ == "__main__":
    main()
