#!/usr/bin/env python3
"""Test C3-10: Gestión de contexto sesiones largas."""
import sys, os
sys.path.insert(0, "E:/Agente_IA")
import atlas_session_context

def test_add_and_context():
    atlas_session_context.clear_session()
    atlas_session_context.add_message("user", "hola mundo")
    atlas_session_context.add_message("assistant", "hola!")
    ctx = atlas_session_context.get_context()
    assert "summary" in ctx
    assert "recent_messages" in ctx
    assert len(ctx["recent_messages"]) == 2
    print("OK add_message and get_context")

def test_summary_generation():
    atlas_session_context.clear_session()
    # add many messages to trigger summary
    for i in range(60):
        atlas_session_context.add_message("user", f"mensaje {i}")
    ctx = atlas_session_context.get_context()
    assert ctx["summary"] != ""
    assert ctx["total_messages"] >= 60
    print("OK summary generated after threshold")

def test_old_messages_pruned():
    # after many messages and summary, old ones should be pruned after 2h simulated
    # we can't easily simulate time, but ensure deque maxlen works
    atlas_session_context.clear_session()
    for i in range(250):
        atlas_session_context.add_message("user", f"msg {i}")
    ctx = atlas_session_context.get_context()
    assert len(ctx["recent_messages"]) <= 200
    print("OK maxlen respected")

if __name__ == "__main__":
    test_add_and_context()
    test_summary_generation()
    test_old_messages_pruned()
    print("\nAll C3-10 tests passed!")