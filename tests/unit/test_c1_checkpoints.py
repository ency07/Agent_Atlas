# ============================================================
# tests/unit/test_c1_checkpoints.py — REQ-C13 tareas reanudables
# ------------------------------------------------------------
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import atlas_checkpoints as cp

TASK = "test-c1-task"


def setup_function():
    cp.clear(TASK)


def teardown_function():
    cp.clear(TASK)


def test_save_and_resume():
    cp.save(TASK, steps=["a", "b", "c"], current_step=1,
            context={"file": "x.html"}, note="mitad")
    r = cp.resume(TASK)
    assert r is not None
    assert r["current_step"] == 1
    assert r["context"]["file"] == "x.html"
    assert len(r["steps"]) == 3
    assert r["status"] == "in_progress"


def test_resume_missing():
    assert cp.resume("no-existe-xyz") is None


def test_advance_keeps_context():
    cp.save(TASK, steps=["a", "b"], current_step=0, context={"k": "v1"})
    cp.advance(TASK, context={"k2": "v2"}, note="nuevo")
    r = cp.resume(TASK)
    assert r["current_step"] == 1
    assert r["context"]["k"] == "v1"      # contexto anterior preservado
    assert r["context"]["k2"] == "v2"     # contexto nuevo fusionado


def test_list_all_and_clear():
    cp.save(TASK, steps=["a"], current_step=0)
    lst = cp.list_all()
    assert TASK in lst
    assert lst[TASK]["status"] == "in_progress"
    assert cp.clear(TASK) is True
    assert cp.load(TASK) is None
