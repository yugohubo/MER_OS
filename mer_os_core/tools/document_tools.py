"""
MER_OS v2 — Döküman Okuma, Akıllı Eşleştirme, Meta Veri Çıkarma ve Başlık Kalıtımlı Parçalama (Semantic Section Chunker)
Fuzzy Match, Türkçe Normalizasyon, Yapısal Meta Veri Çıkarıcı ve Zengin Bağlam Parçalayıcısı
"""
import os
import re
import json
import unicodedata
from difflib import SequenceMatcher
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from config.settings import settings

def normalize_text(text: str) -> str:
    """Türkçe karakterleri ve noktalama işaretlerini eşleştirme için normalize eder."""
    tr_map = str.maketrans("ıİğĞüÜşŞöÖçÇ", "iIgGuUsSoOcC")
    normalized = text.translate(tr_map).lower()
    normalized = re.sub(r"[^a-z0-9]", " ", normalized)
    return " ".join(normalized.split())

def list_input_files(folder: Optional[Path] = None) -> List[Dict[str, Any]]:
    """Girdi klasöründeki mevcut dökümanları metaverileriyle listeler."""
    target_dir = folder or settings.INPUT_DIR
    if not target_dir.exists():
        return []
    
    files = []
    for f in target_dir.rglob("*"):
        if f.is_file():
            files.append({
                "name": f.name,
                "path": str(f),
                "relative_path": str(f.relative_to(settings.SANDBOX_DIR)).replace("\\", "/"),
                "size_kb": round(f.stat().st_size / 1024, 2),
                "extension": f.suffix.lower()
            })
    return files

def find_best_matching_document(query: str) -> Tuple[Optional[Path], float, str]:
    """
    Kullanıcının yazdığı serbest metinden sandbox/input/ altındaki en uygun dosyayı akıllıca eşleştirir.
    """
    files = [f for f in settings.INPUT_DIR.glob("*") if f.is_file()]
    if not files:
        return None, 0.0, "Girdi klasöründe (`sandbox/input/`) hiç dosya bulunamadı."

    clean_query = normalize_text(query)
    query_tokens = set(clean_query.split())

    best_match: Optional[Path] = None
    best_score = 0.0
    match_reason = ""

    for file_path in files:
        fname = file_path.name
        clean_fname = normalize_text(file_path.stem)
        fname_tokens = set(clean_fname.split())

        # 1. Birebir eşleşme
        if clean_fname == clean_query or fname.lower() == query.lower().strip():
            return file_path, 1.0, f"Tam dosya ismi eşleşmesi: '{fname}'"

        # 2. Token kesişim skoru
        common_tokens = query_tokens & fname_tokens
        token_score = len(common_tokens) / max(len(fname_tokens), 1) if fname_tokens else 0.0

        # 3. String benzerlik oranı
        seq_score = SequenceMatcher(None, clean_query, clean_fname).ratio()
        sub_score = 0.5 if clean_fname in clean_query or clean_query in clean_fname else 0.0
        total_score = max(token_score * 0.7 + seq_score * 0.3, sub_score, seq_score)

        if total_score > best_score:
            best_score = total_score
            best_match = file_path
            if common_tokens:
                match_reason = f"'{fname}' dosyası ile ortak anahtar kelimeler: {list(common_tokens)}"
            else:
                match_reason = f"'{fname}' dosyası ile anlamsal isim benzerliği (%{int(best_score*100)})"

    if best_score >= 0.30 and best_match:
        return best_match, best_score, f"Seçilen Dosya: '{best_match.name}' ({match_reason})"
    
    if len(files) == 1:
        return files[0], 0.5, f"Girdi klasöründe tek dosya mevcut olduğu için otomatik seçildi: '{files[0].name}'"

    available_names = [f.name for f in files]
    return None, best_score, f"Eşleşen dosya bulunamadı. Mevcut dosyalar: {available_names}"

def resolve_input_path(file_path: str) -> Path:
    """Verilen dosya yolunu veya serbest sorguyu akıllıca çözümler."""
    p = Path(file_path)
    if p.is_absolute() and p.exists():
        return p
    
    in_input = settings.INPUT_DIR / file_path
    if in_input.exists():
        return in_input
        
    matched_path, score, _ = find_best_matching_document(file_path)
    if matched_path and matched_path.exists():
        return matched_path

    return in_input

def read_document(file_path: str) -> str:
    """
    Belirtilen veya serbest metinle eşleşen PDF, Excel, CSV, TXT veya Markdown dökümanını okur.
    """
    resolved = resolve_input_path(file_path)
    if not resolved.exists():
        available = [f.name for f in settings.INPUT_DIR.glob("*") if f.is_file()]
        return f"Hata: '{file_path}' için uygun bir dosya bulunamadı. `sandbox/input/` içindeki mevcut dosyalar: {available}"

    suffix = resolved.suffix.lower()

    # 1. PDF Dökümanı Okuma
    if suffix == ".pdf":
        try:
            from pypdf import PdfReader
            reader = PdfReader(str(resolved))
            pages_text = []
            for idx, page in enumerate(reader.pages):
                txt = page.extract_text() or ""
                if txt.strip():
                    pages_text.append(f"## Sayfa {idx + 1}\n{txt.strip()}")
            return "\n\n".join(pages_text) if pages_text else "Uyarı: PDF dosyası okundu ancak içinde metin bulunamadı."
        except Exception as e:
            return f"PDF okuma hatası ({resolved.name}): {str(e)}"

    # 2. Excel / BOM Tablosu Okuma
    elif suffix in [".xlsx", ".xls"]:
        try:
            import pandas as pd
            excel_file = pd.ExcelFile(str(resolved))
            sheets_text = []
            for sheet in excel_file.sheet_names:
                df = pd.read_excel(excel_file, sheet_name=sheet)
                sheets_text.append(f"## Sayfa: {sheet}\n" + df.to_markdown(index=False))
            return "\n\n".join(sheets_text)
        except Exception as e:
            return f"Excel okuma hatası ({resolved.name}): {str(e)}"

    # 3. CSV Tablosu Okuma
    elif suffix == ".csv":
        try:
            import pandas as pd
            df = pd.read_csv(str(resolved))
            return f"## CSV Tablosu: {resolved.name}\n" + df.to_markdown(index=False)
        except Exception as e:
            return f"CSV okuma hatası ({resolved.name}): {str(e)}"

    # 4. JSON Dökümanı Okuma
    elif suffix == ".json":
        try:
            data = json.loads(resolved.read_text(encoding="utf-8"))
            return json.dumps(data, ensure_ascii=False, indent=2)
        except Exception as e:
            return f"JSON okuma hatası ({resolved.name}): {str(e)}"

    # 5. Düz Metin / Markdown Okuma
    else:
        try:
            return resolved.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            try:
                return resolved.read_text(encoding="latin-1")
            except Exception as e:
                return f"Metin okuma hatası ({resolved.name}): {str(e)}"

def search_in_document(query: str, file_path: str) -> str:
    """Belirtilen döküman içinde anahtar kelime veya regex araması yapar."""
    content = read_document(file_path)
    if content.startswith("Hata:"):
        return content

    lines = content.splitlines()
    matches = []
    pattern = re.compile(re.escape(query), re.IGNORECASE)
    
    for idx, line in enumerate(lines, 1):
        if pattern.search(line):
            start = max(0, idx - 2)
            end = min(len(lines), idx + 2)
            snippet = "\n".join([f"  {i}: {lines[i-1]}" for i in range(start + 1, end + 1)])
            matches.append(f"📌 Eşleşme (Satır {idx}):\n{snippet}")

    if not matches:
        return f"'{query}' sorgusu '{file_path}' dökümanı içinde bulunamadı."

    return f"🔍 '{file_path}' içinde {len(matches)} eşleşme bulundu:\n\n" + "\n\n".join(matches[:10])

# ==============================================================================
# 🧠 GELİŞMİŞ META VERİ ÇIKARMA VE BAŞLIK KALITIMLI PARÇALAYICI
# ==============================================================================

def extract_document_metadata(doc_name: str, content: str) -> Dict[str, Any]:
    """
    Döküman başlığı, tarihi, proje türü, yazarı ve donanım etiketlerini kural ve regex ile çıkarır.
    """
    meta: Dict[str, Any] = {
        "doc_name": doc_name,
        "doc_type": "technical_doc",
        "date": "2026-01-01",
        "year": 2026,
        "project": "general",
        "author": "Merkon",
        "hardware": ""
    }

    date_match = re.search(r"(\d{2})[.\-_/](\d{2})[.\-_/](\d{4})", doc_name + " " + content[:500])
    if date_match:
        meta["date"] = f"{date_match.group(3)}-{date_match.group(2)}-{date_match.group(1)}"
        meta["year"] = int(date_match.group(3))
    else:
        month_map = {
            "ocak": "01", "subat": "02", "mart": "03", "nisan": "04", "mayis": "05", "haziran": "06",
            "temmuz": "07", "agustos": "08", "ağustos": "08", "eylul": "09", "eylül": "09", "ekim": "10",
            "kasim": "11", "kasım": "11", "aralik": "12", "aralık": "12"
        }
        for m_name, m_num in month_map.items():
            if m_name in doc_name.lower():
                day_match = re.search(r"(\d{1,2})", doc_name)
                day = f"{int(day_match.group(1)):02d}" if day_match else "01"
                meta["date"] = f"2026-{m_num}-{day}"
                meta["year"] = 2026
                break

    text_sample = (doc_name + " " + content[:1000]).lower()
    if any(k in text_sample for k in ["faaliyet raporu", "günlük rapor", "gunluk rapor", "raporu"]):
        meta["doc_type"] = "daily_report"
    elif any(k in text_sample for k in ["bom", "parça listesi", "malzeme listesi", "parca"]):
        meta["doc_type"] = "bom_list"
    elif any(k in text_sample for k in ["şema", "sema", "eplan", "elektrik", "hidrolik"]):
        meta["doc_type"] = "schematic_spec"
    elif any(k in text_sample for k in ["test", "protokol", "kalibrasyon"]):
        meta["doc_type"] = "test_report"

    if any(k in text_sample for k in ["telemetri", "telemetry", "aar", "iot", "switch", "edge pc"]):
        meta["project"] = "telemetry"
    elif any(k in text_sample for k in ["şasi", "sasi", "chassis", "gövde"]):
        meta["project"] = "chassis"
    elif any(k in text_sample for k in ["hidrolik", "valf", "pompa", "basınç", "bar"]):
        meta["project"] = "hydraulic_unit"
    elif any(k in text_sample for k in ["kalıp", "kalip", "pres"]):
        meta["project"] = "mold_system"

    if any(k in text_sample for k in ["yağız", "yagiz"]):
        meta["author"] = "Yağız"

    known_hardware = [
        "Eaton", "RevPi", "Advantech", "Kunbus", "Siemens", "Codesys",
        "EtherNet/IP", "PLC", "HMI", "CANbus", "MQTT", "Mosquitto"
    ]
    found_hw = [hw for hw in known_hardware if hw.lower() in text_sample]
    if found_hw:
        meta["hardware"] = ",".join(found_hw)

    return meta

def semantic_section_chunker(
    doc_name: str,
    content: str,
    base_metadata: Optional[Dict[str, Any]] = None,
    max_chunk_size: int = 800
) -> List[Dict[str, Any]]:
    """
    Dökümanı Markdown başlıklarına (`#`, `##`, `###`) ve mantıksal bölümlere ayırır.
    Her parçaya hiyerarşik bağlam başlığı (Context Header) ekler ve zengin meta verilerle donatır.
    """
    if not content or not content.strip():
        return []

    meta = dict(base_metadata or extract_document_metadata(doc_name, content))
    
    sections = re.split(r'(?=\n#{1,3}\s+)', content)
    chunks: List[Dict[str, Any]] = []

    current_main_header = Path(doc_name).stem

    for sec in sections:
        clean_sec = sec.strip()
        if not clean_sec:
            continue

        header_match = re.search(r'^#{1,3}\s+(.+)', clean_sec)
        if header_match:
            current_main_header = header_match.group(1).strip()
            section_body = re.sub(r'^#{1,3}\s+.+\n?', '', clean_sec).strip()
        else:
            section_body = clean_sec

        if not section_body:
            continue

        if len(section_body) > max_chunk_size:
            paras = section_body.split("\n\n")
            current_sub = []
            curr_len = 0
            for p in paras:
                p_clean = p.strip()
                if not p_clean:
                    continue
                if curr_len + len(p_clean) > max_chunk_size and current_sub:
                    sub_text = "\n\n".join(current_sub)
                    enriched = f"[{doc_name} > {current_main_header}]\n{sub_text}"
                    chunk_meta = dict(meta)
                    chunk_meta["section"] = current_main_header
                    chunk_meta["chunk_idx"] = len(chunks)
                    chunks.append({"text": enriched, "metadata": chunk_meta})
                    current_sub = [p_clean]
                    curr_len = len(p_clean)
                else:
                    current_sub.append(p_clean)
                    curr_len += len(p_clean)
            if current_sub:
                sub_text = "\n\n".join(current_sub)
                enriched = f"[{doc_name} > {current_main_header}]\n{sub_text}"
                chunk_meta = dict(meta)
                chunk_meta["section"] = current_main_header
                chunk_meta["chunk_idx"] = len(chunks)
                chunks.append({"text": enriched, "metadata": chunk_meta})
        else:
            enriched = f"[{doc_name} > {current_main_header}]\n{section_body}"
            chunk_meta = dict(meta)
            chunk_meta["section"] = current_main_header
            chunk_meta["chunk_idx"] = len(chunks)
            chunks.append({"text": enriched, "metadata": chunk_meta})

    return chunks
