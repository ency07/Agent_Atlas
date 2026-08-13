#!/usr/bin/env python3
"""
Atlas Foco MCP Server (F3) — Métricas de foco + control de modo disciplina.

Provee:
  - foco_set_mode(mode)           → cambia modo: off | soft | strict
  - foco_get_rules()              → reglas actuales
  - foco_daily_summary(date)      → tiempo productivo vs fugado (traspaso a F4)
  - foco_override(app, category)  → override manual de categoría
  - foco_backfill()               → clasifica eventos históricos sin categoría

CLI:
  python atlas_foco.py --cli daily            → resumen de hoy
  python atlas_foco.py --cli backfill         → clasifica eventos pendientes
  python atlas_foco.py --cli validate         → valida reglas

Config: state/foco_rules.json (ver templates/foco_rules.json.example)
"""

import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from mcp.server.fastmcp import FastMCP

import foco_rules

MEMORY_ROOT = Path(os.environ.get("MEMORY_ROOT", str(Path(__file__).parent / "memory_data"))).resolve()
STATE_DIR = MEMORY_ROOT / "state"
DB_PATH = STATE_DIR / "memory.db"

mcp = FastMCP("atlas_foco", host="127.0.0.1", port=4100)


def _db():
    import sqlite3
    conn = sqlite3.connect(str(DB_PATH), timeout=10)
    conn.row_factory = sqlite3.Row
    return conn


def _events_for_day(conn, day: datetime) -> list:
    start = day.replace(hour=0, minute=0, second=0, microsecond=0)
    end = start + timedelta(days=1)
    start_iso = start.astimezone(timezone.utc).isoformat(timespec="seconds")
    end_iso = end.astimezone(timezone.utc).isoformat(timespec="seconds")
    rows = conn.execute(
        "SELECT app, window_title, category, monetizable, duration_seconds, ts "
        "FROM events WHERE type='activity' AND ts >= ? AND ts < ?",
        (start_iso, end_iso),
    ).fetchall()
    return [dict(r) for r in rows]


def _events_uncategorized(conn, limit: int = 5000) -> list:
    rows = conn.execute(
        "SELECT id, app, window_title, category FROM events "
        "WHERE (category IS NULL OR category = '') ORDER BY ts DESC LIMIT ?",
        (limit,),
    ).fetchall()
    return [dict(r) for r in rows]


def _today() -> datetime:
    return datetime.now().astimezone()


@mcp.tool()
def foco_set_mode(mode: str) -> dict:
    """
    Cambia el modo de disciplina de foco.

    Args:
        mode: "off" (solo medir) | "soft" (avisos con presupuesto, default) | "strict" (avisos agresivos)
    """
    result = foco_rules.set_mode(mode)
    if "error" in result:
        return result
    return {"success": True, "mode": result["mode"], "hint": "El daemon de actividad leerá el nuevo modo en <1 min"}


@mcp.tool()
def foco_get_rules() -> dict:
    """Devuelve las reglas de foco actuales (modo, categorías, umbrales, excepciones)."""
    rules = foco_rules.load_rules()
    errs = foco_rules.validate_rules(rules)
    rules["_validation_errors"] = errs
    return rules


@mcp.tool()
def foco_daily_summary(date: str = "") -> dict:
    """
    Resumen de foco de un día: tiempo productivo vs fugado + top apps.

    Args:
        date: Fecha opcional en formato YYYY-MM-DD. Vacío = hoy.
    """
    conn = _db()
    try:
        if date:
            day = datetime.strptime(date, "%Y-%m-%d").astimezone()
        else:
            day = _today()
        events = _events_for_day(conn, day)
        summary = foco_rules.daily_summary(events)
        summary["date"] = day.strftime("%Y-%m-%d")
        return summary
    finally:
        conn.close()


@mcp.tool()
def foco_override(app: str, category: str) -> dict:
    """
    Override manual: fuerza la categoría de una app (se aplica en futuras clasificaciones).

    Args:
        app: Nombre del ejecutable (ej: "opera.exe")
        category: Categoría destino (ej: "social") — debe existir en las reglas
    """
    rules = foco_rules.load_rules()
    if category not in rules.get("categories", {}):
        return {"error": f"Categoría '{category}' no existe. Disponibles: {list(rules['categories'].keys())}"}
    app_lower = app.lower()
    for name, cat in rules["categories"].items():
        apps = cat.get("apps", [])
        apps = [a for a in apps if a.lower() != app_lower]
        cat["apps"] = apps
    rules["categories"][category]["apps"].append(app)
    foco_rules.save_rules(rules)
    return {"success": True, "app": app, "category": category}


@mcp.tool()
def foco_backfill(limit: int = 5000, force: bool = False) -> dict:
    """
    Clasifica eventos históricos.

    Args:
        limit: Máximo de eventos a procesar (default 5000)
        force: True = reclasifica TODOS los eventos (útil al cambiar reglas);
               False = solo los que aún no tienen categoría
    """
    conn = _db()
    rules = foco_rules.load_rules()
    processed = 0
    changed = 0
    try:
        if force:
            rows = conn.execute(
                "SELECT id, app, window_title, category FROM events "
                "ORDER BY ts DESC LIMIT ?",
                (limit,),
            ).fetchall()
            pending = [dict(r) for r in rows]
        else:
            pending = _events_uncategorized(conn, limit)
        for ev in pending:
            cat, mon = foco_rules.classify(ev.get("app", ""), ev.get("window_title", ""), rules)
            conn.execute(
                "UPDATE events SET category=?, monetizable=? WHERE id=?",
                (cat, 1 if mon else 0, ev["id"]),
            )
            processed += 1
            if cat != ev.get("category"):
                changed += 1
        conn.commit()
    finally:
        conn.close()
    return {"success": True, "processed": processed, "changed": changed}


# --- CLI ---
def _cli_daily():
    conn = _db()
    try:
        events = _events_for_day(conn, _today())
    finally:
        conn.close()
    s = foco_rules.daily_summary(events)
    s["date"] = _today().strftime("%Y-%m-%d")
    total_min = s["total_seconds"] / 60
    prod_min = s["productive_seconds"] / 60
    dist_min = s["distraction_seconds"] / 60
    print(f"FOCO · {s['date']} · modo {s['mode']}")
    print(f"  total:       {total_min:.0f} min")
    print(f"  productivo:  {prod_min:.0f} min  ({s['focus_pct']}%)")
    print(f"  distracción: {dist_min:.0f} min")
    print(f"  top distracciones:")
    for t in s["top_distractions"]:
        print(f"    - {t['app']}: {t['seconds']/60:.0f} min")
    print(f"  top productivo:")
    for t in s["top_productive"]:
        print(f"    - {t['app']}: {t['seconds']/60:.0f} min")


def _cli_backfill(force: bool = False):
    r = foco_backfill(force=force)
    print(json.dumps(r, ensure_ascii=False, indent=2))


def main():
    if len(sys.argv) >= 3 and sys.argv[1] == "--cli":
        cmd = sys.argv[2]
        if cmd == "daily":
            _cli_daily()
        elif cmd == "backfill":
            _cli_backfill(force="--force" in sys.argv)
        elif cmd == "validate":
            rules = foco_rules.load_rules()
            errs = foco_rules.validate_rules(rules)
            if errs:
                print("ERRORES:"); [print(f"  - {e}") for e in errs]; sys.exit(1)
            print(f"OK · mode {rules['mode']}")
        else:
            print(f"comando CLI desconocido: {cmd}")
        return
    if "--http" in sys.argv:
        run_http()
        return
    mcp.run(transport="stdio")


def run_http(port: int = 4101):
    """Servidor HTTP mínimo para el dashboard (GET /daily y /rules)."""
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

    class Handler(BaseHTTPRequestHandler):
        def _json(self, obj, code=200):
            body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            try:
                if self.path.startswith("/daily"):
                    conn = _db()
                    try:
                        events = _events_for_day(conn, _today())
                    finally:
                        conn.close()
                    s = foco_rules.daily_summary(events)
                    s["date"] = _today().strftime("%Y-%m-%d")
                    self._json(s)
                elif self.path.startswith("/rules"):
                    self._json(foco_rules.load_rules())
                else:
                    self._json({"error": "not found", "routes": ["/daily", "/rules"]}, 404)
            except Exception as exc:
                self._json({"error": str(exc)}, 500)

        def log_message(self, *a):
            pass

    srv = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(f"atlas_foco http en http://127.0.0.1:{port}  (GET /daily /rules)")
    srv.serve_forever()


if __name__ == "__main__":
    main()
