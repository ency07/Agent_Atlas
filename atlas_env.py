#!/usr/bin/env python3
"""
atlas_env.py — Snapshot del entorno con TTL por tipo + invalidación por evento + verificación on-demand.

C3-1: El agente cita "scan de hace X min". Apps/puertos/procesos/workspace/archivos recientes/tiempo.
"""
import json
import os
import time
import subprocess
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, Optional, List

ROOT = Path(__file__).parent
STATE_DIR = ROOT / "memory_data" / "state"
CACHE_FILE = STATE_DIR / "env_snapshot_cache.json"

# TTL por categoría (segundos)
TTL = {
    "apps": 300,          # 5 min
    "ports": 60,          # 1 min
    "processes": 60,
    "workspace": 600,     # 10 min
    "recent_files": 300,
    "time": 1,            # siempre fresco
}

_cache: Dict[str, Any] = {}
_timestamps: Dict[str, float] = {}
_lock = threading.Lock()

def _now() -> float:
    return time.time()

def _save_cache():
    try:
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        data = {"cache": _cache, "timestamps": _timestamps}
        CACHE_FILE.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass

def _load_cache():
    global _cache, _timestamps
    if CACHE_FILE.exists():
        try:
            data = json.loads(CACHE_FILE.read_text(encoding="utf-8"))
            _cache = data.get("cache", {})
            _timestamps = data.get("timestamps", {})
        except Exception:
            _cache, _timestamps = {}, {}

# ----- Colectores -----
def _collect_apps() -> List[str]:
    # lista de ejecutables en PATH + conocidos
    out = []
    for p in os.environ.get("PATH", "").split(os.pathsep):
        try:
            for f in Path(p).iterdir():
                if f.suffix.lower() in (".exe", ".bat", ".cmd"):
                    out.append(f.name)
        except Exception:
            pass
    return sorted(set(out))

def _collect_ports() -> Dict[int, bool]:
    # puertos de interés
    ports = {20128, 4000, 11434, 4096, 4100, 4102, 4103}
    res = {}
    import socket
    for port in ports:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.5):
                res[port] = True
        except Exception:
            res[port] = False
    return res

def _collect_processes() -> List[Dict[str, Any]]:
    try:
        import psutil
        procs = []
        for p in psutil.process_iter(['pid','name','cpu_percent','memory_percent']):
            try:
                procs.append(p.info)
            except Exception:
                pass
        return procs[:50]
    except Exception:
        return []

def _collect_workspace() -> Dict[str, Any]:
    return {
        "cwd": str(Path.cwd()),
        "project_root": str(ROOT),
        "git_branch": _git_branch(),
    }

def _git_branch() -> Optional[str]:
    try:
        out = subprocess.check_output(["git","rev-parse","--abbrev-ref","HEAD"], cwd=ROOT, stderr=subprocess.DEVNULL, text=True, timeout=2)
        return out.strip()
    except Exception:
        return None

def _collect_recent_files() -> List[str]:
    files = []
    for ext in (".py",".md",".json",".vbs",".ps1"):
        for f in ROOT.rglob(f"*{ext}"):
            try:
                if f.stat().st_mtime > _now() - 86400:
                    files.append(str(f.relative_to(ROOT)))
            except Exception:
                pass
    return sorted(files)[:100]

def _collect_time() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")

_COLLECTORS = {
    "apps": _collect_apps,
    "ports": _collect_ports,
    "processes": _collect_processes,
    "workspace": _collect_workspace,
    "recent_files": _collect_recent_files,
    "time": _collect_time,
}

# ----- API pública -----
def get_snapshot(category: Optional[str]=None, force: bool=False) -> Dict[str, Any]:
    """Devuelve snapshot de una categoría o todas. Si force=True ignora TTL."""
    with _lock:
        if not _cache:
            _load_cache()
        result = {}
        cats = [category] if category else list(_COLLECTORS.keys())
        for cat in cats:
            ts = _timestamps.get(cat, 0)
            if force or (_now() - ts) > TTL.get(cat, 300) or cat not in _cache:
                collector = _COLLECTORS.get(cat)
                if collector:
                    _cache[cat] = collector()
                    _timestamps[cat] = _now()
            result[cat] = _cache.get(cat)
            # incluir metadata de antigüedad
            age = int(_now() - _timestamps.get(cat, _now()))
            result[f"{cat}_age_seconds"] = age
        _save_cache()
        return result

def invalidate(category: str):
    """Invalida una categoría para que se refresque en próxima petición."""
    with _lock:
        if category in _timestamps:
            _timestamps[category] = 0
            _save_cache()

def invalidate_all():
    with _lock:
        for cat in _COLLECTORS.keys():
            _timestamps[cat] = 0
        _save_cache()

def on_demand_check(category: str) -> Dict[str, Any]:
    """Verificación explícita bajo demanda (ignora TTL)."""
    return get_snapshot(category, force=True)

# ----- CLI -----
if __name__ == "__main__":
    import sys
    if "--snapshot" in sys.argv:
        cat = None
        for i,a in enumerate(sys.argv):
            if a == "--cat" and i+1 < len(sys.argv):
                cat = sys.argv[i+1]
        print(json.dumps(get_snapshot(cat), ensure_ascii=False, indent=2))
    elif "--invalidate" in sys.argv:
        cat = None
        for i,a in enumerate(sys.argv):
            if a == "--cat" and i+1 < len(sys.argv):
                cat = sys.argv[i+1]
        if cat:
            invalidate(cat)
            print(f"Invalidated {cat}")
        else:
            invalidate_all()
            print("Invalidated all")
    else:
        print("Uso: python atlas_env.py --snapshot [--cat <categoria>] | --invalidate [--cat <categoria>]")