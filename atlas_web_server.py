#!/usr/bin/env python3
"""
atlas_web_server.py — Dashboard real de Atlas (un solo servidor).

Sirve el dashboard.html Y agrega todos los datos del ecosistema desde la DB
real (events/sessions) + reutiliza la logica de atlas_foco / atlas_health /
atlas_orchestrator. Elimina la dependencia de opencode serve + 3 servers.

Endpoints:
  GET /                      -> dashboard.html (UI estatica)
  GET /api/overview          -> daemon (heartbeat) + events totales + sesiones + ultimo tick
  GET /api/top-apps          -> top aplicaciones ultimas 24h (duracion real)
  GET /api/foco              -> resumen foco de hoy (reusa atlas_foco)
  GET /api/health            -> semaforo del sistema (reusa atlas_health)
  GET /api/orchestrator      -> providers activos + modelos (reusa atlas_orchestrator)
  GET /api/modelo            -> modelo activo (config opencode)

Uso:
  python atlas_web_server.py --port 4100
"""
import argparse
import importlib
import io
import json
import os
import sqlite3
import sys
from contextlib import redirect_stdout
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(os.environ.get("ATLAS_ROOT", Path(__file__).parent)).resolve()
WEB_DIR = ROOT / "atlas_web"
STATE_DIR = ROOT / "memory_data" / "state"
DB_PATH = STATE_DIR / "memory.db"
HEARTBEAT = STATE_DIR / "daemon.heartbeat"
DASHBOARD = WEB_DIR / "dashboard.html"

_prov_cache = {}
_cache_ts = {}


def _cache_ok(key: str, ttl: float) -> bool:
    now = datetime.now().timestamp()
    return key in _cache_ts and now - _cache_ts[key] < ttl


def _db() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH), timeout=10)
    conn.row_factory = sqlite3.Row
    return conn


def _table_counts() -> dict:
    conn = _db()
    try:
        out = {}
        for tbl in ("events", "sessions"):
            try:
                out[tbl] = conn.execute(f"SELECT COUNT(*) AS c FROM {tbl}").fetchone()["c"]
            except Exception:
                out[tbl] = 0
        return out
    finally:
        conn.close()


def heartbeat() -> dict | None:
    if HEARTBEAT.exists():
        try:
            return json.loads(HEARTBEAT.read_text(encoding="utf-8"))
        except Exception:
            return None
    return None


def overview() -> dict:
    counts = _table_counts()
    hb = heartbeat()
    daemon_status = "up" if hb else "down"
    if hb:
        try:
            age = (datetime.now(timezone.utc) -
                   datetime.fromisoformat(hb.get("last_tick", ""))).total_seconds()
        except Exception:
            age = -1
    else:
        age = None
    return {
        "daemon": hb,
        "daemon_status": daemon_status,
        "daemon_age_seconds": age,
        "events_total": counts.get("events", 0),
        "sessions_total": counts.get("sessions", 0),
        "last_tick": hb.get("last_tick") if hb else None,
        "uptime_seconds": hb.get("uptime_seconds") if hb else None,
        "foco_mode": hb.get("foco_mode") if hb else None,
        "paused": hb.get("paused") if hb else None,
    }


def top_apps(hours: int = 24) -> list:
    conn = _db()
    try:
        since = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat(timespec="seconds")
        rows = conn.execute(
            "SELECT app, COUNT(*) AS n, SUM(COALESCE(duration_seconds,0)) AS total_seconds "
            "FROM events WHERE type='activity' AND app IS NOT NULL AND ts >= ? "
            "GROUP BY app ORDER BY total_seconds DESC, n DESC LIMIT 12",
            (since,),
        ).fetchall()
        out = []
        for r in rows:
            out.append({"app": r["app"], "events": r["n"],
                        "total_seconds": r["total_seconds"] or 0})
        return out
    finally:
        conn.close()


def _call_attr(mod_name: str, attr: str, *args, **kwargs):
    """Importa un modulo y llama una funcion, silenciando prints de CLI."""
    sys.path.insert(0, str(ROOT))
    mod = importlib.import_module(mod_name)
    fn = getattr(mod, attr)
    buf = io.StringIO()
    with redirect_stdout(buf):
        return fn(*args, **kwargs)


def foco_daily() -> dict:
    try:
        return _call_attr("atlas_foco", "foco_daily_summary")
    except Exception as e:
        return {"error": str(e)}


def health() -> dict:
    try:
        return _call_attr("atlas_health", "health_report")
    except Exception as e:
        return {"error": str(e)}


def orchestrator() -> dict:
    try:
        return _call_attr("atlas_orchestrator", "active_providers")
    except Exception as e:
        return {"error": str(e)}


def activo_modelo() -> dict:
    """Modelo activo desde la config de opencode (mejor esfuerzo)."""
    import re
    cfg_candidates = [
        Path(os.environ.get("APPDATA", "")) / "opencode" / "opencode.jsonc",
        Path.home() / ".config" / "opencode" / "opencode.jsonc",
    ]
    model = "auto/best-coding"
    for p in cfg_candidates:
        if p.exists():
            try:
                txt = p.read_text(encoding="utf-8")
                m = re.search(r'"model"\s*:\s*"([^"]+)"', txt)
                if m:
                    model = m.group(1)
                    break
            except Exception:
                pass
    return {"model": model}


def informes() -> dict:
    """Lista de informes publicados (REQ-C8) desde state/reports_index.json."""
    idx = STATE_DIR / "reports_index.json"
    if not idx.exists():
        return {"count": 0, "reports": []}
    try:
        data = json.loads(idx.read_text(encoding="utf-8"))
        reports = sorted(data, key=lambda r: r.get("published", ""), reverse=True)
        return {"count": len(reports), "reports": reports}
    except Exception as e:
        return {"count": 0, "reports": [], "error": str(e)}


def evals() -> dict:
    """Ultima evaluacion mensual (REQ-C15) desde state/evals/<mes>.json."""
    evals_dir = STATE_DIR / "evals"
    if not evals_dir.exists():
        return {"error": "sin evals todavia"}
    files = sorted(evals_dir.glob("*.json"))
    if not files:
        return {"error": "sin evals todavia"}
    try:
        return json.loads(files[-1].read_text(encoding="utf-8"))
    except Exception as e:
        return {"error": str(e)}


def _json(data: dict) -> bytes:
    return json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")


# --- C2: TAREAS + PENDIENTES + TRUST ---
C2_STATE = STATE_DIR / "tasks"
C2_TRUST = STATE_DIR / "trust_log.jsonl"


def api_tareas():
    if not C2_STATE.exists():
        return {"items": []}
    items = []
    for p in sorted(C2_STATE.glob("*.json"), key=lambda x: x.stat().st_mtime, reverse=True):
        try:
            c = json.loads(p.read_text(encoding="utf-8"))
            items.append({
                "id": c["task_id"],
                "orden": c.get("orden_literal", "")[:80],
                "estado": c["estado"],
                "pct": c["progreso_pct"],
                "intentos": f"{c['intentos']}/{c['max_intentos']}",
                "criterios": [(x["id"], x["estado"]) for x in c["criterios"]],
                "timeout": c.get("timeout"),
            })
        except Exception:
            continue
    return {"items": items}


def api_pendientes():
    """Escaladas + criterios humanos + DEBT activos."""
    items = []
    if C2_STATE.exists():
        for p in C2_STATE.glob("*.json"):
            try:
                c = json.loads(p.read_text(encoding="utf-8"))
                if c["estado"] == "ESCALADA":
                    fails = [x["id"] for x in c["criterios"] if x["estado"] == "FAIL"]
                    items.append({
                        "tipo": "escalada",
                        "task_id": c["task_id"],
                        "detalle": f"{c['progreso_pct']}% · faltan {fails}",
                        "fecha": c.get("cerrado_en") or c.get("creado_en"),
                    })
                humanos = [x for x in c["criterios"] if x["estado"] == "HUMANO"]
                if humanos and c["estado"] != "TERMINADA":
                    items.append({
                        "tipo": "gate_humano",
                        "task_id": c["task_id"],
                        "detalle": f"{len(humanos)} criterios requieren tu acción",
                        "fecha": c.get("creado_en"),
                    })
            except Exception:
                continue
    items.sort(key=lambda x: x.get("fecha") or "", reverse=True)
    return {"items": items}


def api_trust():
    """Claims falsos del agente."""
    if not C2_TRUST.exists():
        return {"items": [], "total": 0}
    lines = C2_TRUST.read_text(encoding="utf-8").strip().splitlines()[-50:]
    items = [json.loads(l) for l in lines if l.strip()]
    return {"items": items, "total": len(items)}


class _Handler(BaseHTTPRequestHandler):
    def _send(self, code: int, body: bytes, ctype: str):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def _json_response(self, data: dict, code: int = 200):
        self._send(code, _json(data), "application/json; charset=utf-8")

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "*")
        self.end_headers()

    def do_GET(self):
        path = self.path.split("?")[0]
        try:
            if path in ("/", "/index.html"):
                if DASHBOARD.exists():
                    body = DASHBOARD.read_bytes()
                    self._send(200, body, "text/html; charset=utf-8")
                else:
                    self._json_response({"error": f"falta {DASHBOARD}"}, 500)
            elif path == "/api/overview":
                self._json_response(overview())
            elif path == "/api/top-apps":
                self._json_response({"apps": top_apps(), "hours": 24})
            elif path == "/api/foco":
                self._json_response(foco_daily())
            elif path == "/api/health":
                self._json_response(health())
            elif path == "/api/orchestrator":
                self._json_response({"providers": orchestrator()})
            elif path == "/api/modelo":
                self._json_response(activo_modelo())
            elif path == "/api/informes":
                self._json_response(informes())
            elif path == "/api/evals":
                self._json_response(evals())
            elif path == "/api/tareas":
                self._json_response(api_tareas())
            elif path == "/api/pendientes":
                self._json_response(api_pendientes())
            elif path == "/api/trust":
                self._json_response(api_trust())
            elif path.startswith("/informe/"):
                self._serve_informe(path)
            else:
                self._json_response({"error": "not found",
                                     "routes": ["/", "/api/overview", "/api/top-apps",
                                                "/api/foco", "/api/health",
                                                "/api/orchestrator", "/api/modelo",
                                                "/api/informes", "/api/evals",
                                                "/api/tareas", "/api/pendientes",
                                                "/api/trust", "/informe/<nombre>"]}, 404)
        except Exception as e:
            self._json_response({"error": str(e)}, 500)

    def _serve_informe(self, path: str):
        """Sirve un informe HTML publicado en vault/outputs/."""
        name = path.split("/")[-1]
        if not name or ".." in name:
            self._json_response({"error": "nombre invalido"}, 400)
            return
        base = Path(os.environ.get("MEMORY_ROOT", ROOT / "memory_data")) / "vault" / "outputs"
        f = base / name
        if not f.exists() or not f.is_file():
            self._json_response({"error": f"informe no encontrado: {name}"}, 404)
            return
        body = f.read_bytes()
        self._send(200, body, "text/html; charset=utf-8")

    def log_message(self, *args):
        pass


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=4100)
    args = ap.parse_args()
    srv = ThreadingHTTPServer(("127.0.0.1", args.port), _Handler)
    print(f"atlas_web_server en http://127.0.0.1:{args.port}  (dashboard + /api/*)")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()