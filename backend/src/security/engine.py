"""
Security & Privacy Engine - Central orchestrator for IoT security simulation.

Sprint 12 - S12.1: Create SecurityPrivacyEngine class

Features:
- Centralized security management
- Security event logging and auditing
- Policy enforcement
- Threat detection integration
- Privacy controls
"""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Coroutine, Optional
from uuid import uuid4
from loguru import logger


class SecurityLevel(str, Enum):
    """Security levels for devices and communications."""
    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class SecurityEventType(str, Enum):
    """Types of security events."""
    # Authentication events
    AUTH_SUCCESS = "auth_success"
    AUTH_FAILURE = "auth_failure"
    AUTH_LOCKOUT = "auth_lockout"
    TOKEN_ISSUED = "token_issued"
    TOKEN_REVOKED = "token_revoked"
    TOKEN_EXPIRED = "token_expired"

    # TLS events
    TLS_HANDSHAKE_START = "tls_handshake_start"
    TLS_HANDSHAKE_SUCCESS = "tls_handshake_success"
    TLS_HANDSHAKE_FAILURE = "tls_handshake_failure"
    CERTIFICATE_EXPIRED = "certificate_expired"
    CERTIFICATE_INVALID = "certificate_invalid"

    # Encryption events
    ENCRYPTION_SUCCESS = "encryption_success"
    ENCRYPTION_FAILURE = "encryption_failure"
    DECRYPTION_SUCCESS = "decryption_success"
    DECRYPTION_FAILURE = "decryption_failure"
    KEY_GENERATED = "key_generated"
    KEY_ROTATED = "key_rotated"

    # Network events
    CONNECTION_ESTABLISHED = "connection_established"
    CONNECTION_TERMINATED = "connection_terminated"
    SUSPICIOUS_TRAFFIC = "suspicious_traffic"
    INTRUSION_DETECTED = "intrusion_detected"

    # Privacy events
    DATA_ANONYMIZED = "data_anonymized"
    PRIVACY_VIOLATION = "privacy_violation"
    CONSENT_GRANTED = "consent_granted"
    CONSENT_REVOKED = "consent_revoked"

    # Policy events
    POLICY_VIOLATION = "policy_violation"
    POLICY_UPDATED = "policy_updated"
    ACCESS_DENIED = "access_denied"
    ACCESS_GRANTED = "access_granted"


@dataclass
class SecurityEvent:
    """Security event record."""
    id: str = field(default_factory=lambda: str(uuid4()))
    event_type: SecurityEventType = SecurityEventType.AUTH_SUCCESS
    timestamp: datetime = field(default_factory=datetime.now)
    source_id: str = ""
    source_type: str = ""  # device, user, service, network
    target_id: Optional[str] = None
    target_type: Optional[str] = None
    severity: SecurityLevel = SecurityLevel.LOW
    success: bool = True
    details: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "event_type": self.event_type.value,
            "timestamp": self.timestamp.isoformat(),
            "source_id": self.source_id,
            "source_type": self.source_type,
            "target_id": self.target_id,
            "target_type": self.target_type,
            "severity": self.severity.value,
            "success": self.success,
            "details": self.details,
            "metadata": self.metadata,
        }


@dataclass
class SecurityPolicy:
    """Security policy definition."""
    id: str = field(default_factory=lambda: str(uuid4()))
    name: str = ""
    description: str = ""
    enabled: bool = True
    # Policy rules
    min_security_level: SecurityLevel = SecurityLevel.LOW
    require_tls: bool = True
    require_authentication: bool = True
    max_failed_auth_attempts: int = 5
    session_timeout_minutes: int = 60
    require_encryption: bool = True
    allowed_cipher_suites: list[str] = field(default_factory=list)
    # Privacy rules
    require_consent: bool = True
    data_retention_days: int = 90
    allow_data_sharing: bool = False
    anonymization_required: bool = False


@dataclass
class SecurityConfig:
    """Configuration for security engine."""
    enabled: bool = True
    default_security_level: SecurityLevel = SecurityLevel.MEDIUM
    # Logging
    log_all_events: bool = True
    max_event_history: int = 10000
    # Alerts
    alert_on_failure: bool = True
    alert_threshold: int = 3  # Consecutive failures
    # Simulation
    simulation_mode: bool = True
    simulate_latency: bool = True
    latency_ms: int = 50


@dataclass
class SecurityStats:
    """Security statistics."""
    total_events: int = 0
    auth_successes: int = 0
    auth_failures: int = 0
    tls_handshakes: int = 0
    encryption_operations: int = 0
    policy_violations: int = 0
    intrusions_detected: int = 0
    privacy_violations: int = 0
    start_time: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "total_events": self.total_events,
            "auth_successes": self.auth_successes,
            "auth_failures": self.auth_failures,
            "tls_handshakes": self.tls_handshakes,
            "encryption_operations": self.encryption_operations,
            "policy_violations": self.policy_violations,
            "intrusions_detected": self.intrusions_detected,
            "privacy_violations": self.privacy_violations,
            "uptime_seconds": (datetime.now() - self.start_time).total_seconds(),
        }


# Type aliases
EventCallback = Callable[[SecurityEvent], None]
AsyncEventCallback = Callable[[SecurityEvent], Coroutine[Any, Any, None]]


class SecurityPrivacyEngine:
    """
    Central Security & Privacy Engine for IoT simulation.

    Provides:
    - Unified security event management
    - Policy enforcement
    - TLS/Authentication/Encryption coordination
    - Privacy controls
    - Audit logging
    """

    def __init__(self, config: Optional[SecurityConfig] = None):
        """
        Initialize security engine.

        Args:
            config: Security configuration
        """
        self.config = config or SecurityConfig()
        self.stats = SecurityStats()
        self._running = False

        # Event storage
        self._events: list[SecurityEvent] = []
        self._event_callbacks: list[EventCallback | AsyncEventCallback] = []

        # Policies
        self._policies: dict[str, SecurityPolicy] = {}
        self._default_policy = SecurityPolicy(
            id="default",
            name="Default Security Policy",
            description="Standard security policy for IoT devices",
        )

        # Component references (set by managers)
        self._tls_manager = None
        self._auth_manager = None
        self._encryption_engine = None
        self._privacy_engine = None

        # Device security states
        self._device_states: dict[str, dict[str, Any]] = {}

        # Alert tracking
        self._failure_counts: dict[str, int] = {}

        logger.info("SecurityPrivacyEngine initialized")

    @property
    def is_running(self) -> bool:
        return self._running

    async def start(self) -> None:
        """Start the security engine."""
        logger.info("Starting SecurityPrivacyEngine")
        self._running = True
        self.stats.start_time = datetime.now()

        # Log startup event
        await self.log_event(SecurityEvent(
            event_type=SecurityEventType.POLICY_UPDATED,
            source_id="security_engine",
            source_type="service",
            severity=SecurityLevel.LOW,
            details={"action": "engine_started"},
        ))

        logger.info("SecurityPrivacyEngine started")

    async def stop(self) -> None:
        """Stop the security engine."""
        logger.info("Stopping SecurityPrivacyEngine")
        self._running = False

        # Log shutdown event
        await self.log_event(SecurityEvent(
            event_type=SecurityEventType.POLICY_UPDATED,
            source_id="security_engine",
            source_type="service",
            severity=SecurityLevel.LOW,
            details={"action": "engine_stopped"},
        ))

        logger.info("SecurityPrivacyEngine stopped")

    def register_tls_manager(self, manager: Any) -> None:
        """Register TLS manager."""
        self._tls_manager = manager
        logger.debug("TLS manager registered")

    def register_auth_manager(self, manager: Any) -> None:
        """Register authentication manager."""
        self._auth_manager = manager
        logger.debug("Auth manager registered")

    def register_encryption_engine(self, engine: Any) -> None:
        """Register encryption engine."""
        self._encryption_engine = engine
        logger.debug("Encryption engine registered")

    def register_privacy_engine(self, engine: Any) -> None:
        """Register privacy engine."""
        self._privacy_engine = engine
        logger.debug("Privacy engine registered")

    def add_event_callback(self, callback: EventCallback | AsyncEventCallback) -> None:
        """Add callback for security events."""
        self._event_callbacks.append(callback)

    def remove_event_callback(self, callback: EventCallback | AsyncEventCallback) -> None:
        """Remove event callback."""
        if callback in self._event_callbacks:
            self._event_callbacks.remove(callback)

    async def log_event(self, event: SecurityEvent) -> None:
        """
        Log a security event.

        Args:
            event: Security event to log
        """
        if not self.config.enabled:
            return

        # Store event
        if self.config.log_all_events:
            self._events.append(event)

            # Trim if over limit
            if len(self._events) > self.config.max_event_history:
                self._events = self._events[-self.config.max_event_history:]

        # Update stats
        self.stats.total_events += 1
        self._update_stats(event)

        # Check for alerts
        if self.config.alert_on_failure and not event.success:
            await self._check_alert(event)

        # Notify callbacks
        for callback in self._event_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(event)
                else:
                    callback(event)
            except Exception as e:
                logger.error(f"Event callback error: {e}")

        # Log to file
        logger.debug(f"Security event: {event.event_type.value} from {event.source_id}")

    def _update_stats(self, event: SecurityEvent) -> None:
        """Update statistics based on event."""
        if event.event_type == SecurityEventType.AUTH_SUCCESS:
            self.stats.auth_successes += 1
        elif event.event_type == SecurityEventType.AUTH_FAILURE:
            self.stats.auth_failures += 1
        elif event.event_type in (SecurityEventType.TLS_HANDSHAKE_SUCCESS,
                                   SecurityEventType.TLS_HANDSHAKE_FAILURE):
            self.stats.tls_handshakes += 1
        elif event.event_type in (SecurityEventType.ENCRYPTION_SUCCESS,
                                   SecurityEventType.DECRYPTION_SUCCESS):
            self.stats.encryption_operations += 1
        elif event.event_type == SecurityEventType.POLICY_VIOLATION:
            self.stats.policy_violations += 1
        elif event.event_type == SecurityEventType.INTRUSION_DETECTED:
            self.stats.intrusions_detected += 1
        elif event.event_type == SecurityEventType.PRIVACY_VIOLATION:
            self.stats.privacy_violations += 1

    async def _check_alert(self, event: SecurityEvent) -> None:
        """Check if alert should be triggered."""
        key = f"{event.source_id}:{event.event_type.value}"
        self._failure_counts[key] = self._failure_counts.get(key, 0) + 1

        if self._failure_counts[key] >= self.config.alert_threshold:
            logger.warning(
                f"SECURITY ALERT: {self.config.alert_threshold} consecutive "
                f"{event.event_type.value} failures from {event.source_id}"
            )
            # Reset counter
            self._failure_counts[key] = 0

    # Policy Management

    def add_policy(self, policy: SecurityPolicy) -> None:
        """Add a security policy."""
        self._policies[policy.id] = policy
        logger.info(f"Security policy added: {policy.name}")

    def remove_policy(self, policy_id: str) -> bool:
        """Remove a security policy."""
        if policy_id in self._policies:
            del self._policies[policy_id]
            return True
        return False

    def get_policy(self, policy_id: str) -> Optional[SecurityPolicy]:
        """Get a security policy."""
        return self._policies.get(policy_id, self._default_policy)

    async def check_policy(
        self,
        device_id: str,
        action: str,
        context: dict[str, Any],
    ) -> tuple[bool, Optional[str]]:
        """
        Check if action is allowed by policy.

        Args:
            device_id: Device attempting action
            action: Action being attempted
            context: Action context

        Returns:
            (allowed, violation_reason)
        """
        policy = self._get_device_policy(device_id)

        if not policy.enabled:
            return True, None

        # Check security level
        device_level = context.get("security_level", SecurityLevel.NONE)
        if isinstance(device_level, str):
            device_level = SecurityLevel(device_level)

        level_order = [SecurityLevel.NONE, SecurityLevel.LOW,
                       SecurityLevel.MEDIUM, SecurityLevel.HIGH, SecurityLevel.CRITICAL]

        if level_order.index(device_level) < level_order.index(policy.min_security_level):
            await self.log_event(SecurityEvent(
                event_type=SecurityEventType.POLICY_VIOLATION,
                source_id=device_id,
                source_type="device",
                severity=SecurityLevel.MEDIUM,
                success=False,
                details={
                    "action": action,
                    "violation": "insufficient_security_level",
                    "required": policy.min_security_level.value,
                    "actual": device_level.value,
                },
            ))
            return False, f"Insufficient security level: {device_level.value} < {policy.min_security_level.value}"

        # Check TLS requirement
        if policy.require_tls and not context.get("tls_enabled", False):
            await self.log_event(SecurityEvent(
                event_type=SecurityEventType.POLICY_VIOLATION,
                source_id=device_id,
                source_type="device",
                severity=SecurityLevel.MEDIUM,
                success=False,
                details={"action": action, "violation": "tls_required"},
            ))
            return False, "TLS is required but not enabled"

        # Check authentication requirement
        if policy.require_authentication and not context.get("authenticated", False):
            await self.log_event(SecurityEvent(
                event_type=SecurityEventType.ACCESS_DENIED,
                source_id=device_id,
                source_type="device",
                severity=SecurityLevel.MEDIUM,
                success=False,
                details={"action": action, "violation": "authentication_required"},
            ))
            return False, "Authentication required"

        # Check encryption requirement
        if policy.require_encryption and not context.get("encrypted", False):
            await self.log_event(SecurityEvent(
                event_type=SecurityEventType.POLICY_VIOLATION,
                source_id=device_id,
                source_type="device",
                severity=SecurityLevel.MEDIUM,
                success=False,
                details={"action": action, "violation": "encryption_required"},
            ))
            return False, "Encryption is required but not enabled"

        # Log successful access
        await self.log_event(SecurityEvent(
            event_type=SecurityEventType.ACCESS_GRANTED,
            source_id=device_id,
            source_type="device",
            severity=SecurityLevel.LOW,
            success=True,
            details={"action": action},
        ))

        return True, None

    def _get_device_policy(self, device_id: str) -> SecurityPolicy:
        """Get policy for a device."""
        # Check if device has specific policy
        device_state = self._device_states.get(device_id, {})
        policy_id = device_state.get("policy_id")

        if policy_id and policy_id in self._policies:
            return self._policies[policy_id]

        return self._default_policy

    # Device Security State Management

    def set_device_state(
        self,
        device_id: str,
        state: dict[str, Any],
    ) -> None:
        """Set security state for a device."""
        if device_id not in self._device_states:
            self._device_states[device_id] = {}
        self._device_states[device_id].update(state)

    def get_device_state(self, device_id: str) -> dict[str, Any]:
        """Get security state for a device."""
        return self._device_states.get(device_id, {})

    def clear_device_state(self, device_id: str) -> None:
        """Clear security state for a device."""
        if device_id in self._device_states:
            del self._device_states[device_id]

    # Event Queries

    def get_events(
        self,
        event_type: Optional[SecurityEventType] = None,
        source_id: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        severity: Optional[SecurityLevel] = None,
        success_only: Optional[bool] = None,
        limit: int = 100,
    ) -> list[SecurityEvent]:
        """
        Get filtered security events.

        Args:
            event_type: Filter by event type
            source_id: Filter by source
            start_time: Filter by start time
            end_time: Filter by end time
            severity: Filter by severity level
            success_only: Filter by success status
            limit: Maximum events to return

        Returns:
            List of matching events
        """
        events = self._events

        if event_type:
            events = [e for e in events if e.event_type == event_type]

        if source_id:
            events = [e for e in events if e.source_id == source_id]

        if start_time:
            events = [e for e in events if e.timestamp >= start_time]

        if end_time:
            events = [e for e in events if e.timestamp <= end_time]

        if severity:
            events = [e for e in events if e.severity == severity]

        if success_only is not None:
            events = [e for e in events if e.success == success_only]

        return events[-limit:]

    def get_stats(self) -> dict[str, Any]:
        """Get security statistics."""
        return {
            "engine": {
                "running": self._running,
                "enabled": self.config.enabled,
                "simulation_mode": self.config.simulation_mode,
            },
            "stats": self.stats.to_dict(),
            "policies": len(self._policies),
            "devices": len(self._device_states),
            "events_stored": len(self._events),
        }

    def export_audit_log(self) -> list[dict[str, Any]]:
        """Export all events as audit log."""
        return [e.to_dict() for e in self._events]
