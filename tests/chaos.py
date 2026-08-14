# ============================================================
# tests/chaos.py — Failure Injection / Chaos Testing
# ------------------------------------------------------------
# Mata procesos, corrompe inbox, simula fallos de red.
# Verifica que el supervisor recupere el sistema.
#
# Uso: python tests/chaos.py --duration 300 --seed 42
# ============================================================
import sys
import os
import time
import json
import random
import argparse
import subprocess
import signal
from pathlib import Path
from datetime import datetime, timedelta

ROOT = Path(__file__).parent.parent

# --- Config ---
COMPONENTS = {
    "memory": "mcp_memory_server.py",
    "web": "atlas_web_server.py",
    "orchestrator": "atlas_orchestrator.py",
    "chat": "atlas_chat.py",
    "activity": "atlas_activity.py"
}

INBOX_DIR = ROOT / "memory_data" / "inbox"
LOG_FILE = ROOT / "logs" / "chaos.log"

def log(msg):
    timestamp = datetime.now().isoformat()
    line = f"[{timestamp}] {msg}"
    print(line)
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG_FILE, 'a', encoding='utf-8') as f:
        f.write(line + '\n')

def find_pids(script_name):
    """Encuentra PIDs de procesos que ejecutan script_name"""
    pids = []
    for proc in psutil.process_iter(['pid', 'cmdline']):
        try:
            cmdline = proc.info.get('cmdline', [])
            if cmdline and any(script_name in str(c) for c in cmdline):
                pids.append(proc.info['pid'])
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    return pids

def kill_component(name):
    """Mata un componente aleatoriamente"""
    pids = find_pids(COMPONENTS[name])
    if not pids:
        log(f"[CHAOS] {name}: no hay procesos corriendo")
        return False
    
    pid = random.choice(pids)
    try:
        os.kill(pid, signal.SIGTERM)
        log(f"[CHAOS] {name}: matado PID {pid}")
        return True
    except Exception as e:
        log(f"[CHAOS] {name}: error al matar PID {pid}: {e}")
        return False

def corrupt_inbox():
    """Corrompe un archivo en inbox con JSON inválido"""
    INBOX_DIR.mkdir(parents=True, exist_ok=True)
    corrupt_file = INBOX_DIR / f"chaos_{int(time.time())}.json"
    corrupt_file.write_text("{ invalid json }")
    log(f"[CHAOS] Inbox corrompido: {corrupt_file.name}")
    return True

def block_port(port):
    """Simula fallo de red (requiere admin - solo loggea)"""
    log(f"[CHAOS] Simulando bloqueo de puerto {port} (solo log)")
    return True

def check_recovery(name, timeout=120):
    """Verifica que el supervisor reinicie el componente"""
    start = time.time()
    while time.time() - start < timeout:
        pids = find_pids(COMPONENTS[name])
        if pids:
            log(f"[RECOVERY] {name}: recuperado (PIDs: {pids})")
            return True
        time.sleep(2)
    log(f"[RECOVERY] {name}: NO recuperado en {timeout}s")
    return False

def run_chaos(duration, seed):
    random.seed(seed)
    log(f"=== CHAOS START: duration={duration}s, seed={seed} ===")
    
    end_time = time.time() + duration
    actions = [
        ("kill_memory", lambda: kill_component("memory")),
        ("kill_web", lambda: kill_component("web")),
        ("kill_orchestrator", lambda: kill_component("orchestrator")),
        ("corrupt_inbox", corrupt_inbox),
        ("block_port_20128", lambda: block_port(20128)),
        ("block_port_4000", lambda: block_port(4000)),
        ("block_port_11434", lambda: block_port(11434)),
    ]
    
    while time.time() < end_time:
        action_name, action = random.choice(actions)
        log(f"[CHAOS] Ejecutando: {action_name}")
        action()
        
        # Verificar recuperación
        if action_name.startswith("kill_"):
            comp = action_name.split("_")[1]
            if not check_recovery(comp, timeout=60):
                log(f"[ALERTA] {comp} no se recuperó")
        
        # Espera aleatoria entre acciones
        wait = random.uniform(5, 30)
        time.sleep(wait)
    
    log("=== CHAOS END ===")
    return True

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--duration", type=int, default=300, help="Duración en segundos")
    parser.add_argument("--seed", type=int, default=42, help="Seed para reproducibilidad")
    args = parser.parse_args()
    
    try:
        import psutil
    except ImportError:
        log("ERROR: psutil no instalado. pip install psutil")
        sys.exit(1)
    
    run_chaos(args.duration, args.seed)