---
id: 20260813-150607-sesi-n-orquestador-vivo-mcp-consolidado-
type: session
project: global
tags: [orquestador,dashboard,consolidacion,f4,pendientes]
created: 2026-08-13T20:06:07+00:00
source: opencode
status: active
links:
---

Sesión productiva: 3 features completados + commits:

1. ORQUESTADOR VIVO (822d357, 35b720e): atlas_orchestrator.py MCP 7 tools. Detección REAL por API (no puerto): active_providers consulta /v1/models (omniroute/9router) o /api/tags (ollama) con caché 15s. Puerto abierto + API sin responder = NO usable (demo: ollama apareció caído). Pool solo con modelos instalados reales (omniroute 260, curados 5: best-coding/reasoning/fast/chat/vision). Capacidades inferidas por heurística si no están en mapa. Circuit breaker: 3 fallos -> cooldown 300s. register_error/success tools. Fix clasificación: 'ui' con word-boundary (arquitectura ya no matchea visión). best-research NO existe en omniroute real -> mapa tenía dato muerto, orquestador cae a best-reasoning. routing_log.json en state.

2. CONSOLIDACIÓN MCP (3990703): mcp_windows_server.py, mcp_corel_server.py, mcp_playwright_visual_server.py + docs/tests/examples movidos de E:\MCP\mcp-windows-ai a E:\Agente_IA\mcp_windows\. setup.ps1 busca mcp_windows/ primero. check.ps1 sección [MCP windows consolidado] (compara ruta JSON con backslashes escapados). Repo autocontenido -> PC nuevo en 15 min.

3. DASHBOARD REAL (6384ed6): atlas_web_server.py :4100 un solo servidor. Sirve dashboard.html + /api/overview (daemon heartbeat, events_total 780, sessions_total 3, last_tick), /api/top-apps (top 12 apps 24h: Qwen 13853s, wezterm 7871s, librewolf 7861s), /api/foco (reusa atlas_foco), /api/health (reusa atlas_health, status yellow), /api/orchestrator, /api/modelo. Elimina dependencia opencode serve + 3 servers. Autostart: start_atlas_web.vbs + tarea AtlasWeb (ONLOGON) registrada y validada. Dashboard JS reescrito, top-apps con barras.

Siguiente: F4 DINERO (mission_control cimiento), luego deudas técnicas (git remote, deshabilitar MCP playwright/ollama, sincronizar modelo_capabilities con catálogo real).
