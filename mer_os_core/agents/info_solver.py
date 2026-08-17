"""
MER_OS v2 — Bilgi Çözücü Ajanı (Information Solver Agent) - Akıllı Dosya Seçimli Sürüm
Dökümanları (PDF, Excel BOM, CSV, MD) akıllıca bulur, okur, gürültüyü eler ve yüksek değerli yapılandırılmış özetler çıkarır.
"""
from typing import Dict, Any
from core.base_agent import BaseAgent
from core.message_types import AgentTask, AgentResponse
from tools.document_tools import read_document, find_best_matching_document, list_input_files

class InfoSolverAgent(BaseAgent):
    def __init__(self):
        super().__init__("info_solver")

    def run(self, task: AgentTask) -> AgentResponse:
        """
        Görevi yürütür.
        """
        payload = task.payload or {}
        candidate_query = (
            payload.get("file_path") or
            payload.get("source_file") or
            payload.get("path") or
            payload.get("dosya") or
            task.instruction
        )
        raw_text = payload.get("raw_text") or ""

        # 1. Dosyayı akıllıca bul ve oku
        doc_content = ""
        source_file_name = "raw_text"
        match_reason = ""

        if not raw_text:
            matched_path, score, reason = find_best_matching_document(str(candidate_query))
            if matched_path and matched_path.exists():
                source_file_name = matched_path.name
                match_reason = reason
                doc_content = read_document(str(matched_path))
                if doc_content.startswith("Hata:"):
                    return AgentResponse(
                        task_id=task.task_id,
                        source_agent=self.name,
                        success=False,
                        error=doc_content
                    )
            else:
                files = list_input_files()
                return AgentResponse(
                    task_id=task.task_id,
                    source_agent=self.name,
                    success=True,
                    data=f"İncelenecek dosya bulunamadı ({reason}). Girdi klasöründeki mevcut dosyalar: {[f['name'] for f in files]}"
                )
        else:
            doc_content = raw_text

        # 2. Çözümleme ve özetleme promptu
        prompt = f"""Aşağıdaki teknik dökümanı incele ve kritik bilgileri damıtarak yapılandırılmış bir özet sun.

## Seçilen Kaynak Döküman: {source_file_name} ({match_reason})
## Odak Noktası / Kullanıcı Talebi:
{task.instruction}

## Döküman İçeriği:
{doc_content[:15000]}

## Senden İstenen Çıktı Formatı:
1. **📌 Temel Konu ve Kapsam:** (Kısa özet)
2. **⚙️ Teknik Veriler / Toleranslar / BOM Maddeleri:** (Varsa parça kodları, stoklar veya ölçüler)
3. **⚠️ Karşılaşılan Sorunlar & Kritik Kısıtlar:** (Varsa uyarılar)
4. **✅ Alınan Kararlar & Sonraki Adımlar:** (Varsa aksiyonlar)
"""
        extracted_result = self.call_llm(prompt)

        return AgentResponse(
            task_id=task.task_id,
            source_agent=self.name,
            success=True,
            data={
                "selected_file": source_file_name,
                "selection_reason": match_reason,
                "extracted_knowledge": extracted_result,
                "raw_doc_length": len(doc_content)
            }
        )
