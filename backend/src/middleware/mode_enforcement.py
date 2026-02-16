"""
Mode Enforcement Middleware

Validates requests based on the current interaction mode (LLM vs No-LLM).
In No-LLM mode, blocks LLM-dependent endpoints to ensure reproducible research.
"""

from typing import Callable, Optional
from fastapi import Request, Response, HTTPException
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from loguru import logger


# Endpoints that require LLM and should be blocked in No-LLM mode
LLM_REQUIRED_ENDPOINTS = [
    "/api/chat/",  # Chat endpoints use LLM
    "/api/chat/stream",
    "/api/chat/action",
    # Note: /api/mode/expert-consultation is allowed - it's the explicit consultation path
]

# Endpoints always allowed regardless of mode
ALWAYS_ALLOWED_ENDPOINTS = [
    "/api/health",
    "/api/mode/",  # Mode management always allowed
    "/api/mode/status",
    "/api/mode/set",
    "/api/mode/current",
    "/api/mode/expert-consultation",  # Explicit consultation allowed
    "/api/mode/scenarios",  # Pre-loaded scenarios
    "/api/mode/statistics",
    "/api/simulation/",  # Simulation is LLM-independent
    "/api/rag/",  # RAG search is allowed (knowledge retrieval, not generation)
    "/api/docs",
    "/api/redoc",
    "/api/openapi.json",
]


class ModeEnforcementMiddleware(BaseHTTPMiddleware):
    """
    Middleware to enforce interaction mode restrictions.

    In No-LLM mode:
    - Blocks direct LLM endpoints (chat, streaming)
    - Allows pre-loaded scenarios and explicit consultations
    - Allows all simulation and data retrieval endpoints
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Get mode from header or session
        mode = request.headers.get("X-Interaction-Mode", "llm").lower()
        path = request.url.path.lower()

        # Record mode in request state for downstream handlers
        request.state.interaction_mode = mode

        # If in LLM mode, allow everything
        if mode == "llm":
            return await call_next(request)

        # In No-LLM mode, check if endpoint is allowed
        if mode == "no-llm":
            # Check if always allowed
            if self._is_always_allowed(path):
                return await call_next(request)

            # Check if LLM-required and should be blocked
            if self._requires_llm(path):
                logger.warning(
                    f"[MODE_ENFORCEMENT] Blocked LLM-required endpoint in no-llm mode: {path}"
                )
                return JSONResponse(
                    status_code=403,
                    content={
                        "error": "LLM_DISABLED",
                        "message": (
                            "This endpoint requires LLM and is disabled in No-LLM mode. "
                            "Use /api/mode/expert-consultation for AI assistance, "
                            "or switch to LLM mode."
                        ),
                        "mode": "no-llm",
                        "blocked_path": path,
                        "alternatives": [
                            "/api/mode/expert-consultation",
                            "/api/mode/scenarios",
                        ],
                    },
                )

        # Allow other requests
        return await call_next(request)

    def _is_always_allowed(self, path: str) -> bool:
        """Check if path is always allowed regardless of mode."""
        for allowed in ALWAYS_ALLOWED_ENDPOINTS:
            if path.startswith(allowed):
                return True
        return False

    def _requires_llm(self, path: str) -> bool:
        """Check if path requires LLM."""
        for llm_path in LLM_REQUIRED_ENDPOINTS:
            if path.startswith(llm_path):
                return True
        return False


def get_current_mode(request: Request) -> str:
    """
    Get the current interaction mode from request.

    Can be used as a FastAPI dependency.
    """
    return getattr(request.state, "interaction_mode", "llm")


def require_llm_mode(request: Request) -> None:
    """
    Dependency that requires LLM mode.

    Raises HTTPException if in No-LLM mode.
    """
    mode = get_current_mode(request)
    if mode == "no-llm":
        raise HTTPException(
            status_code=403,
            detail={
                "error": "LLM_DISABLED",
                "message": "This operation requires LLM mode to be enabled.",
            },
        )


def require_no_llm_mode(request: Request) -> None:
    """
    Dependency that requires No-LLM mode.

    Useful for endpoints that should only work in research mode.
    """
    mode = get_current_mode(request)
    if mode == "llm":
        raise HTTPException(
            status_code=403,
            detail={
                "error": "REQUIRES_NO_LLM_MODE",
                "message": "This operation requires No-LLM mode for reproducibility.",
            },
        )
