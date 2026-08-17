"""
MER_OS v2 — Rapor Yazıcı ve Biçimlendirme Araçları
Kırılmaz Dosya Kayıtçısı ve Şablon Yöneticisi
"""
import os
import re
from pathlib import Path
from typing import Dict, Any, Optional
from config.settings import settings

def parse_report_payload(raw_input: Any) -> tuple:
    """write_report için JSON veya karmaşık string girdilerinden path ve content ayıklar."""
    if isinstance(raw_input, dict):
        p = raw_input.get("path") or raw_input.get("file") or raw_input.get("dosya") or "rapor.md"
        c = raw_input.get("content") or raw_input.get("icerik") or raw_input.get("text") or ""
        return str(p), str(c)

    text = str(raw_input).strip()
    
    # Regex ile esnek path ve content ayıklama
    p_match = re.search(r'["\']?path["\']?\s*:\s*["\']([^"\'\r\n]+)["\']', text)
    path = p_match.group(1) if p_match else "rapor.md"

    c_match = re.search(r'["\']?content["\']?\s*:\s*["\']?(.*)', text, re.DOTALL)
    content = ""
    if c_match:
        content = c_match.group(1)
        content = re.sub(r'["\']?\s*\}?\s*$', '', content)
        content = content.replace('\\n', '\n').replace('\\"', '"').replace('\\t', '\t')
    else:
        content = text

    return path, content

def write_report(file_path: str, content: str) -> str:
    """
    Raporu sandbox/output/ dizini altına güvenli ve dayanıklı bir şekilde yazar.
    """
    if not content or not content.strip():
        return "Hata: Rapor içeriği boş olamaz."

    # Yol temizleme ve sandbox/output altına yerleştirme
    clean_path = file_path.replace("\\", "/").strip().lstrip("/")
    if clean_path.startswith("sandbox/output/"):
        clean_path = clean_path[len("sandbox/output/"):]
    elif clean_path.startswith("output/"):
        clean_path = clean_path[len("output/"):]

    target_file = settings.OUTPUT_DIR / clean_path
    target_file.parent.mkdir(parents=True, exist_ok=True)

    try:
        target_file.write_text(content.strip(), encoding="utf-8")
        rel_path = str(target_file.relative_to(settings.SANDBOX_DIR)).replace("\\", "/")
        return f"✓ Rapor başarıyla kaydedildi: `sandbox/{rel_path}` ({len(content)} karakter)"
    except Exception as e:
        return f"Dosya yazma hatası: {str(e)}"

def read_report_template(template_name: str = "daily_report") -> str:
    """Standart kurumsal rapor şablonunu döner."""
    templates = {
        "daily_report": """# [Kişi veya Proje Adı] — [GG.AA.YYYY] Günlük Faaliyet Raporu

## 1. Tamamlanan Görevler & Operasyonlar
- ...

## 2. Karşılaşılan Sorunlar & Kritik Uyarılar (Stok, Tolerans, Gecikme)
- ...

## 3. Alınan Kararlar & Sonraki Adımlar
- ...
""",
        "technical_analysis": """# Teknik İnceleme ve Analiz Raporu

**Proje/Sistem:** [Sistem Adı]
**Tarih:** [GG.AA.YYYY]

## 1. Mevcut Durum ve Teknik İsterler
- ...

## 2. Parça & Malzeme BOM Listesi Değerlendirmesi
| Parça No | Tanım | Miktar | Durum / Not |
|---|---|---|---|
| ... | ... | ... | ... |

## 3. Riskler ve Mühendislik Tavsiyeleri
- ...
"""
    }
    return templates.get(template_name, templates["daily_report"])
