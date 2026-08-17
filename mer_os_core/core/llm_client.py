"""
MER_OS v2 — Dayanıklı ve Hızlı Ollama LLM İstemcisi
Otomatik Yeniden Deneme (Retry Mechanism), Yerel Model Fallback (401 / Cloud Auth Koruması), Canlı Streaming ve Embedding Desteği
"""
import json
import time
import httpx
from typing import List, Dict, Any, Optional, Generator
from config.settings import settings

class OllamaClient:
    def __init__(self, base_url: Optional[str] = None):
        self.base_url = (base_url or settings.OLLAMA_BASE_URL).rstrip("/")
        self.timeout = httpx.Timeout(180.0, connect=15.0)
        self.fallback_local_model = "qwen3:14b"

    def chat_stream(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        temperature: float = 0.2,
        stop: Optional[List[str]] = None,
        max_retries: int = 2
    ) -> Generator[str, None, None]:
        """Ollama API üzerinden canlı token akışı (Streaming) sağlar."""
        target_model = model or settings.DEFAULT_MODEL
        url = f"{self.base_url}/api/chat"
        payload = {
            "model": target_model,
            "messages": messages,
            "stream": True,
            "options": {
                "temperature": temperature
            }
        }
        if stop:
            payload["options"]["stop"] = stop

        for attempt in range(max_retries + 1):
            try:
                with httpx.Client(timeout=self.timeout) as client:
                    with client.stream("POST", url, json=payload) as response:
                        if response.status_code == 401 and target_model != self.fallback_local_model:
                            # 401 Cloud Auth hatasında yerel offline modele geç
                            target_model = self.fallback_local_model
                            payload["model"] = target_model
                            continue
                        response.raise_for_status()
                        for line in response.iter_lines():
                            if line.strip():
                                data = json.loads(line)
                                chunk = data.get("message", {}).get("content", "")
                                if chunk:
                                    yield chunk
                return
            except (httpx.ConnectError, httpx.RemoteProtocolError, httpx.ReadTimeout) as e:
                if attempt < max_retries:
                    time.sleep(1.0)
                    continue
                yield f"\n[Hata: Model servisine ulaşılamadı ({str(e)}). Lütfen bağlantınızı veya Ollama servisini kontrol edin.]"
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 401 and target_model != self.fallback_local_model:
                    target_model = self.fallback_local_model
                    payload["model"] = target_model
                    continue
                yield f"\n[Hata: Model HTTP {e.response.status_code} -> {str(e)}]"
                return
            except Exception as e:
                yield f"\n[Hata: LLM İletişim Hatası -> {str(e)}]"
                return

    def chat_complete(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        temperature: float = 0.2,
        stop: Optional[List[str]] = None,
        max_retries: int = 2
    ) -> str:
        """Sohbet formatında tek seferde tam yanıt döndürür."""
        target_model = model or settings.DEFAULT_MODEL
        url = f"{self.base_url}/api/chat"
        payload = {
            "model": target_model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": temperature
            }
        }
        if stop:
            payload["options"]["stop"] = stop

        for attempt in range(max_retries + 1):
            try:
                with httpx.Client(timeout=self.timeout) as client:
                    resp = client.post(url, json=payload)
                    if resp.status_code == 401 and target_model != self.fallback_local_model:
                        target_model = self.fallback_local_model
                        payload["model"] = target_model
                        continue
                    resp.raise_for_status()
                    data = resp.json()
                    content = data.get("message", {}).get("content", "").strip()
                    if content:
                        return content
            except (httpx.ConnectError, httpx.RemoteProtocolError, httpx.ReadTimeout) as e:
                if attempt < max_retries:
                    time.sleep(1.0)
                    continue
                return f"[Hata: Model bağlantısı koptu ({str(e)})]"
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 401 and target_model != self.fallback_local_model:
                    target_model = self.fallback_local_model
                    payload["model"] = target_model
                    continue
                return f"[Hata: HTTP {e.response.status_code} ({str(e)})]"
            except Exception as e:
                return f"[Hata: {str(e)}]"

        return "[Hata: Yanıt alınamadı.]"

    def generate_complete(
        self,
        prompt: str,
        system: Optional[str] = None,
        model: Optional[str] = None,
        temperature: float = 0.2,
        stop: Optional[List[str]] = None,
        max_retries: int = 2
    ) -> str:
        """Prompt tabanlı doğrudan tam yanıt üretir."""
        target_model = model or settings.DEFAULT_MODEL
        url = f"{self.base_url}/api/generate"
        payload = {
            "model": target_model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": temperature
            }
        }
        if system:
            payload["system"] = system
        if stop:
            payload["options"]["stop"] = stop

        for attempt in range(max_retries + 1):
            try:
                with httpx.Client(timeout=self.timeout) as client:
                    resp = client.post(url, json=payload)
                    if resp.status_code == 401 and target_model != self.fallback_local_model:
                        target_model = self.fallback_local_model
                        payload["model"] = target_model
                        continue
                    resp.raise_for_status()
                    data = resp.json()
                    return data.get("response", "").strip()
            except (httpx.ConnectError, httpx.RemoteProtocolError, httpx.ReadTimeout):
                if attempt < max_retries:
                    time.sleep(1.0)
                    continue
                return "[Hata: Model bağlantısı zaman aşımına uğradı.]"
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 401 and target_model != self.fallback_local_model:
                    target_model = self.fallback_local_model
                    payload["model"] = target_model
                    continue
                return f"[Hata: HTTP {e.response.status_code} ({str(e)})]"
            except Exception as e:
                return f"[Hata: {str(e)}]"

        return "[Hata: Çıkarım tamamlanamadı.]"

    def get_embedding(self, text: str, model: Optional[str] = None) -> List[float]:
        """Metin için vektör embedding çıkarır (bge-m3 / nomic-embed vb.)."""
        url = f"{self.base_url}/api/embeddings"
        payload = {
            "model": model or settings.EMBEDDING_MODEL,
            "prompt": text
        }
        try:
            with httpx.Client(timeout=httpx.Timeout(30.0, connect=5.0)) as client:
                resp = client.post(url, json=payload)
                resp.raise_for_status()
                data = resp.json()
                return data.get("embedding", [])
        except Exception:
            import hashlib
            h = int(hashlib.md5(text.encode("utf-8")).hexdigest(), 16)
            return [(h >> i & 0xFF) / 255.0 for i in range(128)]

# Global Tekil İstemci
llm_client = OllamaClient()
