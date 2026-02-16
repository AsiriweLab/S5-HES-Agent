"""
LLM Provider API Endpoints

Exposes LLM provider management to the frontend:
- List available providers
- Check provider status
- Switch active provider (with persistent .env updates)
- List models per provider

INTEGRITY REQUIREMENTS:
- Only expose REAL, configured providers
- No mock/fallback providers
- If provider unavailable, report error (don't fallback)
"""

import os
import re
from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, HTTPException
from loguru import logger
from pydantic import BaseModel

from src.ai.llm import (
    get_provider_registry,
    ProviderNotConfiguredError,
)
from src.core.config import settings, reload_settings


router = APIRouter(prefix="/api/llm")


# =============================================================================
# Response Models
# =============================================================================


class ProviderInfo(BaseModel):
    """Information about an LLM provider."""
    name: str
    display_name: str
    is_configured: bool
    is_active: bool
    requires_api_key: bool
    api_key_env_var: Optional[str]
    default_model: str
    available_models: list[str]
    status_message: str


class ProvidersResponse(BaseModel):
    """Response with all available LLM providers."""
    providers: list[ProviderInfo]
    active_provider: Optional[str]
    active_model: Optional[str]


class SwitchProviderRequest(BaseModel):
    """Request to switch LLM provider."""
    provider: str
    model: Optional[str] = None
    persist: bool = True  # Whether to persist to .env file


class SwitchProviderResponse(BaseModel):
    """Response after switching provider."""
    success: bool
    provider: str
    model: str
    message: str
    persisted: bool


class ModelsResponse(BaseModel):
    """Response with available models for a provider."""
    provider: str
    models: list[str]
    default_model: str


# =============================================================================
# Provider Model Lists
# =============================================================================

# These are the commonly available models for each provider.
# For Ollama, models depend on what's installed locally.

OPENAI_MODELS = [
    "gpt-4o",
    "gpt-4o-mini",
    "gpt-4-turbo",
    "gpt-4",
    "gpt-3.5-turbo",
]

GEMINI_MODELS = [
    "gemini-2.0-flash",
    "gemini-2.5-flash",
    "gemini-2.5-pro",
    "gemini-2.0-flash-lite",
]

# Common Ollama models - actual availability depends on local installation
OLLAMA_COMMON_MODELS = [
    "llama3.1:8b-instruct-q4_K_M",
    "llama3.1:8b",
    "llama3.1:70b",
    "llama2:7b",
    "llama2:13b",
    "mistral:7b",
    "mixtral:8x7b",
    "codellama:7b",
    "codellama:13b",
    "phi3:mini",
    "gemma:7b",
]

# Display names for providers
PROVIDER_DISPLAY_NAMES = {
    "ollama": "Ollama (Local)",
    "openai": "OpenAI (Cloud)",
    "gemini": "Google Gemini (Cloud)",
}


# =============================================================================
# .env File Management
# =============================================================================


def _get_env_file_path() -> Path:
    """Get the path to the .env file."""
    # Go up from src/api to backend directory
    backend_dir = Path(__file__).resolve().parent.parent.parent
    return backend_dir / ".env"


def _update_env_file(key: str, value: str) -> bool:
    """
    Update a key in the .env file.

    Args:
        key: Environment variable name
        value: New value

    Returns:
        True if successfully updated, False otherwise
    """
    env_path = _get_env_file_path()
    logger.info(f"Attempting to update .env at: {env_path}")

    if not env_path.exists():
        logger.warning(f".env file not found at {env_path}")
        return False

    try:
        # Read file and split into lines (handles both Unix and Windows line endings)
        content = env_path.read_text(encoding="utf-8")
        lines = content.splitlines(keepends=True)

        # Find and replace the key
        key_found = False
        new_lines = []
        for line in lines:
            # Strip line for comparison but keep original for output
            stripped = line.rstrip('\r\n')

            # Check if this line contains the key (with or without comment)
            if stripped.lstrip('#').lstrip().startswith(f'{key}='):
                # Replace the entire line with new value
                # Preserve line ending from original if present
                line_ending = '\n'
                if line.endswith('\r\n'):
                    line_ending = '\r\n'
                elif line.endswith('\n'):
                    line_ending = '\n'
                elif line.endswith('\r'):
                    line_ending = '\r'

                new_lines.append(f'{key}={value}{line_ending}')
                key_found = True
                logger.info(f"Found and updated {key} in .env")
            else:
                new_lines.append(line)

        # If key wasn't found, append it
        if not key_found:
            # Ensure file ends with newline before adding
            if new_lines and not new_lines[-1].endswith('\n'):
                new_lines[-1] += '\n'
            new_lines.append(f'{key}={value}\n')
            logger.info(f"Appended {key} to .env")

        # Write back
        new_content = ''.join(new_lines)
        env_path.write_text(new_content, encoding="utf-8")
        logger.info(f"Successfully updated .env: {key}={value}")
        return True

    except Exception as e:
        logger.error(f"Failed to update .env file: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False


# =============================================================================
# Endpoints
# =============================================================================


@router.get("/providers", response_model=ProvidersResponse)
async def list_providers() -> ProvidersResponse:
    """
    List all available LLM providers with their configuration status.

    Returns information about each provider including:
    - Whether it's properly configured (API keys set)
    - Available models
    - Current active provider

    INTEGRITY: Only returns real providers. No mock/fallback providers.
    """
    registry = get_provider_registry()
    providers_info: list[ProviderInfo] = []

    for provider_name in registry.list_providers():
        config = registry.get_provider_config(provider_name)
        is_configured = config.is_configured()
        is_active = registry.current_provider == provider_name

        # Get available models based on provider
        if provider_name == "ollama":
            # For Ollama, try to get actual installed models
            available_models = await _get_ollama_models()
            if available_models:
                status_message = "Local LLM server running"
            else:
                status_message = "Ollama not running - start with: ollama serve"
                available_models = OLLAMA_COMMON_MODELS
        elif provider_name == "openai":
            available_models = OPENAI_MODELS
            if is_configured:
                status_message = "API key configured"
            else:
                status_message = f"Set {config.api_key_env_var} in .env"
        elif provider_name == "gemini":
            available_models = GEMINI_MODELS
            if is_configured:
                status_message = "API key configured"
            else:
                status_message = f"Set {config.api_key_env_var} in .env"
        else:
            available_models = [config.default_model]
            status_message = "Configured" if is_configured else "Not configured"

        providers_info.append(ProviderInfo(
            name=provider_name,
            display_name=PROVIDER_DISPLAY_NAMES.get(provider_name, provider_name.title()),
            is_configured=is_configured,
            is_active=is_active,
            requires_api_key=config.requires_api_key,
            api_key_env_var=config.api_key_env_var,
            default_model=config.default_model,
            available_models=available_models,
            status_message=status_message,
        ))

    # Get current active provider and model
    active_provider = registry.current_provider or settings.llm_provider
    active_model = None
    if active_provider:
        try:
            config = registry.get_provider_config(active_provider)
            if active_provider == "ollama":
                active_model = settings.ollama_model
            elif active_provider == "openai":
                active_model = settings.openai_model
            elif active_provider == "gemini":
                active_model = settings.gemini_model
            else:
                active_model = config.default_model
        except ProviderNotConfiguredError:
            pass

    return ProvidersResponse(
        providers=providers_info,
        active_provider=active_provider,
        active_model=active_model,
    )


@router.post("/switch", response_model=SwitchProviderResponse)
async def switch_provider(request: SwitchProviderRequest) -> SwitchProviderResponse:
    """
    Switch to a different LLM provider.

    This endpoint:
    1. Validates the provider is configured
    2. Switches the runtime provider
    3. Persists the change to .env file (if persist=True)

    INTEGRITY:
    - If provider is not configured, returns error (no fallback)
    - If provider is unavailable, returns error (no synthetic responses)
    """
    registry = get_provider_registry()

    try:
        # Validate provider exists
        config = registry.get_provider_config(request.provider)

        # Check if provider is configured
        if not config.is_configured():
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "provider_not_configured",
                    "message": f"Provider '{request.provider}' requires {config.api_key_env_var} environment variable to be set in .env file.",
                    "required_env_var": config.api_key_env_var,
                }
            )

        # Determine model
        model = request.model or config.default_model

        # Switch provider at runtime
        client = registry.switch_provider(request.provider, model)

        # Persist to .env file if requested
        persisted = False
        if request.persist:
            # Update LLM_PROVIDER
            provider_updated = _update_env_file("LLM_PROVIDER", request.provider)

            # Update model based on provider
            if request.provider == "ollama":
                model_updated = _update_env_file("OLLAMA_MODEL", model)
            elif request.provider == "openai":
                model_updated = _update_env_file("OPENAI_MODEL", model)
            elif request.provider == "gemini":
                model_updated = _update_env_file("GEMINI_MODEL", model)
            else:
                model_updated = True

            persisted = provider_updated and model_updated

            # Reload settings to pick up .env changes
            if persisted:
                reload_settings()
                logger.info(f"Reloaded settings after .env update: LLM_PROVIDER={request.provider}")

        message = f"Switched to {request.provider} with model {model}"
        if persisted:
            message += " (saved to .env)"
        elif request.persist:
            message += " (runtime only - .env update failed)"

        return SwitchProviderResponse(
            success=True,
            provider=request.provider,
            model=model,
            message=message,
            persisted=persisted,
        )

    except ProviderNotConfiguredError as e:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "provider_not_configured",
                "message": str(e),
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Provider switch failed: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "error": "switch_failed",
                "message": f"Failed to switch provider: {str(e)}",
            }
        )


@router.get("/models/{provider}", response_model=ModelsResponse)
async def list_provider_models(provider: str) -> ModelsResponse:
    """
    List available models for a specific provider.

    For Ollama: Returns locally installed models.
    For OpenAI: Returns available API models.
    For Gemini: Returns available Gemini models.
    """
    registry = get_provider_registry()

    try:
        config = registry.get_provider_config(provider)
    except ProviderNotConfiguredError:
        raise HTTPException(
            status_code=404,
            detail=f"Provider '{provider}' not found"
        )

    if provider == "ollama":
        models = await _get_ollama_models()
        if not models:
            models = OLLAMA_COMMON_MODELS  # Fallback to common models list
    elif provider == "openai":
        models = OPENAI_MODELS
    elif provider == "gemini":
        models = GEMINI_MODELS
    else:
        models = [config.default_model]

    return ModelsResponse(
        provider=provider,
        models=models,
        default_model=config.default_model,
    )


@router.get("/config-info")
async def get_config_info() -> dict[str, Any]:
    """
    Get information about current LLM configuration.
    """
    return {
        "current_provider": settings.llm_provider,
        "providers": {
            "ollama": {
                "model": settings.ollama_model,
                "host": settings.ollama_host,
                "configured": True,  # Ollama doesn't require API key
            },
            "openai": {
                "model": settings.openai_model,
                "configured": bool(os.environ.get("OPENAI_API_KEY")),
            },
            "gemini": {
                "model": settings.gemini_model,
                "configured": bool(os.environ.get("GEMINI_API_KEY")),
            },
        },
        "env_file": str(_get_env_file_path()),
    }


# =============================================================================
# Helper Functions
# =============================================================================


async def _get_ollama_models() -> list[str]:
    """
    Get list of models installed in Ollama.

    Returns empty list if Ollama is not running.
    """
    try:
        import httpx
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{settings.ollama_host}/api/tags")
            if response.status_code == 200:
                data = response.json()
                models = data.get("models", [])
                return [m.get("name", "") for m in models if m.get("name")]
    except Exception:
        pass
    return []
