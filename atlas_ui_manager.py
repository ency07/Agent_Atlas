#!/usr/bin/env python3
"""
atlas_ui_manager.py — Cara pywebview fullscreen para Atlas Dashboard v3.

Abre una ventana pywebview fullscreen que carga http://127.0.0.1:4100/.
Si UI_V3=0 en ui_config.json, abre dashboard.html (v2) como fallback.

HWND se guarda en ui_config.json al arrancar.

Uso:
    python atlas_ui_manager.py
    (se ejecuta al logon via start_atlas_ui_manager.vbs)

Requiere: pywebview (pip install pywebview), WebView2.
"""
import ctypes
import json
import os
import sys
import time
import webbrowser
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
STATE_DIR = ROOT / "memory_data" / "state"
UI_CONFIG = STATE_DIR / "ui_config.json"
LOG_DIR = ROOT / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

from atlas_log import get_logger
from atlas_monitor import track_error

log = get_logger("ui_manager")

HOST = "127.0.0.1"
PORT = 4100
MUTEX_NAME = "Local\\AtlasUIManagerSingleInstance"


def _load_config() -> dict:
    if UI_CONFIG.exists():
        try:
            return json.loads(UI_CONFIG.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"UI_V3": 1}


def _save_config(cfg: dict):
    tmp = UI_CONFIG.with_suffix(".tmp")
    tmp.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(UI_CONFIG)


def acquire_single_instance():
    try:
        ERROR_ALREADY_EXISTS = 183
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.CreateMutexW.restype = ctypes.c_void_p
        handle = kernel32.CreateMutexW(None, False, MUTEX_NAME)
        if not handle:
            return None
        if ctypes.get_last_error() == ERROR_ALREADY_EXISTS:
            kernel32.CloseHandle(ctypes.c_void_p(handle))
            return None
        return handle
    except Exception:
        return object()


class UiApi:
    """API expuesta al JS del dashboard v3 como pywebview.api.*"""

    def __init__(self):
        self._win = None

    def set_window(self, win):
        self._win = win

    def close(self):
        if self._win:
            self._win.destroy()

    def minimize(self):
        if self._win:
            self._win.minimize()

    def restore(self):
        if self._win:
            self._win.restore()

    def get_hwnd(self):
        """Devuelve el HWND de la ventana."""
        if self._win:
            try:
                return int(self._win.native.Handle.ToInt64())
            except Exception:
                return None
        return None


def set_window_icon(win, ico_path: str) -> None:
    """Pone el .ico como icono de la ventana."""
    try:
        import clr
        from System.Drawing import Icon
        win.native.Icon = Icon(str(ico_path))
        return
    except Exception:
        pass
    try:
        user32 = ctypes.windll.user32
        hwnd = int(win.native.Handle.ToInt64())
        IMAGE_ICON, LR_LOADFROMFILE, LR_DEFAULTSIZE = 1, 0x10, 0x40
        hicon = user32.LoadImageW(
            None, str(ico_path), IMAGE_ICON, 0, 0,
            LR_LOADFROMFILE | LR_DEFAULTSIZE,
        )
        if hicon:
            user32.SendMessageW(hwnd, 0x0080, 1, hicon)
            user32.SendMessageW(hwnd, 0x0080, 0, hicon)
    except Exception as exc:
        log.warning("no se pudo aplicar icono", error=str(exc))


ICON_PATH = ROOT / "artificialintelligence.ico"


def _on_loaded(win) -> None:
    """Tras el load: guarda HWND en ui_config + aplica icono."""
    try:
        hwnd = int(win.native.Handle.ToInt64())
        cfg = _load_config()
        cfg["HWND"] = hwnd
        _save_config(cfg)
        log.info(f"HWND guardado: {hwnd}")
    except Exception as exc:
        log.warning(f"no se pudo guardar HWND: {exc}")
    if ICON_PATH.exists():
        set_window_icon(win, str(ICON_PATH))


def main():
    config = _load_config()
    ui_v3 = config.get("UI_V3", 1)

    if not ui_v3:
        log.info("UI_V3=0 → NAVEGADOR NO ABIERTO (A2-fix)")
        return
        return

    lock = acquire_single_instance()
    if lock is None:
        log.info("ya hay una instancia de ui_manager abierta; saliendo")
        raise SystemExit("Ya hay una ventana Atlas abierta.")

    api = UiApi()
    try:
        win = webview.create_window(
            "Atlas Dashboard v3",
            f"http://{HOST}:{PORT}/",
            width=1920,
            height=1080,
            fullscreen=True,
            on_top=False,
            background_color="#0d1117",
            js_api=api,
        )
        api.set_window(win)
        win.events.loaded += lambda: _on_loaded(win)
        webview.start()
    except Exception as exc:
        track_error("atlas_ui_manager", "webview_start", exc=exc)
        log.error(f"pywebview fallo ({exc}); NAVEGADOR NO ABIERTO (A2-fix)")


if __name__ == "__main__":
    main()
