#!/usr/bin/env python3
"""
Atlas Activity Daemon (F2) — Captura ventana activa + bandeja de sistema.

Captura la ventana en primer plano cada ~10s via ctypes (GetForegroundWindow),
agrupa por ventana con duration_seconds, y escribe eventos tipo 'activity'
a inbox/ que memory_event_ingest drena a la tabla events.

Incluye bandeja de sistema (pystray) con:
  - Icono 🟢/🟡/🔴 (estado del daemon)
  - Pausar / Reanudar
  - Abrir chat flotante
  - Estado (resumen rapido)
  - Salir

Uso:
    python atlas_activity.py              # daemon + bandeja
    python atlas_activity.py --no-tray    # daemon sin bandeja (servidor)
    python atlas_activity.py --interval 5 # cada 5 segundos (default 10)

Requiere: pystray, Pillow (Pillow ya esta en requirements.txt).
"""
import ctypes
import ctypes.wintypes as wintypes
import json
import os
import signal
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

try:
    import pystray
    from PIL import Image, ImageDraw
    HAS_TRAY = True
except ImportError:
    HAS_TRAY = False
    # stubs para que el daemon funcione sin pystray
    class Image:
        @staticmethod
        def new(*a, **kw): pass
    class ImageDraw:
        @staticmethod
        def Draw(*a, **kw): pass

# --- Paths ---
MEMORY_ROOT = Path(os.environ.get("MEMORY_ROOT", str(Path(__file__).parent / "memory_data"))).resolve()
INBOX_DIR = MEMORY_ROOT / "inbox"
STATE_DIR = MEMORY_ROOT / "state"
HEARTBEAT_FILE = STATE_DIR / "daemon.heartbeat"
PAUSE_FLAG = STATE_DIR / "activity.paused"
PROJECT_ROOT = Path(__file__).resolve().parent

# --- Config ---
DEFAULT_INTERVAL = 10  # segundos entre capturas
INGEST_EVERY = 300     # ingestar inbox cada 300s (5 min)
HOST = "127.0.0.1"
PORT = 4096

# --- F3 FOCO: estado ---
_foco_distraction_start = 0.0
_foco_distraction_app = ""
_foco_distraction_title = ""
_foco_notices_today = 0
_foco_last_notice_date = ""
_icon = None

# --- Windows API ---
user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

GetForegroundWindow = user32.GetForegroundWindow
GetForegroundWindow.restype = wintypes.HWND

GetWindowTextW = user32.GetWindowTextW
GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
GetWindowTextW.restype = ctypes.c_int

GetWindowThreadProcessId = user32.GetWindowThreadProcessId
GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
GetWindowThreadProcessId.restype = wintypes.DWORD

PROCESS_QUERY_LIMITED_INFORMATION = 0x1000

OpenProcess = kernel32.OpenProcess
OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
OpenProcess.restype = wintypes.HANDLE

QueryFullProcessImageNameW = ctypes.windll.kernel32.QueryFullProcessImageNameW
QueryFullProcessImageNameW.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)]
QueryFullProcessImageNameW.restype = wintypes.BOOL

CloseHandle = kernel32.CloseHandle

# --- State ---
_running = True
_paused = False
_last_tick = time.time()
_current_app = None
_current_title = None
_current_start = 0.0
_tick_count = 0
_last_ingest = 0.0
_status_text = "iniciando..."



def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")



from atlas_log import get_logger
from atlas_monitor import track_error, RateLimiter
import foco_rules

log = get_logger("atlas_activity")

# rate limit: max 6 eventos de actividad por minuto (protege inbox de inundacion)
event_rl = RateLimiter(rate=6, per=60.0)



def get_foreground_info() -> tuple:
    """Devuelve (app_name, window_title) de la ventana activa."""
    try:
        hwnd = GetForegroundWindow()
        if not hwnd:
            return ("(none)", "")
        # window title
        buf = ctypes.create_unicode_buffer(256)
        GetWindowTextW(hwnd, buf, 256)
        title = buf.value or ""
        # process name via PID
        pid = wintypes.DWORD()
        GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if not pid.value:
            return ("(unknown)", title)
        hproc = OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid.value)
        if not hproc:
            return ("(unknown)", title)
        try:
            buf2 = ctypes.create_unicode_buffer(512)
            size = wintypes.DWORD(512)
            ok = QueryFullProcessImageNameW(hproc, 0, buf2, ctypes.byref(size))
            if ok:
                app = Path(buf2.value).name  # e.g. "chrome.exe"
            else:
                app = f"pid:{pid.value}"
        finally:
            CloseHandle(hproc)
        return (app, title)
    except Exception as exc:
        track_error("atlas_activity", "get_foreground_info", exc=exc)
        return ("(error)", "")



def flush_event(app: str, title: str, start: float, end: float) -> None:
    """Escribe un evento de actividad a inbox/ (rate-limited)."""
    if app in ("(none)", "(unknown)", "(error)") or not app:
        return
    dur = int(end - start)
    if dur < 2:
        return  # eventos < 2s no interesan
    # rate limiting: evita inundar el inbox si el sistema se vuelve inestable
    if not event_rl.allow("activity"):
        log.warning("rate limit alcanzado; descartando evento", app=app, duration=dur)
        return
    INBOX_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.fromtimestamp(start, tz=timezone.utc).isoformat(timespec="seconds")
    rules = foco_rules.load_rules()
    cat, mon = foco_rules.classify(app, title[:200], rules)
    ev = {
        "id": f"act_{int(start)}_{os.getpid()}",
        "ts": ts,
        "source": "daemon",
        "type": "activity",
        "project": "global",
        "app": app,
        "window_title": title[:200],
        "category": cat,
        "monetizable": mon,
        "duration_seconds": dur,
    }
    f = INBOX_DIR / f"activity-{time.strftime('%Y%m%d')}.jsonl"
    with open(f, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(ev, ensure_ascii=False) + "\n")



def write_heartbeat(status: str = "ok") -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    hb = {
        "pid": os.getpid(),
        "status": status,
        "paused": _paused,
        "foco_mode": foco_rules.get_mode(),
        "last_tick": now_iso(),
        "uptime_seconds": int(time.time() - _start_time),
        "ticks": _tick_count,
    }
    HEARTBEAT_FILE.write_text(json.dumps(hb, ensure_ascii=False), encoding="utf-8")



def check_pause() -> bool:
    return PAUSE_FLAG.exists()



def do_ingest() -> None:
    """Llama a memory_event_ingest via CLI para drenar inbox/ a SQLite."""
    try:
        py = str(PROJECT_ROOT / ".venv" / "Scripts" / "python.exe")
        srv = str(PROJECT_ROOT / "mcp_memory_server.py")
        subprocess.run([py, srv, "--cli", "event_ingest"],
                       timeout=30, capture_output=True,
                       creationflags=subprocess.CREATE_NO_WINDOW)
    except Exception as exc:
        track_error("atlas_activity", "event_ingest", exc=exc)



def _reset_foco_budget_if_new_day() -> None:
    global _foco_notices_today, _foco_last_notice_date
    today = datetime.now().strftime("%Y-%m-%d")
    if today != _foco_last_notice_date:
        _foco_notices_today = 0
        _foco_last_notice_date = today


def check_foco_drift(app: str, title: str) -> None:
    """
    F3 FOCO — Detección de fuga de atención.

    Si el modo no es 'off' y la app activa es distracción conocida
    (monetizable=False y categoría no neutral) durante más del umbral,
    muestra un aviso en la bandeja (presupuesto limitado por día).
    """
    global _foco_distraction_start, _foco_distraction_app, _foco_distraction_title
    global _foco_notices_today

    rules = foco_rules.load_rules()
    mode = foco_rules.get_mode(rules)
    if mode == "off":
        _foco_distraction_start = 0.0
        _foco_distraction_app = ""
        return

    cat, mon = foco_rules.classify(app, title, rules)
    is_distraction = (mon is False) and cat not in ("other", "exception")

    if not is_distraction:
        _foco_distraction_start = 0.0
        _foco_distraction_app = ""
        return

    # es distracción → trackear streak
    if app != _foco_distraction_app:
        _foco_distraction_start = time.time()
        _foco_distraction_app = app
        _foco_distraction_title = title
        return

    # misma distracción → ver si pasó el umbral
    thr = foco_rules.get_thresholds(rules)
    threshold = thr.get("distraction_strict_after_seconds", 60) if mode == "strict" \
        else thr.get("distraction_alert_after_seconds", 180)

    elapsed = time.time() - _foco_distraction_start
    if elapsed < threshold:
        return

    # umbral superado → aviso con presupuesto
    _reset_foco_budget_if_new_day()
    limit = thr.get("notices_per_day", 3)
    if _foco_notices_today >= limit:
        return

    _foco_notices_today += 1
    msg = f"⚠️ Llevas {int(elapsed // 60)} min en {app} ({cat})."
    log.info("foco aviso", app=app, category=cat, elapsed=int(elapsed), budget_left=limit - _foco_notices_today)

    # balloon en bandeja (si hay tray); si no, evento focus_notice auditado
    if HAS_TRAY and _icon is not None:
        try:
            _icon.notify(f"Foco: {int(elapsed // 60)} min en {app} ({cat}) — aviso {_foco_notices_today}/{limit}", "Atlas · Foco")
            return
        except Exception:
            pass

    _write_focus_notice(app, cat, int(elapsed))


def _write_focus_notice(app: str, cat: str, elapsed: int) -> None:
    """Registra un aviso de foco como evento auditable (sin bandeja)."""
    try:
        INBOX_DIR.mkdir(parents=True, exist_ok=True)
        ev = {
            "id": f"fn_{int(time.time())}_{os.getpid()}",
            "ts": now_iso(),
            "source": "daemon",
            "type": "focus_notice",
            "project": "global",
            "app": app,
            "window_title": "",
            "category": cat,
            "monetizable": False,
            "duration_seconds": elapsed,
            "data": {"elapsed": elapsed, "budget": "audit"},
        }
        f = INBOX_DIR / f"focus-notice-{time.strftime('%Y%m%d')}.jsonl"
        with open(f, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(ev, ensure_ascii=False) + "\n")
    except Exception as exc:
        track_error("atlas_activity", "focus_notice", exc=exc)


def daemon_loop(interval: int) -> None:
    """Loop principal de captura de ventana activa."""
    global _running, _paused, _current_app, _current_title, _current_start
    global _tick_count, _last_ingest, _status_text

    _start_time_local = time.time()
    while _running:
        # pausa
        if check_pause():
            if not _paused:
                _paused = True
                _status_text = "pausado"
                log.info("daemon pausado (flag detectado)")
                if _current_app:
                    flush_event(_current_app, _current_title, _current_start, time.time())
                    _current_app = None
            write_heartbeat("paused")
            time.sleep(interval)
            continue
        if _paused:
            _paused = False
            _status_text = "activo"
            log.info("daemon reanudado")

        now = time.time()
        app, title = get_foreground_info()

        # F3 FOCO — detección de fuga de atención
        check_foco_drift(app, title)

        # misma ventana -> acumular
        if app == _current_app and title == _current_title:
            pass
        else:
            # ventana nueva -> flush anterior
            if _current_app:
                flush_event(_current_app, _current_title, _current_start, now)
            _current_app = app
            _current_title = title
            _current_start = now

        _tick_count += 1
        _status_text = f"{_current_app} ({_tick_count} ticks)"
        write_heartbeat("ok")

        # ingest periodico
        if now - _last_ingest >= INGEST_EVERY:
            do_ingest()
            _last_ingest = now

        time.sleep(interval)



    # flush final
    if _current_app:
        flush_event(_current_app, _current_title, _current_start, time.time())
    write_heartbeat("stopped")



# --- Pystray ---

def make_icon(color: str):
    """Genera un icono de 16x16 con el color dado."""
    img = Image.new("RGBA", (16, 16), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    colors = {"green": "#3fb950", "yellow": "#d29922", "red": "#f85149", "gray": "#6e7681"}
    d.ellipse([2, 2, 13, 13], fill=colors.get(color, "#6e7681"))
    return img



def tray_icon_color() -> str:
    hb_file = HEARTBEAT_FILE
    if not hb_file.exists():
        return "red"
    try:
        hb = json.loads(hb_file.read_text(encoding="utf-8"))
        if hb.get("status") == "paused":
            return "yellow"
        last = datetime.fromisoformat(hb["last_tick"]).timestamp()
        age = time.time() - last
        if age > 120:
            return "red"
        if age > 30:
            return "yellow"
        # semaforo real: si ningun provider de modelos responde, alerta
        if not _any_provider_alive():
            return "yellow"
        return "green"
    except Exception:
        return "red"


def _any_provider_alive() -> bool:
    return _port_open(20128) or _port_open(11434)



def on_pause(icon, item):
    global _paused
    if _paused:
        PAUSE_FLAG.unlink(missing_ok=True)
        _paused = False
        log.info("reanudado desde bandeja")
    else:
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        PAUSE_FLAG.touch()
        log.info("pausado desde bandeja")



def on_open_chat(icon, item):
    vbs = PROJECT_ROOT / "start_atlas_chat.vbs"
    if vbs.exists():
        subprocess.Popen(["wscript.exe", str(vbs)], creationflags=0x08000000)  # CREATE_NO_WINDOW



def on_status(icon, item):
    try:
        hb = json.loads(HEARTBEAT_FILE.read_text(encoding="utf-8"))
        msg = f"PID: {hb['pid']}\nStatus: {hb['status']}\nPaused: {hb['paused']}\nTicks: {hb['ticks']}\nUptime: {hb['uptime_seconds']}s"
    except Exception:
        msg = "Sin heartbeat todavia"
    omni = "OK" if _port_open(20128) else "caido"
    ollama = "OK" if _port_open(11434) else "caido"
    msg += f"\n\nSemáforo:\n  omniroute :20128 -> {omni}\n  ollama :11434 -> {ollama}"
    log(f"STATUS desde bandeja: {msg}")
    if icon is not None:
        try:
            icon.notify(msg, "Atlas — Estado")
        except Exception:
            pass


def _port_open(port: int, timeout: float = 0.6) -> bool:
    import socket
    try:
        s = socket.create_connection(("127.0.0.1", port), timeout=timeout)
        s.close()
        return True
    except OSError:
        return False



def on_quit(icon, item):
    global _running
    _running = False
    icon.stop()


def on_set_mode(mode):
    def _cb(icon, item):
        r = foco_rules.set_mode(mode)
        if "error" not in r:
            log.info("modo foco cambiado desde bandeja", mode=mode)
        return True
    return _cb


def _mode_checked(mode):
    def _chk(item):
        return foco_rules.get_mode() == mode
    return _chk



def run_tray():
    global _icon
    icon_color = tray_icon_color()
    icon = pystray.Icon(
        "Atlas",
        make_icon(icon_color),
        "Atlas Activity Daemon",
        menu=pystray.Menu(
            pystray.MenuItem("Pausar / Reanudar", on_pause, default=True),
            pystray.MenuItem("Modo foco", pystray.Menu(
                pystray.MenuItem("off — solo medir", on_set_mode("off"), radio=True, checked=_mode_checked("off")),
                pystray.MenuItem("soft — avisos con presupuesto", on_set_mode("soft"), radio=True, checked=_mode_checked("soft")),
                pystray.MenuItem("strict — avisos agresivos", on_set_mode("strict"), radio=True, checked=_mode_checked("strict")),
            )),
            pystray.MenuItem("Abrir chat", on_open_chat),
            pystray.MenuItem("Estado", on_status),
            pystray.MenuItem("Salir", on_quit),
        ),
    )
    _icon = icon
    # thread del daemon
    t = threading.Thread(target=daemon_loop, args=(interval,), daemon=True)
    t.start()

    # updater del icono (cada 30s)
    def update_icon():
        while _running:
            time.sleep(30)
            try:
                icon.icon = make_icon(tray_icon_color())
            except Exception:
                pass
    threading.Thread(target=update_icon, daemon=True).start()

    icon.run()



# --- Main ---
if __name__ == "__main__":
    _start_time = time.time()
    no_tray = "--no-tray" in sys.argv
    interval = DEFAULT_INTERVAL
    for i, a in enumerate(sys.argv):
        if a == "--interval" and i + 1 < len(sys.argv):
            try:
                interval = int(sys.argv[i + 1])
            except ValueError:
                pass

    log.info(f"arrancando daemon", interval=interval, tray=not no_tray and HAS_TRAY)

    # graceful shutdown
    def _sig(s, f):
        global _running
        _running = False
    signal.signal(signal.SIGINT, _sig)
    signal.signal(signal.SIGTERM, _sig)

    if no_tray or not HAS_TRAY:
        daemon_loop(interval)
    else:
        run_tray()
