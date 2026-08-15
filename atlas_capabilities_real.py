#!/usr/bin/env python3
"""
atlas_capabilities_real.py — Auto-modelo de capacidades REAL.
C3-3: Cruza MCPs habilitados en opencode.jsonc + tools + skills.
Nunca promete manos que no tiene (playwright-npx/ollama MCP deshabilitados → no se ofrecen).
"""
import json
import os
import re
from pathlib import Path
from typing import Dict, List, Any, Set

ROOT = Path(__file__).parent
OPENCODE_CFG_CANDIDATES = [
    Path(os.environ.get("APPDATA", "")) / "opencode" / "opencode.jsonc",
    Path.home() / ".config" / "opencode" / "opencode.jsonc",
    ROOT / "opencode.jsonc",
]

def _load_opencode_config() -> Dict[str, Any]:
    for p in OPENCODE_CFG_CANDIDATES:
        if p.exists():
            try:
                txt = p.read_text(encoding="utf-8")
                # strip comments simple
                txt = re.sub(r'//.*', '', txt)
                txt = re.sub(r'/\*.*?\*/', '', txt, flags=re.DOTALL)
                return json.loads(txt)
            except Exception:
                continue
    return {}

def _enabled_mcp_names(config: Dict[str, Any]) -> Set[str]:
    """Devuelve nombres de MCP servers habilitados (clave 'mcpServers')."""
    enabled = set()
    mcps = config.get("mcpServers", {})
    for name, info in mcps.items():
        # si tiene "disabled": true omitir
        if isinstance(info, dict) and info.get("disabled") is True:
            continue
        enabled.add(name)
    return enabled

# Cargar self_model para caps
SELF_MODEL = ROOT / "self_model.json"
_self_model: Dict[str, Any] = {}
if SELF_MODEL.exists():
    try:
        _self_model = json.loads(SELF_MODEL.read_text(encoding="utf-8"))
    except Exception:
        _self_model = {}

def get_real_capabilities() -> Dict[str, Any]:
    """Construye mapa de capacidades reales basado en MCPs habilitados + skills."""
    config = _load_opencode_config()
    enabled = _enabled_mcp_names(config)
    caps = {
        "enabled_mcps": sorted(list(enabled)),
        "components": [],
        "skills": [],
        "tools": [],
    }
    # Filtrar componentes de self_model que correspondan a MCPs habilitados
    for comp in _self_model.get("components", []):
        comp_name = comp.get("name", "")
        # heurística: si el nombre del componente coincide con un MCP habilitado
        if any(en in comp_name.lower() for en in enabled):
            caps["components"].append(comp)
    # Skills: si skill name coincide con mcp habilitado
    for skill in _self_model.get("skills", []):
        if any(en in skill.lower() for en in enabled):
            caps["skills"].append(skill)
    # Tools: from components tools
    for comp in caps["components"]:
        caps["tools"].extend(comp.get("provides", []))
    return caps

def can_use(capability: str) -> Dict[str, Any]:
    """Responde si una capacidad está disponible según MCPs habilitados."""
    caps = get_real_capabilities()
    # búsqueda simple en tools, components, skills
    found = False
    details = []
    for comp in caps["components"]:
        provides = comp.get("provides", [])
        if any(capability.lower() in p.lower() for p in provides):
            found = True
            details.append(f"component:{comp['name']}")
    for skill in caps["skills"]:
        if capability.lower() in skill.lower():
            found = True
            details.append(f"skill:{skill}")
    return {
        "capability": capability,
        "available": found,
        "enabled_mcps": caps["enabled_mcps"],
        "details": details,
    }

# CLI
if __name__ == "__main__":
    import sys
    if "--caps" in sys.argv:
        print(json.dumps(get_real_capabilities(), ensure_ascii=False, indent=2))
    elif "--can" in sys.argv:
        cap = ""
        for i,a in enumerate(sys.argv):
            if a == "--can" and i+1 < len(sys.argv):
                cap = sys.argv[i+1]
        print(json.dumps(can_use(cap), ensure_ascii=False, indent=2))
    else:
        print("Uso: python atlas_capabilities_real.py --caps | --can <capacidad>")