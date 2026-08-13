#!/usr/bin/env python3
"""
MCP Multi-Server Manager
=========================
Lanza y gestiona múltiples servidores MCP simultáneamente,
agregando todas sus herramientas en una interfaz unificada.

Servidores incluidos:
  🪟 windows-automation  - Control de Windows (mcp_windows_server.py)
  📁 filesystem           - Operaciones avanzadas de archivos (oficial MCP)
  🌐 fetch                - Lectura de páginas web como Markdown (oficial MCP)
  🧠 memory               - Memoria persistente entre sesiones (built-in)

Uso:
  from mcp_multi_server import MultiServerManager
  
  manager = MultiServerManager()
  await manager.start_all()
  tools = await manager.list_all_tools()
  result = await manager.call_tool("file_list", {"path": "."})
"""

import asyncio
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import mcp.types as types
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

# Consola Windows en UTF-8 (evita UnicodeEncodeError con emojis en cp1252)
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


# ═════════════════════════════════════════════════════════════════════════════
# CONFIGURACIÓN DE SERVIDORES MCP
# ═════════════════════════════════════════════════════════════════════════════

# Ruta base del proyecto
PROJECT_DIR = Path(__file__).parent.resolve()

# Directorio para memoria persistente
MEMORY_DIR = PROJECT_DIR / "memory_data"
MEMORY_DIR.mkdir(exist_ok=True)

# Configuración de cada servidor MCP
SERVER_CONFIGS = {
    "windows-automation": {
        "description": "Control de Windows (ventanas, mouse, teclado, procesos, sistema)",
        "command": sys.executable,
        "args": [str(PROJECT_DIR / "mcp_windows_server.py")],
        "enabled": True,
        "icon": "🪟",
    },
    "corel-draw": {
        "description": "Control de CorelDRAW (documentos, texto, exportación, macros POD Suite)",
        "command": sys.executable,
        "args": [str(PROJECT_DIR / "mcp_corel_server.py")],
        "enabled": True,
        "icon": "🎨",
    },
    "filesystem": {
        "description": "Operaciones avanzadas de archivos (búsqueda, árbol de directorios)",
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-filesystem", os.environ.get("USERPROFILE", ".")],
        "enabled": True,
        "icon": "📁",
    },
    # NOTA: el servidor fetch oficial (mcp-server-fetch) está roto con las
    # versiones nuevas del SDK MCP (ImportError: McpError). La lectura web
    # ahora la provee la tool 'web_fetch' integrada en mcp_windows_server.py
    "fetch": {
        "description": "Lectura de páginas web (DESHABILITADO: usar web_fetch de windows-automation)",
        "command": "uvx",
        "args": ["mcp-server-fetch"],
        "enabled": False,
        "icon": "🌐",
    },
}


# ═════════════════════════════════════════════════════════════════════════════
# MEMORIA PERSISTENTE (Built-in, no necesita servidor externo)
# ═════════════════════════════════════════════════════════════════════════════

# La memoria es un módulo interno del launcher, no un MCP server externo

MEMORY_TOOLS = [
    {
        "name": "memory_save",
        "description": "Guarda información en la memoria persistente del agente (recuerda datos entre sesiones)",
        "inputSchema": {
            "type": "object",
            "properties": {
                "key": {
                    "type": "string",
                    "description": "Nombre único para recordar este dato (ej: 'user_name', 'project_config')"
                },
                "value": {
                    "type": "string",
                    "description": "Valor a recordar (texto o JSON)"
                },
            },
            "required": ["key", "value"],
        },
    },
    {
        "name": "memory_load",
        "description": "Carga información previamente guardada en la memoria persistente",
        "inputSchema": {
            "type": "object",
            "properties": {
                "key": {
                    "type": "string",
                    "description": "Nombre del dato a recuperar"
                },
            },
            "required": ["key"],
        },
    },
    {
        "name": "memory_list",
        "description": "Lista todas las claves guardadas en la memoria persistente",
        "inputSchema": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "memory_delete",
        "description": "Elimina un dato de la memoria persistente",
        "inputSchema": {
            "type": "object",
            "properties": {
                "key": {
                    "type": "string",
                    "description": "Nombre del dato a eliminar"
                },
            },
            "required": ["key"],
        },
    },
]


def _memory_save(key: str, value: str) -> str:
    """Guarda un valor en la memoria persistente (archivo JSON)."""
    try:
        key_safe = key.replace(" ", "_").replace("/", "_")
        filepath = MEMORY_DIR / f"{key_safe}.json"
        data = {
            "key": key,
            "value": value,
            "saved_at": datetime.now().isoformat(),
        }
        filepath.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        return json.dumps({"success": True, "key": key, "size": len(value)})
    except Exception as e:
        return json.dumps({"error": str(e)})


def _memory_load(key: str) -> str:
    """Carga un valor de la memoria persistente."""
    try:
        key_safe = key.replace(" ", "_").replace("/", "_")
        filepath = MEMORY_DIR / f"{key_safe}.json"
        if not filepath.exists():
            return json.dumps({"error": f"No se encontró '{key}' en la memoria"})
        data = json.loads(filepath.read_text(encoding="utf-8"))
        return json.dumps(data, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": str(e)})


def _memory_list() -> str:
    """Lista todas las claves en la memoria persistente."""
    try:
        memories = []
        for f in MEMORY_DIR.glob("*.json"):
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                memories.append({
                    "key": data.get("key", f.stem),
                    "saved_at": data.get("saved_at", "unknown"),
                    "size": len(data.get("value", "")),
                })
            except Exception:
                memories.append({"key": f.stem, "saved_at": "unknown", "size": 0})
        return json.dumps({"count": len(memories), "memories": memories}, ensure_ascii=False, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)})


def _memory_delete(key: str) -> str:
    """Elimina un valor de la memoria persistente."""
    try:
        key_safe = key.replace(" ", "_").replace("/", "_")
        filepath = MEMORY_DIR / f"{key_safe}.json"
        if not filepath.exists():
            return json.dumps({"error": f"No se encontró '{key}' en la memoria"})
        filepath.unlink()
        return json.dumps({"success": True, "key": key, "action": "deleted"})
    except Exception as e:
        return json.dumps({"error": str(e)})


MEMORY_HANDLERS = {
    "memory_save": _memory_save,
    "memory_load": _memory_load,
    "memory_list": _memory_list,
    "memory_delete": _memory_delete,
}


# ═════════════════════════════════════════════════════════════════════════════
# MANAGER MULTI-SERVIDOR
# ═════════════════════════════════════════════════════════════════════════════

class ServerConnection:
    """Conexión a un servidor MCP individual."""
    
    def __init__(self, name: str, config: dict):
        self.name = name
        self.config = config
        self.session: Optional[ClientSession] = None
        self._read = None
        self._write = None
        self._stdio = None
        self.tools: list = []
    
    async def start(self):
        """Inicia el servidor MCP y establece conexión."""
        params = StdioServerParameters(
            command=self.config["command"],
            args=self.config["args"],
        )
        
        # Timeout para evitar que se cuelgue (ej: npx descargando paquetes)
        # NOTA: se usa asyncio.timeout (NO asyncio.wait_for) porque wait_for
        # crea una TAREA NUEVA y el stdio_client de MCP usa cancel scopes de
        # anyio que DEBEN entrar y salir en la misma tarea, o falla con:
        # "Attempted to exit cancel scope in a different task"
        try:
            self._stdio = stdio_client(params)
            async with asyncio.timeout(30):
                self._read, self._write = await self._stdio.__aenter__()
            
            try:
                async with asyncio.timeout(30):
                    self.session = await ClientSession(self._read, self._write).__aenter__()
                    await self.session.initialize()
                
                # Obtener herramientas
                result = await self.session.list_tools()
                self.tools = result.tools
                
                return len(self.tools)
            except BaseException:
                # El proceso murió o falló la inicialización: cerrar el stdio
                # en LA MISMA TAREA para no romper los cancel scopes de anyio
                # (si lo dejamos al GC, lanza "exit cancel scope in a different task")
                try:
                    await self._stdio.__aexit__(None, None, None)
                except Exception:
                    pass
                self._stdio = None
                raise
        except (asyncio.TimeoutError, TimeoutError):
            raise TimeoutError(f"Timeout al conectar con {self.name} (30s)")
    
    async def stop(self):
        """Detiene el servidor MCP."""
        # NOTA: se captura BaseException porque el cierre de los cancel scopes
        # de anyio puede propagar CancelledError (no hereda de Exception)
        try:
            if self.session:
                await self.session.__aexit__(None, None, None)
        except BaseException:
            pass
        try:
            if self._stdio:
                await self._stdio.__aexit__(None, None, None)
        except BaseException:
            pass
    
    async def call_tool(self, name: str, arguments: dict) -> Any:
        """Llama a una herramienta en este servidor."""
        if not self.session:
            raise RuntimeError(f"Servidor {self.name} no está conectado")
        return await self.session.call_tool(name, arguments)


class MultiServerManager:
    """Gestiona múltiples servidores MCP y provee interfaz unificada."""
    
    def __init__(self, enabled_servers: list[str] = None):
        """
        Args:
            enabled_servers: Lista de servidores a habilitar.
                             None = todos los disponibles.
                             Ej: ['windows-automation', 'fetch']
        """
        self.connections: dict[str, ServerConnection] = {}
        self._enabled_servers = enabled_servers
    
    async def start_all(self) -> dict[str, int]:
        """
        Inicia todos los servidores MCP configurados.

        Returns:
            Dict con nombre del servidor -> cantidad de tools cargadas
        """
        results = {}
        
        for name, config in SERVER_CONFIGS.items():
            if not config.get("enabled", True):
                continue
            if self._enabled_servers and name not in self._enabled_servers:
                continue
            
            icon = config.get("icon", "🔌")
            print(f"{icon} Conectando: {name}...", end=" ", flush=True)
            
            try:
                conn = ServerConnection(name, config)
                tool_count = await conn.start()
                self.connections[name] = conn
                results[name] = tool_count
                print(f"✅ ({tool_count} tools)")
            except Exception as e:
                print(f"❌ {e}")
                results[name] = 0
        
        # Memoria persistente no necesita conexión (built-in)
        print(f"🧠 Conectando: memory... ✅ (4 tools)")
        
        return results
    
    async def stop_all(self):
        """Detiene todos los servidores."""
        for name, conn in self.connections.items():
            try:
                await conn.stop()
            except BaseException:
                pass
        self.connections.clear()
    
    async def list_all_tools(self) -> list[dict]:
        """
        Obtiene todas las herramientas de todos los servidores,
        incluyendo las herramientas de memoria.
        
        Returns:
            Lista de herramientas con información del servidor origen
        """
        all_tools = []
        
        for name, conn in self.connections.items():
            icon = SERVER_CONFIGS.get(name, {}).get("icon", "")
            for tool in conn.tools:
                all_tools.append({
                    "server": name,
                    "icon": icon,
                    "name": tool.name,
                    "description": tool.description,
                    "inputSchema": tool.inputSchema,
                })
        
        # Agregar herramientas de memoria
        for tool_def in MEMORY_TOOLS:
            all_tools.append({
                "server": "memory",
                "icon": "🧠",
                "name": tool_def["name"],
                "description": tool_def["description"],
                "inputSchema": tool_def["inputSchema"],
            })
        
        return all_tools
    
    async def call_tool(self, name: str, arguments: dict) -> Any:
        """
        Ejecuta una herramienta en el servidor correspondiente.
        
        Args:
            name: Nombre de la herramienta
            arguments: Argumentos de la herramienta
            
        Returns:
            Resultado de la herramienta
        """
        # Primero verificar si es herramienta de memoria
        if name in MEMORY_HANDLERS:
            result_text = MEMORY_HANDLERS[name](**arguments)
            return types.CallToolResult(content=[
                types.TextContent(type="text", text=result_text)
            ])
        
        # Buscar en qué servidor está la herramienta
        for server_name, conn in self.connections.items():
            for tool in conn.tools:
                if tool.name == name:
                    return await conn.call_tool(name, arguments)
        
        raise ValueError(f"Herramienta '{name}' no encontrada en ningún servidor")
    
    def get_tools_for_ollama(self) -> list[dict]:
        """
        Convierte todas las herramientas al formato de Ollama.
        
        Returns:
            Lista de herramientas en formato Ollama function calling
        """
        ollama_tools = []
        
        for name, conn in self.connections.items():
            for tool in conn.tools:
                ollama_tools.append({
                    "type": "function",
                    "function": {
                        "name": tool.name,
                        "description": f"[{name}] {tool.description}",
                        "parameters": tool.inputSchema,
                    }
                })
        
        # Agregar herramientas de memoria
        for tool_def in MEMORY_TOOLS:
            ollama_tools.append({
                "type": "function",
                "function": {
                    "name": tool_def["name"],
                    "description": f"[memory] {tool_def['description']}",
                    "parameters": tool_def["inputSchema"],
                }
            })
        
        return ollama_tools


# ═════════════════════════════════════════════════════════════════════════════
# PRUEBA RÁPIDA
# ═════════════════════════════════════════════════════════════════════════════

async def test_connection():
    """Prueba la conexión a todos los servidores."""
    print("=" * 60)
    print("  MCP Multi-Server Manager - Test")
    print("=" * 60)
    print()
    
    manager = MultiServerManager()
    
    try:
        results = await manager.start_all()
        
        print()
        print("-" * 40)
        print("RESUMEN:")
        for name, count in results.items():
            icon = SERVER_CONFIGS.get(name, {}).get("icon", "🔌")
            status = "✅" if count > 0 else "❌"
            print(f"  {icon} {name}: {status} ({count} tools)")
        print(f"  🧠 memory: ✅ (4 tools)")
        
        all_tools = await manager.list_all_tools()
        print(f"\n📦 Total herramientas disponibles: {len(all_tools)}")
        
        # Agrupar por servidor
        by_server = {}
        for tool in all_tools:
            by_server.setdefault(tool["server"], []).append(tool["name"])
        
        for server, tools in by_server.items():
            print(f"\n  {server} ({len(tools)} tools):")
            for t in tools[:5]:  # Mostrar primeras 5
                print(f"    - {t}")
            if len(tools) > 5:
                print(f"    ... y {len(tools) - 5} más")
        
        print("\n✅ Test completado exitosamente")
        
    finally:
        await manager.stop_all()


if __name__ == "__main__":
    asyncio.run(test_connection())
