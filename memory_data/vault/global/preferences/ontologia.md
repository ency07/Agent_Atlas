---
type: preference
category: ontology
---
# Ontología Personal — Atlas

Mapeos de términos coloquiales a entidades reales del sistema.

## Aplicaciones
- **mi navegador** → `opera.exe` (o `chrome.exe` si Opera no está)
- **el editor** → `code.exe` (VS Code)
- **la app de diseño** → `coreldrw.exe` (CorelDRAW)
- **el terminal** → `wt.exe` (Windows Terminal) / `powershell.exe`
- **el chat** → ventana flotante Atlas (puerto 4096)
- **el panel** → dashboard web `http://127.0.0.1:4100`
- **el orquestador** → `atlas_orchestrator.py` (puerto 4103)
- **el guardián** → `atlas_guardian.py` (puerto 4098)

## Conceptos
- **mis modelos** → proveedores activos en `atlas_orchestrator` (omniroute, 9router, ollama)
- **mis capacidades** → `atlas_capabilities_real` (solo MCPs habilitados)
- **mi memoria** → `mcp_memory_server` (vault + SQLite)
- **mi foco** → `atlas_foco` (modo soft/strict/off)
- **mis backups** → `atlas_backup_encrypted` (age) + `mcp_memory_server backup` (zip)

## Métricas
- **mi productividad** → `atlas_foco daily_summary` (focus_pct)
- **mis fricciones** → `friction_log` + dashboard `/api/friction/weekly`
- **mis costos** → `atlas_metrics` (usage_log)

## Reglas de resolución
1. Si el usuario dice "mi X", buscar en esta tabla.
2. Si no existe, intentar inferir por similitud (fuzzy match) sobre claves.
3. Si sigue sin resolver, preguntar **una sola vez** (máx 1 pregunta) y guardar la decisión aquí.