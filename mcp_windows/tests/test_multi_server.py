#!/usr/bin/env python3
"""
Test de verificación: gestor multi-servidor y sistema de seguridad.

No requiere Ollama ni interacción. Verifica:
  1. Los servidores MCP arrancan y listan tools (regresión: cancel scope bug).
  2. El sistema de niveles de riesgo clasifica correctamente.
  3. Las whitelists funcionan.

Uso:
    python tests/test_multi_server.py
"""
import asyncio
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, str(Path(__file__).parent.parent))

failures = 0


def check(name: str, condition: bool, detail: str = "") -> None:
    global failures
    if condition:
        print(f"  ✅ {name}")
    else:
        print(f"  ❌ {name} {detail}")
        failures += 1


async def test_servers() -> None:
    from mcp_multi_server import MultiServerManager

    print("1/3 Arranque de servidores (regresión: cancel scope)...")
    manager = MultiServerManager(enabled_servers=["windows-automation"])
    try:
        results = await manager.start_all()
        check("windows-automation arranca", results.get("windows-automation", 0) > 0,
              f"tools={results}")

        tools = await manager.list_all_tools()
        names = {t["name"] for t in tools}
        expected = {"docx_create", "xlsx_create", "pptx_create", "pdf_create",
                    "open_program", "web_fetch", "run_script"}
        check("tools de documentos/programas registradas", expected.issubset(names),
              f"faltan: {expected - names}")

        # Verificar que call_tool funciona end-to-end con una tool informativa
        result = await manager.call_tool("system_info", {})
        text = "".join(item.text for item in result.content if hasattr(item, "text"))
        check("system_info responde JSON válido", '"memory"' in text or '"system"' in text)
    finally:
        await manager.stop_all()
    print("  ✅ Cierre limpio sin errores de cancel scope")


def test_risk_levels() -> None:
    print("2/3 Niveles de riesgo...")
    import mcp_ollama_client as client

    check("file_delete es CRITICAL",
          client.TOOL_RISK_LEVELS.get("file_delete") == client.RISK_CRITICAL)
    check("docx_create es HIGH",
          client.TOOL_RISK_LEVELS.get("docx_create") == client.RISK_HIGH)
    check("open_program es MEDIUM",
          client.TOOL_RISK_LEVELS.get("open_program") == client.RISK_MEDIUM)
    check("system_info es LOW",
          client.TOOL_RISK_LEVELS.get("system_info") == client.RISK_LOW)


def test_whitelist() -> None:
    print("3/3 Whitelists...")
    import mcp_ollama_client as client

    check("Desktop está en whitelist",
          client.is_whitelisted("file_write", {"path": r"C:\Users\X\Desktop\nota.txt"}))
    check("System32 NO está en whitelist",
          not client.is_whitelisted("file_write", {"path": r"C:\Windows\System32\x.dll"}))
    check("notepad.exe está en whitelist",
          client.is_whitelisted("process_start", {"command": "notepad.exe"}))
    check("proceso desconocido NO está en whitelist",
          not client.is_whitelisted("process_start", {"command": "malware.exe"}))


if __name__ == "__main__":
    asyncio.run(test_servers())
    test_risk_levels()
    test_whitelist()

    print()
    if failures:
        print(f"❌ {failures} FALLOS")
        sys.exit(1)
    print("✅ TODOS LOS TESTS PASARON")
