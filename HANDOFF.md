# HANDOFF — Atlas

> Documento de estado del proyecto. Léelo primero si retomas el trabajo.

**Última actualización:** 12 de agosto de 2026

---

## Qué es

Atlas es un **servidor MCP de memoria persistente** que vive en una bóveda
Obsidian (notas `.md` con frontmatter + wikilinks) indexada en SQLite, con un
grafo de conocimiento derivado. Se conecta a `opencode` como MCP server.

Componentes:

| Archivo | Rol |
|---|---|
| `mcp_memory_server.py` | Servidor MCP de memoria (FastMCP). Núcleo. |
| `atlas_chat.py` | Chat flotante (F2): `opencode serve` + ventana frameless. |
| `atlas_activity.py` | Daemon de actividad (F2): captura ventana activa + bandeja. |
| `foco_rules.py` | Clasificador de actividad monetizable/distracción (F3). |
| `atlas_foco.py` | MCP foco (F3): métricas, modo disciplina, HTTP `/daily` para dashboard. |
| `atlas_health.py` | MCP semáforo (S1): estado global del sistema, HTTP `/health`. |
| `skills/atlas_orchestrator/` | Orquestador (O1): selección de modelo por tarea. |
| `atlas_search.py` | Búsqueda web (DuckDuckGo → SearXNG → DDG HTML) + investigación profunda. |
| `atlas_guardian.py` | Modo guardián: restricciones configurables sobre acciones del PC. |
| `atlas_web/api.js` | Wrapper fino UI↔opencode serve. |
| `atlas_web/dashboard.html` | Dashboard base de actividad. |
| `start_atlas_chat.vbs` | Autostart oculto del chat flotante. |
| `start_atlas_backup.vbs` | Backup diario oculto via Task Scheduler. |
| `hooks/post-commit` | Git hook portable → inbox/. |
| `memory_data/vault/` | Bóveda Obsidian — la memoria viaja con el repo. |
| `memory_data/state/` | SQLite + heartbeat + flags (NO se versiona). |
| `memory_data/backup/` | Backups zip (gitignored, retención 14 copias). |
| `roadmap.html` | Roadmap por fases (F1–F6) y trazabilidad. |

---

## Estado por fases

### F1 · CORE — 🟢 100% COMPLETADA

| Gate | Estado |
|---|---|
| 15 tools MCP OK | ✅ `memory_init`, `note_save`, `note_search`, `session_start`, `session_end`, `session_recover`, `event_ingest`, `pref_set`, `pref_get`, `graph_query`, `graph_rebuild`, `summary`, `health`, `gc`, `projects` |
| Escritura concurrente sin corrupción | ✅ WAL mode + timeout=10s |
| `memory_session_recover` OK | ✅ marca sesiones huérfanas como `recovered` |
| Restore de backup OK | ✅ `--cli restore --backup-file <zip>` verificado |
| Server solo escribe en vault/ | ✅ `project_dir()` valida ruta contra VAULT_ROOT |
| Secretos redactados | ✅ `redact()` en toda escritura |
| Git hook → inbox/ | ✅ `hooks/post-commit` (sh portable, core.hooksPath) |
| Backup diario + restore | ✅ `--cli backup` (zip vault+db, retención 14 copias) + `AtlasBackup` Task Scheduler |

### F2 · ACTIVIDAD — 🟢 100% COMPLETADA

| Gate | Estado |
|---|---|
| Daemon background | ✅ `atlas_activity.py` (ctypes, ~10s, CPU bajo) |
| Captura ventana activa → `events` | ✅ escribe a `inbox/activity-*.jsonl` + ingest periódico |
| Chat flotante con input | ✅ `atlas_chat.py` abre sesión directa (`POST /session`) |
| Heartbeat visible en `memory_health` | ✅ `state/daemon.heartbeat` + `read_daemon_heartbeat()` |
| Pausa detiene captura <1s | ✅ flag file `state/activity.paused` |
| Daemon sobrevive reboot | ✅ `AtlasActivity` Task Scheduler (ONLOGON, restart on failure) |
| Retención: crudos 90 días | ✅ `memory_gc` (default 90 días) |
| Bandeja con estado 🟢/🟡/🔴 | ✅ pystray integrado en `atlas_activity.py` |
| Wrapper `api.js` | ✅ `atlas_web/api.js` (fetch a opencode serve) |
| Dashboard base | ✅ `atlas_web/dashboard.html` (estado daemon, eventos, top apps) |

### F3 · FOCO — 🟢 100% COMPLETADA

Anti-distracción: clasificación monetizable/distracción, avisos, modos de disciplina.

| Gate | Estado |
|---|---|
| Clasificación monetizable/distracción | ✅ `foco_rules.py`: categorías (dev/research/comms/social/game/other/exception), prioridad por título de pestaña, reglas editables |
| Reglas `activity_rules.json` editable | ✅ `state/foco_rules.json` + `templates/foco_rules.json.example` |
| Umbrales ajustables sin tocar código | ✅ `thresholds` (180s soft / 60s strict, presupuesto 3/día, target 50min) |
| Avisos de distracción | ✅ balloon de bandeja (`icon.notify`) con presupuesto ≤3/día; sin bandeja → evento `focus_notice` auditado |
| Modos de disciplina | ✅ `off` / `soft` (default) / `strict`, cambiables desde bandeja, MCP o archivo |
| Override manual | ✅ `foco_override(app, category)` (MCP) |
| Métrica tiempo productivo vs fugado → F4 | ✅ `foco_daily_summary(date)` (MCP) + CLI `--cli daily` |
| Backfill históricos | ✅ `foco_backfill(force)` (MCP) + CLI `--cli backfill [--force]` — 360 eventos clasificados |
| Dashboard foco | ✅ tarjeta "Foco hoy" + top distracciones (sirve `python atlas_foco.py --http 4101`) |
| Bandeja: switch modo | ✅ submenú "Modo foco" con radio off/soft/strict |
| Tests clasificador | ✅ 7/7 (apps, títulos navegador, excepciones, default) |

### O1 · ORQUESTADOR DE MODELOS — 🟢 COMPLETADA

Selección de modelo por tipo de tarea. Evita que Atlas trabaje "a ciegas".

| Gate | Estado |
|---|---|
| Mapa de capacidades por modelo | ✅ `memory_data/state/model_capabilities.json` (vision/coding/reasoning/research/speed + `task_to_model`) |
| Skill orquestador | ✅ `skills/atlas_orchestrator/SKILL.md` (instalado en config de opencode por setup.ps1) |
| Regla dorada | ✅ NUNCA revisión visual con `vision=false` — avisa y sugiere `auto/best-vision` |
| Alternativas sin visión | ✅ `pw_visual_audit`, `pw_computed_style`, `pw_diff` (deterministas, no requieren que el modelo vea) |
| Demostración | ✅ Este modelo (best-coding) no lee imágenes → el orquestador lo detecta y sugiere cambio |

### S1 · SEMÁFORO DEL SISTEMA — 🟢 COMPLETADA

Estado global del ecosistema en bandeja + dashboard.

| Gate | Estado |
|---|---|
| `atlas_health.py` | ✅ MCP (`health_status`/`health_check`) + CLI + HTTP :4102 |
| Chequeo por componente | ✅ daemon, omniroute, ollama, venv, state, configs, inbox → green/yellow/red |
| Bandeja | ✅ color real (providers activos) + "Estado" muestra omniroute/ollama |
| Dashboard | ✅ tarjeta semáforo + tabla componentes + modelo activo (colores green/yellow/red) |
| Setup/check | ✅ setup.ps1 registra MCP + skill; check.ps1 valida |

### F4 · DINERO — ⚪ No iniciada

Money + Content Engines: radar de oportunidades, métricas $, motor de contenido.

**⚠️ Cimiento disponible:** El proyecto `E:\PROYECTOS\mission_control` (Django 6, finanzas, 46 tests, túnel Cloudflare) ya tiene exactamente lo que F4 necesita:
- Dashboard financiero con cuentas, inversiones, gastos, presupuestos
- Reportes de 12 meses con tasa de ahorro
- Multi-moneda con conversión automática
- Cloudflare Tunnel para acceso desde móvil

**Recomendación:** Cuando arranque F4, conectar Atlas a Mission Control en vez de reconstruir un dashboard financiero. Atlas aporta los eventos de actividad y la memoria; Mission Control aporta la UI financiera.

### F5 · TUTOR — ⚪ No iniciada

Trading Tutor (demo): journal, checklist, adaptador CSV TradingView.

### F6 · HORIZONTE — ⚪ Sin compromiso

Automatización: pipelines, publicación programada, reportes auto.
Solo entra si F4/F5 producen procesos repetibles.

---

## F3+ · MANOS EN EL PC — 🟢 Búsqueda + guardián operativos

### Búsqueda web (`atlas_search.py`, MCP `atlas-search`)

- `web_search(query, max_results)` → cadena de respaldo: **DuckDuckGo (`ddgs`)
  → SearXNG → DuckDuckGo HTML** (fallback duro).
- `web_research(topic, depth=1)` → búsqueda, lectura de top-5 fuentes, extracción
  de hechos, preguntas de seguimiento (depth>1), informe sintetizado **guardado
  como nota Obsidian `type: research`** en la bóveda, devuelve resumen + ruta.
- Config: `memory_data/state/search.json` (`searxng_url` vacío = solo ddgs).

### Modo guardián (`atlas_guardian.py`, MCP `atlas-guardian`)

- Niveles: `relax` (todo permitido) / `guard` (default, lista blanca + preguntas)
  / `strict` (bloquea `run_script`, `process_kill`, `registry_write`).
- `guardian_check(operation, params)` → `{allowed, reason, requires_confirmation}`.
- `guardian_set_level(...)`, `guardian_add/remove_whitelist`,
  `guardian_add_allowed_dir`, `guardian_get_config`.
- Intentos bloqueados → evento `guard_block` en la DB (auditable).
- Config: `memory_data/state/guardian.json`.

### Integración windows server

- `mcp_windows_server.py` (repo hermano `E:\MCP\mcp-windows-ai`) consulta el
  guardián ANTES de `run_command`, `run_script`, `process_start`,
  `process_kill` y `file_delete`. Si la operación está bloqueada devuelve
  `{"error": "BLOQUEADO por atlas-guardian", "guard_block": true, ...}`.
- Sin config del guardián → NO bloquea (modo abierto).

### Pendientes

- [ ] Deshabilitar MCP `playwright`/`ollama` en opencode.jsonc si ensucian el chat (playwright-visual cubre el navegador).
- [x] ~~Dashboard: conectar `dashboard.html` a datos reales~~ → HECHO: `atlas_web_server.py:4100` sirve dashboard + /api reales (events, top-apps, foco, health, orchestrator, modelo). Autostart vía tarea `AtlasWeb`.

---

## Comandos útiles

| Comando | Qué hace |
|---|---|
| `python mcp_memory_server.py --cli health` | Diagnóstico completo (DB, daemon, inbox) |
| `python mcp_memory_server.py --cli backup` | Backup manual (zip vault+db) |
| `python mcp_memory_server.py --cli restore` | Listar backups disponibles |
| `python mcp_memory_server.py --cli restore --backup-file <zip>` | Restaurar desde backup |
| `python mcp_memory_server.py --cli gc` | Limpiar eventos >90 días |
| `python mcp_memory_server.py --cli secret_rotation --note "..."` | Registrar rotación de secretos (calendario 90 días) |
| `python atlas_chat.py` | Abrir chat flotante (F2) |
| `python atlas_activity.py` | Daemon + bandeja (F2) |
| `python atlas_activity.py --no-tray` | Daemon sin bandeja (servidor) |
| `python atlas_activity.py --interval 5` | Capturar cada 5s |
| `python atlas_search.py` | Servidor MCP de búsqueda (si no se lanza via opencode) |
| `python atlas_guardian.py` | Servidor MCP del guardián |
| `python atlas_web_server.py --port 4100` | Dashboard real: sirve dashboard.html + /api/* (overview, top-apps, foco, health, orchestrator, modelo). Autostart: tarea AtlasWeb |
| `python atlas_health.py --http 4102` | HTTP server de salud/semáforo (GET /health) |
| `python atlas_health.py --cli` | Chequeo completo del sistema (green/yellow/red) |
| `python atlas_foco.py --cli daily` | Resumen de foco del día |
| `python atlas_foco.py --cli backfill --force` | Reclasifica eventos (tras cambiar reglas) |
| `powershell -ExecutionPolicy Bypass -File check.ps1` | Diagnóstico completo del ecosistema |
| `powershell -ExecutionPolicy Bypass -File setup.ps1` | Bootstrap en PC nuevo |
| `powershell -ExecutionPolicy Bypass -File setup.ps1 -InstallF2` | Bootstrap + autostart chat |

---

## Tareas de Windows (Task Scheduler)

| Tarea | Trigger | Qué hace |
|---|---|---|
| `AtlasChat` | ONLOGON | Abre chat flotante (via `start_atlas_chat.vbs`) |
| `AtlasBackup` | DIARIO 03:00 | Backup zip (via `start_atlas_backup.vbs`) |
| `AtlasActivity` | ONLOGON | Daemon de actividad + bandeja (restart on failure) |

---

## Decisiones clave

1. **F1 nace "final":** schema, bóveda, permisos e identidad no se replantean al llegar a F5.
2. **Cada integración externa** = adaptador reemplazable, nunca lógica en el núcleo.
3. **Graphify siempre opcional** — el sistema funciona sin él.
4. **Lo que no está en la bóveda no existe** — toda decisión que Atlas recuerde pasa por Obsidian.
5. **F6 solo existe si F4/F5 demuestran procesos repetibles.**
6. **Mission Control** (`E:\PROYECTOS\mission_control`) es el cimiento de F4 (dashboard financiero).
7. **MCP consolidados** — mcp_windows_server.py, mcp_corel_server.py, mcp_playwright_visual_server.py ahora viven en `E:\Agente_IA\mcp_windows\` (ya no dependen del repo hermano).

---

## Deudas técnicas / pendientes

- [ ] Git remote: configurar `origin` cuando se decida (gh sin auth aún).
- [ ] Dashboard: conectar `dashboard.html` a datos reales de events (hoy es mock).
- [ ] Daemon: agregar clasificación automática de apps (categoría) → input de F3.
- [ ] Notificaciones: avisos del sistema (precursor de F3).

---

## Endurecimiento de producción (6 puntos)

| # | Mejora | Implementación | Estado |
|---|---|---|---|
| 1 | Logs estructurados | `atlas_log.py` (JSON: ts/level/source/request_id/error). `atlas_chat.py` y `atlas_activity.py` loguean JSON en `logs/` | 🟢 |
| 2 | Monitoreo de errores | `atlas_monitor.py` → `logs/errors.jsonl` + `state/errors.db` con frecuencia; visible en `memory_health` (`errors_24h`) | 🟢 |
| 3 | Rate limiting | `RateLimiter` en `atlas_monitor.py`; daemon limita a 6 eventos/min para no inundar inbox | 🟢 |
| 4 | Health check | `memory_health` verifica DB, daemon, inbox, errores y rotación de secretos | 🟢 |
| 5 | Plan de rollback | Git tag `stable-f1f2` (punto estable) + backups diarios + restore (`--cli restore`). Ver abajo | 🟢 |
| 6 | Rotación de secretos | Calendario 90 días en `state/secret_rotation.json`; visible en `memory_health`; registrar con `--cli secret_rotation --note "..."` | 🟢 |

**Plan de rollback (< 5 min):**
1. `git stash` (o commit del trabajo en curso) para limpiar el working tree.
2. `git checkout stable-f1f2` — vuelve al punto estable F1+F2.
3. Si además los datos están corruptos: `python mcp_memory_server.py --cli restore --backup-file memory_data\backup\atlas_*.zip`.
4. `python mcp_memory_server.py --cli health` — verificar que todo esté OK.
5. Bonus (futuro): feature flags vía `memory_pref_set` para desactivar componentes sin deploy.

**Rotación de secretos:**
- Los secretos de Atlas viven FUERA del repo: `~/.omniroute/.env`, `opencode.jsonc` local, etc.
- `memory_health` avisa cuando `days_remaining <= 0`.
- Registrar cada rotación: `python mcp_memory_server.py --cli secret_rotation --note "rotada API key X"`.

---

## Documentación

- [`docs/PUESTA_EN_MARCHA.md`](docs/PUESTA_EN_MARCHA.md) — paso a paso en PC nuevo
- [`docs/CLONAR_EN_OTRA_PC.md`](docs/CLONAR_EN_OTRA_PC.md) — clonar repo en otra PC (100% funcional)
- [`docs/ARQUITECTURA.md`](docs/ARQUITECTURA.md) — componentes y flujo de memoria
- [`docs/CONFIG_OPCODE.md`](docs/CONFIG_OPCODE.md) — cómo cablear opencode.jsonc
- [`docs/QUE_NO_HACER.md`](docs/QUE_NO_HACER.md) — errores prohibidos
- [`docs/TROUBLESHOOTING.md`](docs/TROUBLESHOOTING.md) — fallos comunes
- [`roadmap.html`](roadmap.html) — fases F1–F6

---

## Seguridad

- **Nunca** se versionan secretos: `.env`, API keys, tokens, passwords.
- El server **redacta** secretos al escribir notas (`sk-...`, `token=`, etc.).
- `%APPDATA%\omniroute\.env` (si usas omniroute) vive **fuera** del repo.
- `memory.db` es derivado del vault: no se versiona, se regenera solo.
- `memory_data/backup/` es gitignored pero viaja con el repo local.

---

Atlas · HANDOFF · E:\Agente_IA\HANDOFF.md
