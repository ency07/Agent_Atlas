# ============================================================
# atlas_model_switch.py — Auto-cambio de modelo en runtime
# ------------------------------------------------------------
# Lee el modelo activo de la config de opencode, analiza la tarea
# con el orquestador y, si el modelo actual no es el óptimo para la
# capacidad requerida, lo cambia en el config (con backup y rollback).
#
# Uso:
#   python atlas_model_switch.py "tarea de codigo"      # decide y cambia
#   python atlas_model_switch.py "tarea" --dry-run       # solo informa
#   python atlas_model_switch.py --current               # modelo activo
# ============================================================
import json
import os
import re
import sys
import shutil
import argparse
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).parent
MEMORY_ROOT = ROOT / "memory_data"
STATE_DIR = MEMORY_ROOT / "state"
LOG_FILE = STATE_DIR / "routing_log.json"
BACKUP_DIR = MEMORY_ROOT / "state" / "config_backups"

import atlas_orchestrator as orch


def _config_candidates():
    """Candidatos de ubicación del config de opencode"""
    return [
        Path(os.environ.get("APPDATA", "")) / "opencode" / "opencode.jsonc",
        Path.home() / ".config" / "opencode" / "opencode.jsonc",
        ROOT / "opencode.jsonc",
    ]


def find_config():
    """Devuelve la ruta del config de opencode existente (o None)"""
    for p in _config_candidates():
        if p.exists():
            return p
    return None


def current_model(config_path=None):
    """Lee el modelo activo de la config"""
    config_path = config_path or find_config()
    if not config_path:
        return None
    try:
        txt = config_path.read_text(encoding="utf-8")
        m = re.search(r'"model"\s*:\s*"([^"]+)"', txt)
        return m.group(1) if m else None
    except Exception:
        return None


def set_model(config_path, model):
    """Reemplaza el modelo activo en la config (con backup previo)"""
    if not config_path:
        return False
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = BACKUP_DIR / f"opencode_{ts}.jsonc"
    try:
        shutil.copy2(config_path, backup_path)
        txt = config_path.read_text(encoding="utf-8")
        new_txt, n = re.subn(r'"model"\s*:\s*"[^"]*"', f'"model": "{model}"', txt, count=1)
        if n == 0:
            # Si no existe la linea model, insertar despues de provider
            new_txt = txt.replace("{\n", f'{{\n  "model": "{model}",\n', 1) if txt.strip().startswith("{") else f'{{"model": "{model}",\n{txt}}}'
            n = 1
        config_path.write_text(new_txt, encoding="utf-8")
        return n > 0
    except Exception as e:
        print(f"  Error cambiando modelo: {e}")
        return False


def _load_log():
    if LOG_FILE.exists():
        try:
            return json.loads(LOG_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"entries": [], "provider_health": {}, "provider_stats": {}}


def _save_log(data):
    try:
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        LOG_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass


def _model_has_capability(model_key, req_cap):
    """¿El modelo activo cubre la capacidad requerida?"""
    if not req_cap:
        return True
    # Buscar en capacidades del orquestador
    try:
        caps = orch.load_capabilities().get("models", {})
        # Intentar match directo y por base
        for key, cap in caps.items():
            if model_key and model_key in key:
                if cap.get(req_cap) in (True, 0.8, 0.85, 0.9, 0.95, 0.98):
                    return True
                if cap.get(req_cap) is False:
                    return False
    except Exception:
        pass
    # Fallback: inferir por nombre
    inferred = orch._infer_capability(model_key, None) if hasattr(orch, "_infer_capability") else {}
    if req_cap == "vision":
        return bool(inferred.get("vision"))
    val = inferred.get(req_cap, 0.5)
    return isinstance(val, (int, float)) and val >= 0.7


def decide_and_switch(task, dry_run=False):
    """Analiza la tarea, compara con el modelo activo y cambia si conviene"""
    print(f"[{datetime.now().isoformat()}] === MODEL SWITCH ===")
    print(f"  Tarea: {task[:80]}")

    config_path = find_config()
    if not config_path:
        print("  ERROR: no se encontro config de opencode")
        return {"changed": False, "reason": "no_config"}

    current = current_model(config_path)
    print(f"  Config: {config_path}")
    print(f"  Modelo activo: {current}")

    # Analizar tarea con el orquestador
    try:
        res = orch.analyze(task)
    except Exception as e:
        print(f"  ERROR orquestador: {e}")
        return {"changed": False, "reason": f"orchestrator_error: {e}"}

    suggested = res.get("decision", {}).get("suggested_model")
    action = res.get("decision", {}).get("action")
    req_cap = res.get("required_capability")

    print(f"  Capacidad requerida: {req_cap}")
    print(f"  Accion orquestador: {action}")
    print(f"  Modelo sugerido: {suggested}")

    if action == "block_and_advise":
        print("  [AVISO] No se cambia: tarea bloqueada (vision sin modelo)")
        return {"changed": False, "reason": "blocked", "detail": res.get("decision", {}).get("reason")}

    if not suggested:
        print("  [AVISO] No se cambia: no hay provider activo")
        return {"changed": False, "reason": "no_suggestion"}

    # Regla: solo cambiar si el modelo activo NO cubre la capacidad requerida
    if _model_has_capability(current, req_cap):
        print(f"  El modelo activo ya cubre la capacidad requerida. No se cambia.")
        _log_switch(task, current, suggested, changed=False, req_cap=req_cap)
        return {"changed": False, "reason": "already_adequate", "current": current, "suggested": suggested}

    # El modelo actual no cubre la capacidad -> cambiar
    if dry_run:
        print(f"  [DRY-RUN] Cambiaria: {current} -> {suggested}")
        return {"changed": True, "dry_run": True, "current": current, "suggested": suggested}

    ok = set_model(config_path, suggested)
    if ok:
        print(f"  [OK] Modelo cambiado: {current} -> {suggested}")
        _log_switch(task, current, suggested, changed=True, req_cap=req_cap)
        return {"changed": True, "current": current, "suggested": suggested}
    else:
        print("  ERROR cambiando modelo")
        return {"changed": False, "reason": "write_error"}


def _log_switch(task, before, after, changed, req_cap=None):
    """Registra el cambio en routing_log.json"""
    data = _load_log()
    entry = {
        "ts": datetime.now().isoformat(),
        "task": task[:120],
        "task_type": "runtime_switch",
        "req_cap": req_cap,
        "decision": "switch" if changed else "keep",
        "model_before": before,
        "model_after": after,
        "changed": changed,
    }
    data.setdefault("entries", []).append(entry)
    data["entries"] = data["entries"][-500:]
    _save_log(data)


def main():
    parser = argparse.ArgumentParser(description="Auto-cambio de modelo en runtime")
    parser.add_argument("task", nargs="?", help="Tarea a analizar")
    parser.add_argument("--dry-run", action="store_true", help="Solo informar sin cambiar")
    parser.add_argument("--current", action="store_true", help="Mostrar modelo activo y salir")
    args = parser.parse_args()

    if args.current:
        cfg = find_config()
        if not cfg:
            print("No config found")
            sys.exit(1)
        print(f"Config: {cfg}")
        print(f"Modelo activo: {current_model(cfg)}")
        return

    if not args.task:
        parser.print_help()
        sys.exit(1)

    result = decide_and_switch(args.task, dry_run=args.dry_run)
    print(f"\nResultado: {json.dumps(result, ensure_ascii=False, indent=2)}")


if __name__ == "__main__":
    main()