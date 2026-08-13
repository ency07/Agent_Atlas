# ADR-003: Sistema de seguridad por niveles de riesgo + listas blancas

- **Fecha:** 2026-07-28
- **Estado:** Aceptada

## Contexto
El sistema original tenía una lista plana `DESTRUCTIVE_TOOLS`: todo pedía la misma aprobación, lo que hacía tedioso el uso diario y no distinguía entre "leer un archivo" y "borrar una carpeta". Además, la IA no conocía las rutas reales del PC y alucinaba rutas (`C:\Users\user`) y código Python en lugar de llamar herramientas.

## Decisión
1. Clasificar cada tool en 4 niveles: `LOW` (auto), `MEDIUM` (Enter), `HIGH` (`y`), `CRITICAL` (escribir `CONFIRMAR`).
2. Whitelists de rutas (`Documents`, `Desktop`, `Downloads`...) y procesos seguros que auto-aprueban riesgo MEDIO.
3. `build_system_prompt()` inyecta las rutas reales del PC en el prompt del sistema.
4. Regla anti-alucinación en el prompt + feedback explícito cuando una tool falla ("corrige y reintenta").

## Consecuencias
- ✅ Menos fricción en operaciones seguras; fricción máxima solo en destructivas.
- ⚠️ Deuda: las whitelists están hardcodeadas en `mcp_ollama_client.py`. Pendiente moverlas a `mcp-servers.config.json` para configuración sin tocar código.
