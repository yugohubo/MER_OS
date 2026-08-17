"""
MER_OS v2 — Alt Ajanlar İçin Temel Sınıf (Base Agent)
İzole Görev Yürütme, Prompt Enjeksiyonu ve Tip Güvenli Sonuç Döndürme
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from config.agents import AGENTS_CONFIG, AgentConfig
from core.message_types import AgentTask, AgentResponse
from core.llm_client import llm_client

class BaseAgent(ABC):
    def __init__(self, agent_name: str):
        self.name = agent_name
        self.config: AgentConfig = AGENTS_CONFIG.get(
            agent_name,
            AgentConfig(
                name=agent_name,
                description="Genel Ajan",
                system_prompt="Sen MER_OS alt ajanısın."
            )
        )

    @abstractmethod
    def run(self, task: AgentTask) -> AgentResponse:
        """Her alt ajanın görevi kendi uzmanlık mantığıyla çalıştırdığı metod."""
        pass

    def call_llm(self, prompt: str, system_override: Optional[str] = None) -> str:
        """Ajanın kendi sistem promptu ve modeliyle LLM çıkarımı üretir."""
        system = system_override or self.config.system_prompt
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": prompt}
        ]
        return llm_client.chat_complete(
            messages=messages,
            model=self.config.model,
            temperature=self.config.temperature
        )
