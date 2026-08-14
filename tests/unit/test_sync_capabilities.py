# ============================================================
# tests/unit/test_sync_capabilities.py — Tests de auto-sync
# ------------------------------------------------------------
import sys
import json
import tempfile
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import atlas_sync_capabilities as sc


def test_infer_capability_vision():
    caps = sc.infer_capability("gpt-4o", {})
    assert caps["vision"] == True


def test_infer_capability_reasoning():
    caps = sc.infer_capability("deepseek-r1", {})
    assert caps["reasoning"] == True


def test_infer_capability_coding():
    caps = sc.infer_capability("best-coding", {})
    assert caps["coding"] == 0.95


def test_infer_capability_context():
    caps = sc.infer_capability("some-model", {"context_length": 16384})
    assert caps["context_ok"] == True
    caps = sc.infer_capability("some-model", {"context_length": 1024})
    assert caps["context_ok"] == False


def test_build_capabilities_file_preserves_existing():
    old_caps = {
        "_meta": {"version": 1},
        "models": {
            "omniroute/auto/best-coding": {"vision": True, "coding": 0.9, "reasoning": 0.8}
        },
        "task_to_model": {"codigo": "omniroute/auto/best-coding"},
    }
    snapshots = {
        "omniroute": [{"id": "auto/best-coding", "object": "model", "owned_by": "x", "context_length": 128000}],
        "9router": [{"id": "new-model", "object": "model", "owned_by": "y", "context_length": 8192}],
    }

    new_caps = sc.build_capabilities_file(snapshots, old_caps)

    # Existente se preserva (vision=True se mantiene aunque se infiera False)
    preserved = new_caps["models"]["omniroute/auto/best-coding"]
    assert preserved["vision"] == True
    assert preserved["coding"] == 0.9

    # Nuevo se infiere
    new_model = new_caps["models"]["9router/new-model"]
    assert "reasoning" in new_model

    # Meta version incrementada
    assert new_caps["_meta"]["version"] == 2

    # task_to_model se preserva
    assert new_caps["task_to_model"]["codigo"] == "omniroute/auto/best-coding"


def test_compute_diff():
    old_caps = {"models": {"a": {}, "b": {}, "c": {}}}
    new_caps = {"models": {"a": {}, "d": {}}}

    diff = sc.compute_diff(old_caps, new_caps)

    assert diff["added"] == ["d"]
    assert diff["removed"] == ["b", "c"]
    assert diff["total_old"] == 3
    assert diff["total_new"] == 2


def test_compute_diff_changed():
    old_caps = {"models": {"a": {"vision": False}, "b": {}}}
    new_caps = {"models": {"a": {"vision": True}, "b": {}}}

    diff = sc.compute_diff(old_caps, new_caps)

    assert len(diff["changed"]) == 1
    assert diff["changed"][0]["model"] == "a"
    assert "vision" in diff["changed"][0]["changes"][0]


@patch("atlas_sync_capabilities.fetch_models")
def test_sync_cmd_creates_file(mock_fetch):
    mock_fetch.side_effect = [
        [{"id": "model-a", "object": "model", "owned_by": "o", "context_length": 100000}],
        [{"id": "model-b", "object": "model", "owned_by": "o", "context_length": 100000}],
        [],  # ollama no responde
    ]

    class Args:
        dry_run = False

    old_file = sc.CAPS_FILE
    with tempfile.TemporaryDirectory() as tmpdir:
        sc.CAPS_FILE = Path(tmpdir) / "model_capabilities.json"
        try:
            new_caps, diff = sc.sync_cmd(Args())
            assert sc.CAPS_FILE.exists()
            assert len(new_caps["models"]) == 2
            assert diff["total_new"] == 2
        finally:
            sc.CAPS_FILE = old_file


if __name__ == "__main__":
    test_infer_capability_vision()
    test_infer_capability_reasoning()
    test_infer_capability_coding()
    test_infer_capability_context()
    test_build_capabilities_file_preserves_existing()
    test_compute_diff()
    test_compute_diff_changed()
    test_sync_cmd_creates_file()
    print("OK tests/unit/test_sync_capabilities.py")