#!/usr/bin/env python3
"""Test C3-8: Aprendizaje de fallos en vivo."""
import sys, json, os
sys.path.insert(0, "E:/Agente_IA")
import atlas_failure_learning

def test_register_new_failure():
    res = atlas_failure_learning.register_failure("test_tool", "Error de prueba único")
    assert res["tool"] == "test_tool"
    assert res["already_seen"] is False
    assert res["retry_allowed"] is True
    print("OK new failure registered, retry allowed")

def test_duplicate_failure_blocked():
    # register same error again
    res1 = atlas_failure_learning.register_failure("tool2", "Otro error duplicado")
    res2 = atlas_failure_learning.register_failure("tool2", "Otro error duplicado")
    assert res1["already_seen"] is False
    assert res2["already_seen"] is True
    assert res2["retry_allowed"] is False
    print("OK duplicate failure blocked from retry")

def test_can_retry():
    assert atlas_failure_learning.can_retry("tool3", "error nuevo") is True
    # register then check
    atlas_failure_learning.register_failure("tool3", "error nuevo")
    assert atlas_failure_learning.can_retry("tool3", "error nuevo") is False
    print("OK can_retry works")

def test_failure_log_written():
    log_path = "E:/Agente_IA/memory_data/state/failure_learning.jsonl"
    assert os.path.exists(log_path)
    with open(log_path, "r", encoding="utf-8") as f:
        lines = f.read().strip().splitlines()
    assert len(lines) >= 1
    print("OK failure_learning.jsonl written")

def test_friction_log_entry():
    # friction_log should have a correccion entry for tool2
    fr_path = "E:/Agente_IA/memory_data/state/friction_log.jsonl"
    assert os.path.exists(fr_path)
    with open(fr_path, "r", encoding="utf-8") as f:
        lines = f.read().strip().splitlines()
    # find last entry with tool2
    found = False
    for line in reversed(lines):
        entry = json.loads(line)
        if entry.get("meta", {}).get("tool") == "tool2":
            found = True
            break
    assert found
    print("OK friction_log entry created")

if __name__ == "__main__":
    test_register_new_failure()
    test_duplicate_failure_blocked()
    test_can_retry()
    test_failure_log_written()
    test_friction_log_entry()
    print("\nAll C3-8 tests passed!")