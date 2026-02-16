"""
Smart-HES Agent - Main Application Entry Point

FastAPI application with health endpoints and API routing.
"""

from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from src.core.config import settings
from src.core.logging import setup_logging
from src.api.health import router as health_router
from src.api.rag import router as rag_router
from src.api.simulation import router as simulation_router
from src.api.chat import router as chat_router
from src.api.iot import router as iot_router
from src.api.experiments import router as experiments_router
from src.api.history import router as history_router
from src.api.sweeps import router as sweeps_router
from src.api.monitoring import router as monitoring_router
from src.api.admin import router as admin_router
from src.api.agents import router as agents_router
from src.api.mode import router as mode_router
from src.api.review_queue import router as review_router
from src.api.exports import router as exports_router
from src.api.security_audit import router as security_audit_router
from src.api.llm import router as llm_router
from src.middleware.mode_enforcement import ModeEnforcementMiddleware


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager for startup and shutdown events."""
    # Startup
    setup_logging()
    logger.info(f"Starting {settings.app_name} v{settings.app_version}")
    logger.info(f"Environment: {settings.environment}")
    logger.info(f"Debug mode: {settings.debug}")
    logger.info(f"Anti-hallucination verification: {settings.verification_enabled}")
    logger.info(f"Strict verification mode: {settings.strict_verification_mode}")

    # Create required directories
    settings.logs_path.mkdir(parents=True, exist_ok=True)
    settings.exports_path.mkdir(parents=True, exist_ok=True)
    settings.knowledge_base_path.mkdir(parents=True, exist_ok=True)

    yield

    # Shutdown
    logger.info(f"Shutting down {settings.app_name}")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title=settings.app_name,
        description=(
            "Agentic RAG-Enhanced Smart Home Energy Simulation Framework "
            "for IoT Security Research. Designed for IEEE IoT Journal and IEEE TDSC publications."
        ),
        version=settings.app_version,
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        openapi_url="/api/openapi.json",
        lifespan=lifespan,
    )

    # Configure CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=settings.cors_allow_credentials,
        allow_methods=settings.cors_allow_methods,
        allow_headers=settings.cors_allow_headers,
    )

    # Add mode enforcement middleware for No-LLM mode support
    app.add_middleware(ModeEnforcementMiddleware)

    # Register routers
    app.include_router(health_router, prefix="/api", tags=["Health"])
    app.include_router(rag_router, prefix="/api/rag", tags=["RAG"])
    app.include_router(simulation_router, prefix="/api/simulation", tags=["Simulation"])
    app.include_router(chat_router, prefix="/api/chat", tags=["Chat"])
    app.include_router(iot_router, prefix="/api", tags=["IoT Communication"])
    app.include_router(experiments_router, tags=["Experiments"])
    app.include_router(history_router, tags=["History"])
    app.include_router(sweeps_router, tags=["Parameter Sweeps"])
    app.include_router(monitoring_router, tags=["Monitoring"])
    app.include_router(admin_router, tags=["Admin"])
    app.include_router(agents_router, tags=["Agents"])
    app.include_router(mode_router, prefix="/api/mode", tags=["Mode & Consultations"])
    app.include_router(review_router, tags=["Human Review Queue"])
    app.include_router(exports_router, tags=["Publication Exports"])
    app.include_router(security_audit_router, tags=["Security Audit"])
    app.include_router(llm_router, tags=["LLM Provider"])

    return app


# Create application instance
app = create_app()


def main() -> None:
    """Run the application using uvicorn."""
    import uvicorn

    uvicorn.run(
        "src.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.reload,
        workers=settings.workers,
    )


if __name__ == "__main__":
    main()
