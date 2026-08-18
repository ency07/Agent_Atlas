"""
Atlas Fidelity — Desviación Cero (REQ C2-10)
Si un contrato activo fija programa/categoría, la primera llamada a una tool
equivalente distinta requiere confirmación; el reintento sin confirmación
se BLOQUEA. Todo intento queda en friction_log como tipo "desviacion".
"""
import json
from pathlib import Path
from datetime import datetime

BASE = Path(__file__).resolve().parent
TASKS = BASE / "memory_data" / "state" / "tasks"
FRICTION = BASE / "memory_data" / "state" / "friction_log.jsonl"

# Tools de desviación por categoría fijada + tool esperada
DESVIADA = {
    "navegador": {"playwright-visual", "playwright"},
    "diseno": set(),
}
ESPERADA = {
    "navegador": "windows (UIA/OCR/teclado-mouse sobre el navegador del usuario)",
    "diseno": "corel-draw",
}

def _save(c, path):
    path.write_text(json.dumps(c, indent=2, ensure_ascii=False), encoding="utf-8")

def active_contract():
    if not TASKS.exists():
        return None, None
    for p in sorted(TASKS.glob("*.json"), key=lambda x: x.stat().st_mtime, reverse=True):
        try:
            c = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        if c.get("estado") == "EN_CURSO" and c.get("categoria_fijada"):
            return c, p
    return None, None

def _log_friction(task_id, tool, decision):
    with open(FRICTION, "a", encoding="utf-8") as f:
        f.write(json.dumps({
            "ts": datetime.now().isoformat(timespec="seconds"),
            "tipo": "desviacion", "task": task_id,
            "tool": tool, "decision": decision,
        }, ensure_ascii=False) + "\n")

def check_tool(tool: str) -> dict:
    c, path = active_contract()
    if not c:
        return {"decision": "allowed"}
    cat = c["categoria_fijada"]
    if tool not in DESVIADA.get(cat, set()):
        return {"decision": "allowed"}
    key = f"{c['task_id']}::{tool}"
    log = c.setdefault("fidelity_log", [])
    conf = c.setdefault("fidelity_confirmed", [])
    if key in conf:
        return {"decision": "allowed"}
    if key not in log:
        log.append(key); _save(c, path)
        _log_friction(c["task_id"], tool, "requires_confirmation")
        return {"decision": "requires_confirmation",
                "mensaje": (f"FIDELIDAD C2-10: el contrato {c['task_id']} fijó "
                            f"'{c.get('programa_fijado', cat)}'. {tool} es desviación. "
                            f"Tool esperada: {ESPERADA.get(cat)}. Pide confirmación al "
                            f"usuario y llama confirmar_fidelity('{tool}') si autoriza.")}
    _log_friction(c["task_id"], tool, "blocked")
    return {"decision": "blocked",
            "mensaje": (f"FIDELIDAD C2-10: {tool} BLOQUEADO en {c['task_id']}: "
                        f"desviación ya advertida sin confirmación. Usa {ESPERADA.get(cat)} "
                        f"o pide confirmación al usuario.")}

def confirmar_fidelity(tool: str) -> dict:
    c, path = active_contract()
    if not c:
        return {"ok": False, "error": "sin contrato activo"}
    c.setdefault("fidelity_confirmed", []).append(f"{c['task_id']}::{tool}")
    _save(c, path)
    return {"ok": True}

def fidelity(tool: str):
    """Decorador para tools MCP: bloquea desviación antes de ejecutar."""
    def deco(fn):
        def wrap(*a, **kw):
            d = check_tool(tool)
            if d["decision"] != "allowed":
                return {"error": d["mensaje"], "decision": d["decision"]}
            return fn(*a, **kw)
        return wrap
    return deco