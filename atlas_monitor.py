#!/usr/bin/env python3
"""
atlas_monitor — Monitoreo de errores y rate limiting para Atlas.

Errores:
  track_error() registra errores en logs/errors.jsonl con contexto
  (fuente, mensaje, traceback, frecuencia). La DB de errores vive en
  memory_data/state/errors.db (derivada, no se versiona) para poder
  reportar frecuencia en memory_health.

Rate limiting:
  RateLimiter limita cuantos eventos por ventana de tiempo puede emitir
  una fuente (ej: el daemon no puede escribir mas de N eventos/min).

Uso:
    from atlas_monitor import track_error, RateLimiter
    track_error("atlas_activity", "get_foreground_info", exc)
    rl = RateLimiter(rate=10, per=60)   # 10 eventos por minuto
    if rl.allow("activity"): ...
"""
import json
import os
import sqlite3
import threading
import time
import traceback
from collections import defaultdict, deque
from datetime import datetime, timezone
from pathlib import Path

MEMORY_ROOT = Path(os.environ.get("MEMORY_ROOT", str(Path(__file__).resolve().parent / "memory_data"))).resolve()
STATE_DIR = MEMORY_ROOT / "state"
LOG_DIR = Path(__file__).resolve().parent / "logs"

_lock = threading.Lock()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _db() -> sqlite3.Connection:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(STATE_DIR / "errors.db"))
    conn.execute(
        """CREATE TABLE IF NOT EXISTS errors (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts TEXT NOT NULL,
            source TEXT NOT NULL,
            operation TEXT NOT NULL,
            error_type TEXT,
            error_message TEXT,
            traceback TEXT,
            count INTEGER DEFAULT 1
        )"""
    )
    return conn


def track_error(source: str, operation: str, exc=None, error_type: str = "",
                error_message: str = ""):
    """Registra un error con contexto en logs/errors.jsonl + errors.db."""
    # linea JSON en logs/errors.jsonl
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    tb = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__)) if exc else ""
    entry = {
        "ts": _now_iso(),
        "source": source,
        "operation": operation,
        "error_type": error_type or (type(exc).__name__ if exc else ""),
        "error_message": error_message or str(exc) if exc else error_message,
        "traceback": tb,
    }
    try:
        with open(LOG_DIR / "errors.jsonl", "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except OSError:
        pass
    # frecuencia en errors.db
    try:
        with _lock:
            conn = _db()
            try:
                # contar errores del mismo tipo en la ultima hora (rollup simple)
                cur = conn.execute(
                    "SELECT id, count FROM errors WHERE source=? AND operation=? "
                    "AND error_type=? AND ts > datetime('now', '-1 hour') "
                    "ORDER BY id DESC LIMIT 1",
                    (source, operation, entry["error_type"]),
                )
                row = cur.fetchone()
                if row:
                    conn.execute("UPDATE errors SET count=count+1, ts=? WHERE id=?",
                                 (_now_iso(), row[0]))
                else:
                    conn.execute(
                        "INSERT INTO errors (ts, source, operation, error_type, "
                        "error_message, traceback, count) VALUES (?,?,?,?,?,?,1)",
                        (entry["ts"], source, operation, entry["error_type"],
                         entry["error_message"], tb),
                    )
                conn.commit()
            finally:
                conn.close()
    except Exception:
        pass


def recent_errors(source: str = None, hours: int = 24) -> list:
    """Errores agrupados de las ultimas N horas (para health check)."""
    try:
        conn = _db()
        try:
            q = ("SELECT source, operation, error_type, SUM(count), "
                 "MAX(ts) FROM errors WHERE ts > datetime('now', ?) ")
            params = (f"-{hours} hours",)
            if source:
                q += "AND source=? "
                params += (source,)
            q += "GROUP BY source, operation, error_type ORDER BY SUM(count) DESC"
            rows = conn.execute(q, params).fetchall()
            return [{"source": r[0], "operation": r[1], "error_type": r[2],
                     "count": r[3], "last_ts": r[4]} for r in rows]
        finally:
            conn.close()
    except Exception:
        return []


class RateLimiter:
    """Limita eventos por ventana de tiempo (sliding window)."""

    def __init__(self, rate: int, per: float = 60.0):
        self._rate = rate
        self._per = per
        self._timestamps = defaultdict(deque)
        self._lock = threading.Lock()

    def allow(self, key: str) -> bool:
        now = time.time()
        with self._lock:
            dq = self._timestamps[key]
            while dq and now - dq[0] > self._per:
                dq.popleft()
            if len(dq) >= self._rate:
                return False
            dq.append(now)
            return True

    def remaining(self, key: str) -> int:
        now = time.time()
        with self._lock:
            dq = self._timestamps[key]
            while dq and now - dq[0] > self._per:
                dq.popleft()
            return max(0, self._rate - len(dq))
