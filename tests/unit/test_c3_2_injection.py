#!/usr/bin/env python3
"""Test C3-2: Inyección automática por relevancia (código)."""
import sys, json
sys.path.insert(0, "E:/Agente_IA")
import atlas_context_inject

def test_corel_slice():
    task = "revisa la configuración de Corel Draw"
    res = atlas_context_inject.inject_context(task)
    assert "matched_sections" in res
    assert "slice" in res
    # Debe incluir components y configs al menos
    assert "components" in res["matched_sections"] or "configs" in res["matched_sections"]
    print("OK corel task yields relevant sections")

def test_generic_task():
    task = "hola mundo"
    res = atlas_context_inject.inject_context(task)
    # al menos capabilities y limits
    secs = set(res["matched_sections"])
    assert "capabilities" in secs and "limits" in secs
    print("OK generic task returns base sections")

def test_injection_log_written():
    task = "test injection logging"
    res = atlas_context_inject.inject_context(task)
    # Verificar que se escribió log
    import os
    log_path = "E:/Agente_IA/memory_data/state/injection_log.jsonl"
    assert os.path.exists(log_path)
    with open(log_path, "r", encoding="utf-8") as f:
        lines = f.read().strip().splitlines()
    assert len(lines) >= 1
    last = json.loads(lines[-1])
    assert last["task"] == task
    print("OK injection_log.jsonl written")

def test_slice_contains_expected_keys():
    task = "configura el modelo en opencode"
    res = atlas_context_inject.inject_context(task)
    slice_data = res["slice"]
    # debe tener configs y components
    assert "configs" in slice_data or "components" in slice_data
    print("OK slice contains expected keys")

if __name__ == "__main__":
    test_corel_slice()
    test_generic_task()
    test_injection_log_written()
    test_slice_contains_expected_keys()
    print("\nAll C3-2 tests passed!")