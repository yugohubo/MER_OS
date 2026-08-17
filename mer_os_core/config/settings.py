"""
MER_OS v2 — Merkezi Ayarlar ve Dizin Yapılandırması
"""
import os
from pathlib import Path
from pydantic import BaseModel

# ChromaDB Telemetrisini ve AsyncIO uyarılarını devre dışı bırak (Python 3.14 uyumluluğu)
os.environ["ANONYMIZED_TELEMETRY"] = "False"
os.environ["CHROMA_TELEMETRY"] = "False"
os.environ["PYTHONWARNINGS"] = "ignore::DeprecationWarning"

# Temel Dizinler
BASE_DIR = Path(__file__).resolve().parent.parent
SANDBOX_DIR = BASE_DIR / "sandbox"

class Settings(BaseModel):
    PROJECT_NAME: str = "MER_OS v2"
    
    # Ollama ve Model Yapılandırması
    OLLAMA_BASE_URL: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    DEFAULT_MODEL: str = os.getenv("DEFAULT_MODEL", "minimax-m3:cloud")
    EMBEDDING_MODEL: str = os.getenv("EMBEDDING_MODEL", "bge-m3")
    
    # Dizin Yolları
    BASE_DIR: Path = BASE_DIR
    SANDBOX_DIR: Path = SANDBOX_DIR
    INPUT_DIR: Path = SANDBOX_DIR / "input"
    OUTPUT_DIR: Path = SANDBOX_DIR / "output"
    SCRIPTS_DIR: Path = SANDBOX_DIR / "scripts"
    
    # Hafıza Yolları
    MEMORY_DIR: Path = SANDBOX_DIR / "memory"
    TRANSCRIPTS_DIR: Path = SANDBOX_DIR / "memory" / "transcripts"
    SEMANTIC_DIR: Path = SANDBOX_DIR / "memory" / "semantic"
    CHROMA_DB_DIR: Path = SANDBOX_DIR / "memory" / "chroma_db"
    LAST_SESSION_SUMMARY_FILE: Path = SANDBOX_DIR / "memory" / "last_session_summary.md"
    
    # Varsayılan Kullanıcı ve Limitler
    DEFAULT_USER_ID: str = "user:yagiz"
    DEFAULT_TOP_K: int = 4
    SUBPROCESS_TIMEOUT_SECONDS: int = 45

settings = Settings()

def ensure_directories():
    """Gerekli tüm çalışma ve hafıza dizinlerinin varlığını garanti eder."""
    for d in [
        settings.SANDBOX_DIR,
        settings.INPUT_DIR,
        settings.OUTPUT_DIR,
        settings.SCRIPTS_DIR,
        settings.MEMORY_DIR,
        settings.TRANSCRIPTS_DIR,
        settings.SEMANTIC_DIR,
        settings.CHROMA_DB_DIR
    ]:
        d.mkdir(parents=True, exist_ok=True)

# Başlangıçta dizinleri hazırla
ensure_directories()
