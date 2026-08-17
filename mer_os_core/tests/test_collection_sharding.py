"""
MER_OS v2 — Ay ve Kategori Bazlı ChromaDB Koleksiyon Bölümleme Testleri (Collection Partitioning)
"""
import sys
import unittest
from pathlib import Path

# Proje dizinini sys.path'e ekle
CURRENT_DIR = Path(__file__).resolve().parent.parent
if str(CURRENT_DIR) not in sys.path:
    sys.path.insert(0, str(CURRENT_DIR))

from tools.memory_tools import memory_engine, get_collection_name_for_date
from agents.memory_curator import parse_query_metadata_filters

class TestCollectionPartitioning(unittest.TestCase):
    
    def test_collection_name_resolution(self):
        """Tarih ve döküman tipine göre koleksiyon adı çözümleme testi."""
        self.assertEqual(get_collection_name_for_date("2026-08-10", "daily_report"), "mer_os_2026_08")
        self.assertEqual(get_collection_name_for_date("2026-09-01", "daily_report"), "mer_os_2026_09")
        self.assertEqual(get_collection_name_for_date(None, "bom_list"), "mer_os_boms")
        self.assertEqual(get_collection_name_for_date(None, "sop_spec"), "mer_os_core")

    def test_query_collection_routing(self):
        """Kullanıcı sorgusundan hedef koleksiyon tespit testi."""
        _, col1 = parse_query_metadata_filters("Ağustos 2026 raporlarındaki kararlar")
        self.assertEqual(col1, "mer_os_2026_08")

        _, col2 = parse_query_metadata_filters("Şasi montaj BOM parça listesi")
        self.assertEqual(col2, "mer_os_boms")

    def test_partitioned_upsert_and_search(self):
        """Ay bazlı koleksiyona yazma ve izole arama testi."""
        chunks = [
            {
                "text": "[2026_08_rapor.md > Donanım] Ağustos 2026'da Eaton switch devreye alındı.",
                "metadata": {"date": "2026-08-10", "doc_type": "daily_report", "doc_name": "2026_08_rapor.md"}
            }
        ]
        
        # 'mer_os_2026_08' koleksiyonuna kaydet
        saved = memory_engine.upsert_document_chunks(chunks, doc_name="2026_08_rapor.md")
        self.assertEqual(saved, 1)

        # Koleksiyon listesinde yer aldığını doğrula
        collections = memory_engine.list_collections()
        self.assertIn("mer_os_2026_08", collections)

        # Sadece bu ay koleksiyonundan arama yap
        hits = memory_engine.search_vector_memory(
            query="Eaton switch",
            target_collection="mer_os_2026_08"
        )
        self.assertGreaterEqual(len(hits), 1)
        self.assertEqual(hits[0]["collection"], "mer_os_2026_08")
        self.assertIn("Eaton", hits[0]["content"])

if __name__ == "__main__":
    unittest.main()
