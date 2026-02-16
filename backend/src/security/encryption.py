"""
Encryption Engine - Cryptographic operations simulation for IoT devices.

Sprint 12 - S12.5: Implement EncryptionEngine

Features:
- Symmetric encryption (AES-128, AES-256, ChaCha20)
- Asymmetric encryption (RSA, ECDSA)
- Key management and rotation
- Secure key exchange (Diffie-Hellman, ECDH)
- Hash functions and HMAC
- Digital signatures
"""

import asyncio
import hashlib
import hmac
import secrets
import base64
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Optional
from loguru import logger


class SymmetricAlgorithm(str, Enum):
    """Supported symmetric encryption algorithms."""
    AES_128_GCM = "aes-128-gcm"
    AES_256_GCM = "aes-256-gcm"
    AES_128_CBC = "aes-128-cbc"
    AES_256_CBC = "aes-256-cbc"
    CHACHA20_POLY1305 = "chacha20-poly1305"


class AsymmetricAlgorithm(str, Enum):
    """Supported asymmetric encryption algorithms."""
    RSA_2048 = "rsa-2048"
    RSA_4096 = "rsa-4096"
    ECDSA_P256 = "ecdsa-p256"
    ECDSA_P384 = "ecdsa-p384"
    ED25519 = "ed25519"


class HashAlgorithm(str, Enum):
    """Supported hash algorithms."""
    SHA256 = "sha256"
    SHA384 = "sha384"
    SHA512 = "sha512"
    BLAKE2B = "blake2b"
    BLAKE2S = "blake2s"


class KeyType(str, Enum):
    """Types of cryptographic keys."""
    SYMMETRIC = "symmetric"
    PUBLIC = "public"
    PRIVATE = "private"
    SHARED = "shared"  # From key exchange


class KeyStatus(str, Enum):
    """Key lifecycle status."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    COMPROMISED = "compromised"
    EXPIRED = "expired"
    PENDING_ROTATION = "pending_rotation"


@dataclass
class CryptoKey:
    """Cryptographic key representation."""
    key_id: str
    key_type: KeyType
    algorithm: str
    key_material: bytes  # Simulated key bytes
    created_at: datetime = field(default_factory=datetime.now)
    expires_at: Optional[datetime] = None
    status: KeyStatus = KeyStatus.ACTIVE
    owner_id: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)

    # For asymmetric keys
    paired_key_id: Optional[str] = None  # Links public/private pairs

    def is_expired(self) -> bool:
        """Check if key has expired."""
        if self.expires_at is None:
            return False
        return datetime.now() > self.expires_at

    def is_usable(self) -> bool:
        """Check if key can be used."""
        return self.status == KeyStatus.ACTIVE and not self.is_expired()

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary (without key material for security)."""
        return {
            "key_id": self.key_id,
            "key_type": self.key_type.value,
            "algorithm": self.algorithm,
            "created_at": self.created_at.isoformat(),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "status": self.status.value,
            "owner_id": self.owner_id,
            "paired_key_id": self.paired_key_id,
            "key_length_bits": len(self.key_material) * 8,
        }


@dataclass
class EncryptedData:
    """Container for encrypted data."""
    ciphertext: bytes
    algorithm: str
    key_id: str
    iv: Optional[bytes] = None  # Initialization vector
    auth_tag: Optional[bytes] = None  # For authenticated encryption
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "ciphertext": base64.b64encode(self.ciphertext).decode(),
            "algorithm": self.algorithm,
            "key_id": self.key_id,
            "iv": base64.b64encode(self.iv).decode() if self.iv else None,
            "auth_tag": base64.b64encode(self.auth_tag).decode() if self.auth_tag else None,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata,
        }


@dataclass
class Signature:
    """Digital signature."""
    signature_id: str
    signature_bytes: bytes
    algorithm: str
    key_id: str
    data_hash: str
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "signature_id": self.signature_id,
            "signature": base64.b64encode(self.signature_bytes).decode(),
            "algorithm": self.algorithm,
            "key_id": self.key_id,
            "data_hash": self.data_hash,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class KeyExchangeSession:
    """Key exchange session (Diffie-Hellman style)."""
    session_id: str
    initiator_id: str
    responder_id: str
    algorithm: str
    public_value_initiator: bytes
    public_value_responder: Optional[bytes] = None
    shared_secret: Optional[bytes] = None
    derived_key_id: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None
    status: str = "pending"


@dataclass
class EncryptionConfig:
    """Encryption engine configuration."""
    default_symmetric_algorithm: SymmetricAlgorithm = SymmetricAlgorithm.AES_256_GCM
    default_asymmetric_algorithm: AsymmetricAlgorithm = AsymmetricAlgorithm.RSA_2048
    default_hash_algorithm: HashAlgorithm = HashAlgorithm.SHA256
    key_rotation_interval_days: int = 90
    max_key_age_days: int = 365
    enable_key_escrow: bool = False
    secure_memory_wipe: bool = True


class EncryptionEngine:
    """
    Cryptographic operations engine for IoT security simulation.

    Simulates encryption, decryption, key management, and digital signatures.
    Uses real cryptographic primitives for hashing but simulates
    encryption/decryption for educational purposes.
    """

    def __init__(self, config: Optional[EncryptionConfig] = None):
        """
        Initialize encryption engine.

        Args:
            config: Encryption configuration
        """
        self.config = config or EncryptionConfig()

        # Key storage
        self._keys: dict[str, CryptoKey] = {}
        self._key_exchanges: dict[str, KeyExchangeSession] = {}

        # Statistics
        self._stats = {
            "encryptions": 0,
            "decryptions": 0,
            "signatures_created": 0,
            "signatures_verified": 0,
            "keys_generated": 0,
            "key_exchanges": 0,
            "errors": 0,
        }

        self._running = False
        self._rotation_task: Optional[asyncio.Task] = None

        logger.info("EncryptionEngine initialized")

    async def start(self) -> None:
        """Start the encryption engine."""
        self._running = True
        self._rotation_task = asyncio.create_task(self._key_rotation_loop())
        logger.info("EncryptionEngine started")

    async def stop(self) -> None:
        """Stop the encryption engine."""
        self._running = False
        if self._rotation_task:
            self._rotation_task.cancel()
            try:
                await self._rotation_task
            except asyncio.CancelledError:
                pass

        # Secure memory wipe (simulated)
        if self.config.secure_memory_wipe:
            await self._secure_wipe_keys()

        logger.info("EncryptionEngine stopped")

    # ========== Key Generation ==========

    async def generate_symmetric_key(
        self,
        algorithm: Optional[SymmetricAlgorithm] = None,
        owner_id: Optional[str] = None,
        expires_in_days: Optional[int] = None,
    ) -> CryptoKey:
        """
        Generate a symmetric encryption key.

        Args:
            algorithm: Encryption algorithm
            owner_id: Key owner identifier
            expires_in_days: Days until expiration

        Returns:
            Generated key
        """
        algorithm = algorithm or self.config.default_symmetric_algorithm

        # Determine key size based on algorithm
        key_sizes = {
            SymmetricAlgorithm.AES_128_GCM: 16,
            SymmetricAlgorithm.AES_256_GCM: 32,
            SymmetricAlgorithm.AES_128_CBC: 16,
            SymmetricAlgorithm.AES_256_CBC: 32,
            SymmetricAlgorithm.CHACHA20_POLY1305: 32,
        }

        key_size = key_sizes.get(algorithm, 32)
        key_material = secrets.token_bytes(key_size)

        key = CryptoKey(
            key_id=f"sym_{secrets.token_hex(8)}",
            key_type=KeyType.SYMMETRIC,
            algorithm=algorithm.value,
            key_material=key_material,
            owner_id=owner_id,
            expires_at=datetime.now() + timedelta(days=expires_in_days) if expires_in_days else None,
        )

        self._keys[key.key_id] = key
        self._stats["keys_generated"] += 1

        logger.debug(f"Generated symmetric key: {key.key_id} ({algorithm.value})")
        return key

    async def generate_asymmetric_keypair(
        self,
        algorithm: Optional[AsymmetricAlgorithm] = None,
        owner_id: Optional[str] = None,
        expires_in_days: Optional[int] = None,
    ) -> tuple[CryptoKey, CryptoKey]:
        """
        Generate an asymmetric key pair.

        Args:
            algorithm: Encryption algorithm
            owner_id: Key owner identifier
            expires_in_days: Days until expiration

        Returns:
            Tuple of (public_key, private_key)
        """
        algorithm = algorithm or self.config.default_asymmetric_algorithm

        # Simulated key sizes
        key_sizes = {
            AsymmetricAlgorithm.RSA_2048: (256, 256),
            AsymmetricAlgorithm.RSA_4096: (512, 512),
            AsymmetricAlgorithm.ECDSA_P256: (32, 32),
            AsymmetricAlgorithm.ECDSA_P384: (48, 48),
            AsymmetricAlgorithm.ED25519: (32, 32),
        }

        pub_size, priv_size = key_sizes.get(algorithm, (32, 32))

        # Generate simulated key material
        public_material = secrets.token_bytes(pub_size)
        private_material = secrets.token_bytes(priv_size)

        base_id = secrets.token_hex(8)
        expires_at = datetime.now() + timedelta(days=expires_in_days) if expires_in_days else None

        public_key = CryptoKey(
            key_id=f"pub_{base_id}",
            key_type=KeyType.PUBLIC,
            algorithm=algorithm.value,
            key_material=public_material,
            owner_id=owner_id,
            expires_at=expires_at,
            paired_key_id=f"priv_{base_id}",
        )

        private_key = CryptoKey(
            key_id=f"priv_{base_id}",
            key_type=KeyType.PRIVATE,
            algorithm=algorithm.value,
            key_material=private_material,
            owner_id=owner_id,
            expires_at=expires_at,
            paired_key_id=f"pub_{base_id}",
        )

        self._keys[public_key.key_id] = public_key
        self._keys[private_key.key_id] = private_key
        self._stats["keys_generated"] += 2

        logger.debug(f"Generated asymmetric keypair: {public_key.key_id} / {private_key.key_id}")
        return public_key, private_key

    # ========== Encryption / Decryption ==========

    async def encrypt(
        self,
        plaintext: bytes,
        key_id: str,
        associated_data: Optional[bytes] = None,
    ) -> tuple[Optional[EncryptedData], Optional[str]]:
        """
        Encrypt data using symmetric encryption.

        Args:
            plaintext: Data to encrypt
            key_id: Key identifier
            associated_data: Additional authenticated data (for AEAD)

        Returns:
            Tuple of (encrypted_data, error_message)
        """
        key = self._keys.get(key_id)
        if not key:
            return None, f"Key not found: {key_id}"

        if not key.is_usable():
            return None, f"Key is not usable: {key.status.value}"

        if key.key_type != KeyType.SYMMETRIC:
            return None, f"Invalid key type for symmetric encryption: {key.key_type.value}"

        try:
            # Generate IV
            iv = secrets.token_bytes(12)  # 96 bits for GCM

            # Simulate encryption (XOR with key-derived stream for demo)
            # In production, use proper cryptographic libraries
            key_stream = self._derive_keystream(key.key_material, iv, len(plaintext))
            ciphertext = bytes(a ^ b for a, b in zip(plaintext, key_stream))

            # Generate auth tag (simulated HMAC)
            auth_data = ciphertext + (associated_data or b"")
            auth_tag = hmac.new(key.key_material, auth_data, hashlib.sha256).digest()[:16]

            encrypted = EncryptedData(
                ciphertext=ciphertext,
                algorithm=key.algorithm,
                key_id=key_id,
                iv=iv,
                auth_tag=auth_tag,
            )

            self._stats["encryptions"] += 1
            logger.debug(f"Encrypted {len(plaintext)} bytes with key {key_id}")

            return encrypted, None

        except Exception as e:
            self._stats["errors"] += 1
            logger.error(f"Encryption error: {e}")
            return None, str(e)

    async def decrypt(
        self,
        encrypted_data: EncryptedData,
        associated_data: Optional[bytes] = None,
    ) -> tuple[Optional[bytes], Optional[str]]:
        """
        Decrypt data using symmetric encryption.

        Args:
            encrypted_data: Encrypted data container
            associated_data: Additional authenticated data (for AEAD)

        Returns:
            Tuple of (plaintext, error_message)
        """
        key = self._keys.get(encrypted_data.key_id)
        if not key:
            return None, f"Key not found: {encrypted_data.key_id}"

        if not key.is_usable():
            return None, f"Key is not usable: {key.status.value}"

        try:
            # Verify auth tag
            auth_data = encrypted_data.ciphertext + (associated_data or b"")
            expected_tag = hmac.new(key.key_material, auth_data, hashlib.sha256).digest()[:16]

            if encrypted_data.auth_tag and not hmac.compare_digest(encrypted_data.auth_tag, expected_tag):
                return None, "Authentication tag mismatch - data may be tampered"

            # Simulate decryption
            key_stream = self._derive_keystream(
                key.key_material,
                encrypted_data.iv or b"",
                len(encrypted_data.ciphertext)
            )
            plaintext = bytes(a ^ b for a, b in zip(encrypted_data.ciphertext, key_stream))

            self._stats["decryptions"] += 1
            logger.debug(f"Decrypted {len(plaintext)} bytes with key {encrypted_data.key_id}")

            return plaintext, None

        except Exception as e:
            self._stats["errors"] += 1
            logger.error(f"Decryption error: {e}")
            return None, str(e)

    async def encrypt_asymmetric(
        self,
        plaintext: bytes,
        public_key_id: str,
    ) -> tuple[Optional[EncryptedData], Optional[str]]:
        """
        Encrypt data using asymmetric encryption.

        Args:
            plaintext: Data to encrypt
            public_key_id: Public key identifier

        Returns:
            Tuple of (encrypted_data, error_message)
        """
        key = self._keys.get(public_key_id)
        if not key:
            return None, f"Key not found: {public_key_id}"

        if key.key_type != KeyType.PUBLIC:
            return None, f"Invalid key type: {key.key_type.value} (expected public)"

        if not key.is_usable():
            return None, f"Key is not usable: {key.status.value}"

        try:
            # Simulate RSA-OAEP encryption
            # Generate random padding
            padding = secrets.token_bytes(32)
            padded_data = padding + plaintext

            # Simulated encryption using key material
            ciphertext = self._simulate_asymmetric_encrypt(padded_data, key.key_material)

            encrypted = EncryptedData(
                ciphertext=ciphertext,
                algorithm=key.algorithm,
                key_id=public_key_id,
            )

            self._stats["encryptions"] += 1
            return encrypted, None

        except Exception as e:
            self._stats["errors"] += 1
            return None, str(e)

    async def decrypt_asymmetric(
        self,
        encrypted_data: EncryptedData,
        private_key_id: str,
    ) -> tuple[Optional[bytes], Optional[str]]:
        """
        Decrypt data using asymmetric encryption.

        Args:
            encrypted_data: Encrypted data container
            private_key_id: Private key identifier

        Returns:
            Tuple of (plaintext, error_message)
        """
        key = self._keys.get(private_key_id)
        if not key:
            return None, f"Key not found: {private_key_id}"

        if key.key_type != KeyType.PRIVATE:
            return None, f"Invalid key type: {key.key_type.value} (expected private)"

        if not key.is_usable():
            return None, f"Key is not usable: {key.status.value}"

        try:
            # Simulated decryption
            padded_data = self._simulate_asymmetric_decrypt(encrypted_data.ciphertext, key.key_material)

            # Remove padding (first 32 bytes)
            plaintext = padded_data[32:] if len(padded_data) > 32 else padded_data

            self._stats["decryptions"] += 1
            return plaintext, None

        except Exception as e:
            self._stats["errors"] += 1
            return None, str(e)

    # ========== Digital Signatures ==========

    async def sign(
        self,
        data: bytes,
        private_key_id: str,
        algorithm: Optional[HashAlgorithm] = None,
    ) -> tuple[Optional[Signature], Optional[str]]:
        """
        Create a digital signature.

        Args:
            data: Data to sign
            private_key_id: Private key identifier
            algorithm: Hash algorithm

        Returns:
            Tuple of (signature, error_message)
        """
        key = self._keys.get(private_key_id)
        if not key:
            return None, f"Key not found: {private_key_id}"

        if key.key_type != KeyType.PRIVATE:
            return None, f"Invalid key type for signing: {key.key_type.value}"

        if not key.is_usable():
            return None, f"Key is not usable: {key.status.value}"

        algorithm = algorithm or self.config.default_hash_algorithm

        try:
            # Hash the data
            data_hash = self._hash_data(data, algorithm)

            # Create signature (simulated using HMAC with private key)
            signature_bytes = hmac.new(
                key.key_material,
                data_hash.encode(),
                hashlib.sha256
            ).digest()

            signature = Signature(
                signature_id=f"sig_{secrets.token_hex(8)}",
                signature_bytes=signature_bytes,
                algorithm=f"{key.algorithm}+{algorithm.value}",
                key_id=private_key_id,
                data_hash=data_hash,
            )

            self._stats["signatures_created"] += 1
            logger.debug(f"Created signature {signature.signature_id}")

            return signature, None

        except Exception as e:
            self._stats["errors"] += 1
            return None, str(e)

    async def verify_signature(
        self,
        data: bytes,
        signature: Signature,
        public_key_id: Optional[str] = None,
    ) -> tuple[bool, Optional[str]]:
        """
        Verify a digital signature.

        Args:
            data: Original data
            signature: Signature to verify
            public_key_id: Public key ID (inferred from signature if not provided)

        Returns:
            Tuple of (is_valid, error_message)
        """
        # Get the private key to find its paired public key
        private_key = self._keys.get(signature.key_id)
        if not private_key:
            return False, f"Signing key not found: {signature.key_id}"

        if public_key_id:
            public_key = self._keys.get(public_key_id)
        elif private_key.paired_key_id:
            public_key = self._keys.get(private_key.paired_key_id)
        else:
            return False, "No public key available for verification"

        if not public_key:
            return False, "Public key not found"

        try:
            # Extract hash algorithm from signature algorithm
            algo_parts = signature.algorithm.split("+")
            hash_algo = HashAlgorithm(algo_parts[1]) if len(algo_parts) > 1 else self.config.default_hash_algorithm

            # Verify data hash matches
            current_hash = self._hash_data(data, hash_algo)
            if current_hash != signature.data_hash:
                return False, "Data hash mismatch - data has been modified"

            # Verify signature (simulated)
            expected_signature = hmac.new(
                private_key.key_material,
                signature.data_hash.encode(),
                hashlib.sha256
            ).digest()

            if hmac.compare_digest(signature.signature_bytes, expected_signature):
                self._stats["signatures_verified"] += 1
                return True, None
            else:
                return False, "Signature verification failed"

        except Exception as e:
            self._stats["errors"] += 1
            return False, str(e)

    # ========== Key Exchange ==========

    async def initiate_key_exchange(
        self,
        initiator_id: str,
        responder_id: str,
        algorithm: str = "ecdh-p256",
    ) -> tuple[Optional[KeyExchangeSession], Optional[str]]:
        """
        Initiate a key exchange session.

        Args:
            initiator_id: Initiating party identifier
            responder_id: Responding party identifier
            algorithm: Key exchange algorithm

        Returns:
            Tuple of (session, error_message)
        """
        try:
            session = KeyExchangeSession(
                session_id=f"kex_{secrets.token_hex(8)}",
                initiator_id=initiator_id,
                responder_id=responder_id,
                algorithm=algorithm,
                public_value_initiator=secrets.token_bytes(32),  # Simulated public value
            )

            self._key_exchanges[session.session_id] = session
            self._stats["key_exchanges"] += 1

            logger.debug(f"Initiated key exchange session: {session.session_id}")
            return session, None

        except Exception as e:
            self._stats["errors"] += 1
            return None, str(e)

    async def complete_key_exchange(
        self,
        session_id: str,
        responder_public_value: Optional[bytes] = None,
    ) -> tuple[Optional[CryptoKey], Optional[str]]:
        """
        Complete a key exchange and derive shared secret.

        Args:
            session_id: Key exchange session identifier
            responder_public_value: Responder's public value

        Returns:
            Tuple of (derived_key, error_message)
        """
        session = self._key_exchanges.get(session_id)
        if not session:
            return None, f"Key exchange session not found: {session_id}"

        if session.status == "completed":
            # Return existing derived key
            if session.derived_key_id:
                return self._keys.get(session.derived_key_id), None
            return None, "Session completed but no derived key"

        try:
            # Set responder's public value
            session.public_value_responder = responder_public_value or secrets.token_bytes(32)

            # Derive shared secret (simulated ECDH)
            combined = session.public_value_initiator + session.public_value_responder
            session.shared_secret = hashlib.sha256(combined).digest()

            # Create derived symmetric key
            derived_key = CryptoKey(
                key_id=f"derived_{secrets.token_hex(8)}",
                key_type=KeyType.SHARED,
                algorithm="aes-256-gcm",
                key_material=session.shared_secret,
                metadata={
                    "source": "key_exchange",
                    "session_id": session_id,
                    "parties": [session.initiator_id, session.responder_id],
                },
            )

            self._keys[derived_key.key_id] = derived_key
            session.derived_key_id = derived_key.key_id
            session.completed_at = datetime.now()
            session.status = "completed"

            logger.debug(f"Completed key exchange {session_id}, derived key: {derived_key.key_id}")
            return derived_key, None

        except Exception as e:
            session.status = "failed"
            self._stats["errors"] += 1
            return None, str(e)

    # ========== Hashing ==========

    def hash(
        self,
        data: bytes,
        algorithm: Optional[HashAlgorithm] = None,
    ) -> str:
        """
        Hash data using specified algorithm.

        Args:
            data: Data to hash
            algorithm: Hash algorithm

        Returns:
            Hex-encoded hash
        """
        return self._hash_data(data, algorithm or self.config.default_hash_algorithm)

    def hmac_sign(
        self,
        data: bytes,
        key: bytes,
        algorithm: Optional[HashAlgorithm] = None,
    ) -> bytes:
        """
        Create HMAC signature.

        Args:
            data: Data to sign
            key: HMAC key
            algorithm: Hash algorithm

        Returns:
            HMAC bytes
        """
        algorithm = algorithm or self.config.default_hash_algorithm
        hash_func = getattr(hashlib, algorithm.value)
        return hmac.new(key, data, hash_func).digest()

    def hmac_verify(
        self,
        data: bytes,
        key: bytes,
        expected_hmac: bytes,
        algorithm: Optional[HashAlgorithm] = None,
    ) -> bool:
        """
        Verify HMAC signature.

        Args:
            data: Original data
            key: HMAC key
            expected_hmac: Expected HMAC value
            algorithm: Hash algorithm

        Returns:
            True if valid
        """
        computed = self.hmac_sign(data, key, algorithm)
        return hmac.compare_digest(computed, expected_hmac)

    # ========== Key Management ==========

    def get_key(self, key_id: str) -> Optional[CryptoKey]:
        """Get a key by ID."""
        return self._keys.get(key_id)

    async def rotate_key(self, key_id: str) -> tuple[Optional[CryptoKey], Optional[str]]:
        """
        Rotate a key (generate new key, mark old as inactive).

        Args:
            key_id: Key to rotate

        Returns:
            Tuple of (new_key, error_message)
        """
        old_key = self._keys.get(key_id)
        if not old_key:
            return None, f"Key not found: {key_id}"

        try:
            # Generate replacement key
            if old_key.key_type == KeyType.SYMMETRIC:
                algo = SymmetricAlgorithm(old_key.algorithm)
                new_key = await self.generate_symmetric_key(
                    algorithm=algo,
                    owner_id=old_key.owner_id,
                )
            else:
                return None, "Asymmetric key rotation not yet supported"

            # Mark old key as inactive
            old_key.status = KeyStatus.INACTIVE
            old_key.metadata["rotated_to"] = new_key.key_id
            new_key.metadata["rotated_from"] = key_id

            logger.info(f"Rotated key {key_id} -> {new_key.key_id}")
            return new_key, None

        except Exception as e:
            self._stats["errors"] += 1
            return None, str(e)

    async def revoke_key(self, key_id: str, reason: str = "manual") -> bool:
        """
        Revoke a key.

        Args:
            key_id: Key to revoke
            reason: Revocation reason

        Returns:
            True if revoked
        """
        key = self._keys.get(key_id)
        if not key:
            return False

        key.status = KeyStatus.COMPROMISED
        key.metadata["revocation_reason"] = reason
        key.metadata["revoked_at"] = datetime.now().isoformat()

        # Also revoke paired key if asymmetric
        if key.paired_key_id:
            paired = self._keys.get(key.paired_key_id)
            if paired:
                paired.status = KeyStatus.COMPROMISED
                paired.metadata["revocation_reason"] = f"paired key revoked: {reason}"

        logger.warning(f"Revoked key {key_id}: {reason}")
        return True

    def list_keys(
        self,
        owner_id: Optional[str] = None,
        key_type: Optional[KeyType] = None,
        status: Optional[KeyStatus] = None,
    ) -> list[CryptoKey]:
        """
        List keys with optional filters.

        Args:
            owner_id: Filter by owner
            key_type: Filter by type
            status: Filter by status

        Returns:
            List of matching keys
        """
        keys = list(self._keys.values())

        if owner_id:
            keys = [k for k in keys if k.owner_id == owner_id]
        if key_type:
            keys = [k for k in keys if k.key_type == key_type]
        if status:
            keys = [k for k in keys if k.status == status]

        return keys

    # ========== Internal Methods ==========

    def _hash_data(self, data: bytes, algorithm: HashAlgorithm) -> str:
        """Hash data using specified algorithm."""
        if algorithm == HashAlgorithm.BLAKE2B:
            return hashlib.blake2b(data).hexdigest()
        elif algorithm == HashAlgorithm.BLAKE2S:
            return hashlib.blake2s(data).hexdigest()
        else:
            hash_func = getattr(hashlib, algorithm.value)
            return hash_func(data).hexdigest()

    def _derive_keystream(self, key: bytes, iv: bytes, length: int) -> bytes:
        """Derive a keystream for symmetric encryption (simulated)."""
        stream = b""
        counter = 0
        while len(stream) < length:
            block = hashlib.sha256(key + iv + counter.to_bytes(4, 'big')).digest()
            stream += block
            counter += 1
        return stream[:length]

    def _simulate_asymmetric_encrypt(self, data: bytes, key: bytes) -> bytes:
        """Simulate asymmetric encryption."""
        # Simple simulation using XOR with key-derived stream
        stream = self._derive_keystream(key, b"asymmetric", len(data))
        return bytes(a ^ b for a, b in zip(data, stream))

    def _simulate_asymmetric_decrypt(self, data: bytes, key: bytes) -> bytes:
        """Simulate asymmetric decryption."""
        # Symmetric XOR operation
        stream = self._derive_keystream(key, b"asymmetric", len(data))
        return bytes(a ^ b for a, b in zip(data, stream))

    async def _key_rotation_loop(self) -> None:
        """Background task for automatic key rotation."""
        while self._running:
            try:
                await asyncio.sleep(3600)  # Check every hour

                rotation_threshold = datetime.now() - timedelta(
                    days=self.config.key_rotation_interval_days
                )

                for key in list(self._keys.values()):
                    if (key.status == KeyStatus.ACTIVE and
                        key.created_at < rotation_threshold and
                        key.key_type == KeyType.SYMMETRIC):

                        key.status = KeyStatus.PENDING_ROTATION
                        logger.info(f"Key {key.key_id} marked for rotation")

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Key rotation loop error: {e}")

    async def _secure_wipe_keys(self) -> None:
        """Securely wipe keys from memory (simulated)."""
        for key in self._keys.values():
            # Overwrite key material with zeros (simulated)
            key.key_material = bytes(len(key.key_material))
        logger.debug("Performed secure memory wipe")

    def get_stats(self) -> dict[str, Any]:
        """Get encryption engine statistics."""
        return {
            **self._stats,
            "total_keys": len(self._keys),
            "active_keys": len([k for k in self._keys.values() if k.status == KeyStatus.ACTIVE]),
            "pending_exchanges": len([s for s in self._key_exchanges.values() if s.status == "pending"]),
        }
