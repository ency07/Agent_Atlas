---
id: 20260810-chat-flotante-f2
type: decision
project: global
tags: [f2, chat, ui, pywebview, opencode-serve]
created: 2026-08-10T08:46:00+00:00
source: opencode
status: active
---

Se implemento el chat flotante de Atlas (F2 · Opcion A del roadmap).

## Que se hizo

- `atlas_chat.py`: launcher que reutiliza/arranca `opencode serve` en
  `127.0.0.1:4096` (modelo por defecto `omniroute/auto/best-chat` via env
  `OPENCODE_CONFIG_CONTENT`) y abre ventana pywebview (WebView2) frameless,
  siempre-al-frente, con overlay de arrastre + minimizar/cerrar.
- `start_atlas_chat.vbs`: autostart oculto con `pythonw.exe` del `.venv`.
- Tarea `AtlasChat` (Task Scheduler, ONLOGON) registrada con
  `Register-ScheduledTask` (schtasks escapaba mal las comillas y colgaba).
- Anti-duplicados con mutex nombrado `Local\AtlasChatSingleInstance`
  (el socket lock con SO_REUSEADDR no funciona en Windows).
- `setup.ps1 -InstallF2` registra la tarea en PC nuevos.
- roadmap.html: F2 marcado como Parcial (chat listo, falta daemon de captura).

## Lecciones

1. `schtasks /Create` con rutas con espacios necesita cuidado extremo con el
   quoting; `Register-ScheduledTask` es mas fiable.
2. ctypes mutex: usar `ctypes.WinDLL("kernel32", use_last_error=True)` para que
   `get_last_error()` capture ERROR_ALREADY_EXISTS.
3. `opencode serve` + `OPENCODE_CONFIG_CONTENT={"model":...}` fija el modelo
   por defecto del chat web. cwd = Desktop -> memoria en modo global.

## Pendiente

- Daemon de captura de ventana activa (eventos continuos -> tabla events, input
  de F3).
- Remoto git cuando se decida.

## Comandos utiles

- Abrir chat: `python atlas_chat.py` (o .\start_atlas_chat.vbs)
- Solo server: `python atlas_chat.py --server-only`
- Autostart: `powershell -ExecutionPolicy Bypass -File setup.ps1 -InstallF2`
- Quitar autostart: `schtasks /Delete /TN "AtlasChat" /F`
- Log: `atlas_chat.log` junto al proyecto.
