"""
Security Audit API Endpoints (S19.1).

Provides REST API for security code review functionality.
"""

from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from loguru import logger

from src.security.code_review import (
    SecurityCodeReviewService,
    SecurityFinding,
    SecurityReviewResult,
    VulnerabilitySeverity,
    VulnerabilityCategory,
    get_code_review_service,
)


router = APIRouter(prefix="/api/security", tags=["Security Audit"])


# =============================================================================
# Request/Response Models
# =============================================================================

class CodeScanRequest(BaseModel):
    """Request to scan code string for vulnerabilities."""
    code: str = Field(..., description="Source code to scan")
    filename: str = Field(default="<input>", description="Virtual filename for findings")


class DirectoryScanRequest(BaseModel):
    """Request to scan a directory for vulnerabilities."""
    path: str = Field(..., description="Directory path to scan")
    recursive: bool = Field(default=True, description="Scan subdirectories")
    file_patterns: list[str] = Field(
        default=["*.py"],
        description="File patterns to include"
    )


class FileScanRequest(BaseModel):
    """Request to scan a specific file."""
    path: str = Field(..., description="File path to scan")


class FindingResponse(BaseModel):
    """Response model for a security finding."""
    id: str
    category: str
    severity: str
    title: str
    description: str
    file_path: str
    line_number: int
    code_snippet: str
    recommendation: str
    cwe_id: Optional[str] = None
    owasp_category: Optional[str] = None
    rule_id: str
    confidence: float


class ScanResultResponse(BaseModel):
    """Response model for scan results."""
    id: str
    timestamp: str
    target_path: str
    files_scanned: int
    lines_scanned: int
    scan_duration_ms: float
    findings: list[FindingResponse]
    summary: dict[str, int]
    risk_score: float
    success: bool
    error_message: Optional[str] = None


class RuleInfo(BaseModel):
    """Information about a security rule."""
    id: str
    name: str
    description: str
    category: str
    severity: str
    cwe_id: Optional[str] = None
    owasp_category: Optional[str] = None
    enabled: bool
    confidence: float


# =============================================================================
# Helper Functions
# =============================================================================

def finding_to_response(finding: SecurityFinding) -> FindingResponse:
    """Convert SecurityFinding to API response."""
    return FindingResponse(
        id=finding.id,
        category=finding.category.value,
        severity=finding.severity.value,
        title=finding.title,
        description=finding.description,
        file_path=finding.file_path,
        line_number=finding.line_number,
        code_snippet=finding.code_snippet,
        recommendation=finding.recommendation,
        cwe_id=finding.cwe_id,
        owasp_category=finding.owasp_category,
        rule_id=finding.rule_id,
        confidence=finding.confidence,
    )


def result_to_response(result: SecurityReviewResult) -> ScanResultResponse:
    """Convert SecurityReviewResult to API response."""
    return ScanResultResponse(
        id=result.id,
        timestamp=result.timestamp.isoformat(),
        target_path=result.target_path,
        files_scanned=result.files_scanned,
        lines_scanned=result.lines_scanned,
        scan_duration_ms=result.scan_duration_ms,
        findings=[finding_to_response(f) for f in result.findings],
        summary={
            "critical": result.critical_count,
            "high": result.high_count,
            "medium": result.medium_count,
            "low": result.low_count,
            "info": result.info_count,
            "total": len(result.findings),
        },
        risk_score=result.get_risk_score(),
        success=result.success,
        error_message=result.error_message,
    )


# =============================================================================
# API Endpoints
# =============================================================================

@router.get("/audit/status")
async def get_audit_status() -> dict[str, Any]:
    """Get security audit service status."""
    service = get_code_review_service()
    rules = service.get_rules()

    return {
        "service": "security_audit",
        "status": "operational",
        "version": "1.0.0",
        "rules_count": len(rules),
        "rules_by_category": _count_rules_by_category(rules),
        "rules_by_severity": _count_rules_by_severity(rules),
    }


def _count_rules_by_category(rules: list[dict]) -> dict[str, int]:
    """Count rules by category."""
    counts: dict[str, int] = {}
    for rule in rules:
        cat = rule["category"]
        counts[cat] = counts.get(cat, 0) + 1
    return counts


def _count_rules_by_severity(rules: list[dict]) -> dict[str, int]:
    """Count rules by severity."""
    counts: dict[str, int] = {}
    for rule in rules:
        sev = rule["severity"]
        counts[sev] = counts.get(sev, 0) + 1
    return counts


@router.get("/audit/rules")
async def get_security_rules(
    category: Optional[str] = Query(None, description="Filter by category"),
    severity: Optional[str] = Query(None, description="Filter by severity"),
    enabled_only: bool = Query(True, description="Only return enabled rules"),
) -> dict[str, Any]:
    """Get all security scanning rules."""
    service = get_code_review_service()
    rules = service.get_rules()

    # Apply filters
    if category:
        rules = [r for r in rules if r["category"] == category]
    if severity:
        rules = [r for r in rules if r["severity"] == severity]
    if enabled_only:
        rules = [r for r in rules if r["enabled"]]

    return {
        "rules": rules,
        "total": len(rules),
    }


@router.post("/audit/scan/code", response_model=dict[str, Any])
async def scan_code(request: CodeScanRequest) -> dict[str, Any]:
    """
    Scan a code string for security vulnerabilities.

    This endpoint allows scanning arbitrary code snippets without
    accessing the filesystem.
    """
    service = get_code_review_service()

    try:
        findings = service.scan_code_string(
            code=request.code,
            filename=request.filename,
        )

        # Convert findings to response format
        findings_response = [finding_to_response(f) for f in findings]

        # Count by severity
        critical = sum(1 for f in findings if f.severity == VulnerabilitySeverity.CRITICAL)
        high = sum(1 for f in findings if f.severity == VulnerabilitySeverity.HIGH)
        medium = sum(1 for f in findings if f.severity == VulnerabilitySeverity.MEDIUM)
        low = sum(1 for f in findings if f.severity == VulnerabilitySeverity.LOW)
        info = sum(1 for f in findings if f.severity == VulnerabilitySeverity.INFO)

        return {
            "success": True,
            "filename": request.filename,
            "lines_scanned": request.code.count("\n") + 1,
            "findings": findings_response,
            "summary": {
                "critical": critical,
                "high": high,
                "medium": medium,
                "low": low,
                "info": info,
                "total": len(findings),
            },
        }

    except Exception as e:
        logger.error(f"Error scanning code: {e}")
        raise HTTPException(status_code=500, detail=f"Scan failed: {str(e)}")


@router.post("/audit/scan/file", response_model=dict[str, Any])
async def scan_file(request: FileScanRequest) -> dict[str, Any]:
    """
    Scan a specific file for security vulnerabilities.

    Note: Only files within the project directory are allowed.
    """
    service = get_code_review_service()
    file_path = Path(request.path)

    # Security: Prevent path traversal
    if ".." in request.path:
        raise HTTPException(status_code=400, detail="Path traversal not allowed")

    if not file_path.exists():
        raise HTTPException(status_code=404, detail=f"File not found: {request.path}")

    if not file_path.is_file():
        raise HTTPException(status_code=400, detail=f"Not a file: {request.path}")

    try:
        findings = service.scan_file(file_path)

        # Convert findings to response format
        findings_response = [finding_to_response(f) for f in findings]

        # Count by severity
        critical = sum(1 for f in findings if f.severity == VulnerabilitySeverity.CRITICAL)
        high = sum(1 for f in findings if f.severity == VulnerabilitySeverity.HIGH)
        medium = sum(1 for f in findings if f.severity == VulnerabilitySeverity.MEDIUM)
        low = sum(1 for f in findings if f.severity == VulnerabilitySeverity.LOW)
        info = sum(1 for f in findings if f.severity == VulnerabilitySeverity.INFO)

        return {
            "success": True,
            "file_path": str(file_path),
            "findings": findings_response,
            "summary": {
                "critical": critical,
                "high": high,
                "medium": medium,
                "low": low,
                "info": info,
                "total": len(findings),
            },
        }

    except Exception as e:
        logger.error(f"Error scanning file {request.path}: {e}")
        raise HTTPException(status_code=500, detail=f"Scan failed: {str(e)}")


@router.post("/audit/scan/directory", response_model=ScanResultResponse)
async def scan_directory(request: DirectoryScanRequest) -> ScanResultResponse:
    """
    Scan a directory for security vulnerabilities.

    This performs a comprehensive scan of all matching files
    in the specified directory.

    Note: Only directories within the project are allowed.
    """
    service = get_code_review_service()
    dir_path = Path(request.path)

    # Security: Prevent path traversal
    if ".." in request.path:
        raise HTTPException(status_code=400, detail="Path traversal not allowed")

    if not dir_path.exists():
        raise HTTPException(status_code=404, detail=f"Directory not found: {request.path}")

    if not dir_path.is_dir():
        raise HTTPException(status_code=400, detail=f"Not a directory: {request.path}")

    try:
        result = service.scan_directory(
            directory=dir_path,
            recursive=request.recursive,
            file_patterns=request.file_patterns,
        )

        return result_to_response(result)

    except Exception as e:
        logger.error(f"Error scanning directory {request.path}: {e}")
        raise HTTPException(status_code=500, detail=f"Scan failed: {str(e)}")


@router.get("/audit/scan/project", response_model=ScanResultResponse)
async def scan_project(
    exclude_tests: bool = Query(True, description="Exclude test files"),
) -> ScanResultResponse:
    """
    Scan the entire project for security vulnerabilities.

    This is a convenience endpoint that scans the backend/src directory.
    """
    service = get_code_review_service()

    # Get project root - navigate from api directory
    project_root = Path(__file__).parent.parent  # backend/src

    if not project_root.exists():
        raise HTTPException(
            status_code=500,
            detail="Could not locate project source directory"
        )

    try:
        # Configure exclude patterns
        if exclude_tests:
            service.exclude_patterns = [
                "**/test_*.py",
                "**/*_test.py",
                "**/tests/**",
                "**/__pycache__/**",
                "**/.venv/**",
                "**/venv/**",
            ]
        else:
            service.exclude_patterns = [
                "**/__pycache__/**",
                "**/.venv/**",
                "**/venv/**",
            ]

        result = service.scan_directory(
            directory=project_root,
            recursive=True,
            file_patterns=["*.py"],
        )

        return result_to_response(result)

    except Exception as e:
        logger.error(f"Error scanning project: {e}")
        raise HTTPException(status_code=500, detail=f"Scan failed: {str(e)}")


@router.get("/audit/report/{format}")
async def get_report(
    format: str,
    path: str = Query(..., description="Directory path to scan"),
) -> dict[str, Any]:
    """
    Generate a security report in the specified format.

    Supported formats: markdown, json, html
    """
    if format not in ["markdown", "json", "html"]:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported format: {format}. Use: markdown, json, html"
        )

    service = get_code_review_service()
    dir_path = Path(path)

    if ".." in path:
        raise HTTPException(status_code=400, detail="Path traversal not allowed")

    if not dir_path.exists():
        raise HTTPException(status_code=404, detail=f"Directory not found: {path}")

    try:
        result = service.scan_directory(dir_path, recursive=True)
        report = service.generate_report(result, format=format)

        # For HTML, return with proper content type hint
        content_type = {
            "markdown": "text/markdown",
            "json": "application/json",
            "html": "text/html",
        }[format]

        return {
            "format": format,
            "content_type": content_type,
            "report": report,
            "scan_id": result.id,
        }

    except Exception as e:
        logger.error(f"Error generating report: {e}")
        raise HTTPException(status_code=500, detail=f"Report generation failed: {str(e)}")


@router.get("/audit/categories")
async def get_categories() -> dict[str, Any]:
    """Get all vulnerability categories with descriptions."""
    categories = [
        {
            "id": cat.value,
            "name": cat.name.replace("_", " ").title(),
            "description": _get_category_description(cat),
        }
        for cat in VulnerabilityCategory
    ]

    return {"categories": categories}


def _get_category_description(cat: VulnerabilityCategory) -> str:
    """Get description for a vulnerability category."""
    descriptions = {
        VulnerabilityCategory.INJECTION: "Code injection vulnerabilities including SQL and command injection",
        VulnerabilityCategory.BROKEN_AUTH: "Authentication and session management weaknesses",
        VulnerabilityCategory.SENSITIVE_DATA: "Improper handling or exposure of sensitive data",
        VulnerabilityCategory.XXE: "XML External Entity processing vulnerabilities",
        VulnerabilityCategory.BROKEN_ACCESS: "Access control and authorization issues",
        VulnerabilityCategory.SECURITY_MISCONFIG: "Security misconfiguration issues",
        VulnerabilityCategory.XSS: "Cross-site scripting vulnerabilities",
        VulnerabilityCategory.INSECURE_DESER: "Insecure deserialization vulnerabilities",
        VulnerabilityCategory.VULNERABLE_DEPS: "Use of components with known vulnerabilities",
        VulnerabilityCategory.INSUFFICIENT_LOGGING: "Insufficient logging and monitoring",
        VulnerabilityCategory.SSRF: "Server-side request forgery vulnerabilities",
        VulnerabilityCategory.HARDCODED_SECRETS: "Hardcoded credentials and secrets",
        VulnerabilityCategory.PATH_TRAVERSAL: "Path traversal and file access vulnerabilities",
        VulnerabilityCategory.COMMAND_INJECTION: "Operating system command injection",
        VulnerabilityCategory.CODE_QUALITY: "Security-related code quality issues",
    }
    return descriptions.get(cat, "Security vulnerability")


@router.get("/audit/severities")
async def get_severities() -> dict[str, Any]:
    """Get all severity levels with descriptions."""
    severities = [
        {
            "id": sev.value,
            "name": sev.name,
            "description": _get_severity_description(sev),
            "remediation_sla": _get_remediation_sla(sev),
        }
        for sev in VulnerabilitySeverity
    ]

    return {"severities": severities}


def _get_severity_description(sev: VulnerabilitySeverity) -> str:
    """Get description for a severity level."""
    descriptions = {
        VulnerabilitySeverity.CRITICAL: "Immediate remediation required - actively exploitable",
        VulnerabilitySeverity.HIGH: "High risk vulnerability requiring prompt attention",
        VulnerabilitySeverity.MEDIUM: "Moderate risk that should be addressed",
        VulnerabilitySeverity.LOW: "Low risk issue for future consideration",
        VulnerabilitySeverity.INFO: "Informational finding or best practice suggestion",
    }
    return descriptions.get(sev, "Security finding")


def _get_remediation_sla(sev: VulnerabilitySeverity) -> str:
    """Get recommended remediation SLA for severity level."""
    slas = {
        VulnerabilitySeverity.CRITICAL: "Immediate (within 24 hours)",
        VulnerabilitySeverity.HIGH: "Within 7 days",
        VulnerabilitySeverity.MEDIUM: "Within 30 days",
        VulnerabilitySeverity.LOW: "Within 90 days",
        VulnerabilitySeverity.INFO: "As time permits",
    }
    return slas.get(sev, "To be determined")
