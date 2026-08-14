---
id: 20260813-150027-consolidaci-n-mcp-en-repo-portabilidad-c
type: decision
project: global
tags: [portabilidad,mcp,consolidacion]
created: 2026-08-13T20:00:27+00:00
source: opencode
status: active
links:
---

Se movieron los servers MCP de Windows/CorelDRAW/Playwright-visual desde el repo hermano E:\MCP\mcp-windows-ai hacia E:\Agente_IA\mcp_windows\ (completo: servers + docs + tests + examples + requirements).

- setup.ps1: ahora busca mcp_windows/ primero (legado solo de respaldo)
- check.ps1: sección [MCP windows consolidado] valida la ruta nueva en config
- Config local de opencode.jsonc ya apunta a E:\Agente_IA\mcp_windows\
- Check.ps1 verde: TODO OK

Objetivo logrado: repo único → portabilidad "PC nuevo en 15 min".

Siguiente pendiente priorizado: Dashboard con datos reales (conectar HTTP servers 4101 foco / 4102 health / 4103 orchestrator). Luego F4 DINERO.
