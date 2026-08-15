#!/usr/bin/env python3
"""
atlas_episodic.py — Memoria episódica (C3-5).
Vincula pedido actual con contratos/notas similares pasadas (éxito/fallo/runbook).
"""
import json
import re
from pathlib import Path
from typing import List, Dict, Any

ROOT = Path(__file__).parent
STATE_DIR = ROOT / "memory_data" / "state"
VAULT_GLOBAL = ROOT / "memory_data" / "vault" / "global"
CONTRACTS_DIR = STATE_DIR / "tasks"
NOTES_DIR = VAULT_GLOBAL / "notes"
DECISIONS_DIR = VAULT_GLOBAL / "decisions"

def _tokenize(text: str) -> List[str]:
    return set(re.findall(r"\w+", text.lower()))

def _load_contracts() -> List[Dict[str, Any]]:
    items = []
    if CONTRACTS_DIR.exists():
        for f in CONTRACTS_DIR.glob("*.json"):
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                data["_source"] = "contract"
                data["_file"] = f.name
                items.append(data)
            except Exception:
                pass
    return items

def _load_notes(dir_path: Path, source: str) -> List[Dict[str, Any]]:
    items = []
    if dir_path.exists():
        for f in dir_path.glob("*.md"):
            try:
                content = f.read_text(encoding="utf-8")
                # extraer frontmatter simple
                fm = {}
                if content.startswith("---"):
                    parts = content.split("---", 2)
                    if len(parts) >= 3:
                        for line in parts[1].splitlines():
                            if ":" in line:
                                k,v = line.split(":",1)
                                fm[k.strip()] = v.strip().strip('"')
                items.append({
                    "_source": source,
                    "_file": f.name,
                    "title": fm.get("title", f.stem),
                    "content": content,
                    "tags": fm.get("tags",""),
                })
            except Exception:
                pass
    return items

def _similarity(query_tokens: set, target_tokens: set) -> float:
    if not query_tokens or not target_tokens:
        return 0.0
    inter = query_tokens & target_tokens
    return len(inter) / len(query_tokens | target_tokens)

def find_similar(task_text: str, top_k: int = 5) -> List[Dict[str, Any]]:
    """Busca contratos/notas/decisiones similares al texto de la tarea."""
    qtokens = _tokenize(task_text)
    results = []

    # contratos
    for c in _load_contracts():
        text = f"{c.get('orden_literal','')} {' '.join([cr.get('descripcion','') for cr in c.get('criterios',[])])}"
        score = _similarity(qtokens, _tokenize(text))
        if score > 0.1:
            results.append({
                "type": "contract",
                "id": c.get("task_id"),
                "title": c.get("orden_literal","")[:80],
                "state": c.get("estado"),
                "score": round(score,3),
                "file": c.get("_file"),
            })

    # notas
    for n in _load_notes(NOTES_DIR, "note"):
        score = _similarity(qtokens, _tokenize(n.get("content","") + " " + n.get("title","")))
        if score > 0.1:
            results.append({
                "type": "note",
                "id": n.get("_file"),
                "title": n.get("title"),
                "score": round(score,3),
                "file": n.get("_file"),
            })

    # decisiones
    for n in _load_notes(DECISIONS_DIR, "decision"):
        score = _similarity(qtokens, _tokenize(n.get("content","") + " " + n.get("title","")))
        if score > 0.1:
            results.append({
                "type": "decision",
                "id": n.get("_file"),
                "title": n.get("title"),
                "score": round(score,3),
                "file": n.get("_file"),
            })

    results.sort(key=lambda x: x["score"], reverse=True)
    return results[:top_k]

# CLI
if __name__ == "__main__":
    import sys, json
    if len(sys.argv) < 2:
        print("Uso: python atlas_episodic.py \"texto de la tarea\"")
        sys.exit(1)
    task = " ".join(sys.argv[1:])
    res = find_similar(task)
    print(json.dumps(res, ensure_ascii=False, indent=2))