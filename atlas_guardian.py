#!/usr/bin/env python3
"""
Atlas Guardian MCP Server — Modo guardián con restricciones configurables.

Provee:
  - guardian_check(operation, params) → valida si una operación está permitida
  - guardian_set_level(level) → cambia nivel: relax | guard | strict
  - guardian_get_config() → devuelve config actual
  - guardian_add_whitelist(cmd) → añade a lista blanca
  - guardian_remove_whitelist(cmd) → quita de lista blanca

Niveles:
  relax  → Todo permitido, se registra todo en logs
  guard  → Lista blanca de comandos/apps; acciones sensibles → pregunta al usuario (default)
  strict → Solo acciones de bajo riesgo; bloquea run_script/process_kill/registry_write

Configuración en state/guardian.json:
{
  "level": "guard",
  "whitelist_binaries": ["python", "node", "npm", "git", "pip", "wscript"],
  "whitelist_processes": ["python.exe", "node.exe", "code.exe"],
  "allowed_dirs": ["E:\\Agente_IA", "C:\\Users\\Administrator\\Documents"],
  "blocked_ops": ["run_script", "process_kill", "registry_write"],
  "confirm_destructive": true
}

Integración: el server windows consulta atlas_guardian.check(operation) antes de ejecutar.
"""

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Any

from mcp.server.fastmcp import FastMCP

# --- Paths ---
MEMORY_ROOT = Path(os.environ.get("MEMORY_ROOT", str(Path(__file__).parent / "memory_data"))).resolve()
STATE_DIR = MEMORY_ROOT / "state"
GUARDIAN_CONFIG = STATE_DIR / "guardian.json"

# --- Config ---
DEFAULT_CONFIG = {
    "level": "guard",
    "whitelist_binaries": ["python", "node", "npm", "git", "pip", "wscript", "powershell", "cmd"],
    "whitelist_processes": ["python.exe", "node.exe", "code.exe", "powershell.exe", "cmd.exe"],
    "allowed_dirs": [str(MEMORY_ROOT.parent), str(Path.home() / "Documents")],
    "blocked_ops": ["run_script", "process_kill", "registry_write"],
    "confirm_destructive": True,
}

# --- Logging ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[
        logging.FileHandler(MEMORY_ROOT / "logs" / "atlas_guardian.log"),
        logging.StreamHandler(),
    ],
)
log = logging.getLogger("atlas_guardian")

# --- MCP Server ---
mcp = FastMCP("atlas_guardian", host="127.0.0.1", port=4098)

# --- Config loader ---
def load_config() -> Dict:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    if not GUARDIAN_CONFIG.exists():
        GUARDIAN_CONFIG.write_text(json.dumps(DEFAULT_CONFIG, indent=2), encoding="utf-8")
    try:
        cfg = json.loads(GUARDIAN_CONFIG.read_text(encoding="utf-8"))
        # Merge con defaults para claves nuevas
        for k, v in DEFAULT_CONFIG.items():
            cfg.setdefault(k, v)
        return cfg
    except Exception as exc:
        log.warning(f"config invalida, usando default: {exc}")
        return DEFAULT_CONFIG.copy()

def save_config(cfg: Dict):
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    GUARDIAN_CONFIG.write_text(json.dumps(cfg, indent=2), encoding="utf-8")

config = load_config()

# --- Helpers ---

def log_blocked(operation: str, params: Dict, reason: str):
    """Registra intento bloqueado en DB de eventos (auditoría)."""
    try:
        from mcp_memory_server import tool_note_save
        event_body = f"""# Guard Block Event
**Operation**: {operation}
**Params**: {json.dumps(params, ensure_ascii=False)}
**Reason**: {reason}
**Level**: {config['level']}
**Timestamp**: {datetime.now(timezone.utc).isoformat()}
"""
        tool_note_save(
            title=f"guard_block - {operation}",
            body=event_body,
            type="fact",
            project="global",
            tags="guardian,audit,blocked",
            status="open",
        )
    except Exception as exc:
        log.warning(f"no se pudo registrar evento guard_block: {exc}")

def is_binary_allowed(binary: str) -> bool:
    """Verifica si un binario está en lista blanca."""
    binary_lower = binary.lower()
    for wl in config["whitelist_binaries"]:
        if wl.lower() in binary_lower or binary_lower in wl.lower():
            return True
    return False

def is_process_allowed(process: str) -> bool:
    """Verifica si un proceso está en lista blanca."""
    process_lower = process.lower()
    for wl in config["whitelist_processes"]:
        if wl.lower() in process_lower or process_lower in wl.lower():
            return True
    return False

def is_path_allowed(path: str) -> bool:
    """Verifica si una ruta está dentro de directorios permitidos."""
    try:
        p = Path(path).resolve()
        for allowed in config["allowed_dirs"]:
            a = Path(allowed).resolve()
            if p.is_relative_to(a):
                return True
        return False
    except Exception:
        return False

def is_operation_blocked(op: str) -> bool:
    """Verifica si una operación está en lista de bloqueadas."""
    return op in config["blocked_ops"]

# --- MCP Tools ---

@mcp.tool()
def guardian_check(operation: str, params: Dict = None) -> Dict:
    """
    Valida si una operación está permitida según el nivel actual.
    
    Args:
        operation: Nombre de la operación (run_command, run_script, process_kill, file_delete, registry_write, etc.)
        params: Parámetros de la operación (ej: {"command": "npm install"}, {"pid": 1234})
        
    Returns:
        {"allowed": bool, "reason": str, "requires_confirmation": bool}
    """
    if params is None:
        params = {}
    
    level = config["level"]
    
    # Relax: todo permitido, solo log
    if level == "relax":
        log.info(f"RELAX: {operation} permitido: {params}")
        return {"allowed": True, "reason": "modo relax", "requires_confirmation": False}
    
    # Strict: bloquea operaciones peligrosas
    if level == "strict":
        if is_operation_blocked(operation):
            reason = f"Operación '{operation}' bloqueada en modo strict"
            log_blocked(operation, params, reason)
            return {"allowed": False, "reason": reason, "requires_confirmation": False}
    
    # Guard (default) + Strict: validaciones específicas
    if operation in ("run_command", "run_script"):
        cmd = params.get("command", "") or params.get("script_path", "")
        binary = cmd.split()[0] if cmd else ""
        if not is_binary_allowed(binary):
            reason = f"Binario '{binary}' no está en lista blanca"
            log_blocked(operation, params, reason)
            return {"allowed": False, "reason": reason, "requires_confirmation": True}
    
    elif operation == "process_kill":
        pid = params.get("pid")
        # No podemos verificar el nombre del proceso por PID fácilmente sin psutil
        # En modo guard pedimos confirmación
        if level == "guard":
            return {"allowed": True, "reason": "confirmación requerida", "requires_confirmation": True}
        if level == "strict":
            reason = "process_kill bloqueado en modo strict"
            log_blocked(operation, params, reason)
            return {"allowed": False, "reason": reason, "requires_confirmation": False}
    
    elif operation == "file_delete":
        path = params.get("path", "")
        if not is_path_allowed(path):
            reason = f"Ruta '{path}' fuera de directorios permitidos"
            log_blocked(operation, params, reason)
            return {"allowed": False, "reason": reason, "requires_confirmation": False}
    
    elif operation == "registry_write":
        if level == "strict":
            reason = "registry_write bloqueado en modo strict"
            log_blocked(operation, params, reason)
            return {"allowed": False, "reason": reason, "requires_confirmation": False}
        if level == "guard":
            return {"allowed": True, "reason": "confirmación requerida", "requires_confirmation": True}
    
    # Operación permitida
    return {"allowed": True, "reason": "ok", "requires_confirmation": config["confirm_destructive"] and level == "guard"}


@mcp.tool()
def guardian_set_level(level: str) -> Dict:
    """
    Cambia el nivel de guardián.
    
    Args:
        level: "relax" | "guard" | "strict"
        
    Returns:
        Config actualizada
    """
    level = level.lower()
    if level not in ("relax", "guard", "strict"):
        return {"error": f"Nivel inválido: {level}. Use: relax, guard, strict"}
    
    config["level"] = level
    save_config(config)
    log.info(f"Nivel guardián cambiado a: {level}")
    return {"level": level, "config": config}


@mcp.tool()
def guardian_get_config() -> Dict:
    """Devuelve la configuración actual del guardián."""
    return config


@mcp.tool()
def guardian_add_whitelist(cmd: str, list_type: str = "binaries") -> Dict:
    """
    Añade un comando/proceso a la lista blanca.
    
    Args:
        cmd: Nombre del binario o proceso
        list_type: "binaries" | "processes"
        
    Returns:
        Lista actualizada
    """
    if list_type == "binaries":
        if cmd not in config["whitelist_binaries"]:
            config["whitelist_binaries"].append(cmd)
            save_config(config)
        return {"whitelist_binaries": config["whitelist_binaries"]}
    elif list_type == "processes":
        if cmd not in config["whitelist_processes"]:
            config["whitelist_processes"].append(cmd)
            save_config(config)
        return {"whitelist_processes": config["whitelist_processes"]}
    else:
        return {"error": "list_type debe ser 'binaries' o 'processes'"}


@mcp.tool()
def guardian_remove_whitelist(cmd: str, list_type: str = "binaries") -> Dict:
    """
    Quita un comando/proceso de la lista blanca.
    
    Args:
        cmd: Nombre del binario o proceso
        list_type: "binaries" | "processes"
        
    Returns:
        Lista actualizada
    """
    if list_type == "binaries":
        if cmd in config["whitelist_binaries"]:
            config["whitelist_binaries"].remove(cmd)
            save_config(config)
        return {"whitelist_binaries": config["whitelist_binaries"]}
    elif list_type == "processes":
        if cmd in config["whitelist_processes"]:
            config["whitelist_processes"].remove(cmd)
            save_config(config)
        return {"whitelist_processes": config["whitelist_processes"]}
    else:
        return {"error": "list_type debe ser 'binaries' o 'processes'"}


@mcp.tool()
def guardian_add_allowed_dir(path: str) -> Dict:
    """Añade un directorio a la lista de permitidos para file_delete."""
    p = str(Path(path).resolve())
    if p not in config["allowed_dirs"]:
        config["allowed_dirs"].append(p)
        save_config(config)
    return {"allowed_dirs": config["allowed_dirs"]}


# --- Main ---
if __name__ == "__main__":
    mcp.run(transport="stdio")