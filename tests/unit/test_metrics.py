# ============================================================
# tests/unit/test_metrics.py — Tests de métricas uso/costo
# ------------------------------------------------------------
import sys
import json
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import atlas_metrics as am


def test_estimate_cost_local_zero():
    cost = am.estimate_cost("ollama/phi4-mini", 1000, 500)
    assert cost == 0.0


def test_estimate_cost_omniroute():
    cost = am.estimate_cost("omniroute/auto/best-coding", 1_000_000, 1_000_000)
    assert cost == 0.75  # 0.15 + 0.60


def test_provider_of():
    assert am._provider_of("omniroute/auto/best-coding") == "omniroute"
    assert am._provider_of("no-slash") == "unknown"


def test_record_and_report(tmp_path):
    am.USAGE_FILE = tmp_path / "usage_log.json"
    am.record("omniroute/auto/best-coding", 1000, 200, latency_ms=100, source="test")
    data = am._load_usage()
    assert len(data["records"]) == 1
    assert data["records"][0]["cost_usd"] > 0
    assert data["records"][0]["latency_ms"] == 100

    snap = am.report(period="today", by_model=True)
    assert snap["calls"] == 1
    assert snap["tokens_in"] == 1000
    assert snap["cost_usd"] > 0


def test_record_caps_at_500(tmp_path):
    am.USAGE_FILE = tmp_path / "usage_log.json"
    for i in range(505):
        am.record(f"provider/model-{i}", 10, 10)
    data = am._load_usage()
    assert len(data["records"]) == 500


def test_ingest_from_routing(tmp_path):
    am.USAGE_FILE = tmp_path / "usage_log.json"
    am.ROUTING_FILE = tmp_path / "routing_log.json"
    am.ROUTING_FILE.write_text(json.dumps({
        "entries": [
            {"decision": "proceed", "model": "omniroute/auto/best-coding"},
            {"decision": "keep", "model_after": "omniroute/auto/best-coding"},
            {"decision": "blocked", "model": "x"},  # no cuenta
            {"decision": "switch", "model_after": "auto/best-vision"},
        ]
    }), encoding="utf-8")

    n = am.ingest_from_routing()
    assert n == 3
    data = am._load_usage()
    assert len(data["records"]) == 3


def test_stats(tmp_path):
    am.USAGE_FILE = tmp_path / "usage_log.json"
    am.record("omniroute/auto/best-coding", 1000, 200)
    am.record("ollama/qwen", 1000, 200)
    s = am.stats()
    assert s["records"] == 2
    assert s["tokens"] == 2400
    assert s["cost_usd"] > 0


if __name__ == "__main__":
    test_estimate_cost_local_zero()
    test_estimate_cost_omniroute()
    test_provider_of()
    test_record_and_report(__import__("tempfile").TemporaryDirectory().name)
    test_record_caps_at_500(__import__("tempfile").TemporaryDirectory().name)
    test_ingest_from_routing(__import__("tempfile").TemporaryDirectory().name)
    test_stats(__import__("tempfile").TemporaryDirectory().name)
    print("OK tests/unit/test_metrics.py")