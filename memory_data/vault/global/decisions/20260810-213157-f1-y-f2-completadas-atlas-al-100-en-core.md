---
id: 20260810-213157-f1-y-f2-completadas-atlas-al-100-en-core
type: decision
project: global
tags: [f1,f2,completado,roadmap,mission-control,f4]
created: 2026-08-11T02:31:57+00:00
source: opencode
status: active
links:
---

F1 (Memory Core) y F2 (Activity Tracker + Atlas UI) están completadas al 100% según roadmap v1.1.

## F1 completada:
- 15 tools MCP (init, note_save, note_search, session_start/end/recover, event_ingest, pref_set/get, graph_query/rebuild, summary, health, gc, projects)
- Git hook portable: hooks/post-commit (sh, core.hooksPath)
- Backup diario: --cli backup (zip vault+db, retención 14 copias) + AtlasBackup Task Scheduler
- Restore verificado: --cli restore --backup-file <zip>
- DB sana: WAL mode, integrity ok, redacción de secretos

## F2 completada:
- atlas_activity.py: daemon captura ventana activa ~10s via ctypes
- Heartbeat en state/daemon.heartbeat, visible en memory_health
- Bandeja pystray con estado 🟢/🟡/🔴, pausa, chat, salir
- Task Scheduler: AtlasActivity (ONLOGON, restart on failure)
- Chat flotante: atlas_chat.py abre sesión directa (POST /session)
- api.js: wrapper fino UI↔opencode serve
- dashboard.html: dashboard base de actividad

## Decisión F4:
Mission Control (E:\PROYECTOS\mission_control, Django 6) es el cimiento de F4 (dashboard financiero). Cuando arranque F4, conectar Atlas a Mission Control en vez de reconstruir.
