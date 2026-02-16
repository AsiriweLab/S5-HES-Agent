"""
Authentication Manager - User and device authentication simulation.

Sprint 12 - S12.3: Implement AuthenticationManager
Sprint 12 - S12.4: Add OAuth 2.0 flow simulation

Features:
- Multiple authentication methods
- OAuth 2.0 flows (Authorization Code, Client Credentials, Device Code)
- Token management (JWT-like)
- Session management
- Rate limiting and lockout
"""

import asyncio
import hashlib
import secrets
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Optional
from uuid import uuid4
from loguru import logger


class AuthMethod(str, Enum):
    """Authentication methods."""
    PASSWORD = "password"
    API_KEY = "api_key"
    CERTIFICATE = "certificate"
    OAUTH2 = "oauth2"
    MFA = "mfa"
    DEVICE_CODE = "device_code"
    BIOMETRIC = "biometric"


class OAuth2Flow(str, Enum):
    """OAuth 2.0 grant types."""
    AUTHORIZATION_CODE = "authorization_code"
    CLIENT_CREDENTIALS = "client_credentials"
    DEVICE_CODE = "device_code"
    REFRESH_TOKEN = "refresh_token"
    IMPLICIT = "implicit"  # Deprecated but supported for legacy


class TokenType(str, Enum):
    """Token types."""
    ACCESS = "access"
    REFRESH = "refresh"
    ID = "id"
    API_KEY = "api_key"
    DEVICE = "device"


class AuthStatus(str, Enum):
    """Authentication status."""
    PENDING = "pending"
    AUTHENTICATED = "authenticated"
    EXPIRED = "expired"
    REVOKED = "revoked"
    LOCKED = "locked"
    FAILED = "failed"


@dataclass
class AuthToken:
    """Authentication token."""
    id: str = field(default_factory=lambda: str(uuid4()))
    token_type: TokenType = TokenType.ACCESS
    token_value: str = field(default_factory=lambda: secrets.token_urlsafe(32))
    subject: str = ""  # User or device ID
    issuer: str = "smart-hes"
    audience: str = ""
    scope: list[str] = field(default_factory=list)
    issued_at: datetime = field(default_factory=datetime.now)
    expires_at: datetime = field(default_factory=lambda: datetime.now() + timedelta(hours=1))
    not_before: datetime = field(default_factory=datetime.now)
    claims: dict[str, Any] = field(default_factory=dict)
    revoked: bool = False

    @property
    def is_valid(self) -> bool:
        """Check if token is currently valid."""
        now = datetime.now()
        return (not self.revoked and
                self.not_before <= now <= self.expires_at)

    @property
    def is_expired(self) -> bool:
        """Check if token is expired."""
        return datetime.now() > self.expires_at

    @property
    def seconds_until_expiry(self) -> int:
        """Seconds until token expires."""
        delta = self.expires_at - datetime.now()
        return max(0, int(delta.total_seconds()))

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary (JWT-like format)."""
        return {
            "jti": self.id,
            "typ": self.token_type.value,
            "sub": self.subject,
            "iss": self.issuer,
            "aud": self.audience,
            "scope": " ".join(self.scope),
            "iat": int(self.issued_at.timestamp()),
            "exp": int(self.expires_at.timestamp()),
            "nbf": int(self.not_before.timestamp()),
            **self.claims,
        }

    def to_response(self) -> dict[str, Any]:
        """Convert to OAuth 2.0 token response format."""
        return {
            "access_token": self.token_value,
            "token_type": "Bearer",
            "expires_in": self.seconds_until_expiry,
            "scope": " ".join(self.scope),
        }


@dataclass
class AuthSession:
    """Authentication session."""
    id: str = field(default_factory=lambda: str(uuid4()))
    subject_id: str = ""
    subject_type: str = "user"  # user, device, service
    auth_method: AuthMethod = AuthMethod.PASSWORD
    status: AuthStatus = AuthStatus.PENDING
    access_token_id: Optional[str] = None
    refresh_token_id: Optional[str] = None
    ip_address: str = ""
    user_agent: str = ""
    created_at: datetime = field(default_factory=datetime.now)
    last_activity: datetime = field(default_factory=datetime.now)
    expires_at: datetime = field(default_factory=lambda: datetime.now() + timedelta(hours=8))
    mfa_verified: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def is_expired(self) -> bool:
        return datetime.now() > self.expires_at

    @property
    def is_active(self) -> bool:
        return (self.status == AuthStatus.AUTHENTICATED and
                not self.is_expired)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "subject_id": self.subject_id,
            "subject_type": self.subject_type,
            "auth_method": self.auth_method.value,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "last_activity": self.last_activity.isoformat(),
            "expires_at": self.expires_at.isoformat(),
            "is_active": self.is_active,
            "mfa_verified": self.mfa_verified,
        }


@dataclass
class OAuth2Config:
    """OAuth 2.0 configuration."""
    client_id: str = ""
    client_secret: str = field(default_factory=lambda: secrets.token_urlsafe(32))
    redirect_uris: list[str] = field(default_factory=list)
    allowed_scopes: list[str] = field(default_factory=lambda: ["read", "write", "admin"])
    allowed_grant_types: list[OAuth2Flow] = field(default_factory=lambda: [
        OAuth2Flow.AUTHORIZATION_CODE,
        OAuth2Flow.CLIENT_CREDENTIALS,
        OAuth2Flow.REFRESH_TOKEN,
    ])
    access_token_lifetime: int = 3600  # seconds
    refresh_token_lifetime: int = 86400  # seconds
    authorization_code_lifetime: int = 600  # seconds
    require_pkce: bool = True  # Proof Key for Code Exchange


@dataclass
class OAuth2AuthorizationCode:
    """OAuth 2.0 authorization code."""
    code: str = field(default_factory=lambda: secrets.token_urlsafe(32))
    client_id: str = ""
    redirect_uri: str = ""
    scope: list[str] = field(default_factory=list)
    user_id: str = ""
    code_challenge: Optional[str] = None
    code_challenge_method: str = "S256"
    created_at: datetime = field(default_factory=datetime.now)
    expires_at: datetime = field(default_factory=lambda: datetime.now() + timedelta(minutes=10))
    used: bool = False


@dataclass
class DeviceAuthorizationRequest:
    """OAuth 2.0 Device Authorization request."""
    device_code: str = field(default_factory=lambda: secrets.token_urlsafe(32))
    user_code: str = field(default_factory=lambda: secrets.token_hex(4).upper())
    verification_uri: str = "https://smart-hes.local/device"
    client_id: str = ""
    scope: list[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    expires_at: datetime = field(default_factory=lambda: datetime.now() + timedelta(minutes=15))
    interval: int = 5  # Polling interval in seconds
    authorized: bool = False
    user_id: Optional[str] = None


@dataclass
class AuthConfig:
    """Authentication configuration."""
    # Password settings
    min_password_length: int = 8
    require_special_chars: bool = True
    password_hash_algorithm: str = "sha256"
    # Lockout settings
    max_failed_attempts: int = 5
    lockout_duration_minutes: int = 30
    # Session settings
    session_timeout_minutes: int = 480  # 8 hours
    max_concurrent_sessions: int = 5
    # Token settings
    access_token_lifetime_seconds: int = 3600
    refresh_token_lifetime_seconds: int = 86400
    # MFA settings
    mfa_enabled: bool = True
    mfa_required_for_admin: bool = True
    # Simulation
    simulation_mode: bool = True
    auth_latency_ms: int = 100


@dataclass
class AuthStats:
    """Authentication statistics."""
    total_authentications: int = 0
    successful_authentications: int = 0
    failed_authentications: int = 0
    tokens_issued: int = 0
    tokens_revoked: int = 0
    sessions_created: int = 0
    sessions_terminated: int = 0
    lockouts: int = 0
    mfa_challenges: int = 0
    oauth_flows: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_authentications": self.total_authentications,
            "successful_authentications": self.successful_authentications,
            "failed_authentications": self.failed_authentications,
            "tokens_issued": self.tokens_issued,
            "tokens_revoked": self.tokens_revoked,
            "sessions_created": self.sessions_created,
            "sessions_terminated": self.sessions_terminated,
            "lockouts": self.lockouts,
            "mfa_challenges": self.mfa_challenges,
            "oauth_flows": self.oauth_flows,
        }


class AuthenticationManager:
    """
    Authentication Manager for IoT security simulation.

    Provides:
    - Multiple authentication methods
    - OAuth 2.0 flow simulation
    - Token management
    - Session management
    - Rate limiting and lockout
    """

    def __init__(
        self,
        config: Optional[AuthConfig] = None,
        security_engine: Optional[Any] = None,
    ):
        """
        Initialize authentication manager.

        Args:
            config: Authentication configuration
            security_engine: Reference to SecurityPrivacyEngine
        """
        self.config = config or AuthConfig()
        self._security_engine = security_engine
        self.stats = AuthStats()

        # User/credential store (simulated)
        self._credentials: dict[str, dict[str, Any]] = {}
        self._api_keys: dict[str, str] = {}  # key -> subject_id

        # Token store
        self._tokens: dict[str, AuthToken] = {}
        self._revoked_tokens: set[str] = set()

        # Session store
        self._sessions: dict[str, AuthSession] = {}

        # OAuth 2.0 stores
        self._oauth_clients: dict[str, OAuth2Config] = {}
        self._auth_codes: dict[str, OAuth2AuthorizationCode] = {}
        self._device_codes: dict[str, DeviceAuthorizationRequest] = {}

        # Rate limiting
        self._failed_attempts: dict[str, int] = {}
        self._lockouts: dict[str, datetime] = {}

        logger.info("AuthenticationManager initialized")

    # Credential Management

    def register_credentials(
        self,
        subject_id: str,
        password: Optional[str] = None,
        api_key: Optional[str] = None,
        roles: Optional[list[str]] = None,
    ) -> bool:
        """
        Register credentials for a user/device.

        Args:
            subject_id: User or device ID
            password: Password (will be hashed)
            api_key: API key
            roles: List of roles

        Returns:
            True if registered successfully
        """
        self._credentials[subject_id] = {
            "password_hash": self._hash_password(password) if password else None,
            "roles": roles or ["user"],
            "created_at": datetime.now().isoformat(),
            "mfa_secret": secrets.token_hex(20) if self.config.mfa_enabled else None,
        }

        if api_key:
            self._api_keys[api_key] = subject_id

        logger.info(f"Credentials registered for: {subject_id}")
        return True

    def _hash_password(self, password: str) -> str:
        """Hash a password."""
        salt = secrets.token_hex(16)
        hash_value = hashlib.sha256(f"{salt}{password}".encode()).hexdigest()
        return f"{salt}${hash_value}"

    def _verify_password(self, password: str, stored_hash: str) -> bool:
        """Verify a password against stored hash."""
        try:
            salt, hash_value = stored_hash.split("$")
            computed = hashlib.sha256(f"{salt}{password}".encode()).hexdigest()
            return secrets.compare_digest(computed, hash_value)
        except Exception:
            return False

    # Authentication Methods

    async def authenticate(
        self,
        method: AuthMethod,
        credentials: dict[str, Any],
        ip_address: str = "",
        user_agent: str = "",
    ) -> tuple[Optional[AuthSession], Optional[str]]:
        """
        Authenticate a user/device.

        Args:
            method: Authentication method
            credentials: Method-specific credentials
            ip_address: Client IP address
            user_agent: Client user agent

        Returns:
            (session, error_message)
        """
        self.stats.total_authentications += 1

        # Simulate latency
        if self.config.simulation_mode:
            await asyncio.sleep(self.config.auth_latency_ms / 1000)

        subject_id = credentials.get("subject_id", credentials.get("username", ""))

        # Check lockout
        if self._is_locked_out(subject_id):
            await self._log_auth_event(subject_id, method, False, "Account locked")
            return None, "Account is locked due to too many failed attempts"

        try:
            if method == AuthMethod.PASSWORD:
                success, error = await self._authenticate_password(credentials)
            elif method == AuthMethod.API_KEY:
                success, error = await self._authenticate_api_key(credentials)
            elif method == AuthMethod.CERTIFICATE:
                success, error = await self._authenticate_certificate(credentials)
            elif method == AuthMethod.OAUTH2:
                # OAuth2 uses separate flow methods
                return None, "Use OAuth2 specific methods"
            else:
                return None, f"Unsupported authentication method: {method}"

            if success:
                self.stats.successful_authentications += 1
                self._failed_attempts[subject_id] = 0

                # Create session
                session = await self._create_session(
                    subject_id=subject_id,
                    auth_method=method,
                    ip_address=ip_address,
                    user_agent=user_agent,
                )

                await self._log_auth_event(subject_id, method, True)
                return session, None

            else:
                self.stats.failed_authentications += 1
                self._record_failed_attempt(subject_id)
                await self._log_auth_event(subject_id, method, False, error)
                return None, error

        except Exception as e:
            self.stats.failed_authentications += 1
            await self._log_auth_event(subject_id, method, False, str(e))
            return None, str(e)

    async def _authenticate_password(
        self,
        credentials: dict[str, Any],
    ) -> tuple[bool, Optional[str]]:
        """Authenticate with username/password."""
        username = credentials.get("username", "")
        password = credentials.get("password", "")

        if not username or not password:
            return False, "Username and password required"

        stored = self._credentials.get(username)
        if not stored:
            return False, "Invalid credentials"

        if not stored.get("password_hash"):
            return False, "Password authentication not configured"

        if not self._verify_password(password, stored["password_hash"]):
            return False, "Invalid credentials"

        return True, None

    async def _authenticate_api_key(
        self,
        credentials: dict[str, Any],
    ) -> tuple[bool, Optional[str]]:
        """Authenticate with API key."""
        api_key = credentials.get("api_key", "")

        if not api_key:
            return False, "API key required"

        if api_key not in self._api_keys:
            return False, "Invalid API key"

        # Update credentials subject_id for session creation
        credentials["subject_id"] = self._api_keys[api_key]
        return True, None

    async def _authenticate_certificate(
        self,
        credentials: dict[str, Any],
    ) -> tuple[bool, Optional[str]]:
        """Authenticate with client certificate."""
        cert_id = credentials.get("certificate_id", "")
        subject_id = credentials.get("subject_id", "")

        if not cert_id or not subject_id:
            return False, "Certificate ID and subject required"

        # In real implementation, would verify certificate
        # For simulation, check if subject exists
        if subject_id not in self._credentials:
            return False, "Unknown subject"

        return True, None

    # Session Management

    async def _create_session(
        self,
        subject_id: str,
        auth_method: AuthMethod,
        ip_address: str = "",
        user_agent: str = "",
    ) -> AuthSession:
        """Create a new authentication session."""
        # Check concurrent session limit
        active_sessions = [
            s for s in self._sessions.values()
            if s.subject_id == subject_id and s.is_active
        ]

        if len(active_sessions) >= self.config.max_concurrent_sessions:
            # Terminate oldest session
            oldest = min(active_sessions, key=lambda s: s.created_at)
            await self.terminate_session(oldest.id)

        # Create access token
        access_token = await self.issue_token(
            subject_id=subject_id,
            token_type=TokenType.ACCESS,
            scope=self._credentials.get(subject_id, {}).get("roles", ["user"]),
        )

        # Create refresh token
        refresh_token = await self.issue_token(
            subject_id=subject_id,
            token_type=TokenType.REFRESH,
            lifetime_seconds=self.config.refresh_token_lifetime_seconds,
        )

        # Create session
        session = AuthSession(
            subject_id=subject_id,
            auth_method=auth_method,
            status=AuthStatus.AUTHENTICATED,
            access_token_id=access_token.id,
            refresh_token_id=refresh_token.id,
            ip_address=ip_address,
            user_agent=user_agent,
            expires_at=datetime.now() + timedelta(minutes=self.config.session_timeout_minutes),
        )

        self._sessions[session.id] = session
        self.stats.sessions_created += 1

        logger.info(f"Session created for: {subject_id}")
        return session

    async def terminate_session(self, session_id: str) -> bool:
        """Terminate an authentication session."""
        session = self._sessions.get(session_id)
        if not session:
            return False

        session.status = AuthStatus.REVOKED

        # Revoke associated tokens
        if session.access_token_id:
            await self.revoke_token(session.access_token_id)
        if session.refresh_token_id:
            await self.revoke_token(session.refresh_token_id)

        del self._sessions[session_id]
        self.stats.sessions_terminated += 1

        logger.info(f"Session terminated: {session_id}")
        return True

    def get_session(self, session_id: str) -> Optional[AuthSession]:
        """Get a session by ID."""
        return self._sessions.get(session_id)

    def validate_session(self, session_id: str) -> tuple[bool, Optional[str]]:
        """Validate a session."""
        session = self._sessions.get(session_id)
        if not session:
            return False, "Session not found"
        if not session.is_active:
            return False, "Session is not active"
        return True, None

    # Token Management

    async def issue_token(
        self,
        subject_id: str,
        token_type: TokenType = TokenType.ACCESS,
        scope: Optional[list[str]] = None,
        lifetime_seconds: Optional[int] = None,
        claims: Optional[dict[str, Any]] = None,
    ) -> AuthToken:
        """
        Issue a new token.

        Args:
            subject_id: Token subject
            token_type: Type of token
            scope: Token scope
            lifetime_seconds: Token lifetime
            claims: Additional claims

        Returns:
            Issued token
        """
        lifetime = lifetime_seconds or self.config.access_token_lifetime_seconds

        token = AuthToken(
            token_type=token_type,
            subject=subject_id,
            scope=scope or [],
            expires_at=datetime.now() + timedelta(seconds=lifetime),
            claims=claims or {},
        )

        self._tokens[token.id] = token
        self.stats.tokens_issued += 1

        logger.debug(f"Token issued: {token.id} for {subject_id}")
        return token

    async def revoke_token(self, token_id: str) -> bool:
        """Revoke a token."""
        token = self._tokens.get(token_id)
        if not token:
            return False

        token.revoked = True
        self._revoked_tokens.add(token_id)
        self.stats.tokens_revoked += 1

        if self._security_engine:
            from .engine import SecurityEvent, SecurityEventType, SecurityLevel
            await self._security_engine.log_event(SecurityEvent(
                event_type=SecurityEventType.TOKEN_REVOKED,
                source_id="auth_manager",
                source_type="service",
                target_id=token_id,
                target_type="token",
                severity=SecurityLevel.LOW,
                details={"subject": token.subject},
            ))

        logger.debug(f"Token revoked: {token_id}")
        return True

    def validate_token(self, token_value: str) -> tuple[bool, Optional[AuthToken], Optional[str]]:
        """
        Validate a token.

        Args:
            token_value: Token value to validate

        Returns:
            (valid, token, error_message)
        """
        # Find token by value
        token = None
        for t in self._tokens.values():
            if t.token_value == token_value:
                token = t
                break

        if not token:
            return False, None, "Token not found"

        if token.id in self._revoked_tokens:
            return False, None, "Token has been revoked"

        if token.is_expired:
            return False, None, "Token has expired"

        if not token.is_valid:
            return False, None, "Token is not valid"

        return True, token, None

    async def refresh_token(self, refresh_token_value: str) -> tuple[Optional[AuthToken], Optional[str]]:
        """
        Refresh an access token using a refresh token.

        Args:
            refresh_token_value: Refresh token value

        Returns:
            (new_access_token, error_message)
        """
        valid, refresh_token, error = self.validate_token(refresh_token_value)
        if not valid:
            return None, error

        if refresh_token.token_type != TokenType.REFRESH:
            return None, "Invalid token type"

        # Issue new access token
        new_token = await self.issue_token(
            subject_id=refresh_token.subject,
            token_type=TokenType.ACCESS,
            scope=refresh_token.scope,
        )

        return new_token, None

    # OAuth 2.0 Flows

    def register_oauth_client(self, config: OAuth2Config) -> str:
        """Register an OAuth 2.0 client."""
        if not config.client_id:
            config.client_id = secrets.token_urlsafe(16)

        self._oauth_clients[config.client_id] = config
        logger.info(f"OAuth client registered: {config.client_id}")
        return config.client_id

    async def oauth_authorize(
        self,
        client_id: str,
        redirect_uri: str,
        scope: list[str],
        user_id: str,
        code_challenge: Optional[str] = None,
        code_challenge_method: str = "S256",
    ) -> tuple[Optional[str], Optional[str]]:
        """
        OAuth 2.0 Authorization Code grant - authorization step.

        Args:
            client_id: Client ID
            redirect_uri: Redirect URI
            scope: Requested scope
            user_id: Authenticating user ID
            code_challenge: PKCE code challenge
            code_challenge_method: PKCE method

        Returns:
            (authorization_code, error)
        """
        self.stats.oauth_flows += 1

        client = self._oauth_clients.get(client_id)
        if not client:
            return None, "Unknown client"

        if OAuth2Flow.AUTHORIZATION_CODE not in client.allowed_grant_types:
            return None, "Grant type not allowed"

        if redirect_uri not in client.redirect_uris:
            return None, "Invalid redirect URI"

        # Validate scope
        invalid_scopes = [s for s in scope if s not in client.allowed_scopes]
        if invalid_scopes:
            return None, f"Invalid scopes: {invalid_scopes}"

        # Check PKCE requirement
        if client.require_pkce and not code_challenge:
            return None, "PKCE required"

        # Generate authorization code
        auth_code = OAuth2AuthorizationCode(
            client_id=client_id,
            redirect_uri=redirect_uri,
            scope=scope,
            user_id=user_id,
            code_challenge=code_challenge,
            code_challenge_method=code_challenge_method,
        )

        self._auth_codes[auth_code.code] = auth_code

        logger.info(f"Authorization code issued for client: {client_id}")
        return auth_code.code, None

    async def oauth_token(
        self,
        grant_type: OAuth2Flow,
        client_id: str,
        client_secret: Optional[str] = None,
        code: Optional[str] = None,
        code_verifier: Optional[str] = None,
        refresh_token: Optional[str] = None,
        scope: Optional[list[str]] = None,
    ) -> tuple[Optional[dict[str, Any]], Optional[str]]:
        """
        OAuth 2.0 Token endpoint.

        Args:
            grant_type: OAuth 2.0 grant type
            client_id: Client ID
            client_secret: Client secret
            code: Authorization code
            code_verifier: PKCE code verifier
            refresh_token: Refresh token
            scope: Requested scope

        Returns:
            (token_response, error)
        """
        client = self._oauth_clients.get(client_id)
        if not client:
            return None, "Unknown client"

        if grant_type not in client.allowed_grant_types:
            return None, "Grant type not allowed"

        # Verify client secret (except for PKCE flows)
        if client_secret and not secrets.compare_digest(client_secret, client.client_secret):
            return None, "Invalid client credentials"

        if grant_type == OAuth2Flow.AUTHORIZATION_CODE:
            return await self._oauth_authorization_code_exchange(
                client, code, code_verifier
            )

        elif grant_type == OAuth2Flow.CLIENT_CREDENTIALS:
            return await self._oauth_client_credentials(client, scope)

        elif grant_type == OAuth2Flow.REFRESH_TOKEN:
            return await self._oauth_refresh_token(refresh_token)

        elif grant_type == OAuth2Flow.DEVICE_CODE:
            return None, "Use device code polling endpoint"

        return None, "Unsupported grant type"

    async def _oauth_authorization_code_exchange(
        self,
        client: OAuth2Config,
        code: Optional[str],
        code_verifier: Optional[str],
    ) -> tuple[Optional[dict[str, Any]], Optional[str]]:
        """Exchange authorization code for tokens."""
        if not code:
            return None, "Authorization code required"

        auth_code = self._auth_codes.get(code)
        if not auth_code:
            return None, "Invalid authorization code"

        if auth_code.used:
            return None, "Authorization code already used"

        if datetime.now() > auth_code.expires_at:
            return None, "Authorization code expired"

        if auth_code.client_id != client.client_id:
            return None, "Client mismatch"

        # Verify PKCE
        if auth_code.code_challenge:
            if not code_verifier:
                return None, "Code verifier required"

            if auth_code.code_challenge_method == "S256":
                expected = hashlib.sha256(code_verifier.encode()).hexdigest()
            else:
                expected = code_verifier

            if not secrets.compare_digest(expected, auth_code.code_challenge):
                return None, "Invalid code verifier"

        # Mark code as used
        auth_code.used = True

        # Issue tokens
        access_token = await self.issue_token(
            subject_id=auth_code.user_id,
            token_type=TokenType.ACCESS,
            scope=auth_code.scope,
            lifetime_seconds=client.access_token_lifetime,
        )

        refresh_token = await self.issue_token(
            subject_id=auth_code.user_id,
            token_type=TokenType.REFRESH,
            scope=auth_code.scope,
            lifetime_seconds=client.refresh_token_lifetime,
        )

        return {
            "access_token": access_token.token_value,
            "token_type": "Bearer",
            "expires_in": access_token.seconds_until_expiry,
            "refresh_token": refresh_token.token_value,
            "scope": " ".join(auth_code.scope),
        }, None

    async def _oauth_client_credentials(
        self,
        client: OAuth2Config,
        scope: Optional[list[str]],
    ) -> tuple[Optional[dict[str, Any]], Optional[str]]:
        """Client credentials grant."""
        requested_scope = scope or client.allowed_scopes

        # Validate scope
        invalid = [s for s in requested_scope if s not in client.allowed_scopes]
        if invalid:
            return None, f"Invalid scopes: {invalid}"

        access_token = await self.issue_token(
            subject_id=client.client_id,
            token_type=TokenType.ACCESS,
            scope=requested_scope,
            lifetime_seconds=client.access_token_lifetime,
        )

        return {
            "access_token": access_token.token_value,
            "token_type": "Bearer",
            "expires_in": access_token.seconds_until_expiry,
            "scope": " ".join(requested_scope),
        }, None

    async def _oauth_refresh_token(
        self,
        refresh_token_value: Optional[str],
    ) -> tuple[Optional[dict[str, Any]], Optional[str]]:
        """Refresh token grant."""
        if not refresh_token_value:
            return None, "Refresh token required"

        new_token, error = await self.refresh_token(refresh_token_value)
        if error:
            return None, error

        return {
            "access_token": new_token.token_value,
            "token_type": "Bearer",
            "expires_in": new_token.seconds_until_expiry,
            "scope": " ".join(new_token.scope),
        }, None

    # Device Authorization Flow

    async def oauth_device_authorization(
        self,
        client_id: str,
        scope: Optional[list[str]] = None,
    ) -> tuple[Optional[dict[str, Any]], Optional[str]]:
        """
        OAuth 2.0 Device Authorization grant - initiation.

        Returns device code and user code for out-of-band authorization.
        """
        client = self._oauth_clients.get(client_id)
        if not client:
            return None, "Unknown client"

        if OAuth2Flow.DEVICE_CODE not in client.allowed_grant_types:
            return None, "Device flow not allowed"

        requested_scope = scope or ["read"]

        device_req = DeviceAuthorizationRequest(
            client_id=client_id,
            scope=requested_scope,
        )

        self._device_codes[device_req.device_code] = device_req

        return {
            "device_code": device_req.device_code,
            "user_code": device_req.user_code,
            "verification_uri": device_req.verification_uri,
            "verification_uri_complete": f"{device_req.verification_uri}?user_code={device_req.user_code}",
            "expires_in": int((device_req.expires_at - datetime.now()).total_seconds()),
            "interval": device_req.interval,
        }, None

    async def oauth_device_authorize(
        self,
        user_code: str,
        user_id: str,
    ) -> tuple[bool, Optional[str]]:
        """Authorize a device using user code (user action)."""
        device_req = None
        for req in self._device_codes.values():
            if req.user_code == user_code:
                device_req = req
                break

        if not device_req:
            return False, "Invalid user code"

        if datetime.now() > device_req.expires_at:
            return False, "User code expired"

        device_req.authorized = True
        device_req.user_id = user_id

        return True, None

    async def oauth_device_token(
        self,
        device_code: str,
        client_id: str,
    ) -> tuple[Optional[dict[str, Any]], Optional[str]]:
        """Poll for device authorization status and get tokens."""
        device_req = self._device_codes.get(device_code)
        if not device_req:
            return None, "Invalid device code"

        if device_req.client_id != client_id:
            return None, "Client mismatch"

        if datetime.now() > device_req.expires_at:
            return None, "Device code expired"

        if not device_req.authorized:
            return None, "authorization_pending"

        # Issue tokens
        access_token = await self.issue_token(
            subject_id=device_req.user_id,
            token_type=TokenType.ACCESS,
            scope=device_req.scope,
        )

        refresh_token = await self.issue_token(
            subject_id=device_req.user_id,
            token_type=TokenType.REFRESH,
            scope=device_req.scope,
        )

        # Clean up
        del self._device_codes[device_code]

        return {
            "access_token": access_token.token_value,
            "token_type": "Bearer",
            "expires_in": access_token.seconds_until_expiry,
            "refresh_token": refresh_token.token_value,
            "scope": " ".join(device_req.scope),
        }, None

    # Rate Limiting / Lockout

    def _is_locked_out(self, subject_id: str) -> bool:
        """Check if subject is locked out."""
        if subject_id not in self._lockouts:
            return False

        lockout_until = self._lockouts[subject_id]
        if datetime.now() > lockout_until:
            del self._lockouts[subject_id]
            del self._failed_attempts[subject_id]
            return False

        return True

    def _record_failed_attempt(self, subject_id: str) -> None:
        """Record a failed authentication attempt."""
        self._failed_attempts[subject_id] = self._failed_attempts.get(subject_id, 0) + 1

        if self._failed_attempts[subject_id] >= self.config.max_failed_attempts:
            self._lockouts[subject_id] = datetime.now() + timedelta(
                minutes=self.config.lockout_duration_minutes
            )
            self.stats.lockouts += 1
            logger.warning(f"Account locked: {subject_id}")

    # Event Logging

    async def _log_auth_event(
        self,
        subject_id: str,
        method: AuthMethod,
        success: bool,
        error: Optional[str] = None,
    ) -> None:
        """Log an authentication event."""
        if not self._security_engine:
            return

        from .engine import SecurityEvent, SecurityEventType, SecurityLevel

        event_type = SecurityEventType.AUTH_SUCCESS if success else SecurityEventType.AUTH_FAILURE

        await self._security_engine.log_event(SecurityEvent(
            event_type=event_type,
            source_id=subject_id,
            source_type="user",
            severity=SecurityLevel.LOW if success else SecurityLevel.MEDIUM,
            success=success,
            details={
                "method": method.value,
                "error": error,
            },
        ))

    # Statistics

    def get_stats(self) -> dict[str, Any]:
        """Get authentication statistics."""
        return {
            "stats": self.stats.to_dict(),
            "active_sessions": len([s for s in self._sessions.values() if s.is_active]),
            "active_tokens": len([t for t in self._tokens.values() if t.is_valid]),
            "registered_users": len(self._credentials),
            "oauth_clients": len(self._oauth_clients),
            "locked_accounts": len(self._lockouts),
        }
