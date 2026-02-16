"""
Threat Intelligence Adapter for the Smart-HES Framework.

Ingests threat intelligence from multiple sources:
- MITRE ATT&CK (TTPs, techniques)
- NVD (NIST National Vulnerability Database)
- CVE.org (Vulnerability IDs)
- MITRE CWE (Weakness patterns)
- ExploitDB (PoC exploits)

Provides unified interface for threat intelligence retrieval and indexing.
"""

import asyncio
import json
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Optional

import httpx
from loguru import logger


class ThreatSource(str, Enum):
    """Threat intelligence sources."""
    MITRE_ATTACK = "mitre_attack"
    NVD = "nvd"
    CVE = "cve"
    CWE = "cwe"
    EXPLOIT_DB = "exploit_db"


class AttackTactic(str, Enum):
    """MITRE ATT&CK Tactics."""
    RECONNAISSANCE = "reconnaissance"
    RESOURCE_DEVELOPMENT = "resource-development"
    INITIAL_ACCESS = "initial-access"
    EXECUTION = "execution"
    PERSISTENCE = "persistence"
    PRIVILEGE_ESCALATION = "privilege-escalation"
    DEFENSE_EVASION = "defense-evasion"
    CREDENTIAL_ACCESS = "credential-access"
    DISCOVERY = "discovery"
    LATERAL_MOVEMENT = "lateral-movement"
    COLLECTION = "collection"
    COMMAND_AND_CONTROL = "command-and-control"
    EXFILTRATION = "exfiltration"
    IMPACT = "impact"


@dataclass
class MitreAttackTechnique:
    """MITRE ATT&CK Technique."""
    technique_id: str  # e.g., T1133
    name: str
    description: str
    tactics: list[AttackTactic] = field(default_factory=list)
    platforms: list[str] = field(default_factory=list)
    data_sources: list[str] = field(default_factory=list)
    detection: str = ""
    mitigations: list[str] = field(default_factory=list)
    sub_techniques: list[str] = field(default_factory=list)
    is_sub_technique: bool = False
    parent_technique: Optional[str] = None
    url: str = ""

    def to_document(self) -> dict:
        """Convert to knowledge base document format."""
        tactics_str = ", ".join(t.value for t in self.tactics)
        platforms_str = ", ".join(self.platforms)

        content = f"MITRE ATT&CK Technique: {self.technique_id} - {self.name}\n\n"
        content += f"Tactics: {tactics_str}\n"
        content += f"Platforms: {platforms_str}\n\n"
        content += f"Description:\n{self.description}\n\n"
        if self.detection:
            content += f"Detection:\n{self.detection}\n\n"
        if self.mitigations:
            content += f"Mitigations:\n" + "\n".join(f"- {m}" for m in self.mitigations)

        return {
            "content": content,
            "metadata": {
                "title": f"{self.technique_id}: {self.name}",
                "category": "threat_intel",
                "source": "mitre_attack",
                "technique_id": self.technique_id,
                "tactics": tactics_str,
                "platforms": platforms_str,
            },
        }


@dataclass
class CVEEntry:
    """CVE Vulnerability entry."""
    cve_id: str  # e.g., CVE-2021-44228
    description: str
    published_date: Optional[datetime] = None
    last_modified: Optional[datetime] = None
    cvss_v3_score: Optional[float] = None
    cvss_v3_vector: Optional[str] = None
    severity: str = ""  # CRITICAL, HIGH, MEDIUM, LOW
    affected_products: list[str] = field(default_factory=list)
    references: list[str] = field(default_factory=list)
    cwe_ids: list[str] = field(default_factory=list)
    exploitability_score: Optional[float] = None
    impact_score: Optional[float] = None

    def to_document(self) -> dict:
        """Convert to knowledge base document format."""
        content = f"CVE: {self.cve_id}\n"
        content += f"Severity: {self.severity}\n"
        if self.cvss_v3_score:
            content += f"CVSS v3 Score: {self.cvss_v3_score}\n"
        content += f"\nDescription:\n{self.description}\n"

        if self.affected_products:
            content += f"\nAffected Products:\n"
            for product in self.affected_products[:10]:
                content += f"- {product}\n"

        if self.cwe_ids:
            content += f"\nRelated Weaknesses: {', '.join(self.cwe_ids)}\n"

        return {
            "content": content,
            "metadata": {
                "title": self.cve_id,
                "category": "threat_intel",
                "source": "nvd",
                "cve_id": self.cve_id,
                "severity": self.severity,
                "cvss_score": self.cvss_v3_score or 0,
                "cwe_ids": ",".join(self.cwe_ids),
            },
        }


@dataclass
class CWEEntry:
    """CWE Weakness entry."""
    cwe_id: str  # e.g., CWE-79
    name: str
    description: str
    extended_description: str = ""
    likelihood_of_exploit: str = ""
    common_consequences: list[str] = field(default_factory=list)
    detection_methods: list[str] = field(default_factory=list)
    mitigations: list[str] = field(default_factory=list)
    related_attack_patterns: list[str] = field(default_factory=list)
    related_cves: list[str] = field(default_factory=list)

    def to_document(self) -> dict:
        """Convert to knowledge base document format."""
        content = f"CWE: {self.cwe_id} - {self.name}\n\n"
        content += f"Description:\n{self.description}\n\n"

        if self.extended_description:
            content += f"Extended Description:\n{self.extended_description}\n\n"

        if self.likelihood_of_exploit:
            content += f"Likelihood of Exploit: {self.likelihood_of_exploit}\n\n"

        if self.common_consequences:
            content += "Common Consequences:\n"
            for c in self.common_consequences[:5]:
                content += f"- {c}\n"
            content += "\n"

        if self.mitigations:
            content += "Mitigations:\n"
            for m in self.mitigations[:5]:
                content += f"- {m}\n"

        return {
            "content": content,
            "metadata": {
                "title": f"{self.cwe_id}: {self.name}",
                "category": "threat_intel",
                "source": "cwe",
                "cwe_id": self.cwe_id,
                "likelihood": self.likelihood_of_exploit,
            },
        }


class MitreAttackClient:
    """Client for MITRE ATT&CK data."""

    # ATT&CK STIX data URLs
    ENTERPRISE_URL = "https://raw.githubusercontent.com/mitre/cti/master/enterprise-attack/enterprise-attack.json"
    ICS_URL = "https://raw.githubusercontent.com/mitre/cti/master/ics-attack/ics-attack.json"

    def __init__(self, cache_dir: Path = None):
        self.cache_dir = cache_dir or Path("knowledge_base/threat_intel/mitre")
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._techniques: dict[str, MitreAttackTechnique] = {}

    async def load_attack_data(self, use_cache: bool = True) -> int:
        """Load MITRE ATT&CK data."""
        cache_file = self.cache_dir / "enterprise-attack.json"

        if use_cache and cache_file.exists():
            # Load from cache
            with open(cache_file, "r") as f:
                data = json.load(f)
            logger.info("Loaded MITRE ATT&CK from cache")
        else:
            # Download fresh data
            async with httpx.AsyncClient(timeout=60.0) as client:
                try:
                    response = await client.get(self.ENTERPRISE_URL)
                    response.raise_for_status()
                    data = response.json()

                    # Cache data
                    with open(cache_file, "w") as f:
                        json.dump(data, f)
                    logger.info("Downloaded and cached MITRE ATT&CK data")

                except Exception as e:
                    logger.error(f"Failed to download ATT&CK data: {e}")
                    return 0

        # Parse techniques
        count = self._parse_stix_data(data)
        logger.info(f"Loaded {count} MITRE ATT&CK techniques")
        return count

    def _parse_stix_data(self, data: dict) -> int:
        """Parse STIX-formatted ATT&CK data."""
        objects = data.get("objects", [])

        # First pass: collect techniques
        techniques_data = {}
        for obj in objects:
            if obj.get("type") == "attack-pattern" and not obj.get("revoked", False):
                external_refs = obj.get("external_references", [])
                technique_id = None
                url = ""

                for ref in external_refs:
                    if ref.get("source_name") == "mitre-attack":
                        technique_id = ref.get("external_id")
                        url = ref.get("url", "")
                        break

                if technique_id:
                    techniques_data[obj["id"]] = {
                        "technique_id": technique_id,
                        "name": obj.get("name", ""),
                        "description": obj.get("description", ""),
                        "platforms": obj.get("x_mitre_platforms", []),
                        "data_sources": obj.get("x_mitre_data_sources", []),
                        "detection": obj.get("x_mitre_detection", ""),
                        "is_sub_technique": obj.get("x_mitre_is_subtechnique", False),
                        "url": url,
                        "stix_id": obj["id"],
                    }

        # Second pass: collect tactics and relationships
        tactic_map = {}
        for obj in objects:
            if obj.get("type") == "x-mitre-tactic":
                shortname = obj.get("x_mitre_shortname", "")
                tactic_map[obj["id"]] = shortname

        # Map techniques to tactics via kill chain phases
        for obj in objects:
            if obj.get("type") == "attack-pattern":
                stix_id = obj["id"]
                if stix_id in techniques_data:
                    kill_chain_phases = obj.get("kill_chain_phases", [])
                    tactics = []
                    for phase in kill_chain_phases:
                        if phase.get("kill_chain_name") == "mitre-attack":
                            phase_name = phase.get("phase_name", "")
                            try:
                                tactics.append(AttackTactic(phase_name))
                            except ValueError:
                                pass
                    techniques_data[stix_id]["tactics"] = tactics

        # Build technique objects
        for stix_id, tech_data in techniques_data.items():
            technique = MitreAttackTechnique(
                technique_id=tech_data["technique_id"],
                name=tech_data["name"],
                description=tech_data["description"],
                tactics=tech_data.get("tactics", []),
                platforms=tech_data["platforms"],
                data_sources=tech_data["data_sources"],
                detection=tech_data["detection"],
                is_sub_technique=tech_data["is_sub_technique"],
                url=tech_data["url"],
            )
            self._techniques[technique.technique_id] = technique

        return len(self._techniques)

    def get_technique(self, technique_id: str) -> Optional[MitreAttackTechnique]:
        """Get a specific technique."""
        return self._techniques.get(technique_id)

    def get_techniques_by_tactic(self, tactic: AttackTactic) -> list[MitreAttackTechnique]:
        """Get all techniques for a tactic."""
        return [t for t in self._techniques.values() if tactic in t.tactics]

    def search_techniques(self, query: str, limit: int = 10) -> list[MitreAttackTechnique]:
        """Search techniques by keyword."""
        query_lower = query.lower()
        matches = []

        for technique in self._techniques.values():
            score = 0
            if query_lower in technique.name.lower():
                score += 3
            if query_lower in technique.description.lower():
                score += 1
            if query_lower in technique.technique_id.lower():
                score += 5

            if score > 0:
                matches.append((score, technique))

        # Sort by score and return top matches
        matches.sort(key=lambda x: x[0], reverse=True)
        return [t for _, t in matches[:limit]]

    def get_all_techniques(self) -> list[MitreAttackTechnique]:
        """Get all techniques."""
        return list(self._techniques.values())


class NVDClient:
    """Client for NIST National Vulnerability Database."""

    BASE_URL = "https://services.nvd.nist.gov/rest/json/cves/2.0"

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key
        self.headers = {}
        if api_key:
            self.headers["apiKey"] = api_key

    async def search_cves(
        self,
        keyword: str = None,
        cve_id: str = None,
        cwe_id: str = None,
        cvss_severity: str = None,
        results_per_page: int = 20,
    ) -> list[CVEEntry]:
        """Search CVEs in NVD."""
        params = {"resultsPerPage": results_per_page}

        if keyword:
            params["keywordSearch"] = keyword
        if cve_id:
            params["cveId"] = cve_id
        if cwe_id:
            params["cweId"] = cwe_id
        if cvss_severity:
            params["cvssV3Severity"] = cvss_severity.upper()

        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.get(
                    self.BASE_URL,
                    params=params,
                    headers=self.headers,
                )
                response.raise_for_status()
                data = response.json()

                cves = []
                for item in data.get("vulnerabilities", []):
                    cve = self._parse_cve(item.get("cve", {}))
                    if cve:
                        cves.append(cve)

                logger.info(f"NVD: Found {len(cves)} CVEs")
                return cves

            except Exception as e:
                logger.error(f"NVD search failed: {e}")
                return []

    def _parse_cve(self, data: dict) -> Optional[CVEEntry]:
        """Parse NVD CVE response."""
        try:
            cve_id = data.get("id", "")
            if not cve_id:
                return None

            # Get description (prefer English)
            description = ""
            for desc in data.get("descriptions", []):
                if desc.get("lang") == "en":
                    description = desc.get("value", "")
                    break

            # Parse CVSS v3 metrics
            cvss_score = None
            cvss_vector = None
            severity = ""

            metrics = data.get("metrics", {})
            cvss_v3 = metrics.get("cvssMetricV31", []) or metrics.get("cvssMetricV30", [])
            if cvss_v3:
                cvss_data = cvss_v3[0].get("cvssData", {})
                cvss_score = cvss_data.get("baseScore")
                cvss_vector = cvss_data.get("vectorString")
                severity = cvss_data.get("baseSeverity", "")

            # Parse CWE IDs
            cwe_ids = []
            for weakness in data.get("weaknesses", []):
                for desc in weakness.get("description", []):
                    value = desc.get("value", "")
                    if value.startswith("CWE-"):
                        cwe_ids.append(value)

            # Parse references
            references = []
            for ref in data.get("references", []):
                url = ref.get("url", "")
                if url:
                    references.append(url)

            # Parse dates
            published = data.get("published")
            modified = data.get("lastModified")

            return CVEEntry(
                cve_id=cve_id,
                description=description,
                published_date=datetime.fromisoformat(published.replace("Z", "+00:00")) if published else None,
                last_modified=datetime.fromisoformat(modified.replace("Z", "+00:00")) if modified else None,
                cvss_v3_score=cvss_score,
                cvss_v3_vector=cvss_vector,
                severity=severity,
                cwe_ids=cwe_ids,
                references=references[:10],
            )

        except Exception as e:
            logger.error(f"Failed to parse CVE: {e}")
            return None

    async def get_cve(self, cve_id: str) -> Optional[CVEEntry]:
        """Get a specific CVE by ID."""
        cves = await self.search_cves(cve_id=cve_id)
        return cves[0] if cves else None


class ThreatIntelAdapter:
    """
    Unified adapter for threat intelligence ingestion and retrieval.

    Supports multiple sources:
    - MITRE ATT&CK (TTPs)
    - NVD (CVEs)
    - CWE (Weaknesses)
    """

    def __init__(
        self,
        nvd_api_key: Optional[str] = None,
        cache_dir: Path = None,
    ):
        self.mitre = MitreAttackClient(cache_dir=cache_dir)
        self.nvd = NVDClient(api_key=nvd_api_key)

        # Cache
        self._cve_cache: dict[str, CVEEntry] = {}
        self._cwe_cache: dict[str, CWEEntry] = {}

        # Statistics
        self._stats = {
            "mitre_techniques_loaded": 0,
            "cves_fetched": 0,
            "cwes_loaded": 0,
        }

        logger.info("ThreatIntelAdapter initialized")

    async def initialize(self) -> None:
        """Initialize threat intelligence data."""
        # Load MITRE ATT&CK
        count = await self.mitre.load_attack_data()
        self._stats["mitre_techniques_loaded"] = count

    async def search_threats(
        self,
        query: str,
        sources: list[ThreatSource] = None,
        limit_per_source: int = 5,
    ) -> dict[ThreatSource, list]:
        """
        Search for threat intelligence across sources.

        Returns dict mapping source to results.
        """
        sources = sources or [ThreatSource.MITRE_ATTACK, ThreatSource.NVD]
        results = {}

        tasks = []

        if ThreatSource.MITRE_ATTACK in sources:
            # MITRE is synchronous (local data)
            results[ThreatSource.MITRE_ATTACK] = self.mitre.search_techniques(
                query, limit=limit_per_source
            )

        if ThreatSource.NVD in sources:
            tasks.append(self._search_nvd(query, limit_per_source))

        # Execute async searches
        if tasks:
            nvd_results = await asyncio.gather(*tasks, return_exceptions=True)
            for i, result in enumerate(nvd_results):
                if isinstance(result, list):
                    results[ThreatSource.NVD] = result
                elif isinstance(result, Exception):
                    logger.error(f"Search failed: {result}")
                    results[ThreatSource.NVD] = []

        return results

    async def _search_nvd(self, query: str, limit: int) -> list[CVEEntry]:
        """Search NVD for CVEs."""
        cves = await self.nvd.search_cves(keyword=query, results_per_page=limit)
        self._stats["cves_fetched"] += len(cves)

        # Cache results
        for cve in cves:
            self._cve_cache[cve.cve_id] = cve

        return cves

    async def get_cve(self, cve_id: str) -> Optional[CVEEntry]:
        """Get a specific CVE."""
        if cve_id in self._cve_cache:
            return self._cve_cache[cve_id]

        cve = await self.nvd.get_cve(cve_id)
        if cve:
            self._cve_cache[cve_id] = cve
        return cve

    def get_technique(self, technique_id: str) -> Optional[MitreAttackTechnique]:
        """Get a specific MITRE ATT&CK technique."""
        return self.mitre.get_technique(technique_id)

    def get_techniques_for_tactic(self, tactic: str) -> list[MitreAttackTechnique]:
        """Get techniques for a specific tactic."""
        try:
            tactic_enum = AttackTactic(tactic.lower().replace(" ", "-"))
            return self.mitre.get_techniques_by_tactic(tactic_enum)
        except ValueError:
            return []

    def get_iot_related_techniques(self) -> list[MitreAttackTechnique]:
        """Get techniques relevant to IoT security."""
        iot_keywords = [
            "iot", "embedded", "firmware", "network", "credential",
            "default", "exploit", "remote", "botnet", "ddos",
        ]

        techniques = []
        for technique in self.mitre.get_all_techniques():
            text = f"{technique.name} {technique.description}".lower()
            if any(kw in text for kw in iot_keywords):
                techniques.append(technique)

        return techniques

    async def get_iot_cves(self, limit: int = 50) -> list[CVEEntry]:
        """Get IoT-related CVEs."""
        iot_keywords = ["smart home", "iot", "router", "camera", "thermostat"]
        all_cves = []

        for keyword in iot_keywords:
            cves = await self.nvd.search_cves(
                keyword=keyword,
                results_per_page=limit // len(iot_keywords),
            )
            all_cves.extend(cves)

        # Deduplicate
        seen = set()
        unique_cves = []
        for cve in all_cves:
            if cve.cve_id not in seen:
                seen.add(cve.cve_id)
                unique_cves.append(cve)

        return unique_cves

    def get_all_documents(self) -> list[dict]:
        """Get all threat intel as documents for indexing."""
        documents = []

        # Add MITRE techniques
        for technique in self.mitre.get_all_techniques():
            documents.append(technique.to_document())

        # Add cached CVEs
        for cve in self._cve_cache.values():
            documents.append(cve.to_document())

        # Add cached CWEs
        for cwe in self._cwe_cache.values():
            documents.append(cwe.to_document())

        return documents

    def get_stats(self) -> dict:
        """Get adapter statistics."""
        return {
            **self._stats,
            "cached_cves": len(self._cve_cache),
            "cached_cwes": len(self._cwe_cache),
        }


# Global instance
_threat_intel_adapter: Optional[ThreatIntelAdapter] = None


def get_threat_intel_adapter() -> ThreatIntelAdapter:
    """Get or create the global threat intel adapter."""
    global _threat_intel_adapter
    if _threat_intel_adapter is None:
        _threat_intel_adapter = ThreatIntelAdapter()
    return _threat_intel_adapter
