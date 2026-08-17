"""
MER_OS v2 — 4 Katmanlı Kurumsal Hafıza Araçları ve Ay/Kategori Bazlı Koleksiyon Bölümleme (Collection Partitioning)
ChromaDB Ay Bazlı Koleksiyonlar (Örn: mer_os_2026_08, mer_os_core), SHA-256 İkiz Engelleme ve Çelişki Çözme
"""
import os
import json
import re
import hashlib
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple, Set
from datetime import datetime
from config.settings import settings
from core.message_types import MemoryFact, FactCategory, FactStatus, SessionTranscript, TranscriptEntry
from core.llm_client import llm_client

def sanitize_entity_filename(entity_id: str) -> str:
    r"""
    Windows ve Linux dosya sistemlerinde yasaklı karakterleri (| / \ : * ? " < >) 
    temizler ve güvenli bir dosya adı üretir.
    """
    text = str(entity_id).strip()
    if "|" in text:
        text = text.split("|")[0].strip()
    safe = re.sub(r'[\\/*?:"<>|]', '_', text)
    safe = re.sub(r'\s+', '_', safe).strip('_')
    return safe or "entity_general"

def compute_file_sha256(file_path: Path) -> str:
    """Dosyanın SHA-256 özetini çıkararak içerik parmak izini hesaplar."""
    h = hashlib.sha256()
    try:
        with open(file_path, "rb") as f:
            while chunk := f.read(8192):
                h.update(chunk)
        return h.hexdigest()
    except Exception:
        return ""

def get_collection_name_for_date(date_str: Optional[str] = None, doc_type: Optional[str] = None) -> str:
    """
    Tarih ve döküman tipine göre ChromaDB koleksiyon adını belirler:
    - Günlük/Faaliyet Raporları: 'mer_os_2026_08' (Ay bazlı dinamik koleksiyon)
    - BOM / Ürün Ağaçları: 'mer_os_boms'
    - Şirket İlkeleri / Prosedürler: 'mer_os_core'
    """
    if doc_type == "bom_list":
        return "mer_os_boms"
    elif doc_type in ["sop_spec", "company_rule"]:
        return "mer_os_core"

    # Tarihten YYYY_MM çıkar
    if date_str:
        match = re.search(r"(\d{4})[.\-_/](\d{2})", date_str)
        if match:
            return f"mer_os_{match.group(1)}_{match.group(2)}"
    
    current_ym = datetime.now().strftime("%Y_%m")
    return f"mer_os_{current_ym}"

class MemoryEngine:
    def __init__(self, chroma_dir: Optional[Path] = None, semantic_dir: Optional[Path] = None):
        self.chroma_dir = chroma_dir or settings.CHROMA_DB_DIR
        self.semantic_dir = semantic_dir or settings.SEMANTIC_DIR
        self.registry_file = self.chroma_dir / "indexed_registry.json"
        
        self.chroma_dir.mkdir(parents=True, exist_ok=True)
        self.semantic_dir.mkdir(parents=True, exist_ok=True)
        
        self._chroma_client = None
        self._collections: Dict[str, Any] = {}

    def _get_client(self):
        """ChromaDB PersistentClient'ı döndürür."""
        if self._chroma_client is None:
            try:
                import chromadb
                self._chroma_client = chromadb.PersistentClient(path=str(self.chroma_dir))
            except Exception:
                return None
        return self._chroma_client

    def get_or_create_collection(self, collection_name: Optional[str] = None):
        """İstenen ay/kategori bazlı koleksiyonu dinamik olarak başlatır."""
        col_name = collection_name or get_collection_name_for_date()
        if col_name in self._collections:
            return self._collections[col_name]

        client = self._get_client()
        if client is None:
            return None

        try:
            col = client.get_or_create_collection(
                name=col_name,
                metadata={"description": f"MER_OS Vektör Koleksiyonu: {col_name}"}
            )
            self._collections[col_name] = col
            return col
        except Exception:
            return None

    def list_collections(self) -> List[str]:
        """Mevcut tüm izole koleksiyonların isimlerini listeler."""
        client = self._get_client()
        if client is None:
            return []
        try:
            return [c.name for c in client.list_collections()]
        except Exception:
            return list(self._collections.keys())

    # ==========================================================================
    # 0. İKİZ ENGELLEME & ARTIMLI İNDEKS DEFTERİ (INDEX REGISTRY)
    # ==========================================================================

    def load_index_registry(self) -> Dict[str, Any]:
        """Daha önce indekslenmiş dosyaların SHA-256 parmak izlerini yükler."""
        if self.registry_file.exists():
            try:
                return json.loads(self.registry_file.read_text(encoding="utf-8"))
            except Exception:
                return {}
        return {}

    def save_index_registry(self, registry: Dict[str, Any]):
        """İndeks defterini kaydeder."""
        try:
            self.registry_file.write_text(json.dumps(registry, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            pass

    def check_file_status(self, file_path: Path) -> Tuple[str, str]:
        """Dosyanın durumunu kontrol eder: ('NEW' | 'MODIFIED' | 'UNCHANGED', sha256_hash)"""
        registry = self.load_index_registry()
        sha = compute_file_sha256(file_path)
        fname = file_path.name

        if fname not in registry:
            return "NEW", sha
        elif registry[fname].get("sha256") != sha:
            return "MODIFIED", sha
        else:
            return "UNCHANGED", sha

    # ==========================================================================
    # 1. SEMANTİK HAFIZA YÖNETİMİ (JSON + MARKDOWN)
    # ==========================================================================

    def load_entity_facts(self, entity_id: str) -> List[MemoryFact]:
        """Belirtilen varlığa ait gerçekleri JSON'dan yükler."""
        safe_name = sanitize_entity_filename(entity_id)
        json_file = self.semantic_dir / f"{safe_name}.json"
        if not json_file.exists():
            return []
        try:
            data = json.loads(json_file.read_text(encoding="utf-8"))
            return [MemoryFact.from_dict(f) for f in data]
        except Exception:
            return []

    def save_entity_facts(self, entity_id: str, facts: List[MemoryFact]):
        """Varlığa ait gerçekleri hem JSON hem de temiz Markdown olarak kaydeder."""
        safe_name = sanitize_entity_filename(entity_id)
        json_file = self.semantic_dir / f"{safe_name}.json"
        md_file = self.semantic_dir / f"{safe_name}.md"

        json_file.write_text(
            json.dumps([f.to_dict() for f in facts], ensure_ascii=False, indent=2),
            encoding="utf-8"
        )

        active_facts = [f for f in facts if f.status == FactStatus.ACTIVE]
        lines = [
            f"# 🧠 Semantik Hafıza Dosyası: {entity_id}",
            f"**Son Güncelleme:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"**Aktif Gerçek Sayısı:** {len(active_facts)}\n",
            "---"
        ]

        for cat in FactCategory:
            cat_facts = [f for f in active_facts if f.category == cat]
            if cat_facts:
                lines.append(f"\n## 📌 {cat.value}")
                for cf in cat_facts:
                    lines.append(f"- {cf.content} *(ID: `{cf.fact_id}`, Kayıt: {cf.created_at})*")

        md_file.write_text("\n".join(lines), encoding="utf-8")

    def merge_facts_with_conflict_resolution(self, entity_id: str, new_facts: List[MemoryFact]) -> List[MemoryFact]:
        """Yeni gerçekleri mevcut hafızayla birleştirir, çelişkileri çözer ve ChromaDB'ye gömer."""
        existing_facts = self.load_entity_facts(entity_id)
        all_facts = list(existing_facts)

        for new_f in new_facts:
            if any(f.content.strip() == new_f.content.strip() and f.status == FactStatus.ACTIVE for f in all_facts):
                continue

            for old_f in all_facts:
                if old_f.status == FactStatus.ACTIVE and old_f.category == new_f.category:
                    old_words = set(re.findall(r"\w{4,}", old_f.content.lower()))
                    new_words = set(re.findall(r"\w{4,}", new_f.content.lower()))
                    if len(old_words & new_words) >= 2:
                        old_f.status = FactStatus.SUPERSEDED
                        old_f.superseded_by = new_f.fact_id
                        old_f.updated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        self._delete_vector(old_f.fact_id)

            new_f.status = FactStatus.ACTIVE
            all_facts.append(new_f)
            self._upsert_vector(new_f)

        self.save_entity_facts(entity_id, all_facts)
        return all_facts

    # ==========================================================================
    # 2. AY VE KATEGORİ BAZLI CHROMADB VEKTÖR YÖNETİMİ
    # ==========================================================================

    def _upsert_vector(self, fact: MemoryFact, collection_name: Optional[str] = None):
        """Gerçeğin embeddingini çıkarıp ilgili koleksiyona kaydeder."""
        target_col = self.get_or_create_collection(collection_name or "mer_os_core")
        if target_col is None:
            return

        try:
            emb = llm_client.get_embedding(fact.content)
            target_col.upsert(
                ids=[fact.fact_id],
                embeddings=[emb],
                documents=[fact.content],
                metadatas=[{
                    "entity_id": fact.entity_id,
                    "category": fact.category.value,
                    "created_at": fact.created_at,
                    "year": 2026
                }]
            )
        except Exception:
            pass

    def purge_document_chunks(self, doc_name: str, collection_name: Optional[str] = None):
        """Dosya güncellendiğinde eski parçaları ilgili koleksiyondan temizler."""
        cols_to_check = [self.get_or_create_collection(collection_name)] if collection_name else [self.get_or_create_collection(c) for c in self.list_collections()]
        for col in cols_to_check:
            if col is not None:
                try:
                    col.delete(where={"doc_name": doc_name})
                except Exception:
                    pass

    def upsert_document_chunks(
        self,
        chunks: List[Dict[str, Any]],
        doc_name: Optional[str] = None,
        sha256_hash: Optional[str] = None,
        target_collection_name: Optional[str] = None
    ) -> int:
        """
        Döküman parçalarını ilgili ay/kategori bazlı koleksiyona (Örn: 'mer_os_2026_08') kaydeder.
        """
        if not chunks:
            return 0

        target_doc = doc_name or chunks[0].get("metadata", {}).get("doc_name", "doc")
        doc_date = chunks[0].get("metadata", {}).get("date")
        doc_type = chunks[0].get("metadata", {}).get("doc_type")

        # Ay bazlı veya kategori bazlı koleksiyon adını belirle
        col_name = target_collection_name or get_collection_name_for_date(doc_date, doc_type)
        collection = self.get_or_create_collection(col_name)
        if collection is None:
            return 0

        # Eski kopyayı temizle
        self.purge_document_chunks(target_doc, collection_name=col_name)

        ids = []
        embeddings = []
        documents = []
        metadatas = []

        for idx, item in enumerate(chunks):
            chunk_text = item["text"]
            chunk_meta = item.get("metadata", {})
            
            clean_doc_slug = sanitize_entity_filename(target_doc)
            chunk_id = f"chunk_{clean_doc_slug}_{chunk_meta.get('chunk_idx', idx)}"

            emb = llm_client.get_embedding(chunk_text)
            
            safe_meta: Dict[str, Any] = {"collection": col_name}
            for k, v in chunk_meta.items():
                if isinstance(v, (str, int, float, bool)):
                    safe_meta[k] = v
                else:
                    safe_meta[k] = str(v)

            ids.append(chunk_id)
            embeddings.append(emb)
            documents.append(chunk_text)
            metadatas.append(safe_meta)

        try:
            collection.upsert(
                ids=ids,
                embeddings=embeddings,
                documents=documents,
                metadatas=metadatas
            )

            if sha256_hash:
                registry = self.load_index_registry()
                registry[target_doc] = {
                    "sha256": sha256_hash,
                    "collection": col_name,
                    "chunks_count": len(ids),
                    "indexed_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }
                self.save_index_registry(registry)

            return len(ids)
        except Exception:
            return 0

    def _delete_vector(self, fact_id: str):
        """Tüm koleksiyonlardan belirtilen fact_id'yi siler."""
        for col_name in self.list_collections():
            col = self.get_or_create_collection(col_name)
            if col:
                try:
                    col.delete(ids=[fact_id])
                except Exception:
                    pass

    def search_vector_memory(
        self,
        query: str,
        top_k: int = 4,
        entity_filter: Optional[str] = None,
        where_filter: Optional[Dict[str, Any]] = None,
        target_collection: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Belirtilen ay/koleksiyon veya tüm koleksiyonlar üzerinde arama yapar.
        Eğer 'target_collection' belirtilmemişse, mevcut tüm koleksiyonları tarayıp en iyi eşleşmeleri birleştirir.
        """
        all_col_names = [target_collection] if target_collection else self.list_collections()
        if not all_col_names:
            all_col_names = [get_collection_name_for_date()]

        all_hits = []
        query_emb = llm_client.get_embedding(query)

        final_where: Optional[Dict[str, Any]] = None
        if entity_filter and where_filter:
            final_where = {"$and": [{"entity_id": entity_filter}, where_filter]}
        elif entity_filter:
            final_where = {"entity_id": entity_filter}
        elif where_filter:
            final_where = where_filter

        for col_name in all_col_names:
            col = self.get_or_create_collection(col_name)
            if col is None:
                continue

            try:
                results = col.query(
                    query_embeddings=[query_emb],
                    n_results=min(top_k, 10),
                    where=final_where
                )

                docs = results.get("documents", [[]])[0]
                metas = results.get("metadatas", [[]])[0]
                ids = results.get("ids", [[]])[0]
                distances = results.get("distances", [[]])[0] if "distances" in results else [0.0] * len(docs)

                for doc_id, doc, meta, dist in zip(ids, docs, metas, distances):
                    all_hits.append({
                        "fact_id": doc_id,
                        "content": doc,
                        "collection": col_name,
                        "distance": dist,
                        "entity_id": meta.get("entity_id") or meta.get("doc_name"),
                        "project": meta.get("project"),
                        "year": meta.get("year"),
                        "doc_type": meta.get("doc_type"),
                        "section": meta.get("section"),
                        "category": meta.get("category"),
                        "created_at": meta.get("created_at") or meta.get("date"),
                        "hardware": meta.get("hardware")
                    })
            except Exception:
                continue

        # Mesafeye göre sırala (en yakın / en alakalı en üstte)
        all_hits.sort(key=lambda x: x.get("distance", 0.0))
        return all_hits[:top_k]

    # ==========================================================================
    # 3. HAFIZADAN SİLME / DÜZELTME (DELETE & REVOKE)
    # ==========================================================================

    def delete_memory_fact(self, fact_id: str, entity_id: str) -> str:
        """Hafıza kaydını iptal eder ve ChromaDB koleksiyonlarından siler."""
        facts = self.load_entity_facts(entity_id)
        found = False
        target_content = ""

        for f in facts:
            if f.fact_id == fact_id:
                f.status = FactStatus.REVOKED
                f.updated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                target_content = f.content
                found = True
                break

        if not found:
            return f"Hata: `{entity_id}` varlığında `{fact_id}` ID'li bir hafıza kaydı bulunamadı."

        self.save_entity_facts(entity_id, facts)
        self._delete_vector(fact_id)

        return f"✓ Hafıza kaydı başarıyla silindi ve geçersiz kılındı:\n- ID: `{fact_id}`\n- İçerik: \"{target_content}\""

    # ==========================================================================
    # 4. OTURUM SONU ÖZETİ VE BAŞLANGIÇ BAĞLAMI
    # ==========================================================================

    def get_last_session_summary(self) -> str:
        """Açılışta sisteme enjekte edilecek son oturum özetini okur."""
        if settings.LAST_SESSION_SUMMARY_FILE.exists():
            try:
                return settings.LAST_SESSION_SUMMARY_FILE.read_text(encoding="utf-8").strip()
            except Exception:
                return ""
        return ""

    def save_last_session_summary(self, summary_text: str):
        """Kapanışta üretilen yeni oturum özetini kaydeder."""
        settings.LAST_SESSION_SUMMARY_FILE.parent.mkdir(parents=True, exist_ok=True)
        settings.LAST_SESSION_SUMMARY_FILE.write_text(summary_text.strip(), encoding="utf-8")

# Global Tekil Hafıza Motoru
memory_engine = MemoryEngine()
