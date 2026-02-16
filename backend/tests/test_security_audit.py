"""
Tests for Centralized Security Audit Logging Service (S12.5).

Tests:
- AuditService initialization
- Event logging
- Event filtering
- Statistics tracking
- Convenience methods
- Integration with admin API
"""

import pytest
import sys
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch
from pathlib import Path
import tempfile

# Mock chromadb before imports
sys.modules['chromadb'] = MagicMock()
sys.modules['chromadb.config'] = MagicMock()


class TestAuditServiceCore:
    """Test core audit service functionality."""

    def test_service_initialization(self):
        """Test service initializes correctly."""
        from src.security.audit_service import (
            SecurityAuditService,
            AuditConfig,
        )

        config = AuditConfig(
            enabled=True,
            log_to_file=False,
            log_to_console=False,
        )

        service = SecurityAuditService(config)
        assert service is not None
        assert service.config.enabled is True

    def test_log_event_basic(self):
        """Test basic event logging."""
        from src.security.audit_service import (
            SecurityAuditService,
            AuditConfig,
            AuditCategory,
            AuditAction,
            AuditSeverity,
        )

        config = AuditConfig(enabled=True, log_to_file=False, log_to_console=False)
        service = SecurityAuditService(config)

        event = service.log_event(
            category=AuditCategory.AUTHENTICATION,
            action=AuditAction.LOGIN_SUCCESS,
            description="Test login",
            username="testuser",
            ip_address="192.168.1.1",
        )

        assert event is not None
        assert event.category == AuditCategory.AUTHENTICATION
        assert event.action == AuditAction.LOGIN_SUCCESS
        assert event.username == "testuser"

    def test_log_event_disabled(self):
        """Test logging when disabled."""
        from src.security.audit_service import (
            SecurityAuditService,
            AuditConfig,
            AuditCategory,
            AuditAction,
        )

        config = AuditConfig(enabled=False)
        service = SecurityAuditService(config)

        event = service.log_event(
            category=AuditCategory.AUTHENTICATION,
            action=AuditAction.LOGIN_SUCCESS,
            description="Test",
        )

        # Should return empty event when disabled
        assert event.event_id is not None

    def test_statistics_tracking(self):
        """Test that statistics are updated."""
        from src.security.audit_service import (
            SecurityAuditService,
            AuditConfig,
            AuditCategory,
            AuditAction,
            AuditSeverity,
        )

        config = AuditConfig(enabled=True, log_to_file=False, log_to_console=False)
        service = SecurityAuditService(config)

        # Log some events
        service.log_event(
            category=AuditCategory.AUTHENTICATION,
            action=AuditAction.LOGIN_SUCCESS,
            description="Success",
            success=True,
        )
        service.log_event(
            category=AuditCategory.AUTHENTICATION,
            action=AuditAction.LOGIN_FAILURE,
            description="Failure",
            success=False,
        )

        stats = service.get_stats()
        assert stats.total_events >= 2
        assert stats.success_events >= 1
        assert stats.failed_events >= 1

    def test_event_filtering(self):
        """Test filtering events."""
        from src.security.audit_service import (
            SecurityAuditService,
            AuditConfig,
            AuditCategory,
            AuditAction,
        )

        config = AuditConfig(enabled=True, log_to_file=False, log_to_console=False)
        service = SecurityAuditService(config)

        # Log different events
        service.log_event(
            category=AuditCategory.AUTHENTICATION,
            action=AuditAction.LOGIN_SUCCESS,
            description="Auth event",
            username="user1",
        )
        service.log_event(
            category=AuditCategory.CONFIGURATION,
            action=AuditAction.CONFIG_UPDATE,
            description="Config event",
            username="admin",
        )

        # Filter by category
        auth_events = service.get_recent_events(
            category=AuditCategory.AUTHENTICATION
        )
        assert all(e.category == AuditCategory.AUTHENTICATION for e in auth_events)

        # Filter by username
        admin_events = service.get_recent_events(username="admin")
        assert all(e.username == "admin" for e in admin_events)


class TestAuditConvenienceMethods:
    """Test convenience logging methods."""

    def test_log_auth_success(self):
        """Test auth success logging."""
        from src.security.audit_service import (
            SecurityAuditService,
            AuditConfig,
            AuditAction,
        )

        config = AuditConfig(enabled=True, log_to_file=False, log_to_console=False)
        service = SecurityAuditService(config)

        event = service.log_auth_success(
            username="testuser",
            user_id="user-123",
            ip_address="10.0.0.1",
        )

        assert event.action == AuditAction.LOGIN_SUCCESS
        assert event.username == "testuser"
        assert event.success is True

    def test_log_auth_failure(self):
        """Test auth failure logging."""
        from src.security.audit_service import (
            SecurityAuditService,
            AuditConfig,
            AuditAction,
        )

        config = AuditConfig(enabled=True, log_to_file=False, log_to_console=False)
        service = SecurityAuditService(config)

        event = service.log_auth_failure(
            username="baduser",
            reason="Invalid password",
        )

        assert event.action == AuditAction.LOGIN_FAILURE
        assert event.success is False
        assert "Invalid password" in event.error_message

    def test_log_access_denied(self):
        """Test access denied logging."""
        from src.security.audit_service import (
            SecurityAuditService,
            AuditConfig,
            AuditAction,
        )

        config = AuditConfig(enabled=True, log_to_file=False, log_to_console=False)
        service = SecurityAuditService(config)

        event = service.log_access_denied(
            username="restricted_user",
            resource_type="admin_panel",
            resource_id="panel-1",
            reason="Insufficient permissions",
        )

        assert event.action == AuditAction.ACCESS_DENIED
        assert event.resource_type == "admin_panel"
        assert event.success is False

    def test_log_config_change(self):
        """Test config change logging."""
        from src.security.audit_service import (
            SecurityAuditService,
            AuditConfig,
            AuditAction,
        )

        config = AuditConfig(enabled=True, log_to_file=False, log_to_console=False)
        service = SecurityAuditService(config)

        event = service.log_config_change(
            username="admin",
            config_key="security.timeout",
            old_value=3600,
            new_value=7200,
        )

        assert event.action == AuditAction.CONFIG_UPDATE
        assert event.resource_type == "config"
        assert "3600" in str(event.details.get("old_value"))

    def test_log_api_request(self):
        """Test API request logging."""
        from src.security.audit_service import (
            SecurityAuditService,
            AuditConfig,
            AuditAction,
        )

        config = AuditConfig(enabled=True, log_to_file=False, log_to_console=False)
        service = SecurityAuditService(config)

        event = service.log_api_request(
            method="POST",
            path="/api/login",
            status_code=200,
            response_time_ms=45.5,
            username="testuser",
        )

        assert event.action == AuditAction.API_REQUEST
        assert event.request_method == "POST"
        assert event.request_path == "/api/login"
        assert event.response_status == 200
        assert event.success is True

    def test_log_verification_result(self):
        """Test verification result logging."""
        from src.security.audit_service import (
            SecurityAuditService,
            AuditConfig,
            AuditAction,
        )

        config = AuditConfig(enabled=True, log_to_file=False, log_to_console=False)
        service = SecurityAuditService(config)

        event = service.log_verification_result(
            status="flag",
            confidence=0.72,
            content_type="llm_response",
        )

        assert event.action == AuditAction.VERIFICATION_FLAG
        assert event.details.get("confidence") == 0.72


class TestSensitiveDataMasking:
    """Test sensitive data masking."""

    def test_password_masking(self):
        """Test password fields are masked."""
        from src.security.audit_service import (
            SecurityAuditService,
            AuditConfig,
            AuditCategory,
            AuditAction,
        )

        config = AuditConfig(
            enabled=True,
            log_to_file=False,
            log_to_console=False,
            mask_sensitive_fields=True,
        )
        service = SecurityAuditService(config)

        event = service.log_event(
            category=AuditCategory.AUTHENTICATION,
            action=AuditAction.LOGIN_SUCCESS,
            description="Login",
            details={"password": "secret123", "username": "user"},
        )

        assert event.details.get("password") == "***MASKED***"
        assert event.details.get("username") == "user"

    def test_api_key_masking(self):
        """Test API key fields are masked."""
        from src.security.audit_service import (
            SecurityAuditService,
            AuditConfig,
            AuditCategory,
            AuditAction,
        )

        config = AuditConfig(
            enabled=True,
            log_to_file=False,
            log_to_console=False,
            mask_sensitive_fields=True,
        )
        service = SecurityAuditService(config)

        event = service.log_event(
            category=AuditCategory.SECURITY,
            action=AuditAction.TOKEN_ISSUED,
            description="Token",
            request_params={"api_key": "sk_live_abc123"},
        )

        assert event.request_params.get("api_key") == "***MASKED***"


class TestAuditEventModel:
    """Test AuditEvent model."""

    def test_to_dict(self):
        """Test event serialization to dict."""
        from src.security.audit_service import (
            AuditEvent,
            AuditCategory,
            AuditAction,
            AuditSeverity,
        )

        event = AuditEvent(
            category=AuditCategory.AUTHENTICATION,
            action=AuditAction.LOGIN_SUCCESS,
            severity=AuditSeverity.INFO,
            description="Test event",
            username="testuser",
        )

        data = event.to_dict()

        assert data["category"] == "authentication"
        assert data["action"] == "login_success"
        assert data["username"] == "testuser"
        assert "timestamp" in data

    def test_to_json(self):
        """Test event serialization to JSON."""
        from src.security.audit_service import (
            AuditEvent,
            AuditCategory,
            AuditAction,
        )
        import json

        event = AuditEvent(
            category=AuditCategory.API,
            action=AuditAction.API_REQUEST,
            description="Test",
        )

        json_str = event.to_json()
        data = json.loads(json_str)

        assert data["category"] == "api"


class TestGlobalAuditService:
    """Test global audit service instance."""

    def test_get_audit_service(self):
        """Test getting global instance."""
        from src.security.audit_service import get_audit_service

        service1 = get_audit_service()
        service2 = get_audit_service()

        # Should be same instance
        assert service1 is service2

    def test_initialize_audit_service(self):
        """Test initializing with custom config."""
        from src.security.audit_service import (
            initialize_audit_service,
            AuditConfig,
        )
        import src.security.audit_service as module

        # Reset global
        module._audit_service = None

        config = AuditConfig(enabled=True, max_memory_events=500)
        service = initialize_audit_service(config)

        assert service.config.max_memory_events == 500


class TestSubscription:
    """Test event subscription."""

    def test_subscribe_to_events(self):
        """Test subscribing to audit events."""
        from src.security.audit_service import (
            SecurityAuditService,
            AuditConfig,
            AuditCategory,
            AuditAction,
        )

        config = AuditConfig(enabled=True, log_to_file=False, log_to_console=False)
        service = SecurityAuditService(config)

        received_events = []

        def callback(event):
            received_events.append(event)

        service.subscribe(callback)

        service.log_event(
            category=AuditCategory.SYSTEM,
            action=AuditAction.SYSTEM_START,
            description="Test",
        )

        assert len(received_events) >= 1

    def test_unsubscribe(self):
        """Test unsubscribing from events."""
        from src.security.audit_service import (
            SecurityAuditService,
            AuditConfig,
            AuditCategory,
            AuditAction,
        )

        config = AuditConfig(enabled=True, log_to_file=False, log_to_console=False)
        service = SecurityAuditService(config)

        received = []

        def callback(event):
            received.append(event)

        service.subscribe(callback)
        service.unsubscribe(callback)

        service.log_event(
            category=AuditCategory.SYSTEM,
            action=AuditAction.SYSTEM_START,
            description="Test",
        )

        # Callback should not be called (only system start event from initialization might be there)
        initial_count = len(received)
        service.log_event(
            category=AuditCategory.SYSTEM,
            action=AuditAction.SYSTEM_STOP,
            description="Test2",
        )
        assert len(received) == initial_count


class TestFileLogging:
    """Test file-based logging."""

    def test_log_to_file(self):
        """Test logging to file."""
        from src.security.audit_service import (
            SecurityAuditService,
            AuditConfig,
            AuditCategory,
            AuditAction,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = Path(tmpdir) / "audit.jsonl"

            config = AuditConfig(
                enabled=True,
                log_to_file=True,
                log_to_console=False,
                log_file_path=log_path,
            )
            service = SecurityAuditService(config)

            service.log_event(
                category=AuditCategory.AUTHENTICATION,
                action=AuditAction.LOGIN_SUCCESS,
                description="File test",
            )

            # Check file exists and has content
            assert log_path.exists()
            content = log_path.read_text()
            assert "File test" in content or "authentication" in content


class TestAdminAPIIntegration:
    """Test integration with admin API."""

    @pytest.fixture
    def mock_dependencies(self):
        """Mock dependencies."""
        with patch('src.ai.llm.llm_engine.OllamaClient') as mock_ollama, \
             patch('src.rag.vector_store_module.vector_store.chromadb') as mock_chroma:

            mock_ollama_instance = MagicMock()
            mock_ollama_instance.is_healthy = MagicMock(return_value=True)
            mock_ollama.return_value = mock_ollama_instance

            mock_collection = MagicMock()
            mock_collection.count.return_value = 0
            mock_chroma_client = MagicMock()
            mock_chroma_client.get_or_create_collection.return_value = mock_collection
            mock_chroma.PersistentClient.return_value = mock_chroma_client

            yield

    @pytest.fixture
    def client(self, mock_dependencies):
        """Create test client."""
        from fastapi.testclient import TestClient
        from src.main import app
        return TestClient(app)

    def test_add_audit_log_integration(self):
        """Test _add_audit_log integrates with centralized service."""
        from src.api.admin import _add_audit_log
        from src.security.audit_service import get_audit_service
        import src.security.audit_service as module

        # Reset global service
        module._audit_service = None

        # Call the admin audit function
        _add_audit_log(
            user="testuser",
            action="auth.login",
            resource="session",
            details="Test login",
            ip="10.0.0.1",
        )

        # Check centralized service received event
        service = get_audit_service()
        events = service.get_recent_events(limit=10)

        # Should have at least one auth event
        auth_events = [e for e in events if "authentication" in e.category.value]
        assert len(auth_events) >= 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
