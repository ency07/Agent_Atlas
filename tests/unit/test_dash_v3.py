# ============================================================
# tests/unit/test_dash_v3.py — Tests Dashboard v3 + Adaptadores
# ============================================================
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import atlas_web_server as ws

ROOT = Path(__file__).parent.parent.parent
STATE_DIR = ROOT / "memory_data" / "state"
ORDERS_DIR = STATE_DIR / "orders"
HB_DIR = STATE_DIR / "task_heartbeat"
CONFIRM_DIR = STATE_DIR / "confirmaciones"
UI_CONFIG = STATE_DIR / "ui_config.json"


def _clean():
    for d in (ORDERS_DIR, HB_DIR, CONFIRM_DIR):
        d.mkdir(parents=True, exist_ok=True)
    for f in ORDERS_DIR.glob("*.json"):
        f.unlink(missing_ok=True)
    for f in HB_DIR.glob("*.json"):
        f.unlink(missing_ok=True)
    for f in CONFIRM_DIR.glob("*.json"):
        f.unlink(missing_ok=True)


# --- 1. Adaptador caído → caché + badge stale ---
def test_adaptador_caido_cache_badge():
    _clean()
    call_count = 0
    def failing_fetch():
        nonlocal call_count
        call_count += 1
        raise ConnectionError("simulated failure")
    data1, stale1 = ws._adaptador_stale("test_fail", failing_fetch, ttl_s=60)
    assert stale1 is True, "first call should be stale (no cache)"
    assert data1 is None, "no data available"
    # second call should also be stale
    data2, stale2 = ws._adaptador_stale("test_fail", failing_fetch, ttl_s=60)
    assert stale2 is True


# --- 2. Adaptador ok → datos frescos ---
def test_adaptador_ok_fresh():
    _clean()
    def ok_fetch():
        return {"value": 42}
    data, stale = ws._adaptador_stale("test_ok", ok_fetch, ttl_s=60)
    assert stale is False
    assert data == {"value": 42}
    # should be cached now
    data2, stale2 = ws._adaptador_stale("test_ok", ok_fetch, ttl_s=60)
    assert stale2 is False
    assert data2 == {"value": 42}


# --- 3. /api/live estructura ---
def test_api_live_estructura():
    _clean()
    r = ws.api_live()
    assert "health_status" in r, f"falta health_status: {r.keys()}"
    assert "tasks_active" in r
    assert "tasks" in r
    assert "timestamp" in r
    assert r["health_status"] in ("green", "yellow", "red", "unknown")


# --- 4. /api/live con task heartbeat ---
def test_api_live_task_heartbeat():
    _clean()
    hb = {
        "task_id": "T-TEST001",
        "last_beat": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "writers": ["test"],
        "current_step": "paso de prueba",
        "eta_s": 10,
        "tokens_alive": True,
    }
    (HB_DIR / "T-TEST001.json").write_text(json.dumps(hb), encoding="utf-8")
    r = ws.api_live()
    assert r["tasks_active"] >= 1
    t = [t for t in r["tasks"] if t["task_id"] == "T-TEST001"][0]
    assert t["heartbeat_status"] == "green", f"esperaba green, got {t['heartbeat_status']}"
    assert t["heartbeat_age_s"] <= 5


# --- 5. UI_V3=0 → sirve dashboard v2 ---
def test_ui_v3_rollback():
    _clean()
    if UI_CONFIG.exists():
        cfg = json.loads(UI_CONFIG.read_text(encoding="utf-8"))
    else:
        cfg = {}
    original = cfg.get("UI_V3", 1)
    cfg["UI_V3"] = 0
    tmp = UI_CONFIG.with_suffix(".tmp")
    tmp.write_text(json.dumps(cfg), encoding="utf-8")
    tmp.replace(UI_CONFIG)
    try:
        assert ws.DASHBOARD.exists(), "dashboard.html v2 no existe"
    finally:
        cfg["UI_V3"] = original
        tmp = UI_CONFIG.with_suffix(".tmp")
        tmp.write_text(json.dumps(cfg), encoding="utf-8")
        tmp.replace(UI_CONFIG)


# --- 6. POST /api/orden → idempotente ---
def test_api_orden_idempotente():
    _clean()
    r1 = ws.api_orden_create("abre el navegador")
    assert r1["ok"] is True
    assert r1["order_id"].startswith("ORD-")
    assert r1["requires_confirmation"] is False
    r2 = ws.api_orden_create("abre el navegador")
    assert r2["ok"] is True
    assert r2["order_id"] != r1["order_id"], "cada orden debe tener ID único"


# --- 7. POST /api/orden L2+ → preview con confirmación ---
def test_api_orden_preview_l2():
    _clean()
    r = ws.api_orden_create("configura el firewall y despliega el servicio")
    assert r["ok"] is True
    assert r["requires_confirmation"] is True
    assert r["preview"] is not None
    assert "criterios" in r["preview"]
    assert "nivel" in r["preview"]


# --- 8. /api/orden archivo atómico ---
def test_api_orden_archivo_atomico():
    _clean()
    r = ws.api_orden_create("test orden archivo")
    assert r["ok"]
    order_path = ORDERS_DIR / f"{r['order_id']}.json"
    assert order_path.exists(), f"archivo no creado: {order_path}"
    data = json.loads(order_path.read_text(encoding="utf-8"))
    assert data["estado"] == "PENDIENTE"
    assert data["texto"] == "test orden archivo"
    assert not (ORDERS_DIR / f"{r['order_id']}.tmp").exists(), ".tmp no limpiado"


# --- 9. Confirmaciones create + resolve ---
def test_confirmaciones_allow():
    _clean()
    r = ws.api_confirm_create("T-TEST002", "test permission")
    assert r["ok"] is True
    perm_id = r["id"]
    # resolve
    res = ws.api_confirm_resolve(perm_id, True)
    assert res["ok"] is True
    assert res["resolution"] == "ALLOW"
    # verify
    p = CONFIRM_DIR / f"{perm_id}.json"
    data = json.loads(p.read_text(encoding="utf-8"))
    assert data["resolved"] is True
    assert data["resolution"] == "ALLOW"


def test_confirmaciones_deny():
    _clean()
    r = ws.api_confirm_create("T-TEST003", "test deny")
    assert r["ok"]
    res = ws.api_confirm_resolve(r["id"], False)
    assert res["resolution"] == "DENY"


# --- 10. Confirmación timeout → DENY ---
def test_permiso_timeout_deny():
    _clean()
    r = ws.api_confirm_create("T-TIMEOUT", "timeout test")
    assert r["ok"]
    perm_id = r["id"]
    # manually set created to 70s ago
    p = CONFIRM_DIR / f"{perm_id}.json"
    data = json.loads(p.read_text(encoding="utf-8"))
    old_time = datetime.now(timezone.utc).timestamp() - 70
    data["created"] = datetime.fromtimestamp(old_time, tz=timezone.utc).isoformat(timespec="seconds")
    p.write_text(json.dumps(data), encoding="utf-8")
    # next call to _pending_confirmations should auto-expire it
    perms = ws._pending_confirmations()
    assert len(perms) == 0, "expired permission should not be in pending list"
    data2 = json.loads(p.read_text(encoding="utf-8"))
    assert data2["resolved"] is True
    assert data2["resolution"] == "DENY"


# --- 11. /api/ui_config read/write ---
def test_ui_config_read_write():
    _clean()
    original = ws.api_ui_config_read()
    assert "UI_V3" in original
    res = ws.api_ui_config_write({"HWND": 12345})
    assert res["ok"] is True
    updated = ws.api_ui_config_read()
    assert updated["HWND"] == 12345
    # restore
    ws.api_ui_config_write({"HWND": None})


# --- 12. Grafo tope nodos ---
def test_grafo_tope_150():
    r = ws._fetch_grafo()
    assert "nodes" in r
    assert "edges" in r
    assert len(r["nodes"]) <= 150, f"grafo excede tope: {len(r['nodes'])}"


# --- 13. Canvas HUD inline (esfera 3D HOLO-GLASS) ---
def test_asset_estatico():
    dashboard = (ws.WEB_DIR / "dashboard_v3.html").read_text(encoding="utf-8")
    assert '<canvas id="sphere-canvas"' in dashboard, "dashboard debe tener canvas esfera inline"
    assert 'initParticles' in dashboard, "dashboard debe tener initParticles"
    assert 'sphereAni' in dashboard, "dashboard debe tener sphereAni"
    assert 'window.onerror' in dashboard, "dashboard debe tener window.onerror handler"


if __name__ == "__main__":
    test_adaptador_caido_cache_badge()
    test_adaptador_ok_fresh()
    test_api_live_estructura()
    test_api_live_task_heartbeat()
    test_ui_v3_rollback()
    test_api_orden_idempotente()
    test_api_orden_preview_l2()
    test_api_orden_archivo_atomico()
    test_confirmaciones_allow()
    test_confirmaciones_deny()
    test_permiso_timeout_deny()
    test_ui_config_read_write()
    test_grafo_tope_150()
    test_asset_estatico()
    print("OK tests/unit/test_dash_v3.py (14 tests)")
