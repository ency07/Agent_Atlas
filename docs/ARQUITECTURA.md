# ARQUITECTURA — Cómo funciona Atlas

## Vista general

```
+--------------------------------------------------------------+
|                          opencode CLI                        |
|  (se abre en cualquier carpeta; carga skill memory + MCP)     |
+-----------------------------+--------------------------------+
                              | MCP (stdin/stdout)
                              v
                  +---------------------------+
                  |  mcp_memory_server.py      |   <- NÚCLEO
                  |  (FastMCP, Python)         |
                  +-----------+---------------+
                              |
                +-------------+-------------+
                |             |             |
                v             v             v
        +-----------+   +-----------+   +-----------+
        | vault/    |   | state/    |   | inbox/    |
        | Obsidian  |   | memory.db |   | cola de   |
        | (.md)     |   | (SQLite)  |   | eventos   |
        | = VERDAD  |   | = índices |   | (hook)    |
        +-----------+   +-----------+   +-----------+
```

## Componentes

### 1. `mcp_memory_server.py` (núcleo)

Servidor MCP usando `FastMCP`. Expone tools: `memory_note_save`,
`memory_note_search`, `memory_summary`, `memory_session_start/end`,
`memory_event_ingest`, `memory_graph_query`, `memory_health`, etc.

- Lee la raíz de `MEMORY_ROOT` (env) o por defecto `./memory_data`.
- **Nunca escribe fuera** de `<MEMORY_ROOT>`. **Nunca ejecuta comandos.**
- Redacta secretos en toda escritura (`sk-...`, `token=`, passwords…).

### 2. Bóveda Obsidian (`memory_data/vault/`)

Fuente de verdad **humana**: notas `.md` con frontmatter YAML y wikilinks.

```
vault/
  global/                <- memoria global (identidad, preferencias)
    preferences/identity.md
  <proyecto>/            <- una carpeta por proyecto
    MEMORY.md            <- índice (siempre ligero)
    notes/ decisions/ facts/ sessions/ preferences/
    graph.json           <- grafo DERIVADO (no editar a mano)
```

- El grafo se **deriva** de frontmatter + wikilinks (se puede reconstruir con
  `memory_graph_rebuild`).
- El proyecto se detecta por el cwd de opencode. Fuera de proyecto → `global`.

### 3. SQLite (`memory_data/state/memory.db`)

Índice canónico y caché derivada: `events`, `sessions`, `notes_index`,
`preferences`, `graph_nodes/edges`, FTS5. **No se versiona**: se regenera
indexando el vault.

### 4. `inbox/` — cola de eventos

El hook de git post-commit escribe eventos crudos aquí (sin bloquear);
`memory_event_ingest` los drena a SQLite. No se versiona.

## Flujo de una sesión

1. Abres `opencode` → skill `memory` se carga.
2. `memory_session_recover` → detecta sesiones huérfanas.
3. `memory_event_ingest` → drena el inbox.
4. `memory_summary` → carga contexto del proyecto (identidad, decisiones,
   pendientes).
5. Durante la sesión, cada decisión/hecho/preferencia se guarda con
   `memory_note_save`.
6. Al cerrar: `memory_session_end` + `memory_event_ingest`.

## Config de opencode

`opencode` carga su config desde `%USERPROFILE%\.config\opencode\`:

- `opencode.json` — proveedores y modelos (en este PC: `omniroute`).
- `opencode.jsonc` — **MCP servers**, incluido `memory` (generado por
  `setup.ps1` desde `templates/`).
- `skills/` — la skill `memory` (instalada por `setup.ps1`).

En `opencode.jsonc` el server `memory` se declara como:

```jsonc
"memory": {
  "type": "local",
  "command": ["<PYTHON_BIN>", "<ROOT>\\mcp_memory_server.py"],
  "environment": { "MEMORY_ROOT": "<ROOT>\\memory_data" }
}
```

## Roadmap (fases)

Ver [roadmap.html](../roadmap.html). Resumen:

- **F1 · Memory Core** — este repo (estable).
- **F2 · Activity Tracker + Atlas UI** — chat flotante vía `opencode serve`
  (web → API). Base instalada (`pywebview`, `serve` headless OK).
- **F3 · Anti-distracción** — clasificación de apps.
- **F4 · Money/Content Engines** — métricas $ (requiere alimentar datos).
- **F5 · Trading Tutor** — análisis de trades (requiere export de TradingView).
