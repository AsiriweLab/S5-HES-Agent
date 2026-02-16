"""
Base LLM Client Protocol

Defines the interface that all LLM provider clients must implement.
This enables runtime provider switching without code changes.

Supported providers:
- Ollama (local, default - no API key required)
- OpenAI (cloud, requires OPENAI_API_KEY)
- Future: Gemini, Anthropic, etc.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import AsyncGenerator, Optional, Protocol, runtime_checkable


@dataclass
class LLMResponse:
    """
    Unified response from any LLM provider.

    All provider clients must return this format.
    """

    content: str
    model: str
    provider: str  # "ollama", "openai", etc.
    total_duration_ms: Optional[float] = None
    prompt_eval_count: Optional[int] = None
    eval_count: Optional[int] = None
    confidence: float = 0.0  # For anti-hallucination tracking


@dataclass
class LLMStatus:
    """
    Status of LLM provider connection.

    All provider clients must return this format from check_status().
    """

    available: bool
    provider: str
    message: str
    models: list[str] = field(default_factory=list)
    current_model: Optional[str] = None


class ProviderNotConfiguredError(Exception):
    """
    Raised when a provider is requested but not configured.

    INTEGRITY: This is a hard failure - no fallback to other providers.
    """

    def __init__(self, provider: str, reason: str):
        self.provider = provider
        self.reason = reason
        super().__init__(f"Provider '{provider}' not configured: {reason}")


class ProviderConnectionError(Exception):
    """
    Raised when a provider is configured but connection fails.

    INTEGRITY: This is a hard failure - no fallback to other providers.
    """

    def __init__(self, provider: str, reason: str):
        self.provider = provider
        self.reason = reason
        super().__init__(f"Provider '{provider}' connection failed: {reason}")


@runtime_checkable
class BaseLLMClient(Protocol):
    """
    Protocol defining the interface for all LLM provider clients.

    INTEGRITY REQUIREMENTS:
    - Each client makes REAL API calls to its provider
    - No mock/stub/dummy implementations
    - No fallback behavior - if provider fails, raise exception
    - No synthetic response generation
    """

    @property
    def provider_name(self) -> str:
        """Return the provider name (e.g., 'ollama', 'openai')."""
        ...

    @property
    def model_name(self) -> str:
        """Return the current model name."""
        ...

    async def check_status(self) -> LLMStatus:
        """
        Check if the provider is available and configured.

        Returns:
            LLMStatus with provider availability and model information

        INTEGRITY: Must return real status, not fabricated availability.
        """
        ...

    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> LLMResponse:
        """
        Generate a response from the LLM.

        Args:
            prompt: User prompt
            system_prompt: Optional system prompt
            temperature: Sampling temperature (0.0-1.0)
            max_tokens: Maximum tokens to generate

        Returns:
            LLMResponse with content and metadata

        Raises:
            ProviderConnectionError: If provider is unreachable
            ProviderNotConfiguredError: If provider is not properly configured

        INTEGRITY: Must return real LLM output, no synthetic/mock responses.
        """
        ...

    async def generate_stream(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> AsyncGenerator[str, None]:
        """
        Generate a streaming response from the LLM.

        Args:
            prompt: User prompt
            system_prompt: Optional system prompt
            temperature: Sampling temperature (0.0-1.0)
            max_tokens: Maximum tokens to generate

        Yields:
            String chunks of the response

        Raises:
            ProviderConnectionError: If provider is unreachable
            ProviderNotConfiguredError: If provider is not properly configured

        INTEGRITY: Must yield real LLM output, no synthetic/mock chunks.
        """
        ...

    async def close(self) -> None:
        """Close any open connections."""
        ...


class AbstractLLMClient(ABC):
    """
    Abstract base class for LLM clients.

    Provides common functionality and enforces the protocol.
    Subclass this for concrete provider implementations.
    """

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Return the provider name."""
        pass

    @property
    @abstractmethod
    def model_name(self) -> str:
        """Return the current model name."""
        pass

    @abstractmethod
    async def check_status(self) -> LLMStatus:
        """Check provider availability."""
        pass

    @abstractmethod
    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> LLMResponse:
        """Generate a response."""
        pass

    @abstractmethod
    async def generate_stream(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> AsyncGenerator[str, None]:
        """Generate a streaming response."""
        pass

    async def close(self) -> None:
        """Close connections. Override if needed."""
        pass
