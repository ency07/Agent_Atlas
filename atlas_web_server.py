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
import re
import sqlite3
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from collections import Counter
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
DASHBOARD_V3 = WEB_DIR / "dashboard_v3.html"
FRICTION_LOG = STATE_DIR / "friction_log.jsonl"
ORDERS_DIR = STATE_DIR / "orders"
HB_TASK_DIR = STATE_DIR / "task_heartbeat"
CONFIRM_DIR = STATE_DIR / "confirmaciones"
UI_CONFIG = STATE_DIR / "ui_config.json"

for d in (ORDERS_DIR, HB_TASK_DIR, CONFIRM_DIR):
    d.mkdir(parents=True, exist_ok=True)

_prov_cache = {}
_cache_ts = {}

# === B1: Caché background para endpoints pesados ===
_BG_CACHE = {"health": None, "orchestrator": None}
_BG_CACHE_TS = {"health": 0, "orchestrator": 0}
_BG_CACHE_TTL = 60  # segundos


def _bg_refresh():
    """Thread background: refresca health y orchestrator cada 60s."""
    import threading
    def _loop():
        while True:
            try:
                _BG_CACHE["health"] = _call_attr("atlas_health", "health_report")
                _BG_CACHE_TS["health"] = time.time()
            except Exception:
                _BG_CACHE["health"] = {"status": "unknown", "checks": []}
                _BG_CACHE_TS["health"] = time.time()
            try:
                _BG_CACHE["orchestrator"] = _call_attr("atlas_orchestrator", "report")
                _BG_CACHE_TS["orchestrator"] = time.time()
            except Exception:
                _BG_CACHE["orchestrator"] = []
                _BG_CACHE_TS["orchestrator"] = time.time()
            time.sleep(_BG_CACHE_TTL)
    t = threading.Thread(target=_loop, daemon=True, name="bg-cache")
    t.start()


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


# --- P-2: Friction Log ---
VALID_FRICTION_TYPES = {"correccion", "repeticion", "espera_larga", "negativa", "exito_falso", "espera"}

def friction_write(event_type: str, detail: str = "", meta: dict = None) -> dict:
    """Escribe un evento de fricción al JSONL."""
    if event_type not in VALID_FRICTION_TYPES:
        return {"error": f"tipo invalido: {event_type}. Validos: {VALID_FRICTION_TYPES}"}
    FRICTION_LOG.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "type": event_type,
        "detail": detail,
        "meta": meta or {},
    }
    with open(FRICTION_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return {"ok": True, "entry": entry}


def friction_read(limit: int = 100) -> dict:
    """Lee eventos de fricción (más recientes primero)."""
    if not FRICTION_LOG.exists():
        return {"count": 0, "items": [], "debug": "v2-friction_read"}
    lines = FRICTION_LOG.read_text(encoding="utf-8").strip().splitlines()
    items = [json.loads(l) for l in lines[-limit:] if l.strip()]
    items.reverse()  # más reciente primero
    return {"count": len(items), "items": items, "debug": "v2-friction_read"}


def friction_weekly() -> dict:
    """Métrica semanal de fricciones para panel P-3."""
    if not FRICTION_LOG.exists():
        return {"weeks": [], "total": 0}
    from collections import Counter
    weekly = Counter()
    for line in FRICTION_LOG.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            ev = json.loads(line)
            ts = datetime.fromisoformat(ev["ts"].replace("Z", "+00:00"))
            week_key = ts.strftime("%Y-W%U")
            weekly[week_key] += 1
        except Exception:
            continue
    weeks = [{"week": k, "count": v} for k, v in sorted(weekly.items())]
    return {"weeks": weeks, "total": sum(weekly.values())}


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


# --- DASH v3: Adaptador base ---
_adaptador_cache = {}
_adaptador_ts = {}


def _adaptador_stale(key: str, fetch_fn, ttl_s: int = 900):
    """Patrón: intenta fetch_fn(); fallo → caché + stale=True."""
    now = time.time()
    if key in _adaptador_ts and now - _adaptador_ts[key] < ttl_s:
        return _adaptador_cache.get(key), False
    try:
        data = fetch_fn()
        _adaptador_cache[key] = data
        _adaptador_ts[key] = now
        return data, False
    except Exception:
        return _adaptador_cache.get(key), True


# --- DASH v3: /api/live ---
def api_live() -> dict:
    """Heartbeat + tasks + pasos/ETA + última acción. SOLO lectura archivos → <50ms."""
    hb = heartbeat()
    health_r = _BG_CACHE.get("health") or {}
    daemon_age = None
    if hb:
        try:
            daemon_age = int((datetime.now(timezone.utc) -
                              datetime.fromisoformat(hb.get("last_tick", ""))).total_seconds())
        except Exception:
            daemon_age = -1
    tasks = _task_heartbeats()
    active_tasks = [t for t in tasks if t.get("heartbeat_status") != "done"]
    perms = _pending_confirmations()
    last_action = max(
        [t.get("last_beat", "") for t in tasks if t.get("last_beat")],
        default=None,
    )
    return {
        "health_status": health_r.get("status", "unknown"),
        "daemon_age_s": daemon_age,
        "tasks_active": len(active_tasks),
        "tasks": tasks,
        "permissions_pending": perms,
        "last_action_ts": last_action,
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }


def _task_heartbeats() -> list:
    """Lee todos los task_heartbeat/*.json y clasifica."""
    tasks = []
    if not HB_TASK_DIR.exists():
        return tasks
    for f in HB_TASK_DIR.glob("*.json"):
        try:
            hb = json.loads(f.read_text(encoding="utf-8"))
            age_s = int((datetime.now(timezone.utc) -
                         datetime.fromisoformat(hb["last_beat"])).total_seconds())
            alive = hb.get("tokens_alive", False)
            pegado = age_s > 60 and not alive
            if age_s > 120 and not alive:
                status = "red"
            elif age_s > 60 and not alive:
                status = "yellow"
            else:
                status = "green"
            hb["heartbeat_age_s"] = age_s
            hb["heartbeat_status"] = status
            tasks.append(hb)
        except Exception:
            continue
    tasks.sort(key=lambda t: t.get("last_beat", ""), reverse=True)
    return tasks


def _pending_confirmations() -> list:
    """Lista de permisos pendientes (no expirados)."""
    perms = []
    timeout_s = 60
    if UI_CONFIG.exists():
        try:
            cfg = json.loads(UI_CONFIG.read_text(encoding="utf-8"))
            timeout_s = cfg.get("permission_timeout_s", 60)
        except Exception:
            pass
    if not CONFIRM_DIR.exists():
        return perms
    now = datetime.now(timezone.utc)
    for f in CONFIRM_DIR.glob("*.json"):
        try:
            c = json.loads(f.read_text(encoding="utf-8"))
            if c.get("resolved"):
                continue
            created = datetime.fromisoformat(c.get("created", "")).replace(tzinfo=timezone.utc)
            age = (now - created).total_seconds()
            if age > timeout_s:
                c["resolved"] = True
                c["resolution"] = "DENY"
                c["resolved_at"] = now.isoformat(timespec="seconds")
                f.write_text(json.dumps(c, ensure_ascii=False, indent=2), encoding="utf-8")
                continue
            perms.append({
                "id": c.get("id"),
                "task_id": c.get("task_id"),
                "detail": c.get("detail", ""),
                "created": c.get("created"),
                "age_s": int(age),
            })
        except Exception:
            continue
    return perms


# --- DASH v3: Adaptadores externos ---
def _fetch_mercado() -> dict:
    """stooq (bonds, S&P500) + CoinGecko (BTC)."""
    data = {"bonds": None, "sp500": None, "btc": None, "ts": None}
    try:
        req = urllib.request.Request(
            "https://stooq.com/q/l/?s=^spx&f=sd2t2ohlcv&h&e=csv",
            headers={"User-Agent": "Atlas/1.0"},
        )
        with urllib.request.urlopen(req, timeout=10) as r:
            lines = r.read().decode("utf-8").strip().splitlines()
            if len(lines) >= 2:
                parts = lines[1].split(",")
                if len(parts) >= 7:
                    data["sp500"] = {"close": parts[6], "high": parts[4], "low": parts[5]}
    except Exception:
        pass
    try:
        req = urllib.request.Request(
            "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd&include_24hr_change=true",
            headers={"User-Agent": "Atlas/1.0"},
        )
        with urllib.request.urlopen(req, timeout=10) as r:
            cg = json.loads(r.read())
            if "bitcoin" in cg:
                data["btc"] = cg["bitcoin"]
    except Exception:
        pass
    data["ts"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    return data


def _fetch_noticias(sources: list = None) -> dict:
    """RSS xml.etree desde fuentes configuradas en ui_config."""
    if not sources:
        sources = [
            "https://feeds.bbci.co.uk/news/technology/rss.xml",
            "https://rss.nytimes.com/services/xml/rss/nyt/Technology.xml",
        ]
    items = []
    for url in sources[:3]:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Atlas/1.0"})
            with urllib.request.urlopen(req, timeout=10) as r:
                xml_bytes = r.read()
            root = ET.fromstring(xml_bytes)
            channel = root.find("channel")
            if channel is None:
                continue
            for item in channel.findall("item")[:5]:
                title = (item.findtext("title") or "").strip()
                link = (item.findtext("link") or "").strip()
                pub = (item.findtext("pubDate") or "").strip()
                desc = (item.findtext("description") or "").strip()[:200]
                if title:
                    items.append({"title": title, "link": link, "pubDate": pub, "source": url, "snippet": desc})
        except Exception:
            continue
    items.sort(key=lambda i: i.get("pubDate", ""), reverse=True)
    return {"items": items[:10], "count": len(items)}


def _fetch_clima() -> dict:
    """open-meteo: temp, humedad, viento."""
    try:
        req = urllib.request.Request(
            "https://api.open-meteo.com/v1/forecast?latitude=6.25&longitude=-75.56"
            "&current=temperature_2m,relative_humidity_2m,wind_speed_10m,weather_code"
            "&timezone=America/Bogota",
            headers={"User-Agent": "Atlas/1.0"},
        )
        with urllib.request.urlopen(req, timeout=10) as r:
            data = json.loads(r.read())
        cur = data.get("current", {})
        return {
            "temperature": cur.get("temperature_2m"),
            "humidity": cur.get("relative_humidity_2m"),
            "wind_speed": cur.get("wind_speed_10m"),
            "weather_code": cur.get("weather_code"),
            "timezone": data.get("timezone"),
            "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }
    except Exception as e:
        return {"error": str(e)}


def _fetch_grafo() -> dict:
    """Knowledge graph: top nodos desde memory.db (graph_nodes + notes_index)."""
    max_nodes = 150
    if UI_CONFIG.exists():
        try:
            cfg = json.loads(UI_CONFIG.read_text(encoding="utf-8"))
            max_nodes = cfg.get("max_graph_nodes", 150)
        except Exception:
            pass
    nodes = []
    try:
        conn = _db()
        rows = conn.execute(
            "SELECT id, label, type FROM graph_nodes ORDER BY id LIMIT ?",
            (max_nodes,),
        ).fetchall()
        for r in rows:
            nodes.append({"id": r["id"], "label": (r["label"] or r["id"])[:40], "type": r["type"]})
        if not nodes:
            rows = conn.execute(
                "SELECT id, title, type FROM notes_index ORDER BY id LIMIT ?",
                (max_nodes,),
            ).fetchall()
            for r in rows:
                nodes.append({"id": r["id"], "label": (r["title"] or r["id"])[:40], "type": r["type"]})
        conn.close()
    except Exception:
        pass
    edges = []
    try:
        conn = _db()
        conn.row_factory = sqlite3.Row
        node_ids = {n["id"] for n in nodes}
        for link in conn.execute("SELECT source, target FROM graph_edges").fetchall():
            src, tgt = link["source"], link["target"]
            if src in node_ids and tgt in node_ids:
                edges.append({"from": src, "to": tgt})
        conn.close()
    except Exception:
        pass
    return {"nodes": nodes[:max_nodes], "edges": edges[:max_nodes * 2], "total_nodes": len(nodes)}


# --- DASH v3: Órdenes ---
def api_orden_create(texto: str, prioridad: str = "normal") -> dict:
    """Crea una orden en state/orders/."""
    if not texto or not texto.strip():
        return {"ok": False, "error": "texto vacío"}
    order_id = f"ORD-{datetime.now().strftime('%Y%m%d-%H%M%S-%f')}"
    nivel = "L1"
    try:
        sys.path.insert(0, str(ROOT))
        from atlas_c4 import classify_level, generate_contract
        nivel = classify_level(texto)
        contract = generate_contract(texto)
    except Exception:
        contract = {"orden_literal": texto, "nivel": nivel}
    order = {
        "order_id": order_id,
        "texto": texto.strip(),
        "nivel": nivel,
        "estado": "PENDIENTE",
        "created": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "completed": None,
        "result": None,
        "prioridad": prioridad,
        "contract": contract,
    }
    order_path = ORDERS_DIR / f"{order_id}.json"
    tmp = order_path.with_suffix(".tmp")
    tmp.write_text(json.dumps(order, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(order_path)
    requires_confirmation = nivel in ("L2", "L3")
    preview = None
    if requires_confirmation:
        preview = {
            "nivel": nivel,
            "criterios": contract.get("criterios", []),
            "modelo": contract.get("modelo", ""),
            "max_intentos": contract.get("max_intentos", 5),
            "timeout_min": contract.get("timeout_min", 20),
        }
    return {
        "ok": True,
        "order_id": order_id,
        "preview": preview,
        "requires_confirmation": requires_confirmation,
    }


# --- DASH v3: Confirmaciones ---
def api_confirm_create(task_id: str, detail: str = "", order_id: str = "") -> dict:
    """Crea una confirmación pendiente."""
    perm_id = f"PERM-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    entry = {
        "id": perm_id,
        "task_id": task_id,
        "order_id": order_id,
        "detail": detail,
        "created": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "resolved": False,
        "resolution": None,
        "resolved_at": None,
    }
    p = CONFIRM_DIR / f"{perm_id}.json"
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(entry, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(p)
    return {"ok": True, "id": perm_id}


def api_confirm_resolve(perm_id: str, allow: bool) -> dict:
    """Resuelve una confirmación (allow/deny)."""
    p = CONFIRM_DIR / f"{perm_id}.json"
    if not p.exists():
        return {"ok": False, "error": "no encontrada"}
    try:
        entry = json.loads(p.read_text(encoding="utf-8"))
        entry["resolved"] = True
        entry["resolution"] = "ALLOW" if allow else "DENY"
        entry["resolved_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
        tmp = p.with_suffix(".tmp")
        tmp.write_text(json.dumps(entry, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(p)
        return {"ok": True, "resolution": entry["resolution"]}
    except Exception as e:
        return {"ok": False, "error": str(e)}


# --- DASH v3: UI Config ---
def api_ui_config_read() -> dict:
    if not UI_CONFIG.exists():
        return {}
    try:
        return json.loads(UI_CONFIG.read_text(encoding="utf-8"))
    except Exception:
        return {}


def api_ui_config_write(data: dict) -> dict:
    current = api_ui_config_read()
    current.update(data)
    tmp = UI_CONFIG.with_suffix(".tmp")
    tmp.write_text(json.dumps(current, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(UI_CONFIG)
    return {"ok": True, "config": current}


def api_preferences_get() -> dict:
    """Lee preferences (nombre/ciudad/usuario) desde memory.db."""
    conn = _db()
    try:
        rows = [dict(r) for r in conn.execute(
            "SELECT key,value,scope,project FROM preferences ORDER BY scope,project,key")]
    finally:
        conn.close()
    prefs = {r["key"]: r["value"] for r in rows}
    return {
        "ok": True,
        "preferences": prefs,
        "user_name": prefs.get("user_name", ""),
        "usuario": prefs.get("user_name", prefs.get("nombre", "")),
        "ciudad": prefs.get("ciudad", prefs.get("city", "")),
        "onboarding_done": bool(prefs.get("user_name")),
    }


def api_preferences_set(data: dict) -> dict:
    """Guarda preferences (user_name, ciudad) en memory.db + vault MD."""
    conn = _db()
    try:
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        saved = []
        for key in ("user_name", "ciudad"):
            val = str(data.get(key, "")).strip()
            if not val:
                continue
            conn.execute(
                "INSERT OR REPLACE INTO preferences (key,value,scope,project,updated) "
                "VALUES (?,?,?,?,?)",
                (key, val, "global", "global", now),
            )
            saved.append(key)
        conn.commit()
    finally:
        conn.close()
    # espejo en vault/global/preferences
    try:
        pref_dir = ROOT / "memory_data" / "vault" / "global" / "preferences"
        pref_dir.mkdir(parents=True, exist_ok=True)
        for key in saved:
            val = data.get(key, "").strip()
            (pref_dir / f"{key}.md").write_text(
                f"---\ntype: preference\nproject: global\nupdated: {now}\n---\n\n# {key}\n\n{val}\n",
                encoding="utf-8",
            )
    except Exception:
        pass
    return {"ok": True, "saved": saved, "onboarding_done": True}


def api_memory(query: str = "", limit: int = 5) -> dict:
    """Recuerdos relevantes FTS5 (para gadget MEMORY)."""
    conn = _db()
    try:
        if query:
            q = query.replace("'", "''")
            rows = [dict(r) for r in conn.execute(
                "SELECT id,title,type,project,summary FROM notes_fts "
                "JOIN notes_index USING(id) WHERE notes_fts MATCH ? LIMIT ?",
                (q, min(int(limit), 10)))]
        else:
            rows = [dict(r) for r in conn.execute(
                "SELECT id,title,type,project,summary FROM notes_index "
                "ORDER BY id DESC LIMIT ?", (min(int(limit), 10),))]
    except Exception:
        rows = []
    finally:
        conn.close()
    return {"ok": True, "count": len(rows), "items": rows}


def api_guardian() -> dict:
    """Eventos guardian recientes desde notes_index (tag=guardian,audit,blocked)."""
    conn = _db()
    try:
        rows = [dict(r) for r in conn.execute(
            "SELECT id,title,summary,type FROM notes_index "
            "WHERE title LIKE '%guard_block%' OR title LIKE '%guardian%' "
            "ORDER BY id DESC LIMIT 8")]
    except Exception:
        rows = []
    finally:
        conn.close()
    return {"ok": True, "count": len(rows), "events": rows}


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

    def do_POST(self):
        path = self.path.split("?")[0]
        try:
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length).decode("utf-8")
            data = json.loads(body) if body else {}
            if path == "/api/friction":
                event_type = data.get("type")
                detail = data.get("detail", "")
                meta = data.get("meta", {})
                result = friction_write(event_type, detail, meta)
                code = 200 if result.get("ok") else 400
                self._json_response(result, code)
            elif path == "/api/orden":
                texto = data.get("texto", "")
                prioridad = data.get("prioridad", "normal")
                result = api_orden_create(texto, prioridad)
                self._json_response(result, 200 if result.get("ok") else 400)
            elif path == "/api/confirmaciones":
                task_id = data.get("task_id", "")
                detail = data.get("detail", "")
                order_id = data.get("order_id", "")
                result = api_confirm_create(task_id, detail, order_id)
                self._json_response(result, 200 if result.get("ok") else 400)
            elif path == "/api/preferences":
                result = api_preferences_set(data)
                self._json_response(result, 200 if result.get("ok") else 400)
            elif path.startswith("/api/confirmaciones/"):
                perm_id = path.split("/")[-1]
                allow = data.get("allow", False)
                result = api_confirm_resolve(perm_id, allow)
                self._json_response(result, 200 if result.get("ok") else 400)
            elif path == "/api/ui_config":
                result = api_ui_config_write(data)
                self._json_response(result, 200 if result.get("ok") else 400)
            else:
                self._json_response({"error": "not found"}, 404)
        except Exception as e:
            self._json_response({"error": str(e)}, 500)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "*")
        self.end_headers()

    def do_GET(self):
        path = self.path.split("?")[0]
        try:
            if path in ("/", "/index.html"):
                ui_v3 = 1
                if UI_CONFIG.exists():
                    try:
                        cfg = json.loads(UI_CONFIG.read_text(encoding="utf-8"))
                        ui_v3 = cfg.get("UI_V3", 1)
                    except Exception:
                        pass
                if ui_v3 and DASHBOARD_V3.exists():
                    body = DASHBOARD_V3.read_bytes()
                    self._send(200, body, "text/html; charset=utf-8")
                elif DASHBOARD.exists():
                    body = DASHBOARD.read_bytes()
                    self._send(200, body, "text/html; charset=utf-8")
                else:
                    self._json_response({"error": f"falta dashboard"}, 500)
            elif path.startswith("/atlas_web/"):
                asset = WEB_DIR / Path(path[len("/atlas_web/"):])
                if asset.exists() and asset.is_file():
                    mime = "application/javascript" if asset.suffix == ".js" else "text/css"
                    self._send(200, asset.read_bytes(), mime + "; charset=utf-8")
                else:
                    self._json_response({"error": "asset not found"}, 404)
            elif path == "/api/overview":
                self._json_response(overview())
            elif path == "/api/top-apps":
                self._json_response({"apps": top_apps(), "hours": 24})
            elif path == "/api/foco":
                self._json_response(foco_daily())
            elif path == "/api/health":
                self._json_response(_BG_CACHE.get("health") or health())
            elif path == "/api/orchestrator":
                cached = _BG_CACHE.get("orchestrator")
                self._json_response({"providers": cached if cached is not None else orchestrator()})
            elif path == "/api/modelo":
                self._json_response(activo_modelo())
            elif path == "/api/informes":
                self._json_response(informes())
            elif path == "/api/evals":
                self._json_response(evals())
            elif path == "/api/friction":
                self._json_response(friction_read())
            elif path == "/api/friction/weekly":
                self._json_response(friction_weekly())
            elif path == "/api/tareas":
                self._json_response(api_tareas())
            elif path == "/api/pendientes":
                self._json_response(api_pendientes())
            elif path == "/api/trust":
                self._json_response(api_trust())
            elif path == "/api/live":
                self._json_response(api_live())
            elif path == "/api/preferences":
                self._json_response(api_preferences_get())
            elif path == "/api/notas":
                query = ""
                limit = 5
                if "?" in self.path:
                    qs = self.path.split("?", 1)[1]
                    for p in qs.split("&"):
                        if p.startswith("q="):
                            query = urllib.parse.unquote(p[2:])
                        elif p.startswith("limit="):
                            limit = int(p[6:])
                self._json_response(api_memory(query, limit))
            elif path == "/api/guardian":
                self._json_response(api_guardian())
            elif path == "/api/mercado":
                data, stale = _adaptador_stale("mercado", _fetch_mercado, ttl_s=900)
                out = dict(data or {})
                out["stale"] = stale
                self._json_response(out)
            elif path == "/api/noticias":
                cfg = api_ui_config_read()
                sources = cfg.get("news_sources", [])
                data, stale = _adaptador_stale("noticias", lambda: _fetch_noticias(sources), ttl_s=1800)
                out = dict(data or {})
                out["stale"] = stale
                self._json_response(out)
            elif path == "/api/clima":
                data, stale = _adaptador_stale("clima", _fetch_clima, ttl_s=1800)
                out = dict(data or {})
                out["stale"] = stale
                self._json_response(out)
            elif path == "/api/grafo":
                data, stale = _adaptador_stale("grafo", _fetch_grafo, ttl_s=900)
                out = dict(data or {})
                out["stale"] = stale
                self._json_response(out)
            elif path == "/api/ui_config":
                self._json_response(api_ui_config_read())
            elif path.startswith("/api/task_heartbeat/"):
                task_id = path.split("/")[-1]
                hb_path = HB_TASK_DIR / f"{task_id}.json"
                if hb_path.exists():
                    self._json_response(json.loads(hb_path.read_text(encoding="utf-8")))
                else:
                    self._json_response({"error": "sin heartbeat"}, 404)
            elif path.startswith("/api/confirmaciones/"):
                perm_id = path.split("/")[-1]
                cp = CONFIRM_DIR / f"{perm_id}.json"
                if cp.exists():
                    self._json_response(json.loads(cp.read_text(encoding="utf-8")))
                else:
                    self._json_response({"error": "no encontrada"}, 404)
            elif path.startswith("/informe/"):
                self._serve_informe(path)
            else:
                self._json_response({"error": "not found", "debug": "v3-else",
                                      "routes": ["/", "/api/overview", "/api/top-apps",
                                                 "/api/foco", "/api/health",
                                                 "/api/orchestrator", "/api/modelo",
                                                 "/api/informes", "/api/evals",
                                                 "/api/tareas", "/api/pendientes",
                                                 "/api/trust", "/api/live",
                                                 "/api/ui_config",
                                                 "/api/mercado", "/api/noticias",
                                                 "/api/clima", "/api/grafo",
                                                 "/api/orden", "/api/confirmaciones",
                                                 "/informe/<nombre>"]}, 404)
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
    _bg_refresh()  # B1: iniciar caché background health/orchestrator
    srv = ThreadingHTTPServer(("127.0.0.1", args.port), _Handler)
    print(f"atlas_web_server en http://127.0.0.1:{args.port}  (dashboard + /api/*)")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()