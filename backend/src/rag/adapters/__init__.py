"""
RAG Adapters - Multi-source knowledge adapters for the Smart Home Security Simulator.

This module provides adapters for various knowledge sources:
- Academic papers (arXiv, Semantic Scholar, IEEE, ACM)
- Threat intelligence (MITRE ATT&CK, NVD CVE, CWE)
- Device specifications (datasheets, protocols, security advisories)
"""

from src.rag.adapters.academic_adapter import (
    AcademicPaper,
    AcademicPaperAdapter,
    AcademicSource,
    ArxivClient,
    LocalPDFIngester,
    SemanticScholarClient,
    get_academic_adapter,
)
from src.rag.adapters.threat_intel_adapter import (
    CVEEntry,
    CWEEntry,
    MitreAttackClient,
    MitreAttackTechnique,
    NVDClient,
    ThreatIntelAdapter,
    ThreatSource,
    get_threat_intel_adapter,
)
from src.rag.adapters.device_spec_adapter import (
    CommunicationProtocol,
    DeviceCategory,
    DeviceSpecAdapter,
    DeviceSpecification,
    LocalDeviceDatabase,
    ProtocolSpecification,
    SecurityAdvisory,
    SpecSource,
    get_device_spec_adapter,
)

__all__ = [
    # Academic Adapter
    "AcademicPaper",
    "AcademicPaperAdapter",
    "AcademicSource",
    "ArxivClient",
    "LocalPDFIngester",
    "SemanticScholarClient",
    "get_academic_adapter",
    # Threat Intelligence Adapter
    "CVEEntry",
    "CWEEntry",
    "MitreAttackClient",
    "MitreAttackTechnique",
    "NVDClient",
    "ThreatIntelAdapter",
    "ThreatSource",
    "get_threat_intel_adapter",
    # Device Specification Adapter
    "CommunicationProtocol",
    "DeviceCategory",
    "DeviceSpecAdapter",
    "DeviceSpecification",
    "LocalDeviceDatabase",
    "ProtocolSpecification",
    "SecurityAdvisory",
    "SpecSource",
    "get_device_spec_adapter",
]
