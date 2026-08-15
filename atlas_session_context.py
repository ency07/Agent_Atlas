#!/usr/bin/env python3
"""
atlas_session_context.py — Gestión de contexto sesiones largas (C3-10).
Resumen deslizante en sesiones >1h; no degrada a las 2h.
"""
import json
import time
from pathlib import Path
from typing import List, Dict, Any
from collections import deque

ROOT = Path(__file__).parent
STATE_DIR = ROOT / "memory_data" / "state"
SESSION_CTX_FILE = STATE_DIR / "session_context.json"

# Config
MAX_MESSAGES = 200          # límite duro de mensajes almacenados
SUMMARY_EVERY = 50          # cada N mensajes generar/actualizar resumen
MAX_AGE_SECONDS = 7200      # 2h máximo vida de mensajes sin resumen

class SessionContext:
    def __init__(self):
        self.messages: deque = deque(maxlen=MAX_MESSAGES)
        self.summary = ""
        self.message_count = 0
        self.last_summary_at = 0
        self._load()

    def _load(self):
        if Path(SESSION_CTX_FILE).exists():
            try:
                data = json.loads(Path(SESSION_CTX_FILE).read_text(encoding="utf-8"))
                self.messages = deque(data.get("messages", []), maxlen=MAX_MESSAGES)
                self.summary = data.get("summary", "")
                self.message_count = data.get("message_count", 0)
                self.last_summary_at = data.get("last_summary_at", 0)
            except Exception:
                pass

    def _save(self):
        Path(SESSION_CTX_FILE).parent.mkdir(parents=True, exist_ok=True)
        data = {
            "messages": list(self.messages),
            "summary": self.summary,
            "message_count": self.message_count,
            "last_summary_at": self.last_summary_at,
        }
        Path(SESSION_CTX_FILE).write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

    def add_message(self, role: str, content: str):
        """Añade mensaje y gestiona resumen deslizante."""
        now = time.time()
        self.messages.append({"role": role, "content": content, "ts": now})
        self.message_count += 1

        # generar/actualizar resumen cada SUMMARY_EVERY mensajes
        if self.message_count - self.last_summary_at >= SUMMARY_EVERY:
            self._update_summary()
            self.last_summary_at = self.message_count

        # limpiar mensajes antiguos >2h si hay resumen
        if self.summary:
            cutoff = now - MAX_AGE_SECONDS
            # eliminar mensajes antiguos del deque (izquierda)
            while self.messages and self.messages[0]["ts"] < cutoff:
                self.messages.popleft()
        self._save()

    def _update_summary(self):
        # simple resumen: últimas 10 mensajes
        recent = list(self.messages)[-10:]
        parts = []
        for m in recent:
            parts.append(f"{m['role']}: {m['content'][:120]}")
        self.summary = " | ".join(parts)

    def get_context(self) -> Dict[str, Any]:
        """Devuelve contexto compacto para inyección en prompt."""
        return {
            "summary": self.summary,
            "recent_messages": list(self.messages)[-20:],
            "total_messages": self.message_count,
            "summary_age": self.message_count - self.last_summary_at,
        }

    def clear(self):
        self.messages.clear()
        self.summary = ""
        self.message_count = 0
        self.last_summary_at = 0
        self._save()

# Instancia global
_session_ctx = SessionContext()

def add_message(role: str, content: str):
    _session_ctx.add_message(role, content)

def get_context() -> Dict[str, Any]:
    return _session_ctx.get_context()

def clear_session():
    _session_ctx.clear()

# CLI
if __name__ == "__main__":
    import sys, json
    if "--add" in sys.argv:
        role = "user"
        content = ""
        for i,a in enumerate(sys.argv):
            if a == "--role" and i+1 < len(sys.argv): role = sys.argv[i+1]
            if a == "--content" and i+1 < len(sys.argv): content = sys.argv[i+1]
        add_message(role, content)
        print("added")
    elif "--context" in sys.argv:
        print(json.dumps(get_context(), ensure_ascii=False, indent=2))
    elif "--clear" in sys.argv:
        clear_session()
        print("cleared")
    else:
        print("Uso: python atlas_session_context.py --add --role user --content 'hola' | --context | --clear")