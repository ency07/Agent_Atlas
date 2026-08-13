# ADR-001: Reemplazo del servidor fetch externo por tool integrada `web_fetch`

- **Fecha:** 2026-07-28
- **Estado:** Aceptada

## Contexto
El servidor MCP oficial de fetch tenía dos problemas:
1. El paquete npm `@modelcontextprotocol/server-fetch` **no existe** (error 404).
2. La alternativa PyPI `mcp-server-fetch` está **rota**: `ImportError: cannot import name 'McpError' from 'mcp.shared.exceptions'` con versiones nuevas del SDK MCP (paquete sin mantenimiento).

## Decisión
Implementar la lectura web como tool `web_fetch` **dentro de** `mcp_windows_server.py` usando `requests` + `markdownify` (con fallback a regex). Deshabilitar el servidor `fetch` en `SERVER_CONFIGS` (`enabled: False`).

## Consecuencias
- ✅ Menos procesos externos: arranque más rápido y un punto menos de fallo.
- ✅ Sin dependencia de npx/uvx para leer web.
- ⚠️ Deuda: si el paquete oficial se repara, se puede reevaluar volver al servidor dedicado.
- ⚠️ La conversión HTML→Markdown propia es más simple que la del servidor oficial (sin caché, sin respeto de robots.txt avanzado).
