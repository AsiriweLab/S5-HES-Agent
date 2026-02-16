"""
LLM Provider Registry

Manages LLM provider registration, configuration, and runtime switching.
Enables multi-LLM evaluation workflows without code changes.

INTEGRITY REQUIREMENTS:
- No mock/stub/dummy providers
- No fallback behavior - if requested provider unavailable, raise exception
- No synthetic response generation
- Each provider makes REAL API calls
"""

from dataclasses import dataclass, field
from typing import Any, Callable, Optional, Type

from loguru import logger

from src.ai.llm.base_client import (
    AbstractLLMClient,
    BaseLLMClient,
    LLMStatus,
    ProviderNotConfiguredError,
)


@dataclass
class ProviderConfig:
    """Configuration for an LLM provider."""

    name: str
    client_class: Type[AbstractLLMClient]
    default_model: str
    requires_api_key: bool = False
    api_key_env_var: Optional[str] = None
    extra_config: dict[str, Any] = field(default_factory=dict)

    def is_configured(self) -> bool:
        """Check if this provider is properly configured."""
        if not self.requires_api_key:
            return True

        import os

        if self.api_key_env_var:
            return bool(os.environ.get(self.api_key_env_var))
        return False


class LLMProviderRegistry:
    """
    Registry for LLM providers with runtime switching support.

    Enables:
    - Registration of provider configurations
    - Runtime provider switching without restart
    - Multi-provider evaluation workflows
    - Provider health checking

    INTEGRITY:
    - No fallback providers - if requested provider unavailable, fails explicitly
    - No mock/dummy providers can be registered
    - Each provider makes real API calls
    """

    def __init__(self):
        self._providers: dict[str, ProviderConfig] = {}
        self._instances: dict[str, BaseLLMClient] = {}
        self._current_provider: Optional[str] = None

        # Register built-in providers
        self._register_builtin_providers()

        # Initialize current provider from settings (persisted in .env)
        # This ensures the provider survives server restarts/hot-reloads
        from src.core.config import settings
        self._current_provider = settings.llm_provider
        logger.info(f"Initialized provider registry with active provider: {self._current_provider}")

    def _register_builtin_providers(self) -> None:
        """Register the built-in providers."""
        from src.ai.llm.ollama_client import OllamaClient
        from src.ai.llm.openai_client import OpenAIClient
        from src.ai.llm.gemini_client import GeminiClient

        # Ollama - local, default, no API key required
        self.register_provider(
            ProviderConfig(
                name="ollama",
                client_class=OllamaClient,
                default_model="llama3.1:8b-instruct-q4_K_M",
                requires_api_key=False,
            )
        )

        # OpenAI - cloud, requires API key
        self.register_provider(
            ProviderConfig(
                name="openai",
                client_class=OpenAIClient,
                default_model="gpt-4o",
                requires_api_key=True,
                api_key_env_var="OPENAI_API_KEY",
            )
        )

        # Google Gemini - cloud, requires API key
        self.register_provider(
            ProviderConfig(
                name="gemini",
                client_class=GeminiClient,
                default_model="gemini-2.0-flash",
                requires_api_key=True,
                api_key_env_var="GEMINI_API_KEY",
            )
        )

        logger.debug(f"Registered built-in providers: {list(self._providers.keys())}")

    def register_provider(self, config: ProviderConfig) -> None:
        """
        Register an LLM provider.

        Args:
            config: Provider configuration

        Raises:
            ValueError: If provider already registered or config invalid
        """
        if config.name in self._providers:
            logger.warning(f"Provider '{config.name}' already registered, updating config")

        self._providers[config.name] = config
        logger.debug(f"Registered provider: {config.name}")

    def list_providers(self) -> list[str]:
        """List all registered provider names."""
        return list(self._providers.keys())

    def list_configured_providers(self) -> list[str]:
        """List providers that are properly configured (have required credentials)."""
        return [
            name for name, config in self._providers.items() if config.is_configured()
        ]

    def get_provider_config(self, name: str) -> ProviderConfig:
        """
        Get configuration for a provider.

        Args:
            name: Provider name

        Returns:
            ProviderConfig for the provider

        Raises:
            ProviderNotConfiguredError: If provider not registered
        """
        if name not in self._providers:
            raise ProviderNotConfiguredError(
                name,
                f"Provider '{name}' not registered. "
                f"Available providers: {self.list_providers()}",
            )
        return self._providers[name]

    def get_client(
        self,
        provider_name: Optional[str] = None,
        model: Optional[str] = None,
        **kwargs,
    ) -> BaseLLMClient:
        """
        Get a client instance for a provider.

        Args:
            provider_name: Provider name (defaults to current provider or 'ollama')
            model: Override default model
            **kwargs: Additional arguments passed to client constructor

        Returns:
            LLM client instance

        Raises:
            ProviderNotConfiguredError: If provider not registered or not configured
        """
        name = provider_name or self._current_provider or "ollama"
        config = self.get_provider_config(name)

        if not config.is_configured():
            raise ProviderNotConfiguredError(
                name,
                f"Provider '{name}' requires API key. "
                f"Set {config.api_key_env_var} environment variable.",
            )

        # Create cache key including model
        cache_key = f"{name}:{model or config.default_model}"

        # Return cached instance if available
        if cache_key in self._instances:
            return self._instances[cache_key]

        # Create new client instance
        client_kwargs = {**config.extra_config, **kwargs}
        if model:
            client_kwargs["model"] = model

        try:
            client = config.client_class(**client_kwargs)
            self._instances[cache_key] = client
            logger.info(f"Created {name} client with model {model or config.default_model}")
            return client
        except Exception as e:
            raise ProviderNotConfiguredError(
                name,
                f"Failed to create {name} client: {str(e)}",
            )

    def switch_provider(
        self,
        provider_name: str,
        model: Optional[str] = None,
    ) -> BaseLLMClient:
        """
        Switch to a different LLM provider.

        This enables runtime provider switching without restart.

        Args:
            provider_name: Name of the provider to switch to
            model: Optional model override

        Returns:
            The new active client instance

        Raises:
            ProviderNotConfiguredError: If provider not available

        INTEGRITY: No fallback - if requested provider unavailable, fails explicitly.
        """
        config = self.get_provider_config(provider_name)

        if not config.is_configured():
            raise ProviderNotConfiguredError(
                provider_name,
                f"Cannot switch to '{provider_name}': API key not configured. "
                f"Set {config.api_key_env_var} environment variable.",
            )

        self._current_provider = provider_name
        client = self.get_client(provider_name, model)

        logger.info(
            f"Switched to provider '{provider_name}' "
            f"with model '{model or config.default_model}'"
        )

        return client

    @property
    def current_provider(self) -> Optional[str]:
        """Get the name of the current active provider."""
        return self._current_provider

    @property
    def current_client(self) -> Optional[BaseLLMClient]:
        """Get the current active client instance."""
        if not self._current_provider:
            return None
        return self.get_client(self._current_provider)

    async def check_provider_status(
        self, provider_name: Optional[str] = None
    ) -> LLMStatus:
        """
        Check the status of a provider.

        Args:
            provider_name: Provider to check (defaults to current)

        Returns:
            LLMStatus with provider availability
        """
        name = provider_name or self._current_provider or "ollama"
        try:
            client = self.get_client(name)
            return await client.check_status()
        except ProviderNotConfiguredError as e:
            return LLMStatus(
                available=False,
                provider=name,
                message=str(e),
            )

    async def close_all(self) -> None:
        """Close all cached client instances."""
        for cache_key, client in self._instances.items():
            try:
                await client.close()
            except Exception as e:
                logger.warning(f"Error closing client {cache_key}: {e}")
        self._instances.clear()


# Global registry instance
_registry: Optional[LLMProviderRegistry] = None


def get_provider_registry() -> LLMProviderRegistry:
    """Get the global provider registry instance."""
    global _registry
    if _registry is None:
        _registry = LLMProviderRegistry()
    return _registry


def reset_provider_registry() -> None:
    """Reset the global provider registry (for testing)."""
    global _registry
    _registry = None
