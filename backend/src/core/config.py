"""
Smart-HES Agent Configuration Module

Centralized configuration management using Pydantic Settings.
Supports environment variables and .env files.
"""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


# Get the project root (parent of backend folder)
_BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
_PROJECT_ROOT = _BACKEND_DIR.parent
_SMART_HOME_ROOT = _PROJECT_ROOT.parent  # smart_home/ directory (parent of simulator)

# Load .env file into os.environ so provider registry can access API keys
# This is needed because pydantic-settings loads into Settings object but not os.environ
_ENV_FILE = _BACKEND_DIR / ".env"
if _ENV_FILE.exists():
    from dotenv import load_dotenv
    load_dotenv(_ENV_FILE, override=True)


class Settings(BaseSettings):
    """Application settings with environment variable support."""

    model_config = SettingsConfigDict(
        env_file=_ENV_FILE,  # Use absolute path to ensure correct .env is read
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ===========================================================================
    # Application Settings
    # ===========================================================================
    app_name: str = "Smart-HES Agent"
    app_version: str = "0.1.0"
    debug: bool = False
    environment: Literal["development", "staging", "production"] = "development"

    # ===========================================================================
    # Server Settings
    # ===========================================================================
    host: str = "127.0.0.1"
    port: int = 8000
    reload: bool = True
    workers: int = 1

    # ===========================================================================
    # LLM Settings
    # ===========================================================================
    # Active LLM provider: "ollama" (local, default), "openai" (cloud)
    # Ollama requires no API key (zero-config local setup)
    # OpenAI requires OPENAI_API_KEY environment variable
    llm_provider: str = "ollama"  # Active provider

    # Ollama settings (local inference - default)
    ollama_host: str = "http://localhost:11434"
    ollama_model: str = "llama3.1:8b-instruct-q4_K_M"

    # OpenAI settings (cloud inference - requires OPENAI_API_KEY env var)
    # API key is read from OPENAI_API_KEY environment variable (not stored here)
    openai_model: str = "gpt-4o"
    openai_base_url: str = ""  # Optional: for Azure OpenAI or proxies

    # Gemini settings (cloud inference - requires GEMINI_API_KEY env var)
    # API key is read from GEMINI_API_KEY environment variable (not stored here)
    gemini_model: str = "gemini-2.0-flash"

    # Common LLM settings
    llm_timeout: int = 120  # seconds (increased for RAG+LLM operations)
    llm_max_tokens: int = 2048
    llm_temperature: float = 0.7

    # ===========================================================================
    # RAG Settings (ChromaDB)
    # ===========================================================================
    # Use absolute path to prevent working directory issues
    # Previously: "./chroma_data" caused multiple database locations
    chroma_persist_directory: Path = Field(default=_BACKEND_DIR / "chroma_data")
    chroma_collection_name: str = "smart_hes_knowledge"
    # Embedding model configuration
    # Options: "all-MiniLM-L6-v2" (384D, fast), "gte-large" (1024D, high quality)
    embedding_model: str = "gte-large"
    # Local models path - all models stored within project directory
    # Structure: models/embeddings/<model-name>/
    shared_models_path: Path = Field(default=_PROJECT_ROOT / "models")
    rag_top_k: int = 5
    rag_similarity_threshold: float = 0.25  # Tuned for GTE model with L2 distance

    # Hybrid Search Configuration
    # search_mode options: "semantic_only", "keyword_only", "hybrid", "auto"
    search_mode: str = "hybrid"
    hybrid_semantic_weight: float = 0.7  # Weight for dense/semantic search (0-1)
    hybrid_keyword_weight: float = 0.3   # Weight for BM25/keyword search (0-1)
    # fusion_method options: "rrf" (Reciprocal Rank Fusion), "weighted", "max", "interleave"
    hybrid_fusion_method: str = "rrf"

    # ===========================================================================
    # Text Chunking Settings (for RAG document processing)
    # ===========================================================================
    chunk_size: int = 512  # Maximum tokens per chunk
    chunk_overlap: int = 50  # Overlap between chunks for context continuity

    # ===========================================================================
    # Anti-Hallucination Settings (CRITICAL for Research Integrity)
    # ===========================================================================
    verification_enabled: bool = True
    confidence_threshold_pass: float = 0.85  # Auto-approve if >= this
    confidence_threshold_flag: float = 0.70  # Flag for review if >= this
    strict_verification_mode: bool = False  # Require human approval for ALL outputs
    require_source_citation: bool = True
    max_hallucination_tolerance: float = 0.0  # Zero tolerance

    # ===========================================================================
    # Simulation Settings
    # ===========================================================================
    simulation_time_compression: int = 1440  # 24 hours in 1 minute
    max_devices: int = 100
    max_rooms: int = 20
    default_simulation_duration_hours: int = 24

    # ===========================================================================
    # Paths (absolute paths derived from project structure)
    # ===========================================================================
    knowledge_base_path: Path = Field(default=_PROJECT_ROOT / "knowledge_base")
    exports_path: Path = Field(default=_PROJECT_ROOT / "exports")
    configs_path: Path = Field(default=_PROJECT_ROOT / "configs")
    logs_path: Path = Field(default=_BACKEND_DIR / "logs")

    # ===========================================================================
    # Logging
    # ===========================================================================
    log_level: str = "INFO"
    log_format: str = "json"  # "json" or "console"

    # ===========================================================================
    # CORS Settings
    # ===========================================================================
    cors_origins: list[str] = ["http://localhost:5173", "http://localhost:3000"]
    cors_allow_credentials: bool = True
    cors_allow_methods: list[str] = ["*"]
    cors_allow_headers: list[str] = ["*"]


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


def reload_settings() -> Settings:
    """
    Reload settings from .env file.

    Call this after updating .env to get fresh values.
    Returns the new settings instance.
    """
    # Reload .env into os.environ
    from dotenv import load_dotenv
    load_dotenv(_ENV_FILE, override=True)

    # Clear the lru_cache
    get_settings.cache_clear()

    # Get fresh settings
    global settings
    settings = get_settings()
    return settings


# Export settings instance for convenience
settings = get_settings()
