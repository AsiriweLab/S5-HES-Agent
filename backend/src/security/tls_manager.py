"""
TLS Manager - Simulated TLS/SSL certificate and connection management.

Sprint 12 - S12.2: Implement TLSManager (simulation)

Features:
- Certificate generation and validation
- TLS handshake simulation
- Cipher suite negotiation
- Certificate chain verification
- Session management
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


class TLSVersion(str, Enum):
    """Supported TLS versions."""
    TLS_1_0 = "TLS 1.0"  # Deprecated
    TLS_1_1 = "TLS 1.1"  # Deprecated
    TLS_1_2 = "TLS 1.2"
    TLS_1_3 = "TLS 1.3"


class CipherSuite(str, Enum):
    """Common cipher suites."""
    # TLS 1.3 suites
    TLS_AES_256_GCM_SHA384 = "TLS_AES_256_GCM_SHA384"
    TLS_AES_128_GCM_SHA256 = "TLS_AES_128_GCM_SHA256"
    TLS_CHACHA20_POLY1305_SHA256 = "TLS_CHACHA20_POLY1305_SHA256"

    # TLS 1.2 suites
    TLS_ECDHE_RSA_WITH_AES_256_GCM_SHA384 = "TLS_ECDHE_RSA_WITH_AES_256_GCM_SHA384"
    TLS_ECDHE_RSA_WITH_AES_128_GCM_SHA256 = "TLS_ECDHE_RSA_WITH_AES_128_GCM_SHA256"
    TLS_ECDHE_ECDSA_WITH_AES_256_GCM_SHA384 = "TLS_ECDHE_ECDSA_WITH_AES_256_GCM_SHA384"

    # Legacy (not recommended)
    TLS_RSA_WITH_AES_256_CBC_SHA256 = "TLS_RSA_WITH_AES_256_CBC_SHA256"
    TLS_RSA_WITH_AES_128_CBC_SHA = "TLS_RSA_WITH_AES_128_CBC_SHA"


class CertificateType(str, Enum):
    """Certificate types."""
    ROOT_CA = "root_ca"
    INTERMEDIATE_CA = "intermediate_ca"
    SERVER = "server"
    CLIENT = "client"
    DEVICE = "device"


class HandshakeState(str, Enum):
    """TLS handshake states."""
    IDLE = "idle"
    CLIENT_HELLO = "client_hello"
    SERVER_HELLO = "server_hello"
    CERTIFICATE = "certificate"
    KEY_EXCHANGE = "key_exchange"
    FINISHED = "finished"
    ESTABLISHED = "established"
    FAILED = "failed"


@dataclass
class Certificate:
    """Simulated X.509 certificate."""
    id: str = field(default_factory=lambda: str(uuid4()))
    serial_number: str = field(default_factory=lambda: secrets.token_hex(16))
    subject: str = ""
    issuer: str = ""
    cert_type: CertificateType = CertificateType.SERVER
    public_key: str = field(default_factory=lambda: secrets.token_hex(64))  # Simulated
    signature: str = field(default_factory=lambda: secrets.token_hex(64))  # Simulated
    not_before: datetime = field(default_factory=datetime.now)
    not_after: datetime = field(default_factory=lambda: datetime.now() + timedelta(days=365))
    key_usage: list[str] = field(default_factory=lambda: ["digital_signature", "key_encipherment"])
    extended_key_usage: list[str] = field(default_factory=lambda: ["server_auth"])
    san: list[str] = field(default_factory=list)  # Subject Alternative Names
    is_ca: bool = False
    path_length: Optional[int] = None
    parent_cert_id: Optional[str] = None

    @property
    def is_valid(self) -> bool:
        """Check if certificate is currently valid."""
        now = datetime.now()
        return self.not_before <= now <= self.not_after

    @property
    def is_expired(self) -> bool:
        """Check if certificate is expired."""
        return datetime.now() > self.not_after

    @property
    def days_until_expiry(self) -> int:
        """Days until certificate expires."""
        delta = self.not_after - datetime.now()
        return max(0, delta.days)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "serial_number": self.serial_number,
            "subject": self.subject,
            "issuer": self.issuer,
            "cert_type": self.cert_type.value,
            "not_before": self.not_before.isoformat(),
            "not_after": self.not_after.isoformat(),
            "is_valid": self.is_valid,
            "is_expired": self.is_expired,
            "days_until_expiry": self.days_until_expiry,
            "key_usage": self.key_usage,
            "extended_key_usage": self.extended_key_usage,
            "san": self.san,
            "is_ca": self.is_ca,
        }


@dataclass
class TLSSession:
    """TLS session information."""
    id: str = field(default_factory=lambda: str(uuid4()))
    client_id: str = ""
    server_id: str = ""
    version: TLSVersion = TLSVersion.TLS_1_3
    cipher_suite: CipherSuite = CipherSuite.TLS_AES_256_GCM_SHA384
    state: HandshakeState = HandshakeState.IDLE
    session_key: str = field(default_factory=lambda: secrets.token_hex(32))
    client_random: str = field(default_factory=lambda: secrets.token_hex(32))
    server_random: str = field(default_factory=lambda: secrets.token_hex(32))
    master_secret: str = field(default_factory=lambda: secrets.token_hex(48))
    created_at: datetime = field(default_factory=datetime.now)
    expires_at: datetime = field(default_factory=lambda: datetime.now() + timedelta(hours=8))
    client_cert_id: Optional[str] = None
    server_cert_id: Optional[str] = None
    resumed: bool = False
    bytes_sent: int = 0
    bytes_received: int = 0

    @property
    def is_expired(self) -> bool:
        return datetime.now() > self.expires_at

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "client_id": self.client_id,
            "server_id": self.server_id,
            "version": self.version.value,
            "cipher_suite": self.cipher_suite.value,
            "state": self.state.value,
            "created_at": self.created_at.isoformat(),
            "expires_at": self.expires_at.isoformat(),
            "is_expired": self.is_expired,
            "resumed": self.resumed,
            "bytes_sent": self.bytes_sent,
            "bytes_received": self.bytes_received,
        }


@dataclass
class TLSConfig:
    """TLS configuration."""
    min_version: TLSVersion = TLSVersion.TLS_1_2
    max_version: TLSVersion = TLSVersion.TLS_1_3
    preferred_cipher_suites: list[CipherSuite] = field(default_factory=lambda: [
        CipherSuite.TLS_AES_256_GCM_SHA384,
        CipherSuite.TLS_CHACHA20_POLY1305_SHA256,
        CipherSuite.TLS_ECDHE_RSA_WITH_AES_256_GCM_SHA384,
    ])
    require_client_cert: bool = False
    verify_server_cert: bool = True
    session_timeout_hours: int = 8
    session_cache_size: int = 1000
    # Simulation settings
    simulation_mode: bool = True
    handshake_latency_ms: int = 50


@dataclass
class TLSStats:
    """TLS statistics."""
    handshakes_initiated: int = 0
    handshakes_completed: int = 0
    handshakes_failed: int = 0
    sessions_created: int = 0
    sessions_resumed: int = 0
    sessions_expired: int = 0
    certificates_issued: int = 0
    certificates_revoked: int = 0
    bytes_encrypted: int = 0
    bytes_decrypted: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "handshakes_initiated": self.handshakes_initiated,
            "handshakes_completed": self.handshakes_completed,
            "handshakes_failed": self.handshakes_failed,
            "sessions_created": self.sessions_created,
            "sessions_resumed": self.sessions_resumed,
            "sessions_expired": self.sessions_expired,
            "certificates_issued": self.certificates_issued,
            "certificates_revoked": self.certificates_revoked,
            "bytes_encrypted": self.bytes_encrypted,
            "bytes_decrypted": self.bytes_decrypted,
        }


class TLSManager:
    """
    Simulated TLS/SSL Manager for IoT security simulation.

    Provides:
    - Certificate authority simulation
    - Certificate generation and validation
    - TLS handshake simulation
    - Session management
    - Cipher suite negotiation
    """

    def __init__(
        self,
        config: Optional[TLSConfig] = None,
        security_engine: Optional[Any] = None,
    ):
        """
        Initialize TLS manager.

        Args:
            config: TLS configuration
            security_engine: Reference to SecurityPrivacyEngine
        """
        self.config = config or TLSConfig()
        self._security_engine = security_engine
        self.stats = TLSStats()

        # Certificate store
        self._certificates: dict[str, Certificate] = {}
        self._revoked_certs: set[str] = set()

        # Session cache
        self._sessions: dict[str, TLSSession] = {}

        # Root CA
        self._root_ca: Optional[Certificate] = None
        self._initialize_root_ca()

        logger.info("TLSManager initialized")

    def _initialize_root_ca(self) -> None:
        """Initialize the root CA certificate."""
        self._root_ca = Certificate(
            subject="CN=Smart-HES Root CA,O=Smart-HES Simulation,C=US",
            issuer="CN=Smart-HES Root CA,O=Smart-HES Simulation,C=US",
            cert_type=CertificateType.ROOT_CA,
            is_ca=True,
            path_length=2,
            key_usage=["key_cert_sign", "crl_sign"],
            extended_key_usage=[],
            not_after=datetime.now() + timedelta(days=3650),  # 10 years
        )
        self._certificates[self._root_ca.id] = self._root_ca
        logger.info(f"Root CA initialized: {self._root_ca.subject}")

    async def generate_certificate(
        self,
        subject: str,
        cert_type: CertificateType = CertificateType.DEVICE,
        san: Optional[list[str]] = None,
        validity_days: int = 365,
        issuer_cert_id: Optional[str] = None,
    ) -> Certificate:
        """
        Generate a new certificate.

        Args:
            subject: Certificate subject (CN=...)
            cert_type: Type of certificate
            san: Subject Alternative Names
            validity_days: Validity period in days
            issuer_cert_id: ID of issuing CA certificate

        Returns:
            Generated certificate
        """
        # Determine issuer
        issuer_cert = None
        if issuer_cert_id:
            issuer_cert = self._certificates.get(issuer_cert_id)
        if not issuer_cert:
            issuer_cert = self._root_ca

        # Create certificate
        cert = Certificate(
            subject=subject,
            issuer=issuer_cert.subject,
            cert_type=cert_type,
            san=san or [],
            not_before=datetime.now(),
            not_after=datetime.now() + timedelta(days=validity_days),
            parent_cert_id=issuer_cert.id,
            is_ca=cert_type in (CertificateType.ROOT_CA, CertificateType.INTERMEDIATE_CA),
        )

        # Set key usage based on type
        if cert_type == CertificateType.SERVER:
            cert.extended_key_usage = ["server_auth"]
        elif cert_type == CertificateType.CLIENT:
            cert.extended_key_usage = ["client_auth"]
        elif cert_type == CertificateType.DEVICE:
            cert.extended_key_usage = ["server_auth", "client_auth"]

        # Store certificate
        self._certificates[cert.id] = cert
        self.stats.certificates_issued += 1

        # Log event
        if self._security_engine:
            from .engine import SecurityEvent, SecurityEventType, SecurityLevel
            await self._security_engine.log_event(SecurityEvent(
                event_type=SecurityEventType.KEY_GENERATED,
                source_id="tls_manager",
                source_type="service",
                target_id=cert.id,
                target_type="certificate",
                severity=SecurityLevel.LOW,
                details={
                    "subject": subject,
                    "cert_type": cert_type.value,
                    "validity_days": validity_days,
                },
            ))

        logger.info(f"Certificate generated: {subject}")
        return cert

    async def revoke_certificate(self, cert_id: str, reason: str = "unspecified") -> bool:
        """
        Revoke a certificate.

        Args:
            cert_id: Certificate ID to revoke
            reason: Revocation reason

        Returns:
            True if revoked successfully
        """
        if cert_id not in self._certificates:
            return False

        self._revoked_certs.add(cert_id)
        self.stats.certificates_revoked += 1

        if self._security_engine:
            from .engine import SecurityEvent, SecurityEventType, SecurityLevel
            await self._security_engine.log_event(SecurityEvent(
                event_type=SecurityEventType.TOKEN_REVOKED,
                source_id="tls_manager",
                source_type="service",
                target_id=cert_id,
                target_type="certificate",
                severity=SecurityLevel.MEDIUM,
                details={"reason": reason},
            ))

        logger.info(f"Certificate revoked: {cert_id}")
        return True

    def verify_certificate(self, cert_id: str) -> tuple[bool, Optional[str]]:
        """
        Verify a certificate.

        Args:
            cert_id: Certificate ID to verify

        Returns:
            (valid, error_message)
        """
        cert = self._certificates.get(cert_id)
        if not cert:
            return False, "Certificate not found"

        # Check revocation
        if cert_id in self._revoked_certs:
            return False, "Certificate has been revoked"

        # Check expiration
        if cert.is_expired:
            return False, "Certificate has expired"

        # Check validity period
        if not cert.is_valid:
            return False, "Certificate not yet valid"

        # Verify chain
        if cert.parent_cert_id:
            parent_valid, parent_error = self.verify_certificate(cert.parent_cert_id)
            if not parent_valid:
                return False, f"Certificate chain invalid: {parent_error}"

        return True, None

    async def initiate_handshake(
        self,
        client_id: str,
        server_id: str,
        client_cert_id: Optional[str] = None,
        server_cert_id: Optional[str] = None,
        preferred_version: Optional[TLSVersion] = None,
        preferred_suites: Optional[list[CipherSuite]] = None,
    ) -> Optional[TLSSession]:
        """
        Initiate a TLS handshake.

        Args:
            client_id: Client identifier
            server_id: Server identifier
            client_cert_id: Client certificate ID (for mutual TLS)
            server_cert_id: Server certificate ID
            preferred_version: Preferred TLS version
            preferred_suites: Preferred cipher suites

        Returns:
            TLS session if successful, None otherwise
        """
        self.stats.handshakes_initiated += 1

        # Check for existing session to resume
        existing_session = self._find_resumable_session(client_id, server_id)
        if existing_session:
            existing_session.resumed = True
            existing_session.state = HandshakeState.ESTABLISHED
            self.stats.sessions_resumed += 1
            logger.debug(f"Session resumed: {existing_session.id}")
            return existing_session

        # Create new session
        session = TLSSession(
            client_id=client_id,
            server_id=server_id,
            client_cert_id=client_cert_id,
            server_cert_id=server_cert_id,
        )

        # Log handshake start
        if self._security_engine:
            from .engine import SecurityEvent, SecurityEventType, SecurityLevel
            await self._security_engine.log_event(SecurityEvent(
                event_type=SecurityEventType.TLS_HANDSHAKE_START,
                source_id=client_id,
                source_type="device",
                target_id=server_id,
                target_type="server",
                severity=SecurityLevel.LOW,
                details={"session_id": session.id},
            ))

        try:
            # Simulate handshake steps
            session = await self._perform_handshake(
                session,
                preferred_version,
                preferred_suites,
            )

            if session.state == HandshakeState.ESTABLISHED:
                self._sessions[session.id] = session
                self.stats.handshakes_completed += 1
                self.stats.sessions_created += 1

                if self._security_engine:
                    await self._security_engine.log_event(SecurityEvent(
                        event_type=SecurityEventType.TLS_HANDSHAKE_SUCCESS,
                        source_id=client_id,
                        source_type="device",
                        target_id=server_id,
                        target_type="server",
                        severity=SecurityLevel.LOW,
                        details={
                            "session_id": session.id,
                            "version": session.version.value,
                            "cipher_suite": session.cipher_suite.value,
                        },
                    ))

                logger.info(f"TLS handshake completed: {session.id}")
                return session

            else:
                self.stats.handshakes_failed += 1
                return None

        except Exception as e:
            self.stats.handshakes_failed += 1

            if self._security_engine:
                from .engine import SecurityEvent, SecurityEventType, SecurityLevel
                await self._security_engine.log_event(SecurityEvent(
                    event_type=SecurityEventType.TLS_HANDSHAKE_FAILURE,
                    source_id=client_id,
                    source_type="device",
                    target_id=server_id,
                    target_type="server",
                    severity=SecurityLevel.MEDIUM,
                    success=False,
                    details={"error": str(e)},
                ))

            logger.error(f"TLS handshake failed: {e}")
            return None

    async def _perform_handshake(
        self,
        session: TLSSession,
        preferred_version: Optional[TLSVersion],
        preferred_suites: Optional[list[CipherSuite]],
    ) -> TLSSession:
        """Simulate TLS handshake process."""
        # Simulate latency
        if self.config.simulation_mode:
            await asyncio.sleep(self.config.handshake_latency_ms / 1000)

        # Step 1: Client Hello
        session.state = HandshakeState.CLIENT_HELLO
        session.client_random = secrets.token_hex(32)

        # Step 2: Server Hello - negotiate version and cipher
        session.state = HandshakeState.SERVER_HELLO
        session.server_random = secrets.token_hex(32)

        # Negotiate version
        version = preferred_version or self.config.max_version
        version_order = [TLSVersion.TLS_1_0, TLSVersion.TLS_1_1,
                         TLSVersion.TLS_1_2, TLSVersion.TLS_1_3]

        if version_order.index(version) < version_order.index(self.config.min_version):
            session.state = HandshakeState.FAILED
            raise ValueError(f"TLS version {version.value} below minimum {self.config.min_version.value}")

        session.version = version

        # Negotiate cipher suite
        client_suites = preferred_suites or self.config.preferred_cipher_suites
        for suite in self.config.preferred_cipher_suites:
            if suite in client_suites:
                session.cipher_suite = suite
                break
        else:
            session.state = HandshakeState.FAILED
            raise ValueError("No common cipher suite found")

        # Step 3: Certificate exchange
        session.state = HandshakeState.CERTIFICATE

        # Verify server certificate
        if session.server_cert_id and self.config.verify_server_cert:
            valid, error = self.verify_certificate(session.server_cert_id)
            if not valid:
                session.state = HandshakeState.FAILED
                raise ValueError(f"Server certificate invalid: {error}")

        # Verify client certificate (if mutual TLS)
        if self.config.require_client_cert:
            if not session.client_cert_id:
                session.state = HandshakeState.FAILED
                raise ValueError("Client certificate required but not provided")

            valid, error = self.verify_certificate(session.client_cert_id)
            if not valid:
                session.state = HandshakeState.FAILED
                raise ValueError(f"Client certificate invalid: {error}")

        # Step 4: Key exchange
        session.state = HandshakeState.KEY_EXCHANGE

        # Generate master secret (simulated)
        combined = session.client_random + session.server_random
        session.master_secret = hashlib.sha384(combined.encode()).hexdigest()
        session.session_key = hashlib.sha256(session.master_secret.encode()).hexdigest()

        # Step 5: Finished
        session.state = HandshakeState.FINISHED
        await asyncio.sleep(0.01)  # Small delay

        # Handshake complete
        session.state = HandshakeState.ESTABLISHED
        return session

    def _find_resumable_session(self, client_id: str, server_id: str) -> Optional[TLSSession]:
        """Find a session that can be resumed."""
        for session in self._sessions.values():
            if (session.client_id == client_id and
                session.server_id == server_id and
                session.state == HandshakeState.ESTABLISHED and
                not session.is_expired):
                return session
        return None

    async def terminate_session(self, session_id: str) -> bool:
        """
        Terminate a TLS session.

        Args:
            session_id: Session ID to terminate

        Returns:
            True if terminated successfully
        """
        if session_id not in self._sessions:
            return False

        session = self._sessions[session_id]

        if self._security_engine:
            from .engine import SecurityEvent, SecurityEventType, SecurityLevel
            await self._security_engine.log_event(SecurityEvent(
                event_type=SecurityEventType.CONNECTION_TERMINATED,
                source_id=session.client_id,
                source_type="device",
                target_id=session.server_id,
                target_type="server",
                severity=SecurityLevel.LOW,
                details={"session_id": session_id},
            ))

        del self._sessions[session_id]
        logger.debug(f"TLS session terminated: {session_id}")
        return True

    def get_certificate(self, cert_id: str) -> Optional[Certificate]:
        """Get a certificate by ID."""
        return self._certificates.get(cert_id)

    def get_session(self, session_id: str) -> Optional[TLSSession]:
        """Get a session by ID."""
        return self._sessions.get(session_id)

    def list_certificates(self, cert_type: Optional[CertificateType] = None) -> list[Certificate]:
        """List certificates, optionally filtered by type."""
        certs = list(self._certificates.values())
        if cert_type:
            certs = [c for c in certs if c.cert_type == cert_type]
        return certs

    def list_sessions(self, active_only: bool = True) -> list[TLSSession]:
        """List sessions, optionally filtering for active only."""
        sessions = list(self._sessions.values())
        if active_only:
            sessions = [s for s in sessions if not s.is_expired and
                        s.state == HandshakeState.ESTABLISHED]
        return sessions

    def cleanup_expired(self) -> int:
        """Clean up expired sessions and certificates."""
        cleaned = 0

        # Clean expired sessions
        expired_sessions = [
            sid for sid, session in self._sessions.items()
            if session.is_expired
        ]
        for sid in expired_sessions:
            del self._sessions[sid]
            self.stats.sessions_expired += 1
            cleaned += 1

        return cleaned

    def get_stats(self) -> dict[str, Any]:
        """Get TLS statistics."""
        return {
            "stats": self.stats.to_dict(),
            "certificates": len(self._certificates),
            "revoked_certificates": len(self._revoked_certs),
            "active_sessions": len([s for s in self._sessions.values()
                                    if not s.is_expired]),
            "config": {
                "min_version": self.config.min_version.value,
                "max_version": self.config.max_version.value,
                "require_client_cert": self.config.require_client_cert,
            },
        }
