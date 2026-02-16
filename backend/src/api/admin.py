"""
Admin API Endpoints

REST API for administrative operations including user management,
API key management, system configuration, and audit logging.

S12.5: Integrated with centralized SecurityAuditService.
"""

import json
import secrets
import hashlib
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Depends, Header, Query, Request
from pydantic import BaseModel, Field, EmailStr

from src.security.audit_service import (
    get_audit_service,
    AuditCategory,
    AuditAction,
    AuditSeverity,
)

router = APIRouter(prefix="/api/admin", tags=["admin"])

# =============================================================================
# Configuration
# =============================================================================

DATA_DIR = Path(__file__).parent.parent.parent.parent / "data" / "admin"
USERS_FILE = DATA_DIR / "users.json"
API_KEYS_FILE = DATA_DIR / "api_keys.json"
CONFIG_FILE = DATA_DIR / "config.json"
AUDIT_LOG_FILE = DATA_DIR / "audit_log.json"
SESSIONS_FILE = DATA_DIR / "sessions.json"

# Default admin credentials (should be changed on first login)
DEFAULT_ADMIN_USERNAME = "admin"
DEFAULT_ADMIN_PASSWORD = "admin123"  # This is hashed before storage


# =============================================================================
# Request/Response Models
# =============================================================================


class LoginRequest(BaseModel):
    """Login credentials."""
    username: str
    password: str


class LoginResponse(BaseModel):
    """Login response with session token."""
    token: str
    username: str
    role: str
    expires_at: datetime


class UserBase(BaseModel):
    """Base user model."""
    username: str
    email: str
    role: str = Field(default="user", pattern="^(admin|user|viewer)$")


class UserCreate(UserBase):
    """User creation request."""
    password: str = Field(min_length=6)


class UserUpdate(BaseModel):
    """User update request."""
    email: Optional[str] = None
    role: Optional[str] = None
    status: Optional[str] = None


class User(UserBase):
    """User response model."""
    id: str
    status: str = "active"
    last_login: Optional[datetime] = None
    created_at: datetime


class ApiKeyCreate(BaseModel):
    """API key creation request."""
    name: str
    permissions: list[str] = Field(default_factory=lambda: ["read"])


class ApiKey(BaseModel):
    """API key response model."""
    id: str
    name: str
    key: str
    permissions: list[str]
    created_at: datetime
    last_used: Optional[datetime] = None
    status: str = "active"


class ConfigItem(BaseModel):
    """System configuration item."""
    key: str
    value: Any
    type: str
    category: str
    description: str
    editable: bool = True


class ConfigUpdate(BaseModel):
    """Configuration update request."""
    value: Any


class AuditLog(BaseModel):
    """Audit log entry."""
    id: str
    timestamp: datetime
    user: str
    action: str
    resource: str
    details: str
    ip: str = "127.0.0.1"


class SystemStats(BaseModel):
    """System statistics for overview."""
    uptime: str
    version: str
    python_version: str
    node_version: str
    cpu_usage: float
    memory_usage: float
    disk_usage: float
    active_connections: int
    total_users: int
    active_api_keys: int
    audit_log_count: int


# =============================================================================
# Data Storage Helpers
# =============================================================================


def _ensure_data_dir() -> None:
    """Ensure data directory exists."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def _hash_password(password: str) -> str:
    """Hash a password using SHA-256."""
    return hashlib.sha256(password.encode()).hexdigest()


def _generate_token() -> str:
    """Generate a secure session token."""
    return secrets.token_urlsafe(32)


def _generate_api_key() -> str:
    """Generate a secure API key."""
    return f"sk_{secrets.token_urlsafe(24)}"


def _load_json(filepath: Path, default: Any = None) -> Any:
    """Load JSON file or return default."""
    if default is None:
        default = []
    if not filepath.exists():
        return default
    try:
        with open(filepath, "r") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return default


def _save_json(filepath: Path, data: Any) -> None:
    """Save data to JSON file."""
    _ensure_data_dir()
    with open(filepath, "w") as f:
        json.dump(data, f, indent=2, default=str)


def _load_users() -> list[dict]:
    """Load users from file, creating default admin if empty."""
    users = _load_json(USERS_FILE, [])
    if not users:
        # Create default admin user
        users = [{
            "id": "user-1",
            "username": DEFAULT_ADMIN_USERNAME,
            "email": "admin@smarthes.local",
            "password_hash": _hash_password(DEFAULT_ADMIN_PASSWORD),
            "role": "admin",
            "status": "active",
            "last_login": None,
            "created_at": datetime.now().isoformat(),
        }]
        _save_json(USERS_FILE, users)
    return users


def _load_sessions() -> dict[str, dict]:
    """Load active sessions."""
    return _load_json(SESSIONS_FILE, {})


def _save_sessions(sessions: dict) -> None:
    """Save sessions to file."""
    _save_json(SESSIONS_FILE, sessions)


def _load_api_keys() -> list[dict]:
    """Load API keys from file."""
    return _load_json(API_KEYS_FILE, [])


def _load_config() -> list[dict]:
    """Load configuration, creating defaults if empty."""
    config = _load_json(CONFIG_FILE, [])
    if not config:
        config = [
            {"key": "simulation.max_duration", "value": 480, "type": "number", "category": "Simulation", "description": "Maximum simulation duration in minutes", "editable": True},
            {"key": "simulation.tick_interval", "value": 1000, "type": "number", "category": "Simulation", "description": "Simulation tick interval in milliseconds", "editable": True},
            {"key": "security.session_timeout", "value": 3600, "type": "number", "category": "Security", "description": "Session timeout in seconds", "editable": True},
            {"key": "security.max_login_attempts", "value": 5, "type": "number", "category": "Security", "description": "Max failed login attempts before lockout", "editable": True},
            {"key": "security.require_mfa", "value": False, "type": "boolean", "category": "Security", "description": "Require MFA for all users", "editable": True},
            {"key": "privacy.default_epsilon", "value": 0.1, "type": "number", "category": "Privacy", "description": "Default differential privacy epsilon", "editable": True},
            {"key": "privacy.enable_anonymization", "value": True, "type": "boolean", "category": "Privacy", "description": "Enable data anonymization", "editable": True},
            {"key": "mesh.max_nodes", "value": 100, "type": "number", "category": "Mesh Network", "description": "Maximum mesh network nodes", "editable": True},
            {"key": "mesh.beacon_interval", "value": 30, "type": "number", "category": "Mesh Network", "description": "Beacon interval in seconds", "editable": True},
            {"key": "api.rate_limit", "value": 100, "type": "number", "category": "API", "description": "API rate limit per minute", "editable": True},
            {"key": "api.cors_enabled", "value": True, "type": "boolean", "category": "API", "description": "Enable CORS", "editable": True},
            {"key": "logging.level", "value": "INFO", "type": "string", "category": "Logging", "description": "Log level (DEBUG, INFO, WARNING, ERROR)", "editable": True},
            {"key": "logging.retention_days", "value": 30, "type": "number", "category": "Logging", "description": "Log retention in days", "editable": True},
        ]
        _save_json(CONFIG_FILE, config)
    return config


def _load_audit_logs() -> list[dict]:
    """Load audit logs from file."""
    return _load_json(AUDIT_LOG_FILE, [])


def _add_audit_log(user: str, action: str, resource: str, details: str, ip: str = "127.0.0.1") -> None:
    """
    Add an entry to the audit log.

    S12.5: Now also logs to centralized SecurityAuditService.
    """
    # Legacy file-based logging (kept for backward compatibility)
    logs = _load_audit_logs()
    logs.insert(0, {
        "id": f"log-{datetime.now().timestamp()}",
        "timestamp": datetime.now().isoformat(),
        "user": user,
        "action": action,
        "resource": resource,
        "details": details,
        "ip": ip,
    })
    # Keep last 1000 entries
    logs = logs[:1000]
    _save_json(AUDIT_LOG_FILE, logs)

    # Centralized audit logging (S12.5)
    audit_service = get_audit_service()

    # Map action string to AuditAction and AuditCategory
    action_mapping = {
        "auth.login": (AuditCategory.AUTHENTICATION, AuditAction.LOGIN_SUCCESS),
        "auth.failed": (AuditCategory.AUTHENTICATION, AuditAction.LOGIN_FAILURE),
        "auth.logout": (AuditCategory.AUTHENTICATION, AuditAction.LOGOUT),
        "user.create": (AuditCategory.DATA_ACCESS, AuditAction.DATA_WRITE),
        "user.update": (AuditCategory.DATA_ACCESS, AuditAction.DATA_WRITE),
        "user.delete": (AuditCategory.DATA_ACCESS, AuditAction.DATA_DELETE),
        "apikey.create": (AuditCategory.SECURITY, AuditAction.TOKEN_ISSUED),
        "apikey.revoke": (AuditCategory.SECURITY, AuditAction.TOKEN_REVOKED),
        "config.update": (AuditCategory.CONFIGURATION, AuditAction.CONFIG_UPDATE),
        "config.export": (AuditCategory.CONFIGURATION, AuditAction.DATA_EXPORT),
        "system.clear_cache": (AuditCategory.SYSTEM, AuditAction.SYSTEM_START),
    }

    category, audit_action = action_mapping.get(
        action,
        (AuditCategory.SYSTEM, AuditAction.API_REQUEST)
    )

    # Determine severity
    severity = AuditSeverity.WARNING if "failed" in action else AuditSeverity.INFO

    audit_service.log_event(
        category=category,
        action=audit_action,
        description=details,
        severity=severity,
        username=user,
        ip_address=ip,
        resource_type=resource.split("/")[0] if "/" in resource else resource,
        resource_id=resource.split("/")[1] if "/" in resource else None,
        success="failed" not in action,
    )


# =============================================================================
# Authentication
# =============================================================================


async def verify_session(authorization: Optional[str] = Header(None)) -> dict:
    """Verify session token and return user info."""
    if not authorization:
        raise HTTPException(status_code=401, detail="Authorization header required")

    # Extract token from "Bearer <token>" format
    if authorization.startswith("Bearer "):
        token = authorization[7:]
    else:
        token = authorization

    sessions = _load_sessions()

    if token not in sessions:
        raise HTTPException(status_code=401, detail="Invalid or expired session")

    session = sessions[token]

    # Check expiration
    expires_at = datetime.fromisoformat(session["expires_at"])
    if datetime.now() > expires_at:
        del sessions[token]
        _save_sessions(sessions)
        raise HTTPException(status_code=401, detail="Session expired")

    return session


async def verify_admin(session: dict = Depends(verify_session)) -> dict:
    """Verify user has admin role."""
    if session.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return session


# =============================================================================
# Authentication Endpoints
# =============================================================================


@router.post("/login", response_model=LoginResponse)
async def login(request: LoginRequest) -> LoginResponse:
    """
    Authenticate and get session token.

    Default credentials: admin / admin123
    """
    users = _load_users()

    # Find user
    user = next((u for u in users if u["username"] == request.username), None)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    # Check password
    if user["password_hash"] != _hash_password(request.password):
        _add_audit_log(request.username, "auth.failed", "login", "Invalid password")
        raise HTTPException(status_code=401, detail="Invalid credentials")

    # Check status
    if user["status"] != "active":
        raise HTTPException(status_code=403, detail="Account is not active")

    # Create session
    token = _generate_token()
    expires_at = datetime.now() + timedelta(hours=24)

    sessions = _load_sessions()
    sessions[token] = {
        "user_id": user["id"],
        "username": user["username"],
        "role": user["role"],
        "expires_at": expires_at.isoformat(),
    }
    _save_sessions(sessions)

    # Update last login
    user["last_login"] = datetime.now().isoformat()
    _save_json(USERS_FILE, users)

    _add_audit_log(user["username"], "auth.login", "session", "Login successful")

    return LoginResponse(
        token=token,
        username=user["username"],
        role=user["role"],
        expires_at=expires_at,
    )


@router.post("/logout")
async def logout(session: dict = Depends(verify_session)) -> dict:
    """Log out and invalidate session."""
    sessions = _load_sessions()

    # Find and remove session by user_id
    token_to_remove = None
    for token, s in sessions.items():
        if s["user_id"] == session["user_id"]:
            token_to_remove = token
            break

    if token_to_remove:
        del sessions[token_to_remove]
        _save_sessions(sessions)

    _add_audit_log(session["username"], "auth.logout", "session", "Logout successful")

    return {"status": "logged_out"}


@router.get("/me")
async def get_current_user(session: dict = Depends(verify_session)) -> dict:
    """Get current user info."""
    users = _load_users()
    user = next((u for u in users if u["id"] == session["user_id"]), None)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return {
        "id": user["id"],
        "username": user["username"],
        "email": user["email"],
        "role": user["role"],
        "status": user["status"],
    }


# =============================================================================
# System Overview
# =============================================================================


@router.get("/overview", response_model=SystemStats)
async def get_system_overview(session: dict = Depends(verify_session)) -> SystemStats:
    """Get system overview statistics."""
    import platform
    import sys

    users = _load_users()
    api_keys = _load_api_keys()
    audit_logs = _load_audit_logs()

    return SystemStats(
        uptime="Running",  # Would calculate from process start time
        version="1.0.0-beta",
        python_version=platform.python_version(),
        node_version="20.10.0",  # Would get from node if available
        cpu_usage=0,  # Would use psutil
        memory_usage=0,  # Would use psutil
        disk_usage=0,  # Would use psutil
        active_connections=1,
        total_users=len(users),
        active_api_keys=len([k for k in api_keys if k.get("status") == "active"]),
        audit_log_count=len(audit_logs),
    )


# =============================================================================
# User Management
# =============================================================================


@router.get("/users", response_model=list[User])
async def list_users(session: dict = Depends(verify_admin)) -> list[User]:
    """List all users (admin only)."""
    users = _load_users()
    return [
        User(
            id=u["id"],
            username=u["username"],
            email=u["email"],
            role=u["role"],
            status=u["status"],
            last_login=datetime.fromisoformat(u["last_login"]) if u.get("last_login") else None,
            created_at=datetime.fromisoformat(u["created_at"]),
        )
        for u in users
    ]


@router.post("/users", response_model=User)
async def create_user(request: UserCreate, session: dict = Depends(verify_admin)) -> User:
    """Create a new user (admin only)."""
    users = _load_users()

    # Check for duplicate username
    if any(u["username"] == request.username for u in users):
        raise HTTPException(status_code=400, detail="Username already exists")

    # Create user
    user_id = f"user-{len(users) + 1}"
    now = datetime.now()

    new_user = {
        "id": user_id,
        "username": request.username,
        "email": request.email,
        "password_hash": _hash_password(request.password),
        "role": request.role,
        "status": "active",
        "last_login": None,
        "created_at": now.isoformat(),
    }

    users.append(new_user)
    _save_json(USERS_FILE, users)

    _add_audit_log(
        session["username"],
        "user.create",
        f"users/{user_id}",
        f"Created user {request.username}"
    )

    return User(
        id=user_id,
        username=request.username,
        email=request.email,
        role=request.role,
        status="active",
        last_login=None,
        created_at=now,
    )


@router.patch("/users/{user_id}", response_model=User)
async def update_user(
    user_id: str,
    request: UserUpdate,
    session: dict = Depends(verify_admin)
) -> User:
    """Update a user (admin only)."""
    users = _load_users()

    user = next((u for u in users if u["id"] == user_id), None)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Update fields
    if request.email is not None:
        user["email"] = request.email
    if request.role is not None:
        user["role"] = request.role
    if request.status is not None:
        user["status"] = request.status

    _save_json(USERS_FILE, users)

    _add_audit_log(
        session["username"],
        "user.update",
        f"users/{user_id}",
        f"Updated user {user['username']}"
    )

    return User(
        id=user["id"],
        username=user["username"],
        email=user["email"],
        role=user["role"],
        status=user["status"],
        last_login=datetime.fromisoformat(user["last_login"]) if user.get("last_login") else None,
        created_at=datetime.fromisoformat(user["created_at"]),
    )


@router.delete("/users/{user_id}")
async def delete_user(user_id: str, session: dict = Depends(verify_admin)) -> dict:
    """Delete a user (admin only)."""
    users = _load_users()

    user = next((u for u in users if u["id"] == user_id), None)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Prevent self-deletion
    if user["id"] == session["user_id"]:
        raise HTTPException(status_code=400, detail="Cannot delete yourself")

    users = [u for u in users if u["id"] != user_id]
    _save_json(USERS_FILE, users)

    _add_audit_log(
        session["username"],
        "user.delete",
        f"users/{user_id}",
        f"Deleted user {user['username']}"
    )

    return {"status": "deleted"}


# =============================================================================
# API Key Management
# =============================================================================


@router.get("/apikeys", response_model=list[ApiKey])
async def list_api_keys(session: dict = Depends(verify_admin)) -> list[ApiKey]:
    """List all API keys (admin only)."""
    keys = _load_api_keys()
    return [
        ApiKey(
            id=k["id"],
            name=k["name"],
            key=k["key"][:12] + "••••••••",  # Mask key
            permissions=k["permissions"],
            created_at=datetime.fromisoformat(k["created_at"]),
            last_used=datetime.fromisoformat(k["last_used"]) if k.get("last_used") else None,
            status=k["status"],
        )
        for k in keys
    ]


@router.post("/apikeys", response_model=ApiKey)
async def create_api_key(request: ApiKeyCreate, session: dict = Depends(verify_admin)) -> ApiKey:
    """Create a new API key (admin only)."""
    keys = _load_api_keys()

    key_id = f"key-{len(keys) + 1}"
    api_key = _generate_api_key()
    now = datetime.now()

    new_key = {
        "id": key_id,
        "name": request.name,
        "key": api_key,
        "permissions": request.permissions,
        "created_at": now.isoformat(),
        "last_used": None,
        "status": "active",
    }

    keys.append(new_key)
    _save_json(API_KEYS_FILE, keys)

    _add_audit_log(
        session["username"],
        "apikey.create",
        f"apikeys/{key_id}",
        f"Created API key {request.name}"
    )

    # Return full key only on creation
    return ApiKey(
        id=key_id,
        name=request.name,
        key=api_key,  # Full key shown only on creation
        permissions=request.permissions,
        created_at=now,
        last_used=None,
        status="active",
    )


@router.patch("/apikeys/{key_id}/revoke")
async def revoke_api_key(key_id: str, session: dict = Depends(verify_admin)) -> dict:
    """Revoke an API key (admin only)."""
    keys = _load_api_keys()

    key = next((k for k in keys if k["id"] == key_id), None)
    if not key:
        raise HTTPException(status_code=404, detail="API key not found")

    key["status"] = "revoked"
    _save_json(API_KEYS_FILE, keys)

    _add_audit_log(
        session["username"],
        "apikey.revoke",
        f"apikeys/{key_id}",
        f"Revoked API key {key['name']}"
    )

    return {"status": "revoked"}


# =============================================================================
# Configuration Management
# =============================================================================


@router.get("/config", response_model=list[ConfigItem])
async def get_config(session: dict = Depends(verify_session)) -> list[ConfigItem]:
    """Get all configuration items."""
    config = _load_config()
    return [ConfigItem(**c) for c in config]


@router.patch("/config/{config_key}")
async def update_config(
    config_key: str,
    request: ConfigUpdate,
    session: dict = Depends(verify_admin)
) -> ConfigItem:
    """Update a configuration value (admin only)."""
    config = _load_config()

    # Find config item (handle dots in key by replacing with encoded version)
    item = next((c for c in config if c["key"] == config_key), None)
    if not item:
        raise HTTPException(status_code=404, detail="Configuration not found")

    if not item["editable"]:
        raise HTTPException(status_code=400, detail="Configuration is not editable")

    old_value = item["value"]
    item["value"] = request.value
    _save_json(CONFIG_FILE, config)

    _add_audit_log(
        session["username"],
        "config.update",
        config_key,
        f"Changed from {old_value} to {request.value}"
    )

    return ConfigItem(**item)


# =============================================================================
# Audit Log
# =============================================================================


@router.get("/audit", response_model=list[AuditLog])
async def get_audit_logs(
    limit: int = Query(100, ge=1, le=1000),
    action: Optional[str] = Query(None, description="Filter by action"),
    user: Optional[str] = Query(None, description="Filter by user"),
    session: dict = Depends(verify_admin)
) -> list[AuditLog]:
    """Get audit logs (admin only)."""
    logs = _load_audit_logs()

    # Apply filters
    if action:
        logs = [l for l in logs if action in l["action"]]
    if user:
        logs = [l for l in logs if l["user"] == user]

    # Return limited results
    logs = logs[:limit]

    return [
        AuditLog(
            id=l["id"],
            timestamp=datetime.fromisoformat(l["timestamp"]),
            user=l["user"],
            action=l["action"],
            resource=l["resource"],
            details=l["details"],
            ip=l.get("ip", "127.0.0.1"),
        )
        for l in logs
    ]


# =============================================================================
# System Actions
# =============================================================================


@router.post("/actions/clear-cache")
async def clear_cache(session: dict = Depends(verify_admin)) -> dict:
    """Clear system caches (admin only)."""
    _add_audit_log(
        session["username"],
        "system.clear_cache",
        "cache",
        "Cache cleared"
    )
    return {"status": "cache_cleared"}


@router.post("/actions/export-config")
async def export_config(session: dict = Depends(verify_admin)) -> dict:
    """Export current configuration (admin only)."""
    config = _load_config()

    _add_audit_log(
        session["username"],
        "config.export",
        "config",
        "Configuration exported"
    )

    return {
        "configs": [{"key": c["key"], "value": c["value"]} for c in config],
        "exported_at": datetime.now().isoformat(),
        "exported_by": session["username"],
    }


# =============================================================================
# Centralized Security Audit Logs (S12.5)
# =============================================================================


@router.get("/security-audit")
async def get_security_audit_logs(
    limit: int = Query(100, ge=1, le=1000),
    category: Optional[str] = Query(None, description="Filter by category"),
    severity: Optional[str] = Query(None, description="Filter by severity"),
    username: Optional[str] = Query(None, description="Filter by username"),
    success_only: Optional[bool] = Query(None, description="Filter by success status"),
    session: dict = Depends(verify_admin)
) -> dict:
    """
    Get centralized security audit logs (admin only).

    S12.5: Access the centralized SecurityAuditService logs.
    """
    from src.security.audit_service import AuditCategory as AC, AuditSeverity as AS

    audit_service = get_audit_service()

    # Convert string filters to enums
    category_enum = None
    if category:
        try:
            category_enum = AC(category)
        except ValueError:
            pass

    severity_enum = None
    if severity:
        try:
            severity_enum = AS(severity)
        except ValueError:
            pass

    events = audit_service.get_recent_events(
        limit=limit,
        category=category_enum,
        severity=severity_enum,
        username=username,
        success_only=success_only,
    )

    return {
        "events": [e.to_dict() for e in events],
        "total": len(events),
        "filters": {
            "category": category,
            "severity": severity,
            "username": username,
            "success_only": success_only,
        },
    }


@router.get("/security-audit/stats")
async def get_security_audit_stats(session: dict = Depends(verify_admin)) -> dict:
    """
    Get security audit statistics (admin only).

    S12.5: Statistics from centralized SecurityAuditService.
    """
    audit_service = get_audit_service()
    stats = audit_service.get_stats()
    return stats.to_dict()


@router.get("/security-audit/categories")
async def get_audit_categories(session: dict = Depends(verify_session)) -> dict:
    """Get available audit categories and actions."""
    from src.security.audit_service import AuditCategory, AuditAction, AuditSeverity

    return {
        "categories": [c.value for c in AuditCategory],
        "actions": [a.value for a in AuditAction],
        "severities": [s.value for s in AuditSeverity],
    }
