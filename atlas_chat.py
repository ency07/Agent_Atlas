#!/usr/bin/env python3
"""
Atlas Chat Flotante (F2 · Opcion A del roadmap).

Arranca `opencode serve` (headless, en el puerto 4096) si no esta corriendo,
espera a que responda, y abre una ventana pywebview (WebView2) frameless y
siempre-al-frente apuntando al chat web de opencode.

Uso:
    python atlas_chat.py             # launcher completo (server + ventana)
    python atlas_chat.py --server-only   # solo levanta el server, no abre UI
    python atlas_chat.py --port 5000     # puerto alternativo
    python atlas_chat.py --model omni... # modelo por defecto del chat

Requiere: pywebview (pip install pywebview), opencode CLI en PATH, WebView2.
Se ejecuta normalmente con pythonw.exe (sin consola) via start_atlas_chat.vbs.
"""
import ctypes
import json
import os
import shutil
import socket
import subprocess
import sys
import time
import urllib.request
import webbrowser
from pathlib import Path

import webview

HOST = "127.0.0.1"
PORT = int(os.environ.get("ATLAS_CHAT_PORT", "4096"))
MODEL = os.environ.get("ATLAS_CHAT_MODEL", "omniroute/auto/best-chat")
LOG_FILE = Path(__file__).resolve().parent / "atlas_chat.log"

MUTEX_NAME = "Local\\AtlasChatSingleInstance"


def log(msg: str) -> None:
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"[{time.strftime('%H:%M:%S')}] {msg}\n")
    except OSError:
        pass


def find_opencode_bin():
    """Localiza el binario de opencode (exe real o shim .cmd)."""
    cands = [
        Path.home() / ".opencode" / "bin" / "opencode.exe",
        Path.home() / "AppData" / "Roaming" / "npm" / "opencode.cmd",
    ]
    for c in cands:
        if c.exists():
            return str(c)
    sh = shutil.which("opencode")
    if sh:
        return sh
    return None


def server_up(port: int) -> bool:
    try:
        urllib.request.urlopen(f"http://{HOST}:{port}/config", timeout=2)
        return True
    except Exception:
        return False


def start_server(opencode_bin: str, port: int, model: str):
    """Lanza opencode serve oculto con el modelo por defecto elegido."""
    log(f"iniciando opencode serve en {HOST}:{port} (modelo={model})")
    env = dict(os.environ)
    env["OPENCODE_CONFIG_CONTENT"] = json.dumps({"model": model})
    # cwd = escritorio del usuario -> la memoria de Atlas cae en modo global
    # (lista proyectos con memory_projects). Si no hay Desktop, usa el home.
    desk = Path.home() / "Desktop"
    cwd = str(desk) if desk.exists() else str(Path.home())
    args = [opencode_bin, "serve", f"--port={port}", "--hostname", HOST]
    flags = subprocess.CREATE_NO_WINDOW
    if str(opencode_bin).lower().endswith((".cmd", ".bat")):
        proc = subprocess.Popen(
            args, env=env, cwd=cwd, shell=True,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            creationflags=flags,
        )
    else:
        proc = subprocess.Popen(
            args, env=env, cwd=cwd,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            creationflags=flags,
        )
    return proc


def acquire_single_instance():
    """Evita ventanas duplicadas: mutex nombrado de Windows.

    Crea (o abre) un mutex global. Si ya existe, significa que otra instancia
    tiene la ventana abierta y devolvemos None (el llamador debe salir).
    Devuelve el handle para mantener el mutex vivo mientras corremos.
    """
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
    except Exception:  # noqa: BLE001 (sin windows / entorno raro)
        return object()


class Api:
    """Expuesto al overlay de la ventana como pywebview.api.*"""

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


OVERLAY_JS = """
(function () {
  var bar = document.createElement('div');
  bar.id = 'atlas-drag-bar';
  bar.innerHTML =
    '<span id="atlas-title">Atlas</span>' +
    '<button id="atlas-min" title="Minimizar">&ndash;</button>' +
    '<button id="atlas-close" title="Cerrar">&times;</button>';
  bar.style.cssText =
    'position:fixed;top:0;left:0;right:0;height:30px;z-index:2147483647;' +
    'display:flex;align-items:center;justify-content:flex-end;gap:6px;' +
    'padding:0 6px;background:rgba(13,17,23,.85);color:#e6edf3;' +
    'font:12px "Segoe UI",sans-serif;cursor:default;-webkit-app-region:drag;' +
    'user-select:none;';
  bar.querySelector('#atlas-title').style.cssText =
    'margin-right:auto;padding-left:8px;opacity:.85;letter-spacing:.5px;';
  var btnCss =
    'width:24px;height:24px;border:none;border-radius:6px;background:transparent;' +
    'color:#e6edf3;font-size:14px;line-height:1;cursor:pointer;' +
    '-webkit-app-region:no-drag;';
  bar.querySelector('#atlas-min').style.cssText = btnCss;
  bar.querySelector('#atlas-close').style.cssText = btnCss;
  bar.querySelector('#atlas-min').onmouseover = function () {
    this.style.background = 'rgba(255,255,255,.12)';
  };
  bar.querySelector('#atlas-min').onmouseout = function () {
    this.style.background = 'transparent';
  };
  bar.querySelector('#atlas-close').onmouseover = function () {
    this.style.background = '#f85149';
  };
  bar.querySelector('#atlas-close').onmouseout = function () {
    this.style.background = 'transparent';
  };
  bar.querySelector('#atlas-min').onclick = function () {
    if (window.pywebview && pywebview.api) pywebview.api.minimize();
  };
  bar.querySelector('#atlas-close').onclick = function () {
    if (window.pywebview && pywebview.api) pywebview.api.close();
  };
  document.body.appendChild(bar);
})();
"""


def main():
    server_only = "--server-only" in sys.argv
    port = PORT
    for i, a in enumerate(sys.argv):
        if a == "--port" and i + 1 < len(sys.argv):
            port = int(sys.argv[i + 1])
    model = MODEL
    for i, a in enumerate(sys.argv):
        if a == "--model" and i + 1 < len(sys.argv):
            model = sys.argv[i + 1]

    opencode_bin = find_opencode_bin()
    if not opencode_bin:
        log("ERROR: no se encontro opencode CLI (npm install -g opencode-ai)")
        raise SystemExit("No se encontro opencode CLI. Ejecuta: npm install -g opencode-ai")

    # 1) server ya corriendo?
    if server_up(port):
        log(f"server ya activo en {HOST}:{port}; reutilizando")
    else:
        start_server(opencode_bin, port, model)
        log("esperando a que el server responda...")
        deadline = time.time() + 40
        ok = False
        while time.time() < deadline:
            if server_up(port):
                ok = True
                break
            time.sleep(1)
        if not ok:
            log(f"ERROR: el server no respondio en {HOST}:{port}")
            raise SystemExit("opencode serve no arranco a tiempo (ver atlas_chat.log)")
        log("server listo")

    url = f"http://{HOST}:{port}/"
    if server_only:
        print(f"server corriendo en {url}")
        return

    # 2) instancia unica de la ventana
    lock = acquire_single_instance()
    if lock is None:
        log("ya hay una ventana Atlas abierta; saliendo")
        raise SystemExit("Ya hay una ventana Atlas abierta.")

    try:
        api = Api()
        win = webview.create_window(
            "Atlas",
            url,
            width=420,
            height=640,
            min_size=(360, 480),
            frameless=True,
            on_top=True,
            resizable=True,
            background_color="#0d1117",
            js_api=api,
        )
        api.set_window(win)
        win.events.loaded += lambda: win.evaluate_js(OVERLAY_JS)
        webview.start()
    except Exception as exc:  # noqa: BLE001
        log(f"pywebview fallo ({exc}); abriendo en navegador")
        webbrowser.open(url)


if __name__ == "__main__":
    main()
