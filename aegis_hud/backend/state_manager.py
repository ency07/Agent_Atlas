"""
state_manager.py — Gestión de task_state.json con operaciones atómicas.

El LLM no es la fuente de la verdad. Este módulo gestiona un archivo
task_state.json con: task_id, user_prompt, status, current_step,
history, error_count.

Funcionalidades:
  - Lectura/escritura atómica (rename pattern)
  - Circuit breaker: si error_count >= 3, DETENER y notificar
  - Historial de pasos con timestamps
  - Recuperación de estado interrumpido
"""

import json
import os
import time
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# Directorio de estado (relativo al backend/)
BACKEND_DIR = Path(__file__).parent
STATE_FILE = BACKEND_DIR / "task_state.json"

# Circuit breaker
MAX_ERRORS = 3

# Estados posibles de una tarea
STATUS_IDLE = "idle"
STATUS_ROUTING = "routing"
STATUS_CLASSIFYING = "classifying"
STATUS_EXECUTING = "executing"
STATUS_REPAIRING = "repairing"
STATUS_ERROR = "error"
STATUS_COMPLETED = "completed"
STATUS_BLOCKED = "blocked"  # circuit breaker activado


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _default_state() -> dict:
    """Estado inicial de task_state.json."""
    return {
        "task_id": None,
        "user_prompt": None,
        "status": STATUS_IDLE,
        "mode": None,           # "chat" | "agent"
        "model_used": None,
        "current_step": 0,
        "total_steps": 0,
        "error_count": 0,
        "last_error": None,
        "history": [],
        "created_at": None,
        "updated_at": None,
        "result": None,
    }


def _atomic_write(path: Path, data: dict) -> None:
    """Escritura atómica: escribe a un temp file y renombra.
    
    Esto previene corrupción si el proceso muere a mitad de escritura.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_fd, tmp_path = tempfile.mkstemp(
        dir=str(path.parent),
        suffix=".tmp",
        prefix="task_state_",
    )
    try:
        with os.fdopen(tmp_fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        # Windows: el destino debe no existir para rename
        if path.exists():
            path.unlink()
        os.replace(tmp_path, str(path))
    except Exception:
        # Limpiar temp en caso de error
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


def load_state() -> dict:
    """Lee task_state.json. Si no existe o está corrupto, devuelve estado default."""
    if not STATE_FILE.exists():
        return _default_state()
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        # Validar campos mínimos
        if not isinstance(data, dict):
            return _default_state()
        data.setdefault("status", STATUS_IDLE)
        data.setdefault("error_count", 0)
        data.setdefault("history", [])
        return data
    except (json.JSONDecodeError, OSError):
        return _default_state()


def save_state(state: dict) -> None:
    """Guarda task_state.json de forma atómica."""
    state["updated_at"] = _now_iso()
    _atomic_write(STATE_FILE, state)


def new_task(user_prompt: str, mode: str = "chat") -> dict:
    """Crea una nueva tarea y la persiste.
    
    Returns:
        El estado recién creado.
    """
    state = _default_state()
    state["task_id"] = f"task-{uuid.uuid4().hex[:12]}"
    state["user_prompt"] = user_prompt
    state["status"] = STATUS_ROUTING
    state["mode"] = mode
    state["created_at"] = _now_iso()
    state["updated_at"] = _now_iso()
    save_state(state)
    return state


def append_history(state: dict, step: str, detail: str = "", error: bool = False) -> dict:
    """Añade un paso al historial de la tarea.
    
    Args:
        state: Estado actual de la tarea.
        step: Nombre del paso (ej: "classify", "execute", "repair").
        detail: Detalle adicional del paso.
        error: Si es True, incrementa error_count.
    
    Returns:
        Estado actualizado (ya persistido).
    """
    entry = {
        "step": step,
        "detail": detail[:500],
        "ts": _now_iso(),
        "error": error,
    }
    state["history"].append(entry)
    state["current_step"] = len(state["history"])
    
    if error:
        state["error_count"] = state.get("error_count", 0) + 1
        state["last_error"] = detail[:300]
    
    save_state(state)
    return state


def check_circuit_breaker(state: dict) -> bool:
    """Verifica si el circuit breaker debe activarse.
    
    Returns:
        True si debe DETENER (error_count >= MAX_ERRORS).
    """
    if state.get("error_count", 0) >= MAX_ERRORS:
        state["status"] = STATUS_BLOCKED
        append_history(
            state,
            "circuit_breaker",
            f"Circuit breaker activado: {state['error_count']} errores consecutivos. "
            f"Acción bloqueada. Revisa el estado y resetea manualmente si es seguro.",
            error=False,
        )
        return True
    return False


def reset_task(task_id: Optional[str] = None) -> dict:
    """Resetea el estado de una tarea o limpia todo.
    
    Args:
        task_id: Si se proporciona, solo resetea esa tarea.
                 Si es None, limpia todo el state.
    
    Returns:
        Nuevo estado.
    """
    state = _default_state()
    if task_id:
        state["task_id"] = task_id
    save_state(state)
    return state


def set_status(state: dict, status: str) -> dict:
    """Actualiza solo el status de una tarea persistida."""
    state["status"] = status
    save_state(state)
    return state


def set_result(state: dict, result: dict) -> dict:
    """Guarda el resultado final de la tarea."""
    state["result"] = result
    state["status"] = STATUS_COMPLETED
    append_history(state, "completed", "Tarea completada exitosamente")
    return state


def get_active_task() -> Optional[dict]:
    """Devuelve la tarea activa actual (si existe y no está idle/completed)."""
    state = load_state()
    if state["status"] in (STATUS_IDLE, STATUS_COMPLETED, STATUS_BLOCKED):
        return None
    return state


def is_blocked() -> bool:
    """Verifica si el sistema está bloqueado por circuit breaker."""
    state = load_state()
    return state["status"] == STATUS_BLOCKED
