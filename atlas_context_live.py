#!/usr/bin/env python3
"""
atlas_context_live.py — Contexto vivo (C3-6).
Contratos C2 activos (% y pendientes) + errores recientes + deadlines (evals, DEBTs).
"""
import json
from pathlib import Path
from typing import List, Dict, Any
from datetime import datetime, timezone

ROOT = Path(__file__).parent
STATE_DIR = ROOT / "memory_data" / "state"
CONTRACTS_DIR = STATE_DIR / "tasks"
ERRORS_DB = ROOT / "logs" / "errors.jsonl"
EVALS_DIR = STATE_DIR / "evals"
DEBT_FILE = ROOT / "docs" / "DEBT.md"

def _load_contracts() -> List[Dict[str, Any]]:
    items = []
    if CONTRACTS_DIR.exists():
        for f in CONTRACTS_DIR.glob("*.json"):
            try:
                c = json.loads(f.read_text(encoding="utf-8"))
                items.append(c)
            except Exception:
                pass
    return items

def _active_contracts() -> List[Dict[str, Any]]:
    contracts = _load_contracts()
    active = []
    for c in contracts:
        if c.get("estado") in ("EN_CURSO", "ESCALADA"):
            pendientes = [cr for cr in c.get("criterios", []) if cr.get("estado") not in ("OK","HUMANO")]
            active.append({
                "task_id": c.get("task_id"),
                "orden": c.get("orden_literal","")[:80],
                "pct": c.get("progreso_pct",0),
                "pending": len(pendientes),
                "pending_details": [(cr["id"], cr["estado"]) for cr in pendientes],
                "timeout": c.get("timeout"),
            })
    return active

def _recent_errors(limit: int = 10) -> List[Dict[str, Any]]:
    errs = []
    if ERRORS_DB.exists():
        lines = ERRORS_DB.read_text(encoding="utf-8").strip().splitlines()
        for line in lines[-limit:]:
            try:
                errs.append(json.loads(line))
            except Exception:
                pass
    return list(reversed(errs))

def _eval_deadlines() -> List[Dict[str, Any]]:
    items = []
    if EVALS_DIR.exists():
        for f in EVALS_DIR.glob("*.json"):
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                items.append({"file": f.name, "data": data})
            except Exception:
                pass
    return items

def _debt_deadlines() -> List[Dict[str, Any]]:
    items = []
    if DEBT_FILE.exists():
        content = DEBT_FILE.read_text(encoding="utf-8")
        for line in content.splitlines():
            if "Fecha objetivo:" in line:
                # simple parse
                parts = line.split("Fecha objetivo:")
                if len(parts) == 2:
                    date_str = parts[1].strip().split()[0]
                    try:
                        dt = datetime.fromisoformat(date_str)
                        if dt.tzinfo is None:
                            dt = dt.replace(tzinfo=timezone.utc)
                        items.append({"date": dt.isoformat(), "raw": line.strip()})
                    except Exception:
                        pass
    return items

def get_live_context() -> Dict[str, Any]:
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "active_contracts": _active_contracts(),
        "recent_errors": _recent_errors(),
        "eval_deadlines": _eval_deadlines(),
        "debt_deadlines": _debt_deadlines(),
    }

# CLI
if __name__ == "__main__":
    import sys, json
    ctx = get_live_context()
    print(json.dumps(ctx, ensure_ascii=False, indent=2))