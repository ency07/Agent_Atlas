# Atlas Orquestador — Selección de modelo por tarea

Usa el módulo MCP **`atlas_orchestrator`** (7 tools) que detecta proveedores
ACTIVOS en vivo y decide el mejor modelo **sin falsos positivos**.

## Tools disponibles

| Tool | Para qué |
|---|---|
| `orchestrator_available` | Proveedores activos + modelos usables AHORA |
| `orchestrator_analyze(task)` | Clasifica la tarea y sugiere el mejor modelo entre activos |
| `orchestrator_route(task)` | analyze + registra la decisión en routing_log.json |
| `orchestrator_report` | Historial de routing + salud de providers |
| `orchestrator_provider_health` | Fallos consecutivos, cooldown, último error por provider |
| `orchestrator_register_error(provider, error)` | Registra un fallo real (degradación) |
| `orchestrator_register_success(provider)` | Resetea fallos tras éxito |

## Cómo funciona (sin falsos positivos)

```
1. atlas_orchestrator detecta providers por PUERTO (no asume nada):
     omniroute :20128 · 9router :4000 · ollama :11434
2. Solo sugiere modelos cuyo provider responde y NO está en cooldown.
3. Si omniroute está caído pero Ollama responde → usa Ollama, nunca dice "GPT" sin base.
```

## Reglas

### 1. REVISIÓN VISUAL = NUNCA con vision=false
- Antes de procesar imágenes: llama `orchestrator_analyze(tarea)`.
- Si `decision.action == "block_and_advise"` → **no ejecutar**: avisa al usuario
  que ningún modelo activo tiene visión y sugiere levantar el provider adecuado.
- Si `vision_supported == false` → ofrece alternativas deterministas:
  `pw_visual_audit`, `pw_computed_style`, `pw_diff` (no requieren que el modelo "vea").

### 2. Confirmar antes de suponer
- `orchestrator_available` siempre te dice la verdad actual. No recuerdes
  proveedores de sesiones anteriores — el estado puede cambiar.
- Si el resultado es `no_providers` → informa al usuario qué levantar
  (omniroute/ollama), no intentes usar modelos imaginarios.

### 3. Errores persistentes → circuit breaker
- Si una llamada al modelo falla: `orchestrator_register_error(provider, error)`.
- Tras 3 fallos consecutivos el provider entra en **cooldown 5 min** y se degrada
  automáticamente (deja de sugerirse).
- Tras un éxito: `orchestrator_register_success(provider)`.
- `orchestrator_provider_health` muestra el estado real antes de decidir.

### 4. Eficiencia de tokens
- Tareas triviales: NO consultes el orquestador, ejecuta directo.
- Tareas complejas: `orchestrator_analyze` primero, delega, verifica.

## Flujo recomendado

```
Tarea compleja?
├─ NO → ejecutar directo
└─ SÍ → orchestrator_analyze(task)
    ├─ proceed + modelo sugerido → ejecutar (y orchestrator_route si se quiere log)
    ├─ block_and_advise (vision) → avisar, no ejecutar a ciegas, ofrecer alternativas
    └─ no_providers → informar qué provider levantar
Si falla en runtime → orchestrator_register_error → seguir con plan B
```
