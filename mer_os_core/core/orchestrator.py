"""
MER_OS v2 — Arayüz ve Koordinasyon Ajanı (Orchestrator) - Çoklu Ajan Boru Hattı (Pipeline) Destekli Sürüm
Canlı JSONL Olay Akışı, İki Ajanlı Sıralı Boru Hattı (Info Solver ➔ Report Writer), Niyet Ayrıştırma ve Hafıza Yaşam Döngüsü
"""
import re
import json
import uuid
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple, Generator
from pathlib import Path

from config.settings import settings
from config.agents import AGENTS_CONFIG
from core.message_types import (
    AgentTask,
    AgentResponse,
    DelegationRequest,
    SessionTranscript,
    TranscriptEntry
)
from core.llm_client import llm_client
from agents.info_solver import InfoSolverAgent
from agents.report_writer import ReportWriterAgent
from agents.memory_curator import MemoryCuratorAgent
from agents.code_runner import CodeRunnerAgent
from tools.memory_tools import memory_engine

def extract_balanced_json_objects(text: str) -> List[Dict[str, Any]]:
    """Metin içindeki tüm dengeli (nested) { ... } JSON nesnelerini eksiksiz ayıklar."""
    results = []
    i = 0
    n = len(text)
    
    while i < n:
        if text[i] == '{':
            start = i
            brace_count = 0
            in_string = False
            escape = False
            
            for j in range(start, n):
                char = text[j]
                
                if char == '"' and not escape:
                    in_string = not in_string
                elif char == '\\' and in_string:
                    escape = not escape
                    continue
                elif not in_string:
                    if char == '{':
                        brace_count += 1
                    elif char == '}':
                        brace_count -= 1
                        if brace_count == 0:
                            candidate = text[start:j+1]
                            try:
                                parsed = json.loads(candidate)
                                if isinstance(parsed, dict):
                                    results.append(parsed)
                            except Exception:
                                pass
                            i = j
                            break
                escape = False
        i += 1
        
    return results

class Orchestrator:
    def __init__(self, user_id: Optional[str] = None):
        self.user_id = user_id or settings.DEFAULT_USER_ID
        self.session_id = f"sess_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:4]}"
        
        # 1. Canlı JSONL Transkript Dosyası
        self.transcript_file = settings.TRANSCRIPTS_DIR / f"{self.session_id}.jsonl"
        self.transcript = SessionTranscript(
            session_id=self.session_id,
            user_id=self.user_id,
            start_time=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        )
        
        self._append_jsonl({
            "type": "session_meta",
            "session_id": self.session_id,
            "user_id": self.user_id,
            "start_time": self.transcript.start_time
        })

        # 2. Alt Ajan Kütüphanesi
        self.sub_agents = {
            "info_solver": InfoSolverAgent(),
            "report_writer": ReportWriterAgent(),
            "memory_curator": MemoryCuratorAgent(),
            "code_runner": CodeRunnerAgent()
        }

        # 3. Başlangıç Bağlamı
        last_summary = memory_engine.get_last_session_summary()
        sys_prompt = AGENTS_CONFIG["orchestrator"].system_prompt

        if last_summary:
            initial_context = f"{sys_prompt}\n\n## 📋 Önceki Oturumdan Aktarılan Bağlam:\n{last_summary}"
        else:
            initial_context = sys_prompt

        self.messages: List[Dict[str, str]] = [
            {"role": "system", "content": initial_context}
        ]

    def _append_jsonl(self, entry_dict: Dict[str, Any]):
        """Olayları anında JSONL dosyasına satır olarak ekler."""
        try:
            self.transcript_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.transcript_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry_dict, ensure_ascii=False) + "\n")
        except Exception:
            pass

    def log_entry(self, entry: TranscriptEntry):
        """Transkripte ekler ve eşzamanlı JSONL'e yazar."""
        self.transcript.entries.append(entry)
        self._append_jsonl(entry.to_dict())

    # ==========================================================================
    # 1. KULLANICI DİYALOG DÖNGÜSÜ VE NİYET AYRIŞTIRMA
    # ==========================================================================

    def stream_orchestrator_turn(self, user_message: str) -> Generator[str, None, str]:
        """Kullanıcı mesajını alır, JSONL'ye kaydeder ve canlı token akışı sağlar."""
        self.messages.append({"role": "user", "content": user_message})
        
        self.log_entry(TranscriptEntry(
            timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            role="user",
            content=user_message
        ))

        full_chunks = []
        for chunk in llm_client.chat_stream(
            messages=self.messages,
            model=AGENTS_CONFIG["orchestrator"].model,
            temperature=AGENTS_CONFIG["orchestrator"].temperature
        ):
            full_chunks.append(chunk)
            yield chunk

        full_response = "".join(full_chunks).strip()
        return full_response

    def parse_delegation_intent(self, response_text: str) -> Optional[DelegationRequest]:
        """Model çıktısındaki dengeli JSON veya açık delege isteklerini hatasız ayıklar."""
        parsed_objects = extract_balanced_json_objects(response_text)
        valid_targets = set(self.sub_agents.keys()) | {"doc_report_pipeline", "info_solver+report_writer"}

        for obj in parsed_objects:
            if obj.get("delegate") is True or "target_agent" in obj:
                target = str(obj.get("target_agent", "")).lower().strip()
                if target in valid_targets:
                    return DelegationRequest(
                        target_agent=target,
                        action_summary=obj.get("action_summary", f"{target} çalıştırılacak."),
                        payload=obj.get("payload", {})
                    )

        # Fallback: Rapor veya döküman talebi geldiğinde otomatik çoklu ajan boru hattı öner
        last_user_msg = self.messages[-1]["content"].lower() if self.messages else ""
        if any(w in last_user_msg for w in ["raporla", "rapor oluştur", "rapor hazırla", "raporu yaz", "raporunu çıkar"]):
            return DelegationRequest(
                target_agent="doc_report_pipeline",
                action_summary="Döküman önce Bilgi Çözücü (Info Solver) ile analiz edilecek, ardından Rapor Yazıcı (Report Writer) ile kurumsal rapora dönüştürülecek.",
                payload={"instruction": last_user_msg}
            )
        elif any(w in last_user_msg for w in ["knowledge index", "dökümanları indeksle", "hafızaya indeksle", "indexer"]):
            return DelegationRequest(
                target_agent="memory_curator",
                action_summary="Girdi dökümanları taranıp ChromaDB vektör veritabanına indekslenecek.",
                payload={"action": "index_documents"}
            )

        return None

    # ==========================================================================
    # 2. ALT AJAN VE ÇOKLU AJAN BORU HATTI YÜRÜTME
    # ==========================================================================

    def execute_delegation(self, request: DelegationRequest) -> AgentResponse:
        """
        Kullanıcı 'EVET' dediğinde tekil ajanı veya iki ajanlı sıralı boru hattını (Pipeline) çalıştırır.
        """
        # A. ÇOKLU AJAN BORU HATTI: INFO_SOLVER ➔ REPORT_WRITER
        if request.target_agent in ["doc_report_pipeline", "info_solver+report_writer"]:
            return self._execute_doc_report_pipeline(request)

        # B. TEKİL ALT AJAN YÜRÜTME
        agent = self.sub_agents.get(request.target_agent)
        if not agent:
            return AgentResponse(
                task_id="err",
                source_agent=request.target_agent,
                success=False,
                error=f"Tanımsız alt ajan: {request.target_agent}"
            )

        task_payload = dict(request.payload)
        if "instruction" not in task_payload and self.messages:
            task_payload["instruction"] = self.messages[-1]["content"]

        task = AgentTask(
            target_agent=request.target_agent,
            instruction=request.action_summary,
            payload=task_payload
        )

        self.log_entry(TranscriptEntry(
            timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            role="agent_event",
            content=f"Delege Edildi -> {request.target_agent}: {request.action_summary}",
            agent_name=request.target_agent,
            task_id=task.task_id,
            metadata={"payload": task_payload}
        ))

        agent_response = agent.run(task)

        self.log_entry(TranscriptEntry(
            timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            role="agent_event",
            content=f"Sonuç Alındı -> {request.target_agent} (Başarı: {agent_response.success})",
            agent_name=request.target_agent,
            task_id=task.task_id,
            metadata={"data": str(agent_response.data)[:500]}
        ))

        return agent_response

    def _execute_doc_report_pipeline(self, request: DelegationRequest) -> AgentResponse:
        """
        İki aşamalı sıralı boru hattı:
        Adım 1: InfoSolverAgent ham dökümanı okur, gürültüyü temizler ve teknik verileri damıtır.
        Adım 2: ReportWriterAgent damıtılan veriyi Merkon kurumsal şablonuna döküp output altına kaydeder.
        """
        task_id = str(uuid.uuid4())[:8]
        payload = dict(request.payload)
        if "instruction" not in payload and self.messages:
            payload["instruction"] = self.messages[-1]["content"]

        print("\n   [1/2] [BİLGİ ÇÖZÜCÜ] Döküman inceleniyor ve veriler damıtılıyor...", flush=True)

        # 1. ADIM: Info Solver Çalıştır
        info_task = AgentTask(
            task_id=f"{task_id}_info",
            target_agent="info_solver",
            instruction=request.action_summary,
            payload=payload
        )
        self.log_entry(TranscriptEntry(
            timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            role="agent_event",
            content=f"Pipeline [1/2] -> info_solver başlatıldı",
            agent_name="info_solver",
            task_id=info_task.task_id
        ))

        info_resp = self.sub_agents["info_solver"].run(info_task)
        if not info_resp.success:
            return AgentResponse(
                task_id=task_id,
                source_agent="doc_report_pipeline",
                success=False,
                error=f"Bilgi Çözücü aşamasında hata: {info_resp.error}"
            )

        extracted_data = info_resp.data if isinstance(info_resp.data, dict) else {}
        extracted_knowledge = extracted_data.get("extracted_knowledge") or str(info_resp.data)
        selected_file = extracted_data.get("selected_file") or "Belirtilmedi"

        print(f"   [+] 1. Aşama Tamamlandı (Döküman: '{selected_file}')", flush=True)
        print("   [2/2] [RAPOR YAZICI] Kurumsal şablon uygulanıyor ve dosya kaydediliyor...", flush=True)

        # 2. ADIM: Report Writer Çalıştır (Info Solver'ın çıktısını girdi olarak ver)
        report_payload = dict(payload)
        report_payload["content"] = extracted_knowledge
        report_payload["source_file"] = selected_file

        report_task = AgentTask(
            task_id=f"{task_id}_report",
            target_agent="report_writer",
            instruction=f"'{selected_file}' dökümanından süzülen verilerle kurumsal rapor hazırla.",
            payload=report_payload
        )
        self.log_entry(TranscriptEntry(
            timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            role="agent_event",
            content=f"Pipeline [2/2] -> report_writer başlatıldı (Girdi döküman: {selected_file})",
            agent_name="report_writer",
            task_id=report_task.task_id
        ))

        report_resp = self.sub_agents["report_writer"].run(report_task)
        if not report_resp.success:
            return AgentResponse(
                task_id=task_id,
                source_agent="doc_report_pipeline",
                success=False,
                error=f"Rapor Yazıcı aşamasında hata: {report_resp.error}"
            )

        report_data = report_resp.data if isinstance(report_resp.data, dict) else {}
        saved_path = report_data.get("saved_path")

        print(f"   [+] 2. Aşama Tamamlandı (Rapor: `{saved_path}`)\n", flush=True)

        # Birleşik Pipeline Yanıtı
        return AgentResponse(
            task_id=task_id,
            source_agent="doc_report_pipeline",
            success=True,
            data={
                "pipeline": "info_solver -> report_writer",
                "source_file_used": selected_file,
                "saved_path": saved_path,
                "extracted_summary": extracted_knowledge[:400] + "...",
                "report_preview": report_data.get("report_preview"),
                "full_report": report_data.get("full_report")
            }
        )

    def synthesize_agent_result(self, request: DelegationRequest, agent_resp: AgentResponse) -> Generator[str, None, str]:
        """Alt ajanın veya boru hattının ürettiği çıktıyı arayüz modeliyle kullanıcıya özetler."""
        if agent_resp.success:
            context_injection = f"İşlem Başarılı ({request.target_agent}):\n{json.dumps(agent_resp.data, ensure_ascii=False, indent=2) if isinstance(agent_resp.data, dict) else str(agent_resp.data)}"
        else:
            context_injection = f"İşlem Sırasında Hata Oluştu ({request.target_agent}): {agent_resp.error}"

        synthesis_messages = list(self.messages)
        synthesis_messages.append({
            "role": "system",
            "content": f"Çoklu Ajan görevi '{request.target_agent}' tamamlandı. İşte elde edilen sonuç:\n{context_injection}\n\nKullanıcıya durumu profesyonelce özetle, analiz edilen dökümanı ve kaydedilen rapor dosya yolunu net olarak sun."
        })

        full_chunks = []
        for chunk in llm_client.chat_stream(
            messages=synthesis_messages,
            model=AGENTS_CONFIG["orchestrator"].model,
            temperature=AGENTS_CONFIG["orchestrator"].temperature
        ):
            full_chunks.append(chunk)
            yield chunk

        final_text = "".join(full_chunks).strip()
        self.messages.append({"role": "assistant", "content": final_text})
        
        self.log_entry(TranscriptEntry(
            timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            role="assistant",
            content=final_text
        ))
        return final_text

    def handle_rejection(self, request: DelegationRequest) -> Generator[str, None, str]:
        """Kullanıcı 'HAYIR' dediğinde alternatif yönlendirme sorusunu üretir."""
        self.log_entry(TranscriptEntry(
            timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            role="user",
            content=f"[Kullanıcı '{request.action_summary}' işlemini ONAYLAMADI]"
        ))

        rejection_messages = list(self.messages)
        rejection_messages.append({
            "role": "system",
            "content": f"Kullanıcı '{request.action_summary}' işlemini onaylamadı ve iptal etti. Kullanıcıya işlemin iptal edildiğini nazikçe bildir ve alternatif olarak ne yapmak istediğini sor."
        })

        full_chunks = []
        for chunk in llm_client.chat_stream(
            messages=rejection_messages,
            model=AGENTS_CONFIG["orchestrator"].model,
            temperature=AGENTS_CONFIG["orchestrator"].temperature
        ):
            full_chunks.append(chunk)
            yield chunk

        final_text = "".join(full_chunks).strip()
        self.messages.append({"role": "assistant", "content": final_text})
        
        self.log_entry(TranscriptEntry(
            timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            role="assistant",
            content=final_text
        ))
        return final_text

    # ==========================================================================
    # 3. OTURUM KAPANIŞI VE HAFIZA MÜHÜRLEME
    # ==========================================================================

    def close_session(self) -> Dict[str, Any]:
        """Oturumu kapatır, kapanış satırını JSONL'ye yazar ve MemoryCurator'a süzme yaptırır."""
        self.transcript.end_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        self._append_jsonl({
            "type": "session_close",
            "session_id": self.session_id,
            "end_time": self.transcript.end_time,
            "total_entries": len(self.transcript.entries)
        })

        curator = self.sub_agents["memory_curator"]
        task = AgentTask(
            target_agent="memory_curator",
            instruction="Oturum transkriptini süz ve last_session_summary.md üret.",
            payload={
                "action": "curate_session",
                "transcript": self.transcript.to_dict()
            }
        )
        curation_response = curator.run(task)

        return {
            "session_id": self.session_id,
            "transcript_file": str(self.transcript_file),
            "curation_success": curation_response.success,
            "curation_data": curation_response.data
        }
