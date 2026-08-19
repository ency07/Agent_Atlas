#!/usr/bin/env python3
"""
launch_hud.py — Levanta el Bridge y abre el HUD en el navegador.

Uso: python launch_hud.py [--port 8765] [--no-browser]
"""
import sys
import os
import time
import threading
import webbrowser

# Add backend to path
BACKEND_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "backend")
sys.path.insert(0, BACKEND_DIR)

PORT = 8765
OPEN_BROWSER = True

for i, arg in enumerate(sys.argv[1:], 1):
    if arg == "--port" and i < len(sys.argv):
        PORT = int(sys.argv[i + 1])
    if arg == "--no-browser":
        OPEN_BROWSER = False

os.chdir(BACKEND_DIR)

import uvicorn


def run_server():
    uvicorn.run("bridge:app", host="0.0.0.0", port=PORT, log_level="info")


if __name__ == "__main__":
    print(f"\n{'='*55}")
    print(f"  AEGIS-JARVIS HUD Launcher")
    print(f"  http://127.0.0.1:{PORT}")
    print(f"  LAN: http://<tu-ip>:{PORT}")
    print(f"{'='*55}\n")

    t = threading.Thread(target=run_server, daemon=True)
    t.start()

    # Wait for server to be ready
    import requests
    for attempt in range(10):
        time.sleep(1)
        try:
            r = requests.get(f"http://127.0.0.1:{PORT}/", timeout=2)
            if r.status_code == 200:
                print("[OK] Server ready!")
                break
        except Exception:
            pass
    else:
        print("[WARN] Server may not be ready, opening anyway...")

    if OPEN_BROWSER:
        print(f"[OK] Opening http://127.0.0.1:{PORT} in browser...")
        webbrowser.open(f"http://127.0.0.1:{PORT}")

    print("\nHUD is running. Press Ctrl+C to stop.\n")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nShutting down...")
