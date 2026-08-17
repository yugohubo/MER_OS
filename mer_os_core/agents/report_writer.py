"""
MER_OS v2 — Rapor Yazıcı Ajanı (Report Writer Agent) - Akıllı Dosya Seçimli Sürüm
Kullanıcının serbest metinlerinden en uygun dökümanı bulur, okur, Merkon kurumsal formatına dönüştürür ve kaydeder.
"""
import re
from datetime import datetime
from typing import Dict, Any, Optional, Tuple
from pathlib import Path

from core.base_agent import BaseAgent
from core.message_types import AgentTask, AgentResponse
from tools.report_tools import write_report, read_report_template
from tools.document_tools import read_document, find_best_matching_document, list_input_files
from config.settings import settings

class ReportWriterAgent(BaseAgent):
    def __init__(self):
        super().__init__("report_writer")

    def _resolve_source_document(self, payload: Dict[str, Any], instruction: str) -> Tuple[Optional[Path], str]:
        """
        Kullanıcının girdiği serbest metinden en uygun girdi dosyasını bulur ve açıklamasını döner.
        """
        # 1. Payload içinde açıkça verilen arama ifadesi
        candidate_query = (
            payload.get("source_file") or
            payload.get("input_file") or
            payload.get("file") or
            payload.get("dosya") or
            payload.get("path") or
            instruction
        )

        # Akıllı eşleştiriciyi çalıştır
        matched_path, score, reason = find_best_matching_document(str(candidate_query))
        return matched_path, reason

    def run(self, task: AgentTask) -> AgentResponse:
        """
        Rapor oluşturma görevini yürütür.
        """
        payload = task.payload or {}
        instruction = task.instruction or ""
        
        user_name = payload.get("user_name") or payload.get("user") or "Yağız"
        date_str = payload.get("date_str") or datetime.now().strftime("%d.%m.%Y")
        
        # 1. Kaynak Dökümanı Akıllıca Bul ve Oku
        source_path, match_reason = self._resolve_source_document(payload, instruction)
        source_content = ""
        source_file_name = "Belirtilmedi"

        if source_path and source_path.exists():
            source_file_name = source_path.name
            source_content = read_document(str(source_path))
            if source_content.startswith("Hata:"):
                source_content = f"[Uyarı: '{source_file_name}' dökümanı okunamadı: {source_content}]"
        else:
            # Girdi klasöründe hiç dosya yoksa veya eşleşmediyse
            available = list_input_files()
            if available:
                source_content = f"[Mevcut Girdi Dosyaları: {[f['name'] for f in available]}]"
        
        raw_content = payload.get("content") or ""
        combined_data = f"Seçilen Kaynak Döküman: {source_file_name} ({match_reason})\n\nDöküman İçeriği:\n{source_content}\n\nKullanıcı Talimatı:\n{raw_content or instruction}"

        # 2. Hedef Çıktı Dosya Yolunu Belirle
        target_file = payload.get("target_file") or payload.get("output_path") or payload.get("file_path")
        if not target_file:
            clean_date = date_str.replace("/", ".").replace("-", ".")
            target_file = f"{user_name}/{clean_date}_raporu.md"

        # 3. LLM ile Kurumsal Şablona Uygun Derleme
        template = read_report_template("daily_report")
        prompt = f"""Aşağıdaki verileri Merkon kurumsal rapor standartlarına uygun eksiksiz bir Markdown faaliyet raporuna dönüştür.

## Şablon:
{template}

## Rapor Sahibi: {user_name}
## Tarih: {date_str}

## Kaynak Döküman ve Veriler:
{combined_data[:15000]}

## Kurallar:
- SADECE tam Markdown rapor metnini üret.
- Başında veya sonunda selamlama veya sohbet metni yazma.
- Varsa kritik stok eşiklerini, toleransları, tamamlanan işleri maddeler halinde net yaz.
"""
        formatted_report = self.call_llm(prompt)

        # Hata kontrolü
        if formatted_report.startswith("[Hata:"):
            return AgentResponse(
                task_id=task.task_id,
                source_agent=self.name,
                success=False,
                error=f"Model rapor metnini oluşturamadı: {formatted_report}"
            )

        # Markdown kod bloklarını temizle
        cleaned_report = re.sub(r"^```(?:markdown)?\s*", "", formatted_report.strip())
        cleaned_report = re.sub(r"\s*```$", "", cleaned_report).strip()

        # 4. Raporu sandbox/output/ Altına Kaydet
        save_result = write_report(file_path=target_file, content=cleaned_report)

        if save_result.startswith("Hata:"):
            return AgentResponse(
                task_id=task.task_id,
                source_agent=self.name,
                success=False,
                error=save_result
            )

        saved_full_path = settings.OUTPUT_DIR / target_file.replace("\\", "/").lstrip("/")
        return AgentResponse(
            task_id=task.task_id,
            source_agent=self.name,
            success=True,
            data={
                "message": save_result,
                "saved_path": str(saved_full_path),
                "source_file_used": source_file_name,
                "selection_reason": match_reason,
                "character_count": len(cleaned_report),
                "report_preview": cleaned_report[:400] + ("..." if len(cleaned_report) > 400 else ""),
                "full_report": cleaned_report
            }
        )
