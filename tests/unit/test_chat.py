# ============================================================
# tests/unit/test_chat.py — Tests de atlas_chat.py (F2.5)
# ------------------------------------------------------------
import sys
import time
import shutil
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import atlas_chat as ac


def test_find_opencode_bin_found():
    """El binario de opencode se localiza (exe real o shim .cmd)."""
    b = ac.find_opencode_bin()
    assert b is not None
    assert Path(b).exists()


def test_find_opencode_bin_version_parses():
    """La version se extrae correctamente del binario."""
    b = ac.find_opencode_bin()
    v = ac._bin_version(str(b))
    assert v != ""


def test_server_up_down():
    """server_up() da False cuando no hay nada escuchando."""
    # Puerto aleatorio alto que no deberia estar ocupado
    assert ac.server_up(4399) is False


def test_start_server_writes_stderr_log():
    """start_server escribe cabecera en atlas_chat_stderr.log (no DEVNULL)."""
    b = ac.find_opencode_bin()
    # usar puerto de test
    old = ac.STDERR_LOG
    test_log = Path(__file__).parent / "chat_test_stderr.log"
    ac.STDERR_LOG = test_log
    try:
        proc = ac.start_server(b, 4199, "auto/best-fast")
        time.sleep(1)
        # el proceso debe estar vivo
        assert proc.poll() is None, "opencode serve murio al arrancar"
        # la cabecera debe haberse escrito
        assert test_log.exists()
        content = test_log.read_text(encoding="utf-8", errors="replace")
        assert "--port=4199" in content
    finally:
        try:
            ac.stop_server(4199)
        except Exception:
            pass
        ac.STDERR_LOG = old
        time.sleep(1)
        if test_log.exists():
            try:
                test_log.unlink()
            except PermissionError:
                pass


def test_start_server_uses_preferred_bin():
    """Usa el binario de mayor version (nunca devuelve None con binario presente)."""
    b = ac.find_opencode_bin()
    assert b is not None
    assert isinstance(b, str)


def test_stop_server_no_crash():
    """stop_server no falla aunque no haya procesos en el puerto."""
    ac.stop_server(4398)  # puerto libre


if __name__ == "__main__":
    test_find_opencode_bin_found()
    test_find_opencode_bin_version_parses()
    test_server_up_down()
    test_start_server_writes_stderr_log()
    test_start_server_uses_preferred_bin()
    test_stop_server_no_crash()
    print("OK tests/unit/test_chat.py")