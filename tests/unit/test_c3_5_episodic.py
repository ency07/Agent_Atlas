#!/usr/bin/env python3
"""Test C3-5: Memoria episódica."""
import sys
sys.path.insert(0, "E:/Agente_IA")
import atlas_episodic

def test_find_similar_returns_list():
    res = atlas_episodic.find_similar("crear archivo de prueba")
    assert isinstance(res, list)
    print(f"OK find_similar returns list ({len(res)} items)")

def test_structure_of_items():
    res = atlas_episodic.find_similar("crear archivo de prueba")
    for item in res:
        assert "type" in item
        assert "id" in item
        assert "title" in item
        assert "score" in item
    print("OK items have required fields")

def test_score_positive():
    res = atlas_episodic.find_similar("crear archivo de prueba")
    for item in res:
        assert item["score"] > 0
    print("OK scores positive")

if __name__ == "__main__":
    test_find_similar_returns_list()
    test_structure_of_items()
    test_score_positive()
    print("\nAll C3-5 tests passed!")