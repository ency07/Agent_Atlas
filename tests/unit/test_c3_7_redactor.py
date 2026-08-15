#!/usr/bin/env python3
"""Test C3-7: Redacción por proveedor."""
import sys, json, tempfile, os
sys.path.insert(0, "E:/Agente_IA")
import atlas_redactor

def test_local_unchanged():
    slice_data = {"components": [{"name": "atlas_activity", "path": "E:\\Agente_IA\\atlas_activity.py"}], "configs": {"model": "auto/best-coding"}}
    out = atlas_redactor.redact_slice(slice_data, "local")
    assert out == slice_data
    print("OK local provider returns unchanged")

def test_cloud_redacts_paths():
    slice_data = {"components": [{"name": "atlas_activity", "path": "E:\\Agente_IA\\atlas_activity.py"}], "configs": {"model": "auto/best-coding"}}
    out = atlas_redactor.redact_slice(slice_data, "cloud")
    # path should be redacted
    comp_path = out["components"][0].get("path", "")
    assert "[RUTA_LOCAL]" in comp_path or comp_path != slice_data["components"][0]["path"]
    print("OK cloud redacts local paths")

def test_cloud_redacts_ports():
    slice_data = {"endpoints": ["http://localhost:4100", "http://127.0.0.1:4103"]}
    out = atlas_redactor.redact_slice(slice_data, "cloud")
    for ep in out["endpoints"]:
        assert "[HOST:PORT]" in ep
    print("OK cloud redacts ports")

def test_cloud_redacts_ips():
    slice_data = {"server": "127.0.0.1"}
    out = atlas_redactor.redact_slice(slice_data, "cloud")
    assert "[IP]" in out["server"]
    print("OK cloud redacts IPs")

def test_cloud_redacts_model():
    slice_data = {"config": {"model": "auto/best-coding"}}
    out = atlas_redactor.redact_slice(slice_data, "cloud")
    # model should be redacted
    assert out["config"]["model"] == "[MODELO]" or out["config"]["model"] != "auto/best-coding"
    print("OK cloud redacts model")

if __name__ == "__main__":
    test_local_unchanged()
    test_cloud_redacts_paths()
    test_cloud_redacts_ports()
    test_cloud_redacts_ips()
    test_cloud_redacts_model()
    print("\nAll C3-7 tests passed!")