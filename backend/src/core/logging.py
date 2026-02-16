"""
Smart-HES Agent Logging Module

Structured logging with loguru for comprehensive audit trails.
Supports both console and JSON output formats.
"""

import sys
from pathlib import Path

from loguru import logger

from src.core.config import settings


def setup_logging() -> None:
    """Configure application logging."""
    # Remove default handler
    logger.remove()

    # Determine log format based on settings
    if settings.log_format == "json":
        log_format = (
            '{{"timestamp": "{time:YYYY-MM-DDTHH:mm:ss.SSS}", '
            '"level": "{level.name}", '
            '"message": "{message}", '
            '"module": "{module}", '
            '"function": "{function}", '
            '"line": {line}}}'
        )
    else:
        log_format = (
            "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>{module}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
            "<level>{message}</level>"
        )

    # Console handler
    logger.add(
        sys.stderr,
        format=log_format,
        level=settings.log_level,
        colorize=settings.log_format != "json",
    )

    # File handler (always JSON for audit trail)
    log_file = settings.logs_path / "smart_hes_{time:YYYY-MM-DD}.log"
    logger.add(
        log_file,
        format=(
            '{{"timestamp": "{time:YYYY-MM-DDTHH:mm:ss.SSS}", '
            '"level": "{level.name}", '
            '"message": "{message}", '
            '"module": "{module}", '
            '"function": "{function}", '
            '"line": {line}}}'
        ),
        level="DEBUG",
        rotation="100 MB",
        retention="30 days",
        compression="gz",
    )

    # Audit log (separate file for research integrity tracking)
    audit_log_file = settings.logs_path / "audit_{time:YYYY-MM-DD}.log"
    logger.add(
        audit_log_file,
        format=(
            '{{"timestamp": "{time:YYYY-MM-DDTHH:mm:ss.SSS}", '
            '"level": "{level.name}", '
            '"message": "{message}", '
            '"extra": {extra}}}'
        ),
        level="INFO",
        filter=lambda record: "audit" in record["extra"],
        rotation="50 MB",
        retention="1 year",  # Keep audit logs for publication compliance
    )


def get_logger(name: str = "smart_hes"):
    """Get a logger instance with the given name."""
    return logger.bind(module=name)


def audit_log(action: str, details: dict) -> None:
    """
    Log an audit event for research integrity tracking.

    All AI decisions, verification results, and data transformations
    should be logged here for publication compliance.
    """
    logger.bind(audit=True).info(
        f"AUDIT: {action}",
        extra={"action": action, "details": details}
    )
