"""
Tests for Security Code Review Module (S19.1).

Tests the security scanning functionality including:
- Pattern-based vulnerability detection
- AST-based analysis
- Report generation
- API endpoints
"""

import pytest
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

# Mock chromadb before imports
sys.modules['chromadb'] = MagicMock()
sys.modules['chromadb.config'] = MagicMock()

from src.security.code_review import (
    SecurityCodeReviewService,
    SecurityFinding,
    SecurityReviewResult,
    VulnerabilitySeverity,
    VulnerabilityCategory,
    SECURITY_RULES,
    get_code_review_service,
)


# =============================================================================
# Test Fixtures
# =============================================================================

@pytest.fixture
def security_service():
    """Create a fresh security code review service."""
    return SecurityCodeReviewService()


@pytest.fixture
def vulnerable_code_samples():
    """Sample vulnerable code for testing."""
    return {
        "hardcoded_password": '''
password = "super_secret_123"
api_key = "sk-1234567890abcdef1234"
''',
        "sql_injection": '''
def get_user(username):
    query = f"SELECT * FROM users WHERE name = '{username}'"
    cursor.execute(query)
''',
        "command_injection": '''
import os
def run_command(cmd):
    os.system(f"echo {cmd}")
''',
        "eval_usage": '''
def calculate(expr):
    return eval(expr)
''',
        "pickle_usage": '''
import pickle
def load_data(data):
    return pickle.loads(data)
''',
        "weak_hash": '''
import hashlib
def hash_password(password):
    return hashlib.md5(password.encode()).hexdigest()
''',
        "debug_enabled": '''
DEBUG = True
app.run(debug=True)
''',
        "ssl_disabled": '''
import requests
response = requests.get(url, verify=False)
''',
        "shell_true": '''
import subprocess
subprocess.run(cmd, shell=True)
''',
        "silent_exception": '''
try:
    do_something()
except:
    pass
''',
    }


@pytest.fixture
def safe_code_sample():
    """Sample of secure code."""
    return '''
import secrets
import hashlib
from typing import Optional

def generate_token() -> str:
    """Generate a secure random token."""
    return secrets.token_urlsafe(32)

def hash_data(data: str) -> str:
    """Hash data using SHA-256."""
    return hashlib.sha256(data.encode()).hexdigest()

def get_user(user_id: int, db_session) -> Optional[dict]:
    """Get user by ID using parameterized query."""
    return db_session.query(User).filter(User.id == user_id).first()
'''


# =============================================================================
# Unit Tests - Pattern Detection
# =============================================================================

class TestPatternDetection:
    """Tests for pattern-based vulnerability detection."""

    def test_detects_hardcoded_password(self, security_service, vulnerable_code_samples):
        """Test detection of hardcoded passwords."""
        findings = security_service.scan_code_string(
            vulnerable_code_samples["hardcoded_password"]
        )

        # Should find hardcoded credentials
        assert len(findings) > 0

        password_findings = [
            f for f in findings
            if f.category == VulnerabilityCategory.HARDCODED_SECRETS
        ]
        assert len(password_findings) > 0

    def test_detects_command_injection(self, security_service, vulnerable_code_samples):
        """Test detection of command injection via os.system."""
        findings = security_service.scan_code_string(
            vulnerable_code_samples["command_injection"]
        )

        cmd_findings = [
            f for f in findings
            if f.category == VulnerabilityCategory.COMMAND_INJECTION
        ]
        assert len(cmd_findings) > 0

    def test_detects_eval_usage(self, security_service, vulnerable_code_samples):
        """Test detection of dangerous eval() usage."""
        findings = security_service.scan_code_string(
            vulnerable_code_samples["eval_usage"]
        )

        eval_findings = [
            f for f in findings
            if "eval" in f.title.lower() or "eval" in f.description.lower()
        ]
        assert len(eval_findings) > 0

    def test_detects_pickle_usage(self, security_service, vulnerable_code_samples):
        """Test detection of insecure pickle deserialization."""
        findings = security_service.scan_code_string(
            vulnerable_code_samples["pickle_usage"]
        )

        pickle_findings = [
            f for f in findings
            if f.category == VulnerabilityCategory.INSECURE_DESER
        ]
        assert len(pickle_findings) > 0

    def test_detects_weak_hash(self, security_service, vulnerable_code_samples):
        """Test detection of weak MD5 hash usage."""
        findings = security_service.scan_code_string(
            vulnerable_code_samples["weak_hash"]
        )

        hash_findings = [
            f for f in findings
            if f.category == VulnerabilityCategory.BROKEN_AUTH
            or "md5" in f.title.lower()
        ]
        assert len(hash_findings) > 0

    def test_detects_debug_enabled(self, security_service, vulnerable_code_samples):
        """Test detection of debug mode enabled."""
        findings = security_service.scan_code_string(
            vulnerable_code_samples["debug_enabled"]
        )

        debug_findings = [
            f for f in findings
            if f.category == VulnerabilityCategory.SECURITY_MISCONFIG
            or "debug" in f.title.lower()
        ]
        assert len(debug_findings) > 0

    def test_detects_ssl_verification_disabled(self, security_service, vulnerable_code_samples):
        """Test detection of SSL verification disabled."""
        findings = security_service.scan_code_string(
            vulnerable_code_samples["ssl_disabled"]
        )

        ssl_findings = [
            f for f in findings
            if "ssl" in f.title.lower() or "verify" in f.description.lower()
        ]
        assert len(ssl_findings) > 0

    def test_detects_shell_true(self, security_service, vulnerable_code_samples):
        """Test detection of subprocess with shell=True."""
        findings = security_service.scan_code_string(
            vulnerable_code_samples["shell_true"]
        )

        shell_findings = [
            f for f in findings
            if "shell" in f.title.lower() or "subprocess" in f.description.lower()
        ]
        assert len(shell_findings) > 0

    def test_safe_code_has_fewer_findings(self, security_service, safe_code_sample):
        """Test that safe code has minimal/no critical findings."""
        findings = security_service.scan_code_string(safe_code_sample)

        critical_findings = [
            f for f in findings
            if f.severity == VulnerabilitySeverity.CRITICAL
        ]
        # Safe code should have no critical findings
        assert len(critical_findings) == 0


# =============================================================================
# Unit Tests - Service Functionality
# =============================================================================

class TestSecurityService:
    """Tests for SecurityCodeReviewService functionality."""

    def test_service_initialization(self, security_service):
        """Test service initializes correctly."""
        assert security_service is not None
        assert len(security_service.rules) > 0

    def test_get_rules(self, security_service):
        """Test getting security rules."""
        rules = security_service.get_rules()

        assert isinstance(rules, list)
        assert len(rules) > 0

        # Check rule structure
        first_rule = rules[0]
        assert "id" in first_rule
        assert "name" in first_rule
        assert "description" in first_rule
        assert "category" in first_rule
        assert "severity" in first_rule

    def test_finding_structure(self, security_service):
        """Test that findings have proper structure."""
        code = 'password = "test12345678"'
        findings = security_service.scan_code_string(code)

        if findings:
            finding = findings[0]
            assert hasattr(finding, "id")
            assert hasattr(finding, "category")
            assert hasattr(finding, "severity")
            assert hasattr(finding, "title")
            assert hasattr(finding, "description")
            assert hasattr(finding, "line_number")
            assert hasattr(finding, "recommendation")

    def test_scan_empty_code(self, security_service):
        """Test scanning empty code."""
        findings = security_service.scan_code_string("")
        assert isinstance(findings, list)

    def test_scan_invalid_syntax(self, security_service):
        """Test scanning code with invalid syntax."""
        invalid_code = "def broken(:\n    pass"
        findings = security_service.scan_code_string(invalid_code)
        # Should still return pattern-based findings, not crash
        assert isinstance(findings, list)

    def test_finding_to_dict(self, security_service):
        """Test finding serialization."""
        code = 'eval(user_input)'
        findings = security_service.scan_code_string(code)

        if findings:
            finding_dict = findings[0].to_dict()
            assert isinstance(finding_dict, dict)
            assert "id" in finding_dict
            assert "timestamp" in finding_dict
            assert "category" in finding_dict


# =============================================================================
# Unit Tests - Report Generation
# =============================================================================

class TestReportGeneration:
    """Tests for security report generation."""

    def test_markdown_report_generation(self, security_service):
        """Test markdown report generation."""
        code = '''
password = "secret123456"
eval(data)
'''
        findings = security_service.scan_code_string(code)

        result = SecurityReviewResult(
            target_path="<test>",
            files_scanned=1,
            lines_scanned=3,
            findings=findings,
            critical_count=sum(1 for f in findings if f.severity == VulnerabilitySeverity.CRITICAL),
            high_count=sum(1 for f in findings if f.severity == VulnerabilitySeverity.HIGH),
        )

        report = security_service.generate_report(result, format="markdown")

        assert isinstance(report, str)
        assert "# Security Code Review Report" in report
        assert "## Summary" in report

    def test_json_report_generation(self, security_service):
        """Test JSON report generation."""
        result = SecurityReviewResult(
            target_path="<test>",
            files_scanned=0,
            lines_scanned=0,
            findings=[],
        )

        report = security_service.generate_report(result, format="json")

        assert isinstance(report, str)
        # Should be valid JSON
        import json
        parsed = json.loads(report)
        assert "id" in parsed
        assert "findings" in parsed

    def test_html_report_generation(self, security_service):
        """Test HTML report generation."""
        result = SecurityReviewResult(
            target_path="<test>",
            files_scanned=0,
            lines_scanned=0,
            findings=[],
        )

        report = security_service.generate_report(result, format="html")

        assert isinstance(report, str)
        assert "<html>" in report
        assert "Security Code Review Report" in report


# =============================================================================
# Unit Tests - Risk Scoring
# =============================================================================

class TestRiskScoring:
    """Tests for risk score calculation."""

    def test_empty_result_score(self):
        """Test risk score for empty results."""
        result = SecurityReviewResult()
        score = result.get_risk_score()
        assert score == 0.0

    def test_critical_findings_high_score(self):
        """Test that critical findings result in high risk score."""
        result = SecurityReviewResult(
            critical_count=2,
            high_count=0,
            medium_count=0,
            low_count=0,
            info_count=0,
        )
        score = result.get_risk_score()
        assert score >= 80  # 2 * 40 = 80

    def test_mixed_findings_score(self):
        """Test risk score with mixed severity findings."""
        result = SecurityReviewResult(
            critical_count=0,
            high_count=2,
            medium_count=3,
            low_count=5,
            info_count=10,
        )
        # 0*40 + 2*20 + 3*10 + 5*5 + 10*1 = 0 + 40 + 30 + 25 + 10 = 105 -> capped at 100
        score = result.get_risk_score()
        assert score == 100


# =============================================================================
# Unit Tests - Rules Coverage
# =============================================================================

class TestRulesCoverage:
    """Tests for security rules coverage."""

    def test_rules_have_required_fields(self):
        """Test that all rules have required fields."""
        for rule in SECURITY_RULES:
            assert rule.id, "Rule must have an ID"
            assert rule.name, "Rule must have a name"
            assert rule.description, "Rule must have a description"
            assert rule.pattern, "Rule must have a pattern"
            assert rule.recommendation, "Rule must have a recommendation"
            assert isinstance(rule.category, VulnerabilityCategory)
            assert isinstance(rule.severity, VulnerabilitySeverity)

    def test_rules_have_unique_ids(self):
        """Test that all rule IDs are unique."""
        ids = [rule.id for rule in SECURITY_RULES]
        assert len(ids) == len(set(ids)), "Rule IDs must be unique"

    def test_rules_cover_owasp_categories(self):
        """Test that rules cover major OWASP categories."""
        categories = {rule.category for rule in SECURITY_RULES}

        # Should cover major vulnerability categories
        assert VulnerabilityCategory.INJECTION in categories
        assert VulnerabilityCategory.BROKEN_AUTH in categories
        assert VulnerabilityCategory.HARDCODED_SECRETS in categories
        assert VulnerabilityCategory.COMMAND_INJECTION in categories


# =============================================================================
# Integration Tests - API Endpoints
# =============================================================================

class TestSecurityAuditAPI:
    """Tests for security audit API endpoints."""

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

    def test_audit_status_endpoint(self, client):
        """Test /api/security/audit/status endpoint."""
        response = client.get("/api/security/audit/status")

        assert response.status_code == 200
        data = response.json()

        assert data["service"] == "security_audit"
        assert data["status"] == "operational"
        assert "rules_count" in data

    def test_audit_rules_endpoint(self, client):
        """Test /api/security/audit/rules endpoint."""
        response = client.get("/api/security/audit/rules")

        assert response.status_code == 200
        data = response.json()

        assert "rules" in data
        assert "total" in data
        assert data["total"] > 0

    def test_audit_categories_endpoint(self, client):
        """Test /api/security/audit/categories endpoint."""
        response = client.get("/api/security/audit/categories")

        assert response.status_code == 200
        data = response.json()

        assert "categories" in data
        assert len(data["categories"]) > 0

    def test_audit_severities_endpoint(self, client):
        """Test /api/security/audit/severities endpoint."""
        response = client.get("/api/security/audit/severities")

        assert response.status_code == 200
        data = response.json()

        assert "severities" in data
        assert len(data["severities"]) == 5  # CRITICAL, HIGH, MEDIUM, LOW, INFO

    def test_scan_code_endpoint(self, client):
        """Test /api/security/audit/scan/code endpoint."""
        response = client.post(
            "/api/security/audit/scan/code",
            json={
                "code": 'password = "secret12345678"',
                "filename": "test.py"
            }
        )

        assert response.status_code == 200
        data = response.json()

        assert data["success"] is True
        assert "findings" in data
        assert "summary" in data

    def test_scan_code_empty(self, client):
        """Test scanning empty code."""
        response = client.post(
            "/api/security/audit/scan/code",
            json={
                "code": "",
                "filename": "empty.py"
            }
        )

        assert response.status_code == 200
        data = response.json()

        assert data["success"] is True
        assert data["summary"]["total"] == 0

    def test_scan_code_with_vulnerabilities(self, client):
        """Test scanning code with known vulnerabilities."""
        vulnerable_code = '''
import os
import pickle

password = "hardcoded_secret_12345678"
api_key = "sk-abcdefghijklmnopqrstuvwxyz"

def dangerous(user_input):
    os.system(f"echo {user_input}")
    return eval(user_input)

def load(data):
    return pickle.loads(data)
'''
        response = client.post(
            "/api/security/audit/scan/code",
            json={
                "code": vulnerable_code,
                "filename": "vulnerable.py"
            }
        )

        assert response.status_code == 200
        data = response.json()

        assert data["success"] is True
        assert data["summary"]["total"] > 0

        # Should find multiple issues
        total_findings = data["summary"]["total"]
        assert total_findings >= 3  # At least password, eval, pickle

    def test_scan_file_path_traversal_blocked(self, client):
        """Test that path traversal is blocked."""
        response = client.post(
            "/api/security/audit/scan/file",
            json={"path": "../../../etc/passwd"}
        )

        assert response.status_code == 400
        assert "traversal" in response.json()["detail"].lower()

    def test_scan_directory_path_traversal_blocked(self, client):
        """Test that directory path traversal is blocked."""
        response = client.post(
            "/api/security/audit/scan/directory",
            json={"path": "../../../", "recursive": True}
        )

        assert response.status_code == 400


# =============================================================================
# Global Service Tests
# =============================================================================

class TestGlobalService:
    """Tests for global service instance."""

    def test_get_code_review_service_returns_instance(self):
        """Test that get_code_review_service returns a service instance."""
        import src.security.code_review as module
        # Reset global
        module._code_review_service = None

        service = get_code_review_service()
        assert service is not None
        assert isinstance(service, SecurityCodeReviewService)

    def test_get_code_review_service_singleton(self):
        """Test that get_code_review_service returns same instance."""
        import src.security.code_review as module
        # Reset global
        module._code_review_service = None

        service1 = get_code_review_service()
        service2 = get_code_review_service()
        assert service1 is service2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
