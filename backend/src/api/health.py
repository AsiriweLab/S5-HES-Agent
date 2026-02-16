"""
Health Check API Endpoints

Provides system health, readiness, and liveness probes.
Includes verification of all critical subsystems.
"""

from datetime import datetime
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from src.core.config import settings


router = APIRouter()


class HealthResponse(BaseModel):
    """Health check response model."""
    status: str
    timestamp: datetime
    version: str
    environment: str


class ReadinessResponse(BaseModel):
    """Readiness check response with subsystem status."""
    status: str
    timestamp: datetime
    checks: dict[str, dict[str, Any]]


class SystemInfoResponse(BaseModel):
    """System information response."""
    app_name: str
    version: str
    environment: str
    features: dict[str, bool]
    settings: dict[str, Any]


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """
    Basic health check endpoint.

    Returns 200 if the API is running.
    Used for load balancer health checks.
    """
    return HealthResponse(
        status="healthy",
        timestamp=datetime.utcnow(),
        version=settings.app_version,
        environment=settings.environment,
    )


@router.get("/health/ready", response_model=ReadinessResponse)
async def readiness_check() -> ReadinessResponse:
    """
    Readiness probe checking all subsystems.

    Checks:
    - Database connectivity (future: ChromaDB)
    - LLM availability (future: Ollama)
    - File system access
    - Configuration validity

    Returns 200 only if all critical systems are ready.
    """
    checks: dict[str, dict[str, Any]] = {}
    all_healthy = True

    # Check 1: Configuration
    try:
        _ = settings.app_name
        checks["configuration"] = {"status": "ok", "message": "Configuration loaded"}
    except Exception as e:
        checks["configuration"] = {"status": "error", "message": str(e)}
        all_healthy = False

    # Check 2: File system (logs directory)
    try:
        settings.logs_path.mkdir(parents=True, exist_ok=True)
        test_file = settings.logs_path / ".health_check"
        test_file.touch()
        test_file.unlink()
        checks["filesystem"] = {"status": "ok", "message": "File system accessible"}
    except Exception as e:
        checks["filesystem"] = {"status": "error", "message": str(e)}
        all_healthy = False

    # Check 3: Ollama/LLM - actual health check
    try:
        import httpx
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{settings.ollama_host}/api/tags")
            if response.status_code == 200:
                models = response.json().get("models", [])
                model_names = [m.get("name", "") for m in models]
                checks["llm"] = {
                    "status": "ok",
                    "message": f"Ollama available with {len(models)} models",
                    "ollama_host": settings.ollama_host,
                    "model": settings.ollama_model,
                    "model_loaded": settings.ollama_model in str(model_names),
                }
            else:
                checks["llm"] = {
                    "status": "error",
                    "message": f"Ollama returned status {response.status_code}",
                    "ollama_host": settings.ollama_host,
                }
                all_healthy = False
    except Exception as e:
        checks["llm"] = {
            "status": "error",
            "message": f"Ollama unreachable: {str(e)}",
            "ollama_host": settings.ollama_host,
        }
        all_healthy = False

    # Check 4: ChromaDB - actual health check
    try:
        import chromadb
        client = chromadb.PersistentClient(path=str(settings.chroma_persist_directory))
        collections = client.list_collections()
        checks["chromadb"] = {
            "status": "ok",
            "message": f"ChromaDB available with {len(collections)} collections",
            "persist_directory": str(settings.chroma_persist_directory),
        }
    except Exception as e:
        checks["chromadb"] = {
            "status": "error",
            "message": f"ChromaDB error: {str(e)}",
            "persist_directory": str(settings.chroma_persist_directory),
        }
        all_healthy = False

    # Check 5: Verification Pipeline - report actual configuration
    checks["verification_pipeline"] = {
        "status": "ok" if settings.verification_enabled else "disabled",
        "message": "Verification pipeline configured" if settings.verification_enabled else "Verification disabled",
        "enabled": settings.verification_enabled,
        "strict_mode": settings.strict_verification_mode,
    }

    overall_status = "ready" if all_healthy else "degraded"

    return ReadinessResponse(
        status=overall_status,
        timestamp=datetime.utcnow(),
        checks=checks,
    )


@router.get("/health/live")
async def liveness_check() -> dict[str, str]:
    """
    Liveness probe.

    Simple check that the process is alive.
    Returns 200 if the process can respond.
    """
    return {"status": "alive"}


@router.get("/info", response_model=SystemInfoResponse)
async def system_info() -> SystemInfoResponse:
    """
    Get system information and enabled features.

    Useful for debugging and understanding the current configuration.
    """
    return SystemInfoResponse(
        app_name=settings.app_name,
        version=settings.app_version,
        environment=settings.environment,
        features={
            "verification_enabled": settings.verification_enabled,
            "strict_verification_mode": settings.strict_verification_mode,
            "require_source_citation": settings.require_source_citation,
            "debug_mode": settings.debug,
        },
        settings={
            "ollama_host": settings.ollama_host,
            "ollama_model": settings.ollama_model,
            "llm_timeout": settings.llm_timeout,
            "rag_top_k": settings.rag_top_k,
            "confidence_threshold_pass": settings.confidence_threshold_pass,
            "confidence_threshold_flag": settings.confidence_threshold_flag,
            "simulation_time_compression": settings.simulation_time_compression,
            "max_devices": settings.max_devices,
        },
    )
