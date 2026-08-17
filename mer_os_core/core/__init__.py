"""
MER_OS v2 Çekirdek Paketi
"""
from .llm_client import llm_client, OllamaClient
from .message_types import (
    AgentTask,
    AgentResponse,
    DelegationRequest,
    MemoryFact,
    FactCategory,
    FactStatus,
    SessionTranscript,
    TranscriptEntry
)
from .base_agent import BaseAgent

# Orchestrator lazy/direct erişim için __getattr__ desteği
def __getattr__(name):
    if name == "Orchestrator":
        from .orchestrator import Orchestrator
        return Orchestrator
    raise AttributeError(f"module 'core' has no attribute '{name}'")

__all__ = [
    "llm_client",
    "OllamaClient",
    "AgentTask",
    "AgentResponse",
    "DelegationRequest",
    "MemoryFact",
    "FactCategory",
    "FactStatus",
    "SessionTranscript",
    "TranscriptEntry",
    "BaseAgent",
    "Orchestrator"
]
