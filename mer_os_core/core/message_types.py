"""
MER_OS v2 — Ajanlar Arası Tip Güvenli Mesaj ve Veri Modelleri
"""
from dataclasses import dataclass, field, asdict
from typing import Dict, Any, List, Optional
from enum import Enum
from datetime import datetime
import uuid

# ==============================================================================
# 1. AJAN GÖREV VE YANIT MODELLERİ
# ==============================================================================

@dataclass
class DelegationRequest:
    """Arayüz ajanının alt ajana veya çoklu ajan boru hattına (pipeline) iş devretme talebi."""
    target_agent: str
    action_summary: str
    payload: Dict[str, Any] = field(default_factory=dict)
    pipeline: Optional[List[str]] = None  # Örn: ["info_solver", "report_writer"]

@dataclass
class AgentTask:
    """Alt ajana iletilen izole görev paketi."""
    task_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    target_agent: str = ""
    instruction: str = ""
    payload: Dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

@dataclass
class AgentResponse:
    """Alt ajanın veya boru hattının ürettiği yapılandırılmış sonuç paketi."""
    task_id: str
    source_agent: str
    success: bool
    data: Any = None
    error: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

# ==============================================================================
# 2. 4-KATMANLI KURUMSAL HAFIZA MODELLERİ
# ==============================================================================

class FactCategory(str, Enum):
    DECISION = "DECISION"          # Alınan kesin kararlar
    PREFERENCE = "PREFERENCE"      # Kullanıcı tercihleri ve üslubu
    CONSTRAINT = "CONSTRAINT"      # Limitler, toleranslar, kritik stok sınırları
    OPEN_ITEM = "OPEN_ITEM"        # Açıkta kalan görev ve taahhütler
    FACT = "FACT"                  # Nesnel teknik ve kurumsal gerçekler

class FactStatus(str, Enum):
    ACTIVE = "ACTIVE"              # Geçerli aktif bilgi
    SUPERSEDED = "SUPERSEDED"      # Yeni bir kararla revize edilmiş/geçersiz kılınmış
    REVOKED = "REVOKED"            # Kullanıcı tarafından silinmiş/iptal edilmiş

@dataclass
class MemoryFact:
    """Semantik ve Vektörel Hafıza Birimi (Atomik Gerçek)."""
    fact_id: str = field(default_factory=lambda: f"fact_{uuid.uuid4().hex[:8]}")
    entity_id: str = "user:yagiz"
    category: FactCategory = FactCategory.FACT
    content: str = ""
    status: FactStatus = FactStatus.ACTIVE
    superseded_by: Optional[str] = None
    source_session_id: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    updated_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["category"] = self.category.value if isinstance(self.category, FactCategory) else self.category
        d["status"] = self.status.value if isinstance(self.status, FactStatus) else self.status
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MemoryFact":
        cat = FactCategory(data.get("category", "FACT"))
        stat = FactStatus(data.get("status", "ACTIVE"))
        return cls(
            fact_id=data.get("fact_id", f"fact_{uuid.uuid4().hex[:8]}"),
            entity_id=data.get("entity_id", "user:yagiz"),
            category=cat,
            content=data.get("content", ""),
            status=stat,
            superseded_by=data.get("superseded_by"),
            source_session_id=data.get("source_session_id"),
            created_at=data.get("created_at", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
            updated_at=data.get("updated_at")
        )

# ==============================================================================
# 3. EPİZODİK TRANSKRİPT MODELLERİ
# ==============================================================================

@dataclass
class TranscriptEntry:
    """Oturum içindeki her bir diyalog ve alt ajan olayı."""
    timestamp: str
    role: str
    content: str
    agent_name: Optional[str] = None
    task_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

@dataclass
class SessionTranscript:
    """Oturumun tamamını temsil eden epizodik veri."""
    session_id: str
    user_id: str
    start_time: str
    end_time: Optional[str] = None
    entries: List[TranscriptEntry] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "user_id": self.user_id,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "entries": [e.to_dict() for e in self.entries]
        }
