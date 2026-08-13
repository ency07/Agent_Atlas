# PUESTA EN MARCHA — Atlas en un PC nuevo

Guía completa para pasar del clon al sistema funcionando. Si algo falla,
revisa [TROUBLESHOOTING.md](TROUBLESHOOTING.md).

## 0. Prerrequisitos

Instala en el PC nuevo (si no los tienes):

- **Node.js >= 20** ? https://nodejs.org (instala `npm` incluido).
- **Python >= 3.11** ? https://python.org (marca "Add to PATH").
- **Git** ? https://git-scm.com (o `winget install Git.Git`).
- (Opcional) **WebView2 runtime** — casi siempre ya viene en Windows 10/11.
  Se necesita para el chat flotante (F2, `pywebview`).

Verifica en una terminal:

```powershell
node --version
python --version
git --version
```

## 1. Clonar

```powershell
git clone <URL-DEL-REPO> Atlas
cd Atlas
```

> La memoria viaja en `memory_data/vault/`. Al clonar ya tienes el cerebro.

## 2. Bootstrap automático

```powershell
powershell -ExecutionPolicy Bypass -File .\setup.ps1
```

Lo que hace:

1. Verifica `node` y `python`.
2. Instala `opencode-ai` global (`npm install -g opencode-ai`) si falta.
3. Crea `.venv` y instala `requirements.txt` (`mcp`, `mcp-server-git`,
   `pywebview`, `playwright`).
4. Genera `%USERPROFILE%\.config\opencode\opencode.jsonc` resolviendo rutas
   desde `templates/opencode.jsonc.example`.
5. Copia la skill `memory` a `%USERPROFILE%\.config\opencode\skills\memory\`.
6. Corre `check.ps1`.

> Si no detecta el repo `mcp-windows-ai`, los MCP corel/windows/playwright-visual
> quedan **deshabilitados** en la config (setup.ps1 los quita de la generada).

## 3. Proveedor de modelos

Atlas necesita un proveedor para responder. Dos caminos:

### A. omniroute (el original de este PC)

```powershell
npm install -g omniroute
omniroute serve        # o como tengas configurado tu servidor local
```

- Config y secretos viven en `%APPDATA%\omniroute\` (fuera del repo).
- El proveedor se llama `omniroute` con `baseURL http://localhost:20128/v1`.
- La API key se pasa por variable de entorno `OMNIROUTE_API_KEY`
  (ver `opencode.json` global de opencode).

### B. Ollama local (más simple, sin claves)

```powershell
winget install Ollama.Ollama
ollama pull phi4-mini
```

El `opencode.jsonc` generado ya declara el proveedor `ollama` y el modelo
por defecto `ollama/phi4-mini`.

## 4. Primer arranque

Abre opencode en cualquier carpeta:

```powershell
opencode
```

La skill `memory` carga automáticamente: recupera sesiones huérfanas, ingesta
eventos y muestra el contexto del proyecto. Prueba:

```
dime donde quedamos
```

## 5. Verificación manual

```powershell
# diagnóstico completo
.\check.ps1

# health del server de memoria
python .\mcp_memory_server.py --cli health

# lista de proyectos con memoria
python .\mcp_memory_server.py --cli projects
```

## 6. Chat flotante (F2)

El chat flotante es una ventana frameless siempre-al-frente que apunta al
chat web de `opencode serve` (headless). La memoria de Atlas funciona ahí igual
que en la terminal.

### Arranque manual

```powershell
python .\atlas_chat.py                 # server + ventana flotante
python .\atlas_chat.py --server-only   # solo el server (sin ventana)
```

- `pywebview` (WebView2) ya lo instala `setup.ps1`.
- El modelo por defecto del chat es `omniroute/auto/best-chat` (cambiable con
  `--model` o env `ATLAS_CHAT_MODEL`).
- El server arranca en `127.0.0.1:4096`. Si ya corre, la ventana se reutiliza.
- El log está en `atlas_chat.log` (junto al proyecto).

### Autostart al iniciar Windows

Registra la tarea `AtlasChat` (Task Scheduler, al iniciar sesión, oculta):

```powershell
powershell -ExecutionPolicy Bypass -File .\setup.ps1 -InstallF2
```

O manualmente (si prefieres no correr todo el setup):

```powershell
schtasks /Create /TN "AtlasChat" /TR "wscript.exe `"$PWD\start_atlas_chat.vbs`"" /SC ONLOGON /F
```

Para desinstalar el autostart:

```powershell
schtasks /Delete /TN "AtlasChat" /F
```

## Checklist final

- [ ] `setup.ps1` termina sin errores
- [ ] `check.ps1` imprime "TODO OK"
- [ ] `opencode` responde con memoria ("dime donde quedamos")
- [ ] `python mcp_memory_server.py --cli health` ? `"status": "ok"`
