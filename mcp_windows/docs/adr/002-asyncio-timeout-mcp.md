# ADR-002: `asyncio.timeout()` en lugar de `asyncio.wait_for()` para conexiones MCP

- **Fecha:** 2026-07-28
- **Estado:** Aceptada

## Contexto
El `stdio_client` del SDK MCP usa *cancel scopes* de anyio que **deben entrar y salir en la misma tarea asyncio**. `asyncio.wait_for()` envuelve la corrutina en una **tarea nueva**, por lo que `__aenter__()` y `__aexit__()` corrían en tareas distintas y se producía:

```
RuntimeError: Attempted to exit cancel scope in a different task than it was entered in
```

Además, cuando un servidor fallaba al iniciar, el contexto quedaba suspendido y el garbage collector lo cerraba en otra tarea ("Task exception was never retrieved").

## Decisión
1. Usar `async with asyncio.timeout(30)` (no crea tarea nueva; Python ≥3.11) alrededor de `__aenter__()`.
2. Si la inicialización falla tras entrar al contexto stdio, llamar a `__aexit__()` **en la misma tarea** antes de propagar el error.
3. En `stop()`/`stop_all()` capturar `BaseException` (el cierre puede propagar `CancelledError`, que no hereda de `Exception`).

## Consecuencias
- ✅ Elimina el crash y los warnings de tareas huérfanas.
- ⚠️ Restricción: requiere Python ≥ 3.11 (el venv hermes-agent usa 3.11.15 ✔).
