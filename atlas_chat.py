#!/usr/bin/env python3
"""
Atlas Chat Flotante (F2 Â· Opcion A del roadmap).

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
import base64
import ctypes
import http.client
import json
import os
import re
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
MUTEX_NAME = "Local\\AtlasChatSingleInstance"

from atlas_log import get_logger
from atlas_monitor import track_error

log = get_logger("atlas_chat")


def _bin_version(bin_path: str):
    """Devuelve la version del binario opencode (o '' si no se puede)."""
    try:
        out = subprocess.run(
            [bin_path, "--version"], capture_output=True, text=True, timeout=15
        ).stdout.strip()
        import re
        m = re.search(r"\d+\.\d+\.\d+", out)
        return m.group(0) if m else ""
    except Exception:  # noqa: BLE001
        return ""


def find_opencode_bin():
    """Localiza el binario de opencode (exe real o shim .cmd).

    Si hay varios, elige el de mayor version (evita usar binarios viejos
    de ~/.opencode/bin que sirven un web UI desactualizado).
    """
    cands = [
        Path.home() / ".opencode" / "bin" / "opencode.exe",
        Path.home() / "AppData" / "Roaming" / "npm" / "opencode.cmd",
        Path.home() / "AppData" / "Roaming" / "npm" / "opencode.exe",
    ]
    found = []
    for c in cands:
        if c.exists():
            found.append((_bin_version(str(c)), str(c)))
    sh = shutil.which("opencode")
    if sh and all(sh != f for _, f in found):
        found.append((_bin_version(sh), sh))
    if not found:
        return None
    found.sort(key=lambda t: tuple(int(p) for p in re.findall(r"\d+", t[0] or "0.0.0")), reverse=True)
    return found[0][1]


def server_up(port: int) -> bool:
    try:
        urllib.request.urlopen(f"http://{HOST}:{port}/config", timeout=2)
        return True
    except Exception:
        return False


def get_server_model(port: int):
    """Devuelve el modelo activo del server (o '' si no responde)."""
    try:
        with urllib.request.urlopen(f"http://{HOST}:{port}/config", timeout=3) as r:
            return json.loads(r.read()).get("model", "")
    except Exception:
        return ""


def stop_server(port: int):
    """Mata los procesos `opencode serve` que escuchan en el puerto dado."""
    try:
        for p in subprocess.check_output(
            ["powershell", "-NoProfile", "-Command",
             f"Get-CimInstance Win32_Process | Where-Object {{ $_.CommandLine -match 'serve --port={port}' }} | ForEach-Object {{ $_.ProcessId }}"],
            timeout=10, text=True,
        ).split():
            pid = int(p.strip())
            if pid > 0:
                os.kill(pid, 9)
                log.info(f"server anterior ({pid}) detenido para aplicar modelo")
        time.sleep(2)
    except Exception:
        pass


def start_server(opencode_bin: str, port: int, model: str):
    """Lanza opencode serve oculto con el modelo por defecto elegido."""
    log.info(f"iniciando opencode serve en {HOST}:{port}", port=port, model=model)
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
  // --- Drag bar ---
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

  // --- Buscar input y hacer foco ---
  var attempts = 0;
  var maxAttempts = 30; // 30 * 500ms = 15s
  var timer = setInterval(function () {
    attempts++;
    // Buscar textarea o input de texto (varios selectores por si cambia el UI)
    var ta = document.querySelector('textarea[placeholder*="Pregunta"]') ||
             document.querySelector('textarea[placeholder*="pregunta"]') ||
             document.querySelector('textarea') ||
             document.querySelector('input[type="text"][placeholder*="Pregunta"]') ||
             document.querySelector('[contenteditable="true"]');
    if (ta) {
      clearInterval(timer);
      ta.scrollIntoView({behavior: 'smooth', block: 'center'});
      setTimeout(function () { ta.focus(); }, 300);
    } else if (attempts >= maxAttempts) {
      clearInterval(timer);
      // no hay input: crear sesion nueva via API y navegar (evita home sin prompt)
      try {
        fetch('/session', {method:'POST', headers:{'Content-Type':'application/json'}, body:'{}'})
          .then(function(r){return r.json();})
          .then(function(d){
            if (d && d.id) {
              var b64 = btoa(location.origin).replace(/=/g,'');
              location.href = location.origin + '/server/' + b64 + '/session/' + d.id;
            } else { location.reload(); }
          })
          .catch(function(){ location.reload(); });
      } catch (e) { location.reload(); }
    }
  }, 500);
})();
"""


def new_session_url(port: int):
    """Crea una sesion via API y devuelve la URL directa a su chat.

    El web UI de opencode v2 no muestra el cuadro de prompt en la raiz "/":
    solo aparece al abrir /server/<b64>/session/<id>. Creamos la sesion con
    POST /session y navegamos directo a esa ruta.
    """
    try:
        b64 = base64.urlsafe_b64encode(f"http://{HOST}:{port}".encode()).decode().rstrip("=")
        conn = http.client.HTTPConnection(HOST, port, timeout=15)
        conn.request("POST", "/session", body=json.dumps({}), headers={"Content-Type": "application/json"})
        resp = conn.getresponse()
        data = json.loads(resp.read().decode("utf-8", errors="replace"))
        conn.close()
        sid = data.get("id")
        if not sid:
            return None
        return f"http://{HOST}:{port}/server/{b64}/session/{sid}"
    except Exception:  # noqa: BLE001
        return None


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
        log.error("no se encontro opencode CLI (npm install -g opencode-ai)")
        raise SystemExit("No se encontro opencode CLI. Ejecuta: npm install -g opencode-ai")

    # 1) server ya corriendo?
    if server_up(port):
        cur = get_server_model(port)
        if cur and cur != model:
            log.warning(f"server con modelo '{cur}' != '{model}'; reiniciando con modelo correcto", cur=cur, model=model)
            stop_server(port)
            start_server(opencode_bin, port, model)
            log.info("esperando a que el nuevo server responda...")
            deadline = time.time() + 40
            ok = False
            while time.time() < deadline:
                if server_up(port):
                    ok = True
                    break
                time.sleep(1)
            if not ok:
                log.error(f"ERROR: el server no respondio tras reinicio")
                raise SystemExit("opencode serve no arranco a tiempo tras reinicio (ver atlas_chat.log)")
            log.info("server reiniciado con modelo correcto")
        else:
            log.info(f"server ya activo en {HOST}:{port}; reutilizando", model=cur)
    else:
        start_server(opencode_bin, port, model)
        log.info("esperando a que el server responda...")
        deadline = time.time() + 40
        ok = False
        while time.time() < deadline:
            if server_up(port):
                ok = True
                break
            time.sleep(1)
        if not ok:
            log.error(f"ERROR: el server no respondio en {HOST}:{port}")
            raise SystemExit("opencode serve no arranco a tiempo (ver atlas_chat.log)")
        log.info("server listo")

    url = f"http://{HOST}:{port}/"
    if server_only:
        print(f"server corriendo en {url}")
        return

    # 2) instancia unica de la ventana
    lock = acquire_single_instance()
    if lock is None:
        log.info("ya hay una ventana Atlas abierta; saliendo")
        raise SystemExit("Ya hay una ventana Atlas abierta.")

    # 3) crear una sesion y apuntar la ventana directo a su chat
    #    (la raiz "/" solo muestra la home sin cuadro de prompt).
    chat_url = new_session_url(port)
    if chat_url:
        log.info(f"abriendo chat en {chat_url}", url=chat_url)
    else:
        chat_url = url
        log.warning("aviso: no se pudo crear sesion; abriendo home")

    try:
        api = Api()
        win = webview.create_window(
            "Atlas",
            chat_url,
            width=420,
            height=720,
            min_size=(360, 560),
            frameless=True,
            on_top=True,
            resizable=True,
            background_color="#0d1117",
            js_api=api,
        )
        api.set_window(win)
        # delay 2s para que React/Next.js monte el DOM antes de inyectar overlay+input-focus
        win.events.loaded += lambda: _on_loaded(win)
        webview.start()
    except Exception as exc:  # noqa: BLE001
        track_error("atlas_chat", "webview_start", exc=exc)
        log.error(f"pywebview fallo ({exc}); abriendo en navegador", error=str(exc))
        webbrowser.open(chat_url)


ICON_PATH = Path(__file__).resolve().parent / "artificialintelligence.ico"


def set_window_icon(win, ico_path: str) -> None:
    """Pone el .ico como icono de la ventana (titulo + taskbar)."""
    # via .NET (pythonnet, ya cargado por pywebview): mas limpio
    try:
        import clr
        from System.Drawing import Icon
        win.native.Icon = Icon(str(ico_path))
        return
    except Exception:
        pass
    # fallback ctypes (Win32)
    try:
        import ctypes
        user32 = ctypes.windll.user32
        hwnd = int(win.native.Handle.ToInt64())
        IMAGE_ICON, LR_LOADFROMFILE, LR_DEFAULTSIZE = 1, 0x10, 0x40
        hicon = user32.LoadImageW(
            None, str(ico_path), IMAGE_ICON, 0, 0,
            LR_LOADFROMFILE | LR_DEFAULTSIZE,
        )
        if hicon:
            user32.SendMessageW(hwnd, 0x0080, 1, hicon)  # WM_SETICON ICON_BIG
            user32.SendMessageW(hwnd, 0x0080, 0, hicon)  # WM_SETICON ICON_SMALL
    except Exception as exc:
        log.warning("no se pudo aplicar icono a la ventana", error=str(exc))


def _on_loaded(win) -> None:
    """Tras el load: aplica icono y espera 2s para que React monte el DOM."""
    set_window_icon(win, ICON_PATH)
    time.sleep(2)
    win.evaluate_js(OVERLAY_JS)


if __name__ == "__main__":
    main()
