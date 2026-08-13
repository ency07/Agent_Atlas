# CONFIG_OPCODE — Cómo cablear opencode.jsonc

El `setup.ps1` genera la config automáticamente. Este documento explica los
placeholders y qué hacer cuando hay que ajustarla a mano.

## Dónde vive

```
%USERPROFILE%\.config\opencode\
    opencode.json      <- proveedores y modelos (NO se genera en setup)
    opencode.jsonc     <- MCP servers (GENERADO por setup.ps1)
    skills\memory\     <- skill memory (instalada por setup.ps1)
```

## Placeholders de la plantilla

`templates/opencode.jsonc.example` usa estos tokens:

| Token | Qué es | Ejemplo |
|---|---|---|
| `%%PYTHON_BIN%%` | python.exe del venv | `D:\Dev\Atlas\.venv\Scripts\python.exe` |
| `%%PROJECT_ROOT%%` | raíz del repo Atlas | `D:\Dev\Atlas` |
| `%%MCP_WINDOWS_AI%%` | repo mcp-windows-ai (opcional) | `E:\Agente_IA\mcp_windows` |

En JSON las rutas van con doble barra: `D:\\Dev\\Atlas`. `setup.ps1` hace esa
sustitución automáticamente.

## Regenerar la config a mano

```powershell
$py = "$PWD\.venv\Scripts\python.exe"
$root = $PWD
$template = Get-Content ".\templates\opencode.jsonc.example" -Raw
$out = $template.Replace("%%PYTHON_BIN%%", $py.Replace("\","\\"))`
              .Replace("%%PROJECT_ROOT%%", $root.Replace("\","\\"))
Set-Content "$env:USERPROFILE\.config\opencode\opencode.jsonc" $out -Encoding UTF8
```

> Sustituir `%%MCP_WINDOWS_AI%%` solo si existe el repo hermano.

## MCP opcionales (windows / corel / playwright-visual)

Provienen del repo externo [`ency07/mcp-windows-ai`](https://github.com/ency07/mcp-windows-ai).
Si no los clonaste:

```powershell
git clone https://github.com/ency07/mcp-windows-ai E:\Agente_IA\mcp_windows
cd E:\Agente_IA\mcp_windows
pip install -r requirements.txt
```

Y reemplaza `%%MCP_WINDOWS_AI%%` en la config. Si no los usas, puedes borrar
esas entradas del `mcp` del jsonc para evitar errores al arrancar opencode.

## Modelos y proveedor

- **`opencode.json`** define `omniroute` (modelos `auto/*`) — ese archivo es de
  este PC y NO se genera. En otro PC:
  - Usa `omniroute` si lo instalas y configuras, o
  - Borra el provider y deja el `ollama` que ya viene en `opencode.jsonc`.
- El modelo por defecto del jsonc es `ollama/phi4-mini`. Para cambiarlo edita
  la clave `"model"`.

## Verificar

```powershell
opencode run "responde ok"
```

Si el server MCP falla al arrancar, revisa:

```powershell
.\check.ps1
python .\mcp_memory_server.py --cli health
```

El primer `opencode` tras editar la config puede tardar (levanta los MCP).
