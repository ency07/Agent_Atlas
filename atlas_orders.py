#!/usr/bin/env python3
"""
atlas_orders.py — Drenador de órdenes para Atlas Dashboard v3.

Daemon que escanea state/orders/ cada 3s, clasifica con C4,
ejecuta L0/L1 directo (fast-path), genera preview para L2+
y espera confirmación (60s timeout → DENY).

Uso:
    python atlas_orders.py
    (se ejecuta al logon via start_atlas_orders.vbs)

Escritura inter-proceso: atomic write (temp+rename) en todos los archivos.
"""
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

STATE_DIR = ROOT / "memory_data" / "state"
ORDERS_DIR = STATE_DIR / "orders"
CONFIRM_DIR = STATE_DIR / "confirmaciones"
HB_DIR = STATE_DIR / "task_heartbeat"
UI_CONFIG = STATE_DIR / "ui_config.json"

from atlas_log import get_logger
from atlas_monitor import track_error

log = get_logger("orders")

POLL_INTERVAL = 3
CONFIRM_TIMEOUT_S = 60


def _load_config() -> dict:
    if UI_CONFIG.exists():
        try:
            return json.loads(UI_CONFIG.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def _atomic_write(path: Path, data: dict):
    """Escrive un dict de forma atómica (temp+rename)."""
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def _write_task_heartbeat(task_id: str, step: str, eta_s: int = 0, tokens_alive: bool = True):
    """Escribe heartbeat de tarea atómicamente."""
    HB_DIR.mkdir(parents=True, exist_ok=True)
    hb = {
        "task_id": task_id,
        "last_beat": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "writers": ["orders"],
        "current_step": step,
        "eta_s": eta_s,
        "tokens_alive": tokens_alive,
    }
    _atomic_write(HB_DIR / f"{task_id}.json", hb)


def _friction_write(event_type: str, detail: str, meta: dict = None):
    """Escribe evento de fricción (append-only JSONL)."""
    friction_log = STATE_DIR / "friction_log.jsonl"
    entry = {
        "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "type": event_type,
        "detail": detail,
        "meta": meta or {},
    }
    with open(friction_log, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def _classify_order(order: dict) -> dict:
    """Clasifica una orden con C4."""
    try:
        from atlas_c4 import classify_level, generate_contract
        nivel = classify_level(order["texto"])
        contract = generate_contract(order["texto"])
        return {"nivel": nivel, "contract": contract}
    except Exception as e:
        log.warning(f"error clasificando: {e}")
        return {"nivel": "L1", "contract": {"orden_literal": order["texto"], "nivel": "L1", "criterios": []}}


def _execute_liviano(order: dict, classification: dict) -> dict:
    """Fast-path L0/L1: ejecuta sin contrato formal."""
    task_id = f"T-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    _write_task_heartbeat(task_id, "ejecutando L0/L1 fast-path")
    try:
        from atlas_controller import ejecutar_liviano
        result = ejecutar_liviano(classification["contract"])
        _write_task_heartbeat(task_id, f"resultado: {result.get('resultado', '?')}")
        return {
            "task_id": task_id,
            "resultado": result.get("resultado", "OK"),
            "evidencias": result.get("evidencias", []),
            "nivel": result.get("nivel", classification["nivel"]),
        }
    except Exception as e:
        log.warning(f"error ejecutando liviano: {e}")
        _write_task_heartbeat(task_id, f"error: {e}")
        return {"task_id": task_id, "resultado": "ERROR", "error": str(e)}


def _create_confirmation(order_id: str, task_id: str, detail: str) -> str:
    """Crea una confirmación pendiente (atomic write)."""
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
    _atomic_write(CONFIRM_DIR / f"{perm_id}.json", entry)
    return perm_id


def _check_confirmation(perm_id: str) -> dict | None:
    """Verifica si una confirmación fue resuelta."""
    p = CONFIRM_DIR / f"{perm_id}.json"
    if not p.exists():
        return None
    try:
        c = json.loads(p.read_text(encoding="utf-8"))
        if c.get("resolved"):
            return c
    except Exception:
        pass
    return None


def _process_order(order_path: Path):
    """Procesa una orden individual (no bloqueante)."""
    try:
        order = json.loads(order_path.read_text(encoding="utf-8"))
    except Exception as e:
        log.warning(f"error leyendo {order_path.name}: {e}")
        return

    order_id = order.get("order_id", "?")
    estado = order.get("estado", "PENDIENTE")

    # L2+ en espera de confirmación → verificar (no bloquear)
    if estado == "EN_EJECUCION" and order.get("perm_id"):
        _check_pending_confirmation(order, order_path)
        return

    if estado != "PENDIENTE":
        return

    # Marcar como en ejecución
    order["estado"] = "EN_EJECUCION"
    _atomic_write(order_path, order)

    log.info(f"procesando {order_id}: {order.get('texto', '')[:60]}")

    # Clasificar
    classification = _classify_order(order)
    nivel = classification["nivel"]
    order["nivel"] = nivel
    order["contract"] = classification["contract"]
    _atomic_write(order_path, order)

    if nivel in ("L0", "L1"):
        # Fast-path: ejecutar directo
        result = _execute_liviano(order, classification)
        order["estado"] = "COMPLETADA"
        order["completed"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
        order["result"] = result
        _atomic_write(order_path, order)
        log.info(f"{order_id} completada ({nivel}): {result.get('resultado', '?')}")

    elif nivel in ("L2", "L3"):
        # Requiere confirmación (no bloqueante: se chequea en cada ciclo)
        task_id = f"T-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        _write_task_heartbeat(task_id, f"L2+ esperando confirmación", eta_s=0)
        perm_id = _create_confirmation(
            order_id, task_id,
            f"{nivel} requiere confirmación: {order.get('texto', '')[:80]}"
        )
        order["task_id"] = task_id
        order["perm_id"] = perm_id
        order["perm_created"] = time.time()
        _atomic_write(order_path, order)
        log.info(f"{order_id} ({nivel}) → confirmación pendiente: {perm_id}")

    else:
        order["estado"] = "DENEGADA"
        order["completed"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
        order["result"] = {"resultado": "DENEGADA", "reason": f"nivel desconocido: {nivel}"}
        _atomic_write(order_path, order)


def _check_pending_confirmation(order: dict, order_path: Path):
    """Chequea una confirmación pendiente (no bloquea el loop)."""
    order_id = order.get("order_id", "?")
    perm_id = order.get("perm_id")
    task_id = order.get("task_id", "")
    timeout_s = _load_config().get("permission_timeout_s", CONFIRM_TIMEOUT_S)
    elapsed = time.time() - order.get("perm_created", time.time())

    if elapsed > timeout_s:
        order["estado"] = "DENEGADA"
        order["completed"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
        order["result"] = {"resultado": "DENEGADA", "reason": "timeout"}
        _atomic_write(order_path, order)
        _friction_write("espera", f"permiso {perm_id} timeout {int(elapsed)}s", {"order_id": order_id})
        _write_task_heartbeat(task_id, f"finalizada: DENEGADA (timeout)")
        log.info(f"{order_id} (L2+) → DENY por timeout")
        return

    check = _check_confirmation(perm_id)
    if check and check.get("resolved"):
        resolution = check.get("resolution", "DENY")
        if resolution == "ALLOW":
            contract = order.get("contract")
            if not contract:
                contract = _classify_order(order)["contract"]
            result = _execute_liviano(order, {"contract": contract, "nivel": order.get("nivel", "L2")})
            order["estado"] = "COMPLETADA"
            order["completed"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
            order["result"] = result
            log.info(f"{order_id} (L2+) → ALLOW, completada: {result.get('resultado', '?')}")
        else:
            order["estado"] = "DENEGADA"
            order["completed"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
            order["result"] = {"resultado": "DENEGADA", "resolution": resolution}
            log.info(f"{order_id} (L2+) → DENY por resolución")
        _atomic_write(order_path, order)
        _write_task_heartbeat(task_id, f"finalizada: {order['estado']}")
    else:
        _write_task_heartbeat(task_id, "esperando confirmación...", eta_s=max(0, int(timeout_s - elapsed)))


def main():
    ORDERS_DIR.mkdir(parents=True, exist_ok=True)
    CONFIRM_DIR.mkdir(parents=True, exist_ok=True)
    HB_DIR.mkdir(parents=True, exist_ok=True)
    log.info("orders daemon iniciado", pid=os.getpid())

    while True:
        try:
            pending = sorted(
                ORDERS_DIR.glob("*.json"),
                key=lambda p: p.stat().st_mtime,
            )
            for order_path in pending:
                try:
                    order = json.loads(order_path.read_text(encoding="utf-8"))
                    estado = order.get("estado")
                    if estado in ("PENDIENTE", "EN_EJECUCION"):
                        _process_order(order_path)
                except Exception as e:
                    log.warning(f"error procesando {order_path.name}: {e}")
                    track_error("atlas_orders", "process_order", exc=e)
        except Exception as e:
            log.error(f"error en loop: {e}")
            track_error("atlas_orders", "main_loop", exc=e)

        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    main()
