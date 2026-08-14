# ============================================================
# tests/unit/test_guardian.py — Tests del guardián
# ------------------------------------------------------------
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from atlas_guardian import (
    guardian_get_config,
    guardian_set_level,
    guardian_check,
    guardian_add_whitelist,
    guardian_remove_whitelist,
)

def test_guardian_config_structure():
    config = guardian_get_config()
    assert "level" in config
    assert config["level"] in ["relax", "guard", "strict"]
    assert "whitelist_binaries" in config
    assert "whitelist_processes" in config
    assert "allowed_dirs" in config
    assert "blocked_ops" in config

def test_set_level():
    result = guardian_set_level("guard")
    assert result["level"] == "guard"
    config = guardian_get_config()
    assert config["level"] == "guard"
    
    result = guardian_set_level("strict")
    assert result["level"] == "strict"

def test_check_allowed_operation():
    result = guardian_check("run_command", {"command": "python --version"})
    assert result["allowed"] == True
    assert result["requires_confirmation"] == False

def test_check_blocked_operation():
    result = guardian_check("registry_write", {"key": "HKLM\\SOFTWARE\\Test"})
    assert "allowed" in result
    assert "requires_confirmation" in result

def test_whitelist_operations():
    # Añadir a whitelist
    result = guardian_add_whitelist("test_binary_guardian", "binaries")
    assert "test_binary_guardian" in result["whitelist_binaries"]
    
    # Verificar que está
    config = guardian_get_config()
    assert "test_binary_guardian" in config["whitelist_binaries"]
    
    # Remover
    result = guardian_remove_whitelist("test_binary_guardian", "binaries")
    assert "test_binary_guardian" not in result["whitelist_binaries"]

if __name__ == "__main__":
    test_guardian_config_structure()
    test_set_level()
    test_check_allowed_operation()
    test_check_blocked_operation()
    test_whitelist_operations()
    print("✅ tests/unit/test_guardian.py: OK")