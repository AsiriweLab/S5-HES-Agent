"""
Google Gemini LLM Client

Implements the BaseLLMClient protocol for Google Gemini API.
Requires GEMINI_API_KEY environment variable or explicit configuration.

INTEGRITY:
- All methods make REAL API calls to Google Gemini
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


class GeminiClient(AbstractLLMClient):
    """
    Client wrapper for Google Gemini API.

    Provides methods for:
    - Connection status checking
    - Model listing
    - Synchronous and streaming chat completion

    INTEGRITY: All methods make real API calls to Google Gemini.
    No mock/stub/dummy implementations.
    If API key is not configured, raises ProviderNotConfiguredError.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        timeout: Optional[int] = None,
    ):
        """
        Initialize Gemini client.

        Args:
            api_key: Gemini API key. If None, reads from GEMINI_API_KEY env var.
            model: Model name (e.g., "gemini-1.5-pro", "gemini-1.5-flash")
            timeout: Request timeout in seconds

        Raises:
            ProviderNotConfiguredError: If API key is not provided and not in env
        """
        self._api_key = api_key or os.environ.get("GEMINI_API_KEY")
        self._model = model or "gemini-2.0-flash"
        self._timeout = timeout or 120
        self._client = None

        # INTEGRITY: Validate configuration at init time
        # Do NOT silently fall back to another provider
        if not self._api_key:
            raise ProviderNotConfiguredError(
                "gemini",
                "GEMINI_API_KEY environment variable not set and no api_key provided. "
                "Set GEMINI_API_KEY or pass api_key parameter.",
            )

    def _get_client(self):
        """Get or create the Gemini client."""
        if self._client is None:
            try:
                import google.generativeai as genai
            except ImportError:
                raise ProviderNotConfiguredError(
                    "gemini",
                    "google-generativeai package not installed. Install with: pip install google-generativeai",
                )

            genai.configure(api_key=self._api_key)
            self._client = genai.GenerativeModel(self._model)

        return self._client

    @property
    def provider_name(self) -> str:
        """Return the provider name."""
        return "gemini"

    @property
    def model_name(self) -> str:
        """Return the current model name."""
        return self._model

    async def check_status(self) -> LLMStatus:
        """
        Check if Gemini API is available.

        Returns:
            LLMStatus with availability information
        """
        try:
            import google.generativeai as genai
            genai.configure(api_key=self._api_key)

            # List models to verify API connectivity
            models = list(genai.list_models())
            model_names = [m.name for m in models if "generateContent" in m.supported_generation_methods]

            # Check if our target model is available
            target_model = f"models/{self._model}"
            model_available = any(target_model in m.name for m in models)

            return LLMStatus(
                available=True,
                provider=self.provider_name,
                message="Gemini API connected" if model_available else f"Connected but model {self._model} not found",
                models=[m.name.replace("models/", "") for m in models if "generateContent" in m.supported_generation_methods][:10],
                current_model=self._model,
            )
        except Exception as e:
            error_msg = str(e)
            if "API key" in error_msg or "authentication" in error_msg.lower() or "invalid" in error_msg.lower():
                return LLMStatus(
                    available=False,
                    provider=self.provider_name,
                    message="Gemini API authentication failed. Check your API key.",
                    current_model=self._model,
                )
            return LLMStatus(
                available=False,
                provider=self.provider_name,
                message=f"Gemini API error: {error_msg}",
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
        Generate a response from Gemini.

        Args:
            prompt: User prompt
            system_prompt: Optional system prompt
            temperature: Sampling temperature (0.0-1.0 for Gemini)
            max_tokens: Maximum tokens to generate

        Returns:
            LLMResponse with content and metadata

        Raises:
            ProviderConnectionError: If Gemini API is unreachable
        """
        import time

        temperature = temperature if temperature is not None else 0.7
        max_tokens = max_tokens if max_tokens is not None else 2048

        try:
            import google.generativeai as genai
            genai.configure(api_key=self._api_key)

            # Create model with generation config
            generation_config = genai.GenerationConfig(
                temperature=temperature,
                max_output_tokens=max_tokens,
            )

            model = genai.GenerativeModel(
                self._model,
                generation_config=generation_config,
                system_instruction=system_prompt if system_prompt else None,
            )

            start_time = time.perf_counter()

            # Generate response
            response = model.generate_content(prompt)

            duration_ms = (time.perf_counter() - start_time) * 1000

            # Extract text from response
            content = ""
            if response.candidates:
                content = response.candidates[0].content.parts[0].text

            # Get token counts if available
            prompt_tokens = None
            completion_tokens = None
            if hasattr(response, 'usage_metadata'):
                prompt_tokens = getattr(response.usage_metadata, 'prompt_token_count', None)
                completion_tokens = getattr(response.usage_metadata, 'candidates_token_count', None)

            return LLMResponse(
                content=content,
                model=self._model,
                provider=self.provider_name,
                total_duration_ms=duration_ms,
                prompt_eval_count=prompt_tokens,
                eval_count=completion_tokens,
            )

        except Exception as e:
            error_msg = str(e)
            logger.error(f"Gemini generation error: {error_msg}")
            raise ProviderConnectionError(
                self.provider_name,
                f"Gemini API error: {error_msg}",
            )

    async def generate_stream(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> AsyncGenerator[str, None]:
        """
        Generate a streaming response from Gemini.

        Args:
            prompt: User prompt
            system_prompt: Optional system prompt
            temperature: Sampling temperature (0.0-1.0 for Gemini)
            max_tokens: Maximum tokens to generate

        Yields:
            String chunks of the response

        Raises:
            ProviderConnectionError: If Gemini API is unreachable
        """
        temperature = temperature if temperature is not None else 0.7
        max_tokens = max_tokens if max_tokens is not None else 2048

        try:
            import google.generativeai as genai
            genai.configure(api_key=self._api_key)

            # Create model with generation config
            generation_config = genai.GenerationConfig(
                temperature=temperature,
                max_output_tokens=max_tokens,
            )

            model = genai.GenerativeModel(
                self._model,
                generation_config=generation_config,
                system_instruction=system_prompt if system_prompt else None,
            )

            # Generate streaming response
            response = model.generate_content(prompt, stream=True)

            for chunk in response:
                if chunk.text:
                    yield chunk.text

        except Exception as e:
            error_msg = str(e)
            logger.error(f"Gemini streaming error: {error_msg}")
            raise ProviderConnectionError(
                self.provider_name,
                f"Gemini API error: {error_msg}",
            )

    async def close(self) -> None:
        """Close the Gemini client."""
        # Gemini client doesn't need explicit cleanup
        self._client = None
