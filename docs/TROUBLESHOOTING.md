# TROUBLESHOOTING — Fallos comunes y solución

## El chat/opencode no responde

### "Error: model not found" o el modelo no existe
- El proveedor `omniroute` no está corriendo: verifica
  `Test-NetConnection 127.0.0.1 -Port 20128`. Si no responde, arranca omniroute
  (o usa Ollama local).
- Revisa qué modelo tienes seleccionado en `opencode.jsonc` (`"model"`).
- Lista modelos disponibles: `opencode models`.

### "port 20128" / proveedor caído
- Omnironte vive fuera del repo. Sus secretos están en `%APPDATA%\omniroute\.env`.
- Alternativa sin omniroute: usa `ollama/phi4-mini` (config ya generada).

## La memoria no carga

### opencode no muestra la skill memory
- Verifica que `%USERPROFILE%\.config\opencode\skills\memory\SKILL.md` exista
  (lo instala `setup.ps1`).
- En opencode pide explícitamente: "usa la skill memory".

### MCP memory falla al arrancar ("Connection closed")
- **Causa típica:** el venv tiene `mcp>=2.0.0`, que **eliminó** el módulo
  `mcp.server.fastmcp` que usan todos los servers de Atlas. Verifica con:
  `python -c "from mcp.server.fastmcp import FastMCP"`.
- Fix: `python -m pip install "mcp>=1.26.0,<2"` (ver `requirements.txt`, el pin
  `<2` es obligatorio).
- El Python del venv debe tener `mcp` instalado:
  `python -m pip install -r requirements.txt`.
- Comprueba el server standalone:
  `python .\mcp_memory_server.py --cli health` → debe dar `"status": "ok"`.
- Revisa que `opencode.jsonc` no tenga placeholders `%%` sin reemplazar
  (regenera con `setup.ps1` o a mano — ver `docs/CONFIG_OPCODE.md`).
- Diagnóstico del estado de todos los MCP: `opencode mcp list`.

### MCP corel-draw / windows / playwright-visual fallan
- Son del repo externo `mcp-windows-ai` y requieren sus deps (pyautogui,
  pywin32, psutil, pyperclip, Pillow, requests) en el Python que los ejecuta.
- Si no clonaste el repo, `setup.ps1` los deshabilita (correcto).
- Si los clonaste pero fallan: `python -m pip install -r requirements.txt` en el
  venv (ya las incluye).

### memory.db no existe / vacío
- Es derivado: se regenera solo al arrancar el MCP. Si está corrupto, borra
  `memory_data/state/` (el vault `.md` es la fuente; no se pierde nada).

## `check.ps1` marca fallos

| Falla | Causa | Fix |
|---|---|---|
| node/opencode no encontrado | No instalado o no en PATH | `npm install -g opencode-ai` |
| omniroute :20128 | Proveedor no arrancado | Arranca omniroute u usa Ollama |
| venv / paquete mcp | `setup.ps1` no corrió | Corre `setup.ps1` |
| pywebview ausente | No se instaló | `pip install pywebview` |
| config con `%%` | Placeholder sin resolver | Regenera config |

## Sesiones huérfanas / "donde quedamos" vacío

- Normal tras cerrar sin `/guardar`. Se recuperan al iniciar
  (`memory_session_recover`).
- Si quieres resetear un proyecto, no borres el vault: usa las tools de memoria.

## Problemas de Windows

### La ventana flotante (F2) no se ve / no es "siempre al frente"
- Requiere WebView2 runtime (casi siempre presente en Win10/11).
- `pywebview` usa el runtime de Edge. Si falla, reinstala WebView2 desde
  https://developer.microsoft.com/microsoft-edge/webview2/

### `setup.ps1` bloqueado por ExecutionPolicy
- Ejecuta: `powershell -ExecutionPolicy Bypass -File .\setup.ps1`

### Path demasiado largo / caracteres raros
- Evita clonar dentro de rutas con espacios o tildes (ej. `OneDrive\Documents`).

## Git

### "no such file" al clonar
- Asegúrate de que el remoto exista y tengas permiso. En este PC el remoto aún
  no está configurado (`git remote add origin <URL>`).

### Quiero ver qué hay en el repo antes de pushear
```powershell
git status
git log --oneline
git ls-files | Select-String -Pattern "\.env|\.key|password"
```
