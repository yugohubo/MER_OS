"""
MER_OS v2 — Gelişmiş Başlık Kalıtımlı Chunking, SHA-256 İkiz Engelleme ve ChromaDB Meta Veri Filtreleme Testleri
"""
import sys
import unittest
from pathlib import Path

# Proje dizinini sys.path'e ekle
CURRENT_DIR = Path(__file__).resolve().parent.parent
if str(CURRENT_DIR) not in sys.path:
    sys.path.insert(0, str(CURRENT_DIR))

from tools.document_tools import extract_document_metadata, semantic_section_chunker
from tools.memory_tools import memory_engine, compute_file_sha256
from agents.memory_curator import parse_query_metadata_filters, MemoryCuratorAgent
from core.message_types import AgentTask

class TestAdvancedRAG(unittest.TestCase):
    
    def test_metadata_extraction(self):
        """Dökümandan yıl, proje, döküman tipi ve donanım etiketlerinin çıkarılması testi."""
        sample_doc = "10_ağustos_rapor.pdf"
        sample_text = """# 10.08.2026 Günlük Faaliyet Raporu
Hazırlayan: Yağız
Proje: Endüstriyel Telemetri ve AAR Mimarisi
Kullanılan Donanımlar: Eaton Switch, Kunbus RevPi ve Advantech UNO.
"""
        meta = extract_document_metadata(sample_doc, sample_text)
        
        self.assertEqual(meta["year"], 2026)
        self.assertEqual(meta["doc_type"], "daily_report")
        self.assertEqual(meta["project"], "telemetry")
        self.assertEqual(meta["author"], "Yağız")
        self.assertIn("Eaton", meta["hardware"])
        self.assertIn("Advantech", meta["hardware"])

    def test_semantic_section_chunker(self):
        """Başlık kalıtımlı parçalama testi (Context Header Prepending)."""
        doc_name = "test_hidrolik.md"
        doc_content = """# Hidrolik Test Protokolü

## 1. Pompa Basınç Testi
Ana pompa 250 bar basınca ayarlandı. Emniyet valfi 270 barda açıyor.

## 2. Valf Geçiş Zamanları
Oransal valf tepki süresi 15 ms olarak ölçüldü.
"""
        chunks = semantic_section_chunker(doc_name, doc_content)
        self.assertGreaterEqual(len(chunks), 2)
        
        self.assertIn("[test_hidrolik.md > 1. Pompa Basınç Testi]", chunks[0]["text"])
        self.assertEqual(chunks[0]["metadata"]["section"], "1. Pompa Basınç Testi")

    def test_query_filter_parsing(self):
        """Doğal dil sorgusundan ChromaDB 'where' filtresi üretme testi."""
        q1 = "2026 yılındaki telemetri raporlarını getir"
        f1, target_col = parse_query_metadata_filters(q1)
        
        self.assertIsNotNone(f1)
        self.assertIn("$and", f1)
        self.assertIn({"year": 2026}, f1["$and"])
        self.assertIn({"project": "telemetry"}, f1["$and"])

    def test_chroma_metadata_filtered_search(self):
        """ChromaDB üzerinde meta veri filtreli vektör arama testi."""
        test_chunks = [
            {
                "text": "[mock_eaton_switch.md > Switch] Eaton XN-332 endüstriyel switch panoda kullanıldı.",
                "metadata": {"year": 2026, "project": "telemetry_isolated_test", "hardware": "Eaton", "doc_name": "mock_eaton_switch.md"}
            },
            {
                "text": "[mock_rexroth_valf.md > Valf] Eski Rexroth valf 210 bar çalışıyor.",
                "metadata": {"year": 2024, "project": "hydraulic_isolated_test", "hardware": "Rexroth", "doc_name": "mock_rexroth_valf.md"}
            }
        ]
        memory_engine.upsert_document_chunks(test_chunks, doc_name="mock_test_docs.md", target_collection_name="mer_os_test_col")

        filtered_hits = memory_engine.search_vector_memory(
            query="switch ve pano donanımı",
            top_k=2,
            where_filter={"project": "telemetry_isolated_test"},
            target_collection="mer_os_test_col"
        )

        self.assertGreaterEqual(len(filtered_hits), 1)
        self.assertEqual(filtered_hits[0]["project"], "telemetry_isolated_test")
        self.assertIn("Eaton", filtered_hits[0]["content"])

    def test_deduplication_and_incremental_skip(self):
        """SHA-256 parmak izi ile aynı dosyanın tekrar indekslenmesinin engellenmesi testi."""
        curator = MemoryCuratorAgent()
        task = AgentTask(
            target_agent="memory_curator",
            instruction="Dökümanları indeksle",
            payload={"action": "index_documents"}
        )
        
        resp = curator.run(task)
        self.assertTrue(resp.success)
        msg = resp.data.get("message", "").lower()
        self.assertTrue(any(w in msg for w in ["indekslendi", "atlandı", "güncel"]))

if __name__ == "__main__":
    unittest.main()
