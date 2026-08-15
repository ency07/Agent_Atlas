#!/usr/bin/env python3
"""
atlas_context_inject.py — Inyección automática por relevancia (código).
C3-2: Tarea menciona Corel → slice Corel; nunca dump completo. Log de inyección.
"""
import json
import re
import sys
from pathlib import Path
from typing import Dict, List, Any

ROOT = Path(__file__).parent
SELF_MODEL = ROOT / "self_model.json"
INJECTION_LOG = ROOT / "memory_data" / "state" / "injection_log.jsonl"

# Cargar self_model una vez
_self_model: Dict[str, Any] = {}
if SELF_MODEL.exists():
    try:
        _self_model = json.loads(SELF_MODEL.read_text(encoding="utf-8"))
    except Exception:
        _self_model = {}

# Mapa de palabras clave a secciones relevantes
KEYWORD_MAP = {
    "corel": ["components", "configs"],          # buscar componentes relacionados a Corel
    "actividad": ["components"],                 # daemon activity
    "daemon": ["components"],
    "actividad": ["components"],
    "chat": ["components"],
    "modelo": ["components", "configs"],
    "orquestador": ["components"],
    "foco": ["components"],
    "guardián": ["components"],
    "guardian": ["components"],
    "backup": ["components"],
    "memoria": ["components"],
    "memoria_db": ["components"],
    "memory": ["components"],
    "config": ["configs"],
    "opencode": ["configs"],
    "entorno": ["components"],
    "snapshot": ["components"],
    "inyección": ["components"],
    "injection": ["components"],
    "flujo": ["flows"],
    "flow": ["flows"],
    "deuda": ["debts"],
    "debt": ["debts"],
    "capacidad": ["capabilities"],
    "capabilities": ["capabilities"],
    "límite": ["limits"],
    "limits": ["limits"],
}

def _find_relevant_sections(task_text: str) -> List[str]:
    text = task_text.lower()
    sections = set()
    for kw, secs in KEYWORD_MAP.items():
        if kw in text:
            sections.update(secs)
    # siempre incluir capabilities y limits como contexto base
    sections.update(["capabilities", "limits"])
    return sorted(sections)

def _slice_model(sections: List[str]) -> Dict[str, Any]:
    slice_data = {}
    for sec in sections:
        if sec in _self_model:
            slice_data[sec] = _self_model[sec]
    return slice_data

def _log_injection(task_text: str, sections: List[str], slice_size: int):
    INJECTION_LOG.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "ts": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(timespec="seconds"),
        "task": task_text[:200],
        "sections": sections,
        "slice_keys": list(slice_data.keys()) if (slice_data := _slice_model(sections)) else [],
        "slice_size_bytes": slice_size,
    }
    with open(INJECTION_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")

def inject_context(task_text: str) -> Dict[str, Any]:
    """
    Devuelve el slice relevante del self_model para la tarea.
    """
    sections = _find_relevant_sections(task_text)
    slice_data = _slice_model(sections)
    # calcular tamaño aproximado
    slice_json = json.dumps(slice_data, ensure_ascii=False)
    size = len(slice_json.encode("utf-8"))
    _log_injection(task_text, sections, size)
    return {
        "task": task_text,
        "matched_sections": sections,
        "slice": slice_data,
        "slice_size_bytes": size,
    }

# CLI
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python atlas_context_inject.py \"texto de la tarea\"")
        sys.exit(1)
    task = " ".join(sys.argv[1:])
    result = inject_context(task)
    print(json.dumps(result, ensure_ascii=False, indent=2))