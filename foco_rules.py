#!/usr/bin/env python3
"""
foco_rules.py — Clasificador de actividad para Atlas F3 (FOCO).

Clasifica eventos de actividad como monetizable/distracción
según reglas editables en state/foco_rules.json.

Uso como módulo:
    from foco_rules import load_rules, classify, set_mode
    cat, mon = classify("opera.exe", "GitHub - repo", rules)

Uso standalone (verificar integridad):
    python foco_rules.py --validate
"""

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Tuple

MEMORY_ROOT = Path(os.environ.get("MEMORY_ROOT", str(Path(__file__).parent / "memory_data"))).resolve()
STATE_DIR = MEMORY_ROOT / "state"
RULES_FILE = STATE_DIR / "foco_rules.json"

DEFAULT_RULES = {
    "mode": "soft",
    "categories": {
        "dev": {"monetizable": True, "apps": ["code.exe", "opencode.exe", "python.exe"]},
        "research": {"monetizable": True, "apps": ["opera.exe", "chrome.exe"]},
        "comms": {"monetizable": False, "apps": ["whatsapp.exe", "teams.exe"]},
        "social": {"monetizable": False, "apps": ["youtube.exe", "reddit.exe"]},
    },
    "default_category": "other",
    "thresholds": {
        "distraction_alert_after_seconds": 180,
        "distraction_strict_after_seconds": 60,
        "notices_per_day": 3,
        "focus_session_target_minutes": 50,
    },
    "exceptions": {
        "apps": ["KeePassXC.exe"],
        "titles_include": ["contraseñas", "login", "2fa"],
    },
}

_rules_cache = None
_rules_mtime = 0.0


def load_rules() -> Dict:
    global _rules_cache, _rules_mtime
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    if RULES_FILE.exists():
        try:
            mtime = RULES_FILE.stat().st_mtime
            if _rules_cache and _rules_mtime == mtime:
                return _rules_cache
            raw = RULES_FILE.read_text(encoding="utf-8")
            rules = json.loads(raw)
            _rules_cache = _rules_cache if not rules else rules
            _rules_mtime = mtime
            return rules
        except Exception:
            pass
    return DEFAULT_RULES.copy()


def save_rules(rules: Dict) -> None:
    global _rules_cache, _rules_mtime
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    RULES_FILE.write_text(json.dumps(rules, indent=2, ensure_ascii=False), encoding="utf-8")
    _rules_cache = rules
    _rules_mtime = RULES_FILE.stat().st_mtime


def set_mode(mode: str) -> Dict:
    rules = load_rules()
    mode = mode.lower()
    if mode not in ("off", "soft", "strict"):
        return {"error": f"Modo inválido: {mode}. Usa: off, soft, strict"}
    rules["mode"] = mode
    save_rules(rules)
    return {"mode": mode}


def get_mode(rules: Dict = None) -> str:
    if rules is None:
        rules = load_rules()
    return rules.get("mode", "soft")


def get_thresholds(rules: Dict = None) -> Dict:
    if rules is None:
        rules = load_rules()
    return rules.get("thresholds", DEFAULT_RULES["thresholds"])


def _is_exception(app: str, title: str, rules: Dict) -> bool:
    exc = rules.get("exceptions", {})
    app = app or ""
    title = title or ""
    app_lower = app.lower()
    for e in exc.get("apps", []):
        if e.lower() in app_lower or app_lower in e.lower():
            return True
    title_lower = title.lower()
    for kw in exc.get("titles_include", []):
        if kw.lower() in title_lower:
            return True
    return False


def _match_app(app: str, cat_rules: Dict) -> bool:
    if not app:
        return False
    app_lower = app.lower()
    for known in cat_rules.get("apps", []):
        if known.lower() in app_lower or app_lower in known.lower():
            return True
    return False


def _match_title(title: str, cat_rules: Dict) -> bool:
    if not title:
        return False
    title_lower = title.lower()
    for kw in cat_rules.get("title_include", []):
        if kw.lower() in title_lower:
            return True
    return False


def classify(app: str, title: str = "", rules: Dict = None) -> Tuple[str, bool]:
    """
    Clasifica un evento de actividad.

    Orden: excepciones → match por título (pestañas de navegador, más preciso)
    → match por app → default.

    Returns:
        (category, monetizable)
    """
    if rules is None:
        rules = load_rules()

    if _is_exception(app, title, rules):
        return ("exception", False)

    cats = rules.get("categories", {})

    for cat_name, cat_rules in cats.items():
        if _match_title(title, cat_rules):
            return (cat_name, cat_rules.get("monetizable", False))

    for cat_name, cat_rules in cats.items():
        if _match_app(app, cat_rules):
            return (cat_name, cat_rules.get("monetizable", False))

    default = rules.get("default_category", "other")
    return (default, False)


def classify_event(event: Dict, rules: Dict = None) -> Dict:
    """
    Clasifica un evento de inbox y devuelve el dict enriquecido.
    No modifica el dict original — devuelve copia.
    """
    if rules is None:
        rules = load_rules()
    ev = dict(event)
    cat, mon = classify(ev.get("app", ""), ev.get("window_title", ""), rules)
    ev["category"] = cat
    ev["monetizable"] = mon
    return ev


def check_budget(events_today: List[Dict], rules: Dict = None) -> Dict:
    """
    Verifica presupuesto de avisos de hoy.

    Returns:
        {"used": int, "remaining": int, "limit": int, "budget_ok": bool}
    """
    if rules is None:
        rules = load_rules()
    limit = rules.get("thresholds", {}).get("notices_per_day", 3)
    used = sum(1 for e in events_today if e.get("type") == "focus_notice")
    remaining = max(0, limit - used)
    return {"used": used, "remaining": remaining, "limit": limit, "budget_ok": remaining > 0}


def daily_summary(events: List[Dict], rules: Dict = None) -> Dict:
    """
    Calcula resumen diario de foco.

    Returns:
        {
            "total_seconds": int,
            "productive_seconds": int,
            "distraction_seconds": int,
            "other_seconds": int,
            "focus_pct": float,
            "top_distractions": [{"app": str, "seconds": int, "category": str}],
            "top_productive": [{"app": str, "seconds": int, "category": str}],
            "mode": str,
        }
    """
    if rules is None:
        rules = load_rules()

    total = 0
    by_cat_seconds = {}
    by_app_seconds = {}

    for ev in events:
        dur = ev.get("duration_seconds", 0)
        if dur <= 0:
            continue
        total += dur
        cat = ev.get("category")
        app = ev.get("app", "")
        mon = ev.get("monetizable", False)

        if cat is None:
            cat, mon = classify(app, ev.get("window_title", ""), rules)

        key = "productive" if mon else "distraction"
        if cat == "exception":
            key = "other"
        if cat == "other":
            key = "other"

        by_cat_seconds[key] = by_cat_seconds.get(key, 0) + dur
        by_app_seconds[app] = by_app_seconds.get(app, 0) + dur

    prod = by_cat_seconds.get("productive", 0)
    distract = by_cat_seconds.get("distraction", 0)
    other = by_cat_seconds.get("other", 0)

    top_dist = []
    for a, s in sorted(by_app_seconds.items(), key=lambda x: -x[1]):
        cat, mon = classify(a, "", rules)
        if mon is False and cat not in ("other", "exception"):
            top_dist.append({"app": a, "seconds": s})
        if len(top_dist) >= 5:
            break

    top_prod = []
    for a, s in sorted(by_app_seconds.items(), key=lambda x: -x[1]):
        cat, mon = classify(a, "", rules)
        if mon is True:
            top_prod.append({"app": a, "seconds": s})
        if len(top_prod) >= 5:
            break

    pct = round((prod / total * 100) if total > 0 else 0, 1)

    return {
        "total_seconds": total,
        "productive_seconds": prod,
        "distraction_seconds": distract,
        "other_seconds": other,
        "focus_pct": pct,
        "top_distractions": top_dist,
        "top_productive": top_prod,
        "mode": rules.get("mode", "soft"),
    }


def validate_rules(rules: Dict) -> List[str]:
    """Valida la estructura de reglas. Devuelve lista de errores (vacía = OK)."""
    errors = []
    if "mode" not in rules:
        errors.append("Falta campo 'mode'")
    elif rules["mode"] not in ("off", "soft", "strict"):
        errors.append(f"mode inválido: {rules['mode']}")

    cats = rules.get("categories")
    if not cats or not isinstance(cats, dict):
        errors.append("Falta 'categories' o no es dict")
    else:
        for name, cat in cats.items():
            if "monetizable" not in cat:
                errors.append(f"Categoría '{name}' sin campo 'monetizable'")
            if "apps" not in cat or not isinstance(cat["apps"], list):
                errors.append(f"Categoría '{name}' sin lista 'apps'")

    thresh = rules.get("thresholds", {})
    if not isinstance(thresh, dict):
        errors.append("'thresholds' no es dict")
    else:
        for k in ("notices_per_day", "distraction_alert_after_seconds"):
            if k not in thresh:
                errors.append(f"Falta threshold '{k}'")

    exc = rules.get("exceptions", {})
    if not isinstance(exc, dict):
        errors.append("'exceptions' no es dict")

    return errors


# --- CLI ---
if __name__ == "__main__":
    import sys
    if "--validate" in sys.argv:
        rules = load_rules()
        errs = validate_rules(rules)
        if errs:
            print("ERRORES:")
            for e in errs:
                print(f"  - {e}")
            sys.exit(1)
        else:
            print("OK")
            print(f"  mode: {rules['mode']}")
            print(f"  categorías: {len(rules.get('categories', {}))}")
            print(f"  default: {rules.get('default_category', 'other')}")
    elif "--test" in sys.argv:
        rules = load_rules()
        tests = [
            ("code.exe", "main.py — VS Code", "dev", True),
            ("opera.exe", "GitHub - repo", "research", True),
            ("chrome.exe", "Video tutorial - YouTube", "social", False),
            ("chrome.exe", "GitHub - stackoverflow question", "research", True),
            ("teams.exe", "", "comms", False),
            ("KeePassXC.exe", "contraseñas", "exception", False),
            ("desconocido.exe", "", "other", False),
        ]
        ok = 0
        for app, title, expect_cat, expect_mon in tests:
            cat, mon = classify(app, title, rules)
            passed = (cat == expect_cat and mon == expect_mon)
            status = "PASS" if passed else "FAIL"
            print(f"  [{status}] ({app}, {title!r}) -> ({cat}, {mon})")
            if passed:
                ok += 1
        print(f"\n{ok}/{len(tests)} passed")
        sys.exit(0 if ok == len(tests) else 1)
    else:
        print("Uso: python foco_rules.py --validate | --test")
