"""
Chat API Endpoints

Provides REST API for LLM chat interactions with RAG-augmented responses.
Supports both synchronous and streaming responses.
Integrates with Agent Orchestrator for actionable requests.
"""

import uuid
from datetime import datetime
from typing import Any, Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from loguru import logger

from src.ai.llm.llm_engine import (
    InferenceResult,
    ResponseConfidence,
    get_llm_engine,
)
from src.ai.orchestrator.orchestrator import get_orchestrator, AgentOrchestrator
from src.ai.orchestrator.task_decomposer import TASK_PATTERNS

router = APIRouter()


# ===========================================================================
# Request/Response Models
# ===========================================================================


class ChatRequest(BaseModel):
    """Request model for chat completion."""

    message: str = Field(..., description="User message")
    session_id: Optional[str] = Field(default=None, description="Session ID for conversation history")
    use_rag: bool = Field(default=True, description="Enable RAG for knowledge augmentation")
    temperature: Optional[float] = Field(default=None, ge=0.0, le=2.0, description="Sampling temperature")
    max_tokens: Optional[int] = Field(default=None, ge=1, le=4096, description="Maximum tokens")


class ChatSource(BaseModel):
    """Source citation in a response."""

    title: str
    source: str
    relevance: float


class ChatResponse(BaseModel):
    """Response model for chat completion."""

    message: str
    session_id: str
    model: str
    confidence: str
    sources: list[str]
    has_rag_context: bool
    inference_time_ms: float
    total_time_ms: float
    timestamp: datetime


class StreamChunk(BaseModel):
    """A single chunk in a streaming response."""

    content: str
    done: bool = False
    session_id: Optional[str] = None
    sources: list[str] = []


class ConversationMessage(BaseModel):
    """A message in conversation history."""

    role: str
    content: str
    timestamp: datetime


class ConversationHistory(BaseModel):
    """Conversation history for a session."""

    session_id: str
    messages: list[ConversationMessage]
    message_count: int


class EngineHealth(BaseModel):
    """LLM engine health status."""

    # Provider-agnostic fields (current active provider)
    provider: str  # Current active provider: "ollama", "openai", "gemini"
    provider_available: bool
    provider_message: str
    available_models: list[str]
    rag_enabled: bool
    knowledge_base_documents: int
    active_sessions: int

    # Legacy fields for backwards compatibility (deprecated)
    ollama_available: bool  # Deprecated: use provider_available
    ollama_message: str  # Deprecated: use provider_message


class ActionResult(BaseModel):
    """Result of an action executed by agents."""

    task_id: str
    task_type: str
    action: str
    success: bool
    data: Optional[dict] = None
    error: Optional[str] = None


class ActionableChatResponse(BaseModel):
    """Enhanced response model for actionable chat requests."""

    message: str
    session_id: str
    model: str
    confidence: str
    sources: list[str]
    has_rag_context: bool
    inference_time_ms: float
    total_time_ms: float
    timestamp: datetime
    # Action-specific fields
    is_actionable: bool = False
    action_type: Optional[str] = None
    action_results: list[ActionResult] = []
    created_resources: dict = {}  # e.g., {"home_id": "...", "simulation_id": "..."}


# ===========================================================================
# Helper Functions
# ===========================================================================


def is_actionable_request(message: str) -> tuple[bool, Optional[str]]:
    """
    Check if a message is an actionable request that should trigger agents.

    Uses priority-based matching to handle ambiguous requests like "build a threat"
    where both "build" (home) and "threat" (inject_threat) could match.

    Returns:
        (is_actionable, action_type)
    """
    message_lower = message.lower()

    # === COMPOSITE SCENARIO DETECTION ===
    # Check if message contains BOTH home AND threat indicators
    # This ensures "build scenario with home and threat to X" is detected as create_scenario
    home_indicators = ["home", "house", "apartment", "bedroom", "mansion", "studio", "room", "scenario"]
    threat_indicators = ["threat", "attack", "botnet", "malware", "hack", "exploit", "security", "vulnerability"]
    build_indicators = ["build", "create", "make", "generate", "set up", "setup"]
    # Device targets that indicate a threat scenario
    device_targets = ["camera", "lock", "thermostat", "sensor", "light", "speaker", "tv", "plug", "switch"]

    has_home_indicator = any(ind in message_lower for ind in home_indicators)
    has_threat_indicator = any(ind in message_lower for ind in threat_indicators)
    has_build_indicator = any(ind in message_lower for ind in build_indicators)
    has_device_target = any(dev in message_lower for dev in device_targets)

    # If message has build + home + threat indicators, it's a composite scenario
    # Also detect "threat to [device]" patterns as composite scenarios
    if has_build_indicator and has_home_indicator and has_threat_indicator:
        logger.debug(f"[ACTION] Composite scenario detected: home={has_home_indicator}, threat={has_threat_indicator}")
        return True, "create_scenario"

    # "threat to [device]" with a home/scenario context is also a composite scenario
    if has_build_indicator and has_home_indicator and has_device_target and "threat to" in message_lower:
        logger.debug(f"[ACTION] Composite scenario detected via 'threat to device': device_target={has_device_target}")
        return True, "create_scenario"

    # Priority order for action types (higher priority = checked first)
    # create_scenario must be first so "scenario with apartment and botnet" isn't captured by inject_threat
    priority_order = [
        "create_scenario",  # Highest: composite scenario (home + threat)
        "inject_threat",    # High: threat/attack/security keywords
        "run_simulation",   # Medium: simulation control
        "export_data",      # Medium: data export
        "create_home",      # Lower: home building (generic "build" keyword)
        "modify_home",      # Lower
        "add_device",       # Lower
        "remove_device",    # Lower
        "configure_device", # Lowest
    ]

    # Check each action type in priority order
    for task_name in priority_order:
        if task_name not in TASK_PATTERNS:
            continue
        pattern = TASK_PATTERNS[task_name]
        for keyword in pattern["keywords"]:
            if keyword in message_lower:
                return True, task_name

    # Check any remaining patterns not in priority list
    for task_name, pattern in TASK_PATTERNS.items():
        if task_name in priority_order:
            continue
        for keyword in pattern["keywords"]:
            if keyword in message_lower:
                return True, task_name

    return False, None


def extract_home_parameters(message: str) -> dict:
    """Extract home building parameters from natural language."""
    import random
    import re

    params = {
        "original_request": message,
    }
    message_lower = message.lower()

    # Extract home type with expanded keyword matching
    # Check for specific home types first (most specific to least specific)
    # Combined phrases first for accuracy
    if "small apartment" in message_lower or "tiny apartment" in message_lower:
        params["home_type"] = random.choice(["studio", "one_bedroom"])
    elif "large apartment" in message_lower or "big apartment" in message_lower:
        params["home_type"] = "two_bedroom"
    elif "small house" in message_lower or "tiny house" in message_lower:
        params["home_type"] = random.choice(["one_bedroom", "two_bedroom"])
    elif "large house" in message_lower or "big house" in message_lower:
        params["home_type"] = random.choice(["family_house", "smart_mansion"])
    elif "mansion" in message_lower or "luxury" in message_lower:
        params["home_type"] = "smart_mansion"
    elif "family home" in message_lower or "family house" in message_lower:
        params["home_type"] = "family_house"
    elif "3 bedroom" in message_lower or "three bedroom" in message_lower or "3-bedroom" in message_lower:
        params["home_type"] = "three_bedroom"
    elif "2 bedroom" in message_lower or "two bedroom" in message_lower or "2-bedroom" in message_lower:
        params["home_type"] = "two_bedroom"
    elif "1 bedroom" in message_lower or "one bedroom" in message_lower or "1-bedroom" in message_lower:
        params["home_type"] = "one_bedroom"
    elif "studio" in message_lower or "single room" in message_lower:
        params["home_type"] = "studio"
    elif "small" in message_lower or "tiny" in message_lower or "compact" in message_lower:
        # Small/tiny/compact -> pick between studio and one_bedroom
        params["home_type"] = random.choice(["studio", "one_bedroom"])
    elif "large" in message_lower or "big" in message_lower:
        # Large/big without specific type -> family house or mansion
        params["home_type"] = random.choice(["family_house", "smart_mansion"])
    elif "medium" in message_lower or "average" in message_lower or "typical" in message_lower:
        # Medium/average -> pick between one_bedroom and two_bedroom
        params["home_type"] = random.choice(["one_bedroom", "two_bedroom"])
    elif "apartment" in message_lower or "flat" in message_lower or "condo" in message_lower:
        # Apartment could be any size - pick randomly for variety
        params["home_type"] = random.choice(["studio", "one_bedroom", "two_bedroom"])
    elif "house" in message_lower:
        # House is typically larger
        params["home_type"] = random.choice(["two_bedroom", "three_bedroom", "family_house"])
    elif "home" in message_lower:
        # Generic "home" - pick any type for variety
        all_types = ["studio", "one_bedroom", "two_bedroom", "three_bedroom", "family_house"]
        params["home_type"] = random.choice(all_types)
    else:
        # No home type specified - pick randomly for variety in scenarios
        all_types = ["studio", "one_bedroom", "two_bedroom", "family_house"]
        params["home_type"] = random.choice(all_types)

    # Extract device count request
    device_match = re.search(r"(\d+)\s*device", message_lower)
    if device_match:
        params["target_device_count"] = int(device_match.group(1))
    elif "many devices" in message_lower or "lots of devices" in message_lower:
        params["target_device_count"] = random.randint(15, 25)
    elif "few devices" in message_lower or "minimal" in message_lower:
        params["target_device_count"] = random.randint(3, 6)

    # Extract inhabitant count
    inhabitant_match = re.search(r"(\d+)\s*(people|person|inhabitant|resident|family member)", message_lower)
    if inhabitant_match:
        params["inhabitant_count"] = int(inhabitant_match.group(1))
    else:
        # Default based on home type with some randomness
        inhabitant_defaults = {
            "studio": random.randint(1, 2),
            "one_bedroom": random.randint(1, 2),
            "two_bedroom": random.randint(2, 4),
            "three_bedroom": random.randint(3, 5),
            "family_house": random.randint(3, 6),
            "smart_mansion": random.randint(4, 8),
        }
        params["inhabitant_count"] = inhabitant_defaults.get(params["home_type"], 2)

    # Extract requirements
    params["requirements"] = message

    logger.debug(f"[HOME] Extracted params: type={params['home_type']}, inhabitants={params['inhabitant_count']}")

    return params


# ===========================================================================
# System Prompt
# ===========================================================================

SYSTEM_PROMPT = """You are Smart-HES Agent, an intelligent assistant for the Smart Home Environment Simulator.

Your role is to help users:
1. Configure smart home simulations with IoT devices
2. Understand IoT security threats and attack patterns
3. Generate synthetic datasets for cybersecurity research
4. Analyze simulation results and device behaviors

Guidelines:
- Be precise and technical when discussing IoT security
- Provide citations when using information from the knowledge base
- Admit when you don't have information about something
- Suggest relevant simulation configurations based on user goals
- Explain security concepts clearly for research purposes

You have access to a knowledge base containing IoT security research, CVE databases, MITRE ATT&CK patterns, and device specifications."""


# ===========================================================================
# Endpoints
# ===========================================================================


@router.post("/", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    Send a message and get a response.

    This endpoint provides non-streaming chat completion with full metadata.
    Use the /stream endpoint for real-time streaming responses.
    """
    engine = get_llm_engine()

    # Generate session ID if not provided
    session_id = request.session_id or str(uuid.uuid4())

    try:
        result: InferenceResult = await engine.generate(
            prompt=request.message,
            system_prompt=SYSTEM_PROMPT,
            session_id=session_id,
            use_rag=request.use_rag,
            temperature=request.temperature,
            max_tokens=request.max_tokens,
        )

        return ChatResponse(
            message=result.content,
            session_id=session_id,
            model=result.model,
            confidence=result.confidence.value,
            sources=result.sources,
            has_rag_context=result.rag_context is not None,
            inference_time_ms=result.inference_time_ms,
            total_time_ms=result.total_time_ms,
            timestamp=datetime.utcnow(),
        )

    except ConnectionError as e:
        raise HTTPException(
            status_code=503,
            detail=f"LLM service unavailable: {str(e)}",
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Chat generation failed: {str(e)}",
        )


@router.post("/stream")
async def chat_stream(request: ChatRequest):
    """
    Send a message and get a streaming response.

    Returns Server-Sent Events (SSE) with content chunks.
    Each chunk is a JSON object with 'content' and 'done' fields.
    """
    engine = get_llm_engine()

    # Generate session ID if not provided
    session_id = request.session_id or str(uuid.uuid4())

    async def generate():
        import json

        sources = []
        rag_context = None

        # Get RAG context once (used for both system prompt building AND sources extraction)
        # This avoids duplicate retrieval - previously RAG was called here AND inside generate_stream()
        if request.use_rag and engine.knowledge_base:
            rag_context = engine.knowledge_base.get_rag_context(request.message)
            sources = rag_context.sources if rag_context else []

        try:
            # Pass pre-computed rag_context to avoid duplicate retrieval
            async for chunk in engine.generate_stream(
                prompt=request.message,
                system_prompt=SYSTEM_PROMPT,
                session_id=session_id,
                use_rag=request.use_rag,
                rag_context=rag_context,  # Pass pre-computed context
                temperature=request.temperature,
                max_tokens=request.max_tokens,
            ):
                data = {
                    "content": chunk,
                    "done": False,
                    "session_id": session_id,
                }
                yield f"data: {json.dumps(data)}\n\n"

            # Send final chunk with sources
            final_data = {
                "content": "",
                "done": True,
                "session_id": session_id,
                "sources": sources,
            }
            yield f"data: {json.dumps(final_data)}\n\n"

        except ConnectionError as e:
            error_data = {
                "error": f"LLM service unavailable: {str(e)}",
                "done": True,
            }
            yield f"data: {json.dumps(error_data)}\n\n"
        except Exception as e:
            error_data = {
                "error": f"Stream generation failed: {str(e)}",
                "done": True,
            }
            yield f"data: {json.dumps(error_data)}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/history/{session_id}", response_model=ConversationHistory)
async def get_history(session_id: str):
    """
    Get conversation history for a session.

    Returns all messages in the conversation.
    """
    engine = get_llm_engine()
    messages = engine.get_conversation_history(session_id)

    if not messages:
        raise HTTPException(
            status_code=404,
            detail=f"No conversation found for session: {session_id}",
        )

    return ConversationHistory(
        session_id=session_id,
        messages=[
            ConversationMessage(
                role=msg.role,
                content=msg.content,
                timestamp=msg.timestamp,
            )
            for msg in messages
        ],
        message_count=len(messages),
    )


@router.delete("/history/{session_id}")
async def clear_history(session_id: str):
    """
    Clear conversation history for a session.

    This resets the conversation context.
    """
    engine = get_llm_engine()
    engine.clear_conversation(session_id)

    return {
        "status": "success",
        "message": f"Conversation history cleared for session: {session_id}",
    }


@router.get("/health", response_model=EngineHealth)
async def chat_health():
    """
    Check LLM engine health status.

    Returns information about current LLM provider availability, model status,
    and knowledge base statistics. Works with all providers (Ollama, OpenAI, Gemini).
    """
    engine = get_llm_engine()
    health = await engine.check_health()

    kb_doc_count = 0
    if health.get("knowledge_base"):
        kb_doc_count = health["knowledge_base"].get("document_count", 0)

    # Get provider info from health check
    provider = health.get("provider", "unknown")
    provider_available = health.get("provider_available", False)
    provider_message = health.get("provider_message", "Unknown")

    return EngineHealth(
        # Provider-agnostic fields
        provider=provider,
        provider_available=provider_available,
        provider_message=provider_message,
        available_models=health.get("available_models", []),
        rag_enabled=health.get("rag_enabled", False),
        knowledge_base_documents=kb_doc_count,
        active_sessions=health.get("active_sessions", 0),
        # Legacy fields (for backwards compatibility)
        ollama_available=provider_available,  # Maps to provider_available
        ollama_message=provider_message,  # Maps to provider_message
    )


# ===========================================================================
# Actionable Chat Endpoint (with Agent Orchestration)
# ===========================================================================


@router.post("/action", response_model=ActionableChatResponse)
async def chat_with_action(request: ChatRequest):
    """
    Send a message and execute actions if the request is actionable.

    This endpoint detects actionable requests like "Build a family home with 20 devices"
    and automatically triggers the appropriate agents to execute the task.

    Returns both a natural language response AND the results of any actions taken.
    """
    import time
    start_time = time.perf_counter()

    logger.info(f"[ACTION] Received request: {request.message[:100]}...")

    engine = get_llm_engine()
    session_id = request.session_id or str(uuid.uuid4())

    # Check if request is actionable
    actionable, action_type = is_actionable_request(request.message)
    logger.info(f"[ACTION] Actionable: {actionable}, Type: {action_type}")

    action_results = []
    created_resources = {}

    if actionable:
        logger.info(f"[ACTION] Executing action: {action_type}")

        try:
            # Handle based on action type
            if action_type == "create_home":
                logger.info("[ACTION] Starting home creation...")
                result = await _execute_create_home(request.message, engine)
                logger.info(f"[ACTION] Home creation result: success={result.get('success')}")
                action_results.append(ActionResult(
                    task_id=result.get("home_id", str(uuid.uuid4())),
                    task_type="home_builder",
                    action="create_home",
                    success=result.get("success", False),
                    data=result.get("data"),
                    error=result.get("error"),
                ))
                if result.get("success"):
                    created_resources["home"] = result.get("data", {})
                    logger.info(f"[ACTION] Home created with {result.get('data', {}).get('total_rooms', 0)} rooms")

            elif action_type == "run_simulation":
                result = await _execute_run_simulation(request.message)
                action_results.append(ActionResult(
                    task_id=result.get("simulation_id", str(uuid.uuid4())),
                    task_type="simulation_controller",
                    action="run_simulation",
                    success=result.get("success", False),
                    data=result.get("data"),
                    error=result.get("error"),
                ))
                if result.get("success"):
                    created_resources["simulation"] = result.get("data", {})

            elif action_type == "inject_threat":
                result = await _execute_inject_threat(request.message)
                action_results.append(ActionResult(
                    task_id=str(uuid.uuid4()),
                    task_type="threat_injector",
                    action="inject_threat",
                    success=result.get("success", False),
                    data=result.get("data"),
                    error=result.get("error"),
                ))

            elif action_type == "create_scenario":
                # Composite action: create home + threat + prepare simulation
                logger.info("[ACTION] Starting composite scenario creation...")
                scenario_result = await _execute_create_scenario(request.message, engine)

                # Add home result if created
                if scenario_result.get("home_result", {}).get("success"):
                    action_results.append(ActionResult(
                        task_id=scenario_result["home_result"].get("home_id", str(uuid.uuid4())),
                        task_type="home_builder",
                        action="create_home",
                        success=True,
                        data=scenario_result["home_result"].get("data"),
                    ))
                    created_resources["home"] = scenario_result["home_result"].get("data", {})

                # Add threat result if created
                if scenario_result.get("threat_result", {}).get("success"):
                    action_results.append(ActionResult(
                        task_id=scenario_result["threat_result"].get("threat_id", str(uuid.uuid4())),
                        task_type="threat_injector",
                        action="inject_threat",
                        success=True,
                        data=scenario_result["threat_result"].get("data"),
                    ))
                    created_resources["threat"] = scenario_result["threat_result"].get("data", {})

                # Add scenario metadata
                if scenario_result.get("success"):
                    created_resources["scenario"] = {
                        "scenario_id": scenario_result.get("scenario_id"),
                        "name": scenario_result.get("name"),
                        "ready_to_simulate": scenario_result.get("ready_to_simulate", False),
                    }
                    logger.info(f"[ACTION] Scenario created: {scenario_result.get('name')}")

        except Exception as e:
            logger.error(f"[ACTION] Action execution failed: {e}", exc_info=True)
            action_results.append(ActionResult(
                task_id=str(uuid.uuid4()),
                task_type=action_type or "unknown",
                action=action_type or "unknown",
                success=False,
                error=str(e),
            ))

    # Generate natural language response
    # If action was taken, include a summary of what was done
    if action_results and any(r.success for r in action_results):
        action_summary = _generate_action_summary(action_type, action_results, created_resources)
        prompt_with_context = f"""{request.message}

[SYSTEM NOTE: The following action was just executed successfully:
{action_summary}

Please acknowledge this action in your response and provide any relevant next steps or information.]"""
    else:
        prompt_with_context = request.message

    logger.info("[ACTION] Generating LLM response...")

    try:
        result: InferenceResult = await engine.generate(
            prompt=prompt_with_context,
            system_prompt=SYSTEM_PROMPT,
            session_id=session_id,
            use_rag=request.use_rag,
            temperature=request.temperature,
            max_tokens=request.max_tokens,
        )

        total_time = (time.perf_counter() - start_time) * 1000
        logger.info(f"[ACTION] LLM response generated in {total_time:.0f}ms")

        return ActionableChatResponse(
            message=result.content,
            session_id=session_id,
            model=result.model,
            confidence=result.confidence.value,
            sources=result.sources,
            has_rag_context=result.rag_context is not None,
            inference_time_ms=result.inference_time_ms,
            total_time_ms=total_time,
            timestamp=datetime.utcnow(),
            is_actionable=actionable,
            action_type=action_type,
            action_results=action_results,
            created_resources=created_resources,
        )

    except ConnectionError as e:
        logger.error(f"[ACTION] LLM connection error: {e}", exc_info=True)
        # If action was successful but LLM failed, still return a response
        # INTEGRITY: Use honest values - no fake model name or confidence
        if action_results and any(r.success for r in action_results):
            total_time = (time.perf_counter() - start_time) * 1000
            action_summary = _generate_action_summary(action_type, action_results, created_resources)
            return ActionableChatResponse(
                message=f"Action completed successfully! {action_summary}\n\n(Note: LLM response unavailable - connection error)",
                session_id=session_id,
                model="none",  # INTEGRITY: No LLM was used, be honest
                confidence="unknown",  # INTEGRITY: No LLM output to evaluate
                sources=[],
                has_rag_context=False,
                inference_time_ms=0,
                total_time_ms=total_time,
                timestamp=datetime.utcnow(),
                is_actionable=actionable,
                action_type=action_type,
                action_results=action_results,
                created_resources=created_resources,
            )
        raise HTTPException(
            status_code=503,
            detail=f"LLM service unavailable: {str(e)}",
        )
    except Exception as e:
        logger.error(f"[ACTION] Chat generation error: {e}", exc_info=True)
        # If action was successful but LLM failed, still return a response
        # INTEGRITY: Use honest values - no fake model name or confidence
        if action_results and any(r.success for r in action_results):
            total_time = (time.perf_counter() - start_time) * 1000
            action_summary = _generate_action_summary(action_type, action_results, created_resources)
            return ActionableChatResponse(
                message=f"Action completed successfully! {action_summary}\n\n(Note: LLM response unavailable due to error)",
                session_id=session_id,
                model="none",  # INTEGRITY: No LLM was used, be honest
                confidence="unknown",  # INTEGRITY: No LLM output to evaluate
                sources=[],
                has_rag_context=False,
                inference_time_ms=0,
                total_time_ms=total_time,
                timestamp=datetime.utcnow(),
                is_actionable=actionable,
                action_type=action_type,
                action_results=action_results,
                created_resources=created_resources,
            )
        raise HTTPException(
            status_code=500,
            detail=f"Chat generation failed: {str(e)}",
        )


# ===========================================================================
# Action Execution Helpers
# ===========================================================================


async def _execute_create_home(message: str, llm_engine) -> dict:
    """Execute home creation action."""
    from src.simulation.home.home_generator import HomeGenerator, HomeTemplate

    params = extract_home_parameters(message)
    logger.info(f"Creating home with params: {params}")

    try:
        # Map home type to template
        template_map = {
            "studio": HomeTemplate.STUDIO_APARTMENT,
            "one_bedroom": HomeTemplate.ONE_BEDROOM,
            "two_bedroom": HomeTemplate.TWO_BEDROOM,
            "three_bedroom": HomeTemplate.FAMILY_HOUSE,  # Map to family house
            "family_house": HomeTemplate.FAMILY_HOUSE,
            "smart_mansion": HomeTemplate.SMART_MANSION,
        }
        home_type = params.get("home_type", "two_bedroom")
        template = template_map.get(home_type, HomeTemplate.TWO_BEDROOM)
        logger.info(f"[HOME] Using template {template.name} for home type '{home_type}'")

        # Create home generator
        generator = HomeGenerator()

        # Generate home
        home = generator.generate_from_template(
            template=template,
            name=f"Generated Home - {params.get('home_type', 'Smart Home')}",
            num_inhabitants=params.get("inhabitant_count", 2),
        )

        # Adjust device count if requested
        target_devices = params.get("target_device_count")
        if target_devices:
            current_count = len(home.devices)
            if current_count < target_devices:
                # Add more devices to reach target
                generator._add_additional_devices(home, target_devices - current_count)

        # Convert to serializable format matching frontend CreatedHome interface
        # Group devices by room for easier frontend consumption
        devices_by_room = {}
        for d in home.devices:
            room_id = d.room_id
            if room_id not in devices_by_room:
                devices_by_room[room_id] = []
            devices_by_room[room_id].append({
                "id": d.id,
                "name": d.name,
                "device_type": d.device_type.value if hasattr(d.device_type, 'value') else str(d.device_type),
            })

        home_data = {
            "id": home.id,  # Frontend expects "id" not "home_id"
            "name": home.name,
            "rooms": [
                {
                    "id": r.id,  # Frontend expects "id" not "room_id"
                    "name": r.name,
                    "room_type": r.room_type.value if hasattr(r.room_type, 'value') else str(r.room_type),
                    "floor": getattr(r, 'floor', 0),  # Include floor if available
                    "devices": devices_by_room.get(r.id, []),  # Include devices for this room
                }
                for r in home.rooms
            ],
            "inhabitants": [
                {
                    "id": i.id,  # Frontend expects "id" not "inhabitant_id"
                    "name": i.name,
                    "role": i.inhabitant_type.value if hasattr(i.inhabitant_type, 'value') else str(i.inhabitant_type),  # Frontend expects "role"
                }
                for i in home.inhabitants
            ],
            # Frontend expects these at top level, not in "stats"
            "total_rooms": len(home.rooms),
            "total_devices": len(home.devices),
            "total_inhabitants": len(home.inhabitants),
        }

        # Store the home in the simulation service for later use
        import src.api.simulation as sim_module
        sim_module._current_home = home

        return {
            "success": True,
            "home_id": home.id,
            "data": home_data,
        }

    except Exception as e:
        logger.error(f"Home creation failed: {e}")
        return {
            "success": False,
            "error": str(e),
        }


async def _execute_run_simulation(message: str) -> dict:
    """Execute simulation start action."""
    from src.api.simulation import _current_home, _simulation_engine
    import src.api.simulation as sim_module

    try:
        if sim_module._current_home is None:
            return {
                "success": False,
                "error": "No home configured. Please create a home first.",
            }

        # Start simulation
        if sim_module._simulation_engine is None:
            from src.simulation.engine import SimulationEngine
            sim_module._simulation_engine = SimulationEngine(sim_module._current_home)

        await sim_module._simulation_engine.start()

        return {
            "success": True,
            "simulation_id": sim_module._simulation_engine.simulation_id,
            "data": {
                "status": "running",
                "home_id": sim_module._current_home.home_id,
            },
        }

    except Exception as e:
        logger.error(f"Simulation start failed: {e}")
        return {
            "success": False,
            "error": str(e),
        }


def extract_threat_parameters(message: str) -> dict:
    """Extract threat parameters from natural language, including count and multiple threat types."""
    import re
    import random

    params = {
        "original_request": message,
    }
    message_lower = message.lower()

    # Extract threat count from message
    count_patterns = [
        r"(\d+)\s*(?:attacks?|threats?)",  # "3 attacks", "5 threats"
        r"(\d+)\s*(?:different|various|multiple)",  # "3 different", "5 various"
        r"(?:with|include|includes|including)\s*(\d+)",  # "with 3", "includes 5"
    ]
    threat_count = 1  # default
    for pattern in count_patterns:
        match = re.search(pattern, message_lower)
        if match:
            threat_count = min(int(match.group(1)), 10)  # Cap at 10
            break

    # Check for keywords indicating multiple threats
    if threat_count == 1:
        if "multiple" in message_lower or "several" in message_lower or "various" in message_lower:
            threat_count = random.randint(2, 4)
        elif "few" in message_lower:
            threat_count = random.randint(2, 3)
        elif "many" in message_lower or "lots" in message_lower:
            threat_count = random.randint(4, 6)

    # Check for "frequent" or "common" which implies variety
    if "frequent" in message_lower or "common" in message_lower or "occurring" in message_lower:
        if threat_count == 1:
            threat_count = 3  # Default to 3 for "frequently occurring"
        params["use_common_threats"] = True

    params["threat_count"] = threat_count

    # Map keywords to threat types
    threat_type_keywords = {
        "data_exfiltration": ["data exfiltration", "steal data", "exfiltrate", "data theft"],
        "credential_theft": ["credential", "password", "login theft"],
        "device_tampering": ["tamper", "modify device", "device tampering"],
        "botnet_recruitment": ["botnet", "recruit", "ddos"],
        "ransomware": ["ransomware", "encrypt", "ransom"],
        "denial_of_service": ["dos", "denial of service", "flood", "ddos attack"],
        "unauthorized_access": ["unauthorized access", "break in", "unlock"],
        "surveillance": ["surveillance", "spy", "monitor", "watch", "camera"],
        "man_in_the_middle": ["mitm", "man in the middle", "intercept"],
        "energy_theft": ["energy theft", "meter tampering", "electricity theft"],
    }

    # Find ALL matching threat types
    detected_threats = []
    for threat_type, keywords in threat_type_keywords.items():
        for keyword in keywords:
            if keyword in message_lower:
                if threat_type not in detected_threats:
                    detected_threats.append(threat_type)
                break

    # If no specific threats detected but threat-related keywords present
    if not detected_threats:
        general_threat_words = ["threat", "attack", "malicious", "hack", "exploit", "vulnerability"]
        if any(word in message_lower for word in general_threat_words):
            # Use common/frequent threats for variety
            common_threats = [
                "data_exfiltration",
                "botnet_recruitment",
                "unauthorized_access",
                "surveillance",
                "credential_theft",
                "man_in_the_middle",
            ]
            detected_threats = random.sample(common_threats, min(threat_count, len(common_threats)))

    # Store detected threats
    params["threat_types"] = detected_threats if detected_threats else None
    params["threat_type"] = detected_threats[0] if detected_threats else None

    # Extract severity
    if "critical" in message_lower or "severe" in message_lower:
        params["severity"] = "critical"
    elif "high" in message_lower or "serious" in message_lower:
        params["severity"] = "high"
    elif "low" in message_lower or "minor" in message_lower:
        params["severity"] = "low"
    else:
        params["severity"] = "medium"

    logger.debug(f"[THREAT] Extracted params: count={threat_count}, types={detected_threats}, severity={params['severity']}")

    return params


async def _execute_inject_threat(message: str) -> dict:
    """Execute threat injection action - creates one or more threat scenarios."""
    import random
    import uuid

    from src.simulation.threats.threat_catalog import (
        ThreatCatalog,
        ThreatType,
    )

    params = extract_threat_parameters(message)
    threat_count = params.get("threat_count", 1)
    logger.info(f"[ACTION] Creating {threat_count} threat(s) with params: {params}")

    try:
        # Initialize catalog if needed
        ThreatCatalog.initialize()

        # Map string to ThreatType enum
        threat_type_map = {
            "data_exfiltration": ThreatType.DATA_EXFILTRATION,
            "credential_theft": ThreatType.CREDENTIAL_THEFT,
            "device_tampering": ThreatType.DEVICE_TAMPERING,
            "botnet_recruitment": ThreatType.BOTNET_RECRUITMENT,
            "ransomware": ThreatType.RANSOMWARE,
            "denial_of_service": ThreatType.DENIAL_OF_SERVICE,
            "unauthorized_access": ThreatType.UNAUTHORIZED_ACCESS,
            "surveillance": ThreatType.SURVEILLANCE,
            "man_in_the_middle": ThreatType.MAN_IN_THE_MIDDLE,
            "energy_theft": ThreatType.ENERGY_THEFT,
        }

        # Get threat types to create
        threat_types_to_create = params.get("threat_types") or []

        # If we need more threats than specified, pick random common ones
        if len(threat_types_to_create) < threat_count:
            all_threat_types = list(threat_type_map.keys())
            # Remove already selected ones
            available = [t for t in all_threat_types if t not in threat_types_to_create]
            # Add random threats to reach the count
            needed = threat_count - len(threat_types_to_create)
            if needed > 0 and available:
                additional = random.sample(available, min(needed, len(available)))
                threat_types_to_create.extend(additional)

        # If still no threats, return available list
        if not threat_types_to_create:
            all_threats = ThreatCatalog.get_all_threats()
            threat_list = [
                {
                    "type": t.threat_type.value,
                    "name": t.name,
                    "category": t.category.value,
                    "severity": t.severity.value,
                    "description": t.description[:100] + "..." if len(t.description) > 100 else t.description,
                }
                for t in all_threats
            ]
            return {
                "success": True,
                "data": {
                    "message": "No specific threat type detected. Here are available threats:",
                    "available_threats": threat_list,
                    "total_threats": len(threat_list),
                },
            }

        # Create multiple threats
        created_threats = []
        primary_threat_data = None

        for i, threat_type_str in enumerate(threat_types_to_create[:threat_count]):
            threat_type = threat_type_map.get(threat_type_str)
            if not threat_type:
                logger.warning(f"[ACTION] Unknown threat type: {threat_type_str}, skipping")
                continue

            # Get threat definition from catalog
            threat_def = ThreatCatalog.get_threat(threat_type)
            if not threat_def:
                logger.warning(f"[ACTION] Threat definition not found for: {threat_type_str}, skipping")
                continue

            threat_id = str(uuid.uuid4())

            threat_data = {
                "id": threat_id,
                "threat_type": threat_def.threat_type.value,
                "name": threat_def.name,
                "category": threat_def.category.value,
                "severity": params.get("severity", threat_def.severity.value),
                "description": threat_def.description,
                "target_device_types": [dt.value for dt in threat_def.target_device_types],
                "requires_network_access": threat_def.requires_network_access,
                "requires_physical_access": threat_def.requires_physical_access,
                "detection_difficulty": threat_def.detection_difficulty,
                "impacts": {
                    "data": threat_def.data_impact,
                    "availability": threat_def.availability_impact,
                    "integrity": threat_def.integrity_impact,
                    "safety": threat_def.safety_impact,
                    "financial": threat_def.financial_impact,
                },
                "indicators": [
                    {
                        "name": ind.name,
                        "description": ind.description,
                        "detection_method": ind.detection_method,
                    }
                    for ind in threat_def.indicators
                ],
                "mitre_techniques": threat_def.mitre_techniques,
                "evasion_techniques": threat_def.evasion_techniques,
            }

            created_threats.append(threat_data)
            logger.info(f"[ACTION] Created threat {i+1}/{threat_count}: {threat_def.name} ({threat_id})")

            # Store first as primary for backwards compatibility
            if primary_threat_data is None:
                primary_threat_data = threat_data

        if not created_threats:
            return {
                "success": False,
                "error": "No valid threats could be created",
            }

        # Return data with all threats
        # Primary threat data for backwards compatibility, plus all_threats array
        result_data = primary_threat_data.copy()
        result_data["all_threats"] = created_threats
        result_data["threat_count"] = len(created_threats)

        # Update name to reflect multiple threats
        if len(created_threats) > 1:
            threat_names = [t["name"] for t in created_threats[:3]]
            if len(created_threats) > 3:
                result_data["name"] = f"{', '.join(threat_names)}, +{len(created_threats)-3} more"
            else:
                result_data["name"] = ", ".join(threat_names)

        logger.info(f"[ACTION] Created {len(created_threats)} threat scenario(s)")

        return {
            "success": True,
            "threat_id": primary_threat_data["id"],
            "data": result_data,
        }

    except Exception as e:
        logger.error(f"[ACTION] Threat creation failed: {e}", exc_info=True)
        return {
            "success": False,
            "error": str(e),
        }


async def _execute_create_scenario(message: str, llm_engine) -> dict:
    """
    Execute composite scenario creation: home + threat + simulation ready.

    This handles requests like "create a scenario with small apartment and botnet attack"
    by creating both the home and threat configuration together.
    """
    import uuid as uuid_mod

    logger.info(f"[ACTION] Creating composite scenario from: {message[:100]}...")

    scenario_id = str(uuid_mod.uuid4())
    result = {
        "success": False,
        "scenario_id": scenario_id,
        "name": "Custom Scenario",
        "home_result": None,
        "threat_result": None,
        "ready_to_simulate": False,
    }

    try:
        # Step 1: Create the home
        logger.info("[ACTION] Step 1: Creating home for scenario...")
        home_result = await _execute_create_home(message, llm_engine)
        result["home_result"] = home_result

        if not home_result.get("success"):
            logger.warning(f"[ACTION] Home creation failed: {home_result.get('error')}")
            # Continue anyway - threat can still be created
        else:
            home_name = home_result.get("data", {}).get("name", "Smart Home")
            logger.info(f"[ACTION] Home created: {home_name}")

        # Step 2: Create the threat
        logger.info("[ACTION] Step 2: Creating threat for scenario...")
        threat_result = await _execute_inject_threat(message)
        result["threat_result"] = threat_result

        if not threat_result.get("success"):
            logger.warning(f"[ACTION] Threat creation failed: {threat_result.get('error')}")
        else:
            threat_name = threat_result.get("data", {}).get("name", "Security Threat")
            logger.info(f"[ACTION] Threat created: {threat_name}")

        # Generate scenario name from components
        home_type = "Home"
        threat_type = "Threat"

        if home_result.get("success"):
            home_data = home_result.get("data", {})
            home_type = home_data.get("name", "Smart Home").replace("Generated Home - ", "")

        if threat_result.get("success"):
            threat_data = threat_result.get("data", {})
            threat_type = threat_data.get("name", "Security Threat")

        result["name"] = f"{home_type} + {threat_type}"

        # Determine overall success
        # Success if at least one component was created
        result["success"] = (
            home_result.get("success", False) or
            threat_result.get("success", False)
        )

        # Ready to simulate if both home and threat are created
        result["ready_to_simulate"] = (
            home_result.get("success", False) and
            threat_result.get("success", False)
        )

        logger.info(
            f"[ACTION] Scenario '{result['name']}' created. "
            f"Home: {home_result.get('success')}, "
            f"Threat: {threat_result.get('success')}, "
            f"Ready: {result['ready_to_simulate']}"
        )

        return result

    except Exception as e:
        logger.error(f"[ACTION] Scenario creation failed: {e}", exc_info=True)
        result["error"] = str(e)
        return result


def _generate_action_summary(action_type: str, results: list[ActionResult], resources: dict) -> str:
    """Generate a human-readable summary of actions taken."""
    summaries = []

    for result in results:
        if result.success:
            if result.action == "create_home" and "home" in resources:
                home = resources["home"]
                room_list = ", ".join([r.get("name", "Room") for r in home.get("rooms", [])[:5]])
                if len(home.get("rooms", [])) > 5:
                    room_list += f", and {len(home.get('rooms', [])) - 5} more"
                summaries.append(
                    f"Successfully created smart home **'{home.get('name', 'Unknown')}'**!\n\n"
                    f"**Configuration:**\n"
                    f"- Rooms: {home.get('total_rooms', 0)} ({room_list})\n"
                    f"- Smart Devices: {home.get('total_devices', 0)}\n"
                    f"- Inhabitants: {home.get('total_inhabitants', 0)}\n\n"
                    f"You can view and modify this home in the **Home Builder** section."
                )
            elif result.action == "run_simulation":
                summaries.append("Started the simulation successfully.")
            elif result.action == "inject_threat" and result.data:
                threat_data = result.data
                if "available_threats" in threat_data:
                    # List available threats
                    threat_list = threat_data.get("available_threats", [])
                    threat_names = [t.get("name", "Unknown") for t in threat_list[:8]]
                    summaries.append(
                        f"**{threat_data.get('total_threats', 0)} Threat Scenarios Available:**\n\n"
                        f"- " + "\n- ".join(threat_names) +
                        (f"\n- ...and {len(threat_list) - 8} more" if len(threat_list) > 8 else "") +
                        "\n\nTo create a specific threat, try:\n"
                        "- 'Create a data exfiltration threat'\n"
                        "- 'Build a botnet attack scenario'\n"
                        "- 'Inject a high severity surveillance threat'"
                    )
                else:
                    # Specific threat was created
                    target_devices = threat_data.get("target_device_types", [])
                    targets_str = ", ".join(target_devices[:3]) if target_devices else "various devices"
                    if len(target_devices) > 3:
                        targets_str += f", +{len(target_devices) - 3} more"

                    mitre_techniques = threat_data.get("mitre_techniques", [])
                    mitre_str = ", ".join(mitre_techniques[:3]) if mitre_techniques else "N/A"

                    summaries.append(
                        f"Successfully created threat scenario **'{threat_data.get('name', 'Unknown')}'**!\n\n"
                        f"**Threat Details:**\n"
                        f"- Category: {threat_data.get('category', 'unknown').replace('_', ' ').title()}\n"
                        f"- Severity: **{threat_data.get('severity', 'unknown').upper()}**\n"
                        f"- Target Devices: {targets_str}\n"
                        f"- Detection Difficulty: {threat_data.get('detection_difficulty', 'unknown')}\n"
                        f"- MITRE ATT&CK: {mitre_str}\n\n"
                        f"**Description:**\n{threat_data.get('description', 'No description available.')}\n\n"
                        f"You can view and configure this threat in the **Threat Builder** section."
                    )
            else:
                summaries.append(f"Completed action: {result.action}")
        else:
            summaries.append(f"Failed to execute {result.action}: {result.error}")

    # Add scenario-level summary if this was a composite scenario creation
    if "scenario" in resources:
        scenario = resources["scenario"]
        scenario_name = scenario.get("name", "Custom Scenario")
        ready = scenario.get("ready_to_simulate", False)

        # Build combined summary for scenario
        scenario_summary = f"\n---\n\n**Scenario: '{scenario_name}'**\n\n"

        if "home" in resources and "threat" in resources:
            home = resources["home"]
            threat = resources["threat"]
            scenario_summary += (
                f"**Home Configuration:**\n"
                f"- Name: {home.get('name', 'Smart Home')}\n"
                f"- Rooms: {home.get('total_rooms', 0)}\n"
                f"- Devices: {home.get('total_devices', 0)}\n"
                f"- Inhabitants: {home.get('total_inhabitants', 0)}\n\n"
                f"**Threat Configuration:**\n"
                f"- Type: {threat.get('name', 'Unknown')}\n"
                f"- Severity: {threat.get('severity', 'medium').upper()}\n"
                f"- Category: {threat.get('category', 'unknown').replace('_', ' ').title()}\n\n"
            )

        if ready:
            scenario_summary += (
                "**Status: Ready to Simulate!**\n\n"
                "You can now:\n"
                "1. Start the simulation from the **Simulation** view\n"
                "2. Modify settings in **Home Builder** or **Threat Builder**\n"
                "3. Ask me to 'run the simulation' or 'start the scenario'"
            )
        else:
            scenario_summary += (
                "**Status: Partially Configured**\n\n"
                "Some components may need additional configuration before simulation."
            )

        summaries.append(scenario_summary)

    return "\n".join(summaries) if summaries else "No actions completed."
