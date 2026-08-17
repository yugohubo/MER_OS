"""
MER_OS v2 — Canlı Çoklu Ajan Terminal Arayüzü (CLI Entry Point)
Arayüz Orkestrasyonu, Canlı Token Streaming, Sıralı Boru Hatları (Pipelines), İnteraktif Onay Kapısı (HITL) ve JSONL Hafıza Hattı
"""
import sys
import os
from pathlib import Path

# Windows Konsol UTF-8 Desteği
try:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

# Proje dizinini sys.path'e ekle
CURRENT_DIR = Path(__file__).resolve().parent
if str(CURRENT_DIR) not in sys.path:
    sys.path.insert(0, str(CURRENT_DIR))

from config.settings import settings
from config.agents import AGENTS_CONFIG
from core.orchestrator import Orchestrator
from tools.memory_tools import memory_engine

def print_banner():
    print("=" * 75)
    print("🤖 MER_OS v2 — Çoklu Ajanlı Kurumsal Zeka & Otonom Hafıza Sistemi")
    print("=" * 75)
    print(f"• Arayüz Modeli   : {AGENTS_CONFIG['orchestrator'].model}")
    print(f"• Mimari          : Saf Python Hub & Spoke (5 Bağımsız Uzman Ajan & Pipeline)")
    print(f"• Boru Hattı      : Döküman Çözücü (Info Solver) ➔ Rapor Yazıcı (Report Writer)")
    print(f"• Hafıza Katmanı  : 4 Katmanlı (ChromaDB + Semantik MD + Canlı JSONL + Özet)")
    print(f"• Güvenlik/Kontrol: Human-in-the-Loop (İnteraktif Onay Kapısı)")
    print(f"• Çalışma Alanı   : v2/sandbox/")
    print("• Çıkış           : 'q', 'exit' veya 'quit'")
    print("=" * 75 + "\n")

def main():
    print_banner()

    orchestrator = Orchestrator()

    # Önceki Oturum Özeti Bildirimi
    last_summary = memory_engine.get_last_session_summary()
    if last_summary:
        print("📋 [Önceki Oturumdan Hatırlanan Başlangıç Bağlamı]:")
        for line in last_summary.strip().splitlines()[:5]:
            print(f"   {line}")
        print("   ...\n" + "─" * 75 + "\n")

    try:
        while True:
            user_input = input("\n[Siz] >> ").strip()
            if not user_input:
                continue

            if user_input.lower() in ["q", "exit", "quit"]:
                break

            print(f"\n[MER_OS] >> ", end="", flush=True)

            # Arayüz Ajanının Canlı Yanıtını Akıt
            response_chunks = []
            for chunk in orchestrator.stream_orchestrator_turn(user_input):
                sys.stdout.write(chunk)
                sys.stdout.flush()
                response_chunks.append(chunk)

            full_response = "".join(response_chunks).strip()
            print()

            # Delege veya Boru Hattı İsteği Kontrolü
            delegation_req = orchestrator.parse_delegation_intent(full_response)
            if delegation_req:
                is_pipeline = delegation_req.target_agent in ["doc_report_pipeline", "info_solver+report_writer"]
                target_label = "INFO_SOLVER ➔ REPORT_WRITER (Sıralı Boru Hattı)" if is_pipeline else delegation_req.target_agent.upper()

                print("\n" + "─" * 65)
                print(f"⚡ [ALT AJAN ÇALIŞTIRMA ONAYI]")
                print(f"🎯 Hedef      : {target_label}")
                print(f"📌 Görev Özeti: {delegation_req.action_summary}")
                print("─" * 65)
                print(" [1] Evet, İşi Başlat (Varsayılan)")
                print(" [2] Hayır, İptal Et ve Alternatif Sor")
                
                choice = input("\n[Seçiminiz (1/2)] >> ").strip()

                if choice in ["2", "hayır", "hayir", "no", "h", "n"]:
                    print("\n[MER_OS] >> ", end="", flush=True)
                    for chunk in orchestrator.handle_rejection(delegation_req):
                        sys.stdout.write(chunk)
                        sys.stdout.flush()
                    print()
                else:
                    # EVET Seçildi -> Alt Ajanı / Pipeline'ı Çalıştır
                    if not is_pipeline:
                        print(f"\n⚙️ [{delegation_req.target_agent.upper()} Ajanı Çalıştırılıyor...]")
                    
                    agent_resp = orchestrator.execute_delegation(delegation_req)
                    
                    if agent_resp.success:
                        print(f"✓ [{target_label} Görevini Başarıyla Tamamladı]\n")
                    else:
                        print(f"⚠️ [{target_label} Hatayla Sonuçlandı: {agent_resp.error}]\n")

                    # Sonucu Arayüz ile Kullanıcıya Sentezle
                    print("[MER_OS] >> ", end="", flush=True)
                    for chunk in orchestrator.synthesize_agent_result(delegation_req, agent_resp):
                        sys.stdout.write(chunk)
                        sys.stdout.flush()
                    print()

    except KeyboardInterrupt:
        print("\n\nOturum kullanıcı tarafından sonlandırıldı.")
    except Exception as e:
        print(f"\nBeklenmeyen Çalışma Hatası: {str(e)}")
    finally:
        # Oturum Kapanışında Canlı JSONL Mühürleme & Tek Geçişli Hafıza Süzme
        print("\n" + "─" * 75)
        print("💾 Oturum kapatılıyor, transkript kaydediliyor ve hafıza süzülüyor...")
        res = orchestrator.close_session()
        print(f"✓ Epizodik Kayıt: {Path(res['transcript_file']).name}")
        curation_data = res.get("curation_data")
        if isinstance(curation_data, dict):
            extracted = curation_data.get("extracted_facts_count", 0)
            entities = curation_data.get("entities_updated", [])
            print(f"✓ Semantik & Vektör Hafıza Güncellendi ({extracted} gerçek süzüldü -> {entities})")
            print("✓ Bir sonraki açılış için 'last_session_summary.md' hazırlandı.")
        print("MER_OS v2 başarıyla mühürlendi. İyi çalışmalar dileriz!\n")

if __name__ == "__main__":
    main()
