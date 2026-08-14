# ============================================================
# tests/unit/test_benchmark.py — Tests de benchmark de providers
# ------------------------------------------------------------
import sys
import json
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import atlas_benchmark as ab


def test_load_log_default():
    with tempfile.TemporaryDirectory() as tmpdir:
        ab.LOG_FILE = Path(tmpdir) / "routing_log.json"
        data = ab._load_log()
        assert data["entries"] == []
        assert "provider_stats" in data


def test_load_log_corrupted():
    with tempfile.TemporaryDirectory() as tmpdir:
        log = Path(tmpdir) / "routing_log.json"
        log.write_text("invalid json{{")
        ab.LOG_FILE = log
        data = ab._load_log()
        assert data["entries"] == []


def test_save_and_load_log():
    with tempfile.TemporaryDirectory() as tmpdir:
        ab.LOG_FILE = Path(tmpdir) / "routing_log.json"
        data = {"entries": [], "provider_stats": {}}
        ab._save_log(data)

        reloaded = ab._load_log()
        assert reloaded == data


def test_measure_returns_tuple():
    # Debe devolver (latency_ms, ok, error) siempre
    lat, ok, err = ab._measure("nonexistent_provider", {"api": "http://127.0.0.1:1/v1"})
    assert isinstance(lat, float)
    assert isinstance(ok, bool)
    assert isinstance(err, str) or err is None


def test_run_benchmark_accumulates():
    with tempfile.TemporaryDirectory() as tmpdir:
        ab.LOG_FILE = Path(tmpdir) / "routing_log.json"
        stats = ab.run_benchmark(repeat=1, deep=False)

        # Todos los providers deben estar en stats
        for name in ab.PROVIDERS:
            assert name in stats
            assert stats[name]["attempts"] >= 1
            assert "success_rate" in stats[name]
            assert "avg_latency_ms" in stats[name]

        # Segunda corrida debe acumular
        stats2 = ab.run_benchmark(repeat=1, deep=False)
        for name in ab.PROVIDERS:
            assert stats2[name]["attempts"] >= stats[name]["attempts"]


def test_report_does_not_crash():
    with tempfile.TemporaryDirectory() as tmpdir:
        ab.LOG_FILE = Path(tmpdir) / "routing_log.json"
        ab._save_log({
            "provider_stats": {
                "omniroute": {"attempts": 5, "success": 4, "success_rate": 80.0, "avg_latency_ms": 3000, "last_error": None},
                "9router": {"attempts": 3, "success": 3, "success_rate": 100.0, "avg_latency_ms": 1500, "last_error": None},
            }
        })
        stats = ab.report()
        assert stats["omniroute"]["success"] == 4


if __name__ == "__main__":
    test_load_log_default()
    test_load_log_corrupted()
    test_save_and_load_log()
    test_measure_returns_tuple()
    test_run_benchmark_accumulates()
    test_report_does_not_crash()
    print("OK tests/unit/test_benchmark.py")