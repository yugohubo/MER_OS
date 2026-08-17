"""
MER_OS v2 — İzole 4 Katmanlı Hafıza Yaşam Döngüsü ve Silme Testleri
Mock Geçici Dizin Kullanılarak Gerçek Hafıza Asla Kirletilmez!
"""
import sys
import shutil
import tempfile
import unittest
from pathlib import Path

# Proje dizinini sys.path'e ekle
CURRENT_DIR = Path(__file__).resolve().parent.parent
if str(CURRENT_DIR) not in sys.path:
    sys.path.insert(0, str(CURRENT_DIR))

from tools.memory_tools import MemoryEngine
from core.message_types import MemoryFact, FactCategory, FactStatus

class TestV2MemoryLifecycle(unittest.TestCase):
    
    def setUp(self):
        """Her test için geçici izole bir klasör oluşturur."""
        self.test_dir = Path(tempfile.mkdtemp(prefix="mer_os_mem_test_"))
        self.chroma_dir = self.test_dir / "chroma_db"
        self.semantic_dir = self.test_dir / "semantic"
        
        self.memory = MemoryEngine(
            chroma_dir=self.chroma_dir,
            semantic_dir=self.semantic_dir
        )

    def tearDown(self):
        """Test bitiminde geçici klasörü tamamen temizler."""
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_fact_creation_and_curated_markdown(self):
        """Gerçek ekleme ve Curated Markdown üretimi testi."""
        entity = "project:chassis"
        facts = [
            MemoryFact(
                entity_id=entity,
                category=FactCategory.DECISION,
                content="Şasi malzemesi 6061-T6 Alüminyum olarak seçildi."
            ),
            MemoryFact(
                entity_id=entity,
                category=FactCategory.CONSTRAINT,
                content="Maksimum toplam şasi ağırlığı 14.5 kg sınırını aşamaz."
            )
        ]

        self.memory.save_entity_facts(entity, facts)

        # Dosyaların varlığını kontrol et
        md_file = self.semantic_dir / "project_chassis.md"
        json_file = self.semantic_dir / "project_chassis.json"

        self.assertTrue(md_file.exists())
        self.assertTrue(json_file.exists())

        md_content = md_file.read_text(encoding="utf-8")
        self.assertIn("6061-T6 Alüminyum", md_content)
        self.assertIn("14.5 kg", md_content)

    def test_conflict_resolution(self):
        """Çelişki çözümü: Eski bilginin SUPERSEDED yapılması testi."""
        entity = "project:chassis"
        
        # 1. İlk Karar: M10 Cıvata
        fact1 = MemoryFact(
            fact_id="f_1",
            entity_id=entity,
            category=FactCategory.DECISION,
            content="Ana bağlantılarda M10 paslanmaz cıvata kullanılacak."
        )
        self.memory.merge_facts_with_conflict_resolution(entity, [fact1])

        # 2. Revize Karar: M12 Cıvata
        fact2 = MemoryFact(
            fact_id="f_2",
            entity_id=entity,
            category=FactCategory.DECISION,
            content="Ana bağlantılarda M12 paslanmaz cıvata kullanılacak."
        )
        all_facts = self.memory.merge_facts_with_conflict_resolution(entity, [fact2])

        # Doğrulama: fact1 SUPERSEDED olmalı, fact2 ACTIVE olmalı
        f1_saved = next(f for f in all_facts if f.fact_id == "f_1")
        f2_saved = next(f for f in all_facts if f.fact_id == "f_2")

        self.assertEqual(f1_saved.status, FactStatus.SUPERSEDED)
        self.assertEqual(f1_saved.superseded_by, "f_2")
        self.assertEqual(f2_saved.status, FactStatus.ACTIVE)

        # Curated Markdown içinde sadece M12 görünmeli
        md_content = (self.semantic_dir / "project_chassis.md").read_text(encoding="utf-8")
        self.assertIn("M12 paslanmaz cıvata", md_content)
        self.assertNotIn("M10 paslanmaz cıvata", md_content)

    def test_memory_deletion_and_revoke(self):
        """Hafızadan kullanıcı onayıyla kalıcı silme / revoke etme testi."""
        entity = "user:yagiz"
        fact = MemoryFact(
            fact_id="fact_wrong_123",
            entity_id=entity,
            category=FactCategory.PREFERENCE,
            content="Raporları daima Excel tablosu olarak ister."
        )
        self.memory.save_entity_facts(entity, [fact])

        # Silme aracını çalıştır
        del_msg = self.memory.delete_memory_fact("fact_wrong_123", entity)
        self.assertIn("başarıyla silindi", del_msg)

        # Doğrulama: Fact JSON'da REVOKED olmalı, Markdown'da hiç görünmemeli
        reloaded = self.memory.load_entity_facts(entity)
        self.assertEqual(reloaded[0].status, FactStatus.REVOKED)

        md_content = (self.semantic_dir / "user_yagiz.md").read_text(encoding="utf-8")
        self.assertNotIn("Excel tablosu olarak ister", md_content)

if __name__ == "__main__":
    unittest.main()
