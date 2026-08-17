"""
MER_OS v2 — Uçtan Uca Çoklu Ajan ve Orkestrasyon Entegrasyon Testi (E2E Integration Test)
"""
import sys
import unittest
from pathlib import Path

# Proje dizinini sys.path'e ekle
CURRENT_DIR = Path(__file__).resolve().parent.parent
if str(CURRENT_DIR) not in sys.path:
    sys.path.insert(0, str(CURRENT_DIR))

from core.orchestrator import Orchestrator
from core.message_types import DelegationRequest, AgentTask
from tools.memory_tools import memory_engine

class TestV2E2EIntegration(unittest.TestCase):
    
    def test_startup_context_loaded(self):
        """Orchestrator açılışta son oturum özetini context'e ekliyor mu?"""
        orch = Orchestrator(user_id="user:test")
        sys_msg = orch.messages[0]["content"]
        self.assertIn("MER_OS v2'nin Arayüz ve Koordinasyon Ajanısın", sys_msg)
        
        last_summary = memory_engine.get_last_session_summary()
        if last_summary:
            self.assertIn("Önceki Oturumdan Aktarılan Bağlam", sys_msg)

    def test_delegation_execution_and_synthesis(self):
        """Alt ajana görev delege etme, çalıştırma ve yanıt sentezi testi."""
        orch = Orchestrator(user_id="user:test")

        del_req = DelegationRequest(
            target_agent="code_runner",
            action_summary="Kritik flanş basınç testi hesaplaması",
            payload={
                "instruction": "Bir flanşın 250 bar basınçtaki cıvata gerilmesini hesapla",
                "script_name": "flans_test.py",
                "raw_code": "p = 250\narea = 12.5\nforce = p * area\nprint(f'TOTAL_FORCE:{force}')"
            }
        )

        resp = orch.execute_delegation(del_req)
        self.assertTrue(resp.success, f"Delege başarısız: {resp.error}")
        self.assertIn("TOTAL_FORCE:3125.0", resp.data.get("stdout", ""))

        events = [e for e in orch.transcript.entries if e.role == "agent_event"]
        self.assertGreaterEqual(len(events), 2)
        self.assertEqual(events[0].agent_name, "code_runner")

        # JSONL dosyasının anında oluşturulduğunu ve satır satır yazıldığını doğrula
        self.assertTrue(orch.transcript_file.exists())
        lines = orch.transcript_file.read_text(encoding="utf-8").strip().splitlines()
        self.assertGreaterEqual(len(lines), 2)

if __name__ == "__main__":
    unittest.main()
