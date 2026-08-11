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
