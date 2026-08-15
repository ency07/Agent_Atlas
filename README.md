# Atlas — Memoria persistente para agentes de IA

> Socio operativo con memoria. Sistema de memoria total + coprocesador monetario.
> Un solo repo, portable, para clonar en cualquier PC con Windows.

## Qué es

Atlas es un **servidor MCP de memoria persistente** que vive en una bóveda
Obsidian (notas `.md` con frontmatter + wikilinks) indexada en SQLite, con un
grafo de conocimiento derivado. Se conecta a `opencode` como MCP server llamado
`memory`.

Componentes:

| Archivo | Rol |
|---|---|
| `mcp_memory_server.py` | Servidor MCP de memoria (FastMCP). Núcleo. |
| `atlas_chat.py` | **Chat flotante (F2)**: `opencode serve` + ventana frameless. |
| `atlas_activity.py` | **Daemon de actividad (F2)**: captura ventana activa + bandeja. |
| `atlas_log.py` | Logs estructurados JSON (producción #1). |
| `atlas_monitor.py` | Monitoreo de errores + rate limiting (producción #2/#3). |
| `atlas_secret_reminder.py` | Recordatorio semanal de rotación de secretos (producción #6). |
| `atlas_search.py` | **Búsqueda web (F3+)**: DuckDuckGo → SearXNG → DDG HTML. |
| `atlas_guardian.py` | **Modo guardián**: restricciones configurables sobre acciones. |
| `foco_rules.py` | Clasificador de actividad monetizable/distracción (F3). |
| `atlas_foco.py` | **Foco (F3)**: métricas foco, modo disciplina, HTTP server para dashboard. |
| `atlas_web/api.js` | Wrapper fino UI↔opencode serve. |
| `atlas_web/dashboard.html` | Dashboard base de actividad. |
| `start_atlas_chat.vbs` | Autostart oculto del chat flotante (Task Scheduler). |
| `start_atlas_backup.vbs` | Backup diario oculto via Task Scheduler. |
| `hooks/post-commit` | Git hook portable → inbox/. |
| `memory_data/vault/` | Bóveda Obsidian — **la memoria viaja con el repo**. |
| `memory_data/state/` | SQLite + heartbeat + flags (NO se versiona). |
| `memory_data/backup/` | Backups zip (gitignored, retención 14 copias). |
| `HANDOFF.md` | Documento de estado del proyecto (léelo primero). |
| `roadmap.html` | Roadmap por fases (F1–F6) y trazabilidad. |
| `setup.ps1` | Bootstrap en un PC nuevo (venv, deps, config, hook, backup, daemon). |
| `check.ps1` | Diagnóstico del ecosistema. |
| `templates/` | Plantillas de config + skill memory (portables). |
| `docs/` | Guías: instalación, arquitectura, config, qué-no-hacer. |

## Requisitos

- Windows 10/11
- Node.js >= 20 (para opencode CLI)
- Python >= 3.11
- (Opcional) Proveedor de modelos. Este repo usa `omniroute`
  (`localhost:20128`) para los modelos `auto/*`, u `ollama` local.

## Instalación en un PC nuevo (resumen)

```powershell
# 1. clonar
git clone <tu-remoto> Atlas
cd Atlas

# 2. bootstrap automático
powershell -ExecutionPolicy Bypass -File setup.ps1

# 3. abrir opencode (cualquier carpeta)
opencode
```

`setup.ps1` hace: detecta node/python → instala `opencode-ai` (npm global) →
crea `.venv` e instala `requirements.txt` → genera
`%USERPROFILE%\.config\opencode\opencode.jsonc` desde la plantilla → instala la
skill `memory` → corre `check.ps1`.

Detalle completo: [`docs/PUESTA_EN_MARCHA.md`](docs/PUESTA_EN_MARCHA.md).

## Uso

La memoria se carga **automáticamente** al iniciar una sesión de opencode
(skill `memory`): recupera sesiones huérfanas, ingesta eventos pendientes y
carga el contexto del proyecto. Desde el escritorio (fuera de proyecto) muestra
la lista de proyectos y pregunta sobre cuál seguir.

Comandos útiles del server:

```powershell
python mcp_memory_server.py --cli health          # diagnóstico
python mcp_memory_server.py --cli init <proyecto> # crear proyecto
```

## Chat flotante (F2)

Ventana frameless siempre-al-frente que usa el chat web de `opencode serve`
con toda la memoria de Atlas:

```powershell
python atlas_chat.py                  # arrancar el chat flotante
python atlas_chat.py --server-only    # solo server (sin ventana)
```

Autostart al iniciar Windows:

```powershell
powershell -ExecutionPolicy Bypass -File setup.ps1 -InstallF2
schtasks /Delete /TN "AtlasChat" /F   # desinstalar autostart
```

El server vive en `127.0.0.1:4096`; log en `atlas_chat.log`. Detalle en
[`docs/PUESTA_EN_MARCHA.md`](docs/PUESTA_EN_MARCHA.md).

## Búsqueda web + investigación (F3+)

Atlas busca en internet sin API keys, con cadena de respaldo automática:

| Nivel | Proveedor |
|---|---|
| 1º | DuckDuckGo (`ddgs`, pip, open-source MIT) |
| 2º | SearXNG self-hosted (`state/search.json` → `searxng_url`) |
| 3º | DuckDuckGo HTML (fallback duro, sin lib) |

Herramientas MCP (server `atlas-search`):

- `web_search(query, max_results)` → resultados `[{title, url, snippet, source}]`
- `web_research(topic, depth=1)` → busca, lee las 5 fuentes más relevantes,
  extrae hechos, genera preguntas de seguimiento (depth>1), sintetiza informe
  y lo guarda como **nota Obsidian** (`type: research`) en la bóveda. Devuelve
  resumen + ruta de la nota + fuentes.

Config en `memory_data/state/search.json`:

```json
{ "searxng_url": "", "timeout_ddgs": 15, "timeout_searxng": 10, "max_results": 10 }
```

Para activar SearXNG: `"searxng_url": "http://localhost:8080"` (o levanta con
`docker run -p 8080:8080 searxng/searxng`). Si no está levantado, se salta
silenciosamente al siguiente proveedor.

## Modo guardián (F3+)

`atlas_guardian.py` (server MCP `atlas-guardian`) restringe las acciones de
Atlas sobre el PC. Niveles configurables en `memory_data/state/guardian.json`:

| Nivel | Comportamiento |
|---|---|
| `relax` | Todo permitido, todo se registra en logs. |
| `guard` (default) | Lista blanca de binarios; acciones sensibles → pregunta. |
| `strict` | Solo acciones de bajo riesgo; bloquea `run_script`/`process_kill`/`registry_write`. |

Qué restringe:
- `run_command` / `run_script`: lista blanca de binarios permitidos.
- `process_kill`: solo procesos de la lista blanca (guard pide confirmación).
- `file_delete`: solo dentro de carpetas permitidas (`allowed_dirs`).
- Toda acción bloqueada se registra como evento `guard_block` en la DB (auditable).

Herramientas MCP:
- `guardian_check(operation, params)` → `{allowed, reason, requires_confirmation}`
- `guardian_set_level("relax"|"guard"|"strict")`
- `guardian_get_config()` / `guardian_add_whitelist()` / `guardian_remove_whitelist()`
- `guardian_add_allowed_dir(path)`

## Foco · Anti-distracción (F3)

Atlas clasifica cada evento de actividad como **productivo** o **distracción**
y puede avisarte cuando pierdas el foco. Todo configurable sin tocar código.

### Clasificador

- `foco_rules.py` clasifica apps por categoría (dev, research, comms, social,
  game, other, exception) y marca si son monetizables.
- **Primero mira la title de la pestaña** (más preciso en navegadores) y luego
  la app. KeePassXC, etc. → exception (neutro).
- Reglas editables: `state/foco_rules.json` (plantilla en `templates/foco_rules.json.example`).

### Modos de disciplina

| Modo | Comportamiento |
|---|---|
| `off` | Solo clasifica y mide (sin avisos). |
| `soft` (default) | Clasifica + avisa si estás en distracción > 3min, presupuesto 3 avisos/día. |
| `strict` | Avisa más agresivo (> 1min) + registro de fuga en cada sesión. |

Cambiar modo: desde la bandeja de Atlas (`Modo foco`), por MCP (`foco_set_mode`)
o editando `state/foco_rules.json`.

### Dashboard de foco

Tarjeta "Foco hoy" en `atlas_web/dashboard.html` con:
- % productivo vs distracción
- Tiempo total productivo, distracción, neutro
- Top distracciones del día

Sirve desde `python atlas_foco.py --http 4101` (GET `/daily`).

### Herramientas MCP (`atlas-foco`)

- `foco_set_mode("off"|"soft"|"strict")` → cambia modo
- `foco_get_rules()` → reglas actuales
- `foco_daily_summary(date?)` → resumen del día (traspaso a F4)
- `foco_override(app, category)` → override manual de categoría
- `foco_backfill(force?)` → reclasifica eventos históricos

## Documentación

- [`docs/PUESTA_EN_MARCHA.md`](docs/PUESTA_EN_MARCHA.md) — paso a paso en PC nuevo
- [`docs/ARQUITECTURA.md`](docs/ARQUITECTURA.md) — componentes y flujo de memoria
- [`docs/CONFIG_OPCODE.md`](docs/CONFIG_OPCODE.md) — cómo cablear opencode.jsonc
- [`docs/QUE_NO_HACER.md`](docs/QUE_NO_HACER.md) — errores prohibidos
- [`docs/TROUBLESHOOTING.md`](docs/TROUBLESHOOTING.md) — fallos comunes
- [`roadmap.html`](roadmap.html) — fases F1–F5

## Seguridad

- **Nunca** se versionan secretos: `.env`, API keys, tokens, passwords.
- El server **redacta** secretos al escribir notas (`sk-...`, `token=`, etc.).
- `%APPDATA%\omniroute\.env` (si usas omniroute) vive **fuera** del repo.
- `memory.db` es derivado del vault: no se versiona, se regenera solo.

## Deuda registrada (DEBT)

| ID | Deuda | Responsable | Fecha | Riesgo | Mitigación |
|---|---|---|---|---|---|
| DEBT-001 | 2 runbooks verificados en bóveda (instalar extensión, exportar diseño) | Usuario | 2026-08-31 | MEDIO | Verificar próximos 2 runbooks reales con skill runbooks |
| DEBT-002 | 3 entregables calificados "profesional" → exemplars | Usuario | 2026-08-31 | MEDIO | Usuario califica entregables; se registran como exemplars |
| DEBT-003 | Prueba de crítico con trampa (entregable sembrado) | Usuario | 2026-08-31 | MEDIO | Ejecutar skill critico sobre un entregable con error sembrado |
| DEBT-004 | Launcher duplicado activity (mutex añadido; verificar en producción) | Atlas (código) | 2026-08-21 | BAJO | Mutex Windows añadido; verificar estabilidad tras 2 reboots reales |
| DEBT-005 | 3er reboot del chat para gate "3 reboots" | Entorno | 2026-08-21 | BAJO | Requerido reboot real adicional; BLOCKED_BY_ENVIRONMENT |
| DEBT-006 | win10toast no instalado (toast notification en supervisor) | Atlas | 2026-08-31 | BAJO | `pip install win10toast` si se necesita |
| DEBT-007 | Integrar controller C2 en supervisor COMPONENTS | Atlas (código) | 2026-08-14 | BAJO | ✅ **PAGADO**: entrada `controller` con `demand: True` (bajo demanda, no auto-reinicia, cooldown anti-spam) |

Gates humanos pendientes de C1 (ver `docs/verification/2026-08-14-cierre-f25-c1.md`).
