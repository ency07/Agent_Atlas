"""
Atlas Verifier — Ejecutores reales por tipo (C2-3)
El "listo" del agente no vale. Solo el ejecutor cierra el criterio.
"""
import json
import subprocess
import sys
import urllib.request
import urllib.error
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

PROJECT_ROOT = Path(__file__).resolve().parent
PYTHON = PROJECT_ROOT / ".venv" / "Scripts" / "python.exe"
if not PYTHON.exists():
    PYTHON = Path(sys.executable)


@dataclass
class VerificationResult:
    ok: bool
    evidencia: str


class Verifier:
    def ejecutar(self, criterio: dict) -> VerificationResult:
        tipo = criterio.get("tipo")
        v = criterio.get("verificacion", {})
        try:
            if tipo == "comando":     return self._comando(v)
            if tipo == "archivo":     return self._archivo(v)
            if tipo == "endpoint":    return self._endpoint(v)
            if tipo == "ui":          return self._ui(v)
            if tipo == "captura":     return self._captura(v)
            if tipo == "test":        return self._test(v)
            if tipo == "humano":      return VerificationResult(False, "Pendiente de usuario")
            return VerificationResult(False, f"tipo desconocido: {tipo}")
        except Exception as e:
            return VerificationResult(False, f"ERROR: {e}")

    def _comando(self, v: dict) -> VerificationResult:
        cmd = v["cmd"]
        try:
            r = subprocess.run(cmd, shell=True, capture_output=True,
                               text=True, timeout=30, encoding="utf-8", errors="ignore")
            out = (r.stdout or "") + (r.stderr or "")
            ok = (r.returncode == 0)
            if "esperado" in v:
                ok = ok and (v["esperado"] in out)
            return VerificationResult(ok, out[:500])
        except subprocess.TimeoutExpired:
            return VerificationResult(False, "timeout 30s")

    def _archivo(self, v: dict) -> VerificationResult:
        p = Path(v["ruta"]).expanduser()
        if not p.exists():
            return VerificationResult(False, f"no existe {p}")
        if "contiene" in v:
            contenido = p.read_text(encoding="utf-8", errors="ignore")
            ok = v["contiene"] in contenido
            return VerificationResult(ok, f"contiene={ok}")
        return VerificationResult(True, f"existe {p}")

    def _endpoint(self, v: dict) -> VerificationResult:
        url = v["url"]
        try:
            req = urllib.request.Request(url, method="GET")
            with urllib.request.urlopen(req, timeout=10) as r:
                body = r.read().decode("utf-8", errors="replace")
            ok = r.status == 200
            if "contiene" in v:
                ok = ok and (v["contiene"] in body)
            if "status" in v:
                ok = ok and (r.status == v["status"])
            return VerificationResult(ok, f"{r.status} · {body[:300]}")
        except urllib.error.HTTPError as e:
            return VerificationResult(False, f"HTTP {e.code}")
        except Exception as e:
            return VerificationResult(False, f"endpoint fallo: {e}")

    def _ui(self, v: dict) -> VerificationResult:
        """Verifica UI real vía read_ui_state (import directo, no subprocess)."""
        try:
            sys.path.insert(0, str(PROJECT_ROOT))
            from mcp_windows.mcp_windows_server import read_ui_state
            out = read_ui_state(v.get("window_title", ""), max_depth=3)
            contiene = v.get("contiene", "")
            ok = contiene in out if contiene else True
            return VerificationResult(ok, out[:500])
        except Exception as e:
            return VerificationResult(False, f"UIA fallo: {e}")

    def _captura(self, v: dict) -> VerificationResult:
        """Verifica pantalla vía screen_capture + ocr_screen (import directo)."""
        try:
            sys.path.insert(0, str(PROJECT_ROOT))
            from mcp_windows.mcp_windows_server import screen_capture, ocr_screen
            region = v.get("region", "full")
            screen_capture(region=region, filename="")  # screenshot a atlas_shots/
            out = ocr_screen(region=region, language="es")
            contiene = v.get("contiene", "")
            ok = contiene in out if contiene else True
            return VerificationResult(ok, out[:500])
        except Exception as e:
            return VerificationResult(False, f"captura fallo: {e}")

    def _test(self, v: dict) -> VerificationResult:
        selector = v.get("selector", "")
        cmd = f"{str(PYTHON)} -m pytest tests/unit/ -q -k \"{selector}\"" if selector else f"{str(PYTHON)} -m pytest tests/unit/ -q"
        try:
            r = subprocess.run(cmd, shell=True, capture_output=True,
                               text=True, timeout=120, encoding="utf-8", errors="ignore")
            out = (r.stdout or "") + (r.stderr or "")
            ok = "failed" not in out.lower() and r.returncode == 0
            return VerificationResult(ok, out[-400:])
        except subprocess.TimeoutExpired:
            return VerificationResult(False, "timeout 120s")
