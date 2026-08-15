#!/usr/bin/env python3
"""Tests for P-2: friction_log endpoints."""
import json
import subprocess
import sys
import time
import threading
import urllib.request
import urllib.error

# Add project root to path
sys.path.insert(0, "E:/Agente_IA")

ROOT = "E:/Agente_IA"

def start_server():
    """Start atlas_web_server in background thread."""
    import atlas_web_server
    import threading
    def run():
        atlas_web_server.main()
    t = threading.Thread(target=run, daemon=True)
    t.start()
    time.sleep(2)
    return t

def test_friction_endpoints():
    """Test P-2 friction endpoints."""
    base = "http://127.0.0.1:4100"
    
    # Start server
    t = start_server()
    
    try:
        # Test 1: GET friction log (may have existing entries)
        r = urllib.request.urlopen(f"{base}/api/friction")
        data = json.loads(r.read().decode())
        initial_count = data["count"]
        assert isinstance(data["items"], list), "Items should be list"
        assert "debug" in data, "Missing debug marker"
        print("OK GET /api/friction (initial count: %d)" % initial_count)
        
        # Test 2: POST valid friction event
        payload = json.dumps({
            "type": "correccion",
            "detail": "test correction",
            "meta": {"source": "pytest"}
        }).encode()
        req = urllib.request.Request(
            f"{base}/api/friction",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        r = urllib.request.urlopen(req)
        data = json.loads(r.read().decode())
        assert data["ok"] == True, "POST should return ok"
        assert data["entry"]["type"] == "correccion"
        print("OK POST /api/friction (valid)")
        
        # Test 3: GET after POST
        r = urllib.request.urlopen(f"{base}/api/friction")
        data = json.loads(r.read().decode())
        assert data["count"] == initial_count + 1, "Expected %d, got %d" % (initial_count + 1, data["count"])
        assert data["items"][0]["type"] == "correccion"
        print("OK GET /api/friction (after POST)")
        
        # Test 4: POST invalid type
        payload = json.dumps({"type": "invalid", "detail": "test"}).encode()
        req = urllib.request.Request(
            f"{base}/api/friction",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        try:
            urllib.request.urlopen(req)
            assert False, "Should have raised 400"
        except urllib.error.HTTPError as e:
            assert e.code == 400, "Expected 400, got %d" % e.code
            print("OK POST /api/friction (invalid type rejected)")
        
        # Test 5: GET weekly
        r = urllib.request.urlopen(f"{base}/api/friction/weekly")
        data = json.loads(r.read().decode())
        assert "weeks" in data
        assert "total" in data
        assert data["total"] >= 1
        print("OK GET /api/friction/weekly")
        
        # Test 6: Verify file written
        with open("E:/Agente_IA/memory_data/state/friction_log.jsonl", "r", encoding="utf-8") as f:
            lines = f.read().strip().splitlines()
        assert len(lines) >= 1
        entry = json.loads(lines[-1])
        assert entry["type"] == "correccion"
        print("OK friction_log.jsonl written")
        
        print("\nAll P-2 tests passed!")
        return True
        
    except Exception as e:
        print("FAIL Test failed: %s" % e)
        import traceback
        traceback.print_exc()
        return False
    finally:
        # Server runs in daemon thread, will die when main exits
        pass

if __name__ == "__main__":
    success = test_friction_endpoints()
    sys.exit(0 if success else 1)