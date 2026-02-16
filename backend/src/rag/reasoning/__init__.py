"""
Advanced Reasoning Module for RAG.

Provides enhanced reasoning capabilities:
- Chain-of-thought reasoning
- Multi-hop reasoning across documents
- Iterative query refinement
- Hypothesis generation and validation
- Confidence calibration
"""

from src.rag.reasoning.reasoning_engine import (
    ReasoningEngine,
    ReasoningStep,
    ReasoningChain,
    ReasoningResult,
    ReasoningStrategy,
    get_reasoning_engine,
)

__all__ = [
    "ReasoningEngine",
    "ReasoningStep",
    "ReasoningChain",
    "ReasoningResult",
    "ReasoningStrategy",
    "get_reasoning_engine",
]
