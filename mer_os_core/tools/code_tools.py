"""
MER_OS v2 — Güvenli Python Betik Üretim ve Yürütme Araçları (Code Synthesizer Tools)
Dosyaya Yaz -> AST Sözdizimi Kontrolü -> İzole Subprocess Çalıştırma Modeli
"""
import os
import sys
import ast
import subprocess
import time
from pathlib import Path
from typing import Dict, Any, List, Optional
from config.settings import settings

def write_script(script_name: str, code: str) -> Dict[str, Any]:
    """
    Python kodunu sandbox/scripts/ dizini altına .py dosyası olarak yazar.
    Yazmadan önce AST ile Python sözdizimi doğrulaması yapar.
    """
    if not script_name.endswith(".py"):
        script_name += ".py"

    # 1. Sözdizimi Kontrolü (Syntax Check)
    try:
        ast.parse(code)
    except SyntaxError as e:
        return {
            "success": False,
            "error": f"Sözdizimi Hatası (Satır {e.lineno}): {e.msg}\nKod:\n{e.text}",
            "script_path": None
        }

    # 2. Dosyayı sandbox/scripts altına kaydet
    target_file = settings.SCRIPTS_DIR / script_name
    target_file.parent.mkdir(parents=True, exist_ok=True)

    try:
        target_file.write_text(code.strip(), encoding="utf-8")
        rel_path = str(target_file.relative_to(settings.SANDBOX_DIR)).replace("\\", "/")
        return {
            "success": True,
            "message": f"✓ Betik başarıyla oluşturuldu: `sandbox/{rel_path}`",
            "script_name": script_name,
            "script_path": str(target_file)
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Dosya kaydetme hatası: {str(e)}",
            "script_path": None
        }

def check_syntax(code: str) -> str:
    """Python kodunun sözdizimini derlemeden doğrular."""
    try:
        ast.parse(code)
        return "✓ Kod sözdizimi geçerli (AST Passed)."
    except SyntaxError as e:
        return f"❌ Sözdizimi Hatası (Satır {e.lineno}): {e.msg}"

def run_script(script_name: str, args: Optional[List[str]] = None, timeout: Optional[int] = None) -> Dict[str, Any]:
    """
    sandbox/scripts/ altındaki belirtilen Python dosyasını izole alt süreçte çalıştırır.
    Çalışma dizini olarak sandbox/ kullanılır.
    """
    if not script_name.endswith(".py"):
        script_name += ".py"

    target_file = settings.SCRIPTS_DIR / script_name
    if not target_file.exists():
        return {
            "success": False,
            "error": f"Hata: '{script_name}' betiği bulunamadı. Lütfen önce `write_script` ile oluşturun.",
            "stdout": "",
            "stderr": ""
        }

    timeout_secs = timeout or settings.SUBPROCESS_TIMEOUT_SECONDS
    cmd = [sys.executable, str(target_file)]
    if args:
        cmd.extend(args)

    start_time = time.time()
    try:
        process = subprocess.run(
            cmd,
            cwd=str(settings.SANDBOX_DIR),
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=timeout_secs
        )
        elapsed = round(time.time() - start_time, 3)

        return {
            "success": process.returncode == 0,
            "returncode": process.returncode,
            "stdout": process.stdout.strip(),
            "stderr": process.stderr.strip(),
            "elapsed_seconds": elapsed,
            "executed_file": script_name
        }
    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "error": f"Zaman Aşımı Hatası: Betik {timeout_secs} saniye içinde tamamlanamadı ve durduruldu.",
            "stdout": "",
            "stderr": "",
            "elapsed_seconds": timeout_secs,
            "executed_file": script_name
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Çalıştırma Hatası: {str(e)}",
            "stdout": "",
            "stderr": "",
            "elapsed_seconds": 0,
            "executed_file": script_name
        }
