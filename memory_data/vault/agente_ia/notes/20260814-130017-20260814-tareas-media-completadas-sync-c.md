---
id: 20260814-130017-20260814-tareas-media-completadas-sync-c
type: summary
project: agente_ia
tags: [roadmap,medio,capacidades,benchmark,model_switch,metricas,atlas]
created: 2026-08-14T18:00:17+00:00
source: opencode
status: active
links:
---

Se completaron las 4 tareas MEDIA del roadmap tras F1/F3 (el 20260814):

1. **Auto-sync capacidades** (`atlas_sync_capabilities.py`): consulta /v1/models de omniroute/9router/ollama, regenera model_capabilities.json (preservando capacidades curadas), genera diff. Tarea `AtlasSyncCapabilities` lunes 03:15. Commit 0adb530.

2. **Benchmark real** (`atlas_benchmark.py`): mide latencia y éxito por provider, acumula en routing_log.json (provider_stats). Tarea `AtlasBenchmark` lunes 03:20 (3 rondas). Commit 6153fe1. Resultado: omniroute ~2-3.8s, 9router ~2s, ollama ~2s, todos 100% éxito.

3. **Auto-cambio de modelo runtime** (`atlas_model_switch.py`): analiza tarea con orquestador, cambia modelo en ~/.config/opencode/opencode.jsonc SOLO si el activo no cubre la capacidad requerida (vision/coding/reasoning). Backup automático. Commit 04b12e4. Lógica clave: `_model_has_capability()` evita cambios innecesarios (ej. best-coding ya cubre coding).

4. **Métricas uso/costo** (`atlas_metrics.py`): usage_log.json con llamadas (modelo, tokens, costo, latencia), pricing por provider (ollama local=$0, omniroute $0.15/$0.60 por M), ingesta desde routing_log, informes periodos. El benchmark ahora registra uso real en --deep. Tarea `AtlasMetrics` lunes 03:25. Commit 5690da8.

Verificación: 72/72 unit tests PASS + 15/15 config tests PASS.

PENDIENTE MEDIA: configurar git remote (origin) - requiere URL del repo del usuario.
PENDIENTES ALTA históricas: auto-inicio AtlasChat, 9Router ONLOGON, orquestador como modelo por defecto.
PENDIENTE MEDIA mayor: F4 DINERO con mission_control (Django).
