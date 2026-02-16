#!/usr/bin/env python3
"""
Model Download Script

Downloads and saves embedding models to the local project directory.
This ensures all models are stored within the project for portability
and reproducibility.

Usage:
    python download_models.py --model gte-large
    python download_models.py --model all-MiniLM-L6-v2
    python download_models.py --list  # Show available models
"""

import argparse
import sys
from pathlib import Path

# Add backend to path
SCRIPT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = SCRIPT_DIR.parent
PROJECT_ROOT = BACKEND_DIR.parent
sys.path.insert(0, str(BACKEND_DIR / "src"))

from sentence_transformers import SentenceTransformer
from loguru import logger


# Available models with their HuggingFace identifiers
AVAILABLE_MODELS = {
    # Small/Fast models
    "all-MiniLM-L6-v2": {
        "hf_name": "sentence-transformers/all-MiniLM-L6-v2",
        "dimensions": 384,
        "description": "Small, fast model for general use",
        "size_mb": 90,
    },
    # Large/Quality models
    "gte-large": {
        "hf_name": "thenlper/gte-large",
        "dimensions": 1024,
        "description": "High-quality embeddings, best for retrieval",
        "size_mb": 1340,
    },
    "e5-large": {
        "hf_name": "intfloat/e5-large-v2",
        "dimensions": 1024,
        "description": "Strong performance on benchmarks",
        "size_mb": 1340,
    },
    "bge-large": {
        "hf_name": "BAAI/bge-large-en-v1.5",
        "dimensions": 1024,
        "description": "BAAI General Embeddings, multilingual",
        "size_mb": 1340,
    },
}


def get_models_dir() -> Path:
    """Get the local models directory."""
    return PROJECT_ROOT / "models" / "embeddings"


def list_models():
    """List available models and their status."""
    models_dir = get_models_dir()

    print("\n" + "=" * 70)
    print("AVAILABLE EMBEDDING MODELS")
    print("=" * 70)

    for name, info in AVAILABLE_MODELS.items():
        local_path = models_dir / name
        status = "INSTALLED" if local_path.exists() else "NOT INSTALLED"

        print(f"\n{name}")
        print(f"  HuggingFace: {info['hf_name']}")
        print(f"  Dimensions:  {info['dimensions']}")
        print(f"  Size:        ~{info['size_mb']} MB")
        print(f"  Description: {info['description']}")
        print(f"  Status:      {status}")
        if local_path.exists():
            print(f"  Local Path:  {local_path}")

    print("\n" + "=" * 70)


def download_model(model_name: str, force: bool = False) -> bool:
    """
    Download and save a model to the local directory.

    Args:
        model_name: Short name of the model (e.g., "gte-large")
        force: If True, re-download even if exists

    Returns:
        True if successful, False otherwise
    """
    if model_name not in AVAILABLE_MODELS:
        logger.error(f"Unknown model: {model_name}")
        logger.info(f"Available models: {list(AVAILABLE_MODELS.keys())}")
        return False

    model_info = AVAILABLE_MODELS[model_name]
    models_dir = get_models_dir()
    local_path = models_dir / model_name

    # Check if already exists
    if local_path.exists() and not force:
        logger.info(f"Model already exists at: {local_path}")
        logger.info("Use --force to re-download")
        return True

    # Create directory
    models_dir.mkdir(parents=True, exist_ok=True)

    logger.info("=" * 70)
    logger.info(f"DOWNLOADING MODEL: {model_name}")
    logger.info("=" * 70)
    logger.info(f"HuggingFace ID: {model_info['hf_name']}")
    logger.info(f"Expected size: ~{model_info['size_mb']} MB")
    logger.info(f"Target path:   {local_path}")
    logger.info("")
    logger.info("This may take several minutes depending on your connection...")
    logger.info("")

    try:
        # Download from HuggingFace
        logger.info("Downloading from HuggingFace Hub...")
        model = SentenceTransformer(model_info["hf_name"])

        # Save to local directory
        logger.info(f"Saving to local directory: {local_path}")
        model.save(str(local_path))

        # Verify the saved model
        logger.info("Verifying saved model...")
        loaded_model = SentenceTransformer(str(local_path))

        # Test embedding
        test_text = "This is a test sentence for embedding verification."
        embedding = loaded_model.encode(test_text)

        actual_dim = len(embedding)
        expected_dim = model_info["dimensions"]

        if actual_dim != expected_dim:
            logger.warning(f"Dimension mismatch: expected {expected_dim}, got {actual_dim}")

        logger.info("=" * 70)
        logger.info("MODEL DOWNLOAD COMPLETE")
        logger.info("=" * 70)
        logger.info(f"Model:      {model_name}")
        logger.info(f"Dimensions: {actual_dim}")
        logger.info(f"Location:   {local_path}")
        logger.info("")
        logger.info("The model is now available for use in the project.")
        logger.info("=" * 70)

        return True

    except Exception as e:
        logger.error(f"Failed to download model: {e}")
        logger.exception("Full traceback:")
        return False


def verify_model(model_name: str) -> bool:
    """
    Verify a locally installed model works correctly.

    Args:
        model_name: Short name of the model

    Returns:
        True if model works, False otherwise
    """
    models_dir = get_models_dir()
    local_path = models_dir / model_name

    if not local_path.exists():
        logger.error(f"Model not found at: {local_path}")
        return False

    logger.info(f"Verifying model: {model_name}")

    try:
        model = SentenceTransformer(str(local_path))

        # Test with sample texts
        test_texts = [
            "Smart home automation system",
            "IoT security vulnerability",
            "Turn on the living room lights",
        ]

        embeddings = model.encode(test_texts)

        logger.info(f"Model loaded successfully")
        logger.info(f"Embedding dimension: {embeddings.shape[1]}")
        logger.info(f"Test embeddings shape: {embeddings.shape}")

        return True

    except Exception as e:
        logger.error(f"Model verification failed: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Download and manage embedding models for S5-HES Agent"
    )
    parser.add_argument(
        "--model",
        type=str,
        help="Model name to download (e.g., gte-large)",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List available models and their status",
    )
    parser.add_argument(
        "--verify",
        type=str,
        help="Verify a locally installed model",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force re-download even if model exists",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Download all available models",
    )

    args = parser.parse_args()

    if args.list:
        list_models()
        return

    if args.verify:
        success = verify_model(args.verify)
        sys.exit(0 if success else 1)

    if args.all:
        logger.info("Downloading all available models...")
        for model_name in AVAILABLE_MODELS:
            success = download_model(model_name, force=args.force)
            if not success:
                logger.error(f"Failed to download {model_name}")
        return

    if args.model:
        success = download_model(args.model, force=args.force)
        sys.exit(0 if success else 1)

    # No arguments - show help
    parser.print_help()


if __name__ == "__main__":
    main()
