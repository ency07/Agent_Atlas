# ============================================================
# atlas_supervisor.py — Servicio de auto-reparación para Atlas
# ------------------------------------------------------------
# Monitorea el semáforo de salud y reinicia componentes caídos.
# - Instancia única (lockfile + mutex)
# - Cooldown para evitar thrashing
# - Notificaciones via toast (Windows)
# - Logs estructurados en logs/supervisor.log
#
# Uso: python atlas_supervisor.py
#      (se ejecuta al logon via start_atlas_supervisor.vbs)
# ============================================================
import os
import sys
import json
import time
import logging
import subprocess
import psutil
import threading
from datetime import datetime, timedelta
from pathlib import Path

# --- Config ---
ROOT = Path(__file__).parent
LOG_DIR = ROOT / "logs"
STATE_DIR = ROOT / "memory_data" / "state"
LOCK_FILE = STATE_DIR / "supervisor.lock"
LOG_FILE = LOG_DIR / "supervisor.log"
COOLDOWN_FILE = STATE_DIR / "supervisor_cooldown.json"

# --- Logging ---
logging.basicConfig(
    level=logging.INFO,
    format='{"timestamp":"%(asctime)s","level":"%(levelname)s","message":"%(message)s"}',
    handlers=[
        logging.FileHandler(LOG_FILE, encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("atlas_supervisor")

# --- Lockfile (instancia única) ---
class LockManager:
    def __init__(self, lock_file):
        self.lock_file = lock_file
        self.lock_file.parent.mkdir(parents=True, exist_ok=True)

    def acquire(self):
        if self.lock_file.exists():
            try:
                data = json.loads(self.lock_file.read_text())
                pid = data.get("pid")
                if pid and psutil.pid_exists(pid):
                    logger.error(f"Supervisor ya en ejecución (PID {pid})")
                    return False
            except Exception as e:
                logger.warning(f"Lockfile corrupto: {e}")
        
        self.lock_file.write_text(json.dumps({"pid": os.getpid(), "started": datetime.now().isoformat()}))
        return True

    def release(self):
        if self.lock_file.exists():
            self.lock_file.unlink()

# --- Health Check ---
def load_health():
    """Carga el reporte de salud usando atlas_health.health_report()"""
    try:
        sys.path.insert(0, str(ROOT))
        import atlas_health
        return atlas_health.health_report()
    except Exception as e:
        logger.error(f"Error al cargar health: {e}")
        return None

# --- Componentes a supervisar ---
COMPONENTS = {
    "memory": {
        "cmd": [sys.executable, "mcp_memory_server.py"],
        "cwd": ROOT,
        "log": "memory.log",
        "check": lambda h: h.get("daemon", {}).get("status") == "ok"
    },
    "web": {
        "cmd": [sys.executable, "atlas_web_server.py"],
        "cwd": ROOT,
        "log": "web.log",
        "check": lambda h: h.get("dashboard", {}).get("status") == "ok"
    },
    "orchestrator": {
        "cmd": [sys.executable, "atlas_orchestrator.py"],
        "cwd": ROOT,
        "log": "orchestrator.log",
        "check": lambda h: h.get("orchestrator", {}).get("status") == "ok"
    }
}

# --- Cooldown ---
def is_on_cooldown(component):
    if not COOLDOWN_FILE.exists():
        return False
    try:
        cooldowns = json.loads(COOLDOWN_FILE.read_text())
        if component in cooldowns:
            until = datetime.fromisoformat(cooldowns[component])
            return datetime.now() < until
    except Exception as e:
        logger.warning(f"Error al leer cooldown: {e}")
    return False

def set_cooldown(component, minutes=5):
    cooldowns = {}
    if COOLDOWN_FILE.exists():
        try:
            cooldowns = json.loads(COOLDOWN_FILE.read_text())
        except Exception:
            pass
    cooldowns[component] = (datetime.now() + timedelta(minutes=minutes)).isoformat()
    COOLDOWN_FILE.write_text(json.dumps(cooldowns))

# --- Notificaciones ---
def notify(title, message):
    try:
        from win10toast import ToastNotifier
        toaster = ToastNotifier()
        toaster.show_toast(title, message, duration=10)
    except Exception as e:
        logger.warning(f"Toast falló: {e}")

# --- Reinicio de componentes ---
def restart_component(name, config):
    logger.info(f"Reiniciando {name}...")
    
    # Matar proceso existente
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            if proc.info['cmdline'] and any(str(config['cmd'][0]) in str(x) for x in proc.info['cmdline']):
                logger.info(f"Matando PID {proc.info['pid']}")
                proc.kill()
        except Exception as e:
            logger.warning(f"Error al matar proceso: {e}")
    
    # Iniciar nuevo proceso
    try:
        log_path = LOG_DIR / config['log']
        with open(log_path, 'a', encoding='utf-8') as log_file:
            subprocess.Popen(
                config['cmd'],
                cwd=config['cwd'],
                stdout=log_file,
                stderr=log_file,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP
            )
        logger.info(f"{name} reiniciado")
        return True
    except Exception as e:
        logger.error(f"Error al reiniciar {name}: {e}")
        return False

# --- Loop principal ---
def monitor():
    logger.info("Supervisor iniciado")
    
    while True:
        try:
            health = load_health()
            if not health:
                logger.warning("Health no disponible")
                time.sleep(30)
                continue
            
            for name, config in COMPONENTS.items():
                if is_on_cooldown(name):
                    continue
                
                if not config['check'](health):
                    logger.warning(f"{name} caído")
                    if restart_component(name, config):
                        set_cooldown(name)
                        notify("Atlas Supervisor", f"{name} reiniciado")
                    else:
                        set_cooldown(name, minutes=10)
                        notify("Atlas Supervisor", f"Fallo al reiniciar {name}")
            
            time.sleep(30)
        except Exception as e:
            logger.error(f"Error en loop: {e}")
            time.sleep(10)

# --- Entrada ---
if __name__ == "__main__":
    lock = LockManager(LOCK_FILE)
    if not lock.acquire():
        sys.exit(1)
    
    try:
        monitor()
    except KeyboardInterrupt:
        logger.info("Supervisor detenido")
    finally:
        lock.release()
