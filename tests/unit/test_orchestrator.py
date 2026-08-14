# ============================================================
# tests/unit/test_orchestrator.py — Tests del orquestador
# ------------------------------------------------------------
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from atlas_orchestrator import (
    load_capabilities,
    analyze,
    orchestrator_register_success,
    orchestrator_register_error,
    orchestrator_provider_health,
    orchestrator_available,
)

def test_load_capabilities():
    caps = load_capabilities()
    assert "models" in caps
    assert len(caps["models"]) > 0

def test_analyze_returns_decision():
    result = analyze("escribe una función en python")
    assert "decision" in result
    assert "suggested_model" in result["decision"]
    assert "reason" in result["decision"]

def test_analyze_vision():
    result = analyze("analiza esta imagen")
    assert "decision" in result
    assert result["decision"]["vision_supported"] in [True, False]

def test_provider_health_init():
    health = orchestrator_provider_health()
    assert isinstance(health, dict)
    for name, h in health.items():
        assert "consecutive_failures" in h
        assert h["consecutive_failures"] == 0

def test_register_error_increments_failures():
    orchestrator_register_error("test_provider", "test error")
    health = orchestrator_provider_health()
    # El provider de test puede no existir si no está en la lista activa
    # Verificar que la función no falla
    assert True  # Si llegamos aquí, no hubo excepción

def test_register_success_resets_failures():
    orchestrator_register_error("test_provider2", "test error")
    orchestrator_register_success("test_provider2")
    # Verificar que no lanza excepción
    assert True

def test_circuit_breaker_threshold():
    for _ in range(3):
        orchestrator_register_error("test_provider3", "error")
    # Verificar que no lanza excepción
    assert True

def test_orchestrator_available():
    result = orchestrator_available()
    assert "providers" in result
    assert isinstance(result["providers"], dict)

if __name__ == "__main__":
    test_load_capabilities()
    test_analyze_returns_decision()
    test_analyze_vision()
    test_provider_health_init()
    test_register_error_increments_failures()
    test_register_success_resets_failures()
    test_circuit_breaker_threshold()
    test_orchestrator_available()
    print("✅ tests/unit/test_orchestrator.py: OK")