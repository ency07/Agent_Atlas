# ============================================================
# tests/unit/test_bootcheck.py — Tests de boot check E2E
# ------------------------------------------------------------
import sys
import threading
import http.server
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import atlas_bootcheck as bc

class _OKHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Length", "2")
        self.end_headers()
        self.wfile.write(b"{}")
    def log_message(self, *a):
        pass

def test_check_port():
    # Puerto que debería estar abierto (daemon health)
    assert bc.check_port("127.0.0.1", 4100) == True
    # Puerto que no debería estar abierto
    assert bc.check_port("127.0.0.1", 9999) == False

def test_check_http_isolated():
    """Aislado con server HTTP efimero en localhost (no depende de :4100). A-08."""
    srv = http.server.HTTPServer(("127.0.0.1", 0), _OKHandler)
    port = srv.server_address[1]
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    try:
        assert bc.check_http(f"http://127.0.0.1:{port}/api/health", timeout=5) == True
        assert bc.check_http("http://127.0.0.1:9999/api/health", timeout=1) == False
    finally:
        srv.shutdown()
        srv.server_close()

def test_check_http_reachable_4100():
    # Integracion real contra el server del proyecto (diagnostico, no aislado)
    assert bc.check_http("http://127.0.0.1:4100/api/health", timeout=5) == True

def test_check_daemon():
    ok, detail = bc.check_daemon()
    assert ok == True
    assert "PID" in detail

def test_check_web():
    ok, detail = bc.check_web()
    assert ok == True
    assert "respondiendo" in detail

def test_check_providers():
    ok, detail = bc.check_providers()
    assert ok == True
    assert "activos" in detail

def test_check_venv():
    ok, detail = bc.check_venv()
    assert ok == True
    assert ".venv" in detail

def test_run_bootcheck():
    status, results = bc.run_bootcheck(timeout=10)
    assert status in ("green", "yellow", "red")
    assert len(results) == 4
    assert all("name" in r and "ok" in r and "detail" in r for r in results)

if __name__ == "__main__":
    test_check_port()
    test_check_http_isolated()
    test_check_http_reachable_4100()
    test_check_daemon()
    test_check_web()
    test_check_providers()
    test_check_venv()
    test_run_bootcheck()
    print("✅ tests/unit/test_bootcheck.py: OK")