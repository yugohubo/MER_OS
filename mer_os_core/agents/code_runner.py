"""
MER_OS v2 — Kod ve Araç Yazıcı Ajanı (Code Synthesizer & Runner Agent)
Dinamik Python betikleri üretir, sandbox/scripts altına yazar ve izole subprocess'te çalıştırır.
"""
import re
from typing import Dict, Any
from core.base_agent import BaseAgent
from core.message_types import AgentTask, AgentResponse
from tools.code_tools import write_script, run_script

class CodeRunnerAgent(BaseAgent):
    def __init__(self):
        super().__init__("code_runner")

    def run(self, task: AgentTask) -> AgentResponse:
        """
        Görevi yürütür.
        Payload:
          - instruction: str (Yapılacak hesaplama veya işlem)
          - script_name: str (Opsiyonel betik adı, örn: calculate_stress.py)
          - raw_code: str (Varsa doğrudan çalıştırılacak Python kodu)
        """
        payload = task.payload or {}
        instruction = payload.get("instruction") or task.instruction
        script_name = payload.get("script_name") or "dynamic_task.py"
        raw_code = payload.get("raw_code")

        # 1. Kod verilmemişse LLM ile Python kodu üret
        if not raw_code:
            prompt = f"""Aşağıdaki işlem veya hesaplama için tam, bağımsız ve güvenli bir Python betiği yaz.

## İstenen Görev:
{instruction}

## Kurallar:
1. SADECE Python kod bloğu üret. Başka hiçbir açıklama, selamlama veya metin yazma.
2. Kodun ürettiği sonucu `print()` ile standart çıktıya net bir şekilde yazdır.
3. Gerekli importları eksiksiz yap (math, os, sys, json, pandas vb.).
4. Hataları try-except bloklarıyla yakala.
"""
            llm_code_response = self.call_llm(prompt)
            
            # Markdown bloklarını temizle
            cleaned_code = re.sub(r"^```(?:python)?\s*", "", llm_code_response.strip())
            cleaned_code = re.sub(r"\s*```$", "", cleaned_code).strip()
        else:
            cleaned_code = raw_code.strip()

        # 2. Betiği sandbox/scripts/ altına kaydet (AST sözdizimi kontrolü ile)
        write_res = write_script(script_name=script_name, code=cleaned_code)
        if not write_res["success"]:
            return AgentResponse(
                task_id=task.task_id,
                source_agent=self.name,
                success=False,
                error=f"Betik oluşturulamadı: {write_res.get('error')}"
            )

        # 3. Betiği izole subprocess olarak çalıştır
        exec_res = run_script(script_name=script_name)

        return AgentResponse(
            task_id=task.task_id,
            source_agent=self.name,
            success=exec_res["success"],
            data={
                "script_name": script_name,
                "code": cleaned_code,
                "stdout": exec_res.get("stdout"),
                "stderr": exec_res.get("stderr"),
                "elapsed_seconds": exec_res.get("elapsed_seconds"),
                "returncode": exec_res.get("returncode")
            },
            error=exec_res.get("stderr") or exec_res.get("error") if not exec_res["success"] else None
        )
