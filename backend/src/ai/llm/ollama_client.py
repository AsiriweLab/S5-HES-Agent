"""
Ollama LLM Client

Implements the BaseLLMClient protocol for local Ollama inference.
This is the default provider (zero-config, no API key required).

Ollama must be running locally: `ollama serve`
"""

from typing import AsyncGenerator, Optional

import httpx
from loguru import logger

from src.ai.llm.base_client import (
    AbstractLLMClient,
    LLMResponse,
    LLMStatus,
    ProviderConnectionError,
)
from src.core.config import settings


class OllamaClient(AbstractLLMClient):
    """
    Client wrapper for Ollama API.

    Provides methods for:
    - Connection status checking
    - Model listing and pulling
    - Synchronous and streaming chat completion
    - Response time tracking for performance monitoring

    INTEGRITY: All methods make real API calls to Ollama.
    No mock/stub/dummy implementations.
    """

    def __init__(
        self,
        host: Optional[str] = None,
        model: Optional[str] = None,
        timeout: Optional[int] = None,
    ):
        self._host = host or settings.ollama_host
        self._model = model or settings.ollama_model
        self._timeout = timeout or settings.llm_timeout
        self._client: Optional[httpx.AsyncClient] = None

    @property
    def provider_name(self) -> str:
        """Return the provider name."""
        return "ollama"

    @property
    def model_name(self) -> str:
        """Return the current model name."""
        return self._model

    @property
    def host(self) -> str:
        """Return the Ollama host URL."""
        return self._host

    @property
    def model(self) -> str:
        """Alias for model_name (backward compatibility)."""
        return self._model

    @property
    def timeout(self) -> int:
        """Return the timeout setting."""
        return self._timeout

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create async HTTP client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self._host,
                timeout=httpx.Timeout(self._timeout),
            )
        return self._client

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    async def check_status(self) -> LLMStatus:
        """
        Check if Ollama is running and available.

        Returns:
            LLMStatus with availability and model information
        """
        try:
            client = await self._get_client()
            response = await client.get("/api/tags")

            if response.status_code == 200:
                data = response.json()
                models = [m["name"] for m in data.get("models", [])]
                return LLMStatus(
                    available=True,
                    provider=self.provider_name,
                    message="Ollama is running",
                    models=models,
                    current_model=self._model,
                )
            else:
                return LLMStatus(
                    available=False,
                    provider=self.provider_name,
                    message=f"Ollama returned status {response.status_code}",
                    current_model=self._model,
                )
        except httpx.ConnectError:
            return LLMStatus(
                available=False,
                provider=self.provider_name,
                message=f"Cannot connect to Ollama at {self._host}. Is Ollama running?",
                current_model=self._model,
            )
        except Exception as e:
            return LLMStatus(
                available=False,
                provider=self.provider_name,
                message=f"Error checking Ollama: {str(e)}",
                current_model=self._model,
            )

    async def is_model_available(self, model: Optional[str] = None) -> bool:
        """Check if a specific model is available locally."""
        model = model or self._model
        status = await self.check_status()

        if not status.available:
            return False

        # Check if model (or base model name) is in the list
        model_base = model.split(":")[0]
        for available_model in status.models:
            if model in available_model or model_base in available_model:
                return True
        return False

    async def pull_model(self, model: Optional[str] = None) -> bool:
        """
        Pull a model from Ollama library.

        Args:
            model: Model name to pull (e.g., "llama3.1:8b-instruct-q4_K_M")

        Returns:
            True if successful, False otherwise
        """
        model = model or self._model
        logger.info(f"Pulling model: {model}")

        try:
            client = await self._get_client()
            response = await client.post(
                "/api/pull",
                json={"name": model},
                timeout=httpx.Timeout(600.0),  # 10 minutes for large models
            )

            if response.status_code == 200:
                logger.info(f"Successfully pulled model: {model}")
                return True
            else:
                logger.error(f"Failed to pull model: {response.text}")
                return False
        except Exception as e:
            logger.error(f"Error pulling model: {e}")
            return False

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
            ProviderConnectionError: If Ollama is unreachable
        """
        temperature = temperature if temperature is not None else settings.llm_temperature
        max_tokens = max_tokens if max_tokens is not None else settings.llm_max_tokens

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        try:
            client = await self._get_client()
            response = await client.post(
                "/api/chat",
                json={
                    "model": self._model,
                    "messages": messages,
                    "stream": False,
                    "options": {
                        "temperature": temperature,
                        "num_predict": max_tokens,
                    },
                },
            )

            if response.status_code == 200:
                data = response.json()
                return LLMResponse(
                    content=data["message"]["content"],
                    model=data["model"],
                    provider=self.provider_name,
                    total_duration_ms=data.get("total_duration", 0) / 1_000_000,
                    prompt_eval_count=data.get("prompt_eval_count"),
                    eval_count=data.get("eval_count"),
                )
            else:
                raise ProviderConnectionError(
                    self.provider_name,
                    f"Ollama error: {response.text}",
                )

        except httpx.ConnectError:
            raise ProviderConnectionError(
                self.provider_name,
                f"Cannot connect to Ollama at {self._host}. "
                "Please ensure Ollama is running: `ollama serve`",
            )

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
            ProviderConnectionError: If Ollama is unreachable
        """
        temperature = temperature if temperature is not None else settings.llm_temperature
        max_tokens = max_tokens if max_tokens is not None else settings.llm_max_tokens

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        try:
            # For streaming, we need a much longer timeout since we're waiting for incremental data
            # Use a fresh client with extended timeout for streaming operations
            async with httpx.AsyncClient(
                base_url=self._host,
                timeout=httpx.Timeout(300.0, connect=30.0),  # 5 min read, 30s connect
            ) as stream_client:
                async with stream_client.stream(
                    "POST",
                    "/api/chat",
                    json={
                        "model": self._model,
                        "messages": messages,
                        "stream": True,
                        "options": {
                            "temperature": temperature,
                            "num_predict": max_tokens,
                        },
                    },
                ) as response:
                    async for line in response.aiter_lines():
                        if line:
                            import json

                            data = json.loads(line)
                            if "message" in data and "content" in data["message"]:
                                yield data["message"]["content"]

        except httpx.ConnectError:
            raise ProviderConnectionError(
                self.provider_name,
                f"Cannot connect to Ollama at {self._host}. "
                "Please ensure Ollama is running: `ollama serve`",
            )


# Backward compatibility aliases
OllamaStatus = LLMStatus


# Global client instance
_ollama_client: Optional[OllamaClient] = None


def get_ollama_client() -> OllamaClient:
    """Get the global Ollama client instance."""
    global _ollama_client
    if _ollama_client is None:
        _ollama_client = OllamaClient()
    return _ollama_client


async def check_ollama_health() -> dict:
    """
    Health check function for Ollama.

    Returns a dict with status information for the health endpoint.
    """
    client = get_ollama_client()
    status = await client.check_status()

    if not status.available:
        return {
            "status": "unavailable",
            "message": status.message,
            "host": client.host,
            "model": client.model,
        }

    model_available = await client.is_model_available()

    return {
        "status": "ok" if model_available else "model_missing",
        "message": "Ollama connected" if model_available else f"Model {client.model} not found",
        "host": client.host,
        "model": client.model,
        "available_models": status.models,
        "model_ready": model_available,
    }
