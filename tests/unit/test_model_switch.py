# ============================================================
# tests/unit/test_model_switch.py — Tests de auto-cambio de modelo
# ------------------------------------------------------------
import sys
import json
import tempfile
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import atlas_model_switch as ms


def test_current_model():
    with tempfile.TemporaryDirectory() as tmpdir:
        cfg = Path(tmpdir) / "opencode.jsonc"
        cfg.write_text('{\n  "model": "auto/best-coding",\n  "provider": {}\n}', encoding="utf-8")
        assert ms.current_model(cfg) == "auto/best-coding"


def test_current_model_none():
    with tempfile.TemporaryDirectory() as tmpdir:
        cfg = Path(tmpdir) / "opencode.jsonc"
        cfg.write_text('{\n  "provider": {}\n}', encoding="utf-8")
        assert ms.current_model(cfg) is None


def test_set_model_replaces():
    with tempfile.TemporaryDirectory() as tmpdir:
        cfg = Path(tmpdir) / "opencode.jsonc"
        cfg.write_text('{\n  "model": "auto/best-coding",\n  "provider": {}\n}', encoding="utf-8")
        ok = ms.set_model(cfg, "auto/best-vision")
        assert ok
        assert ms.current_model(cfg) == "auto/best-vision"


def test_set_model_creates_backup():
    with tempfile.TemporaryDirectory() as tmpdir:
        cfg = Path(tmpdir) / "opencode.jsonc"
        cfg.write_text('{"model": "a"}', encoding="utf-8")
        ms.BACKUP_DIR = Path(tmpdir) / "backups"
        ok = ms.set_model(cfg, "b")
        assert ok
        backups = list(ms.BACKUP_DIR.glob("opencode_*.jsonc"))
        assert len(backups) >= 1


def test_model_has_capability_vision_true():
    assert ms._model_has_capability("omniroute/auto/best-vision", "vision") is True


def test_model_has_capability_vision_false():
    assert ms._model_has_capability("auto/best-coding", "vision") is False


def test_model_has_capability_coding_true():
    assert ms._model_has_capability("auto/best-coding", "coding") is True


def test_model_has_capability_no_req():
    assert ms._model_has_capability("anything", None) is True


@patch("atlas_model_switch.orch.analyze")
def test_decide_switch_coding_no_change(mock_analyze):
    mock_analyze.return_value = {
        "required_capability": "coding",
        "decision": {"action": "proceed", "suggested_model": "omniroute/auto/best-coding"},
    }
    with tempfile.TemporaryDirectory() as tmpdir:
        cfg = Path(tmpdir) / "opencode.jsonc"
        cfg.write_text('{"model": "auto/best-coding"}', encoding="utf-8")
        ms._config_candidates = lambda: [cfg]
        result = ms.decide_and_switch("tarea de codigo")
        assert result["changed"] is False
        assert result["reason"] == "already_adequate"


@patch("atlas_model_switch.orch.analyze")
def test_decide_switch_vision_changes(mock_analyze):
    mock_analyze.return_value = {
        "required_capability": "vision",
        "decision": {"action": "proceed", "suggested_model": "omniroute/auto/best-vision"},
    }
    with tempfile.TemporaryDirectory() as tmpdir:
        cfg = Path(tmpdir) / "opencode.jsonc"
        cfg.write_text('{"model": "auto/best-coding"}', encoding="utf-8")
        ms._config_candidates = lambda: [cfg]
        result = ms.decide_and_switch("screenshot", dry_run=True)
        assert result["changed"] is True
        assert result["dry_run"] is True
        # No debe modificar en dry-run
        assert ms.current_model(cfg) == "auto/best-coding"


@patch("atlas_model_switch.orch.analyze")
def test_decide_switch_blocked(mock_analyze):
    mock_analyze.return_value = {
        "required_capability": "vision",
        "decision": {"action": "block_and_advise", "suggested_model": None, "reason": "sin vision"},
    }
    with tempfile.TemporaryDirectory() as tmpdir:
        cfg = Path(tmpdir) / "opencode.jsonc"
        cfg.write_text('{"model": "auto/best-coding"}', encoding="utf-8")
        ms._config_candidates = lambda: [cfg]
        result = ms.decide_and_switch("screenshot")
        assert result["changed"] is False
        assert result["reason"] == "blocked"


if __name__ == "__main__":
    test_current_model()
    test_current_model_none()
    test_set_model_replaces()
    test_set_model_creates_backup()
    test_model_has_capability_vision_true()
    test_model_has_capability_vision_false()
    test_model_has_capability_coding_true()
    test_model_has_capability_no_req()
    test_decide_switch_coding_no_change()
    test_decide_switch_vision_changes()
    test_decide_switch_blocked()
    print("OK tests/unit/test_model_switch.py")