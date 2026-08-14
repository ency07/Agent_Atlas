# ============================================================
# tests/unit/test_foco.py — Tests de clasificación de foco
# ------------------------------------------------------------
import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from foco_rules import load_rules, classify, validate_rules, set_mode, get_mode

def test_load_rules():
    rules = load_rules()
    assert "categories" in rules
    assert "thresholds" in rules
    assert "mode" in rules

def test_validate_rules():
    rules = load_rules()
    errors = validate_rules(rules)
    assert errors == [], f"Reglas inválidas: {errors}"

def test_classify_known_apps():
    rules = load_rules()
    # Apps conocidas en reglas (coincidencia por nombre parcial)
    cat, mon = classify("code.exe", "", rules)
    assert cat == "dev"
    assert mon == True
    
    cat, mon = classify("opera.exe", "GitHub - repo", rules)
    assert cat == "research"
    assert mon == True
    
    cat, mon = classify("chrome.exe", "YouTube", rules)
    assert cat == "social"
    assert mon == False

def test_classify_unknown_app():
    rules = load_rules()
    cat, mon = classify("unknown_xyz.exe", "", rules)
    assert cat == "other"
    assert mon == False

def test_exceptions():
    rules = load_rules()
    cat, mon = classify("KeePassXC.exe", "contraseñas", rules)
    assert cat == "exception"
    assert mon == False

def test_set_mode():
    # Test modo soft
    result = set_mode("soft")
    assert result["mode"] == "soft"
    rules = load_rules()
    assert get_mode(rules) == "soft"
    
    # Test modo strict
    result = set_mode("strict")
    assert result["mode"] == "strict"
    rules = load_rules()
    assert get_mode(rules) == "strict"

def test_invalid_mode():
    result = set_mode("invalid")
    assert "error" in result

if __name__ == "__main__":
    test_load_rules()
    test_validate_rules()
    test_classify_known_apps()
    test_classify_unknown_app()
    test_exceptions()
    test_set_mode()
    test_invalid_mode()
    print("✅ tests/unit/test_foco.py: OK")