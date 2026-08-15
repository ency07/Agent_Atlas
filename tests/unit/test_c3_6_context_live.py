#!/usr/bin/env python3
"""Test C3-6: Contexto vivo."""
import sys
sys.path.insert(0, "E:/Agente_IA")
import atlas_context_live

def test_live_context_structure():
    ctx = atlas_context_live.get_live_context()
    assert "timestamp" in ctx
    assert "active_contracts" in ctx
    assert "recent_errors" in ctx
    assert "eval_deadlines" in ctx
    assert "debt_deadlines" in ctx
    print("OK live context structure")

def test_active_contracts_list():
    contracts = ctx["active_contracts"]
    assert isinstance(contracts, list)
    for c in contracts:
        assert "task_id" in c
        assert "pct" in c
        assert "pending" in c
    print("OK active contracts list")

if __name__ == "__main__":
    test_live_context_structure()
    # need ctx variable
    ctx = atlas_context_live.get_live_context()
    test_active_contracts_list()
    print("\nAll C3-6 tests passed!")