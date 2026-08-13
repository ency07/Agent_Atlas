# Atlas Orquestador — Selección de modelo por tarea

Consulta **`memory_data/state/model_capabilities.json`** antes de ejecutar
cualquier tarea que pueda requerir una capacidad específica (visión, razonamiento
profundo, velocidad, contexto largo). Este skill evita que Atlas trabaje "a ciegas".

## Cuándo usar este skill (SIEMPRE que el task sea complejo)

Actívalo automáticamente ante tareas que encajen en los tipos de `task_to_model`:

| Señal en la tarea | Tipo | Modelo sugerido |
|---|---|---|
| "revisa esta imagen/screenshot/pantalla", "audita el UI", "mira el diseño", CorelDRAW | `revision_visual` | vision=true |
| "refactoriza", "debug", "implementa", "arregla bug" | `codigo_profundo` | best-coding |
| "arquitectura", "planifica", "decide entre X e Y" | `planificacion` | best-reasoning |
| "investiga", "web_research", "documenta" | `investigacion` | best-research |
| "resume", conversación casual | `resumen` | best-chat |
| consulta trivial, "traduce", "formatea" | `consulta_rapida` | best-fast |

## Reglas del orquestador

### 1. REVISIÓN VISUAL = NUNCA con vision=false

Si la tarea necesita **ver una imagen/screenshot** y el modelo activo tiene
`vision: false`:

1. **NO intentes procesar la imagen con ese modelo** — desperdicia tokens y da
   resultados imprecisos.
2. Avisa al usuario:
   > ⚠️ El modelo actual (X) no soporta visión. Para revisar esta imagen necesito
   > cambiar a un modelo con visión (ej: `omniroute/auto/best-vision`).
   > ¿Cambio de modelo? / ¿Quieres que verifique solo la estructura sin visión?
3. Si el usuario acepta, sugiere el modelo correcto de `task_to_model`.
4. Alternativa sin cambiar modelo: describe textualmente lo que ves con
   herramientas como `pw_computed_style`/`pw_visual_audit` (que NO requieren
   que el modelo "vea" — extraen estilos y lanzan alertas deterministas).

### 2. Carga el mapa de capacidades

- Lee `memory_data/state/model_capabilities.json` (o el path relativo al proyecto).
- Si el archivo no existe, regresa al comportamiento default (asume el modelo
  activo puede con todo, pero avisa en tareas visuales).

### 3. Delegación a subagentes según capacidad

Cuando uses la herramienta `task` (Task tool), elige el `subagent_type` acorde:
- Investigación/exploración de codebase → `explore` (rápido, económico)
- Tareas multi-paso de investigación web → `general`
- Revisión visual de UI → usa tools pw_* que no dependen de visión del modelo
  (pw_visual_audit, pw_computed_style, pw_diff) y luego interpreta los JSON.

### 4. Foco / eficiencia de tokens

- Tareas triviales: NO cargues skills pesados ni subagentes.
- Tareas complejas: planifica → delega → verifica, no repitas trabajo.

## Flujo

```
1. Recibir tarea
2. ¿Requiere capacidad específica? (vision / razonamiento / velocidad)
   ├─ NO → ejecutar normal con modelo actual
   └─ SÍ → consultar model_capabilities.json
       ├─ modelo activo SÍ la tiene → ejecutar
       └─ modelo activo NO la tiene → avisar + sugerir cambio (regla 1)
3. Reportar al usuario qué modelo se usó y por qué (opcional pero recomendado
   si hubo un cambio o un aviso de capacidad).
```
