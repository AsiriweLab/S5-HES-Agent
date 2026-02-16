"""
Conversation Manager for the Smart-HES Agent Framework.

Manages conversational AI interactions with users, including:
- Session management
- Conversation history
- Context injection
- Agent coordination for user requests
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, AsyncGenerator, Optional
from uuid import uuid4

from loguru import logger

from src.ai.llm.llm_engine import LLMEngine, InferenceResult, get_llm_engine
from src.ai.llm.prompts import get_prompt_manager
from src.ai.orchestrator import AgentOrchestrator, get_orchestrator


@dataclass
class ConversationTurn:
    """A single turn in a conversation."""
    turn_id: str
    role: str  # "user" or "assistant"
    content: str
    timestamp: datetime = field(default_factory=datetime.utcnow)
    metadata: dict = field(default_factory=dict)
    inference_result: Optional[InferenceResult] = None


@dataclass
class ConversationSession:
    """A conversation session with a user."""
    session_id: str
    created_at: datetime = field(default_factory=datetime.utcnow)
    last_activity: datetime = field(default_factory=datetime.utcnow)
    turns: list[ConversationTurn] = field(default_factory=list)
    context: dict = field(default_factory=dict)  # Session context (current home, etc.)
    metadata: dict = field(default_factory=dict)

    def add_turn(
        self,
        role: str,
        content: str,
        inference_result: Optional[InferenceResult] = None,
    ) -> ConversationTurn:
        """Add a turn to the conversation."""
        turn = ConversationTurn(
            turn_id=str(uuid4()),
            role=role,
            content=content,
            inference_result=inference_result,
        )
        self.turns.append(turn)
        self.last_activity = datetime.utcnow()
        return turn

    def get_history_for_prompt(self, max_turns: int = 10) -> str:
        """Get formatted conversation history for prompt context."""
        recent_turns = self.turns[-max_turns:]
        formatted = []

        for turn in recent_turns:
            formatted.append(f"{turn.role.upper()}: {turn.content}")

        return "\n".join(formatted)

    def get_context_summary(self) -> str:
        """Get a summary of the current session context."""
        parts = []

        if "current_home" in self.context:
            home = self.context["current_home"]
            parts.append(f"Current home: {home.get('name', 'Unnamed')}")
            parts.append(f"  - Rooms: {home.get('room_count', 'unknown')}")
            parts.append(f"  - Devices: {home.get('device_count', 'unknown')}")

        if "active_simulation" in self.context:
            parts.append("Active simulation running")

        if "active_threats" in self.context:
            threats = self.context["active_threats"]
            parts.append(f"Active threats: {len(threats)}")

        return "\n".join(parts) if parts else "No context set"


class ConversationManager:
    """
    Manages conversational AI interactions.

    Features:
    - Multi-session support
    - Context-aware responses
    - Integration with agent orchestrator
    - Streaming responses
    - Conversation history management
    """

    def __init__(
        self,
        llm_engine: Optional[LLMEngine] = None,
        orchestrator: Optional[AgentOrchestrator] = None,
        max_history_turns: int = 20,
    ):
        self.llm_engine = llm_engine or get_llm_engine()
        self.orchestrator = orchestrator or get_orchestrator()
        self.prompt_manager = get_prompt_manager()
        self.max_history_turns = max_history_turns

        # Active sessions
        self._sessions: dict[str, ConversationSession] = {}

        # Session timeout (30 minutes)
        self._session_timeout_seconds = 1800

        logger.info("ConversationManager initialized")

    def create_session(self, metadata: dict = None) -> ConversationSession:
        """Create a new conversation session."""
        session = ConversationSession(
            session_id=str(uuid4()),
            metadata=metadata or {},
        )
        self._sessions[session.session_id] = session
        logger.info(f"Created conversation session: {session.session_id}")
        return session

    def get_session(self, session_id: str) -> Optional[ConversationSession]:
        """Get an existing session."""
        session = self._sessions.get(session_id)
        if session:
            # Check if expired
            age = (datetime.utcnow() - session.last_activity).total_seconds()
            if age > self._session_timeout_seconds:
                logger.info(f"Session expired: {session_id}")
                del self._sessions[session_id]
                return None
        return session

    def get_or_create_session(self, session_id: str = None) -> ConversationSession:
        """Get an existing session or create a new one."""
        if session_id:
            session = self.get_session(session_id)
            if session:
                return session

        return self.create_session()

    async def chat(
        self,
        user_message: str,
        session_id: str = None,
        use_orchestrator: bool = True,
    ) -> dict:
        """
        Process a user message and generate a response.

        Args:
            user_message: The user's message
            session_id: Optional session ID
            use_orchestrator: Whether to use the agent orchestrator for complex tasks

        Returns:
            Response dict with content and metadata
        """
        # Get or create session
        session = self.get_or_create_session(session_id)

        # Add user turn
        session.add_turn("user", user_message)

        # Build context-aware system prompt
        system_prompt = self._build_conversation_prompt(session)

        # Check if this is an actionable request
        if use_orchestrator and self._is_actionable_request(user_message):
            # Use orchestrator for complex tasks
            result = await self._handle_with_orchestrator(user_message, session)
        else:
            # Simple conversational response
            result = await self.llm_engine.generate(
                prompt=user_message,
                system_prompt=system_prompt,
                session_id=session.session_id,
                use_rag=True,
            )

        # Add assistant turn
        session.add_turn(
            "assistant",
            result.content if hasattr(result, 'content') else str(result),
            inference_result=result if isinstance(result, InferenceResult) else None,
        )

        return {
            "session_id": session.session_id,
            "response": result.content if hasattr(result, 'content') else str(result),
            "confidence": result.confidence.value if hasattr(result, 'confidence') else "unknown",
            "sources": result.sources if hasattr(result, 'sources') else [],
            "context": session.get_context_summary(),
            "turn_count": len(session.turns),
        }

    async def chat_stream(
        self,
        user_message: str,
        session_id: str = None,
    ) -> AsyncGenerator[str, None]:
        """
        Process a user message with streaming response.

        Args:
            user_message: The user's message
            session_id: Optional session ID

        Yields:
            Response chunks
        """
        session = self.get_or_create_session(session_id)
        session.add_turn("user", user_message)

        system_prompt = self._build_conversation_prompt(session)

        full_response = []
        async for chunk in self.llm_engine.generate_stream(
            prompt=user_message,
            system_prompt=system_prompt,
            session_id=session.session_id,
        ):
            full_response.append(chunk)
            yield chunk

        # Add assistant turn after streaming completes
        session.add_turn("assistant", "".join(full_response))

    def update_context(self, session_id: str, context_update: dict) -> bool:
        """Update the context for a session."""
        session = self.get_session(session_id)
        if not session:
            return False

        session.context.update(context_update)
        return True

    def clear_session(self, session_id: str) -> bool:
        """Clear a session."""
        if session_id in self._sessions:
            del self._sessions[session_id]
            return True
        return False

    def get_session_summary(self, session_id: str) -> Optional[dict]:
        """Get a summary of a session."""
        session = self.get_session(session_id)
        if not session:
            return None

        return {
            "session_id": session.session_id,
            "created_at": session.created_at.isoformat(),
            "last_activity": session.last_activity.isoformat(),
            "turn_count": len(session.turns),
            "context": session.context,
            "recent_topics": self._extract_topics(session),
        }

    def get_active_sessions(self) -> list[dict]:
        """Get all active sessions."""
        # Clean up expired sessions first
        self._cleanup_expired_sessions()

        return [
            {
                "session_id": s.session_id,
                "created_at": s.created_at.isoformat(),
                "turn_count": len(s.turns),
            }
            for s in self._sessions.values()
        ]

    def _build_conversation_prompt(self, session: ConversationSession) -> str:
        """Build a context-aware system prompt."""
        base_prompt = self.prompt_manager.get_agent_prompt("conversation")

        # Add session context
        context_summary = session.get_context_summary()
        if context_summary:
            base_prompt += f"\n\n## Current Session Context\n{context_summary}"

        # Add conversation history summary
        if len(session.turns) > 2:
            history = session.get_history_for_prompt(max_turns=5)
            base_prompt += f"\n\n## Recent Conversation\n{history}"

        return base_prompt

    def _is_actionable_request(self, message: str) -> bool:
        """Check if a message contains an actionable request."""
        action_keywords = [
            "create", "build", "generate", "make",
            "add", "remove", "delete",
            "configure", "set up", "change",
            "simulate", "run", "start", "stop",
            "inject", "attack", "threat",
            "export", "save", "download",
        ]

        message_lower = message.lower()
        return any(kw in message_lower for kw in action_keywords)

    async def _handle_with_orchestrator(
        self,
        message: str,
        session: ConversationSession,
    ) -> Any:
        """Handle an actionable request using the orchestrator."""
        try:
            # Process through orchestrator
            exec_context = await self.orchestrator.process_request(
                user_request=message,
                use_llm_decomposition=True,
                llm_engine=self.llm_engine,
                context=session.context,
            )

            # Format response based on results
            if exec_context.status == "completed":
                aggregated = exec_context.results.get("_aggregated", {})
                summary = aggregated.get("summary", {})

                response = f"I've processed your request. "
                response += f"Completed {summary.get('successful_tasks', 0)} out of "
                response += f"{summary.get('total_tasks', 0)} tasks successfully."

                # Add details from individual tasks
                for task_result in aggregated.get("task_results", []):
                    if task_result.get("success") and task_result.get("data"):
                        data = task_result["data"]
                        if isinstance(data, dict) and "response" in data:
                            response += f"\n\n{data['response']}"

                return InferenceResult(
                    content=response,
                    model="orchestrator",
                    confidence=self.llm_engine._calculate_confidence(None, response),
                )
            else:
                error_msg = exec_context.error or "Unknown error occurred"
                return InferenceResult(
                    content=f"I encountered an issue processing your request: {error_msg}",
                    model="orchestrator",
                    confidence=self.llm_engine._calculate_confidence(None, ""),
                )

        except Exception as e:
            logger.error(f"Orchestrator handling failed: {e}")
            # Fall back to direct LLM response
            return await self.llm_engine.generate(
                prompt=message,
                system_prompt=self._build_conversation_prompt(session),
            )

    def _extract_topics(self, session: ConversationSession) -> list[str]:
        """Extract main topics from conversation."""
        topics = set()
        topic_keywords = {
            "home": ["home", "house", "room", "layout"],
            "devices": ["device", "sensor", "camera", "lock", "light"],
            "security": ["threat", "attack", "security", "vulnerability"],
            "simulation": ["simulate", "run", "test"],
        }

        for turn in session.turns:
            content_lower = turn.content.lower()
            for topic, keywords in topic_keywords.items():
                if any(kw in content_lower for kw in keywords):
                    topics.add(topic)

        return list(topics)

    def _cleanup_expired_sessions(self) -> int:
        """Remove expired sessions."""
        now = datetime.utcnow()
        expired = []

        for session_id, session in self._sessions.items():
            age = (now - session.last_activity).total_seconds()
            if age > self._session_timeout_seconds:
                expired.append(session_id)

        for session_id in expired:
            del self._sessions[session_id]

        return len(expired)


# Global instance
_conversation_manager: Optional[ConversationManager] = None


def get_conversation_manager() -> ConversationManager:
    """Get or create the global conversation manager."""
    global _conversation_manager
    if _conversation_manager is None:
        _conversation_manager = ConversationManager()
    return _conversation_manager
