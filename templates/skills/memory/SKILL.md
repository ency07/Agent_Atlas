---
name: memory
description: "Memoria persistente de Atlas (MCP memory server): carga contexto al iniciar, guarda decisiones/hechos/preferencias/sesiones, cierra sesiones y consulta el grafo de conocimiento. Usar SIEMPRE al inicio y al final de cada sesion de trabajo, y ante peticiones que mencionen 'recuerda', 'que hice', 'proyecto anterior', o cuando haya decisiones que preservar."
---

# Memoria de Atlas

Atlas tiene memoria persistente via el servidor MCP `memory`
(<PROJECT_ROOT>\mcp_memory_server.py, donde <PROJECT_ROOT> es la raiz del
proyecto clonado — normalmente donde se clono este repo).
El cerebro vive en una boveda Obsidian (archivos .md con frontmatter + wikilinks)
con un indice SQLite y un grafo de conocimiento derivado.

> **Una sola raiz:** la carpeta del repo clonado (server + memory_data + roadmap.html).
> El proyecto se detecta automaticamente por la carpeta donde se abre opencode
> (cwd). Abrir opencode desde cualquier carpeta = memoria de ese proyecto +
> memoria global. Todo en un mismo lugar.

## Reglas de oro

1. **Lo que no se guarda, no existe.** Toda decision, hecho, preferencia o sesion
   relevante DEBE registrarse en la boveda.
2. **MEMORY.md es solo un indice.** El detalle va en notas enlazadas, nunca en un
   archivo gigante.
3. **Nunca guardes secretos.** Tokens (sk-...), passwords, api_keys, datos
   bancarios o de trading crudos: el server los redacta, pero no los menciones.
4. **El grafo es derivado** de frontmatter + wikilinks. No lo edites a mano.
5. **Atlas es configurable** (`global/preferences/identity.md`). Su nombre y tono
   pueden cambiar en cualquier momento; nunca los quemes en codigo.

## Al INICIAR una sesion de trabajo (automatico)

1. `memory_session_recover` — detecta sesiones huerfanas previas.
2. `memory_event_ingest` — drena commits/eventos pendientes del inbox.
3. `memory_summary` — carga contexto del proyecto actual (identidad, estado,
   sesiones, decisiones, pendientes, eventos). Usar budget ~2500.
4. Si el proyecto aun no existe en la boveda: `memory_init`.

### Si Atlas se abre FUERA de un proyecto (ej. Escritorio)

El proyecto detectado sera `global`. En ese caso:
1. Llama `memory_projects` — resumen de TODOS los proyectos con memoria.
2. Presentale al usuario la lista ordenada por actividad reciente:
   - Nombre del proyecto + objetivo.
   - Ultima sesion y resumen.
   - Cantidad de decisiones/notas.
3. Pregunta: "¿Sobre cual proyecto seguimos?".
4. Cuando el usuario elija un proyecto, trabaja SIEMPRE pasando
   `project="<nombre>"` en las tools de memoria (note_save, summary, etc.),
   porque el proyecto NO se detecta por el cwd en este caso.

Despues de cargar, dime brevemente que recuerdas y que hay pendiente.

## Durante la sesion

- **Decisiones** (`type=decision`): registra cada decision importante con contexto
  y alternativas. Incluye `links` a notas relacionadas.
- **Hechos** (`type=fact`): conocimiento concreto del proyecto que haya que recordar.
- **Preferencias** (`type=preference` o `memory_pref_set`): como le gusta trabajar
  al usuario (formato, tono, herramientas). Las preferencias globales van con
  `project=global`.
- **Tareas** (`type=task`): pendientes que el usuario mencione. Mantener `status=active`
  hasta resolver.
- **Riesgos** (`type=risk`): problemas potenciales detectados.
- **Lecciones** (`type=lesson`): aprendizaje que no debe repetirse.

Formato de nota:
```
memory_note_save title="..." body="..." type="decision|fact|preference|task|risk|lesson" tags="a,b" links="[[otra-nota]]"
```

## Comando manual: /guardar

Cuando el usuario escriba `/guardar`:
1. Resume la sesion en `memory_session_end` con un resumen conciso.
2. Confirma que quedo guardado y donde.

## Al CERRAR la sesion (automatico)

1. `memory_session_end` con un resumen que capture: que se hizo, decisiones,
   pendientes, y proximo paso. (Si el usuario se fue sin resumen, igual cierra
   la sesion marcandola como incompleta.)
2. `memory_event_ingest` para asegurar que no queden commits sin registrar.

## Consultar memoria

- **Contexto general:** `memory_summary` (project del cwd).
- **Buscar notas:** `memory_note_search query="..." scope="project|global|both"`.
- **Grafo:** `memory_graph_query node="concepto"` — muestra relaciones entre ideas.
- **Preferencias:** `memory_pref_get`.
- **Diagnostico:** `memory_health`.

## Permisos (recordatorio)

- Tools de memoria de bajo riesgo (save/search/session/summary): automaticas.
- `memory_graph_rebuild`, `memory_gc`, `memory_note_delete` (si existiera):
  preguntar antes de ejecutar.
- Acciones de Windows: siempre siguiendo los permisos de opencode (MEDIUM pide,
  HIGH/CRITICAL exige aprobacion).
