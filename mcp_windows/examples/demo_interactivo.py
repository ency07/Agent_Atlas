#!/usr/bin/env python3
"""
🎬 DEMO INTERACTIVO - MCP Windows AI
======================================
Muestra TODAS las capabilities de los MCP servers combinados.

Ejecutar: python examples/demo_interactivo.py

Categorías:
  🪟  Windows  - Ventanas, mouse, teclado, procesos
  📁  Archivos - Leer, escribir, buscar, organizar
  🌐  Web      - Leer páginas, buscar info, abrir URLs
  🧠  Memoria  - Recordar datos entre sesiones
  🔧  Sistema  - Info del PC, capturas, comandos
"""

import asyncio
import json
import os
import sys
import time
from pathlib import Path

# Añadir directorio padre al path
sys.path.insert(0, str(Path(__file__).parent.parent))

from mcp_multi_server import MultiServerManager


# ═════════════════════════════════════════════════════════════════════════════
# UTILIDADES
# ═════════════════════════════════════════════════════════════════════════════

def pprint(label: str, data):
    """Imprime bonito."""
    if isinstance(data, str):
        try:
            data = json.loads(data)
        except json.JSONDecodeError:
            pass
    if isinstance(data, (dict, list)):
        text = json.dumps(data, ensure_ascii=False, indent=2)
    else:
        text = str(data)
    print(f"\n  {label}: {text[:500]}{'...' if len(text) > 500 else ''}")


async def call(manager, tool: str, args: dict = None) -> str:
    """Llama a una herramienta y devuelve el texto del resultado."""
    try:
        result = await manager.call_tool(tool, args or {})
        if hasattr(result, "content") and result.content:
            texts = []
            for item in result.content:
                if hasattr(item, "text"):
                    texts.append(item.text)
            return "\n".join(texts)
        return str(result)
    except Exception as e:
        return f"⚠️ Error: {e}"


# ═════════════════════════════════════════════════════════════════════════════
# DEMOS POR CATEGORÍA
# ═════════════════════════════════════════════════════════════════════════════

async def demo_sistema(manager):
    """ℹ️  INFORMACIÓN DEL SISTEMA"""
    print("\n" + "=" * 60)
    print("  ℹ️  INFORMACION DEL SISTEMA")
    print("=" * 60)
    
    # Info del PC
    print("\n📊 ¿Qué PC tienes?")
    result = await call(manager, "system_info")
    info = json.loads(result)
    print(f"   💻 Sistema: {info.get('system')} {info.get('release')}")
    print(f"   🏠 PC: {info.get('hostname')}")
    print(f"   🧠 CPU: {info.get('cpu', {}).get('cores', '?')} nucleos")
    print(f"   💾 RAM: {info.get('memory', {}).get('total_gb', '?')} GB")
    print(f"   💿 Disco: {info.get('disk', {}).get('total_gb', '?')} GB")
    
    # Captura de pantalla
    print("\n📸 Captura de pantalla...")
    result = await call(manager, "screenshot")
    pprint("Guardada en", result)
    
    # Procesos top
    print("\n⚡ Top 5 procesos por memoria:")
    result = await call(manager, "process_list")
    data = json.loads(result)
    for p in data.get("processes", [])[:5]:
        print(f"   {p['name']}: {p['memory_mb']} MB (PID {p['pid']})")


async def demo_ventanas(manager):
    """🪟  CONTROL DE VENTANAS"""
    print("\n" + "=" * 60)
    print("  🪟  CONTROL DE VENTANAS")
    print("=" * 60)
    
    # Listar ventanas
    print("\n📋 Ventanas abiertas:")
    result = await call(manager, "list_windows")
    windows = json.loads(result)
    if isinstance(windows, list):
        for i, w in enumerate(windows[:8]):  # Top 8
            estado = ""
            if w.get("is_minimized"):
                estado = " (minimizada)"
            elif w.get("is_maximized"):
                estado = " (maximizada)"
            print(f"   {i+1}. {w['title'][:60]}{estado}")
        if len(windows) > 8:
            print(f"   ... y {len(windows) - 8} mas")
    
    # Ventana activa
    print("\n🎯 Ventana activa ahora:")
    result = await call(manager, "get_active_window")
    pprint("", result)


async def demo_archivos(manager):
    """📁  OPERACIONES CON ARCHIVOS"""
    print("\n" + "=" * 60)
    print("  📁  OPERACIONES CON ARCHIVOS")
    print("=" * 60)
    
    escritorio = Path.home() / "Desktop"
    demo_folder = escritorio / "MCP_Demo"
    
    # Crear carpeta
    print(f"\n📂 Creando carpeta de demo: {demo_folder.name}")
    result = await call(manager, "folder_create", {"path": str(demo_folder)})
    print(f"   ✅ Creada")
    
    # Escribir archivos
    print(f"\n📝 Creando archivos de ejemplo...")
    for i in range(1, 4):
        archivo = demo_folder / f"nota_{i}.txt"
        await call(manager, "file_write", {
            "path": str(archivo),
            "content": f"Nota #{i} - Creada por IA local\nFecha: {time.ctime()}\n"
        })
        print(f"   ✅ nota_{i}.txt")
    
    # Listar contenido
    print(f"\n📋 Contenido de la carpeta:")
    result = await call(manager, "file_list", {"path": str(demo_folder)})
    data = json.loads(result)
    for item in data.get("items", []):
        icono = "📁" if item["type"] == "directory" else "📄"
        print(f"   {icono} {item['name']} ({item['size']} bytes)")


async def demo_memoria(manager):
    """🧠  MEMORIA PERSISTENTE"""
    print("\n" + "=" * 60)
    print("  🧠  MEMORIA PERSISTENTE")
    print("=" * 60)
    
    print("\n💾 Guardando datos en memoria...")
    
    # Guardar varios datos
    datos = {
        "usuario": "Juan Pérez",
        "proyecto": "MCP Windows AI",
        "config": json.dumps({"tema": "oscuro", "idioma": "español"})
    }
    
    for key, value in datos.items():
        result = await call(manager, "memory_save", {"key": key, "value": value})
        pprint(f"✅ Guardado '{key}'", result)
    
    # Listar memoria
    print(f"\n📋 Datos en memoria:")
    result = await call(manager, "memory_list")
    data = json.loads(result)
    for mem in data.get("memories", []):
        print(f"   🧠 {mem['key']} ({mem['size']} chars, {mem['saved_at'][:19]})")
    
    # Cargar un dato
    print(f"\n🔍 Cargando 'usuario'...")
    result = await call(manager, "memory_load", {"key": "usuario"})
    pprint("Valor", result)
    
    # Limpiar demo
    print(f"\n🧹 Limpiando datos de demo...")
    for key in datos:
        await call(manager, "memory_delete", {"key": key})
    print("   ✅ Memoria de demo limpiada")


async def demo_web(manager):
    """🌐  LECTURA DE WEB"""
    print("\n" + "=" * 60)
    print("  🌐  LECTURA DE WEB")
    print("=" * 60)
    
    # Abrir URL en navegador
    url = "https://ollama.com"
    print(f"\n🔗 Abriendo {url} en el navegador...")
    result = await call(manager, "open_url", {"url": url})
    pprint("", result)


async def demo_comandos(manager):
    """⚡  COMANDOS DEL SISTEMA"""
    print("\n" + "=" * 60)
    print("  ⚡  COMANDOS DEL SISTEMA")
    print("=" * 60)
    
    # IP local
    print(f"\n🌐 Tu IP local:")
    result = await call(manager, "run_command", {
        "command": "ipconfig | findstr IPv4",
        "timeout": 5
    })
    data = json.loads(result)
    print(f"   {data.get('stdout', 'N/A').strip()}")
    
    # Variable de entorno
    print(f"\n📋 Variables de entorno:")
    result = await call(manager, "run_command", {
        "command": "echo USERNAME=%USERNAME% & echo COMPUTERNAME=%COMPUTERNAME%",
        "timeout": 5
    })
    data = json.loads(result)
    print(f"   {data.get('stdout', 'N/A').strip()}")


async def demo_mouse_teclado(manager):
    """🖱️  MOUSE Y TECLADO (simulado)"""
    print("\n" + "=" * 60)
    print("  🖱️  MOUSE Y TECLADO")
    print("=" * 60)
    
    print(f"\n📍 Posición actual del mouse:")
    result = await call(manager, "mouse_position")
    pprint("", result)


# ═════════════════════════════════════════════════════════════════════════════
# MENÚ PRINCIPAL
# ═════════════════════════════════════════════════════════════════════════════

async def main():
    print("=" * 60)
    print("  🎬  DEMO INTERACTIVO - MCP Windows AI")
    print("  Prueba todas las capabilities combinadas")
    print("=" * 60)
    print()
    print("  Cargando servidores MCP...")
    
    manager = MultiServerManager(enabled_servers=["windows-automation"])
    
    try:
        await manager.start_all()
        
        print("\n✅ Servidores listos!")
        print("   Elige qué quieres ver:")
        print()
        print("   [1] ℹ️  Información del sistema")
        print("   [2] 🪟  Ventanas abiertas")
        print("   [3] 📁  Archivos (crear/leer carpeta demo)")
        print("   [4] 🧠  Memoria persistente")
        print("   [5] 🌐  Abrir web en navegador")
        print("   [6] ⚡  Comandos del sistema")
        print("   [7] 🖱️  Estado del mouse")
        print("   [0] 🎬  TODO (demo completa)")
        print()
        
        opcion = input("  Selecciona: ").strip()
        
        if opcion == "1":
            await demo_sistema(manager)
        elif opcion == "2":
            await demo_ventanas(manager)
        elif opcion == "3":
            await demo_archivos(manager)
        elif opcion == "4":
            await demo_memoria(manager)
        elif opcion == "5":
            await demo_web(manager)
        elif opcion == "6":
            await demo_comandos(manager)
        elif opcion == "7":
            await demo_mouse_teclado(manager)
        elif opcion == "0":
            await demo_sistema(manager)
            await demo_ventanas(manager)
            await demo_archivos(manager)
            await demo_memoria(manager)
            await demo_web(manager)
            await demo_comandos(manager)
            await demo_mouse_teclado(manager)
        else:
            print("  Opción no válida")
    
    finally:
        await manager.stop_all()
    
    print("\n" + "=" * 60)
    print("  🎬  Demo finalizado!")
    print("  Ahora prueba con Ollama: python mcp_ollama_client.py")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
