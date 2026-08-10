---
id: 20260810-portabilizar-atlas-clonable
type: decision
project: global
tags: [portabilidad, docs, git, setup]
created: 2026-08-10T02:15:00+00:00
source: opencode
status: active
---

Se portabilizo el ecosistema Atlas para poder clonarlo y ejecutarlo en cualquier PC nuevo.

## Que se hizo

- `git init` en E:\Agente_IA (rama main, 2 commits).
- `.gitignore`: se versiona `memory_data/vault/` (la memoria) pero NO `state/` ni `inbox/`.
- `setup.ps1`: bootstrap en PC nuevo (venv, deps, genera opencode.jsonc desde template, instala skill memory, corre check).
- `check.ps1`: diagnostico del ecosistema (fallback a python del PATH si no hay .venv).
- `templates/opencode.jsonc.example` con placeholders %%PYTHON_BIN%% / %%PROJECT_ROOT%% / %%MCP_WINDOWS_AI%%.
- `templates/skills/memory/SKILL.md`: skill portable (sin rutas absolutas).
- `docs/`: PUESTA_EN_MARCHA, ARQUITECTURA, CONFIG_OPCODE, QUE_NO_HACER, TROUBLESHOOTING.
- `requirements.txt`, `.env.example`, README.md.

## Decisiones clave

- La memoria (vault) viaja con el clon; el estado SQLite (memory.db) se regenera solo.
- Los secretos NO se versionan: omniroute .env vive en %APPDATA% y la API key va por env var.
- La config de opencode (opencode.jsonc) NO se versiona: se genera por setup.ps1 con rutas del PC destino.

## Estado

- setup.ps1 y check.ps1 probados en este PC: TODO OK.
- pywebview instalado (para F2 chat flotante).
- FIX MCP: setup.ps1 instalo mcp 2.0.0 (pip resolvio la mas nueva) que rompio
  FastMCP (elimino mcp.server.fastmcp). Todos los MCP Python caian
  ("Connection closed"). Se fijo mcp>=1.26.0,<2 en requirements.txt y se
  anadieron las deps de mcp-windows-ai. Ahora opencode mcp list = 7/7 connected.
  LECCION: nunca instalar mcp 2.x en este ecosistema.

## Pendiente

- Chat flotante (F2 Opcion A): web -> opencode serve + ventana frameless pywebview.
- Configurar remoto git cuando se decida (gh sin auth).
