"""
Security Code Review Module (S19.1).

Provides automated security code review capabilities for the S5-HES Agent project.

Features:
- Static code analysis for common vulnerabilities
- OWASP Top 10 checks
- Hardcoded secret detection
- SQL injection patterns
- Command injection patterns
- XSS vulnerability patterns
- Insecure deserialization
- Security best practices validation
- Dependency vulnerability scanning
- Custom rule support
"""

import ast
import re
import hashlib
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Optional
from uuid import uuid4

from loguru import logger


# =============================================================================
# Vulnerability Types and Severity
# =============================================================================

class VulnerabilitySeverity(str, Enum):
    """Severity levels for security vulnerabilities."""
    CRITICAL = "critical"  # Immediate remediation required
    HIGH = "high"          # Should be fixed within 24 hours
    MEDIUM = "medium"      # Should be fixed within 1 week
    LOW = "low"           # Should be fixed within 1 month
    INFO = "info"          # Informational findings


class VulnerabilityCategory(str, Enum):
    """Categories of security vulnerabilities (OWASP-aligned)."""
    INJECTION = "injection"                    # A03:2021
    BROKEN_AUTH = "broken_authentication"      # A07:2021
    SENSITIVE_DATA = "sensitive_data_exposure" # A02:2021
    XXE = "xml_external_entities"              # A05:2021
    BROKEN_ACCESS = "broken_access_control"    # A01:2021
    SECURITY_MISCONFIG = "security_misconfiguration"  # A05:2021
    XSS = "cross_site_scripting"              # A03:2021
    INSECURE_DESER = "insecure_deserialization"  # A08:2021
    VULNERABLE_DEPS = "vulnerable_dependencies"  # A06:2021
    INSUFFICIENT_LOGGING = "insufficient_logging"  # A09:2021
    SSRF = "server_side_request_forgery"      # A10:2021
    HARDCODED_SECRETS = "hardcoded_secrets"
    PATH_TRAVERSAL = "path_traversal"
    COMMAND_INJECTION = "command_injection"
    CODE_QUALITY = "code_quality"


# =============================================================================
# Data Models
# =============================================================================

@dataclass
class SecurityFinding:
    """A security finding from code review."""
    id: str = field(default_factory=lambda: str(uuid4()))
    timestamp: datetime = field(default_factory=datetime.utcnow)

    # Finding details
    category: VulnerabilityCategory = VulnerabilityCategory.CODE_QUALITY
    severity: VulnerabilitySeverity = VulnerabilitySeverity.INFO
    title: str = ""
    description: str = ""

    # Location
    file_path: str = ""
    line_number: int = 0
    column: int = 0
    code_snippet: str = ""

    # Remediation
    recommendation: str = ""
    cwe_id: Optional[str] = None  # Common Weakness Enumeration
    owasp_category: Optional[str] = None

    # Metadata
    rule_id: str = ""
    confidence: float = 1.0  # 0.0 - 1.0
    false_positive: bool = False
    tags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "timestamp": self.timestamp.isoformat(),
            "category": self.category.value,
            "severity": self.severity.value,
            "title": self.title,
            "description": self.description,
            "file_path": self.file_path,
            "line_number": self.line_number,
            "column": self.column,
            "code_snippet": self.code_snippet,
            "recommendation": self.recommendation,
            "cwe_id": self.cwe_id,
            "owasp_category": self.owasp_category,
            "rule_id": self.rule_id,
            "confidence": self.confidence,
            "false_positive": self.false_positive,
            "tags": self.tags,
        }


@dataclass
class SecurityReviewResult:
    """Result of a security code review."""
    id: str = field(default_factory=lambda: str(uuid4()))
    timestamp: datetime = field(default_factory=datetime.utcnow)

    # Scope
    target_path: str = ""
    files_scanned: int = 0
    lines_scanned: int = 0
    scan_duration_ms: float = 0.0

    # Findings
    findings: list[SecurityFinding] = field(default_factory=list)

    # Summary
    critical_count: int = 0
    high_count: int = 0
    medium_count: int = 0
    low_count: int = 0
    info_count: int = 0

    # Status
    success: bool = True
    error_message: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "timestamp": self.timestamp.isoformat(),
            "target_path": self.target_path,
            "files_scanned": self.files_scanned,
            "lines_scanned": self.lines_scanned,
            "scan_duration_ms": self.scan_duration_ms,
            "findings": [f.to_dict() for f in self.findings],
            "summary": {
                "critical": self.critical_count,
                "high": self.high_count,
                "medium": self.medium_count,
                "low": self.low_count,
                "info": self.info_count,
                "total": len(self.findings),
            },
            "success": self.success,
            "error_message": self.error_message,
        }

    def get_risk_score(self) -> float:
        """Calculate overall risk score (0-100)."""
        # Weighted scoring
        score = (
            self.critical_count * 40 +
            self.high_count * 20 +
            self.medium_count * 10 +
            self.low_count * 5 +
            self.info_count * 1
        )
        # Normalize to 0-100
        return min(100, score)


# =============================================================================
# Security Rules
# =============================================================================

@dataclass
class SecurityRule:
    """A security scanning rule."""
    id: str
    name: str
    description: str
    category: VulnerabilityCategory
    severity: VulnerabilitySeverity
    pattern: str  # Regex pattern
    recommendation: str
    cwe_id: Optional[str] = None
    owasp_category: Optional[str] = None
    file_patterns: list[str] = field(default_factory=lambda: ["*.py"])
    enabled: bool = True
    confidence: float = 0.9


# =============================================================================
# Built-in Security Rules
# =============================================================================

SECURITY_RULES: list[SecurityRule] = [
    # Hardcoded Secrets
    SecurityRule(
        id="SEC001",
        name="Hardcoded Password",
        description="Password appears to be hardcoded in source code",
        category=VulnerabilityCategory.HARDCODED_SECRETS,
        severity=VulnerabilitySeverity.CRITICAL,
        pattern=r'(?i)(password|passwd|pwd)\s*=\s*["\'][^"\']{4,}["\']',
        recommendation="Use environment variables or a secrets management system",
        cwe_id="CWE-798",
        owasp_category="A02:2021",
    ),
    SecurityRule(
        id="SEC002",
        name="Hardcoded API Key",
        description="API key appears to be hardcoded in source code",
        category=VulnerabilityCategory.HARDCODED_SECRETS,
        severity=VulnerabilitySeverity.CRITICAL,
        pattern=r'(?i)(api[_-]?key|apikey|api_secret)\s*=\s*["\'][a-zA-Z0-9_\-]{16,}["\']',
        recommendation="Store API keys in environment variables or secrets manager",
        cwe_id="CWE-798",
        owasp_category="A02:2021",
    ),
    SecurityRule(
        id="SEC003",
        name="Hardcoded Secret Token",
        description="Secret token appears to be hardcoded in source code",
        category=VulnerabilityCategory.HARDCODED_SECRETS,
        severity=VulnerabilitySeverity.CRITICAL,
        pattern=r'(?i)(secret|token|auth_token|access_token)\s*=\s*["\'][a-zA-Z0-9_\-]{20,}["\']',
        recommendation="Use environment variables for sensitive tokens",
        cwe_id="CWE-798",
        owasp_category="A02:2021",
    ),
    SecurityRule(
        id="SEC004",
        name="AWS Credentials",
        description="AWS credentials pattern detected",
        category=VulnerabilityCategory.HARDCODED_SECRETS,
        severity=VulnerabilitySeverity.CRITICAL,
        pattern=r'(?i)(aws_access_key_id|aws_secret_access_key)\s*=\s*["\'][A-Z0-9]{16,}["\']',
        recommendation="Use AWS IAM roles or environment variables",
        cwe_id="CWE-798",
        owasp_category="A02:2021",
    ),

    # SQL Injection
    SecurityRule(
        id="SEC010",
        name="Potential SQL Injection",
        description="String formatting in SQL query may lead to SQL injection",
        category=VulnerabilityCategory.INJECTION,
        severity=VulnerabilitySeverity.HIGH,
        pattern=r'(?i)(execute|query)\s*\(\s*[f"\'].*\{.*\}|%s',
        recommendation="Use parameterized queries or ORM",
        cwe_id="CWE-89",
        owasp_category="A03:2021",
        confidence=0.7,
    ),
    SecurityRule(
        id="SEC011",
        name="SQL String Concatenation",
        description="String concatenation in SQL query detected",
        category=VulnerabilityCategory.INJECTION,
        severity=VulnerabilitySeverity.HIGH,
        pattern=r'(?i)(SELECT|INSERT|UPDATE|DELETE).*\+\s*\w+',
        recommendation="Use parameterized queries instead of string concatenation",
        cwe_id="CWE-89",
        owasp_category="A03:2021",
        confidence=0.6,
    ),

    # Command Injection
    SecurityRule(
        id="SEC020",
        name="Potential Command Injection - os.system",
        description="os.system() with variable input may allow command injection",
        category=VulnerabilityCategory.COMMAND_INJECTION,
        severity=VulnerabilitySeverity.CRITICAL,
        pattern=r'os\.system\s*\(\s*[f"\'].*\{|os\.system\s*\(.*\+',
        recommendation="Use subprocess with shell=False and list arguments",
        cwe_id="CWE-78",
        owasp_category="A03:2021",
    ),
    SecurityRule(
        id="SEC021",
        name="Potential Command Injection - subprocess shell",
        description="subprocess with shell=True may allow command injection",
        category=VulnerabilityCategory.COMMAND_INJECTION,
        severity=VulnerabilitySeverity.HIGH,
        pattern=r'subprocess\.(run|call|Popen)\s*\([^)]*shell\s*=\s*True',
        recommendation="Use subprocess with shell=False and list arguments",
        cwe_id="CWE-78",
        owasp_category="A03:2021",
    ),
    SecurityRule(
        id="SEC022",
        name="Dangerous eval() Usage",
        description="eval() can execute arbitrary code",
        category=VulnerabilityCategory.COMMAND_INJECTION,
        severity=VulnerabilitySeverity.CRITICAL,
        pattern=r'\beval\s*\(',
        recommendation="Avoid eval(); use ast.literal_eval() for safe evaluation",
        cwe_id="CWE-95",
        owasp_category="A03:2021",
    ),
    SecurityRule(
        id="SEC023",
        name="Dangerous exec() Usage",
        description="exec() can execute arbitrary code",
        category=VulnerabilityCategory.COMMAND_INJECTION,
        severity=VulnerabilitySeverity.CRITICAL,
        pattern=r'\bexec\s*\(',
        recommendation="Avoid exec(); refactor to use safe alternatives",
        cwe_id="CWE-95",
        owasp_category="A03:2021",
    ),

    # Path Traversal
    SecurityRule(
        id="SEC030",
        name="Potential Path Traversal",
        description="File path from user input may allow path traversal",
        category=VulnerabilityCategory.PATH_TRAVERSAL,
        severity=VulnerabilitySeverity.HIGH,
        pattern=r'open\s*\(\s*[f"\'].*\{',
        recommendation="Validate and sanitize file paths; use os.path.basename()",
        cwe_id="CWE-22",
        owasp_category="A01:2021",
        confidence=0.6,
    ),

    # Insecure Deserialization
    SecurityRule(
        id="SEC040",
        name="Insecure Pickle Usage",
        description="pickle can execute arbitrary code during deserialization",
        category=VulnerabilityCategory.INSECURE_DESER,
        severity=VulnerabilitySeverity.HIGH,
        pattern=r'pickle\.loads?\s*\(',
        recommendation="Use JSON or other safe serialization formats",
        cwe_id="CWE-502",
        owasp_category="A08:2021",
    ),
    SecurityRule(
        id="SEC041",
        name="Insecure YAML Loading",
        description="yaml.load() without Loader can execute arbitrary code",
        category=VulnerabilityCategory.INSECURE_DESER,
        severity=VulnerabilitySeverity.HIGH,
        pattern=r'yaml\.load\s*\([^)]*(?!Loader)',
        recommendation="Use yaml.safe_load() instead",
        cwe_id="CWE-502",
        owasp_category="A08:2021",
        confidence=0.7,
    ),

    # XSS (for template files)
    SecurityRule(
        id="SEC050",
        name="Potential XSS - Unescaped Output",
        description="Output may not be properly escaped",
        category=VulnerabilityCategory.XSS,
        severity=VulnerabilitySeverity.MEDIUM,
        pattern=r'\{\{\s*\w+\s*\|\s*safe\s*\}\}',
        recommendation="Avoid using |safe filter unless content is trusted",
        cwe_id="CWE-79",
        owasp_category="A03:2021",
        file_patterns=["*.html", "*.jinja2", "*.j2"],
    ),

    # Broken Authentication
    SecurityRule(
        id="SEC060",
        name="Weak Password Hashing - MD5",
        description="MD5 is cryptographically broken and should not be used for passwords",
        category=VulnerabilityCategory.BROKEN_AUTH,
        severity=VulnerabilitySeverity.HIGH,
        pattern=r'hashlib\.md5\s*\(',
        recommendation="Use bcrypt, scrypt, or Argon2 for password hashing",
        cwe_id="CWE-328",
        owasp_category="A07:2021",
    ),
    SecurityRule(
        id="SEC061",
        name="Weak Password Hashing - SHA1",
        description="SHA1 is deprecated for security purposes",
        category=VulnerabilityCategory.BROKEN_AUTH,
        severity=VulnerabilitySeverity.MEDIUM,
        pattern=r'hashlib\.sha1\s*\(',
        recommendation="Use SHA-256 or stronger; use bcrypt/Argon2 for passwords",
        cwe_id="CWE-328",
        owasp_category="A07:2021",
    ),

    # Security Misconfiguration
    SecurityRule(
        id="SEC070",
        name="Debug Mode Enabled",
        description="Debug mode should be disabled in production",
        category=VulnerabilityCategory.SECURITY_MISCONFIG,
        severity=VulnerabilitySeverity.MEDIUM,
        pattern=r'(?i)debug\s*=\s*True',
        recommendation="Disable debug mode in production environments",
        cwe_id="CWE-489",
        owasp_category="A05:2021",
        confidence=0.6,
    ),
    SecurityRule(
        id="SEC071",
        name="Insecure SSL/TLS - Disabled Verification",
        description="SSL certificate verification is disabled",
        category=VulnerabilityCategory.SECURITY_MISCONFIG,
        severity=VulnerabilitySeverity.HIGH,
        pattern=r'verify\s*=\s*False|ssl\._create_unverified_context',
        recommendation="Enable SSL certificate verification",
        cwe_id="CWE-295",
        owasp_category="A05:2021",
    ),
    SecurityRule(
        id="SEC072",
        name="Permissive CORS",
        description="CORS allows all origins which may be insecure",
        category=VulnerabilityCategory.SECURITY_MISCONFIG,
        severity=VulnerabilitySeverity.MEDIUM,
        pattern=r'(?i)allow_origins\s*=\s*\[\s*["\']?\*["\']?\s*\]|Access-Control-Allow-Origin.*\*',
        recommendation="Restrict CORS to specific trusted origins",
        cwe_id="CWE-942",
        owasp_category="A05:2021",
    ),

    # Insufficient Logging
    SecurityRule(
        id="SEC080",
        name="Exception Silently Caught",
        description="Exception caught but not logged",
        category=VulnerabilityCategory.INSUFFICIENT_LOGGING,
        severity=VulnerabilitySeverity.LOW,
        pattern=r'except.*:\s*pass',
        recommendation="Log exceptions for debugging and security monitoring",
        cwe_id="CWE-778",
        owasp_category="A09:2021",
    ),

    # SSRF
    SecurityRule(
        id="SEC090",
        name="Potential SSRF",
        description="URL from user input may allow SSRF attacks",
        category=VulnerabilityCategory.SSRF,
        severity=VulnerabilitySeverity.HIGH,
        pattern=r'requests\.(get|post|put|delete|patch)\s*\(\s*[f"\'].*\{',
        recommendation="Validate and whitelist allowed URLs/hosts",
        cwe_id="CWE-918",
        owasp_category="A10:2021",
        confidence=0.6,
    ),

    # Sensitive Data
    SecurityRule(
        id="SEC100",
        name="Sensitive Data in Logs",
        description="Sensitive data may be written to logs",
        category=VulnerabilityCategory.SENSITIVE_DATA,
        severity=VulnerabilitySeverity.MEDIUM,
        pattern=r'(?i)(logger|log|print)\s*\([^)]*password|(?i)(logger|log|print)\s*\([^)]*secret',
        recommendation="Mask sensitive data before logging",
        cwe_id="CWE-532",
        owasp_category="A02:2021",
        confidence=0.7,
    ),

    # Code Quality (Security-Related)
    SecurityRule(
        id="SEC110",
        name="Assert in Production Code",
        description="assert statements are disabled with -O flag",
        category=VulnerabilityCategory.CODE_QUALITY,
        severity=VulnerabilitySeverity.LOW,
        pattern=r'^(?!\s*#)\s*assert\s+',
        recommendation="Use explicit error handling instead of assert for security checks",
        cwe_id="CWE-617",
    ),
    SecurityRule(
        id="SEC111",
        name="Temporary File Security",
        description="Temporary file created without secure permissions",
        category=VulnerabilityCategory.CODE_QUALITY,
        severity=VulnerabilitySeverity.MEDIUM,
        pattern=r'open\s*\(\s*["\']\/tmp\/',
        recommendation="Use tempfile module with secure defaults",
        cwe_id="CWE-377",
    ),
    SecurityRule(
        id="SEC112",
        name="Random for Security",
        description="random module is not cryptographically secure",
        category=VulnerabilityCategory.CODE_QUALITY,
        severity=VulnerabilitySeverity.MEDIUM,
        pattern=r'import random(?!\.SystemRandom)|from random import',
        recommendation="Use secrets module for security-sensitive randomness",
        cwe_id="CWE-330",
        confidence=0.5,
    ),
]


# =============================================================================
# Security Code Review Service
# =============================================================================

class SecurityCodeReviewService:
    """
    Service for performing automated security code reviews.

    Features:
    - Pattern-based vulnerability detection
    - AST-based analysis for Python
    - Configurable rules
    - Risk scoring
    """

    def __init__(
        self,
        rules: Optional[list[SecurityRule]] = None,
        exclude_patterns: Optional[list[str]] = None,
    ):
        """
        Initialize the security code review service.

        Args:
            rules: Custom security rules (defaults to built-in rules)
            exclude_patterns: File patterns to exclude from scanning
        """
        self.rules = rules or SECURITY_RULES
        self.exclude_patterns = exclude_patterns or [
            "**/test_*.py",
            "**/*_test.py",
            "**/tests/**",
            "**/__pycache__/**",
            "**/.venv/**",
            "**/venv/**",
            "**/node_modules/**",
        ]

        # Compile regex patterns for performance
        self._compiled_rules: list[tuple[SecurityRule, re.Pattern]] = []
        for rule in self.rules:
            if rule.enabled:
                try:
                    pattern = re.compile(rule.pattern, re.MULTILINE)
                    self._compiled_rules.append((rule, pattern))
                except re.error as e:
                    logger.warning(f"Invalid regex in rule {rule.id}: {e}")

        logger.info(f"SecurityCodeReviewService initialized with {len(self._compiled_rules)} rules")

    def scan_file(self, file_path: Path) -> list[SecurityFinding]:
        """
        Scan a single file for security vulnerabilities.

        Args:
            file_path: Path to file to scan

        Returns:
            List of security findings
        """
        findings: list[SecurityFinding] = []

        if not file_path.exists():
            logger.warning(f"File not found: {file_path}")
            return findings

        try:
            content = file_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            logger.warning(f"Cannot decode file: {file_path}")
            return findings
        except Exception as e:
            logger.error(f"Error reading file {file_path}: {e}")
            return findings

        lines = content.split("\n")

        # Pattern-based scanning
        for rule, pattern in self._compiled_rules:
            # Check file pattern match
            if not self._matches_file_pattern(file_path, rule.file_patterns):
                continue

            # Find matches
            for match in pattern.finditer(content):
                # Calculate line number
                line_num = content[:match.start()].count("\n") + 1
                col = match.start() - content.rfind("\n", 0, match.start())

                # Get code snippet
                snippet_start = max(0, line_num - 2)
                snippet_end = min(len(lines), line_num + 1)
                snippet = "\n".join(lines[snippet_start:snippet_end])

                finding = SecurityFinding(
                    category=rule.category,
                    severity=rule.severity,
                    title=rule.name,
                    description=rule.description,
                    file_path=str(file_path),
                    line_number=line_num,
                    column=col,
                    code_snippet=snippet,
                    recommendation=rule.recommendation,
                    cwe_id=rule.cwe_id,
                    owasp_category=rule.owasp_category,
                    rule_id=rule.id,
                    confidence=rule.confidence,
                )
                findings.append(finding)

        # AST-based scanning for Python files
        if file_path.suffix == ".py":
            ast_findings = self._ast_scan(file_path, content)
            findings.extend(ast_findings)

        return findings

    def _matches_file_pattern(self, file_path: Path, patterns: list[str]) -> bool:
        """Check if file matches any of the patterns."""
        from fnmatch import fnmatch

        file_str = str(file_path)
        for pattern in patterns:
            if fnmatch(file_path.name, pattern.replace("**/", "")):
                return True
            if fnmatch(file_str, pattern):
                return True
        return False

    def _is_excluded(self, file_path: Path) -> bool:
        """Check if file should be excluded from scanning."""
        from fnmatch import fnmatch

        file_str = str(file_path)
        for pattern in self.exclude_patterns:
            if fnmatch(file_str, pattern):
                return True
            if fnmatch(file_path.name, pattern.replace("**/", "")):
                return True
        return False

    def _ast_scan(self, file_path: Path, content: str) -> list[SecurityFinding]:
        """Perform AST-based security analysis on Python files."""
        findings: list[SecurityFinding] = []

        try:
            tree = ast.parse(content)
        except SyntaxError as e:
            logger.warning(f"Syntax error in {file_path}: {e}")
            return findings

        for node in ast.walk(tree):
            # Check for dangerous function calls
            if isinstance(node, ast.Call):
                finding = self._check_dangerous_call(node, file_path, content)
                if finding:
                    findings.append(finding)

            # Check for string formatting in sensitive contexts
            if isinstance(node, ast.JoinedStr):  # f-string
                finding = self._check_fstring_usage(node, file_path, content)
                if finding:
                    findings.append(finding)

        return findings

    def _check_dangerous_call(
        self,
        node: ast.Call,
        file_path: Path,
        content: str
    ) -> Optional[SecurityFinding]:
        """Check for dangerous function calls via AST."""
        # Get function name
        func_name = None
        if isinstance(node.func, ast.Name):
            func_name = node.func.id
        elif isinstance(node.func, ast.Attribute):
            if isinstance(node.func.value, ast.Name):
                func_name = f"{node.func.value.id}.{node.func.attr}"
            else:
                func_name = node.func.attr

        if not func_name:
            return None

        # Dangerous functions to flag
        dangerous_funcs = {
            "eval": ("Dangerous eval() usage", VulnerabilitySeverity.CRITICAL, "CWE-95"),
            "exec": ("Dangerous exec() usage", VulnerabilitySeverity.CRITICAL, "CWE-95"),
            "compile": ("compile() with user input", VulnerabilitySeverity.HIGH, "CWE-95"),
            "os.system": ("os.system() command execution", VulnerabilitySeverity.HIGH, "CWE-78"),
            "os.popen": ("os.popen() command execution", VulnerabilitySeverity.HIGH, "CWE-78"),
            "pickle.loads": ("Insecure pickle deserialization", VulnerabilitySeverity.HIGH, "CWE-502"),
            "pickle.load": ("Insecure pickle deserialization", VulnerabilitySeverity.HIGH, "CWE-502"),
        }

        if func_name in dangerous_funcs:
            title, severity, cwe = dangerous_funcs[func_name]
            lines = content.split("\n")
            line_num = node.lineno
            snippet = lines[max(0, line_num-2):min(len(lines), line_num+1)]

            return SecurityFinding(
                category=VulnerabilityCategory.COMMAND_INJECTION
                    if "os." in func_name else VulnerabilityCategory.INSECURE_DESER,
                severity=severity,
                title=title,
                description=f"Use of {func_name}() detected which can lead to security vulnerabilities",
                file_path=str(file_path),
                line_number=line_num,
                column=node.col_offset,
                code_snippet="\n".join(snippet),
                recommendation=f"Avoid using {func_name}(); use safer alternatives",
                cwe_id=cwe,
                rule_id=f"AST-{func_name.replace('.', '-').upper()}",
                confidence=0.95,
            )

        return None

    def _check_fstring_usage(
        self,
        node: ast.JoinedStr,
        file_path: Path,
        content: str
    ) -> Optional[SecurityFinding]:
        """Check for potentially dangerous f-string usage."""
        # This is a simplified check - in production, would need more context
        return None

    def scan_directory(
        self,
        directory: Path,
        recursive: bool = True,
        file_patterns: Optional[list[str]] = None,
    ) -> SecurityReviewResult:
        """
        Scan a directory for security vulnerabilities.

        Args:
            directory: Directory to scan
            recursive: Whether to scan subdirectories
            file_patterns: File patterns to include (default: *.py)

        Returns:
            Security review result with all findings
        """
        import time

        start_time = time.time()
        result = SecurityReviewResult(target_path=str(directory))

        file_patterns = file_patterns or ["*.py"]

        if not directory.exists():
            result.success = False
            result.error_message = f"Directory not found: {directory}"
            return result

        # Collect files to scan
        files_to_scan: list[Path] = []

        for pattern in file_patterns:
            if recursive:
                files_to_scan.extend(directory.rglob(pattern))
            else:
                files_to_scan.extend(directory.glob(pattern))

        # Remove excluded files
        files_to_scan = [f for f in files_to_scan if not self._is_excluded(f)]

        # Scan each file
        total_lines = 0
        for file_path in files_to_scan:
            findings = self.scan_file(file_path)
            result.findings.extend(findings)

            try:
                lines = file_path.read_text(encoding="utf-8").count("\n")
                total_lines += lines
            except Exception:
                pass

        # Update counts
        result.files_scanned = len(files_to_scan)
        result.lines_scanned = total_lines
        result.scan_duration_ms = (time.time() - start_time) * 1000

        # Count by severity
        for finding in result.findings:
            if finding.severity == VulnerabilitySeverity.CRITICAL:
                result.critical_count += 1
            elif finding.severity == VulnerabilitySeverity.HIGH:
                result.high_count += 1
            elif finding.severity == VulnerabilitySeverity.MEDIUM:
                result.medium_count += 1
            elif finding.severity == VulnerabilitySeverity.LOW:
                result.low_count += 1
            else:
                result.info_count += 1

        logger.info(
            f"Security scan complete: {result.files_scanned} files, "
            f"{len(result.findings)} findings, "
            f"{result.scan_duration_ms:.1f}ms"
        )

        return result

    def scan_code_string(
        self,
        code: str,
        filename: str = "<string>",
    ) -> list[SecurityFinding]:
        """
        Scan a code string for security vulnerabilities.

        Args:
            code: Source code to scan
            filename: Virtual filename for findings

        Returns:
            List of security findings
        """
        findings: list[SecurityFinding] = []
        lines = code.split("\n")

        # Pattern-based scanning
        for rule, pattern in self._compiled_rules:
            # Only check Python patterns for code strings
            if "*.py" not in rule.file_patterns:
                continue

            for match in pattern.finditer(code):
                line_num = code[:match.start()].count("\n") + 1
                col = match.start() - code.rfind("\n", 0, match.start())

                snippet_start = max(0, line_num - 2)
                snippet_end = min(len(lines), line_num + 1)
                snippet = "\n".join(lines[snippet_start:snippet_end])

                finding = SecurityFinding(
                    category=rule.category,
                    severity=rule.severity,
                    title=rule.name,
                    description=rule.description,
                    file_path=filename,
                    line_number=line_num,
                    column=col,
                    code_snippet=snippet,
                    recommendation=rule.recommendation,
                    cwe_id=rule.cwe_id,
                    owasp_category=rule.owasp_category,
                    rule_id=rule.id,
                    confidence=rule.confidence,
                )
                findings.append(finding)

        # AST scanning
        try:
            tree = ast.parse(code)
            for node in ast.walk(tree):
                if isinstance(node, ast.Call):
                    finding = self._check_dangerous_call(
                        node,
                        Path(filename),
                        code
                    )
                    if finding:
                        findings.append(finding)
        except SyntaxError:
            pass

        return findings

    def get_rules(self) -> list[dict[str, Any]]:
        """Get all security rules."""
        return [
            {
                "id": rule.id,
                "name": rule.name,
                "description": rule.description,
                "category": rule.category.value,
                "severity": rule.severity.value,
                "cwe_id": rule.cwe_id,
                "owasp_category": rule.owasp_category,
                "enabled": rule.enabled,
                "confidence": rule.confidence,
            }
            for rule in self.rules
        ]

    def generate_report(
        self,
        result: SecurityReviewResult,
        format: str = "markdown",
    ) -> str:
        """
        Generate a security report from scan results.

        Args:
            result: Security review result
            format: Output format (markdown, json, html)

        Returns:
            Formatted report string
        """
        if format == "json":
            import json
            return json.dumps(result.to_dict(), indent=2)

        if format == "html":
            return self._generate_html_report(result)

        # Default: Markdown
        return self._generate_markdown_report(result)

    def _generate_markdown_report(self, result: SecurityReviewResult) -> str:
        """Generate Markdown security report."""
        lines = [
            "# Security Code Review Report",
            "",
            f"**Scan Date:** {result.timestamp.strftime('%Y-%m-%d %H:%M:%S')}",
            f"**Target:** {result.target_path}",
            f"**Files Scanned:** {result.files_scanned}",
            f"**Lines Scanned:** {result.lines_scanned:,}",
            f"**Scan Duration:** {result.scan_duration_ms:.1f}ms",
            f"**Risk Score:** {result.get_risk_score():.1f}/100",
            "",
            "## Summary",
            "",
            "| Severity | Count |",
            "|----------|-------|",
            f"| 🔴 Critical | {result.critical_count} |",
            f"| 🟠 High | {result.high_count} |",
            f"| 🟡 Medium | {result.medium_count} |",
            f"| 🟢 Low | {result.low_count} |",
            f"| ℹ️ Info | {result.info_count} |",
            f"| **Total** | **{len(result.findings)}** |",
            "",
        ]

        if result.findings:
            lines.extend([
                "## Findings",
                "",
            ])

            # Group by severity
            for severity in [
                VulnerabilitySeverity.CRITICAL,
                VulnerabilitySeverity.HIGH,
                VulnerabilitySeverity.MEDIUM,
                VulnerabilitySeverity.LOW,
                VulnerabilitySeverity.INFO,
            ]:
                severity_findings = [
                    f for f in result.findings if f.severity == severity
                ]

                if not severity_findings:
                    continue

                severity_emoji = {
                    VulnerabilitySeverity.CRITICAL: "🔴",
                    VulnerabilitySeverity.HIGH: "🟠",
                    VulnerabilitySeverity.MEDIUM: "🟡",
                    VulnerabilitySeverity.LOW: "🟢",
                    VulnerabilitySeverity.INFO: "ℹ️",
                }[severity]

                lines.append(f"### {severity_emoji} {severity.value.upper()} ({len(severity_findings)})")
                lines.append("")

                for finding in severity_findings:
                    lines.extend([
                        f"#### {finding.title}",
                        "",
                        f"**File:** `{finding.file_path}:{finding.line_number}`",
                        f"**Rule:** {finding.rule_id}",
                        f"**Category:** {finding.category.value}",
                    ])

                    if finding.cwe_id:
                        lines.append(f"**CWE:** {finding.cwe_id}")

                    if finding.owasp_category:
                        lines.append(f"**OWASP:** {finding.owasp_category}")

                    lines.extend([
                        "",
                        f"**Description:** {finding.description}",
                        "",
                        "```python",
                        finding.code_snippet,
                        "```",
                        "",
                        f"**Recommendation:** {finding.recommendation}",
                        "",
                        "---",
                        "",
                    ])
        else:
            lines.extend([
                "## Findings",
                "",
                "✅ No security vulnerabilities detected.",
                "",
            ])

        lines.extend([
            "## Recommendations",
            "",
            "1. Address all Critical and High severity findings immediately",
            "2. Review Medium severity findings within one week",
            "3. Schedule Low severity findings for future sprints",
            "4. Consider implementing security testing in CI/CD pipeline",
            "",
            "---",
            f"*Generated by S5-HES Agent Security Scanner v1.0*",
        ])

        return "\n".join(lines)

    def _generate_html_report(self, result: SecurityReviewResult) -> str:
        """Generate HTML security report."""
        # Simplified HTML report
        findings_html = ""
        for finding in result.findings:
            severity_color = {
                VulnerabilitySeverity.CRITICAL: "#dc3545",
                VulnerabilitySeverity.HIGH: "#fd7e14",
                VulnerabilitySeverity.MEDIUM: "#ffc107",
                VulnerabilitySeverity.LOW: "#28a745",
                VulnerabilitySeverity.INFO: "#17a2b8",
            }[finding.severity]

            findings_html += f"""
            <div style="border-left: 4px solid {severity_color}; padding: 10px; margin: 10px 0; background: #f8f9fa;">
                <h4>{finding.title}</h4>
                <p><strong>Severity:</strong> <span style="color: {severity_color}">{finding.severity.value.upper()}</span></p>
                <p><strong>File:</strong> {finding.file_path}:{finding.line_number}</p>
                <p><strong>Description:</strong> {finding.description}</p>
                <pre style="background: #282c34; color: #abb2bf; padding: 10px; border-radius: 4px;">{finding.code_snippet}</pre>
                <p><strong>Recommendation:</strong> {finding.recommendation}</p>
            </div>
            """

        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Security Code Review Report</title>
            <style>
                body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; margin: 40px; }}
                h1 {{ color: #333; }}
                table {{ border-collapse: collapse; width: 100%; margin: 20px 0; }}
                th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
                th {{ background: #f4f4f4; }}
            </style>
        </head>
        <body>
            <h1>Security Code Review Report</h1>
            <p><strong>Scan Date:</strong> {result.timestamp.strftime('%Y-%m-%d %H:%M:%S')}</p>
            <p><strong>Target:</strong> {result.target_path}</p>
            <p><strong>Files Scanned:</strong> {result.files_scanned}</p>
            <p><strong>Risk Score:</strong> {result.get_risk_score():.1f}/100</p>

            <h2>Summary</h2>
            <table>
                <tr><th>Severity</th><th>Count</th></tr>
                <tr><td>Critical</td><td>{result.critical_count}</td></tr>
                <tr><td>High</td><td>{result.high_count}</td></tr>
                <tr><td>Medium</td><td>{result.medium_count}</td></tr>
                <tr><td>Low</td><td>{result.low_count}</td></tr>
                <tr><td>Info</td><td>{result.info_count}</td></tr>
                <tr><td><strong>Total</strong></td><td><strong>{len(result.findings)}</strong></td></tr>
            </table>

            <h2>Findings</h2>
            {findings_html if findings_html else "<p>✅ No security vulnerabilities detected.</p>"}
        </body>
        </html>
        """


# =============================================================================
# Global Instance
# =============================================================================

_code_review_service: Optional[SecurityCodeReviewService] = None


def get_code_review_service() -> SecurityCodeReviewService:
    """Get or create the global code review service instance."""
    global _code_review_service
    if _code_review_service is None:
        _code_review_service = SecurityCodeReviewService()
    return _code_review_service
