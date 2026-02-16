"""
OpenAI LLM Client

Implements the BaseLLMClient protocol for OpenAI API.
Requires OPENAI_API_KEY environment variable or explicit configuration.

INTEGRITY:
- All methods make REAL API calls to OpenAI
- No mock/stub/dummy implementations
- No fallback behavior - if not configured, raises ProviderNotConfiguredError
- No synthetic response generation
"""

import os
from typing import AsyncGenerator, Optional

from loguru import logger

from src.ai.llm.base_client import (
    AbstractLLMClient,
    LLMResponse,
    LLMStatus,
    ProviderConnectionError,
    ProviderNotConfiguredError,
)


class OpenAIClient(AbstractLLMClient):
    """
    Client wrapper for OpenAI API.

    Provides methods for:
    - Connection status checking
    - Model listing
    - Synchronous and streaming chat completion

    INTEGRITY: All methods make real API calls to OpenAI.
    No mock/stub/dummy implementations.
    If API key is not configured, raises ProviderNotConfiguredError.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout: Optional[int] = None,
    ):
        """
        Initialize OpenAI client.

        Args:
            api_key: OpenAI API key. If None, reads from OPENAI_API_KEY env var.
            model: Model name (e.g., "gpt-4o", "gpt-4-turbo", "gpt-3.5-turbo")
            base_url: Optional custom base URL (for Azure OpenAI or proxies)
            timeout: Request timeout in seconds

        Raises:
            ProviderNotConfiguredError: If API key is not provided and not in env
        """
        self._api_key = api_key or os.environ.get("OPENAI_API_KEY")
        self._model = model or "gpt-4o"
        self._base_url = base_url
        self._timeout = timeout or 120
        self._client = None

        # INTEGRITY: Validate configuration at init time
        # Do NOT silently fall back to another provider
        if not self._api_key:
            raise ProviderNotConfiguredError(
                "openai",
                "OPENAI_API_KEY environment variable not set and no api_key provided. "
                "Set OPENAI_API_KEY or pass api_key parameter.",
            )

    def _get_client(self):
        """Get or create the OpenAI client."""
        if self._client is None:
            try:
                from openai import AsyncOpenAI
            except ImportError:
                raise ProviderNotConfiguredError(
                    "openai",
                    "openai package not installed. Install with: pip install openai",
                )

            kwargs = {
                "api_key": self._api_key,
                "timeout": self._timeout,
            }
            if self._base_url:
                kwargs["base_url"] = self._base_url

            self._client = AsyncOpenAI(**kwargs)

        return self._client

    @property
    def provider_name(self) -> str:
        """Return the provider name."""
        return "openai"

    @property
    def model_name(self) -> str:
        """Return the current model name."""
        return self._model

    async def check_status(self) -> LLMStatus:
        """
        Check if OpenAI API is available.

        Returns:
            LLMStatus with availability information
        """
        try:
            client = self._get_client()
            # List models to verify API connectivity
            models_response = await client.models.list()
            model_ids = [m.id for m in models_response.data]

            # Check if our target model is available
            model_available = self._model in model_ids

            return LLMStatus(
                available=True,
                provider=self.provider_name,
                message="OpenAI API connected" if model_available else f"Connected but model {self._model} not found",
                models=model_ids[:20],  # Limit to first 20 models
                current_model=self._model,
            )
        except Exception as e:
            error_msg = str(e)
            if "API key" in error_msg or "authentication" in error_msg.lower():
                return LLMStatus(
                    available=False,
                    provider=self.provider_name,
                    message="OpenAI API authentication failed. Check your API key.",
                    current_model=self._model,
                )
            return LLMStatus(
                available=False,
                provider=self.provider_name,
                message=f"OpenAI API error: {error_msg}",
                current_model=self._model,
            )

    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> LLMResponse:
        """
        Generate a response from OpenAI.

        Args:
            prompt: User prompt
            system_prompt: Optional system prompt
            temperature: Sampling temperature (0.0-2.0 for OpenAI)
            max_tokens: Maximum tokens to generate

        Returns:
            LLMResponse with content and metadata

        Raises:
            ProviderConnectionError: If OpenAI API is unreachable
        """
        import time

        temperature = temperature if temperature is not None else 0.7
        max_tokens = max_tokens if max_tokens is not None else 2048

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        try:
            client = self._get_client()
            start_time = time.perf_counter()

            response = await client.chat.completions.create(
                model=self._model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )

            duration_ms = (time.perf_counter() - start_time) * 1000

            choice = response.choices[0]
            usage = response.usage

            return LLMResponse(
                content=choice.message.content or "",
                model=response.model,
                provider=self.provider_name,
                total_duration_ms=duration_ms,
                prompt_eval_count=usage.prompt_tokens if usage else None,
                eval_count=usage.completion_tokens if usage else None,
            )

        except Exception as e:
            error_msg = str(e)
            logger.error(f"OpenAI generation error: {error_msg}")
            raise ProviderConnectionError(
                self.provider_name,
                f"OpenAI API error: {error_msg}",
            )

    async def generate_stream(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> AsyncGenerator[str, None]:
        """
        Generate a streaming response from OpenAI.

        Args:
            prompt: User prompt
            system_prompt: Optional system prompt
            temperature: Sampling temperature (0.0-2.0 for OpenAI)
            max_tokens: Maximum tokens to generate

        Yields:
            String chunks of the response

        Raises:
            ProviderConnectionError: If OpenAI API is unreachable
        """
        temperature = temperature if temperature is not None else 0.7
        max_tokens = max_tokens if max_tokens is not None else 2048

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        try:
            client = self._get_client()

            stream = await client.chat.completions.create(
                model=self._model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=True,
            )

            async for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content

        except Exception as e:
            error_msg = str(e)
            logger.error(f"OpenAI streaming error: {error_msg}")
            raise ProviderConnectionError(
                self.provider_name,
                f"OpenAI API error: {error_msg}",
            )

    async def close(self) -> None:
        """Close the OpenAI client."""
        if self._client:
            await self._client.close()
            self._client = None
