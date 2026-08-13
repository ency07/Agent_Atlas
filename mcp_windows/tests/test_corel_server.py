#!/usr/bin/env python3
"""Test end-to-end del servidor CorelDRAW via MultiServerManager."""
import asyncio
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, str(Path(__file__).parent.parent))

from mcp_multi_server import MultiServerManager

failures = 0


def check(name, result_text):
    global failures
    try:
        data = json.loads(result_text)
    except json.JSONDecodeError:
        print(f"  ❌ {name}: respuesta no JSON: {result_text[:150]}")
        failures += 1
        return None
    if "error" in data:
        print(f"  ❌ {name}: {data['error']}")
        failures += 1
        return None
    print(f"  ✅ {name}: {json.dumps(data, ensure_ascii=False)[:140]}")
    return data


async def call(manager, tool, args=None):
    result = await manager.call_tool(tool, args or {})
    return "".join(i.text for i in result.content if hasattr(i, "text"))


async def main():
    global failures
    manager = MultiServerManager(enabled_servers=["corel-draw"])
    try:
        results = await manager.start_all()
        assert results.get("corel-draw", 0) > 0, "corel-draw no arrancó"
        print(f"Servidor corel-draw: {results['corel-draw']} tools\n")

        check("ping", await call(manager, "corel_ping"))
        check("create_document", await call(manager, "corel_create_document",
              {"name": "Test_MCP_Server", "width": 210, "height": 297}))
        check("add_text", await call(manager, "corel_add_text",
              {"text": "MCP COREL", "x": 30, "y": 200, "font_name": "Impact",
               "font_size": 72, "color_hex": "#e67e22", "bold": True}))
        check("add_rectangle", await call(manager, "corel_add_rectangle",
              {"x": 20, "y": 150, "width": 100, "height": 30, "fill_hex": "#1a5276"}))
        check("select_all", await call(manager, "corel_select_all"))
        check("center_on_page", await call(manager, "corel_center_on_page"))
        check("document_info", await call(manager, "corel_get_document_info"))

        out = Path.home() / "Desktop" / "test_mcp_corel_server.png"
        data = check("export_png_300dpi", await call(manager, "corel_export_png",
                     {"file_path": str(out), "dpi": 300, "transparent": True}))
        if data and out.exists() and out.stat().st_size > 10000:
            print(f"  ✅ PNG verificado en disco: {out.stat().st_size} bytes")
        elif data:
            print("  ❌ PNG no se creó correctamente")
            failures += 1

        check("convert_to_curves", await call(manager, "corel_convert_to_curves"))
        check("list_objects", await call(manager, "corel_list_objects"))
    finally:
        await manager.stop_all()

    print()
    if failures:
        print(f"❌ {failures} FALLOS")
        sys.exit(1)
    print("✅ TEST COREL SERVER COMPLETO")


asyncio.run(main())
