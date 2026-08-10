# QUE NO HACER — Errores prohibidos en Atlas

Reglas que evitan romper el sistema o filtrar datos. **Leer antes de tocar nada.**

## Secretos y datos sensibles

1. **Nunca versiones secretos.** `.env`, API keys, tokens, passwords, claves de
   trading/bancos: quedan fuera del repo. `.gitignore` ya excluye `.env*`
   (salvo `.env.example`).
2. **`%APPDATA%\omniroute\.env`** contiene las claves reales de omniroute.
   Vive fuera del repo y NO se copia ni se commitea.
3. **No menciones secretos en las notas.** El server redacta `sk-...`,
   `token=...`, passwords, pero la regla es: ni en notas ni en chat.
4. **No subas el repo a GitHub sin revisar**: `git status` antes de cada push,
   y `git log --oneline` para confirmar que ningún commit trae claves.

## Estado derivado

5. **No versiones `memory_data/state/`** (memory.db, WAL, índices). Es
   derivado del vault; se regenera solo. Ya está en `.gitignore`.
6. **No versiones `memory_data/inbox/`.** Es cola temporal de eventos.
7. **No edites `graph.json` a mano.** El grafo se deriva de frontmatter +
   wikilinks. Para reconstruirlo: `memory_graph_rebuild`.

## El server de memoria

8. **No corras `mcp_memory_server.py` sin el paquete `mcp` instalado** en el
   Python que lo ejecuta (usa `FastMCP`). El venv correcto lo crea `setup.ps1`.
9. **No cambies `MEMORY_ROOT` a una ruta compartida o con espacios raros** sin
   probar; el server valida que los proyectos queden dentro del vault.
10. **No elimines `memory_data/vault/`.** Es la memoria. Si borras algo,
    borra en la bóveda, no en SQLite (el índice se reindexa).

## Rutas y portabilidad

11. **No hardcodees rutas de tu PC en archivos que se versionan.** Usa los
    placeholders `%%PYTHON_BIN%%`, `%%PROJECT_ROOT%%`, `%%MCP_WINDOWS_AI%%`
    de `templates/`. La config generada (`opencode.jsonc`) NO se versiona: se
    regenera con `setup.ps1`.
12. **No asumas puertos fijos.** El proveedor de modelos (omniroute) vive en
    `localhost:20128` en este PC; en otro puede ser distinto o usar Ollama.

## Flujo de trabajo

13. **No cierres la terminal de opencode sin cerrar la sesión** (o sin
    `/guardar`): quedan sesiones huérfanas (se recuperan al reiniciar, pero
    conviene evitarlo).
14. **No inicies `memory_init` a la ligera** sobre un proyecto ya existente:
    comprueba primero `memory_summary` / `memory_projects`.
15. **No mezcles la memoria de varios proyectos en una sola nota.** Una nota =
    un proyecto (`project` en el frontmatter). Si es global, `project: global`.

## Reglas de oro (de la skill memory)

- Lo que no se guarda, no existe → toda decisión relevante se registra.
- `MEMORY.md` es solo un índice → el detalle va en notas enlazadas.
- El grafo es derivado → no se edita a mano.
- Atlas es configurable (`global/preferences/identity.md`) → nunca quemes su
  nombre/tono en código.
