# 📘 Guía Completa de Uso — MCP Windows AI

> Cómo usar este ecosistema MCP con las **3 opciones de agente** que tienes instaladas:
> **Cliente propio**, **OpenCode** y **Hermes Agent**.

---

## 0. ¿Qué es cada cosa? (Aclaración importante)

```
┌────────────────────────────────────────────────────────────────────┐
│  SERVIDORES (las "manos" — ejecutan acciones en Windows)           │
│  ├─ mcp_windows_server.py   → 44 tools (documentos, programas…)    │
│  ├─ mcp_corel_server.py     → 18 tools CorelDRAW + macros POD      │
│  ├─ filesystem (npx)        → 14 tools de archivos                 │
│  └─ memory (integrada)      → 4 tools de memoria persistente       │
│                                                                    │
│  AGENTES (el "cerebro" — decides cuál usar):                       │
│  ├─ CLIENTE PROPIO → mcp_ollama_client.py (¡ya viene incluido!)    │
│  ├─ OpenCode       → el agente de terminal que editó este proyecto │
│  └─ Hermes Agent   → tu asistente personal (usa el venv hermes)    │
└────────────────────────────────────────────────────────────────────┘
```

**El "cliente propio" NO es un software aparte**: es el archivo `mcp_ollama_client.py`
que vive dentro de esta misma carpeta. Es un chat de terminal que conecta Ollama
con los servidores. Lo arrancas tú manualmente cuando lo necesitas.

| | Cliente propio | OpenCode | Hermes |
|---|---|---|---|
| Qué es | Script Python del proyecto | Agente de terminal (TUI) | Tu asistente personal instalado |
| Modelos | Solo Ollama (local) | Ollama + nube | Ollama + Groq + Gemini + OpenCode Go |
| Privacidad | 100% local | Local o nube (según modelo) | Local o nube (según modelo) |
| Seguridad granular | ✅ Niveles de riesgo + whitelist | Permisos propios de opencode | Guardrails propios de Hermes |
| Config necesaria | Ninguna | `opencode.jsonc` | `config.yaml` |

---

## 1. 🐍 CLIENTE PROPIO (`mcp_ollama_client.py`)

El más simple y 100% privado. Ideal para tareas cotidianas con modelos locales.

### Arrancar

```bash
cd E:\MCP\mcp-windows-ai

# Opción A — menú interactivo (te pregunta el modelo)
run_with_ollama.bat

# Opción B — directo con modelo elegido
python mcp_ollama_client.py --model phi4-mini

# Opción C — máxima inteligencia local (workflows, documentos)
python mcp_ollama_client.py --model qwen2.5-coder:7b

# Opción D — modo automático (SIN confirmaciones — ¡cuidado!)
python mcp_ollama_client.py --model phi4-mini --auto
```

> 💡 Qué modelo elegir según tu PC (CPU, sin GPU): ver **`MODELOS.md`**.

### Comandos dentro de la sesión

| Comando | Acción |
|---|---|
| `salir` / `exit` | Terminar |
| `help` | Ayuda |
| `tools` | Listar las 62 herramientas |
| `servers` | Estado de servidores |
| `reset` | Limpiar conversación (si la IA se "traba") |
| `toggle-approve` | Activar/desactivar confirmaciones |

### Niveles de aprobación (seguridad)

| Nivel | Se pide | Ejemplos |
|---|---|---|
| 🟢 BAJO | Nada (automático) | listar archivos, info del sistema, leer web |
| 🟡 MEDIO | Enter | abrir programas, clicks, escribir texto |
| 🟠 ALTO | escribir `y` | crear/editar archivos, ejecutar scripts |
| 🔴 CRÍTICO | escribir `CONFIRMAR` | borrar, matar procesos, comandos shell |

### Ejemplos de prompts que ya funcionan

```
👤 Crea una carpeta "reportes" en el escritorio y dentro un Excel
   de gastos con fórmulas que sumen solas

👤 Hazme una presentación PowerPoint de 5 diapositivas sobre mi
   negocio de camisetas y ábrela cuando termines

👤 Genera una carta en PDF con membrete de "Soluciones Tech S.A."

👤 Lee https://ejemplo.com y guárdame un resumen en un Word en Documentos

👤 ¿Qué programas de diseño tengo instalados?

👤 Guarda en memoria que mi empresa se llama "MiMarca" y úsala
   en los membretes de ahora en adelante
```

---

## 2. 🖥️ OPENCODE

El agente de terminal más capaz que tienes (modelos locales + nube). Aquí los
servidores se registran **individualmente** en su config global.

### Configuración (una sola vez)

Edita `C:\Users\Administrator\.config\opencode\opencode.jsonc` y añade dentro
de la sección `"mcp"` (junto al `corel-draw` que ya tienes):

```jsonc
"mcp": {
  "corel-draw": {
    "type": "local",
    "command": ["C:\\Users\\Administrator\\AppData\\Local\\hermes\\hermes-agent\\venv\\Scripts\\python.exe", "C:\\Users\\Administrator\\Desktop\\corel_mcp_server.py"],
    "enabled": true
  },
  "windows-ai": {
    "type": "local",
    "command": ["C:\\Users\\Administrator\\AppData\\Local\\hermes\\hermes-agent\\venv\\Scripts\\python.exe", "E:\\MCP\\mcp-windows-ai\\mcp_windows_server.py"],
    "enabled": true
  },
  "corel-mcp": {
    "type": "local",
    "command": ["C:\\Users\\Administrator\\AppData\\Local\\hermes\\hermes-agent\\venv\\Scripts\\python.exe", "E:\\MCP\\mcp-windows-ai\\mcp_corel_server.py"],
    "enabled": true
  },
  "filesystem": {
    "type": "local",
    "command": ["npx", "-y", "@modelcontextprotocol/server-filesystem", "C:\\Users\\Administrator"],
    "enabled": true
  }
}
```

> ⚠️ **Importante**: usa el Python del **venv de hermes** (es donde están
> instaladas las librerías de documentos). Si usas otro Python, las tools de
> Word/Excel/PowerPoint/PDF devolverán error.
>
> 🔄 Después de guardar, **cierra y reabre OpenCode** (la config no se recarga en caliente).

### Uso

```
opencode
> Créame un informe de ventas en Word con una tabla de los últimos 3 meses
> Abre VS Code en E:\MCP\mcp-windows-ai
> Ejecuta los tests del proyecto y dime si pasan
```

OpenCode tiene su propio sistema de permisos (`permission` en el jsonc), por lo
que el sistema de niveles de riesgo del cliente propio **no aplica** aquí.

---

## 3. 🚀 HERMES AGENT

Tu asistente personal. Ya tiene las librerías instaladas en su venv
(`...\hermes\hermes-agent\venv`) — por eso los tests y servidores funcionan con él.

### Configuración (una sola vez)

Edita `C:\Users\Administrator\AppData\Local\hermes\config.yaml` y añade al final:

```yaml
mcp_servers:
  windows-ai:
    command: C:\Users\Administrator\AppData\Local\hermes\hermes-agent\venv\Scripts\python.exe
    args:
      - E:\MCP\mcp-windows-ai\mcp_windows_server.py
    enabled: true
    timeout: 120
  corel-draw:
    command: C:\Users\Administrator\AppData\Local\hermes\hermes-agent\venv\Scripts\python.exe
    args:
      - E:\MCP\mcp-windows-ai\mcp_corel_server.py
    enabled: true
    timeout: 120
```

Reinicia Hermes y las 44 herramientas aparecerán disponibles para el modelo activo.

### Uso

Hermes usa el modelo que tengas por defecto (`model.default` en tu config:
actualmente `qwen3:1.7b`). Para tareas de documentos complejas, cámbialo a uno
más capaz de tus providers:

```yaml
model:
  default: qwen2.5:3b        # local, obediente con tools
  # o uno de nube que ya tienes configurado:
  # default: llama-3.3-70b-versatile   (Groq - gratis y muy capaz)
  # default: gemini-3-flash-preview    (Gemini)
```

> 💡 **Recomendación probada hoy**: los modelos locales pequeños (≤3B) a veces
> escriben código en vez de llamar herramientas. Si ves eso en Hermes, cambia a
> `llama-3.3-70b-versatile` (Groq) o un Gemini — el salto de fiabilidad es enorme.

---

## 4. 🎯 ¿Cuál uso y cuándo?

```
¿Quiero máxima privacidad (nada sale del PC)?
└─► Cliente propio + phi4-mini (rápido) o qwen2.5-coder:7b (documentos)

¿Tarea compleja de varios pasos / programación / depuración?
└─► OpenCode (modelos grandes, mejor razonamiento con herramientas)

¿Uso diario conversacional, ya tengo Hermes abierto?
└─► Hermes con Groq/Gemini para workflows, o modelo local para cosas simples
```

### Compatibilidad de modelos locales con herramientas (probado en tu PC)

| Modelo | Tool-calling | Recomendado para MCP |
|---|---|---|
| qwen2.5-coder:7b | ⭐⭐⭐⭐ | ✅ Documentos y workflows (lento en CPU) |
| phi4-mini | ⭐⭐⭐⭐ | ✅ Mejor equilibrio diario |
| llama3.2:3b | ⭐⭐⭐ | ⚠️ Tareas simples de 1-2 pasos |
| qwen2.5:3b | ⭐⭐⭐ | ⚠️ Similar a llama3.2 |
| qwen3:1.7b / 0.6b | ⭐⭐ | ❌ Se confunde con 62 herramientas |
| gemma3:1b | ⭐ | ❌ No recomendado |

---

## 5. 🔧 Solución de problemas

| Problema | Causa | Solución |
|---|---|---|
| "pip install python-docx" al crear documentos | El agente usa otro Python | Apunta el config al venv hermes (ver §2) |
| La IA escribe código Python en vez de actuar | Modelo pequeño alucina | Cambia a phi4-mini o mayor; escribe `reset` |
| "Access denied - path outside allowed directories" | filesystem solo entra a `C:\Users\Administrator` | Usa rutas dentro de tu carpeta de usuario |
| La IA usa rutas que no existen (`C:\Users\user`) | Modelo adivinando | Ya corregido: el cliente inyecta rutas reales. Actualiza si usas otro cliente |
| Error "cancel scope" al cerrar | Bug anyio (ya corregido) | Actualiza `mcp_multi_server.py` a la versión actual |
| Servidor `fetch` no conecta | Paquete oficial roto | Ya reemplazado por `web_fetch` integrada |
| Ollama no responde | Servicio apagado | `ollama serve` o abrir la app Ollama |

### Verificar que todo está sano

```bash
cd E:\MCP\mcp-windows-ai
python tests\test_documents.py       # prueba Word/Excel/PPT/PDF
python tests\test_multi_server.py    # prueba servidores + seguridad
```

---

## 6. 📂 Mapa del proyecto

```
E:\MCP\mcp-windows-ai\
├── mcp_windows_server.py    # 🪟 Servidor Windows (44 tools)
├── mcp_corel_server.py      # 🎨 Servidor CorelDRAW (18 tools + POD Suite)
├── mcp_multi_server.py      # 🔌 Gestor que lanza todos los servidores
├── mcp_ollama_client.py     # 🐍 CLIENTE PROPIO (chat terminal + seguridad)
├── run_with_ollama.bat      # Menú interactivo de arranque
├── mcp-servers.config.json  # Config de referencia (Claude Desktop)
├── MODELOS.md               # 🎯 Qué modelo Ollama usar y por qué
├── GUIA_USO.md              # 📘 Esta guía
├── GOVERNANCE.md            # 📋 Protocolo de desarrollo
├── README.md                # Documentación general + Deuda Operativa
├── requirements.txt         # Dependencias Python
├── docs\adr\                # Decisiones de arquitectura (ADRs)
├── tests\                   # Tests de verificación
└── memory_data\             # Memoria persistente del agente
```
