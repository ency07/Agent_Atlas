# 🤖 MCP Windows AI - Controla Windows con IA Local

**MCP Windows AI** es un servidor **MCP (Model Context Protocol)** que permite a modelos de IA locales (como Ollama) controlar Windows automáticamente. Es completamente **gratuito, open-source** y funciona 100% local - tus datos nunca salen de tu computadora.

## ✨ ¿Qué puede hacer?

| Categoría | Acciones |
|-----------|----------|
| 🪟 **Ventanas** | Listar, enfocar, mover, redimensionar, minimizar, maximizar, cerrar |
| 🖱️ **Mouse** | Mover cursor, click (izquierdo/derecho), scroll, arrastrar |
| ⌨️ **Teclado** | Escribir texto, atajos (Ctrl+C, Win+D), presionar teclas |
| 📁 **Archivos** | Listar, leer, escribir, copiar, eliminar, crear carpetas |
| 🔧 **Procesos** | Listar, matar, iniciar programas |
| ℹ️ **Sistema** | Info del PC, captura de pantalla, portapapeles, volumen, WiFi |
| 📋 **Registro** | Leer el registro de Windows |
| 🔔 **Notificaciones** | Mostrar notificaciones del sistema |

### 🚀 Multi-Server (NUEVO)

Además del control de Windows, ahora puedes activar **servidores MCP adicionales** que se conectan automáticamente:

| Servidor | Tools | Propósito |
|----------|-------|-----------|
| 🪟 **windows-automation** | 35 | Control de Windows (núcleo) |
| 📁 **filesystem** | ~5 | Operaciones avanzadas de archivos (búsqueda, árbol) |
| 🌐 **fetch** | ~3 | Leer páginas web como Markdown |
| 🧠 **memory** | 4 | Memoria persistente entre sesiones |

**Total: ~47 herramientas** disponibles para la IA.

## 🚀 Requisitos

- **Windows 10/11**
- **Python 3.10+** ([Descargar](https://www.python.org/downloads/))
- **Ollama** ([Descargar](https://ollama.com/download))

## 📥 Instalación Rápida

### Paso 1: Clonar e instalar dependencias

```bash
# Clonar el repositorio
git clone https://github.com/tu-usuario/mcp-windows-ai.git
cd mcp-windows-ai

# Instalar dependencias
pip install -r requirements.txt
```

### Paso 2: Instalar y configurar Ollama

```bash
# Descargar Ollama desde: https://ollama.com/download
# Instalarlo y luego abrir CMD:

# Descargar un modelo (recomendado: llama3.2 por ser ligero)
ollama pull llama3.2

# Opciones recomendadas:
ollama pull mistral          # Rápido y ligero
ollama pull qwen2.5:7b       # Excelente para function calling
ollama pull deepseek-r1:8b   # Buen razonamiento
```

### Paso 3: ¡A usarlo!

```bash
# Opción A: Usar el menú interactivo
run_with_ollama.bat

# Opción B: Directo desde CMD
python mcp_ollama_client.py

# Opción C: Con modelo específico
python mcp_ollama_client.py --model qwen2.5:7b

# Opción D: Modo automático (sin confirmaciones)
python mcp_ollama_client.py --auto
```

## 💡 Ejemplos de Uso

Una vez iniciada la sesión interactiva, puedes escribir comandos como:

```
👤 Tú: Abre el bloc de notas y escribe "Hola Mundo"
👤 Tú: ¿Cuánta memoria RAM tiene mi PC?
👤 Tú: Lista los archivos del escritorio
👤 Tú: Crea una carpeta llamada "proyectos" en el escritorio
👤 Tú: Saca una captura de pantalla
👤 Tú: Ejecuta ipconfig en el CMD
👤 Tú: Cierra todas las ventanas del navegador
👤 Tú: Sube el volumen al 70%
👤 Tú: ¿Qué procesos están usando más memoria?
```

## 🎮 Comandos del Cliente

Durante la sesión interactiva:

| Comando | Acción |
|---------|--------|
| `salir` / `exit` | Terminar la sesión |
| `help` | Mostrar ayuda |
| `tools` | Listar herramientas disponibles |
| `reset` | Reiniciar la conversación |
| `toggle-approve` | Activar/desactivar aprobación manual |

## 🔧 Usar con Claude Desktop

Si usas Claude Desktop, agrega esta configuración en:
`%APPDATA%\Claude\claude_desktop_config.json`

```json
{
  "mcpServers": {
    "windows-automation": {
      "command": "python",
      "args": ["C:\\ruta\\completa\\mcp-windows-ai\\mcp_windows_server.py"]
    }
  }
}
```

## 🛠️ Arquitectura

```
┌─────────────────────────────────────────────────────┐
│                    TÚ (Usuario)                      │
└─────────────────┬───────────────────────────────────┘
                  │ "Abre el bloc de notas"
                  ▼
┌─────────────────────────────────────────────────────┐
│              mcp_ollama_client.py                    │
│   ┌──────────────────────────────────────────┐      │
│   │  Traductor MCP ←→ Ollama                    │      │
│   │  - Convierte tools MCP a funciones Ollama │      │
│   │  - Maneja el loop de conversación         │      │
│   │  - Sistema de aprobación (HITL)           │      │
│   └──────────────┬───────────────────────────┘      │
└──────────────────┼──────────────────────────────────┘
                   │
          ┌────────┴────────┐
          ▼                  ▼
┌─────────────────┐  ┌─────────────────┐
│  Ollama API      │  │  MCP Server      │
│  http://localhost│  │  (stdio)         │
│  :11434/api/chat │  │  mcp_windows_    │
│                  │  │  server.py       │
└─────────────────┘  └────────┬─────────┘
                              │
                              ▼
                   ┌─────────────────┐
                   │   Windows API    │
                   │  - win32gui      │
                   │  - pyautogui     │
                   │  - psutil        │
                   │  - subprocess    │
                   └─────────────────┘
```

## 📦 Dependencias

| Paquete | Propósito |
|---------|-----------|
| `mcp` | SDK oficial de Model Context Protocol |
| `pyautogui` | Control de mouse, teclado y capturas |
| `pygetwindow` | Gestión de ventanas |
| `psutil` | Información del sistema y procesos |
| `pyperclip` | Acceso al portapapeles |
| `pywin32` | API nativa de Windows (opcional) |
| `requests` | Comunicación con Ollama |
| `Pillow` | Procesamiento de imágenes |

## 🔒 Seguridad

- **100% Local**: Todo corre en tu máquina, nada sale a internet
- **Human-in-the-Loop**: Las operaciones destructivas requieren aprobación
- **Modo Auto**: Puedes desactivar las confirmaciones con `--auto`
- **Límite de herramientas**: Máximo 15 tool calls por turno
- **Sin permisos especiales**: Usa las APIs estándar de Windows

## 🤝 Modelos de IA Recomendados

| Modelo | Comando | Calidad | Velocidad |
|--------|---------|---------|-----------|
| Llama 3.2 | `ollama pull llama3.2` | ⭐⭐⭐ | ⚡⚡⚡ |
| Mistral | `ollama pull mistral` | ⭐⭐⭐ | ⚡⚡⚡⚡ |
| Qwen 2.5 7B | `ollama pull qwen2.5:7b` | ⭐⭐⭐⭐ | ⚡⚡⚡ |
| DeepSeek R1 8B | `ollama pull deepseek-r1:8b` | ⭐⭐⭐⭐ | ⚡⚡ |
| Llama 3.1 8B | `ollama pull llama3.1:8b` | ⭐⭐⭐⭐ | ⚡⚡⚡ |

## 📄 Licencia

MIT - Haz lo que quieras con este código. Es libre y gratuito.

---

## 🧾 Deuda Operativa (GOVERNANCE.md §4)

Decisiones técnicas que se alejan del estándar y deben revisarse:

| # | Deuda | Motivo | Revisar cuando |
|---|-------|--------|----------------|
| 1 | Servidor `fetch` externo deshabilitado; lectura web la hace `web_fetch` integrada | El paquete oficial `mcp-server-fetch` está roto con el SDK MCP actual (ver [ADR-001](docs/adr/001-web-fetch-integrado.md)) | El paquete oficial se repare |
| 2 | Whitelists de seguridad hardcodeadas en `mcp_ollama_client.py` | Simplicidad inicial (ver [ADR-003](docs/adr/003-seguridad-niveles-riesgo.md)) | Mover a `mcp-servers.config.json` |
| 3 | Macros VBA de POD Suite invocadas vía `GMSManager.RunMacro` sin paso de parámetros | GMSManager no admite argumentos; los parámetros requerirían archivo temporal intermedio | Al integrar POD Suite completo |
| 4 | Tests de CorelDRAW requieren CorelDRAW instalado y visible | La API COM no funciona headless | — |

**Decisiones de arquitectura documentadas:** ver [`docs/adr/`](docs/adr/).

**Tests:** `python tests/test_documents.py` y `python tests/test_multi_server.py`

---

**¿Preguntas?** Abre un issue en GitHub o contribuye con un Pull Request.
