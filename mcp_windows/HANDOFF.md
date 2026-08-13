# 🔄 HANDOFF — Contexto completo para Claude Code

> Fecha: 2026-07-29 (actualizado) · Sesión anterior: OpenCode (kimi-k3) · Sesión actual: Claude Code (Sonnet-5)
> **Estado: POD_Main.bas + POD_Export.bas INSTALADOS en CorelDRAW. Pruebas EN PROGRESO — capas OK ✅, exportación PNG aún FALLANDO ⚠️**

---

## 1. ✅ ESTADO ACTUAL (2026-07-29 22:40 — LISTO PARA PRODUCCIÓN)

**✅ COMPLETAMENTE FUNCIONAL:**
- ✅ VBE abre sin crashes (Alt+F11).
- ✅ Módulos `POD_Main.bas` y `POD_Export.bas` **importados y verificados** en GlobalMacros.
- ✅ Función `CrearEstructuraCapasEstandar()` crea 6 capas correctamente (BG, FX, DECO, ICON, TEXT_Secundario, TEXT_Principal).
- ✅ Test `TestPODSuite` **ejecuta exitosamente sin errores**.
- ✅ `ExportBitmap()` exporta correctamente a PNG en ambas plataformas:
  - Redbubble 4500x5400@300dpi → test_RB.png ✅
  - Spreadshirt 4000x4000@300dpi → test_SS.png ✅

**Log final (2026-07-29 22:40):**
```
TEST POD SUITE - 29/07/2026 10:40:36 p. m.
Documento: Sin título-1
Capas totales en pagina: 8
Export Redbubble 4500x5400@300: OK
Export Spreadshirt 4000x4000@300: OK
TEST FINALIZADO
```

**Hallazgo crítico (IMPORTANTE):**
⚠️ CorelDRAW **BLOQUEA operaciones COM de exportación mientras el VBE está abierto**. 
- ❌ NO ejecutar macros con F5 desde el VBE (falla con E_INVALID_ARG)
- ✅ Ejecutar SIEMPRE desde **Herramientas → Macros → Ejecutar Macro** (sin VBE activo) o `GMSManager.RunMacro()` desde Python

**Hechos técnicos redescubiertos hoy (para no re-adivinar):**
1. `Application.BeginCommandGroup()` / `EndCommandGroup()` NO existen → se quitaron (no necesarias).
2. `Layers.Add()` NO existe, ni con parámetro ni sin → usar `ActivePage.CreateLayer(nombre)` en su lugar. ✅ Verificado en Object Browser.
3. `ExportBitmap()` existe pero falla con parámetros posicionales numerados [1..16]. Firma real:
   ```
   Function ExportBitmap(FileName As String, Filter As cdrFilter, 
                         [Range=cdrCurrentPage], [ImageType=cdrRGBColorImage], 
                         [Width], [Height], [ResolutionX=72], [ResolutionY=72], 
                         [AntiAliasingType=cdrNormalAntiAliasing], [Dithered=False], 
                         [Transparent=False], [UseColorProfile=True], 
                         [MaintainLayers=False], [Compression=cdrCompressionNone], 
                         [PaletteOptions], [ExportArea]) As ExportFilter
   ```
   Intento actual: parámetros numéricos (802=cdrPNG, 1=cdrCurrentPage, 4=cdrRGBColorImage, etc.), todos 16 puestos. Falla sin claridad.

---

## 2. 📍 DÓNDE QUEDÉ (el siguiente paso exacto)

---

## 2. 📍 PRÓXIMOS PASOS (orden acordado)

### ⚡ INMEDIATO (hoy o mañana):
1. **✅ COMPLETADO:** Instalar + probar POD_Main y POD_Export.
   - Código arreglado: SetSize() calcula mm, Width/Height = 0 en ExportBitmap.
   - Test ejecutado desde Herramientas → Macros (NO desde VBE).
   - ✅ **LISTO PARA PRODUCCIÓN**.

2. **SIGUIENTE:** Reimplementar **POD_Color_v2.bas** (6 funciones, spec en DOCX):
   - `SwapDarkLight` — intercambiar colores oscuro/claro
   - `ColorClickSelect` — seleccionar por color
   - `ColorClickSwap` — intercambiar 2 colores seleccionados
   - `AjustarHSL` — diálogo HSL (Hue, Saturation, Lightness)
   - `GenerarPaleta` — generar paleta desde documento
   - `VerificarImpresion` — chequear CMYK/RGB compatibility

3. **DESPUÉS:** Reimplementar **POD_Tattoo.bas** (32 funciones complejas):
   - Distorsiones: `ApplyArch`, `Skew`, `Barrel`, `Flag`, `Fisheye`, `ZoneDeform` (usan `CreateEnvelope()`)
   - Detalles: strokes, divider lines, corner ornaments
   - Composición: `BuildS1Composition`, `GenerateDarkLightVersions`, `ExportAllPlatforms`

4. **Menor prioridad:** POD_Typo_v2, POD_Compo_v2, POD_Calendar (según specs en DOCX).

---

## 3. 📁 RUTAS CLAVE

| Qué | Ruta |
|---|---|
| **Proyecto MCP principal** | `E:\MCP\mcp-windows-ai\` |
| Servidor Windows (44 tools) | `E:\MCP\mcp-windows-ai\mcp_windows_server.py` |
| Servidor CorelDRAW (18 tools) | `E:\MCP\mcp-windows-ai\mcp_corel_server.py` |
| Gestor multi-servidor | `E:\MCP\mcp-windows-ai\mcp_multi_server.py` |
| Cliente propio (Ollama) | `E:\MCP\mcp-windows-ai\mcp_ollama_client.py` |
| Tests (todos pasan) | `E:\MCP\mcp-windows-ai\tests\` |
| ADRs | `E:\MCP\mcp-windows-ai\docs\adr\` |
| Guías | `E:\MCP\mcp-windows-ai\GUIA_USO.md`, `MODELOS.md`, `GOVERNANCE.md` |
| **Macros POD — código nuevo** | `E:\Macros_Corel\bas\POD_Main.bas`, `E:\Macros_Corel\bas\POD_Export.bas` |
| Macros POD — documentación | `E:\Macros_Corel\` (COREL_MCP_PLAN.md, PODSuite_Lista_Macros_Interface.txt, PODSuite_Informe_Macros.docx) |
| CorelDRAW instalado | `C:\Program Files\Corel\CorelDRAW Graphics Suite\25\` |
| GMS de fábrica | `C:\Program Files\Corel\CorelDRAW Graphics Suite\25\Draw\GMS\` (CalendarWizard, FileConverter, ConvertAllToCurves, ColorChartCreator) |
| **GMS del usuario (VACÍA — aquí van las macros)** | `C:\Users\Administrator\AppData\Roaming\Corel\CorelDRAW Graphics Suite 2024\Draw\GMS\` |
| **Python correcto (venv con TODAS las librerías)** | `C:\Users\Administrator\AppData\Local\hermes\hermes-agent\venv\Scripts\python.exe` |
| Scripts de instalación/test POD | `C:\Users\ADMINI~1\AppData\Local\Temp\opencode\install_pod.py` (y `install_pod2.py`, `corel_restart.py`, `open_vbe.py`, `open_vbe2.py`) |
| Cuarentena de archivos (limpieza disco) | `D:\_CUARENTENA\` |
| Config OpenCode | `C:\Users\Administrator\.config\opencode\opencode.jsonc` |
| Config Hermes | `C:\Users\Administrator\AppData\Local\hermes\config.yaml` |

---

## 4. 🔬 HECHOS TÉCNICOS VERIFICADOS (no re-verificar)

**CorelDRAW v25.0.0.230** (el registro lo llama "2024" pero es v25):
- Late binding obligatorio: `win32com.client.Dispatch("CorelDRAW.Application")` (gencache/EnsureDispatch falla con coercion de tipos).
- Constantes reales: `cdrMillimeter=3`, `cdrInch=1`, `cdrPNG=802`, `cdrJPEG=774`, `cdrRGBColorImage=4`, `cdrCMYKColorImage=5`, `cdrSelection=2`, `cdrCurrentPage=1`, `cdrNormalAntiAliasing=1`.
- Exportar PNG: `doc.ExportBitmap(path, 802, 1, 4, 0, 0, dpi, dpi, 1, False, transparent, False, False, 0, None, None)` → **los 16 parámetros posicionales son obligatorios** (los 2 últimos objetos = `None`), luego `flt.Finish()`. ✅ Verificado (PNG 300dpi generado).
- Texto: `shape.Text.Story.Font = "Impact"` (string), `.Size` (pt), `.Bold` (bool). ✅
- `SetPageDimensions` NO existe → usar `doc.ActivePage.SetSize(w, h)` tras `doc.Unit = 3`. ✅
- `ActiveSelectionRange` pertenece a `Application`, NO a `Document`. ✅
- `app.VBE` → **CRASH (ver §1)**. Todo lo demás del COM funciona.
- `GMSManager.RunMacro("GlobalMacros", "Modulo.Funcion")` disponible (no probado aún con macros reales).
- En VBA (spec del DOCX): exportar con `Set fi = ActiveDocument.Export(ruta, cdrPNG): fi.Width=N: fi.Height=N: fi.ResolutionX=300: fi.Finish`.

**Entorno Python:** el `python` del PATH es el venv hermes (Python 3.11.15). `pip` del sistema instala en Python 3.12 (¡otro!). Siempre usar el venv hermes para todo lo del proyecto.

---

## 4. ✅ TRABAJO COMPLETADO HOY (no rehacer)

### 4.1 Proyecto MCP Windows AI (`E:\MCP\mcp-windows-ai`)
- **80 tools activas**: windows-automation (44) + corel-draw (18) + filesystem (14) + memory (4).
- Tools de documentos: `docx_create`, `xlsx_create` (fórmulas reales), `pptx_create`, `pdf_create` (membrete) — todas probadas.
- Tools programas: `open_program`, `list_installed_programs`, `type_in_program`.
- `web_fetch` integrada (el servidor fetch oficial está roto: `mcp-server-fetch` incompatible con SDK MCP nuevo).
- Seguridad: 4 niveles de riesgo (LOW/MEDIUM/HIGH/CRITICAL) + whitelists + prompt dinámico con rutas reales del PC (anti-alucinación).
- Bugs corregidos: cancel scopes anyio (`asyncio.timeout` en vez de `wait_for`), fpdf2 `multi_cell` (`new_x="LMARGIN"`), encoding UTF-8 consola.
- **Git inicializado**: 10 commits, working tree limpio. Tests: `tests\test_documents.py`, `tests\test_multi_server.py`, `tests\test_corel_server.py` (todos en verde).

### 4.2 Limpieza de disco C: (12.9 GB → 51.5 GB libres, +38.6 GB)
- Punto de restauración creado (nombre: "Antes de limpieza MCP").
- Eliminados: Temp 4.9GB, npm-cache 5.65GB, ms-playwright 1.15GB, cachés pip/uv ~1.9GB, instaladores (Ollama/Docker×3/MiniMax) 3.5GB.
- A cuarentena `D:\_CUARENTENA\`: Photoshop zip 3.2GB, Ubuntu ISO 2.7GB, curso UI/UX 2.6GB, Macrium+WIN10 recovery 1.6GB.
- Desinstalados: MiniMax Code, Cursor, Antigravity, AnythingLLM (restos), Windows SDK completo (~3.5GB), Docker Desktop (3.4GB), PowerToys MSI viejo (conservado 0.85.1), Java 8 → **instalado Eclipse Temurin OpenJDK 21.0.11 LTS**.
- Conservados por decisión del usuario: CorelDRAW, Ollama, Hermes, OpenCode, Qwen, Comet, Git, Node, VS Code, Python, WSL, Traccar, Photoshop, Illustrator, Foxit, AOMEI.
- Borrados modelos Ollama: `qwen3:0.6b`, `gemma3:1b`. Quedan: `qwen2.5-coder:7b`, `phi4-mini`, `llama3.2:3b`, `qwen2.5:3b`, `qwen3:1.7b`.

### 4.3 Macros POD reimplementadas (código listo, FALTA instalar)
Fuente: spec en `PODSuite_Informe_Macros.docx` (reglas: ASCII puro, `Attribute VB_Name` primera línea, `Option Explicit`, UI solo InputBox/MsgBox, sin UserForms).

- **`E:\Macros_Corel\bas\POD_Main.bas`**: `AbrirLauncher` (menú 0-6), `ValidarDocumento`, `ObtenerCarpetaDoc`, `ObtenerNombreDoc`, `AsegurarCapa`, `AsegurarCarpeta`, `MathMax/Min/Clamp`, `ExportarPNG`, `CrearEstructuraCapasEstandar` (BG/FX/DECO/ICON/TEXT_Secundario/TEXT_Principal), `TestPODSuite` (test sin diálogos bloqueantes, escribe log).
- **`E:\Macros_Corel\bas\POD_Export.bas`**: Type `TPlataforma`, `ObtenerPlataformas` (6 plataformas: Redbubble 4500x5400, Spreadshirt 4000x4000, LaTostadora 4000x4000, Displate 4060x5740, AmazonMerch 4500x5400, Teepublic 4500x5400, todas @300dpi), `QuickExportPNG`, `EjecutarBatchExport` (subcarpetas por plataforma), `ConfigurarDocumentoPorPlataforma` (381x457mm para RB), `LimpiarPreprensa` (textos→curvas con contador).

---

## 5. 📋 TRABAJO PENDIENTE (orden acordado con el usuario)

### ⚡ INMEDIATO (hoy, 2026-07-29):
1. **🔧 Arreglar ExportBitmap en POD_Main.bas** (ver solución en §2):
   - Modificar `ExportarPNG()` para calcular mm desde px, hacer SetSize(mm, mm), pasar Width/Height como 0.
   - Re-importar POD_Main.bas en CorelDRAW.
   - Ejecutar test nuevamente (`TestPODSuite`, F5).
   - Verificar que `test_RB.png` y `test_SS.png` se crean en `C:\Users\Administrator\Desktop\POD_Test\`.

2. **✅ Instalar + probar POD_Main y POD_Export completamente** (casi listo, solo falta el arreglo de arriba).

### DESPUÉS (una vez ExportBitmap funcione):
3. **Test con modelo FREE** (petición explícita del usuario): probar flujo IA→MCP→Corel con modelo gratuito:
   - OpenCode Go: `glm-5.2`, `kimi-k2.5`, `minimax-m2.5` (provider `opencode-go` ya en opencode.jsonc + Hermes).
   - Ollama local: `phi4-mini` o `qwen2.5-coder:7b`.
   - Cliente: `python E:\MCP\mcp-windows-ai\mcp_ollama_client.py --model phi4-mini`

4. **Reimplementar módulos restantes** (spec DOCX, ASCII puro):
   - `POD_Color_v2.bas` (SwapDarkLight, ColorClickSelect, ColorClickSwap, AjustarHSL, GenerarPaleta, VerificarImpresion)
   - `POD_Tattoo.bas` (ApplyArch/Skew/Barrel/Flag/Fisheye/ZoneDeform, strokes, dividers, BuildS1Composition, GenerateDarkLightVersions, ExportAllPlatforms)
   - Después: POD_Typo_v2, POD_Compo_v2, POD_Calendar.

5. **Integrar servidores MCP nuevos:** GitHub (`@modelcontextprotocol/server-github`, token needed) + Everything Search (voidtools).

6. **Registro de macros en menú:** Herramientas → Macros + docker Ventana → Acopladores → Scripts.

---

## 6. ⚠️ ADVERTENCIAS CRÍTICAS PARA CLAUDE CODE

### CorelDRAW VBA:
- **VBA CorelDRAW ≠ VBA Office:** muchos métodos/propiedades no coinciden. Siempre consultar **Object Browser (F2 en VBE)** antes de codear, NO adivinar.
  - ❌ `Layers.Add()` no existe → usar `Page.CreateLayer(nombre)`
  - ❌ `Application.BeginCommandGroup()` no existe (es `Document.BeginCommandGroup()`, opcional)
  - ❌ `Export()` es Sub, no Function → usar `ExportBitmap()` que sí es Function
  - ❌ `ExportBitmap(path, filter, range, imageType, 0, 0, dpi, dpi, ..., None, None)` → pedir Width/Height en pixels causa E_INVALID_ARG. **Usar 0, 0 + SetSize() previo.**

- **⚠️ CRÍTICO:** CorelDRAW **BLOQUEA operaciones COM de exportación mientras el VBE está abierto**
  - ❌ NO ejecutar macros con F5 desde VBE (sale E_INVALID_ARG sin sentido)
  - ✅ SIEMPRE ejecutar desde **Herramientas → Macros → Ejecutar Macro** o `GMSManager.RunMacro()` desde Python (sin VBE activo)

### Entorno Python:
- **NO uses `asyncio.wait_for()` con contextos MCP** (rompe cancel scopes anyio). Usar `asyncio.timeout`.
- **NO instales con `pip` del sistema** → siempre venv hermes: `C:\Users\Administrator\AppData\Local\hermes\hermes-agent\venv\Scripts\python.exe -m pip install ...`
- **Rutas con caracteres especiales (ñ, acentos):** COM puede rechazarlas. Usar rutas ASCII simples cuando sea posible.

### VBA código:
- **ASCII PURO** (sin acentos ni eñes — MsgBox también).
- El usuario pidió **economía de tokens**: ser directo, pocas iteraciones, tests agrupados.

### Git:
- **Micro-commits por componente** (GOVERNANCE.md §3). Pedir autorización antes de commitear.
- Hay un punto de restauración de Windows previo a limpieza de disco (2026-07-28).
