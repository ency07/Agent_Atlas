#!/usr/bin/env python3
"""Test C3-3: Auto-modelo de capacidades REAL."""
import sys, json
sys.path.insert(0, "E:/Agente_IA")
import atlas_capabilities_real

def test_real_caps_structure():
    caps = atlas_capabilities_real.get_real_capabilities()
    assert "enabled_mcps" in caps
    assert "components" in caps
    assert "skills" in caps
    assert "tools" in caps
    print("OK get_real_capabilities structure")

def test_can_use_existing():
    # capacidad conocida presente en self_model components
    res = atlas_capabilities_real.can_use("event_ingest")
    assert "available" in res
    assert "enabled_mcps" in res
    print(f"OK can_use event_ingest -> available={res['available']}")

def test_can_use_nonexistent():
    res = atlas_capabilities_real.can_use("capacidad_inexistente_xyz")
    assert res["available"] is False
    print("OK can_use nonexistent returns false")

def test_enabled_mcps_list():
    caps = atlas_capabilities_real.get_real_capabilities()
    # al menos memory mcp debería estar habilitado
    enabled = caps["enabled_mcps"]
    assert isinstance(enabled, list)
    print(f"OK enabled_mcps list: {enabled}")

if __name__ == "__main__":
    test_real_caps_structure()
    test_can_use_existing()
    test_can_use_nonexistent()
    test_enabled_mcps_list()
    print("\nAll C3-3 tests passed!")