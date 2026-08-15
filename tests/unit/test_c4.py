#!/usr/bin/env python3
"""Tests C4-1..C4-5."""
import sys, json
sys.path.insert(0, "E:/Agente_IA")
import atlas_c4

def test_c4_1_decompose():
    task = "configura el backup cifrado"
    contract = atlas_c4.generate_contract(task)
    assert "criterios" in contract
    # should have at least one result-oriented criterion
    criterios = contract["criterios"]
    assert any("backup" in c["descripcion"].lower() for c in criterios)
    print("OK C4-1 descomposición a resultado")

def test_c4_2_implicit_constraints():
    task = "haz un trade"
    contract = atlas_c4.generate_contract(task)
    criterios = contract["criterios"]
    # implicit constraint "no_romper_lo_que_funciona" should be present
    assert any("no_romper" in c["descripcion"] for c in criterios)
    print("OK C4-2 restricciones implícitas")

def test_c4_3_auto_contract():
    task = "publica el informe en web"
    contract = atlas_c4.generate_contract(task)
    # contract must be valid for atlas_controller.crear_contrato
    assert "orden_literal" in contract
    assert "criterios" in contract
    assert "max_intentos" in contract
    assert "timeout_min" in contract
    print("OK C4-3 contrato C2 auto-generado")

def test_c4_4_clarification():
    # ambiguous task
    task = "usa el modelo para analizar"
    contract = atlas_c4.generate_contract(task)
    clar = contract.get("clarificaciones", [])
    # at most 1 question
    assert len(clar) <= 1
    print("OK C4-4 clarificación máx 1")

def test_c4_5_domain():
    for task, expected in [
        ("revisa mi setup de trading", "trading"),
        ("publica diseño en pod", "pod"),
        ("escribe post para instagram", "contenido"),
        ("haz backup", "general"),
    ]:
        contract = atlas_c4.generate_contract(task)
        assert contract["dominio"] == expected
    print("OK C4-5 dominio correcto")

if __name__ == "__main__":
    test_c4_1_decompose()
    test_c4_2_implicit_constraints()
    test_c4_3_auto_contract()
    test_c4_4_clarification()
    test_c4_5_domain()
    print("\nAll C4 tests passed!")