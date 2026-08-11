#!/usr/bin/env python3
"""
atlas_log — Sistema de logs estructurados JSON para Atlas.

Formato: una linea JSON por evento con campos:
  ts, level, source, msg, [request_id], [user_id], [extra...]

Uso:
    from atlas_log import get_logger
    log = get_logger("atlas_chat")
    log.info("server arrancado", port=4096)
    log.error("fallo al crear sesion", error=str(e), url=url)

Reemplaza los log() ad-hoc de atlas_chat.py y atlas_activity.py.
"""
import json
import logging
import os
import sys
import time
import traceback
import uuid
from datetime import datetime, timezone
from pathlib import Path

LOG_DIR = Path(os.environ.get(
    "ATLAS_LOG_DIR",
    str(Path(__file__).resolve().parent / "logs")
))


class JSONFormatter(logging.Formatter):
    """Formatea cada record como una linea JSON."""

    def format(self, record: logging.LogRecord) -> str:
        entry = {
            "ts": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(timespec="seconds"),
            "level": record.levelname.lower(),
            "source": getattr(record, "source", record.name),
            "msg": record.getMessage(),
        }
        # campos extra via keyword args: log.info("msg", port=4096)
        for key in ("request_id", "user_id", "project", "pid", "error", "url", "port", "model"):
            val = getattr(record, key, None)
            if val is not None:
                entry[key] = val
        # si hay exception, adjuntar traceback
        if record.exc_info and record.exc_info[1]:
            entry["exception"] = {
                "type": record.exc_info[0].__name__ if record.exc_info[0] else "unknown",
                "message": str(record.exc_info[1]),
                "traceback": traceback.format_exception(*record.exc_info),
            }
        return json.dumps(entry, ensure_ascii=False, default=str)


class AtlasLogger:
    """Logger con contexto de fuente y campos extra por defecto."""

    def __init__(self, source: str, extra: dict = None):
        self._source = source
        self._extra = extra or {}
        self._logger = logging.getLogger(f"atlas.{source}")
        if not self._logger.handlers:
            self._logger.setLevel(logging.DEBUG)
            # handler stderr (consola)
            sh = logging.StreamHandler(sys.stderr)
            sh.setLevel(logging.WARNING)
            sh.setFormatter(JSONFormatter())
            self._logger.addHandler(sh)
            # handler archivo JSON
            LOG_DIR.mkdir(parents=True, exist_ok=True)
            fh = logging.FileHandler(
                str(LOG_DIR / f"{source}.log"), encoding="utf-8"
            )
            fh.setLevel(logging.DEBUG)
            fh.setFormatter(JSONFormatter())
            self._logger.addHandler(fh)

    def _log(self, level: str, msg: str, **kwargs):
        extra = {**self._extra, "source": self._source, **kwargs}
        self._logger.log(
            getattr(logging, level.upper(), logging.INFO),
            msg,
            extra=extra,
        )

    def info(self, msg: str, **kwargs):
        self._log("info", msg, **kwargs)

    def warning(self, msg: str, **kwargs):
        self._log("warning", msg, **kwargs)

    def error(self, msg: str, **kwargs):
        self._log("error", msg, **kwargs)

    def debug(self, msg: str, **kwargs):
        self._log("debug", msg, **kwargs)

    def exception(self, msg: str, exc_info=None, **kwargs):
        """Log con exception info completa."""
        extra = {**self._extra, "source": self._source, **kwargs}
        self._logger.error(msg, exc_info=exc_info or True, extra=extra)

    def with_context(self, **kwargs) -> "AtlasLogger":
        """Devuelve un logger con campos extra fijos (request_id, user_id, etc.)."""
        merged = {**self._extra, **kwargs}
        child = AtlasLogger.__new__(AtlasLogger)
        child._source = self._source
        child._extra = merged
        child._logger = self._logger
        return child


def get_logger(source: str, **extra) -> AtlasLogger:
    """Factory: crea un AtlasLogger con la fuente dada."""
    return AtlasLogger(source, extra=extra)


def new_request_id() -> str:
    """Genera un ID unico de peticion corto."""
    return uuid.uuid4().hex[:12]
