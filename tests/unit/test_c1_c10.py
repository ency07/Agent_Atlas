# ============================================================
# tests/unit/test_c1_c10.py — REQ-C10 tools de ejecucion verificada
# (screen_capture, read_ui_state, ocr_screen, open_app)
# ------------------------------------------------------------
import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import mcp_windows.mcp_windows_server as win

def parse_result(result):
    if isinstance(result, str):
        return json.loads(result)
    return result


def test_screen_capture_full():
    r = parse_result(win.screen_capture(region="full"))
    if "error" in r and "pyautogui" in str(r.get("error", "")):
        return  # entorno sin GUI
    assert r.get("success") is True
    assert Path(r["path"]).exists()
    assert r["path"].endswith(".png")


def test_screen_capture_region():
    r = parse_result(win.screen_capture(region="0,0,100,100"))
    if "error" in r:
        return
    assert r.get("success") is True


def test_open_app_known():
    r = parse_result(win.open_app("cmd"))
    assert r.get("success") is True
    assert "pid" in r


def test_open_app_blocked_by_guardian():
    # nootepad no esta en whitelist del guardian -> debe bloquear
    r = parse_result(win.open_app("notepad"))
    assert "error" in r
    assert "BLOQUEADO" in r.get("error", "").upper() or "guard" in r.get("error", "").lower()


def test_read_ui_state():
    r = parse_result(win.read_ui_state())
    if "error" in r:
        return  # entorno sin UI activa
    assert r.get("success") is True
    assert "tree" in r
