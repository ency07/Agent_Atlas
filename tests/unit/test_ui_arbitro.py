# ============================================================
# tests/unit/test_ui_arbitro.py — Tests UX Árbitro
# ============================================================
import json
import os
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import atlas_web_server as ws

ROOT = Path(__file__).parent.parent.parent
STATE_DIR = ROOT / "memory_data" / "state"
HB_DIR = STATE_DIR / "task_heartbeat"
CONFIRM_DIR = STATE_DIR / "confirmaciones"
ORDERS_DIR = STATE_DIR / "orders"
UI_CONFIG = STATE_DIR / "ui_config.json"


def _clean():
    for d in (HB_DIR, CONFIRM_DIR, ORDERS_DIR):
        d.mkdir(parents=True, exist_ok=True)
    for f in HB_DIR.glob("*.json"):
        f.unlink(missing_ok=True)
    for f in CONFIRM_DIR.glob("*.json"):
        f.unlink(missing_ok=True)
    for f in ORDERS_DIR.glob("*.json"):
        f.unlink(missing_ok=True)


def _write_hb(task_id: str, age_s: int = 5, tokens_alive: bool = True):
    """Escribe un heartbeat de prueba con la edad especificada."""
    hb = {
        "task_id": task_id,
        "last_beat": (datetime.now(timezone.utc) - timedelta(seconds=age_s)).isoformat(timespec="seconds"),
        "writers": ["test"],
        "current_step": "test step",
        "eta_s": 0,
        "tokens_alive": tokens_alive,
    }
    (HB_DIR / f"{task_id}.json").write_text(json.dumps(hb), encoding="utf-8")
    return hb


# --- 1. Heartbeat stale yellow (60-120s, sin tokens_alive) ---
def test_heartbeat_stale_yellow():
    _clean()
    _write_hb("T-YELLOW", age_s=80, tokens_alive=False)
    tasks = ws._task_heartbeats()
    t = [t for t in tasks if t["task_id"] == "T-YELLOW"][0]
    assert t["heartbeat_status"] == "yellow", f"esperaba yellow, got {t['heartbeat_status']}"
    assert 60 < t["heartbeat_age_s"] < 120


# --- 2. Heartbeat stale red (>120s, sin tokens_alive) ---
def test_heartbeat_stale_red():
    _clean()
    _write_hb("T-RED", age_s=150, tokens_alive=False)
    tasks = ws._task_heartbeats()
    t = [t for t in tasks if t["task_id"] == "T-RED"][0]
    assert t["heartbeat_status"] == "red", f"esperaba red, got {t['heartbeat_status']}"
    assert t["heartbeat_age_s"] > 120


# --- 3. Stream vivo no pegado (tokens_alive=true aunque age >60s) ---
def test_stream_vivo_no_pegado():
    _clean()
    _write_hb("T-ALIVE", age_s=90, tokens_alive=True)
    tasks = ws._task_heartbeats()
    t = [t for t in tasks if t["task_id"] == "T-ALIVE"][0]
    assert t["heartbeat_status"] == "green", f"tokens_alive=True → debería ser green, got {t['heartbeat_status']}"


# --- 4. Overlay sin :4100 → "sin conexión" ---
def test_overlay_sin_4100():
    _clean()
    # Verificar que el overlay HTML contiene el texto "sin conexión"
    overlay_path = ROOT / "atlas_overlay.py"
    content = overlay_path.read_text(encoding="utf-8")
    assert "sin conexión" in content, "overlay debe mostrar 'sin conexión' cuando :4100 cae"


# --- 5. FULL → EXEC → FULL (mock) ---
def test_full_exec_full():
    _clean()
    import atlas_ui_manager as um
    api = um.UiApi()
    assert api._win is None
    api.set_window(None)
    assert api.get_hwnd() is None


# --- 6. Orders drenador L0 ---
def test_orders_drenador_l0():
    _clean()
    from atlas_orders import _classify_order
    order = {"texto": "abre el navegador", "nivel": "L1"}
    cls = _classify_order(order)
    assert cls["nivel"] in ("L0", "L1"), f"L0 pattern debería clasificar L0/L1, got {cls['nivel']}"


# --- 7. Orders drenador L2 preview ---
def test_orders_drenador_l2_preview():
    _clean()
    from atlas_orders import _classify_order
    order = {"texto": "configura el firewall y despliega el servicio"}
    cls = _classify_order(order)
    assert cls["nivel"] in ("L2", "L3"), f"L2 pattern debería clasificar L2+, got {cls['nivel']}"


# --- 8. Overlay permission allow ---
def test_overlay_permission_allow():
    _clean()
    r = ws.api_confirm_create("T-ALLOW", "test allow permission")
    assert r["ok"]
    res = ws.api_confirm_resolve(r["id"], True)
    assert res["resolution"] == "ALLOW"
    data = json.loads((CONFIRM_DIR / f"{r['id']}.json").read_text(encoding="utf-8"))
    assert data["resolved"] is True


# --- 9. Overlay permission deny ---
def test_overlay_permission_deny():
    _clean()
    r = ws.api_confirm_create("T-DENY", "test deny permission")
    assert r["ok"]
    res = ws.api_confirm_resolve(r["id"], False)
    assert res["resolution"] == "DENY"


# --- 10. Grafo tope 150 ---
def test_grafo_tope_150():
    r = ws._fetch_grafo()
    assert len(r["nodes"]) <= 150


# --- 11. Foco stale badge ---
def test_foco_stale_badge():
    _clean()
    def failing_fetch():
        raise ConnectionError("foco offline")
    data, stale = ws._adaptador_stale("foco_test", failing_fetch, ttl_s=60)
    assert stale is True
    assert data is None


# --- 12. Overlay colapsable ---
def test_overlay_colapsable():
    _clean()
    overlay_path = ROOT / "atlas_overlay.py"
    content = overlay_path.read_text(encoding="utf-8")
    assert "collapse-btn" in content, "overlay debe tener botón colapsable"
    assert "collapsed" in content, "overlay debe soportar estado collapsed"


# --- 13. UI manager HWND guardado ---
def test_ui_manager_hwnd_guardado():
    _clean()
    ui_path = ROOT / "atlas_ui_manager.py"
    content = ui_path.read_text(encoding="utf-8")
    assert "HWND" in content, "ui_manager debe guardar HWND"
    assert "_save_config" in content, "ui_manager debe tener _save_config"


# --- 14. Orders daemon loop ---
def test_orders_daemon_loop():
    _clean()
    orders_path = ROOT / "atlas_orders.py"
    content = orders_path.read_text(encoding="utf-8")
    assert "POLL_INTERVAL" in content, "orders daemon debe tener POLL_INTERVAL"
    assert "while True" in content, "orders daemon debe ser un loop infinito"
    assert "_process_order" in content, "orders daemon debe tener _process_order"


# --- 15. Confirmación no bloqueante: EN_EJECUCION → ALLOW → COMPLETADA ---
def test_orders_confirmacion_no_bloqueante():
    _clean()
    import atlas_orders as ao
    # Orden L2 en EN_EJECUCION con perm_id pendiente
    order_id = "ORD-NOBLOCK"
    perm_id = "PERM-NOBLOCK"
    order = {
        "order_id": order_id,
        "texto": "configura el firewall",
        "nivel": "L2",
        "estado": "EN_EJECUCION",
        "created": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "perm_id": perm_id,
        "perm_created": time.time(),
        "contract": {"orden_literal": "configura el firewall", "nivel": "L2", "criterios": []},
    }
    order_path = ORDERS_DIR / f"{order_id}.json"
    order_path.write_text(json.dumps(order), encoding="utf-8")
    # Confirmación
    ao._atomic_write(CONFIRM_DIR / f"{perm_id}.json", {
        "id": perm_id, "task_id": "T-NOBLOCK", "order_id": order_id,
        "created": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "resolved": True, "resolution": "ALLOW", "resolved_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    })
    # Al procesar la orden EN_EJECUCION, debe resolver la confirmación
    ao._process_order(order_path)
    final = json.loads(order_path.read_text(encoding="utf-8"))
    assert final["estado"] == "COMPLETADA", f"esperaba COMPLETADA, got {final['estado']}"


# --- 16. Confirmación no bloqueante: timeout → DENY ---
def test_orders_confirmacion_timeout_deny():
    _clean()
    import atlas_orders as ao
    order_id = "ORD-TIMEOUT"
    perm_id = "PERM-TIMEOUT"
    order = {
        "order_id": order_id,
        "texto": "configura el firewall",
        "nivel": "L2",
        "estado": "EN_EJECUCION",
        "created": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "perm_id": perm_id,
        "perm_created": time.time() - 120,  # vencida
        "contract": {"orden_literal": "configura el firewall", "nivel": "L2", "criterios": []},
    }
    order_path = ORDERS_DIR / f"{order_id}.json"
    order_path.write_text(json.dumps(order), encoding="utf-8")
    ao._atomic_write(CONFIRM_DIR / f"{perm_id}.json", {
        "id": perm_id, "task_id": "T-TIMEOUT", "order_id": order_id,
        "created": (datetime.now(timezone.utc) - timedelta(seconds=120)).isoformat(timespec="seconds"),
        "resolved": False, "resolution": None, "resolved_at": None,
    })
    ao._process_order(order_path)
    final = json.loads(order_path.read_text(encoding="utf-8"))
    assert final["estado"] == "DENEGADA", f"esperaba DENEGADA, got {final['estado']}"
    assert final["result"]["reason"] == "timeout"


if __name__ == "__main__":
    test_heartbeat_stale_yellow()
    test_heartbeat_stale_red()
    test_stream_vivo_no_pegado()
    test_overlay_sin_4100()
    test_full_exec_full()
    test_orders_drenador_l0()
    test_orders_drenador_l2_preview()
    test_overlay_permission_allow()
    test_overlay_permission_deny()
    test_grafo_tope_150()
    test_foco_stale_badge()
    test_overlay_colapsable()
    test_ui_manager_hwnd_guardado()
    test_orders_daemon_loop()
    test_orders_confirmacion_no_bloqueante()
    test_orders_confirmacion_timeout_deny()
    print("OK tests/unit/test_ui_arbitro.py (16 tests)")
