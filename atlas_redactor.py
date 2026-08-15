#!/usr/bin/env python3
"""
atlas_redactor.py — Redacción por proveedor (C3-7).
Slice local completo; slice cloud sin rutas/puertos/inventario.
"""
import json
import re
from typing import Dict, Any, List

# Patrones sensibles
SENSITIVE_PATTERNS = [
    (re.compile(r"(?:E|C|D):\\[^\\s]*"), "[RUTA_LOCAL]"),
    (re.compile(r"(?:localhost|127\.0\.0\.1):\d+"), "[HOST:PORT]"),
    (re.compile(r"\b\d{1,3}(?:\.\d{1,3}){3}\b"), "[IP]"),
    (re.compile(r"(?:puertos?|ports?)\s*:?\s*\d+(?:,\s*\d+)*"), "[PUERTOS]"),
    (re.compile(r"(?:modelo|model)\s*[=:]\s*\S+"), "[MODELO]"),
]

def _redact_text(text: str) -> str:
    for pattern, repl in SENSITIVE_PATTERNS:
        text = pattern.sub(repl, text)
    return text

def _redact_obj(obj: Any, provider: str) -> Any:
    """Recursively redact sensitive info for cloud provider."""
    if provider == "local":
        return obj
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            if provider == "cloud" and k.lower() == "model":
                out[k] = "[MODELO]"
            else:
                out[k] = _redact_obj(v, provider)
        return out
    elif isinstance(obj, list):
        return [_redact_obj(v, provider) for v in obj]
    elif isinstance(obj, str):
        return _redact_text(obj)
    else:
        return obj

def redact_slice(slice_data: Dict[str, Any], provider: str) -> Dict[str, Any]:
    """
    Devuelve slice redactado según proveedor.
    provider: "local" (completo) | "cloud" (redactado)
    """
    if provider not in ("local", "cloud"):
        provider = "cloud"
    return _redact_obj(slice_data, provider)

# CLI
if __name__ == "__main__":
    import sys, json
    if len(sys.argv) < 3:
        print("Uso: python atlas_redactor.py <provider:local|cloud> <archivo_json_slice>")
        sys.exit(1)
    provider = sys.argv[1]
    slice_file = sys.argv[2]
    with open(slice_file, "r", encoding="utf-8") as f:
        data = json.load(f)
    out = redact_slice(data, provider)
    print(json.dumps(out, ensure_ascii=False, indent=2))