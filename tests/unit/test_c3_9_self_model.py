#!/usr/bin/env python3
"""Test C3-9: self_model.json exists and has required keys."""
import sys, json
sys.path.insert(0, "E:/Agente_IA")

def test_self_model_exists():
    path = "E:/Agente_IA/self_model.json"
    assert os.path.exists(path)
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    assert "components" in data
    assert "configs" in data
    assert "flows" in data
    assert "debts" in data
    assert "capabilities" in data
    assert "limits" in data
    print("OK self_model.json exists with required keys")

if __name__ == "__main__":
    import os
    test_self_model_exists()
    print("\nAll C3-9 tests passed!")