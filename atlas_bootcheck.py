# ============================================================
# atlas_bootcheck.py — Verificación E2E al iniciar sesión
# ------------------------------------------------------------
# Verifica: daemon memoria, dashboard web, proveedores críticos.
# Muestra toast verde/rojo según estado.
# Se ejecuta al logon via Task Scheduler (start_atlas_bootcheck.vbs)
#
# Uso: python atlas_bootcheck.py [--timeout 30]
# ============================================================
import sys
import time
import json
import socket
import subprocess
import urllib.request
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).parent
LOG_DIR = ROOT / "logs"
STATE_DIR = ROOT / "memory_data" / "state"
HEARTBEAT_FILE = STATE_DIR / "daemon.heartbeat"

def notify(title, message, is_error=False):
    """Toast de Windows"""
    try:
        from win10toast import ToastNotifier
        toaster = ToastNotifier()
        icon = None  # Podría usar .ico custom
        toaster.show_toast(title, message, duration=15, icon_path=icon)
    except Exception as e:
        print(f"Toast falló: {e}")

def check_port(host, port, timeout=2):
    """Verifica puerto TCP"""
    try:
        sock = socket.create_connection((host, port), timeout=timeout)
        sock.close()
        return True
    except Exception:
        return False

def check_http(url, timeout=10):
    """Verifica HTTP GET"""
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return r.status == 200
    except Exception:
        return False

def check_daemon():
    """Verifica daemon de memoria via heartbeat"""
    if not HEARTBEAT_FILE.exists():
        return False, "sin heartbeat"
    try:
        import json
        hb = json.loads(HEARTBEAT_FILE.read_text(encoding='utf-8'))
        import time
        age = time.time() - datetime.fromisoformat(hb["last_tick"]).timestamp()
        if age < 120:
            return True, f"PID {hb['pid']} · {int(age)}s ago"
        return False, f"heartbeat stale ({int(age)}s)"
    except Exception as e:
        return False, f"error: {e}"

def check_web():
    """Verifica dashboard web"""
    ok = check_http("http://127.0.0.1:4100/api/health", timeout=10)
    return ok, "dashboard respondiendo" if ok else "dashboard no responde"

def check_providers():
    """Verifica proveedores críticos (al menos 1 activo)"""
    results = []
    
    # OmniRoute
    if check_port("127.0.0.1", 20128):
        try:
            with urllib.request.urlopen("http://localhost:20128/v1/models", timeout=4) as r:
                if r.status == 200:
                    results.append(("omniroute", True, "API ok"))
                else:
                    results.append(("omniroute", False, f"HTTP {r.status}"))
        except Exception:
            results.append(("omniroute", False, "puerto abierto pero API no responde"))
    else:
        results.append(("omniroute", False, "puerto 20128 cerrado"))
    
    # 9Router
    if check_port("127.0.0.1", 4000):
        try:
            with urllib.request.urlopen("http://localhost:4000/v1/models", timeout=4) as r:
                if r.status == 200:
                    results.append(("9router", True, "API ok"))
                else:
                    results.append(("9router", False, f"HTTP {r.status}"))
        except Exception:
            results.append(("9router", False, "puerto abierto pero API no responde"))
    else:
        results.append(("9router", False, "puerto 4000 cerrado"))
    
    # Ollama
    if check_port("127.0.0.1", 11434):
        try:
            with urllib.request.urlopen("http://localhost:11434/api/tags", timeout=4) as r:
                if r.status == 200:
                    results.append(("ollama", True, "API ok"))
                else:
                    results.append(("ollama", False, f"HTTP {r.status}"))
        except Exception:
            results.append(("ollama", False, "puerto abierto pero API no responde"))
    else:
        results.append(("ollama", False, "puerto 11434 cerrado"))
    
    active = [r for r in results if r[1]]
    return len(active) > 0, f"{len(active)}/3 activos: " + ", ".join([r[0] for r in active])

def check_venv():
    """Verifica venv"""
    venv_python = ROOT / ".venv" / "Scripts" / "python.exe"
    return venv_python.exists(), ".venv ok" if venv_python.exists() else "falta .venv"

def run_bootcheck(timeout=30):
    """Ejecuta todos los checks y muestra toast"""
    print(f"[{datetime.now().isoformat()}] === BOOT CHECK INICIO ===")
    
    checks = [
        ("Daemon memoria", check_daemon),
        ("Dashboard web", check_web),
        ("Proveedores IA", check_providers),
        ("Entorno Python", check_venv),
    ]
    
    results = []
    for name, check_fn in checks:
        try:
            ok, detail = check_fn()
            results.append({"name": name, "ok": ok, "detail": detail})
            print(f"  [OK] {name}: {detail}" if ok else f"  [FAIL] {name}: {detail}")
        except Exception as e:
            results.append({"name": name, "ok": False, "detail": f"excepcion: {e}"})
            print(f"  [FAIL] {name}: excepcion: {e}")
    
    failed = [r for r in results if not r["ok"]]
    critical_failed = [r for r in failed if r["name"] in ("Daemon memoria", "Proveedores IA")]
    
    if not failed:
        status = "green"
        msg = "✅ Atlas OK: todos los servicios activos"
    elif critical_failed:
        status = "red"
        msg = "🔴 Atlas DEGRADADO: " + "; ".join([f"{r['name']} ({r['detail']})" for r in critical_failed])
    else:
        status = "yellow"
        msg = "🟡 Atlas PARCIAL: " + "; ".join([f"{r['name']} ({r['detail']})" for r in failed])
    
    # Toast
    title = f"Atlas Boot Check - {status.upper()}"
    notify(title, msg, is_error=(status == "red"))
    
    # Log
    log_file = LOG_DIR / "bootcheck.log"
    LOG_DIR.mkdir(exist_ok=True)
    with open(log_file, 'a', encoding='utf-8') as f:
        f.write(f"[{datetime.now().isoformat()}] {status.upper()}: {msg}\n")
        for r in results:
            f.write(f"  {r['name']}: {'OK' if r['ok'] else 'FAIL'} - {r['detail']}\n")
    
    print(f"[{datetime.now().isoformat()}] === BOOT CHECK FIN: {status.upper()} ===")
    return status, results

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--timeout", type=int, default=30, help="Timeout total en segundos")
    args = parser.parse_args()
    
    status, _ = run_bootcheck(args.timeout)
    sys.exit(0 if status != "red" else 1)