# HANDOFF — Atlas

> Documento de estado del proyecto. Léelo primero si retomas el trabajo.

**Última actualización:** 11 de agosto de 2026

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

### F3 · FOCO — ⚪ No iniciada

Anti-distracción: clasificación monetizable/distracción, avisos, modos de disciplina.
Requiere: eventos continuos de actividad (F2 listo).

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

## Comandos útiles

| Comando | Qué hace |
|---|---|
| `python mcp_memory_server.py --cli health` | Diagnóstico completo (DB, daemon, inbox) |
| `python mcp_memory_server.py --cli backup` | Backup manual (zip vault+db) |
| `python mcp_memory_server.py --cli restore` | Listar backups disponibles |
| `python mcp_memory_server.py --cli restore --backup-file <zip>` | Restaurar desde backup |
| `python mcp_memory_server.py --cli gc` | Limpiar eventos >90 días |
| `python atlas_chat.py` | Abrir chat flotante (F2) |
| `python atlas_activity.py` | Daemon + bandeja (F2) |
| `python atlas_activity.py --no-tray` | Daemon sin bandeja (servidor) |
| `python atlas_activity.py --interval 5` | Capturar cada 5s |
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

---

## Deudas técnicas / pendientes

- [ ] Git remote: configurar `origin` cuando se decida (gh sin auth aún).
- [ ] Dashboard: conectar `dashboard.html` a datos reales de events (hoy es mock).
- [ ] Daemon: agregar clasificación automática de apps (categoría) → input de F3.
- [ ] Notificaciones: avisos del sistema (precursor de F3).

---

## Documentación

- [`docs/PUESTA_EN_MARCHA.md`](docs/PUESTA_EN_MARCHA.md) — paso a paso en PC nuevo
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
