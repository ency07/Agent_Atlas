---
id: 20260811-100414-20260811-endurecimiento-produccion-6-pun
type: decision
project: global
tags: [produccion,logging,errores,rate-limit,health,rollback,secretos]
created: 2026-08-11T15:04:14+00:00
source: opencode
status: active
links:
---

Los 6 puntos de endurecimiento de producción quedaron implementados y commiteados (f859bfd) ANTES de pasar a F3/F4:

1. Logs estructurados JSON → atlas_log.py (ts/level/source/request_id/error), usado por atlas_chat.py y atlas_activity.py en logs/
2. Monitoreo de errores → atlas_monitor.py: logs/errors.jsonl + state/errors.db con frecuencia; visible en memory_health como errors_24h
3. Rate limiting → RateLimiter en atlas_monitor.py; el daemon limita a 6 eventos/min para no inundar inbox
4. Health check → memory_health ahora reporta DB, daemon, inbox, errores 24h y rotación de secretos
5. Plan de rollback → git tag stable-f1f2 + backups diarios + restore; documentado en HANDOFF.md (< 5 min)
6. Rotación de secretos → calendario 90 días en state/secret_rotation.json; recordatorio semanal (AtlasSecretReminder, domingo 09:00); registrar con `python mcp_memory_server.py --cli secret_rotation`

Todo verificado con check.ps1 (TODO OK). Herramientas elegidas son 100% open source (solo stdlib de Python: logging, sqlite3, ctypes). Siguiente: F3 anti-distracción con la clasificación de apps ya anotada como input.
