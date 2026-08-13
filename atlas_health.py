#!/usr/bin/env python3
"""
atlas_health.py — Semáforo de estado del ecosistema Atlas.

Verifica cada componente y devuelve un estado global:
  green: todo OK | yellow: alertas | red: fallos criticos

Uso:
  python atlas_health.py --cli            # chequeo completo, texto plano
  python atlas_health.py --cli --json     # chequeo completo, JSON
  python atlas_health.py --http 4102      # HTTP GET /health para dashboard
  (sin args)                              # MCP server (tool health_check / health_status)
"""
import json
import os
import socket
import subprocess
import sys
import time
import warnings
from datetime import datetime

warnings.filterwarnings("ignore")

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("atlas-health")

PROJECT_ROOT = os.environ.get("MEMORY_ROOT", os.path.dirname(os.path.abspath(__file__)))
STATE_DIR = os.path.join(PROJECT_ROOT, "memory_data", "state")
INBOX_DIR = os.path.join(PROJECT_ROOT, "memory_data", "inbox")
HEARTBEAT = os.path.join(STATE_DIR, "daemon.heartbeat")


def _port_open(port: int, timeout: float = 1.0) -> bool:
    try:
        s = socket.create_connection(("127.0.0.1", port), timeout=timeout)
        s.close()
        return True
    except OSError:
        return False


def _check_component(name: str, ok: bool, detail: str = "", critical: bool = True):
    return {"name": name, "ok": ok, "detail": detail, "critical": critical}


def health_report() -> dict:
    checks = []

    # daemon de actividad (heartbeat)
    daemon = {"ok": False, "detail": "sin heartbeat", "age_s": -1}
    try:
        if os.path.exists(HEARTBEAT):
            hb = json.load(open(HEARTBEAT, encoding="utf-8"))
            last = datetime.fromisoformat(hb["last_tick"]).timestamp()
            age = time.time() - last
            daemon = {
                "ok": age < 120,
                "detail": f"PID {hb['pid']} · {hb['status']} · {int(age)}s ago",
                "age_s": int(age),
            }
    except Exception as exc:
        daemon = {"ok": False, "detail": f"error leyendo heartbeat: {exc}", "age_s": -1}
    checks.append(_check_component("daemon_activity", daemon["ok"], daemon["detail"]))

    # providers de modelos
    omniroute = _port_open(20128)
    checks.append(_check_component("omniroute", omniroute,
                                   "localhost:20128" if omniroute else "no responde"))
    ollama = _port_open(11434)
    checks.append(_check_component("ollama", ollama,
                                   "localhost:11434" if ollama else "no responde",
                                   critical=False))
    if not omniroute and not ollama:
        checks.append(_check_component("modelos", False, "ningun provider de modelos activo"))

    # infra base
    checks.append(_check_component("venv_python",
                                   os.path.exists(os.path.join(PROJECT_ROOT, ".venv", "Scripts", "python.exe")),
                                   ".venv ok" if os.path.exists(os.path.join(PROJECT_ROOT, ".venv")) else "falta .venv (corre setup.ps1)"))
    checks.append(_check_component("state_dir", os.path.isdir(STATE_DIR), STATE_DIR))

    # configs de estado
    for cfg in ("guardian.json", "foco_rules.json", "search.json"):
        p = os.path.join(STATE_DIR, cfg)
        checks.append(_check_component(f"config_{cfg[:-5]}", os.path.exists(p),
                                       cfg if os.path.exists(p) else f"falta {cfg} (setup.ps1)", critical=False))

    # inbox pendiente (colchon de eventos)
    try:
        pending = 0
        if os.path.isdir(INBOX_DIR):
            pending = sum(1 for f in os.listdir(INBOX_DIR) if f.endswith(".jsonl"))
        checks.append(_check_component("inbox_pending", pending <= 20,
                                       f"{pending} eventos por ingestar", critical=False))
    except Exception:
        pass

    # semáforo global
    criticals = [c for c in checks if c["critical"]]
    failures = [c for c in checks if not c["ok"] and c["critical"]]
    if failures:
        status = "red"
    elif any(not c["ok"] for c in checks):
        status = "yellow"
    else:
        status = "green"

    return {
        "status": status,
        "status_label": {"green": "✅ TODO OK", "yellow": "🟡 ALERTAS", "red": "🔴 FALLOS"}[status],
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "checks": checks,
    }


@mcp.tool()
def health_status() -> dict:
    """Semáforo global del ecosistema Atlas: green/yellow/red + detalle por componente."""
    return health_report()


@mcp.tool()
def health_check(name: str = "") -> dict:
    """Chequea un componente especifico (daemon_activity, omniroute, ollama, ...). Vacio = todo."""
    r = health_report()
    if name:
        r["checks"] = [c for c in r["checks"] if c["name"] == name]
    return r


# ---------------------------------------------------------------------------
# CLI + HTTP
# ---------------------------------------------------------------------------

def _cli():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    r = health_report()
    print(r["status_label"])
    for c in r["checks"]:
        icon = "[OK]  " if c["ok"] else "[FAIL]"
        crit = " (critico)" if c["critical"] and not c["ok"] else ""
        print(f"  {icon} {c['name']}: {c['detail']}{crit}")
    sys.exit(0 if r["status"] != "red" else 1)


def _http(port: int = 4102):
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            r = health_report()
            body = json.dumps(r, ensure_ascii=False).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *a):
            pass

    srv = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(f"atlas_health http en http://127.0.0.1:{port}  (GET /health)")
    srv.serve_forever()


if __name__ == "__main__":
    if "--cli" in sys.argv:
        _cli()
    elif "--http" in sys.argv:
        port = 4102
        for i, a in enumerate(sys.argv):
            if a == "--http" and i + 1 < len(sys.argv) and sys.argv[i + 1].isdigit():
                port = int(sys.argv[i + 1])
        _http(port)
    else:
        mcp.run(transport="stdio")
