#!/usr/bin/env python3
"""
atlas_secret_reminder.py — Recordatorio semanal de rotacion de secretos.

Solo muestra un aviso si la rotacion esta vencida (days_remaining <= 0).
Se invoca via Task Scheduler (AtlasSecretReminder, semanal).

Uso: python atlas_secret_reminder.py
"""
import ctypes
import json
import os
import sys
from pathlib import Path

STATE_DIR = Path(__file__).resolve().parent / "memory_data" / "state"
ROT_FILE = STATE_DIR / "secret_rotation.json"
DAYS = 90


def main():
    if not ROT_FILE.exists():
        return  # sin calendario: no molestar
    try:
        data = json.loads(ROT_FILE.read_text(encoding="utf-8"))
        last = data.get("last_rotated", "")
        if not last:
            return
        from datetime import datetime
        next_due = datetime.fromisoformat(last).timestamp() + DAYS * 86400
        import time
        remaining = int((next_due - time.time()) / 86400)
        if remaining > 0:
            return  # aun no vence
        # aviso en ventana nativa de Windows
        msg = (f"Atlas: la rotacion de secretos esta vencida.\n"
               f"Ultima rotacion: {last}\n"
               f"Hace mas de {DAYS} dias.\n\n"
               f"Rota las credenciales y registralo con:\n"
               f"  python mcp_memory_server.py --cli secret_rotation")
        ctypes.windll.user32.MessageBoxW(0, msg, "Atlas - Rotar secretos", 0x10)
    except Exception:
        pass


if __name__ == "__main__":
    main()
