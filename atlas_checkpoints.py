#!/usr/bin/env python3
"""atlas_checkpoints.py — Checkpoints reanudables para tareas largas (REQ-C13).

Un checkpoint guarda el estado reanudable de una tarea larga en
memory_data/state/tasks/<id>.json. Permite retomar una ejecucion interrumpida
sin perder contexto.

Uso:
    import atlas_checkpoints as cp
    cp.save(task_id, steps=[...], current_step=3, context={...})
    cp.load(task_id)          # -> dict o None
    cp.resume(task_id)        # -> contexto del ultimo checkpoint
    cp.list_all()             # -> dict {task_id: {status, updated, step}}
    cp.clear(task_id)         # borra checkpoint completado
"""
import json
import re
import time
from datetime import datetime
from pathlib import Path

STATE_DIR = Path(__file__).parent / "memory_data" / "state" / "tasks"


def _slug(task_id: str) -> str:
    return re.sub(r"[^A-Za-z0-9_-]", "_", task_id).strip("_") or "task"


def _path(task_id: str) -> Path:
    return STATE_DIR / f"{_slug(task_id)}.json"


def save(task_id: str, steps=None, current_step=0, context=None,
         status: str = "in_progress", note: str = "") -> dict:
    """Guarda el estado de una tarea larga."""
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    data = {
        "task_id": task_id,
        "steps": steps or [],
        "current_step": current_step,
        "context": context or {},
        "status": status,
        "note": note,
        "updated": datetime.now().isoformat(),
    }
    _path(task_id).write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return data


def load(task_id: str):
    """Carga el checkpoint de una tarea (None si no existe)."""
    p = _path(task_id)
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def resume(task_id: str):
    """Devuelve el contexto para reanudar: pasos, paso actual y contexto."""
    data = load(task_id)
    if not data:
        return None
    return {
        "task_id": data.get("task_id"),
        "steps": data.get("steps", []),
        "current_step": data.get("current_step", 0),
        "context": data.get("context", {}),
        "note": data.get("note", ""),
        "status": data.get("status", "in_progress"),
    }


def list_all() -> dict:
    """Lista todos los checkpoints con su estado."""
    if not STATE_DIR.exists():
        return {}
    result = {}
    for p in sorted(STATE_DIR.glob("*.json")):
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            result[data.get("task_id", p.stem)] = {
                "status": data.get("status", "?"),
                "step": f"{data.get('current_step', 0)}/{len(data.get('steps', []))}",
                "updated": data.get("updated", ""),
                "file": p.name,
            }
        except Exception:
            continue
    return result


def clear(task_id: str) -> bool:
    """Borra el checkpoint (tarea completada o cancelada)."""
    p = _path(task_id)
    if p.exists():
        p.unlink()
        return True
    return False


def advance(task_id: str, context=None, note: str = "") -> dict:
    """Avanza al siguiente paso manteniendo el contexto."""
    data = load(task_id)
    if not data:
        return save(task_id, context=context, note=note, current_step=0)
    step = data.get("current_step", 0) + 1
    return save(task_id,
                steps=data.get("steps", []),
                current_step=step,
                context={**(data.get("context", {})), **(context or {})},
                status=data.get("status", "in_progress"),
                note=note)


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("uso: python atlas_checkpoints.py <list|resume TASK_ID>")
        sys.exit(0)
    cmd = sys.argv[1]
    if cmd == "list":
        print(json.dumps(list_all(), ensure_ascii=False, indent=2))
    elif cmd == "resume" and len(sys.argv) > 2:
        r = resume(sys.argv[2])
        print(json.dumps(r, ensure_ascii=False, indent=2) if r else "sin checkpoint")
    else:
        print("comando desconocido")
