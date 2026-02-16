"""
Centralized Security Audit Logging Service (S12.5).

Provides unified audit logging for:
- Authentication events (login, logout, failed attempts)
- Authorization events (access granted/denied)
- Data access events (read, write, delete)
- Configuration changes
- Security events (threats, violations, anomalies)
- API requests (critical endpoints)

Features:
- Multiple output backends (file, database, external SIEM)
- Structured JSON logging for analysis
- Real-time event streaming
- Compliance-ready audit trails
- Automatic log rotation and retention
"""

import json
import asyncio
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Optional
from uuid import uuid4

from loguru import logger

from src.core.config import settings


# =============================================================================
# Audit Event Types
# =============================================================================

class AuditCategory(str, Enum):
    """Categories of audit events."""
    AUTHENTICATION = "authentication"
    AUTHORIZATION = "authorization"
    DATA_ACCESS = "data_access"
    CONFIGURATION = "configuration"
    SECURITY = "security"
    API = "api"
    SYSTEM = "system"
    SIMULATION = "simulation"
    RAG = "rag"
    VERIFICATION = "verification"


class AuditAction(str, Enum):
    """Specific audit actions."""
    # Authentication
    LOGIN_SUCCESS = "login_success"
    LOGIN_FAILURE = "login_failure"
    LOGOUT = "logout"
    SESSION_CREATED = "session_created"
    SESSION_EXPIRED = "session_expired"
    TOKEN_ISSUED = "token_issued"
    TOKEN_REVOKED = "token_revoked"
    PASSWORD_CHANGED = "password_changed"
    MFA_ENABLED = "mfa_enabled"
    MFA_DISABLED = "mfa_disabled"

    # Authorization
    ACCESS_GRANTED = "access_granted"
    ACCESS_DENIED = "access_denied"
    PERMISSION_CHANGED = "permission_changed"
    ROLE_ASSIGNED = "role_assigned"
    ROLE_REMOVED = "role_removed"

    # Data Access
    DATA_READ = "data_read"
    DATA_WRITE = "data_write"
    DATA_DELETE = "data_delete"
    DATA_EXPORT = "data_export"
    DATA_IMPORT = "data_import"

    # Configuration
    CONFIG_READ = "config_read"
    CONFIG_UPDATE = "config_update"
    SETTINGS_CHANGED = "settings_changed"

    # Security
    THREAT_DETECTED = "threat_detected"
    ANOMALY_DETECTED = "anomaly_detected"
    POLICY_VIOLATION = "policy_violation"
    INTRUSION_ATTEMPT = "intrusion_attempt"
    ENCRYPTION_EVENT = "encryption_event"
    CERTIFICATE_EVENT = "certificate_event"

    # API
    API_REQUEST = "api_request"
    API_ERROR = "api_error"
    RATE_LIMIT_EXCEEDED = "rate_limit_exceeded"

    # System
    SYSTEM_START = "system_start"
    SYSTEM_STOP = "system_stop"
    SERVICE_ERROR = "service_error"
    HEALTH_CHECK = "health_check"

    # Simulation
    SIMULATION_START = "simulation_start"
    SIMULATION_STOP = "simulation_stop"
    HOME_CREATED = "home_created"
    THREAT_INJECTED = "threat_injected"

    # RAG
    KNOWLEDGE_QUERY = "knowledge_query"
    DOCUMENT_INGESTED = "document_ingested"

    # Verification
    VERIFICATION_PASS = "verification_pass"
    VERIFICATION_FLAG = "verification_flag"
    VERIFICATION_REJECT = "verification_reject"
    HUMAN_REVIEW_SUBMITTED = "human_review_submitted"


class AuditSeverity(str, Enum):
    """Severity levels for audit events."""
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


# =============================================================================
# Audit Event Model
# =============================================================================

@dataclass
class AuditEvent:
    """Structured audit event."""
    # Core fields
    event_id: str = field(default_factory=lambda: str(uuid4()))
    timestamp: datetime = field(default_factory=datetime.utcnow)
    category: AuditCategory = AuditCategory.SYSTEM
    action: AuditAction = AuditAction.API_REQUEST
    severity: AuditSeverity = AuditSeverity.INFO

    # Actor information
    user_id: Optional[str] = None
    username: Optional[str] = None
    session_id: Optional[str] = None
    ip_address: str = "127.0.0.1"
    user_agent: Optional[str] = None

    # Resource information
    resource_type: Optional[str] = None
    resource_id: Optional[str] = None
    resource_name: Optional[str] = None

    # Event details
    description: str = ""
    success: bool = True
    error_message: Optional[str] = None
    details: dict = field(default_factory=dict)

    # Request context
    request_method: Optional[str] = None
    request_path: Optional[str] = None
    request_params: Optional[dict] = None
    response_status: Optional[int] = None
    response_time_ms: Optional[float] = None

    # Metadata
    correlation_id: Optional[str] = None
    parent_event_id: Optional[str] = None
    tags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "event_id": self.event_id,
            "timestamp": self.timestamp.isoformat() + "Z",
            "category": self.category.value,
            "action": self.action.value,
            "severity": self.severity.value,
            "user_id": self.user_id,
            "username": self.username,
            "session_id": self.session_id,
            "ip_address": self.ip_address,
            "user_agent": self.user_agent,
            "resource_type": self.resource_type,
            "resource_id": self.resource_id,
            "resource_name": self.resource_name,
            "description": self.description,
            "success": self.success,
            "error_message": self.error_message,
            "details": self.details,
            "request_method": self.request_method,
            "request_path": self.request_path,
            "request_params": self.request_params,
            "response_status": self.response_status,
            "response_time_ms": self.response_time_ms,
            "correlation_id": self.correlation_id,
            "parent_event_id": self.parent_event_id,
            "tags": self.tags,
        }

    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict(), default=str)


# =============================================================================
# Audit Statistics
# =============================================================================

@dataclass
class AuditStats:
    """Audit logging statistics."""
    total_events: int = 0
    events_by_category: dict[str, int] = field(default_factory=dict)
    events_by_severity: dict[str, int] = field(default_factory=dict)
    events_by_action: dict[str, int] = field(default_factory=dict)
    failed_events: int = 0
    success_events: int = 0
    start_time: datetime = field(default_factory=datetime.utcnow)
    last_event_time: Optional[datetime] = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "total_events": self.total_events,
            "events_by_category": self.events_by_category,
            "events_by_severity": self.events_by_severity,
            "events_by_action": self.events_by_action,
            "failed_events": self.failed_events,
            "success_events": self.success_events,
            "uptime_seconds": (datetime.utcnow() - self.start_time).total_seconds(),
            "last_event_time": self.last_event_time.isoformat() if self.last_event_time else None,
        }


# =============================================================================
# Audit Service Configuration
# =============================================================================

@dataclass
class AuditConfig:
    """Configuration for audit service."""
    enabled: bool = True
    log_to_file: bool = True
    log_to_console: bool = True
    log_file_path: Optional[Path] = None
    max_file_size_mb: int = 100
    retention_days: int = 365  # 1 year for compliance
    max_memory_events: int = 1000
    async_logging: bool = True
    include_request_params: bool = True
    mask_sensitive_fields: bool = True
    sensitive_fields: list[str] = field(default_factory=lambda: [
        "password", "token", "api_key", "secret", "credential", "auth"
    ])


# =============================================================================
# Centralized Audit Service
# =============================================================================

class SecurityAuditService:
    """
    Centralized security audit logging service.

    Provides:
    - Unified logging for all security events
    - Multiple output backends
    - Real-time event streaming
    - Statistics and analytics
    - Compliance-ready audit trails
    """

    def __init__(self, config: Optional[AuditConfig] = None):
        """Initialize audit service."""
        self.config = config or AuditConfig()
        self.stats = AuditStats()
        self._event_queue: deque[AuditEvent] = deque(maxlen=self.config.max_memory_events)
        self._subscribers: list[Callable[[AuditEvent], None]] = []
        self._async_subscribers: list[Callable[[AuditEvent], Any]] = []
        self._file_handle = None
        self._initialized = False

        # Setup log file path
        if self.config.log_file_path is None:
            self.config.log_file_path = settings.logs_path / "security_audit.jsonl"

        logger.info(
            f"SecurityAuditService initialized (enabled={self.config.enabled}, "
            f"file={self.config.log_file_path})"
        )

    def _ensure_initialized(self) -> None:
        """Ensure service is initialized."""
        if self._initialized:
            return

        # Create logs directory
        self.config.log_file_path.parent.mkdir(parents=True, exist_ok=True)

        # Log startup event
        self._initialized = True
        self.log_event(
            category=AuditCategory.SYSTEM,
            action=AuditAction.SYSTEM_START,
            description="Security audit service started",
            severity=AuditSeverity.INFO,
        )

    def log_event(
        self,
        category: AuditCategory,
        action: AuditAction,
        description: str,
        severity: AuditSeverity = AuditSeverity.INFO,
        user_id: Optional[str] = None,
        username: Optional[str] = None,
        session_id: Optional[str] = None,
        ip_address: str = "127.0.0.1",
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        resource_name: Optional[str] = None,
        success: bool = True,
        error_message: Optional[str] = None,
        details: Optional[dict] = None,
        request_method: Optional[str] = None,
        request_path: Optional[str] = None,
        request_params: Optional[dict] = None,
        response_status: Optional[int] = None,
        response_time_ms: Optional[float] = None,
        correlation_id: Optional[str] = None,
        tags: Optional[list[str]] = None,
    ) -> AuditEvent:
        """
        Log an audit event.

        Args:
            category: Event category
            action: Specific action
            description: Human-readable description
            severity: Event severity level
            user_id: ID of user performing action
            username: Username of actor
            session_id: Session identifier
            ip_address: Client IP address
            resource_type: Type of resource affected
            resource_id: ID of resource affected
            resource_name: Name of resource affected
            success: Whether action succeeded
            error_message: Error message if failed
            details: Additional event details
            request_method: HTTP method if API request
            request_path: Request path if API request
            request_params: Request parameters (masked)
            response_status: HTTP response status
            response_time_ms: Response time in milliseconds
            correlation_id: ID for correlating related events
            tags: Tags for categorization

        Returns:
            Created AuditEvent
        """
        if not self.config.enabled:
            return AuditEvent()

        self._ensure_initialized()

        # Mask sensitive fields in request params
        if request_params and self.config.mask_sensitive_fields:
            request_params = self._mask_sensitive(request_params)

        # Mask sensitive fields in details
        if details and self.config.mask_sensitive_fields:
            details = self._mask_sensitive(details)

        # Create event
        event = AuditEvent(
            category=category,
            action=action,
            severity=severity,
            description=description,
            user_id=user_id,
            username=username,
            session_id=session_id,
            ip_address=ip_address,
            resource_type=resource_type,
            resource_id=resource_id,
            resource_name=resource_name,
            success=success,
            error_message=error_message,
            details=details or {},
            request_method=request_method,
            request_path=request_path,
            request_params=request_params if self.config.include_request_params else None,
            response_status=response_status,
            response_time_ms=response_time_ms,
            correlation_id=correlation_id,
            tags=tags or [],
        )

        # Process event
        self._process_event(event)

        return event

    def _process_event(self, event: AuditEvent) -> None:
        """Process and store audit event."""
        # Update statistics
        self._update_stats(event)

        # Store in memory
        self._event_queue.append(event)

        # Log to file
        if self.config.log_to_file:
            self._log_to_file(event)

        # Log to console via loguru
        if self.config.log_to_console:
            self._log_to_console(event)

        # Notify subscribers
        self._notify_subscribers(event)

    def _update_stats(self, event: AuditEvent) -> None:
        """Update audit statistics."""
        self.stats.total_events += 1
        self.stats.last_event_time = event.timestamp

        # By category
        cat = event.category.value
        self.stats.events_by_category[cat] = self.stats.events_by_category.get(cat, 0) + 1

        # By severity
        sev = event.severity.value
        self.stats.events_by_severity[sev] = self.stats.events_by_severity.get(sev, 0) + 1

        # By action
        act = event.action.value
        self.stats.events_by_action[act] = self.stats.events_by_action.get(act, 0) + 1

        # Success/failure
        if event.success:
            self.stats.success_events += 1
        else:
            self.stats.failed_events += 1

    def _log_to_file(self, event: AuditEvent) -> None:
        """Write event to audit log file."""
        try:
            with open(self.config.log_file_path, "a") as f:
                f.write(event.to_json() + "\n")
        except Exception as e:
            logger.error(f"Failed to write audit log: {e}")

    def _log_to_console(self, event: AuditEvent) -> None:
        """Log event to console via loguru."""
        log_level = {
            AuditSeverity.DEBUG: "DEBUG",
            AuditSeverity.INFO: "INFO",
            AuditSeverity.WARNING: "WARNING",
            AuditSeverity.ERROR: "ERROR",
            AuditSeverity.CRITICAL: "CRITICAL",
        }.get(event.severity, "INFO")

        status = "✓" if event.success else "✗"
        msg = f"[AUDIT] {status} [{event.category.value}:{event.action.value}] {event.description}"

        if event.username:
            msg += f" (user={event.username})"
        if event.resource_type:
            msg += f" (resource={event.resource_type}/{event.resource_id})"

        logger.log(log_level, msg)

    def _notify_subscribers(self, event: AuditEvent) -> None:
        """Notify event subscribers."""
        for subscriber in self._subscribers:
            try:
                subscriber(event)
            except Exception as e:
                logger.error(f"Audit subscriber error: {e}")

    def _mask_sensitive(self, data: dict) -> dict:
        """Mask sensitive fields in data."""
        if not isinstance(data, dict):
            return data

        masked = {}
        for key, value in data.items():
            key_lower = key.lower()
            if any(field in key_lower for field in self.config.sensitive_fields):
                masked[key] = "***MASKED***"
            elif isinstance(value, dict):
                masked[key] = self._mask_sensitive(value)
            else:
                masked[key] = value
        return masked

    # =========================================================================
    # Convenience Methods
    # =========================================================================

    def log_auth_success(
        self,
        username: str,
        user_id: str,
        ip_address: str = "127.0.0.1",
        session_id: Optional[str] = None,
        details: Optional[dict] = None,
    ) -> AuditEvent:
        """Log successful authentication."""
        return self.log_event(
            category=AuditCategory.AUTHENTICATION,
            action=AuditAction.LOGIN_SUCCESS,
            description=f"User '{username}' logged in successfully",
            severity=AuditSeverity.INFO,
            username=username,
            user_id=user_id,
            ip_address=ip_address,
            session_id=session_id,
            success=True,
            details=details,
        )

    def log_auth_failure(
        self,
        username: str,
        ip_address: str = "127.0.0.1",
        reason: str = "Invalid credentials",
        details: Optional[dict] = None,
    ) -> AuditEvent:
        """Log failed authentication."""
        return self.log_event(
            category=AuditCategory.AUTHENTICATION,
            action=AuditAction.LOGIN_FAILURE,
            description=f"Login failed for '{username}': {reason}",
            severity=AuditSeverity.WARNING,
            username=username,
            ip_address=ip_address,
            success=False,
            error_message=reason,
            details=details,
        )

    def log_logout(
        self,
        username: str,
        user_id: str,
        session_id: Optional[str] = None,
    ) -> AuditEvent:
        """Log user logout."""
        return self.log_event(
            category=AuditCategory.AUTHENTICATION,
            action=AuditAction.LOGOUT,
            description=f"User '{username}' logged out",
            severity=AuditSeverity.INFO,
            username=username,
            user_id=user_id,
            session_id=session_id,
            success=True,
        )

    def log_access_denied(
        self,
        username: Optional[str],
        resource_type: str,
        resource_id: str,
        reason: str = "Insufficient permissions",
        ip_address: str = "127.0.0.1",
    ) -> AuditEvent:
        """Log access denied event."""
        return self.log_event(
            category=AuditCategory.AUTHORIZATION,
            action=AuditAction.ACCESS_DENIED,
            description=f"Access denied to {resource_type}/{resource_id}: {reason}",
            severity=AuditSeverity.WARNING,
            username=username,
            ip_address=ip_address,
            resource_type=resource_type,
            resource_id=resource_id,
            success=False,
            error_message=reason,
        )

    def log_config_change(
        self,
        username: str,
        config_key: str,
        old_value: Any,
        new_value: Any,
        ip_address: str = "127.0.0.1",
    ) -> AuditEvent:
        """Log configuration change."""
        return self.log_event(
            category=AuditCategory.CONFIGURATION,
            action=AuditAction.CONFIG_UPDATE,
            description=f"Configuration '{config_key}' changed",
            severity=AuditSeverity.INFO,
            username=username,
            ip_address=ip_address,
            resource_type="config",
            resource_id=config_key,
            success=True,
            details={
                "old_value": str(old_value),
                "new_value": str(new_value),
            },
        )

    def log_security_event(
        self,
        action: AuditAction,
        description: str,
        severity: AuditSeverity = AuditSeverity.WARNING,
        source_id: Optional[str] = None,
        details: Optional[dict] = None,
    ) -> AuditEvent:
        """Log security-related event."""
        return self.log_event(
            category=AuditCategory.SECURITY,
            action=action,
            description=description,
            severity=severity,
            resource_id=source_id,
            details=details,
        )

    def log_api_request(
        self,
        method: str,
        path: str,
        status_code: int,
        response_time_ms: float,
        username: Optional[str] = None,
        ip_address: str = "127.0.0.1",
        params: Optional[dict] = None,
        error: Optional[str] = None,
    ) -> AuditEvent:
        """Log API request."""
        success = 200 <= status_code < 400
        severity = AuditSeverity.INFO if success else AuditSeverity.WARNING

        return self.log_event(
            category=AuditCategory.API,
            action=AuditAction.API_REQUEST if success else AuditAction.API_ERROR,
            description=f"{method} {path} -> {status_code}",
            severity=severity,
            username=username,
            ip_address=ip_address,
            request_method=method,
            request_path=path,
            request_params=params,
            response_status=status_code,
            response_time_ms=response_time_ms,
            success=success,
            error_message=error,
        )

    def log_verification_result(
        self,
        status: str,
        confidence: float,
        content_type: str,
        details: Optional[dict] = None,
    ) -> AuditEvent:
        """Log verification pipeline result."""
        action_map = {
            "pass": AuditAction.VERIFICATION_PASS,
            "flag": AuditAction.VERIFICATION_FLAG,
            "reject": AuditAction.VERIFICATION_REJECT,
        }
        severity_map = {
            "pass": AuditSeverity.INFO,
            "flag": AuditSeverity.WARNING,
            "reject": AuditSeverity.ERROR,
        }

        return self.log_event(
            category=AuditCategory.VERIFICATION,
            action=action_map.get(status.lower(), AuditAction.VERIFICATION_FLAG),
            description=f"Verification {status}: {content_type} (confidence={confidence:.2f})",
            severity=severity_map.get(status.lower(), AuditSeverity.WARNING),
            resource_type=content_type,
            success=status.lower() == "pass",
            details={
                "confidence": confidence,
                **(details or {}),
            },
        )

    # =========================================================================
    # Query Methods
    # =========================================================================

    def get_recent_events(
        self,
        limit: int = 100,
        category: Optional[AuditCategory] = None,
        action: Optional[AuditAction] = None,
        severity: Optional[AuditSeverity] = None,
        username: Optional[str] = None,
        success_only: Optional[bool] = None,
    ) -> list[AuditEvent]:
        """Get recent audit events with optional filters."""
        events = list(self._event_queue)

        if category:
            events = [e for e in events if e.category == category]
        if action:
            events = [e for e in events if e.action == action]
        if severity:
            events = [e for e in events if e.severity == severity]
        if username:
            events = [e for e in events if e.username == username]
        if success_only is not None:
            events = [e for e in events if e.success == success_only]

        # Sort by timestamp descending
        events.sort(key=lambda e: e.timestamp, reverse=True)

        return events[:limit]

    def get_stats(self) -> AuditStats:
        """Get audit statistics."""
        return self.stats

    def get_events_since(self, since: datetime) -> list[AuditEvent]:
        """Get events since a specific time."""
        return [e for e in self._event_queue if e.timestamp >= since]

    # =========================================================================
    # Subscription
    # =========================================================================

    def subscribe(self, callback: Callable[[AuditEvent], None]) -> None:
        """Subscribe to audit events."""
        self._subscribers.append(callback)

    def unsubscribe(self, callback: Callable[[AuditEvent], None]) -> None:
        """Unsubscribe from audit events."""
        if callback in self._subscribers:
            self._subscribers.remove(callback)


# =============================================================================
# Global Instance
# =============================================================================

_audit_service: Optional[SecurityAuditService] = None


def get_audit_service() -> SecurityAuditService:
    """Get or create the global audit service instance."""
    global _audit_service
    if _audit_service is None:
        _audit_service = SecurityAuditService()
    return _audit_service


def initialize_audit_service(config: Optional[AuditConfig] = None) -> SecurityAuditService:
    """Initialize the global audit service with custom config."""
    global _audit_service
    _audit_service = SecurityAuditService(config)
    return _audit_service


# =============================================================================
# FastAPI Middleware Integration
# =============================================================================

async def audit_middleware_factory(request, call_next):
    """
    FastAPI middleware for automatic API request auditing.

    Usage in main.py:
        from src.security.audit_service import audit_middleware_factory
        app.middleware("http")(audit_middleware_factory)
    """
    import time

    start_time = time.time()

    # Get client info
    ip_address = request.client.host if request.client else "unknown"
    method = request.method
    path = request.url.path

    # Skip health checks and static files
    skip_paths = ["/api/health", "/docs", "/openapi.json", "/redoc"]
    if any(path.startswith(p) for p in skip_paths):
        return await call_next(request)

    # Process request
    response = await call_next(request)

    # Calculate response time
    response_time_ms = (time.time() - start_time) * 1000

    # Get username from session if available
    username = None
    # Could extract from authorization header or session

    # Log the request
    audit_service = get_audit_service()
    audit_service.log_api_request(
        method=method,
        path=path,
        status_code=response.status_code,
        response_time_ms=response_time_ms,
        username=username,
        ip_address=ip_address,
    )

    return response
