"""
Tests for Health API Endpoints.
"""

import pytest
from fastapi.testclient import TestClient

from src.main import app


@pytest.fixture
def client():
    """Create a test client."""
    return TestClient(app)


def test_health_check(client):
    """Test basic health check endpoint."""
    response = client.get("/api/health")
    assert response.status_code == 200

    data = response.json()
    assert data["status"] == "healthy"
    assert "timestamp" in data
    assert "version" in data
    assert "environment" in data


def test_liveness_check(client):
    """Test liveness probe endpoint."""
    response = client.get("/api/health/live")
    assert response.status_code == 200

    data = response.json()
    assert data["status"] == "alive"


def test_readiness_check(client):
    """Test readiness probe endpoint."""
    response = client.get("/api/health/ready")
    assert response.status_code == 200

    data = response.json()
    assert "status" in data
    assert "timestamp" in data
    assert "checks" in data

    # Verify subsystem checks are present
    assert "configuration" in data["checks"]
    assert "filesystem" in data["checks"]


def test_system_info(client):
    """Test system info endpoint."""
    response = client.get("/api/info")
    assert response.status_code == 200

    data = response.json()
    assert data["app_name"] == "Smart-HES Agent"
    assert "version" in data
    assert "environment" in data
    assert "features" in data
    assert "settings" in data

    # Verify anti-hallucination features are exposed
    assert "verification_enabled" in data["features"]
    assert "strict_verification_mode" in data["features"]
