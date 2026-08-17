"""
MER_OS v2 — Sıralı Çoklu Ajan Boru Hattı Testi (Pipeline Integration Test)
Info Solver ➔ Report Writer
"""
import sys
import unittest
from pathlib import Path

# Proje dizinini sys.path'e ekle
CURRENT_DIR = Path(__file__).resolve().parent.parent
if str(CURRENT_DIR) not in sys.path:
    sys.path.insert(0, str(CURRENT_DIR))

from core.orchestrator import Orchestrator
from core.message_types import DelegationRequest

class TestV2Pipeline(unittest.TestCase):
    
    def test_doc_report_pipeline_execution(self):
        """Döküman çözme ve kurumsal raporlama boru hattı testi."""
        orch = Orchestrator(user_id="user:test")

        del_req = DelegationRequest(
            target_agent="doc_report_pipeline",
            action_summary="10 Ağustos faaliyet dökümanını incele ve raporla.",
            payload={
                "source_file": "10_ağustos_rapor.pdf",
                "user_name": "Yağız",
                "date_str": "10.08.2026"
            }
        )

        resp = orch.execute_delegation(del_req)
        self.assertTrue(resp.success, f"Pipeline hatası: {resp.error}")
        self.assertIn("info_solver -> report_writer", resp.data.get("pipeline", ""))
        self.assertTrue(Path(resp.data.get("saved_path")).exists())

        # Transkriptte her iki ajanın da olayı kaydedilmiş mi?
        events = [e for e in orch.transcript.entries if e.role == "agent_event"]
        self.assertTrue(any(e.agent_name == "info_solver" for e in events))
        self.assertTrue(any(e.agent_name == "report_writer" for e in events))

if __name__ == "__main__":
    unittest.main()
