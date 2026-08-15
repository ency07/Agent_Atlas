#!/usr/bin/env python3
"""
atlas_failure_learning.py — Aprendizaje de fallos en vivo (C3-8).
Tool falla → invalida snapshot parcial + friction_log + no reintenta igual.
"""
import json
import time
import uuid
from pathlib import Path
from typing import Dict, Any, Set

ROOT = Path(__file__).parent
STATE_DIR = ROOT / "memory_data" / "state"
FAILURE_LOG = STATE_DIR / "failure_learning.jsonl"
FAILURE_INDEX = STATE_DIR / "failure_index.json"  # tool->set of error signatures

# Cargar índice de fallos conocidos
_failure_index: Dict[str, Set[str]] = {}
if Path(FAILURE_INDEX).exists():
    try:
        data = json.loads(Path(FAILURE_INDEX).read_text(encoding="utf-8"))
        _failure_index = {k: set(v) for k, v in data.items()}
    except Exception:
        _failure_index = {}

def _save_index():
    try:
        Path(FAILURE_INDEX).write_text(
            json.dumps({k: list(v) for k, v in _failure_index.items()}, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )
    except Exception:
        pass

def _error_signature(error: str) -> str:
    # simple hash of first 200 chars
    import hashlib
    return hashlib.sha256(error[:200].encode()).hexdigest()[:16]

def register_failure(tool_name: str, error: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    Registra un fallo de tool, invalida snapshot relacionado, logea en friction_log,
    y evita reintento idéntico.
    """
    sig = _error_signature(error)
    tool_failures = _failure_index.setdefault(tool_name, set())
    already_seen = sig in tool_failures

    # Registrar en failure log
    entry = {
        "ts": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(timespec="seconds"),
        "tool": tool_name,
        "error": error[:500],
        "signature": sig,
        "context": context or {},
        "already_seen": already_seen,
    }
    Path(FAILURE_LOG).parent.mkdir(parents=True, exist_ok=True)
    with open(FAILURE_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    # Invalidar snapshot parcial relacionado (heurística: invalidar 'apps' y 'processes')
    try:
        import atlas_env
        atlas_env.invalidate("apps")
        atlas_env.invalidate("processes")
    except Exception:
        pass

    # Log a friction_log (tipo correccion)
    try:
        friction_log = Path(ROOT) / "memory_data" / "state" / "friction_log.jsonl"
        friction_log.parent.mkdir(parents=True, exist_ok=True)
        fr_entry = {
            "ts": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(timespec="seconds"),
            "type": "correccion",
            "detail": f"Fallo tool {tool_name}: {error[:100]}",
            "meta": {"tool": tool_name, "signature": sig},
        }
        with open(friction_log, "a", encoding="utf-8") as f:
            f.write(json.dumps(fr_entry, ensure_ascii=False) + "\n")
    except Exception:
        pass

    if not already_seen:
        tool_failures.add(sig)
        _save_index()

    return {
        "tool": tool_name,
        "signature": sig,
        "already_seen": already_seen,
        "retry_allowed": not already_seen,
    }

def can_retry(tool_name: str, error: str) -> bool:
    """True si no se ha visto este fallo antes para este tool."""
    sig = _failure_index.get(tool_name, set())
    error_sig = _error_signature(error)
    return error_sig not in sig

# CLI
if __name__ == "__main__":
    import sys, json
    if "--register" in sys.argv:
        tool = ""
        err = ""
        for i,a in enumerate(sys.argv):
            if a == "--tool" and i+1 < len(sys.argv): tool = sys.argv[i+1]
            if a == "--error" and i+1 < len(sys.argv): err = sys.argv[i+1]
        print(json.dumps(register_failure(tool, err), ensure_ascii=False, indent=2))
    elif "--can-retry" in sys.argv:
        tool = ""
        err = ""
        for i,a in enumerate(sys.argv):
            if a == "--tool" and i+1 < len(sys.argv): tool = sys.argv[i+1]
            if a == "--error" and i+1 < len(sys.argv): err = sys.argv[i+1]
        print(json.dumps({"can_retry": can_retry(tool, err)}, ensure_ascii=False, indent=2))
    else:
        print("Uso: python atlas_failure_learning.py --register --tool X --error Y | --can-retry --tool X --error Y")