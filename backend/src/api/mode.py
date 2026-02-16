"""
Mode and Expert Consultation API Endpoints

Implements the No-LLM Mode (Dual-Mode) functionality for research integrity.
Provides expert consultation with verification pipeline integration.

Features:
- Expert consultation requests with RAG-augmented responses
- Consultation feedback tracking (accept/reject)
- Pre-loaded scenario execution without LLM
- Mode enforcement for reproducible research
"""

import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Request, Depends
from pydantic import BaseModel, Field
from loguru import logger

from src.ai.llm.llm_engine import (
    InferenceResult,
    ResponseConfidence,
    get_llm_engine,
)
from src.rag.knowledge_base import get_knowledge_base, RAGContext


router = APIRouter()


# ===========================================================================
# Enums and Models
# ===========================================================================


class InteractionMode(str, Enum):
    """User interaction modes."""
    LLM = "llm"  # Full AI assistance
    NO_LLM = "no-llm"  # Pre-loaded scenarios only


class ConsultationStatus(str, Enum):
    """Expert consultation status."""
    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"


class ExpertConsultationRequest(BaseModel):
    """Request for expert AI consultation."""
    question: str = Field(..., description="User's question for AI expert")
    context: str = Field(default="", description="Additional context for the question")
    session_id: Optional[str] = Field(default=None, description="Session ID")
    use_rag: bool = Field(default=True, description="Use RAG for knowledge augmentation")


class ExpertConsultationResponse(BaseModel):
    """Response from expert AI consultation."""
    id: str
    question: str
    context: str
    response: str
    sources: list[str]
    confidence: str
    confidence_score: float
    status: ConsultationStatus
    timestamp: datetime
    rag_context_count: int
    inference_time_ms: float
    verification_notes: list[str]


class ConsultationFeedback(BaseModel):
    """Feedback for a consultation response."""
    accepted: bool
    reason: Optional[str] = Field(default=None, description="Reason for acceptance/rejection")
    notes: Optional[str] = Field(default=None, description="Additional notes")


class ConsultationFeedbackResponse(BaseModel):
    """Response after submitting consultation feedback."""
    id: str
    status: ConsultationStatus
    feedback_recorded: bool
    timestamp: datetime


class PreloadedScenario(BaseModel):
    """A pre-loaded scenario for No-LLM mode."""
    id: str
    name: str
    description: str
    category: str
    difficulty: str
    tags: list[str]
    home_config: Optional[dict] = None
    threat_config: Optional[dict] = None
    simulation_params: Optional[dict] = None


class ScenarioExecutionRequest(BaseModel):
    """Request to execute a pre-loaded scenario."""
    scenario_id: str
    custom_params: Optional[dict] = None


class ScenarioExecutionResponse(BaseModel):
    """Response from scenario execution."""
    execution_id: str
    scenario_id: str
    scenario_name: str
    status: str
    home_id: Optional[str] = None
    simulation_id: Optional[str] = None
    results: Optional[dict] = None
    timestamp: datetime


class ModeStatusResponse(BaseModel):
    """Current mode status."""
    mode: InteractionMode
    pending_consultations: int
    total_consultations: int
    accepted_consultations: int
    rejected_consultations: int
    available_scenarios: int
    llm_available: bool


# ===========================================================================
# In-Memory Storage (would use database in production)
# ===========================================================================


_consultations: dict[str, dict] = {}
_current_mode: InteractionMode = InteractionMode.LLM

# Pre-loaded scenarios for No-LLM mode
_preloaded_scenarios: dict[str, PreloadedScenario] = {
    "basic-attack-detection": PreloadedScenario(
        id="basic-attack-detection",
        name="Basic Attack Detection",
        description="Standard home setup with common IoT attack patterns for baseline testing",
        category="security",
        difficulty="beginner",
        tags=["baseline", "detection", "iot-attacks"],
        home_config={
            "template": "two_bedroom",
            "num_inhabitants": 2,
            "device_density": 1.0,
        },
        threat_config={
            "threats": ["data_exfiltration", "unauthorized_access"],
            "severity": "medium",
        },
        simulation_params={
            "duration_hours": 24,
            "time_compression": 60,
        },
    ),
    "traffic-analysis": PreloadedScenario(
        id="traffic-analysis",
        name="Network Traffic Analysis",
        description="Focus on network anomaly detection with varied traffic patterns",
        category="network",
        difficulty="intermediate",
        tags=["network", "anomaly", "traffic"],
        home_config={
            "template": "family_house",
            "num_inhabitants": 4,
            "device_density": 1.5,
        },
        threat_config={
            "threats": ["man_in_the_middle", "data_exfiltration"],
            "severity": "high",
        },
        simulation_params={
            "duration_hours": 48,
            "time_compression": 120,
        },
    ),
    "botnet-simulation": PreloadedScenario(
        id="botnet-simulation",
        name="Botnet Recruitment Simulation",
        description="Simulates IoT botnet recruitment and C2 communication",
        category="malware",
        difficulty="advanced",
        tags=["botnet", "malware", "c2"],
        home_config={
            "template": "smart_mansion",
            "num_inhabitants": 6,
            "device_density": 2.0,
        },
        threat_config={
            "threats": ["botnet_recruitment", "denial_of_service"],
            "severity": "critical",
        },
        simulation_params={
            "duration_hours": 72,
            "time_compression": 180,
        },
    ),
    "credential-theft": PreloadedScenario(
        id="credential-theft",
        name="Credential Theft Scenario",
        description="Tests credential harvesting and authentication bypass attacks",
        category="authentication",
        difficulty="intermediate",
        tags=["credentials", "authentication", "lateral-movement"],
        home_config={
            "template": "three_bedroom",
            "num_inhabitants": 3,
            "device_density": 1.2,
        },
        threat_config={
            "threats": ["credential_theft", "unauthorized_access"],
            "severity": "high",
        },
        simulation_params={
            "duration_hours": 24,
            "time_compression": 60,
        },
    ),
    "ransomware-attack": PreloadedScenario(
        id="ransomware-attack",
        name="IoT Ransomware Attack",
        description="Simulates ransomware targeting smart home devices",
        category="malware",
        difficulty="expert",
        tags=["ransomware", "malware", "encryption"],
        home_config={
            "template": "smart_mansion",
            "num_inhabitants": 4,
            "device_density": 2.0,
        },
        threat_config={
            "threats": ["ransomware", "data_exfiltration"],
            "severity": "critical",
        },
        simulation_params={
            "duration_hours": 24,
            "time_compression": 30,
        },
    ),
    "energy-manipulation": PreloadedScenario(
        id="energy-manipulation",
        name="Energy Grid Manipulation",
        description="Tests attacks on smart meters and energy management systems",
        category="critical-infrastructure",
        difficulty="advanced",
        tags=["energy", "smart-meter", "grid"],
        home_config={
            "template": "family_house",
            "num_inhabitants": 4,
            "device_density": 1.5,
        },
        threat_config={
            "threats": ["energy_theft", "device_tampering"],
            "severity": "high",
        },
        simulation_params={
            "duration_hours": 168,  # 1 week
            "time_compression": 360,
        },
    ),
    "surveillance-detection": PreloadedScenario(
        id="surveillance-detection",
        name="Surveillance Detection",
        description="Tests detection of unauthorized surveillance via cameras and microphones",
        category="privacy",
        difficulty="intermediate",
        tags=["surveillance", "privacy", "cameras"],
        home_config={
            "template": "two_bedroom",
            "num_inhabitants": 2,
            "device_density": 1.0,
        },
        threat_config={
            "threats": ["surveillance", "unauthorized_access"],
            "severity": "medium",
        },
        simulation_params={
            "duration_hours": 48,
            "time_compression": 60,
        },
    ),
    "apt-simulation": PreloadedScenario(
        id="apt-simulation",
        name="APT Simulation",
        description="Advanced Persistent Threat simulation with multi-stage attack chain",
        category="apt",
        difficulty="expert",
        tags=["apt", "multi-stage", "persistence"],
        home_config={
            "template": "smart_mansion",
            "num_inhabitants": 6,
            "device_density": 2.5,
        },
        threat_config={
            "threats": ["data_exfiltration", "credential_theft", "surveillance", "unauthorized_access"],
            "severity": "critical",
        },
        simulation_params={
            "duration_hours": 720,  # 30 days
            "time_compression": 720,
        },
    ),
}


# ===========================================================================
# Helper Functions
# ===========================================================================


def _calculate_confidence_score(confidence: ResponseConfidence) -> float:
    """Convert confidence level to numerical score."""
    mapping = {
        ResponseConfidence.HIGH: 0.9,
        ResponseConfidence.MEDIUM: 0.65,
        ResponseConfidence.LOW: 0.35,
        ResponseConfidence.UNKNOWN: 0.0,
    }
    return mapping.get(confidence, 0.0)


def _generate_verification_notes(
    rag_context: Optional[RAGContext],
    confidence: ResponseConfidence,
) -> list[str]:
    """Generate verification notes for research integrity."""
    notes = []

    if rag_context and rag_context.has_context:
        notes.append(f"Response augmented with {len(rag_context.contexts)} knowledge base sources")
        if rag_context.confidence_scores and len(rag_context.confidence_scores) > 0:
            avg_score = sum(rag_context.confidence_scores) / len(rag_context.confidence_scores)
            notes.append(f"Average RAG similarity score: {avg_score:.2f}")
    else:
        notes.append("No knowledge base context used - response may contain unverified information")

    if confidence == ResponseConfidence.HIGH:
        notes.append("High confidence - response well-supported by knowledge base")
    elif confidence == ResponseConfidence.MEDIUM:
        notes.append("Medium confidence - partial knowledge base support, review recommended")
    elif confidence == ResponseConfidence.LOW:
        notes.append("Low confidence - limited knowledge base support, verification required")
    else:
        notes.append("Unknown confidence - no verification performed")

    return notes


# ===========================================================================
# Mode Management Endpoints
# ===========================================================================


@router.get("/status", response_model=ModeStatusResponse)
async def get_mode_status():
    """
    Get the current mode status and statistics.

    Returns information about the current interaction mode,
    consultation statistics, and available scenarios.
    """
    pending = sum(1 for c in _consultations.values() if c["status"] == ConsultationStatus.PENDING)
    accepted = sum(1 for c in _consultations.values() if c["status"] == ConsultationStatus.ACCEPTED)
    rejected = sum(1 for c in _consultations.values() if c["status"] == ConsultationStatus.REJECTED)

    # Check LLM availability
    llm_available = True
    try:
        engine = get_llm_engine()
        health = await engine.check_health()
        llm_available = health.get("ollama_available", False)
    except Exception:
        llm_available = False

    return ModeStatusResponse(
        mode=_current_mode,
        pending_consultations=pending,
        total_consultations=len(_consultations),
        accepted_consultations=accepted,
        rejected_consultations=rejected,
        available_scenarios=len(_preloaded_scenarios),
        llm_available=llm_available,
    )


@router.post("/set")
async def set_mode(mode: InteractionMode):
    """
    Set the interaction mode.

    Switches between LLM mode (full AI assistance) and No-LLM mode
    (pre-loaded scenarios only for reproducible research).
    """
    global _current_mode
    old_mode = _current_mode
    _current_mode = mode

    logger.info(f"Mode changed: {old_mode.value} -> {mode.value}")

    return {
        "status": "success",
        "previous_mode": old_mode.value,
        "current_mode": mode.value,
        "message": f"Mode set to {mode.value}",
    }


@router.get("/current")
async def get_current_mode():
    """Get the current interaction mode."""
    return {"mode": _current_mode.value}


# ===========================================================================
# Expert Consultation Endpoints
# ===========================================================================


@router.post("/expert-consultation", response_model=ExpertConsultationResponse)
async def request_expert_consultation(request: ExpertConsultationRequest):
    """
    Request expert AI consultation.

    This endpoint allows users in No-LLM mode to temporarily request
    AI assistance for specific questions. The response includes
    verification metadata and must be explicitly accepted or rejected.

    The consultation is recorded for research audit purposes.
    """
    import time
    start_time = time.perf_counter()

    consultation_id = str(uuid.uuid4())
    logger.info(f"[CONSULTATION] New request: {consultation_id} - {request.question[:50]}...")

    try:
        engine = get_llm_engine()

        # Create specialized system prompt for expert consultation
        system_prompt = """You are an IoT security expert assistant for the Smart Home Environment Simulator.

Your role is to provide accurate, well-sourced information about:
1. IoT security threats and vulnerabilities
2. Smart home device behavior and protocols
3. Attack detection and mitigation strategies
4. Cybersecurity research methodologies

IMPORTANT GUIDELINES:
- Always cite your sources using [Source N] notation
- If information is not in the knowledge base, clearly state this
- Provide actionable, specific guidance
- Acknowledge uncertainty when appropriate
- Focus on research integrity and reproducibility"""

        # Generate response with RAG
        result: InferenceResult = await engine.generate(
            prompt=f"[Expert Consultation Request]\n\nContext: {request.context}\n\nQuestion: {request.question}",
            system_prompt=system_prompt,
            session_id=request.session_id,
            use_rag=request.use_rag,
        )

        # Calculate confidence score
        confidence_score = _calculate_confidence_score(result.confidence)

        # Generate verification notes
        verification_notes = _generate_verification_notes(
            result.rag_context,
            result.confidence,
        )

        # Store consultation
        consultation = {
            "id": consultation_id,
            "question": request.question,
            "context": request.context,
            "response": result.content,
            "sources": result.sources,
            "confidence": result.confidence.value,
            "confidence_score": confidence_score,
            "status": ConsultationStatus.PENDING,
            "timestamp": datetime.utcnow(),
            "rag_context_count": len(result.rag_context.contexts) if result.rag_context else 0,
            "inference_time_ms": result.inference_time_ms,
            "verification_notes": verification_notes,
            "session_id": request.session_id,
        }
        _consultations[consultation_id] = consultation

        total_time = (time.perf_counter() - start_time) * 1000
        logger.info(f"[CONSULTATION] Completed in {total_time:.0f}ms, confidence: {result.confidence.value}")

        return ExpertConsultationResponse(**consultation)

    except ConnectionError as e:
        logger.error(f"[CONSULTATION] LLM unavailable: {e}")
        raise HTTPException(
            status_code=503,
            detail="LLM service unavailable. Please try again later or use pre-loaded scenarios.",
        )
    except Exception as e:
        logger.error(f"[CONSULTATION] Error: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Consultation failed: {str(e)}",
        )


@router.get("/expert-consultation/{consultation_id}", response_model=ExpertConsultationResponse)
async def get_consultation(consultation_id: str):
    """
    Get a specific consultation by ID.
    """
    if consultation_id not in _consultations:
        raise HTTPException(
            status_code=404,
            detail=f"Consultation not found: {consultation_id}",
        )

    return ExpertConsultationResponse(**_consultations[consultation_id])


@router.get("/expert-consultation", response_model=list[ExpertConsultationResponse])
async def list_consultations(
    status: Optional[ConsultationStatus] = None,
    limit: int = 50,
    offset: int = 0,
):
    """
    List all consultations with optional filtering.
    """
    consultations = list(_consultations.values())

    if status:
        consultations = [c for c in consultations if c["status"] == status]

    # Sort by timestamp descending
    consultations.sort(key=lambda x: x["timestamp"], reverse=True)

    # Apply pagination
    consultations = consultations[offset:offset + limit]

    return [ExpertConsultationResponse(**c) for c in consultations]


@router.post("/expert-consultation/{consultation_id}/feedback", response_model=ConsultationFeedbackResponse)
async def submit_consultation_feedback(consultation_id: str, feedback: ConsultationFeedback):
    """
    Submit feedback for a consultation (accept/reject).

    This records whether the user accepted or rejected the AI's response,
    along with any reasoning. This data is used for:
    - Research audit trails
    - Verification pipeline improvement
    - Anti-hallucination metrics
    """
    if consultation_id not in _consultations:
        raise HTTPException(
            status_code=404,
            detail=f"Consultation not found: {consultation_id}",
        )

    consultation = _consultations[consultation_id]

    # Update status
    new_status = ConsultationStatus.ACCEPTED if feedback.accepted else ConsultationStatus.REJECTED
    consultation["status"] = new_status
    consultation["feedback_reason"] = feedback.reason
    consultation["feedback_notes"] = feedback.notes
    consultation["feedback_timestamp"] = datetime.utcnow()

    logger.info(
        f"[CONSULTATION] Feedback recorded for {consultation_id}: "
        f"{'ACCEPTED' if feedback.accepted else 'REJECTED'}"
        f"{f' - {feedback.reason}' if feedback.reason else ''}"
    )

    return ConsultationFeedbackResponse(
        id=consultation_id,
        status=new_status,
        feedback_recorded=True,
        timestamp=datetime.utcnow(),
    )


# ===========================================================================
# Pre-loaded Scenario Endpoints
# ===========================================================================


@router.get("/scenarios", response_model=list[PreloadedScenario])
async def list_scenarios(
    category: Optional[str] = None,
    difficulty: Optional[str] = None,
    tag: Optional[str] = None,
):
    """
    List all available pre-loaded scenarios.

    Pre-loaded scenarios allow reproducible research without LLM involvement.
    """
    scenarios = list(_preloaded_scenarios.values())

    if category:
        scenarios = [s for s in scenarios if s.category == category]

    if difficulty:
        scenarios = [s for s in scenarios if s.difficulty == difficulty]

    if tag:
        scenarios = [s for s in scenarios if tag in s.tags]

    return scenarios


@router.get("/scenarios/categories")
async def get_scenario_categories():
    """Get all unique scenario categories."""
    categories = set(s.category for s in _preloaded_scenarios.values())
    return {"categories": sorted(categories)}


@router.get("/scenarios/tags")
async def get_scenario_tags():
    """Get all unique scenario tags."""
    tags = set()
    for scenario in _preloaded_scenarios.values():
        tags.update(scenario.tags)
    return {"tags": sorted(tags)}


@router.get("/scenarios/{scenario_id}", response_model=PreloadedScenario)
async def get_scenario(scenario_id: str):
    """Get a specific pre-loaded scenario."""
    if scenario_id not in _preloaded_scenarios:
        raise HTTPException(
            status_code=404,
            detail=f"Scenario not found: {scenario_id}",
        )

    return _preloaded_scenarios[scenario_id]


@router.post("/scenarios/{scenario_id}/execute", response_model=ScenarioExecutionResponse)
async def execute_scenario(scenario_id: str, request: Optional[ScenarioExecutionRequest] = None):
    """
    Execute a pre-loaded scenario.

    Creates the home configuration, sets up threats, and optionally
    starts the simulation based on the scenario parameters.

    This operation does NOT use LLM and is fully reproducible.
    """
    if scenario_id not in _preloaded_scenarios:
        raise HTTPException(
            status_code=404,
            detail=f"Scenario not found: {scenario_id}",
        )

    scenario = _preloaded_scenarios[scenario_id]
    execution_id = str(uuid.uuid4())

    logger.info(f"[SCENARIO] Executing scenario: {scenario.name} ({execution_id})")

    try:
        from src.simulation.home.home_generator import HomeGenerator, HomeTemplate

        home_id = None
        simulation_id = None
        results = {}

        # Create home if configured
        if scenario.home_config:
            generator = HomeGenerator()

            # Map template name to enum
            template_map = {
                "studio": HomeTemplate.STUDIO_APARTMENT,
                "one_bedroom": HomeTemplate.ONE_BEDROOM,
                "two_bedroom": HomeTemplate.TWO_BEDROOM,
                "three_bedroom": HomeTemplate.FAMILY_HOUSE,
                "family_house": HomeTemplate.FAMILY_HOUSE,
                "smart_mansion": HomeTemplate.SMART_MANSION,
            }

            template_name = scenario.home_config.get("template", "two_bedroom")
            template = template_map.get(template_name, HomeTemplate.TWO_BEDROOM)

            home = generator.generate_from_template(
                template=template,
                name=f"{scenario.name} - Home",
                num_inhabitants=scenario.home_config.get("num_inhabitants", 2),
            )
            home_id = home.id

            # Store for simulation
            import src.api.simulation as sim_module
            sim_module._current_home = home

            results["home"] = {
                "id": home.id,
                "name": home.name,
                "rooms": len(home.rooms),
                "devices": len(home.devices),
                "inhabitants": len(home.inhabitants),
            }

        # Set up threats if configured
        if scenario.threat_config:
            from src.simulation.threats.threat_catalog import ThreatCatalog, ThreatType
            ThreatCatalog.initialize()

            configured_threat_ids = scenario.threat_config.get("threats", [])
            threat_details = []

            # Map threat config IDs to actual ThreatType values
            threat_id_mapping = {
                # Shorthand names
                "botnet": ThreatType.BOTNET_RECRUITMENT,
                "ddos": ThreatType.DENIAL_OF_SERVICE,
                "traffic_analysis": ThreatType.DATA_EXFILTRATION,
                "mitm": ThreatType.MAN_IN_THE_MIDDLE,
                # Full names (matching ThreatType enum values)
                "botnet_recruitment": ThreatType.BOTNET_RECRUITMENT,
                "denial_of_service": ThreatType.DENIAL_OF_SERVICE,
                "credential_theft": ThreatType.CREDENTIAL_THEFT,
                "unauthorized_access": ThreatType.UNAUTHORIZED_ACCESS,
                "ransomware": ThreatType.RANSOMWARE,
                "data_exfiltration": ThreatType.DATA_EXFILTRATION,
                "energy_theft": ThreatType.ENERGY_THEFT,
                "device_tampering": ThreatType.DEVICE_TAMPERING,
                "surveillance": ThreatType.SURVEILLANCE,
                "man_in_the_middle": ThreatType.MAN_IN_THE_MIDDLE,
                "sensor_data_interception": ThreatType.SENSOR_DATA_INTERCEPTION,
                "firmware_modification": ThreatType.FIRMWARE_MODIFICATION,
                "jamming": ThreatType.JAMMING,
                "resource_exhaustion": ThreatType.RESOURCE_EXHAUSTION,
                "safety_system_bypass": ThreatType.SAFETY_SYSTEM_BYPASS,
                "hvac_manipulation": ThreatType.HVAC_MANIPULATION,
                "meter_tampering": ThreatType.METER_TAMPERING,
                "usage_falsification": ThreatType.USAGE_FALSIFICATION,
                "location_tracking": ThreatType.LOCATION_TRACKING,
                "behavior_profiling": ThreatType.BEHAVIOR_PROFILING,
                "dns_spoofing": ThreatType.DNS_SPOOFING,
                "arp_poisoning": ThreatType.ARP_POISONING,
            }

            for threat_id in configured_threat_ids:
                threat_type = threat_id_mapping.get(threat_id)
                if threat_type and threat_type in ThreatCatalog._threats:
                    threat_def = ThreatCatalog._threats[threat_type]
                    threat_details.append({
                        "id": threat_type.value,
                        "name": threat_def.name,
                        "description": threat_def.description,
                        "category": threat_def.category.value,
                        "severity": threat_def.severity.value,
                        "detection_difficulty": threat_def.detection_difficulty,
                        "typical_duration_minutes": threat_def.typical_duration_minutes,
                        "indicators": [ind.name for ind in threat_def.indicators],
                        "mitre_techniques": threat_def.mitre_techniques,
                    })

            results["threats"] = {
                "configured_threats": configured_threat_ids,
                "severity": scenario.threat_config.get("severity", "medium"),
                "threat_details": threat_details,
            }

        # Include simulation parameters
        if scenario.simulation_params:
            results["simulation_params"] = scenario.simulation_params

        logger.info(f"[SCENARIO] Execution complete: {execution_id}")

        return ScenarioExecutionResponse(
            execution_id=execution_id,
            scenario_id=scenario_id,
            scenario_name=scenario.name,
            status="ready",
            home_id=home_id,
            simulation_id=simulation_id,
            results=results,
            timestamp=datetime.utcnow(),
        )

    except Exception as e:
        logger.error(f"[SCENARIO] Execution failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Scenario execution failed: {str(e)}",
        )


# ===========================================================================
# Consultation Statistics
# ===========================================================================


@router.get("/statistics")
async def get_mode_statistics():
    """
    Get detailed statistics about consultations and mode usage.

    Useful for research audit and verification pipeline metrics.
    """
    total = len(_consultations)

    if total == 0:
        return {
            "total_consultations": 0,
            "acceptance_rate": None,
            "average_confidence": None,
            "confidence_distribution": {},
            "consultation_by_status": {},
        }

    accepted = sum(1 for c in _consultations.values() if c["status"] == ConsultationStatus.ACCEPTED)
    rejected = sum(1 for c in _consultations.values() if c["status"] == ConsultationStatus.REJECTED)
    pending = sum(1 for c in _consultations.values() if c["status"] == ConsultationStatus.PENDING)

    avg_confidence = sum(c["confidence_score"] for c in _consultations.values()) / total

    confidence_dist = {}
    for c in _consultations.values():
        conf = c["confidence"]
        confidence_dist[conf] = confidence_dist.get(conf, 0) + 1

    return {
        "total_consultations": total,
        "acceptance_rate": accepted / (accepted + rejected) if (accepted + rejected) > 0 else None,
        "average_confidence": round(avg_confidence, 3),
        "confidence_distribution": confidence_dist,
        "consultation_by_status": {
            "pending": pending,
            "accepted": accepted,
            "rejected": rejected,
        },
    }


# ===========================================================================
# Threat Catalog Endpoints
# ===========================================================================


@router.get("/threats")
async def get_available_threats():
    """
    Get all available threat definitions from the catalog.

    Returns threat definitions that can be used in scenarios.
    """
    from src.simulation.threats.threat_catalog import ThreatCatalog, ThreatType
    ThreatCatalog.initialize()

    threats = []
    for threat_type, threat_def in ThreatCatalog._threats.items():
        threats.append({
            "id": threat_type.value,
            "name": threat_def.name,
            "description": threat_def.description,
            "category": threat_def.category.value,
            "severity": threat_def.severity.value,
            "detection_difficulty": threat_def.detection_difficulty,
            "typical_duration_minutes": threat_def.typical_duration_minutes,
            "indicators": [
                {
                    "name": ind.name,
                    "description": ind.description,
                    "detection_method": ind.detection_method,
                }
                for ind in threat_def.indicators
            ],
            "mitre_techniques": threat_def.mitre_techniques,
            "target_device_types": [dt.value for dt in threat_def.target_device_types],
        })

    return {"threats": threats}


@router.get("/threats/{threat_id}")
async def get_threat_details(threat_id: str):
    """
    Get detailed information about a specific threat.
    """
    from src.simulation.threats.threat_catalog import ThreatCatalog, ThreatType
    ThreatCatalog.initialize()

    # Find the threat by ID
    try:
        threat_type = ThreatType(threat_id)
    except ValueError:
        raise HTTPException(
            status_code=404,
            detail=f"Threat not found: {threat_id}",
        )

    if threat_type not in ThreatCatalog._threats:
        raise HTTPException(
            status_code=404,
            detail=f"Threat not found: {threat_id}",
        )

    threat_def = ThreatCatalog._threats[threat_type]

    return {
        "id": threat_type.value,
        "name": threat_def.name,
        "description": threat_def.description,
        "category": threat_def.category.value,
        "severity": threat_def.severity.value,
        "detection_difficulty": threat_def.detection_difficulty,
        "typical_duration_minutes": threat_def.typical_duration_minutes,
        "requires_network_access": threat_def.requires_network_access,
        "requires_physical_access": threat_def.requires_physical_access,
        "evasion_techniques": threat_def.evasion_techniques,
        "data_impact": threat_def.data_impact,
        "availability_impact": threat_def.availability_impact,
        "integrity_impact": threat_def.integrity_impact,
        "safety_impact": threat_def.safety_impact,
        "financial_impact": threat_def.financial_impact,
        "indicators": [
            {
                "name": ind.name,
                "description": ind.description,
                "detection_method": ind.detection_method,
                "threshold": ind.threshold,
                "pattern": ind.pattern,
            }
            for ind in threat_def.indicators
        ],
        "mitre_techniques": threat_def.mitre_techniques,
        "references": threat_def.references,
        "target_device_types": [dt.value for dt in threat_def.target_device_types],
        "frequency": threat_def.frequency.value,
        "priority": threat_def.priority.value,
    }
