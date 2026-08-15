# ============================================================
# tests/unit/test_c1_redact.py — REQ-C14 redaccion de sensibles
# ------------------------------------------------------------
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import mcp_memory_server as mem


def test_redact_api_keys():
    assert "REDACTED" in mem.redact("api key: sk-1234567890abcdef")
    assert "sk-" not in mem.redact("sk-abcdef1234567890abcdef12")


def test_redact_token_patterns():
    assert "REDACTED" in mem.redact("token=abcdef1234567890abcdef12")
    assert "REDACTED" in mem.redact("password=supersecreto123")
    assert "REDACTED" in mem.redact("Authorization: Bearer abcdefghijklmnopqrst1234")


def test_redact_no_false_positive():
    original = "este es un texto normal sin claves"
    assert mem.redact(original) == original
    # una password sin separador '=' no debe redactarse (no es clave)
    assert mem.redact("la password del sistema es fuerte") == "la password del sistema es fuerte"


def test_redact_empty():
    assert mem.redact("") == ""
    assert mem.redact(None) is None or mem.redact(None) == ""
