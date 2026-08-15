#!/usr/bin/env python3
"""Test C3-4: Ontología personal resuelta."""
import sys
sys.path.insert(0, "E:/Agente_IA")
import atlas_ontology

def test_resolve_known():
    assert atlas_ontology.resolve("mi navegador") == "opera.exe"
    assert atlas_ontology.resolve("el editor") == "code.exe"
    assert atlas_ontology.resolve("la app de diseño") == "coreldrw.exe"
    print("OK known terms resolve")

def test_fuzzy():
    # fuzzy match
    assert atlas_ontology.resolve("navegador") == "opera.exe"
    assert atlas_ontology.resolve("editor") == "code.exe"
    print("OK fuzzy match works")

def test_unknown_returns_none():
    assert atlas_ontology.resolve("cosa desconocida") is None
    print("OK unknown returns None")

def test_list_all():
    mapping = atlas_ontology.all_mappings()
    assert isinstance(mapping, dict) and len(mapping) > 0
    print(f"OK list_all returns {len(mapping)} mappings")

if __name__ == "__main__":
    test_resolve_known()
    test_fuzzy()
    test_unknown_returns_none()
    test_list_all()
    print("\nAll C3-4 tests passed!")