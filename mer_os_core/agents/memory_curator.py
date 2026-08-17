"""
MER_OS v2 — Hafıza Düzenleyici Ajanı (Memory Curator Agent) - Ay Bazlı Bölümlenmiş Vektör Hafıza Sürümü
Ay Bazlı Koleksiyonlar (mer_os_YYYY_MM), Zengin Meta Veri Filtreleme, SHA-256 İkiz Engelleme ve Oturum Kapanış Özeti
"""
import sys
import json
import re
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple
from pathlib import Path

from core.base_agent import BaseAgent
from core.message_types import (
    AgentTask,
    AgentResponse,
    MemoryFact,
    FactCategory,
    FactStatus,
    SessionTranscript
)
from tools.memory_tools import memory_engine, sanitize_entity_filename, get_collection_name_for_date
from tools.document_tools import (
    read_document,
    list_input_files,
    extract_document_metadata,
    semantic_section_chunker
)
from config.settings import settings

def parse_query_metadata_filters(query: str) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """
    Kullanıcının doğal dil sorgusundan:
    1. ChromaDB 'where' filtresi üretir.
    2. Varsa hedeflenen özel koleksiyonu belirler (Örn: 'mer_os_2026_08', 'mer_os_boms').
    """
    filters = []
    q_lower = query.lower()
    target_collection: Optional[str] = None

    # 1. Tarih & Ay Tespiti (Örn: ağustos 2026 -> mer_os_2026_08)
    month_map = {
        "ocak": "01", "subat": "02", "şubat": "02", "mart": "03", "nisan": "04", "mayis": "05", "mayıs": "05",
        "haziran": "06", "temmuz": "07", "agustos": "08", "ağustos": "08", "eylul": "09", "eylül": "09",
        "ekim": "10", "kasim": "11", "kasım": "11", "aralik": "12", "aralık": "12"
    }

    year_match = re.search(r"\b(202[0-9])\b", query)
    detected_year = int(year_match.group(1)) if year_match else None

    for m_name, m_num in month_map.items():
        if m_name in q_lower:
            yr = detected_year or 2026
            target_collection = f"mer_os_{yr}_{m_num}"
            break

    if detected_year:
        filters.append({"year": detected_year})

    # 2. BOM veya Şema Kategori Tespiti
    if any(k in q_lower for k in ["bom", "ürün ağacı", "parça listesi"]):
        target_collection = "mer_os_boms"
        filters.append({"doc_type": "bom_list"})

    # 3. Proje Filtresi
    if any(k in q_lower for k in ["telemetri", "telemetry", "aar", "switch", "edge pc"]):
        filters.append({"project": "telemetry"})
    elif any(k in q_lower for k in ["şasi", "sasi", "chassis"]):
        filters.append({"project": "chassis"})
    elif any(k in q_lower for k in ["hidrolik", "valf", "pompa"]):
        filters.append({"project": "hydraulic_unit"})

    # 4. Yazar Filtresi
    if "yağız" in q_lower or "yagiz" in q_lower:
        filters.append({"author": "Yağız"})

    where_clause: Optional[Dict[str, Any]] = None
    if filters:
        where_clause = filters[0] if len(filters) == 1 else {"$and": filters}

    return where_clause, target_collection

class MemoryCuratorAgent(BaseAgent):
    def __init__(self):
        super().__init__("memory_curator")

    def run(self, task: AgentTask) -> AgentResponse:
        """
        Gelişmiş Hafıza görevini yürütür.
        """
        payload = task.payload or {}
        action = payload.get("action") or "search"
        instruction = task.instruction.lower()

        if any(w in instruction for w in ["indeks", "index", "tara", "knowledge", "vektörle"]):
            action = "index_documents"
        elif any(w in instruction for w in ["sil", "iptal", "kaldır", "delete", "revoke"]):
            action = "delete_fact"

        # ----------------------------------------------------------------------
        # 1. AY BAZLI BÖLÜMLENMİŞ DÖKÜMAN İNDEKSLENME (KNOWLEDGE INDEXER)
        # ----------------------------------------------------------------------
        if action == "index_documents":
            folder = payload.get("folder") or settings.INPUT_DIR
            files = list_input_files(folder)
            
            if not files:
                return AgentResponse(
                    task_id=task.task_id,
                    source_agent=self.name,
                    success=True,
                    data="İndekslenecek dosya bulunamadı. `sandbox/input/` klasörü boş."
                )

            indexed_summary = []
            skipped_summary = []
            total_chunks = 0

            for f in files:
                fname = f["name"]
                fpath = Path(f["path"])
                
                # SHA-256 Kontrolü
                status, sha256_hash = memory_engine.check_file_status(fpath)
                if status == "UNCHANGED":
                    skipped_summary.append({"file": fname, "reason": "İçerik değişmedi, atlandı."})
                    continue

                content = read_document(fname)
                if content.startswith("Hata:"):
                    continue

                base_meta = extract_document_metadata(fname, content)
                chunks = semantic_section_chunker(fname, content, base_metadata=base_meta)
                
                # Ay bazlı koleksiyon adını hesapla (Örn: mer_os_2026_08)
                target_col_name = get_collection_name_for_date(base_meta.get("date"), base_meta.get("doc_type"))

                saved_count = memory_engine.upsert_document_chunks(
                    chunks=chunks,
                    doc_name=fname,
                    sha256_hash=sha256_hash,
                    target_collection_name=target_col_name
                )
                total_chunks += saved_count

                indexed_summary.append({
                    "file": fname,
                    "collection": target_col_name,
                    "status": status,
                    "size_kb": f["size_kb"],
                    "project": base_meta["project"],
                    "doc_type": base_meta["doc_type"],
                    "year": base_meta["year"],
                    "sections_indexed": len(chunks)
                })

            msg_parts = []
            if indexed_summary:
                msg_parts.append(f"✓ {len(indexed_summary)} döküman ({total_chunks} parça) ilgili ay koleksiyonlarına işlendi.")
            if skipped_summary:
                msg_parts.append(f"⚡ {len(skipped_summary)} dosya değişmediği için atlandı (İkiz koruması).")

            return AgentResponse(
                task_id=task.task_id,
                source_agent=self.name,
                success=True,
                data={
                    "message": " ".join(msg_parts) if msg_parts else "Tüm dökümanlar zaten güncel.",
                    "indexed_files": indexed_summary,
                    "skipped_files": skipped_summary,
                    "active_collections": memory_engine.list_collections()
                }
            )

        # ----------------------------------------------------------------------
        # 2. AY VE METAVERİ FİLTRELİ VEKTÖR ARAMA (PARTITIONED SEARCH)
        # ----------------------------------------------------------------------
        elif action == "search":
            query = payload.get("query") or task.instruction
            top_k = int(payload.get("top_k", 4))
            entity_filter = payload.get("entity")
            
            # Doğal dilden hem where filtrelerini hem de hedef koleksiyonu çıkar
            parsed_where, detected_col = parse_query_metadata_filters(query)
            where_filter = payload.get("where") or parsed_where
            target_col = payload.get("collection") or detected_col

            hits = memory_engine.search_vector_memory(
                query=query,
                top_k=top_k,
                entity_filter=entity_filter,
                where_filter=where_filter,
                target_collection=target_col
            )
            
            profile_text = ""
            if entity_filter:
                facts = memory_engine.load_entity_facts(entity_filter)
                active = [f.content for f in facts if f.status == FactStatus.ACTIVE]
                profile_text = "\n".join([f"- {c}" for c in active])

            return AgentResponse(
                task_id=task.task_id,
                source_agent=self.name,
                success=True,
                data={
                    "query": query,
                    "target_collection": target_col or "Tüm Koleksiyonlar",
                    "applied_filters": where_filter or "Yok",
                    "hits_count": len(hits),
                    "vector_hits": hits,
                    "entity_profile": profile_text or "Yok"
                }
            )

        # ----------------------------------------------------------------------
        # 3. HAFIZADAN SİLME / DÜZELTME (DELETE / REVOKE FACT)
        # ----------------------------------------------------------------------
        elif action == "delete_fact":
            fact_id = payload.get("fact_id")
            entity_id = payload.get("entity_id") or "user:yagiz"

            if not fact_id:
                query = payload.get("query") or task.instruction
                hits = memory_engine.search_vector_memory(query=query, top_k=2)
                if hits:
                    fact_id = hits[0]["fact_id"]
                    entity_id = hits[0]["entity_id"] or entity_id

            if not fact_id:
                return AgentResponse(
                    task_id=task.task_id,
                    source_agent=self.name,
                    success=False,
                    error="Silinecek hafıza kaydı tespit edilemedi."
                )

            del_res = memory_engine.delete_memory_fact(fact_id=fact_id, entity_id=entity_id)
            return AgentResponse(
                task_id=task.task_id,
                source_agent=self.name,
                success=not del_res.startswith("Hata:"),
                data=del_res
            )

        # ----------------------------------------------------------------------
        # 4. TEK GEÇİŞLİ (SINGLE-PASS) HIZLI OTURUM SÜZME & ÖZET ÜRETME
        # ----------------------------------------------------------------------
        elif action == "curate_session":
            transcript_dict = payload.get("transcript") or {}
            user_id = transcript_dict.get("user_id", "user:yagiz")
            entries = transcript_dict.get("entries", [])

            user_turns = [e for e in entries if e.get("role") == "user" and e.get("content", "").strip().lower() not in ["q", "exit", "quit"]]
            if len(user_turns) < 1:
                return AgentResponse(
                    task_id=task.task_id,
                    source_agent=self.name,
                    success=True,
                    data={"fast_exit": True, "message": "Kısa oturum; derin süzme gerekmedi."}
                )

            print("   [1/3] [ANALİZ] Oturum analiz ediliyor ve gerçekler süzülüyor...", flush=True)

            full_text_turns = []
            for e in entries:
                role = e.get("role", "user")
                content = e.get("content", "").strip()
                if content:
                    full_text_turns.append(f"{role.upper()}: {content}")

            combined_conversation = "\n".join(full_text_turns)

            unified_prompt = f"""Aşağıdaki oturum diyaloğunu analiz et.
Tek bir JSON çıktısı içinde hem bir sonraki oturumda kullanılacak ÖZETİ hem de kurumsal hafızaya kaydedilecek GERÇEKLERİ (Facts) üret.

## Diyalog:
{combined_conversation[:10000]}

## Kurallar:
- entity_id alanına SADECE TEK BİR VARLIK adı yaz (Örn: "user:yagiz" veya "project:chassis" veya "system:merkon"). Asla boru karakteri (|) kullanma.

## İstenen JSON Formatı:
```json
{{
  "summary": "# 📋 Son Oturum Özeti ({datetime.now().strftime('%d.%m.%Y %H:%M')})\\n- **Tamamlanan İşler:** ...\\n- **Alınan Kararlar:** ...\\n- **Karşılaşılan Sorunlar / Uyarılar:** ...\\n- **Açık Maddeler:** ...",
  "facts": [
    {{
      "entity_id": "project:chassis",
      "category": "DECISION",
      "content": "Net, tek cümlelik doğrulanmış gerçek metni"
    }}
  ]
}}
```
"""
            unified_res_str = self.call_llm(unified_prompt)

            print("   [2/3] [HAFIZA] Vektör & Semantik hafıza güncelleniyor...", flush=True)

            new_facts: List[MemoryFact] = []
            session_summary = ""
            try:
                cleaned = re.sub(r"^```(?:json)?\s*", "", unified_res_str.strip())
                cleaned = re.sub(r"\s*```$", "", cleaned).strip()
                data = json.loads(cleaned)
                
                session_summary = data.get("summary", "")
                fact_items = data.get("facts", [])
                
                if isinstance(fact_items, list):
                    for item in fact_items:
                        content = item.get("content", "").strip()
                        raw_entity = item.get("entity_id", user_id)
                        clean_entity = sanitize_entity_filename(raw_entity)
                        if content and len(content) < 350:
                            new_facts.append(MemoryFact(
                                entity_id=clean_entity,
                                category=FactCategory(item.get("category", "FACT")),
                                content=content,
                                source_session_id=transcript_dict.get("session_id")
                            ))
            except Exception:
                pass

            entities_updated = set()
            for entity_id in set(f.entity_id for f in new_facts):
                entity_new_facts = [f for f in new_facts if f.entity_id == entity_id]
                memory_engine.merge_facts_with_conflict_resolution(entity_id, entity_new_facts)
                entities_updated.add(entity_id)

            print("   [3/3] [ÖZET] 'last_session_summary.md' kaydediliyor...", flush=True)

            if session_summary:
                memory_engine.save_last_session_summary(session_summary)

            return AgentResponse(
                task_id=task.task_id,
                source_agent=self.name,
                success=True,
                data={
                    "extracted_facts_count": len(new_facts),
                    "entities_updated": list(entities_updated),
                    "summary_saved": bool(session_summary)
                }
            )

        return AgentResponse(
            task_id=task.task_id,
            source_agent=self.name,
            success=False,
            error=f"Tanımsız hafıza eylemi: {action}"
        )
