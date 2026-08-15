#!/usr/bin/env python3
"""
atlas_ontology.py — Carga y resolución de ontología personal (C3-4).
"""
import re
from pathlib import Path
from typing import Dict, Optional

ROOT = Path(__file__).parent
ONTOLOGY_FILE = ROOT / "memory_data" / "vault" / "global" / "preferences" / "ontologia.md"

_cache: Optional[Dict[str, str]] = None

def _load() -> Dict[str, str]:
    global _cache
    if _cache is not None:
        return _cache
    mapping = {}
    if ONTOLOGY_FILE.exists():
        content = ONTOLOGY_FILE.read_text(encoding="utf-8")
        # parse lines like "- **mi navegador** → `opera.exe`"
        for line in content.splitlines():
            m = re.match(r"\s*-\s*\*\*(.+?)\*\*\s*→\s*`(.+?)`", line)
            if m:
                key = m.group(1).strip().lower()
                val = m.group(2).strip()
                mapping[key] = val
    _cache = mapping
    return mapping

def resolve(term: str) -> Optional[str]:
    """Resuelve un término coloquial a su entidad real."""
    mapping = _load()
    term_l = term.strip().lower()
    # exact
    if term_l in mapping:
        return mapping[term_l]
    # fuzzy: contains
    for k, v in mapping.items():
        if k in term_l or term_l in k:
            return v
    return None

def all_mappings() -> Dict[str, str]:
    return _load()

def reload():
    global _cache
    _cache = None
    _load()

# CLI
if __name__ == "__main__":
    import sys, json
    if "--resolve" in sys.argv:
        term = ""
        for i,a in enumerate(sys.argv):
            if a == "--resolve" and i+1 < len(sys.argv):
                term = sys.argv[i+1]
        res = resolve(term)
        print(json.dumps({"term": term, "resolved": res}, ensure_ascii=False, indent=2))
    elif "--list" in sys.argv:
        print(json.dumps(all_mappings(), ensure_ascii=False, indent=2))
    else:
        print("Uso: python atlas_ontology.py --resolve \"mi navegador\" | --list")