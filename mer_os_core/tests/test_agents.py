"""
MER_OS v2 — Alt Ajanlar ve Araçlar Birim Testleri
"""
import sys
import unittest
from pathlib import Path

# Proje dizinini sys.path'e ekle
CURRENT_DIR = Path(__file__).resolve().parent.parent
if str(CURRENT_DIR) not in sys.path:
    sys.path.insert(0, str(CURRENT_DIR))

from tools.document_tools import read_document, list_input_files, search_in_document
from tools.report_tools import write_report, parse_report_payload, read_report_template
from tools.code_tools import write_script, run_script, check_syntax
from core.message_types import AgentTask, AgentResponse
from agents.report_writer import ReportWriterAgent
from agents.memory_curator import MemoryCuratorAgent
from config.settings import settings

class TestV2ToolsAndAgents(unittest.TestCase):
    
    def test_code_tools_write_and_run(self):
        """Python script yazma, AST kontrolü ve subprocess çalıştırma testi."""
        test_code = """import math
val = math.sqrt(144)
print(f"CALC_RESULT:{int(val)}")
"""
        write_res = write_script("test_math_calc.py", test_code)
        self.assertTrue(write_res["success"], f"Script yazılamadı: {write_res.get('error')}")

        syntax_res = check_syntax(test_code)
        self.assertIn("AST Passed", syntax_res)

        run_res = run_script("test_math_calc.py")
        self.assertTrue(run_res["success"], f"Script çalıştırılamadı: {run_res.get('stderr')}")
        self.assertEqual(run_res["stdout"], "CALC_RESULT:12")

    def test_report_tools_write(self):
        """Rapor yazma ve şablon testi."""
        sample_report = "# Test Raporu\n- Madde 1\n- Madde 2"
        res = write_report("test_user/test_report.md", sample_report)
        self.assertTrue(res.startswith("✓ Rapor başarıyla kaydedildi"))

        saved_file = settings.OUTPUT_DIR / "test_user" / "test_report.md"
        self.assertTrue(saved_file.exists())

        template = read_report_template("daily_report")
        self.assertIn("Günlük Faaliyet Raporu", template)

    def test_report_writer_agent_execution(self):
        """ReportWriterAgent'ın dökümanı okuyup output klasörüne rapor kaydettiğinin testi."""
        # 1. Girdi için geçici test dökümanı oluştur
        test_input_file = settings.INPUT_DIR / "ornek_faaliyet.md"
        test_input_file.write_text("# 10 Ağustos Montaj Notları\n- Şasi montajı bitti.\n- M12 cıvata stoğu 150.", encoding="utf-8")

        agent = ReportWriterAgent()
        task = AgentTask(
            target_agent="report_writer",
            instruction="ornek_faaliyet.md dosyasını oku ve Yağız için 10.08.2026 raporu oluştur.",
            payload={
                "source_file": "ornek_faaliyet.md",
                "user_name": "Yağız",
                "date_str": "10.08.2026"
            }
        )

        resp = agent.run(task)
        self.assertTrue(resp.success, f"ReportWriter hatası: {resp.error}")
        
        # Çıktı dosyasının sandbox/output altında oluştuğunu doğrula
        expected_output = settings.OUTPUT_DIR / "Yağız" / "10.08.2026_raporu.md"
        self.assertTrue(expected_output.exists(), f"Rapor dosyası kaydedilmedi: {expected_output}")

    def test_knowledge_indexer_action(self):
        """MemoryCuratorAgent döküman indeksleme (Knowledge Indexer) testi."""
        agent = MemoryCuratorAgent()
        task = AgentTask(
            target_agent="memory_curator",
            instruction="Dökümanları ChromaDB'ye indeksle",
            payload={"action": "index_documents"}
        )
        resp = agent.run(task)
        msg = resp.data.get("message", "").lower()
        self.assertTrue(any(w in msg for w in ["indekslendi", "atlandı", "tamamlandı", "güncel"]))

if __name__ == "__main__":
    unittest.main()
