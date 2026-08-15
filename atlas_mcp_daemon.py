#!/usr/bin/env python3
"""
atlas_mcp_daemon.py — Daemon persistente para servidores MCP.
Mantiene los servidores MCP calientes para evitar cold start (P-4).

Uso:
  python atlas_mcp_daemon.py              # inicia todos los MCPs configurados
  python atlas_mcp_daemon.py --list       # lista MCPs disponibles
  python atlas_mcp_daemon.py --stop       # detiene todos
"""
import argparse
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).parent
STATE_DIR = ROOT / "memory_data" / "state"
LOCK_FILE = STATE_DIR / "mcp_daemon.lock"
LOG_DIR = ROOT / "logs"

MCP_CONFIGS = [
    {
        "name": "memory",
        "cmd": [sys.executable, "mcp_memory_server.py"],
        "cwd": str(ROOT),
        "stdio": "pipe",  # MCP via stdio
    },
    {
        "name": "orchestrator",
        "cmd": [sys.executable, "atlas_orchestrator.py"],
        "cwd": str(ROOT),
        "stdio": "pipe",
    },
    {
        "name": "foco",
        "cmd": [sys.executable, "atlas_foco.py"],
        "cwd": str(ROOT),
        "stdio": "pipe",
    },
    {
        "name": "guardian",
        "cmd": [sys.executable, "atlas_guardian.py"],
        "cwd": str(ROOT),
        "stdio": "pipe",
    },
]

# Optional: mcp_windows if exists
MCP_WINDOWS = ROOT / "mcp_windows" / "mcp_windows_server.py"
if MCP_WINDOWS.exists():
    MCP_CONFIGS.append({
        "name": "mcp_windows",
        "cmd": [sys.executable, str(MCP_WINDOWS)],
        "cwd": str(ROOT / "mcp_windows"),
        "stdio": "pipe",
    })

class MCPDaemon:
    def __init__(self):
        self.processes = {}
        self.running = False
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        LOG_DIR.mkdir(parents=True, exist_ok=True)

    def acquire_lock(self):
        if LOCK_FILE.exists():
            try:
                data = json.loads(LOCK_FILE.read_text())
                pid = data.get("pid")
                if pid and self._pid_exists(pid):
                    print(f"MCP Daemon ya corriendo (PID {pid})")
                    return False
            except Exception:
                pass
        LOCK_FILE.write_text(json.dumps({"pid": os.getpid(), "started": time.time()}))
        return True

    def _pid_exists(self, pid):
        try:
            os.kill(pid, 0)
            return True
        except OSError:
            return False

    def release_lock(self):
        if LOCK_FILE.exists():
            LOCK_FILE.unlink()

    def start_mcp(self, config):
        name = config["name"]
        log_file = LOG_DIR / f"mcp_{name}.log"
        log_f = open(log_file, "a", encoding="utf-8")
        log_f.write(f"\n--- {time.ctime()} starting {name} ---\n")
        log_f.flush()
        
        proc = subprocess.Popen(
            config["cmd"],
            cwd=config["cwd"],
            stdin=subprocess.PIPE,
            stdout=log_f,
            stderr=log_f,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == 'nt' else 0,
        )
        self.processes[name] = {"proc": proc, "log": log_f, "config": config}
        print(f"  Started {name} (PID {proc.pid})")
        return proc

    def start_all(self):
        print("Iniciando MCPs persistentes...")
        for config in MCP_CONFIGS:
            self.start_mcp(config)
        self.running = True
        print(f"Total MCPs iniciados: {len(self.processes)}")

    def stop_all(self):
        print("Deteniendo MCPs...")
        for name, info in self.processes.items():
            proc = info["proc"]
            if proc.poll() is None:
                print(f"  Stopping {name} (PID {proc.pid})")
                if os.name == 'nt':
                    proc.terminate()
                else:
                    proc.send_signal(signal.SIGTERM)
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill()
            info["log"].close()
        self.processes.clear()
        self.running = False

    def status(self):
        print("Estado MCPs:")
        for name, info in self.processes.items():
            proc = info["proc"]
            status = "running" if proc.poll() is None else f"stopped (exit {proc.returncode})"
            print(f"  {name}: {status} (PID {proc.pid})")
        if not self.processes:
            print("  (ninguno)")

def main():
    parser = argparse.ArgumentParser(description="MCP Daemon persistente")
    parser.add_argument("--list", action="store_true", help="Listar MCPs configurados")
    parser.add_argument("--stop", action="store_true", help="Detener todos los MCPs")
    parser.add_argument("--status", action="store_true", help="Mostrar estado")
    args = parser.parse_args()

    daemon = MCPDaemon()

    if args.list:
        for c in MCP_CONFIGS:
            print(f"  {c['name']}: {' '.join(c['cmd'])}")
        return

    if args.stop:
        # Try to stop existing daemon
        if LOCK_FILE.exists():
            try:
                data = json.loads(LOCK_FILE.read_text())
                pid = data.get("pid")
                if pid:
                    try:
                        os.kill(pid, signal.SIGTERM)
                        print(f"Señal de parada enviada a PID {pid}")
                    except OSError:
                        print(f"Proceso {pid} no encontrado")
            except Exception:
                pass
        return

    if args.status:
        if LOCK_FILE.exists():
            try:
                data = json.loads(LOCK_FILE.read_text())
                pid = data.get("pid")
                if pid and daemon._pid_exists(pid):
                    print(f"Daemon corriendo (PID {pid})")
                else:
                    print("Lock file existe pero proceso muerto")
            except Exception:
                print("Lock file corrupto")
        else:
            print("Daemon no corriendo")
        return

    if not daemon.acquire_lock():
        sys.exit(1)

    def sig_handler(sig, frame):
        print("\nSeñal recibida, deteniendo...")
        daemon.stop_all()
        daemon.release_lock()
        sys.exit(0)

    signal.signal(signal.SIGINT, sig_handler)
    signal.signal(signal.SIGTERM, sig_handler)

    try:
        daemon.start_all()
        print("MCP Daemon corriendo. Ctrl+C para detener.")
        while daemon.running:
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        daemon.stop_all()
        daemon.release_lock()

if __name__ == "__main__":
    main()