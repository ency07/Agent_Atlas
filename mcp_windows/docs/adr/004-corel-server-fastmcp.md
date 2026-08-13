# ADR-004: Servidor CorelDRAW con FastMCP + verificación empírica de la API COM

- **Fecha:** 2026-07-28
- **Estado:** Implementada y verificada (tests/test_corel_server.py — 11 operaciones OK)

## Contexto
El plan original (`E:\Macros_Corel\COREL_MCP_PLAN.md`) proponía implementar el protocolo MCP **manualmente** con JSON-RPC sobre stdio y asumía constantes COM (ej: `cdrFilter=6` para PNG, `units=1` para mm).

La verificación empírica contra CorelDRAW v25 instalado demostró que esos valores eran **incorrectos**:
| Constante | Plan | Real (v25) |
|---|---|---|
| cdrPNG | 6 | **802** |
| cdrMillimeter | 1 | **3** |
| cdrRGBColorImage | — | **4** |

También se descubrió: `SetPageDimensions` no existe en v25 (se usa `Page.SetSize`), `Text.Range()` requiere parámetros (se usa `Text.Story`), y `ExportBitmap` falla por coercion de tipos con gencache (se usa `ExportEx` + `StructExportOptions`).

## Decisión
1. Implementar `mcp_corel_server.py` con **FastMCP** (mismo patrón que `mcp_windows_server.py`) en lugar del JSON-RPC manual del plan.
2. Toda constante/método COM se verifica empíricamente antes de escribir la tool.
3. Registrar el servidor en `MultiServerManager` como un servidor más.

## Consecuencias
- ✅ ~80% menos código que el plan original (FastMCP abstrae el protocolo).
- ✅ Consistencia con el servidor Windows existente.
- ✅ Late binding (Dispatch dinámico): gencache falla con coercion de tipos en `ExportBitmap`/`ExportEx`.
- ✅ Receta de exportación verificada: `ExportBitmap` con los 16 parámetros posicionales (los 2 objetos finales como `None`).
- ✅ `ActiveSelectionRange` pertenece a `Application`, no a `Document` (v25).
- ⚠️ Deuda: las macros POD Suite se invocan vía `GMSManager.RunMacro` sin paso de parámetros; muchas abren InputBox/MsgBox que el usuario completa manualmente.
