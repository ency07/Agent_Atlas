#!/usr/bin/env python3
"""
Ejemplos de uso programático del MCP Windows Server
=====================================================
Estos ejemplos muestran cómo usar el servidor MCP directamente
desde Python sin necesidad de Ollama.
"""

import asyncio
import json
import sys
import os

# Agregar el directorio padre al path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def ejemplo_listar_ventanas():
    """Ejemplo 1: Listar todas las ventanas abiertas."""
    print("=" * 60)
    print("EJEMPLO 1: Listar ventanas abiertas")
    print("=" * 60)
    
    server_params = StdioServerParameters(
        command=sys.executable,
        args=["mcp_windows_server.py"],
    )
    
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            
            # Listar herramientas
            tools = await session.list_tools()
            print(f"\n🔧 Tools cargadas: {len(tools.tools)}")
            
            # Listar ventanas
            result = await session.call_tool("list_windows", {})
            if result.content:
                windows = json.loads(result.content[0].text)
                print(f"\n🪟 Ventanas encontradas: {len(windows) if isinstance(windows, list) else 'error'}")
                if isinstance(windows, list):
                    for i, win in enumerate(windows[:5]):  # Mostrar primeras 5
                        print(f"  {i+1}. {win['title'][:50]}")
                    if len(windows) > 5:
                        print(f"  ... y {len(windows) - 5} más")


async def ejemplo_info_sistema():
    """Ejemplo 2: Obtener información del sistema."""
    print("\n" + "=" * 60)
    print("EJEMPLO 2: Información del sistema")
    print("=" * 60)
    
    server_params = StdioServerParameters(
        command=sys.executable,
        args=["mcp_windows_server.py"],
    )
    
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            
            result = await session.call_tool("system_info", {})
            if result.content:
                info = json.loads(result.content[0].text)
                print(f"\n💻 Sistema: {info.get('system')} {info.get('release')}")
                print(f"🏠 Hostname: {info.get('hostname')}")
                print(f"🧠 Procesador: {info.get('processor')}")
                
                if "memory" in info:
                    mem = info["memory"]
                    print(f"💾 RAM: {mem['total_gb']}GB total, {mem['available_gb']}GB disponible")
                
                if "disk" in info:
                    disk = info["disk"]
                    print(f"💿 Disco: {disk['total_gb']}GB total, {disk['free_gb']}GB libre")
                
                if "cpu" in info:
                    cpu = info["cpu"]
                    print(f"⚡ CPU: {cpu['cores']} núcleos/{cpu['logical_cores']} lógicos, {cpu['percent']}% uso")


async def ejemplo_archivos():
    """Ejemplo 3: Operaciones con archivos."""
    print("\n" + "=" * 60)
    print("EJEMPLO 3: Operaciones con archivos")
    print("=" * 60)
    
    server_params = StdioServerParameters(
        command=sys.executable,
        args=["mcp_windows_server.py"],
    )
    
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            
            # Crear una carpeta
            desktop = os.path.join(os.path.expanduser("~"), "Desktop")
            test_folder = os.path.join(desktop, "mcp_test")
            
            print(f"\n📁 Creando carpeta: {test_folder}")
            result = await session.call_tool("folder_create", {"path": test_folder})
            print(f"   Resultado: {result.content[0].text[:100] if result.content else 'ok'}")
            
            # Escribir un archivo
            test_file = os.path.join(test_folder, "hola_mcp.txt")
            print(f"\n📝 Escribiendo archivo: {test_file}")
            result = await session.call_tool("file_write", {
                "path": test_file,
                "content": "¡Hola desde MCP Windows AI!\n\nEsto fue escrito por IA local.\n"
            })
            print(f"   Resultado: {result.content[0].text[:100] if result.content else 'ok'}")
            
            # Listar la carpeta
            print(f"\n📂 Listando contenido de la carpeta:")
            result = await session.call_tool("file_list", {"path": test_folder})
            if result.content:
                data = json.loads(result.content[0].text)
                for item in data.get("items", []):
                    print(f"   - {item['name']} ({item['type']}, {item['size']} bytes)")


async def ejemplo_ejecutar_comando():
    """Ejemplo 4: Ejecutar comandos del sistema."""
    print("\n" + "=" * 60)
    print("EJEMPLO 4: Ejecutar comandos del sistema")
    print("=" * 60)
    
    server_params = StdioServerParameters(
        command=sys.executable,
        args=["mcp_windows_server.py"],
    )
    
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            
            # Ejecutar ipconfig
            result = await session.call_tool("run_command", {
                "command": "ipconfig | findstr IPv4",
                "timeout": 10,
            })
            if result.content:
                data = json.loads(result.content[0].text)
                print(f"\n🌐 Direcciones IP:")
                print(f"   {data.get('stdout', 'No disponible')}")


async def main():
    """Ejecutar todos los ejemplos."""
    print("🚀 Ejemplos de uso del MCP Windows Server")
    print("   Asegúrate de tener las dependencias instaladas: pip install -r requirements.txt\n")
    
    try:
        await ejemplo_listar_ventanas()
        await ejemplo_info_sistema()
        await ejemplo_archivos()
        await ejemplo_ejecutar_comando()
    except Exception as e:
        print(f"\n❌ Error: {e}")
        print("\n💡 Asegúrate de ejecutar este script desde el directorio 'mcp-windows-ai'")
        print("   y tener instaladas las dependencias.")
    
    print("\n" + "=" * 60)
    print("✅ Ejemplos completados")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
