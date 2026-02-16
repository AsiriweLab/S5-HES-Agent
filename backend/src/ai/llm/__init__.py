"""
LLM Engine - Multi-provider LLM integration with RAG and verification.

Supports multiple LLM providers:
- Ollama (local, default - no API key required)
- OpenAI (cloud - requires OPENAI_API_KEY)

Runtime provider switching enabled via LLMEngine.switch_provider().
"""

# Base client protocol and types
from src.ai.llm.base_client import (
    AbstractLLMClient,
    BaseLLMClient,
    LLMResponse,
    LLMStatus,
    ProviderConnectionError,
    ProviderNotConfiguredError,
)

# Provider registry
from src.ai.llm.provider_registry import (
    LLMProviderRegistry,
    ProviderConfig,
    get_provider_registry,
    reset_provider_registry,
)

# Ollama Client (backward compatibility + direct access)
from src.ai.llm.ollama_client import (
    OllamaClient,
    check_ollama_health,
    get_ollama_client,
)

# OpenAI Client
from src.ai.llm.openai_client import OpenAIClient

# Gemini Client
from src.ai.llm.gemini_client import GeminiClient

# LLM Engine (high-level interface)
from src.ai.llm.llm_engine import (
    InferenceResult,
    LLMEngine,
    Message,
    ResponseConfidence,
    get_llm_engine,
    initialize_llm_engine,
    reset_llm_engine,
)

# Prompts
from src.ai.llm.prompts import (
    PromptManager,
    get_prompt_manager,
)

# Backward compatibility alias
OllamaStatus = LLMStatus

__all__ = [
    # Base types
    "AbstractLLMClient",
    "BaseLLMClient",
    "LLMResponse",
    "LLMStatus",
    "ProviderConnectionError",
    "ProviderNotConfiguredError",
    # Provider registry
    "LLMProviderRegistry",
    "ProviderConfig",
    "get_provider_registry",
    "reset_provider_registry",
    # Ollama Client
    "OllamaClient",
    "OllamaStatus",  # Backward compatibility alias for LLMStatus
    "check_ollama_health",
    "get_ollama_client",
    # OpenAI Client
    "OpenAIClient",
    # Gemini Client
    "GeminiClient",
    # LLM Engine
    "InferenceResult",
    "LLMEngine",
    "Message",
    "ResponseConfidence",
    "get_llm_engine",
    "initialize_llm_engine",
    "reset_llm_engine",
    # Prompts
    "PromptManager",
    "get_prompt_manager",
]
