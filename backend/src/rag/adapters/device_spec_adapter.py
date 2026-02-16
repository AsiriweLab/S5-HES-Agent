"""
Device Specification Adapter - IoT device documentation and specifications management.

This adapter manages:
- Device datasheets and technical specifications
- Protocol documentation (Zigbee, Z-Wave, Matter, Thread, etc.)
- Manufacturer security advisories
- Known vulnerability databases for IoT devices
- Communication protocol specifications
"""

import asyncio
import json
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urljoin

import aiohttp

logger = logging.getLogger(__name__)


class DeviceCategory(str, Enum):
    """IoT device categories."""
    SMART_LIGHT = "smart_light"
    SMART_PLUG = "smart_plug"
    SMART_THERMOSTAT = "smart_thermostat"
    SMART_LOCK = "smart_lock"
    SMART_CAMERA = "smart_camera"
    SMART_SENSOR = "smart_sensor"
    SMART_SPEAKER = "smart_speaker"
    SMART_HUB = "smart_hub"
    SMART_APPLIANCE = "smart_appliance"
    UNKNOWN = "unknown"


class CommunicationProtocol(str, Enum):
    """IoT communication protocols."""
    ZIGBEE = "zigbee"
    ZWAVE = "zwave"
    WIFI = "wifi"
    BLUETOOTH = "bluetooth"
    BLUETOOTH_LE = "bluetooth_le"
    MATTER = "matter"
    THREAD = "thread"
    MQTT = "mqtt"
    COAP = "coap"
    HTTP = "http"
    PROPRIETARY = "proprietary"


class SpecSource(str, Enum):
    """Device specification sources."""
    MANUFACTURER = "manufacturer"
    ZIGBEE_ALLIANCE = "zigbee_alliance"
    ZWAVE_ALLIANCE = "zwave_alliance"
    CSA_MATTER = "csa_matter"  # Connectivity Standards Alliance
    COMMUNITY = "community"
    LOCAL_DATABASE = "local_database"


@dataclass
class DeviceSpecification:
    """IoT device specification."""
    device_id: str
    manufacturer: str
    model: str
    category: DeviceCategory
    protocols: list[CommunicationProtocol]

    # Technical specifications
    firmware_version: Optional[str] = None
    hardware_version: Optional[str] = None
    power_consumption: Optional[str] = None
    operating_temperature: Optional[str] = None

    # Security information
    encryption_supported: list[str] = field(default_factory=list)
    authentication_methods: list[str] = field(default_factory=list)
    known_vulnerabilities: list[str] = field(default_factory=list)
    security_certifications: list[str] = field(default_factory=list)

    # Documentation
    datasheet_url: Optional[str] = None
    manual_url: Optional[str] = None
    api_documentation: Optional[str] = None

    # Metadata
    source: SpecSource = SpecSource.LOCAL_DATABASE
    last_updated: datetime = field(default_factory=datetime.utcnow)
    raw_data: dict[str, Any] = field(default_factory=dict)

    def to_document_text(self) -> str:
        """Convert specification to searchable document text."""
        sections = [
            f"Device: {self.manufacturer} {self.model}",
            f"Category: {self.category.value}",
            f"Protocols: {', '.join(p.value for p in self.protocols)}",
        ]

        if self.firmware_version:
            sections.append(f"Firmware: {self.firmware_version}")
        if self.encryption_supported:
            sections.append(f"Encryption: {', '.join(self.encryption_supported)}")
        if self.authentication_methods:
            sections.append(f"Authentication: {', '.join(self.authentication_methods)}")
        if self.known_vulnerabilities:
            sections.append(f"Known Vulnerabilities: {', '.join(self.known_vulnerabilities)}")
        if self.security_certifications:
            sections.append(f"Security Certifications: {', '.join(self.security_certifications)}")

        return "\n".join(sections)


@dataclass
class ProtocolSpecification:
    """Communication protocol specification."""
    protocol: CommunicationProtocol
    version: str
    specification_url: Optional[str] = None

    # Security features
    security_features: list[str] = field(default_factory=list)
    encryption_methods: list[str] = field(default_factory=list)
    key_exchange: Optional[str] = None

    # Network characteristics
    topology: Optional[str] = None  # mesh, star, etc.
    range_meters: Optional[int] = None
    data_rate: Optional[str] = None
    frequency: Optional[str] = None

    # Vulnerability information
    known_attacks: list[str] = field(default_factory=list)
    mitigations: list[str] = field(default_factory=list)

    source: SpecSource = SpecSource.LOCAL_DATABASE
    last_updated: datetime = field(default_factory=datetime.utcnow)

    def to_document_text(self) -> str:
        """Convert protocol spec to searchable document text."""
        sections = [
            f"Protocol: {self.protocol.value} v{self.version}",
        ]

        if self.topology:
            sections.append(f"Topology: {self.topology}")
        if self.frequency:
            sections.append(f"Frequency: {self.frequency}")
        if self.security_features:
            sections.append(f"Security Features: {', '.join(self.security_features)}")
        if self.encryption_methods:
            sections.append(f"Encryption: {', '.join(self.encryption_methods)}")
        if self.known_attacks:
            sections.append(f"Known Attacks: {', '.join(self.known_attacks)}")
        if self.mitigations:
            sections.append(f"Mitigations: {', '.join(self.mitigations)}")

        return "\n".join(sections)


@dataclass
class SecurityAdvisory:
    """Manufacturer or protocol security advisory."""
    advisory_id: str
    title: str
    description: str
    severity: str  # critical, high, medium, low
    affected_devices: list[str]
    affected_protocols: list[CommunicationProtocol]

    cve_ids: list[str] = field(default_factory=list)
    remediation: Optional[str] = None
    published_date: Optional[datetime] = None
    source: str = "unknown"
    url: Optional[str] = None

    def to_document_text(self) -> str:
        """Convert advisory to searchable document text."""
        sections = [
            f"Advisory: {self.advisory_id} - {self.title}",
            f"Severity: {self.severity}",
            f"Description: {self.description}",
        ]

        if self.affected_devices:
            sections.append(f"Affected Devices: {', '.join(self.affected_devices)}")
        if self.affected_protocols:
            sections.append(f"Affected Protocols: {', '.join(p.value for p in self.affected_protocols)}")
        if self.cve_ids:
            sections.append(f"CVEs: {', '.join(self.cve_ids)}")
        if self.remediation:
            sections.append(f"Remediation: {self.remediation}")

        return "\n".join(sections)


class LocalDeviceDatabase:
    """Local database of device specifications."""

    def __init__(self, database_path: Optional[Path] = None):
        """Initialize local device database."""
        self.database_path = database_path or Path("knowledge_base/device_specs")
        self.devices: dict[str, DeviceSpecification] = {}
        self.protocols: dict[CommunicationProtocol, ProtocolSpecification] = {}
        self.advisories: list[SecurityAdvisory] = []
        self._initialized = False

    async def initialize(self) -> None:
        """Load device database from disk."""
        if self._initialized:
            return

        # Load devices
        devices_file = self.database_path / "devices.json"
        if devices_file.exists():
            try:
                data = json.loads(devices_file.read_text())
                for device_data in data.get("devices", []):
                    spec = self._parse_device_spec(device_data)
                    self.devices[spec.device_id] = spec
                logger.info(f"Loaded {len(self.devices)} device specifications")
            except Exception as e:
                logger.warning(f"Failed to load devices.json: {e}")

        # Load protocol specifications
        protocols_file = self.database_path / "protocols.json"
        if protocols_file.exists():
            try:
                data = json.loads(protocols_file.read_text())
                for protocol_data in data.get("protocols", []):
                    spec = self._parse_protocol_spec(protocol_data)
                    self.protocols[spec.protocol] = spec
                logger.info(f"Loaded {len(self.protocols)} protocol specifications")
            except Exception as e:
                logger.warning(f"Failed to load protocols.json: {e}")

        # Load security advisories
        advisories_file = self.database_path / "advisories.json"
        if advisories_file.exists():
            try:
                data = json.loads(advisories_file.read_text())
                for advisory_data in data.get("advisories", []):
                    advisory = self._parse_advisory(advisory_data)
                    self.advisories.append(advisory)
                logger.info(f"Loaded {len(self.advisories)} security advisories")
            except Exception as e:
                logger.warning(f"Failed to load advisories.json: {e}")

        # Initialize with default protocol specs if none loaded
        if not self.protocols:
            self._initialize_default_protocols()

        self._initialized = True

    def _parse_device_spec(self, data: dict) -> DeviceSpecification:
        """Parse device specification from JSON data."""
        return DeviceSpecification(
            device_id=data.get("device_id", ""),
            manufacturer=data.get("manufacturer", "Unknown"),
            model=data.get("model", "Unknown"),
            category=DeviceCategory(data.get("category", "unknown")),
            protocols=[CommunicationProtocol(p) for p in data.get("protocols", [])],
            firmware_version=data.get("firmware_version"),
            hardware_version=data.get("hardware_version"),
            power_consumption=data.get("power_consumption"),
            operating_temperature=data.get("operating_temperature"),
            encryption_supported=data.get("encryption_supported", []),
            authentication_methods=data.get("authentication_methods", []),
            known_vulnerabilities=data.get("known_vulnerabilities", []),
            security_certifications=data.get("security_certifications", []),
            datasheet_url=data.get("datasheet_url"),
            manual_url=data.get("manual_url"),
            api_documentation=data.get("api_documentation"),
            source=SpecSource(data.get("source", "local_database")),
            raw_data=data,
        )

    def _parse_protocol_spec(self, data: dict) -> ProtocolSpecification:
        """Parse protocol specification from JSON data."""
        return ProtocolSpecification(
            protocol=CommunicationProtocol(data.get("protocol", "proprietary")),
            version=data.get("version", "1.0"),
            specification_url=data.get("specification_url"),
            security_features=data.get("security_features", []),
            encryption_methods=data.get("encryption_methods", []),
            key_exchange=data.get("key_exchange"),
            topology=data.get("topology"),
            range_meters=data.get("range_meters"),
            data_rate=data.get("data_rate"),
            frequency=data.get("frequency"),
            known_attacks=data.get("known_attacks", []),
            mitigations=data.get("mitigations", []),
            source=SpecSource(data.get("source", "local_database")),
        )

    def _parse_advisory(self, data: dict) -> SecurityAdvisory:
        """Parse security advisory from JSON data."""
        published = data.get("published_date")
        if published:
            try:
                published = datetime.fromisoformat(published)
            except ValueError:
                published = None

        return SecurityAdvisory(
            advisory_id=data.get("advisory_id", ""),
            title=data.get("title", ""),
            description=data.get("description", ""),
            severity=data.get("severity", "medium"),
            affected_devices=data.get("affected_devices", []),
            affected_protocols=[CommunicationProtocol(p) for p in data.get("affected_protocols", [])],
            cve_ids=data.get("cve_ids", []),
            remediation=data.get("remediation"),
            published_date=published,
            source=data.get("source", "unknown"),
            url=data.get("url"),
        )

    def _initialize_default_protocols(self) -> None:
        """Initialize with well-known protocol specifications."""
        default_protocols = [
            ProtocolSpecification(
                protocol=CommunicationProtocol.ZIGBEE,
                version="3.0",
                specification_url="https://csa-iot.org/developer-resource/specifications-download-request/",
                security_features=["AES-128 encryption", "Network key", "Link key", "Trust center"],
                encryption_methods=["AES-128-CCM"],
                key_exchange="CBKE (Certificate-Based Key Exchange)",
                topology="Mesh",
                range_meters=100,
                data_rate="250 kbps",
                frequency="2.4 GHz",
                known_attacks=[
                    "Key sniffing during joining",
                    "Replay attacks",
                    "ZigBee worm (CVE-2015-2880)",
                    "Insecure rejoin",
                ],
                mitigations=[
                    "Use install codes for secure joining",
                    "Enable APS encryption",
                    "Use unique link keys",
                    "Disable insecure rejoin",
                ],
                source=SpecSource.ZIGBEE_ALLIANCE,
            ),
            ProtocolSpecification(
                protocol=CommunicationProtocol.ZWAVE,
                version="7.0 (S2)",
                specification_url="https://www.silabs.com/wireless/z-wave",
                security_features=["S2 security framework", "ECDH key exchange", "AES-128"],
                encryption_methods=["AES-128-CCM", "AES-128-CBC"],
                key_exchange="ECDH (Curve25519)",
                topology="Mesh",
                range_meters=30,
                data_rate="100 kbps",
                frequency="908.42 MHz (US), 868.42 MHz (EU)",
                known_attacks=[
                    "S0 downgrade attack",
                    "Signal jamming",
                    "Key extraction (pre-S2)",
                ],
                mitigations=[
                    "Use S2 security only",
                    "Disable S0 fallback",
                    "Use authenticated inclusion",
                ],
                source=SpecSource.ZWAVE_ALLIANCE,
            ),
            ProtocolSpecification(
                protocol=CommunicationProtocol.MATTER,
                version="1.2",
                specification_url="https://csa-iot.org/all-solutions/matter/",
                security_features=[
                    "Certificate-based device attestation",
                    "CASE (Certificate Authenticated Session Establishment)",
                    "PASE (Password Authenticated Session Establishment)",
                    "Operational certificates",
                ],
                encryption_methods=["AES-128-CCM", "ECDSA P-256"],
                key_exchange="ECDH (P-256)",
                topology="Mesh (Thread), Star (Wi-Fi)",
                frequency="2.4 GHz (Thread/Wi-Fi)",
                known_attacks=[
                    "Relatively new - limited attack research",
                    "Potential for implementation vulnerabilities",
                ],
                mitigations=[
                    "Use certified devices",
                    "Keep firmware updated",
                    "Use proper commissioning procedures",
                ],
                source=SpecSource.CSA_MATTER,
            ),
            ProtocolSpecification(
                protocol=CommunicationProtocol.THREAD,
                version="1.3",
                specification_url="https://www.threadgroup.org/",
                security_features=[
                    "IEEE 802.15.4 security",
                    "Network-wide key",
                    "Device-to-device encryption",
                    "Secure commissioning",
                ],
                encryption_methods=["AES-128-CCM"],
                key_exchange="DTLS with ECDH",
                topology="Mesh",
                range_meters=100,
                data_rate="250 kbps",
                frequency="2.4 GHz",
                known_attacks=[
                    "Network key exposure",
                    "Commissioning attacks",
                ],
                mitigations=[
                    "Secure key storage",
                    "Use Thread Border Router with proper security",
                ],
                source=SpecSource.CSA_MATTER,
            ),
            ProtocolSpecification(
                protocol=CommunicationProtocol.BLUETOOTH_LE,
                version="5.3",
                specification_url="https://www.bluetooth.com/specifications/specs/",
                security_features=[
                    "LE Secure Connections",
                    "ECDH key exchange",
                    "AES-CCM encryption",
                    "Privacy features (address randomization)",
                ],
                encryption_methods=["AES-128-CCM"],
                key_exchange="ECDH (P-256)",
                topology="Star, Mesh (Bluetooth Mesh)",
                range_meters=100,
                data_rate="2 Mbps",
                frequency="2.4 GHz",
                known_attacks=[
                    "KNOB attack (key negotiation)",
                    "BIAS attack (impersonation)",
                    "BlueBorne (CVE-2017-1000251)",
                    "SweynTooth",
                    "BLESA (spoofing)",
                ],
                mitigations=[
                    "Use LE Secure Connections only",
                    "Enforce minimum key size",
                    "Keep firmware updated",
                    "Use random addresses",
                ],
                source=SpecSource.COMMUNITY,
            ),
            ProtocolSpecification(
                protocol=CommunicationProtocol.MQTT,
                version="5.0",
                specification_url="https://mqtt.org/mqtt-specification/",
                security_features=[
                    "TLS/SSL support",
                    "Username/password authentication",
                    "Enhanced authentication (MQTT 5.0)",
                    "Topic-based ACLs",
                ],
                encryption_methods=["TLS 1.2/1.3", "AES-256-GCM"],
                key_exchange="TLS handshake",
                topology="Client-Broker (hub-and-spoke)",
                known_attacks=[
                    "Man-in-the-middle (without TLS)",
                    "Credential sniffing",
                    "Topic squatting",
                    "Denial of service",
                ],
                mitigations=[
                    "Always use TLS",
                    "Use strong authentication",
                    "Implement proper ACLs",
                    "Use client certificates",
                ],
                source=SpecSource.COMMUNITY,
            ),
        ]

        for protocol in default_protocols:
            self.protocols[protocol.protocol] = protocol

    def search_devices(
        self,
        query: str,
        category: Optional[DeviceCategory] = None,
        protocol: Optional[CommunicationProtocol] = None,
    ) -> list[DeviceSpecification]:
        """Search devices by query string."""
        results = []
        query_lower = query.lower()

        for device in self.devices.values():
            # Check category filter
            if category and device.category != category:
                continue
            # Check protocol filter
            if protocol and protocol not in device.protocols:
                continue
            # Check query match
            searchable = f"{device.manufacturer} {device.model} {device.category.value}".lower()
            if query_lower in searchable:
                results.append(device)

        return results

    def get_protocol_spec(self, protocol: CommunicationProtocol) -> Optional[ProtocolSpecification]:
        """Get specification for a specific protocol."""
        return self.protocols.get(protocol)

    def search_advisories(
        self,
        query: str,
        severity: Optional[str] = None,
        protocol: Optional[CommunicationProtocol] = None,
    ) -> list[SecurityAdvisory]:
        """Search security advisories."""
        results = []
        query_lower = query.lower()

        for advisory in self.advisories:
            # Check severity filter
            if severity and advisory.severity.lower() != severity.lower():
                continue
            # Check protocol filter
            if protocol and protocol not in advisory.affected_protocols:
                continue
            # Check query match
            searchable = f"{advisory.title} {advisory.description}".lower()
            if query_lower in searchable or not query:
                results.append(advisory)

        return results

    async def add_device(self, spec: DeviceSpecification) -> None:
        """Add or update a device specification."""
        self.devices[spec.device_id] = spec
        await self._save_devices()

    async def _save_devices(self) -> None:
        """Save devices to disk."""
        self.database_path.mkdir(parents=True, exist_ok=True)
        devices_file = self.database_path / "devices.json"

        data = {
            "devices": [
                {
                    "device_id": d.device_id,
                    "manufacturer": d.manufacturer,
                    "model": d.model,
                    "category": d.category.value,
                    "protocols": [p.value for p in d.protocols],
                    "firmware_version": d.firmware_version,
                    "hardware_version": d.hardware_version,
                    "power_consumption": d.power_consumption,
                    "encryption_supported": d.encryption_supported,
                    "authentication_methods": d.authentication_methods,
                    "known_vulnerabilities": d.known_vulnerabilities,
                    "security_certifications": d.security_certifications,
                    "datasheet_url": d.datasheet_url,
                    "source": d.source.value,
                }
                for d in self.devices.values()
            ]
        }

        devices_file.write_text(json.dumps(data, indent=2))


class DeviceSpecAdapter:
    """
    Unified adapter for IoT device specifications and protocol documentation.

    Provides:
    - Device specification lookup and search
    - Protocol documentation and security info
    - Security advisory aggregation
    - Integration with knowledge base for RAG
    """

    def __init__(
        self,
        database_path: Optional[Path] = None,
        knowledge_base: Optional[Any] = None,
    ):
        """Initialize device specification adapter."""
        self.local_db = LocalDeviceDatabase(database_path)
        self.knowledge_base = knowledge_base
        self._session: Optional[aiohttp.ClientSession] = None

    async def initialize(self) -> None:
        """Initialize the adapter and load local database."""
        await self.local_db.initialize()
        logger.info("DeviceSpecAdapter initialized")

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    async def close(self) -> None:
        """Close the adapter and cleanup resources."""
        if self._session and not self._session.closed:
            await self._session.close()

    async def search_device_specs(
        self,
        query: str,
        category: Optional[DeviceCategory] = None,
        protocol: Optional[CommunicationProtocol] = None,
        include_rag: bool = True,
    ) -> list[DeviceSpecification]:
        """
        Search for device specifications.

        Args:
            query: Search query string
            category: Filter by device category
            protocol: Filter by communication protocol
            include_rag: Whether to also search RAG knowledge base

        Returns:
            List of matching device specifications
        """
        results = self.local_db.search_devices(query, category, protocol)

        # Also search knowledge base if available
        if include_rag and self.knowledge_base:
            try:
                from src.rag.knowledge_base import CollectionType

                rag_query = f"device specification {query}"
                if category:
                    rag_query += f" {category.value}"
                if protocol:
                    rag_query += f" {protocol.value}"

                rag_results = await self.knowledge_base.query(
                    query=rag_query,
                    collection_type=CollectionType.DEVICE_MANUALS,
                    n_results=5,
                )

                # Convert RAG results to DeviceSpecification if possible
                for doc in rag_results.get("documents", [[]])[0]:
                    # Try to extract device info from document
                    extracted = self._extract_device_from_text(doc)
                    if extracted:
                        results.append(extracted)

            except Exception as e:
                logger.warning(f"Failed to search knowledge base: {e}")

        return results

    def _extract_device_from_text(self, text: str) -> Optional[DeviceSpecification]:
        """Try to extract device specification from document text."""
        # Simple extraction - could be enhanced with NLP
        manufacturer_match = re.search(r"manufacturer[:\s]+([^\n,]+)", text, re.I)
        model_match = re.search(r"model[:\s]+([^\n,]+)", text, re.I)

        if manufacturer_match and model_match:
            return DeviceSpecification(
                device_id=f"extracted_{hash(text) % 10000}",
                manufacturer=manufacturer_match.group(1).strip(),
                model=model_match.group(1).strip(),
                category=DeviceCategory.UNKNOWN,
                protocols=[],
                source=SpecSource.LOCAL_DATABASE,
            )
        return None

    def get_protocol_specification(
        self,
        protocol: CommunicationProtocol,
    ) -> Optional[ProtocolSpecification]:
        """
        Get detailed specification for a communication protocol.

        Args:
            protocol: The protocol to get specification for

        Returns:
            Protocol specification or None if not found
        """
        return self.local_db.get_protocol_spec(protocol)

    def get_all_protocols(self) -> list[ProtocolSpecification]:
        """Get all available protocol specifications."""
        return list(self.local_db.protocols.values())

    async def search_security_advisories(
        self,
        query: str = "",
        severity: Optional[str] = None,
        protocol: Optional[CommunicationProtocol] = None,
        device_id: Optional[str] = None,
    ) -> list[SecurityAdvisory]:
        """
        Search security advisories.

        Args:
            query: Search query string
            severity: Filter by severity (critical, high, medium, low)
            protocol: Filter by affected protocol
            device_id: Filter by affected device

        Returns:
            List of matching security advisories
        """
        results = self.local_db.search_advisories(query, severity, protocol)

        if device_id:
            results = [
                a for a in results
                if device_id in a.affected_devices
            ]

        return results

    async def get_protocol_vulnerabilities(
        self,
        protocol: CommunicationProtocol,
    ) -> dict[str, Any]:
        """
        Get comprehensive vulnerability information for a protocol.

        Args:
            protocol: The protocol to analyze

        Returns:
            Dictionary with vulnerability information
        """
        spec = self.get_protocol_specification(protocol)
        advisories = await self.search_security_advisories(protocol=protocol)

        return {
            "protocol": protocol.value,
            "specification": spec,
            "known_attacks": spec.known_attacks if spec else [],
            "mitigations": spec.mitigations if spec else [],
            "advisories": advisories,
            "advisory_count": len(advisories),
            "critical_advisories": len([a for a in advisories if a.severity == "critical"]),
        }

    async def compare_protocols(
        self,
        protocols: list[CommunicationProtocol],
    ) -> dict[str, Any]:
        """
        Compare security features of multiple protocols.

        Args:
            protocols: List of protocols to compare

        Returns:
            Comparison dictionary
        """
        comparison = {
            "protocols": [],
            "security_comparison": {},
        }

        for protocol in protocols:
            spec = self.get_protocol_specification(protocol)
            if spec:
                comparison["protocols"].append({
                    "name": protocol.value,
                    "version": spec.version,
                    "encryption": spec.encryption_methods,
                    "key_exchange": spec.key_exchange,
                    "topology": spec.topology,
                    "known_attacks": len(spec.known_attacks),
                    "security_features": spec.security_features,
                })

        return comparison

    async def ingest_datasheet(
        self,
        pdf_path: Path,
        manufacturer: str,
        model: str,
        category: DeviceCategory,
        protocols: list[CommunicationProtocol],
    ) -> Optional[DeviceSpecification]:
        """
        Ingest a device datasheet PDF into the knowledge base.

        Args:
            pdf_path: Path to the PDF datasheet
            manufacturer: Device manufacturer
            model: Device model name
            category: Device category
            protocols: Supported communication protocols

        Returns:
            Created DeviceSpecification or None on failure
        """
        if not pdf_path.exists():
            logger.error(f"Datasheet not found: {pdf_path}")
            return None

        try:
            # Extract text from PDF
            text = ""
            try:
                import pypdf
                reader = pypdf.PdfReader(str(pdf_path))
                for page in reader.pages:
                    text += page.extract_text() + "\n"
            except ImportError:
                logger.warning("pypdf not installed, cannot extract PDF text")

            # Create device specification
            spec = DeviceSpecification(
                device_id=f"{manufacturer}_{model}".replace(" ", "_").lower(),
                manufacturer=manufacturer,
                model=model,
                category=category,
                protocols=protocols,
                datasheet_url=str(pdf_path),
                source=SpecSource.MANUFACTURER,
                raw_data={"extracted_text": text[:5000]},  # Limit stored text
            )

            # Extract additional info from text
            spec = self._enrich_spec_from_text(spec, text)

            # Add to local database
            await self.local_db.add_device(spec)

            # Add to knowledge base if available
            if self.knowledge_base and text:
                try:
                    from src.rag.knowledge_base import CollectionType

                    await self.knowledge_base.add_document(
                        content=text,
                        collection_type=CollectionType.DEVICE_MANUALS,
                        metadata={
                            "type": "datasheet",
                            "manufacturer": manufacturer,
                            "model": model,
                            "category": category.value,
                            "protocols": [p.value for p in protocols],
                            "source_file": str(pdf_path),
                        },
                    )
                except Exception as e:
                    logger.warning(f"Failed to add to knowledge base: {e}")

            logger.info(f"Ingested datasheet for {manufacturer} {model}")
            return spec

        except Exception as e:
            logger.error(f"Failed to ingest datasheet: {e}")
            return None

    def _enrich_spec_from_text(
        self,
        spec: DeviceSpecification,
        text: str,
    ) -> DeviceSpecification:
        """Extract additional specification details from text."""
        text_lower = text.lower()

        # Extract encryption info
        encryption_patterns = [
            r"(aes[-\s]?128)", r"(aes[-\s]?256)", r"(tls\s*1\.[0-3])",
            r"(ssl)", r"(wpa[23]?)", r"(https)",
        ]
        for pattern in encryption_patterns:
            if re.search(pattern, text_lower):
                match = re.search(pattern, text_lower).group(1).upper()
                if match not in spec.encryption_supported:
                    spec.encryption_supported.append(match)

        # Extract certifications
        cert_patterns = [
            r"(zigbee\s*certified)", r"(z-wave\s*certified)", r"(matter\s*certified)",
            r"(ul\s*listed)", r"(fcc\s*certified)", r"(ce\s*marked)",
        ]
        for pattern in cert_patterns:
            match = re.search(pattern, text_lower)
            if match:
                cert = match.group(1).title()
                if cert not in spec.security_certifications:
                    spec.security_certifications.append(cert)

        # Extract firmware version
        fw_match = re.search(r"firmware\s*(?:version)?[:\s]+([v\d.]+)", text_lower)
        if fw_match and not spec.firmware_version:
            spec.firmware_version = fw_match.group(1)

        return spec

    def get_security_recommendations(
        self,
        protocol: CommunicationProtocol,
    ) -> list[str]:
        """
        Get security recommendations for a protocol.

        Args:
            protocol: The protocol to get recommendations for

        Returns:
            List of security recommendations
        """
        spec = self.get_protocol_specification(protocol)
        if not spec:
            return ["No specification available for this protocol"]

        recommendations = []

        # Add mitigations as recommendations
        recommendations.extend(spec.mitigations)

        # Add general recommendations based on protocol
        if protocol == CommunicationProtocol.ZIGBEE:
            recommendations.extend([
                "Use Zigbee 3.0 with enhanced security features",
                "Enable APS layer encryption for sensitive data",
                "Monitor for unauthorized device joins",
            ])
        elif protocol == CommunicationProtocol.ZWAVE:
            recommendations.extend([
                "Ensure all devices use S2 security framework",
                "Use SmartStart for secure device inclusion",
                "Regularly audit network for S0-only devices",
            ])
        elif protocol == CommunicationProtocol.BLUETOOTH_LE:
            recommendations.extend([
                "Use LE Secure Connections (LESC) pairing",
                "Enable address randomization",
                "Implement proper bond management",
            ])
        elif protocol == CommunicationProtocol.MQTT:
            recommendations.extend([
                "Always use TLS 1.2 or higher",
                "Implement proper topic-based ACLs",
                "Use client certificate authentication when possible",
            ])

        return recommendations


# Factory function for easy instantiation
def get_device_spec_adapter(
    database_path: Optional[Path] = None,
    knowledge_base: Optional[Any] = None,
) -> DeviceSpecAdapter:
    """Get or create DeviceSpecAdapter instance."""
    return DeviceSpecAdapter(database_path, knowledge_base)
