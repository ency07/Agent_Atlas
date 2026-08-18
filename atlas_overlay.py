#!/usr/bin/env python3
"""
atlas_overlay.py — Overlay siempre-visible para Atlas Dashboard v3.

Ventana on_top 380px que muestra:
  - Pulso de heartbeat (color = estado)
  - Tarea activa + paso/ETA
  - Cola de permisos [Permitir][Denegar][Ver]
  - Colapsable

Polling: /api/live cada 2s
Fallback: si :4100 cae → "sin conexión" (nunca verde falso)
Click → abre ventana FULL (restaura HWND de ui_config.json)

Uso:
    python atlas_overlay.py
    (se ejecuta al logon via start_atlas_overlay.vbs)

Requiere: pywebview, WebView2.
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

from atlas_log import get_logger
from atlas_monitor import track_error

log = get_logger("overlay")

HOST = "127.0.0.1"
PORT = 4100
API_URL = f"http://{HOST}:{PORT}"
MUTEX_NAME = "Local\\AtlasOverlaySingleInstance"
POLL_INTERVAL = 2


def _load_config() -> dict:
    if UI_CONFIG.exists():
        try:
            return json.loads(UI_CONFIG.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


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


class OverlayApi:
    """API expuesta al JS del overlay como pywebview.api.*"""

    def __init__(self):
        self._win = None

    def set_window(self, win):
        self._win = win

    def close(self):
        if self._win:
            self._win.destroy()

    def click_to_full(self):
        """Restaura la ventana principal (dashboard v3 fullscreen)."""
        config = _load_config()
        hwnd = config.get("HWND")
        if hwnd:
            try:
                user32 = ctypes.windll.user32
                user32.ShowWindow(hwnd, 9)  # SW_RESTORE
                user32.SetForegroundWindow(hwnd)
                log.info(f"restaurando ventana HWND={hwnd}")
            except Exception as exc:
                log.warning(f"no se pudo restaurar HWND={hwnd}: {exc}")
        else:
            log.info("HWND no disponible; NAVEGADOR NO ABIERTO (A2-fix)")


OVERLAY_HTML = """
<!DOCTYPE html>
<html><head><meta charset="UTF-8"><style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { background: rgba(13,17,23,.92); color: #e6edf3; font-family: 'Segoe UI', sans-serif;
         backdrop-filter: blur(8px); overflow-y: auto; height: 100vh; }
  #header { display: flex; align-items: center; padding: 10px 14px; gap: 8px; border-bottom: 1px solid #30363d; cursor: pointer; }
  #header h3 { font-size: .9rem; flex: 1; }
  #pulse { width: 10px; height: 10px; border-radius: 50%; background: #6e7681; transition: background .3s; }
  #content { padding: 12px 14px; }
  .task-card { background: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 10px; margin-bottom: 8px; }
  .task-id { font-weight: 600; font-size: .82rem; }
  .task-step { font-size: .78rem; color: #8b949e; margin-top: 3px; }
  .task-eta { font-size: .72rem; color: #d29922; margin-top: 2px; }
  .perm-card { background: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 10px; margin-bottom: 8px; }
  .perm-btn { padding: 5px 14px; border-radius: 6px; border: 1px solid #30363d; background: #1f2630; color: #e6edf3; cursor: pointer; font-size: .78rem; margin-right: 4px; }
  .perm-btn.allow { border-color: #3fb950; color: #3fb950; }
  .perm-btn.deny { border-color: #f85149; color: #f85149; }
  .perm-btn.view { border-color: #58a6ff; color: #58a6ff; }
  .perm-btn:hover { opacity: .8; }
  .stale-msg { color: #d29922; font-size: .78rem; padding: 6px; }
  .error-msg { color: #f85149; font-size: .78rem; padding: 6px; }
  .collapse-btn { background: none; border: none; color: #8b949e; cursor: pointer; font-size: .8rem; padding: 2px 6px; }
</style></head><body>
<div id="header"><h3>Atlas</h3><span id="pulse"></span><button class="collapse-btn" id="collapse-btn">▼</button></div>
<div id="content"><div class="stale-msg">cargando...</div></div>
<script>
(function() {
  var API = '%API_URL%';
  var collapsed = false;
  var content = document.getElementById('content');
  var collapseBtn = document.getElementById('collapse-btn');
  var header = document.getElementById('header');
  var pulse = document.getElementById('pulse');
  var COLORS = {green:'#3fb950',yellow:'#d29922',red:'#f85149'};

  collapseBtn.addEventListener('click', function(e) {
    e.stopPropagation();
    collapsed = !collapsed;
    content.style.display = collapsed ? 'none' : 'block';
    collapseBtn.textContent = collapsed ? '▲' : '▼';
  });

  header.addEventListener('click', function() {
    if (window.pywebview && pywebview.api) pywebview.api.click_to_full();
  });

  function poll() {
    fetch(API + '/api/live').then(function(r){return r.json();}).then(function(d) {
      var color = COLORS[d.health_status] || '#6e7681';
      pulse.style.background = color;
      pulse.title = 'Salud: ' + (d.health_status || '?');

      var html = '';

      // Tasks activos
      (d.tasks || []).forEach(function(t) {
        if (t.heartbeat_status === 'done') return;
        var tc = COLORS[t.heartbeat_status] || '#6e7681';
        html += '<div class="task-card" style="border-left:3px solid ' + tc + '">';
        html += '<div class="task-id">' + (t.task_id || '?') + '</div>';
        html += '<div class="task-step">' + (t.current_step || t.orden || 'procesando...') + '</div>';
        if (t.eta_s > 0) html += '<div class="task-eta">~' + t.eta_s + 's ETA</div>';
        html += '</div>';
      });

      if (d.tasks_active === 0 && (!d.tasks || !d.tasks.length)) {
        html += '<div class="stale-msg">sin tareas activas</div>';
      }

      // Permisos pendientes
      (d.permissions_pending || []).forEach(function(p) {
        html += '<div class="perm-card">';
        html += '<div style="font-size:.82rem;margin-bottom:6px">' + (p.detail || 'permiso requerido') + '</div>';
        html += '<button class="perm-btn allow" onclick="resolvePerm(\\'' + p.id + '\\',true)">Permitir</button>';
        html += '<button class="perm-btn deny" onclick="resolvePerm(\\'' + p.id + '\\',false)">Denegar</button>';
        html += '<button class="perm-btn view" onclick="if(window.pywebview&&pywebview.api)pywebview.api.click_to_full()">Ver</button>';
        html += '</div>';
      });

      if (!html) html = '<div class="stale-msg">sin actividad</div>';
      content.innerHTML = html;
    }).catch(function() {
      pulse.style.background = '#f85149';
      content.innerHTML = '<div class="error-msg">sin conexión</div>';
    });
  }

  window.resolvePerm = function(id, allow) {
    fetch(API + '/api/confirmaciones/' + id, {
      method: 'POST',
      headers: {'Content-Type':'application/json'},
      body: JSON.stringify({allow: allow})
    }).then(function(){ poll(); });
  };

  poll();
  setInterval(poll, %POLL_MS%);
})();
</script>
</body></html>
""".replace("%API_URL%", API_URL).replace("%POLL_MS%", str(POLL_INTERVAL * 1000))


def main():
    import webview as wv

    config = _load_config()
    if not config.get("overlay_on_top", True):
        log.info("overlay_on_top=false; no abriendo overlay")
        return

    lock = acquire_single_instance()
    if lock is None:
        log.info("ya hay un overlay abierto; saliendo")
        raise SystemExit("Ya hay un overlay abierto.")

    width = config.get("overlay_width", 380)
    height = config.get("overlay_height", 600)

    api = OverlayApi()
    try:
        # Crear archivo temporal con el HTML del overlay
        tmp_html = ROOT / "tmp" / "overlay.html"
        tmp_html.parent.mkdir(parents=True, exist_ok=True)
        tmp_html.write_text(OVERLAY_HTML, encoding="utf-8")

        win = wv.create_window(
            "Atlas Overlay",
            str(tmp_html),
            width=width,
            height=height,
            on_top=True,
            frameless=False,
            resizable=False,
            background_color="#0d1117",
            js_api=api,
        )
        api.set_window(win)
        log.info(f"overlay abierto {width}x{height} on_top")
        wv.start()
    except Exception as exc:
        track_error("atlas_overlay", "webview_start", exc=exc)
        log.error(f"pywebview fallo ({exc}); NAVEGADOR NO ABIERTO (A2-fix)")


if __name__ == "__main__":
    main()
