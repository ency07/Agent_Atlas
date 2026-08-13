#!/usr/bin/env python3
"""
MCP Ollama Client for Windows
==============================
Cliente MCP que conecta Ollama (modelos locales de IA) con el servidor MCP
de Windows, permitiendo que la IA controle Windows automáticamente.

Uso:
  1. Asegúrate de que Ollama esté instalado y corriendo
     https://ollama.com/download
     
  2. Instala las dependencias:
     pip install -r requirements.txt
     
  3. Ejecuta este cliente:
     python mcp_ollama_client.py
     
  4. El cliente iniciará una sesión interactiva donde puedes
     pedirle a la IA que realice acciones en Windows.

Ejemplo de comandos:
  - "Enumera las ventanas abiertas"
  - "Abre el bloc de notas y escribe 'Hola Mundo'"
  - "¿Cuánta memoria RAM tiene mi PC?"
  - "Crea una carpeta llamada 'proyectos' en el escritorio"
  - "Saca una captura de pantalla"
  - "Cierra el navegador Chrome"
  - "Ejecuta 'ipconfig' en el CMD"
"""

import asyncio
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

import requests

# MCP Multi-Server Manager
from mcp_multi_server import MultiServerManager, SERVER_CONFIGS


# ═════════════════════════════════════════════════════════════════════════════
# CONFIGURACIÓN
# ═════════════════════════════════════════════════════════════════════════════

# Configuración de Ollama
OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "llama3.2")

# ═════════════════════════════════════════════════════════════════════════════
# CONFIGURACIÓN DE SEGURIDAD
# ═════════════════════════════════════════════════════════════════════════════

# Niveles de riesgo
RISK_LOW = "LOW"
RISK_MEDIUM = "MEDIUM"
RISK_HIGH = "HIGH"
RISK_CRITICAL = "CRITICAL"

# Herramientas y su nivel de riesgo
TOOL_RISK_LEVELS = {
    # Crítico: Requiere aprobación estricta
    "file_delete": RISK_CRITICAL,
    "process_kill": RISK_CRITICAL,
    "run_command": RISK_CRITICAL,
    "registry_read": RISK_CRITICAL,
    # Alto: Cambios de estado del sistema
    "file_write": RISK_HIGH,
    "run_script": RISK_HIGH,
    "volume_set": RISK_HIGH,
    "process_start": RISK_HIGH,
    "docx_create": RISK_HIGH,
    "xlsx_create": RISK_HIGH,
    "pptx_create": RISK_HIGH,
    "pdf_create": RISK_HIGH,
    # Medio: Acciones visibles pero reversibles
    "close_window": RISK_MEDIUM,
    "move_window": RISK_MEDIUM,
    "mouse_click": RISK_MEDIUM,
    "keyboard_type": RISK_MEDIUM,
    "keyboard_hotkey": RISK_MEDIUM,
    "open_program": RISK_MEDIUM,
    "type_in_program": RISK_MEDIUM,
    "focus_window": RISK_MEDIUM,
    "clipboard_set": RISK_MEDIUM,
    "open_url": RISK_MEDIUM,
    "notify": RISK_MEDIUM,
    # Bajo: Informativo
    "list_windows": RISK_LOW,
    "system_info": RISK_LOW,
    "file_list": RISK_LOW,
    "file_read": RISK_LOW,
    "process_list": RISK_LOW,
    "get_active_window": RISK_LOW,
    "screenshot": RISK_LOW,
    "clipboard_get": RISK_LOW,
    "get_wifi_info": RISK_LOW,
    "list_installed_programs": RISK_LOW,
    "mouse_position": RISK_LOW,
    "folder_create": RISK_LOW,
    "file_copy": RISK_LOW,
    # ── Servidor filesystem (oficial MCP) ──
    "read_file": RISK_LOW,
    "read_text_file": RISK_LOW,
    "read_multiple_files": RISK_LOW,
    "list_directory": RISK_LOW,
    "directory_tree": RISK_LOW,
    "search_files": RISK_LOW,
    "get_file_info": RISK_LOW,
    "list_allowed_directories": RISK_LOW,
    "create_directory": RISK_LOW,
    "write_file": RISK_HIGH,
    "edit_file": RISK_HIGH,
    "move_file": RISK_HIGH,
    # ── Servidor CorelDRAW ──
    "corel_ping": RISK_LOW,
    "corel_get_document_info": RISK_LOW,
    "corel_list_objects": RISK_LOW,
    "corel_create_document": RISK_MEDIUM,
    "corel_open_document": RISK_MEDIUM,
    "corel_add_text": RISK_MEDIUM,
    "corel_add_rectangle": RISK_MEDIUM,
    "corel_add_ellipse": RISK_MEDIUM,
    "corel_select_all": RISK_MEDIUM,
    "corel_center_on_page": RISK_MEDIUM,
    "corel_run_vba_macro": RISK_HIGH,
    "corel_convert_to_curves": RISK_HIGH,
    "corel_export_png": RISK_MEDIUM,
    "corel_export_jpg": RISK_MEDIUM,
    "corel_publish_pdf": RISK_MEDIUM,
    "corel_save_document": RISK_MEDIUM,
    "corel_delete_selection": RISK_HIGH,
    "corel_close_document": RISK_MEDIUM,
    # ── Servidor fetch ──
    "fetch": RISK_LOW,
    # ── Memoria persistente ──
    "memory_save": RISK_LOW,
    "memory_load": RISK_LOW,
    "memory_list": RISK_LOW,
    "memory_delete": RISK_MEDIUM,
}

# Listas blancas de seguridad (Archivos y Procesos)
WHITELIST_PATHS = [
    "Documents", "Desktop", "Downloads", "Pictures", "Projects"
]
WHITELIST_PROCESSES = [
    "notepad.exe", "calc.exe", "chrome.exe", "explorer.exe", "code.exe"
]

# Habilitar/deshabilitar servidores (por defecto todos activos)
ENABLED_SERVERS = os.environ.get("MCP_SERVERS", "").split(",") if os.environ.get("MCP_SERVERS") else None

# Configuración de la sesión
MAX_TOOL_CALLS_PER_TURN = 20
SHOW_TOOL_APPROVALS = True


# ═════════════════════════════════════════════════════════════════════════════
# CLIENTE OLLAMA
# ═════════════════════════════════════════════════════════════════════════════

class OllamaClient:
    """Cliente para interactuar con la API de Ollama."""
    
    def __init__(self, base_url: str = OLLAMA_HOST, model: str = OLLAMA_MODEL):
        self.base_url = base_url.rstrip("/")
        self.model = model
        
    def check_connection(self) -> bool:
        """Verifica que Ollama esté corriendo."""
        try:
            resp = requests.get(f"{self.base_url}/api/tags", timeout=5)
            if resp.status_code == 200:
                models = resp.json().get("models", [])
                model_names = [m["name"] for m in models]
                print(f"✅ Ollama conectado. Modelos disponibles: {', '.join(model_names)}")
                return True
            return False
        except requests.ConnectionError:
            return False
    
    def pull_model(self) -> bool:
        """Descarga el modelo si no está disponible."""
        try:
            print(f"🔄 Verificando modelo '{self.model}'...")
            resp = requests.get(f"{self.base_url}/api/tags", timeout=5)
            models = resp.json().get("models", [])
            model_names = [m["name"] for m in models]
            
            if self.model in model_names:
                print(f"✅ Modelo '{self.model}' ya disponible")
                return True
            
            print(f"📥 Descargando modelo '{self.model}' (puede tomar varios minutos)...")
            resp = requests.post(
                f"{self.base_url}/api/pull",
                json={"name": self.model},
                stream=True,
                timeout=300,
            )
            for line in resp.iter_lines():
                if line:
                    data = json.loads(line)
                    if "status" in data:
                        print(f"  {data['status']}")
            return True
        except Exception as e:
            print(f"❌ Error descargando modelo: {e}")
            return False
    
    def chat(self, messages: list, tools: list = None) -> dict:
        """
        Envía un mensaje a Ollama y obtiene respuesta.
        
        Args:
            messages: Lista de mensajes [{"role": "...", "content": "..."}]
            tools: Lista de herramientas en formato Ollama
            
        Returns:
            Respuesta de Ollama
        """
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,
        }
        
        if tools:
            payload["tools"] = tools
        
        try:
            resp = requests.post(
                f"{self.base_url}/api/chat",
                json=payload,
                timeout=120,
            )
            resp.raise_for_status()
            return resp.json()
        except requests.Timeout:
            return {"error": "La solicitud a Ollama agotó el tiempo de espera"}
        except requests.RequestException as e:
            return {"error": f"Error de conexión con Ollama: {e}"}


# ═════════════════════════════════════════════════════════════════════════════
# SISTEMA DE APROBACIÓN (HUMAN-IN-THE-LOOP)
# ═════════════════════════════════════════════════════════════════════════════

def is_whitelisted(tool_name: str, arguments: dict) -> bool:
    """
    Verifica si la operación está dentro de las listas blancas de seguridad.
    """
    # Whitelist para Archivos
    path = arguments.get("path", "") or arguments.get("destination", "")
    if path:
        p = str(path).lower()
        if any(allowed.lower() in p for allowed in WHITELIST_PATHS):
            return True
        return False
    
    # Whitelist para Procesos/Comandos
    cmd = arguments.get("command", "") or arguments.get("name", "")
    if cmd:
        c = str(cmd).lower()
        if any(proc in c for proc in WHITELIST_PROCESSES):
            return True
        return False

    return False

def should_approve(tool_name: str, arguments: dict) -> bool:
    """
    Pide confirmación al usuario basándose en el nivel de riesgo y whitelist.
    """
    if not SHOW_TOOL_APPROVALS:
        return True

    risk = TOOL_RISK_LEVELS.get(tool_name, RISK_LOW)
    whitelisted = is_whitelisted(tool_name, arguments)

    # Lógica de aprobación
    if risk == RISK_CRITICAL:
        print(f"\n🚨 [RIESGO CRÍTICO] La IA quiere ejecutar: {tool_name}")
        print(f"   Argumentos: {json.dumps(arguments, ensure_ascii=False)}")
        if whitelisted:
            print("   (Nota: La ruta/proceso está en la whitelist, pero sigue siendo crítico)")
        resp = input("   ¿APROBAR CRÍTICO? (escribe 'CONFIRMAR'): ").strip()
        return resp == "CONFIRMAR"

    if risk == RISK_HIGH:
        print(f"\n⚠️ [RIESGO ALTO] La IA quiere ejecutar: {tool_name}")
        print(f"   Argumentos: {json.dumps(arguments, ensure_ascii=False)}")
        resp = input("   ¿Aprobar? (y/N): ").strip().lower()
        return resp in ("y", "yes", "s", "si")

    if risk == RISK_MEDIUM:
        if whitelisted:
            return True # Auto-aprueba acciones medias en whitelist
        print(f"\n🔧 [RIESGO MEDIO] {tool_name}")
        resp = input("   ¿Aprobar? (Y/n): ").strip().lower()
        return resp not in ("n", "no")

    return True # Bajo riesgo siempre aprueba


# ═════════════════════════════════════════════════════════════════════════════
# SESIÓN INTERACTIVA
# ═════════════════════════════════════════════════════════════════════════════

def build_system_prompt() -> str:
    """
    Construye el prompt del sistema con las rutas REALES de este PC.
    Esto evita que la IA adivine rutas incorrectas (ej: C:\\Users\\user).
    """
    home = Path.home()
    desktop = home / "Desktop"
    documents = home / "Documents"
    downloads = home / "Downloads"
    pictures = home / "Pictures"
    
    return f"""Eres un agente de IA con control total sobre Windows mediante HERRAMIENTAS.

⛔ REGLA MÁS IMPORTANTE:
NUNCA escribas código Python, ni imports, ni snippets para el usuario.
Tú NO ejecutas código: tú LLAMAS HERRAMIENTAS (tools) directamente.
Si una herramienta falla, corrige los argumentos y REINTÉNTALA. No te rindas ni inventes alternativas en código.

📂 RUTAS REALES DE ESTE PC (úsalas siempre, NUNCA las adivines):
- Usuario:    {home}
- Escritorio: {desktop}
- Documentos: {documents}
- Descargas:  {downloads}
- Imágenes:   {pictures}
El servidor de archivos (filesystem) SOLO puede acceder dentro de {home}.

🛠️ CAPACIDADES CLAVE:
1. DOCUMENTOS (reciben JSON con la estructura):
   - docx_create: Word con títulos, secciones, tablas, listas
   - xlsx_create: Excel con FÓRMULAS (=SUM, =AVERAGE, =VLOOKUP, =IF...), formato, varias hojas
   - pptx_create: PowerPoint con diapositivas, bullets, tablas y notas
   - pdf_create: PDF con MEMBRETE (empresa, logo, color, pie de página)

2. PROGRAMAS: open_program abre apps (word, excel, chrome, vscode, notepad, paint,
   coreldraw, photoshop, gimp, blender...) opcionalmente con un archivo.
   list_installed_programs dice qué hay instalado. type_in_program escribe en una ventana.

3. ARCHIVOS: folder_create crea carpetas; file_list explora; file_write escribe texto.

4. AUTOMATIZACIÓN: run_command (shell), run_script (.bat/.ps1).

5. CONTROL: ventanas, mouse, teclado, procesos, portapapeles, capturas.

📋 FLUJO DE TRABAJO OBLIGATORIO:
- Para crear una carpeta: llama folder_create con la ruta completa real (ej: {desktop}\\prueba_ia).
- Para crear documentos: llama la tool docx/xlsx/pptx/pdf_create con el JSON de contenido.
- Después de crear algo, confirma la ruta y ofrece abrirlo con open_program.
- Si una tool devuelve error de ruta, usa las RUTAS REALES de arriba y reintenta.
- ANTES DE ACCIONES CRÍTICAS (borrar, matar procesos): explica por qué es necesario.
- Responde en el idioma del usuario.
"""


async def run_interactive_session():
    """Ejecuta una sesión interactiva completa."""
    
    print("=" * 60)
    print("  MCP Windows + Ollama")
    print("  Controla Windows con IA Local")
    print("=" * 60)
    print("")
    
    # ── Verificar Ollama ────────────────────────────────────────────────
    ollama = OllamaClient()
    
    if not ollama.check_connection():
        print("❌ No se pudo conectar a Ollama.")
        print("")
        print("   Asegúrate de que Ollama esté instalado y ejecutándose:")
        print("   1. Descarga Ollama: https://ollama.com/download")
        print("   2. Ejecuta: ollama serve")
        print("   3. O simplemente: ollama run llama3.2")
        print("")
        input("Presiona Enter para salir...")
        sys.exit(1)
    
    if not ollama.pull_model():
        print("❌ No se pudo asegurar el modelo.")
        sys.exit(1)        # ── Iniciar Multi-Server Manager ──────────────────────────────
    print(f"\n🔧 Iniciando servidores MCP...")
    manager = MultiServerManager(enabled_servers=ENABLED_SERVERS)
    server_results = await manager.start_all()
    
    active_servers = [n for n, c in server_results.items() if c > 0]
    print(f"\n✅ {len(active_servers)} servidores activos")
    for name, count in server_results.items():
        icon = SERVER_CONFIGS.get(name, {}).get("icon", "🔌") if name in SERVER_CONFIGS else "🧠"
        if count > 0:
            print(f"   {icon} {name}: {count} tools")
    
    # Obtener herramientas en formato Ollama
    all_tools_info = await manager.list_all_tools()
    ollama_tools = manager.get_tools_for_ollama()
    
    print(f"\n🤖 Modelo Ollama: {OLLAMA_MODEL}")
    print(f"📦 Tools totales: {len(all_tools_info)}")
    print(f"")
    print(f"📝 Escribe 'salir' o 'exit' para terminar.")
    print(f"📝 Escribe 'help' para ver los comandos disponibles.")
    print(f"📝 Escribe 'tools' para listar todas las herramientas.")
    print(f"📝 Escribe 'servers' para ver estado de servidores.")
    print("=" * 60)
    
    # ── Historial de conversación ────────────────────────────────
    system_prompt = build_system_prompt()
    messages = [
        {"role": "system", "content": system_prompt},
        {
            "role": "assistant",
            "content": "¡Hola! Soy tu asistente de IA local para Windows. "
                       "Tengo acceso a múltiples herramientas: control de Windows, "
                       "archivos, web, memoria persistente y más. "
                       "¿En qué puedo ayudarte?"
        },
    ]
    
    # ── Bucle principal ──────────────────────────────────────────
    try:
        while True:
            user_input = input("\n👤 Tú: ").strip()
            
            if not user_input:
                continue
            
            if user_input.lower() in ("salir", "exit", "quit", "q"):
                print("👋 ¡Hasta luego!")
                break
            
            if user_input.lower() == "help":
                print("""
📋 Comandos disponibles:
  salir / exit   - Terminar la sesión
  help           - Mostrar esta ayuda
  tools          - Listar todas las herramientas disponibles
  servers        - Mostrar estado de servidores
  reset          - Reiniciar la conversación
  toggle-approve - Activar/desactivar aprobación manual

💡 Ejemplos de uso:
  "Enumera las ventanas abiertas"
  "Abre el bloc de notas y escribe 'Hola'"
  "¿Cuánta memoria RAM tengo?"
  "Busca archivos .txt en el escritorio"
  "Lee el contenido de https://ejemplo.com"
  "Guarda en memoria mi configuración"
  "Saca una captura de pantalla"
                """)
                continue
            
            if user_input.lower() == "tools":
                print("\n🔧 Herramientas disponibles:")
                by_server = {}
                for t in all_tools_info:
                    by_server.setdefault(t["server"], []).append(t["name"])
                for server, tools in by_server.items():
                    print(f"\n  [{server}]")
                    for tool_name in tools:
                        print(f"    - {tool_name}")
                continue
            
            if user_input.lower() == "servers":
                print("\n📡 Estado de servidores:")
                for name, count in server_results.items():
                    icon = SERVER_CONFIGS.get(name, {}).get("icon", "🔌") if name in SERVER_CONFIGS else "🧠"
                    status = "✅" if count > 0 else "❌"
                    print(f"  {icon} {name}: {status} ({count} tools)")
                print(f"  🧠 memory: ✅ (4 tools)")
                continue
            
            if user_input.lower() == "reset":
                messages = [
                    {"role": "system", "content": system_prompt},
                ]
                print("🔄 Conversación reiniciada.")
                continue
            
            if user_input.lower() == "toggle-approve":
                global SHOW_TOOL_APPROVALS
                SHOW_TOOL_APPROVALS = not SHOW_TOOL_APPROVALS
                status = "activada" if SHOW_TOOL_APPROVALS else "desactivada"
                print(f"Aprobación manual: {status}")
                continue
            
            # Agregar mensaje del usuario
            messages.append({"role": "user", "content": user_input})
            
            # ── Bucle de herramienta ────────────────────────────────
            tool_call_count = 0
            reached_limit = False
            while tool_call_count < MAX_TOOL_CALLS_PER_TURN:
                # Consultar a Ollama
                print("🤔 Pensando...")
                response = ollama.chat(messages, tools=ollama_tools)
                
                if "error" in response:
                    print(f"❌ Error: {response['error']}")
                    break
                
                message = response.get("message", {})
                
                if not message:
                    print(f"❌ Respuesta vacía de Ollama")
                    break
                
                # Verificar si hay tool_calls
                tool_calls = message.get("tool_calls", [])
                
                if not tool_calls:
                    # Respuesta normal de texto
                    content = message.get("content", "")
                    if content:
                        print(f"\n🤖 IA: {content}")
                    messages.append({"role": "assistant", "content": content})
                    break
                
                # Tiene tool_calls — ejecutar herramientas
                content = message.get("content", "")
                if content and content.strip():
                    print(f"\n🤖 IA: {content}")
                
                # Agregar mensaje del asistente
                messages.append({"role": "assistant", "content": content or ""})
                
                for tool_call in tool_calls:
                    tool_call_count += 1
                    if tool_call_count > MAX_TOOL_CALLS_PER_TURN:
                        reached_limit = True
                        break
                    function = tool_call.get("function", {})
                    tool_name = function.get("name", "")
                    raw_args = function.get("arguments", "{}")
                    
                    # Parsear argumentos
                    if isinstance(raw_args, str):
                        try:
                            arguments = json.loads(raw_args)
                        except json.JSONDecodeError:
                            arguments = {}
                    else:
                        arguments = raw_args
                    
                    print(f"\n🔧 Ejecutando: {tool_name}({json.dumps(arguments, ensure_ascii=False)[:200]})")
                    
                    # Pedir aprobación
                    if not should_approve(tool_name, arguments):
                        print("⏭️  Operación cancelada por el usuario.")
                        messages.append({
                            "role": "tool",
                            "content": json.dumps({"error": "Cancelada por el usuario"}),
                            "name": tool_name,
                        })
                        continue
                    
                    # Ejecutar herramienta en el servidor correspondiente
                    try:
                        tool_result = await manager.call_tool(tool_name, arguments)
                        
                        result_text = ""
                        if hasattr(tool_result, "content"):
                            for item in tool_result.content:
                                if hasattr(item, "text"):
                                    result_text += item.text
                        
                        # Si la tool devolvió un error, indicarle a la IA que reintente
                        is_error = '"error"' in result_text or "Access denied" in result_text
                        if is_error:
                            print(f"⚠️  Error de tool: {result_text[:200]}")
                            result_text += (
                                "\n\n[SISTEMA] La herramienta falló. NO escribas código para el "
                                "usuario. Corrige los argumentos (usa las RUTAS REALES del prompt "
                                "del sistema) y vuelve a llamar la herramienta adecuada."
                            )
                        else:
                            print(f"✅ Resultado: {result_text[:300]}{'...' if len(result_text) > 300 else ''}")
                        messages.append({
                            "role": "tool",
                            "content": result_text,
                            "name": tool_name,
                        })
                    except ValueError as e:
                        print(f"❌ {e}")
                        messages.append({
                            "role": "tool",
                            "content": json.dumps({"error": str(e)}),
                            "name": tool_name,
                        })
                    except Exception as e:
                        error_msg = f"Error ejecutando {tool_name}: {e}"
                        print(f"❌ {error_msg}")
                        messages.append({
                            "role": "tool",
                            "content": json.dumps({"error": str(e)}),
                            "name": tool_name,
                        })
                
                if reached_limit:
                    print(f"\n⚠️  Límite de {MAX_TOOL_CALLS_PER_TURN} herramientas alcanzado.")
                    break
    finally:
        await manager.stop_all()

# ═════════════════════════════════════════════════════════════════════════════
# AUTO-APROBACIÓN: Si se pasa --auto, no pide confirmación
# ═════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    if "--auto" in sys.argv:
        SHOW_TOOL_APPROVALS = False
        print("🤖 Modo automático: no se pedirá confirmación para las herramientas.")
    
    if "--model" in sys.argv:
        idx = sys.argv.index("--model") + 1
        if idx < len(sys.argv):
            OLLAMA_MODEL = sys.argv[idx]
    
    try:
        asyncio.run(run_interactive_session())
    except KeyboardInterrupt:
        print("\n\n👋 Sesión interrumpida. ¡Hasta luego!")
    except Exception as e:
        print(f"\n❌ Error fatal: {e}")
        import traceback
        traceback.print_exc()
        input("\nPresiona Enter para salir...")
