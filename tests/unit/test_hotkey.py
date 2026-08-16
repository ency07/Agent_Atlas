# ============================================================
# tests/unit/test_hotkey.py — Tests del hotkey global (Ctrl+Alt+A)
# Reabre/trae al frente la ventana flotante del chat Atlas.
# ------------------------------------------------------------
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import atlas_activity as aa


def test_open_chat_launches_vbs():
    """_open_chat lanza wscript con start_atlas_chat.vbs (sin consola)."""
    vbs = aa.PROJECT_ROOT / "start_atlas_chat.vbs"
    assert vbs.exists()
    with patch("atlas_activity.subprocess.Popen") as popen:
        aa._open_chat()
        popen.assert_called_once()
        args = popen.call_args.args[0]
        assert args[0].lower() == "wscript.exe"
        assert str(vbs).lower() in str(args[1]).lower()
        assert popen.call_args.kwargs["creationflags"] == 0x08000000  # CREATE_NO_WINDOW


def test_focus_brings_existing_window_to_front():
    """Ventana Atlas existente -> ShowWindow + SetForegroundWindow, sin reabrir."""
    called = {"show": False, "front": False, "reopen": False}
    orig = (aa.FindWindowW, aa.ShowWindow, aa.SetForegroundWindow, aa._open_chat)
    aa.FindWindowW = lambda klass, title: 12345
    aa.ShowWindow = lambda h, cmd: called.update(show=True) or True
    aa.SetForegroundWindow = lambda h: called.update(front=True) or True
    aa._open_chat = lambda: called.update(reopen=True)
    try:
        aa._focus_or_open_chat()
    finally:
        (aa.FindWindowW, aa.ShowWindow, aa.SetForegroundWindow, aa._open_chat) = orig
    assert called["show"] and called["front"] and not called["reopen"]


def test_focus_reopens_when_closed():
    """Sin ventana Atlas -> _open_chat() (reabre)."""
    reopened = {"n": 0}
    orig = (aa.FindWindowW, aa._open_chat)
    aa.FindWindowW = lambda klass, title: 0
    aa._open_chat = lambda: reopened.update(n=reopened["n"] + 1)
    try:
        aa._focus_or_open_chat()
    finally:
        (aa.FindWindowW, aa._open_chat) = orig
    assert reopened["n"] == 1


def test_hotkey_constants():
    """Ctrl+Alt+A sin auto-repeat: MOD_ALT|MOD_CONTROL|MOD_NOREPEAT y VK 'A'."""
    assert aa.HOTKEY_MOD == (0x1 | 0x2 | 0x4000)
    assert aa.HOTKEY_VK == ord("A")
    assert aa.WM_HOTKEY == 0x0312


def test_hotkey_loop_graceful_on_conflict():
    """Combinacion tomada -> warning y return, sin colgar el thread."""
    with patch("atlas_activity.RegisterHotKey", return_value=False) as reg, \
         patch("atlas_activity.UnregisterHotKey") as unreg:
        aa._hotkey_loop()
    reg.assert_called_once()
    unreg.assert_not_called()


def test_register_hotkey_mechanism_works():
    """Smoke test real: RegisterHotKey/UnregisterHotKey ctypes (VK_F24, poco usado)."""
    vk_f24 = 0x87
    ok = aa.RegisterHotKey(None, aa.HOTKEY_ID, aa.HOTKEY_MOD, vk_f24)
    try:
        assert ok, "RegisterHotKey fallo (mecanismo ctypes roto o F24 tomado)"
    finally:
        if ok:
            aa.UnregisterHotKey(None, aa.HOTKEY_ID)


def test_single_instance_mutex_enforced():
    """acquire_single_instance() devuelve None si otra instancia ya tiene el mutex."""
    import ctypes as _ctypes
    # si el daemon externo tiene el mutex, la primera llamada ya devuelve None
    first = aa.acquire_single_instance()
    second = aa.acquire_single_instance()
    if first:
        # nosotros tenemos el mutex -> el segundo fallo
        assert second is None, "deberia devolver None (ERROR_ALREADY_EXISTS)"
        aa.kernel32.CloseHandle(_ctypes.c_void_p(first))
    else:
        # el daemon activo tiene el mutex -> ambos None, correcto
        assert first is second is None


if __name__ == "__main__":
    test_open_chat_launches_vbs()
    test_focus_brings_existing_window_to_front()
    test_focus_reopens_when_closed()
    test_hotkey_constants()
    test_hotkey_loop_graceful_on_conflict()
    test_register_hotkey_mechanism_works()
    test_single_instance_mutex_enforced()
    print("OK tests/unit/test_hotkey.py")
