"""Tests C2 — Bucle de Cierre Forzoso (9 REQs)"""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from atlas_controller import crear_contrato, validar_contrato, AtlasController, STATE_DIR, VAULT_TASKS_DIR


# --- C2-1: contrato sin criterios → rechazo ---

def test_c2_1_contrato_sin_criterios_es_invalido():
    c = {"task_id": "T-test", "criterios": []}
    assert validar_contrato(c) is False


def test_c2_1_contrato_con_criterios_es_valido():
    c = {"task_id": "T-test", "criterios": [{"id": "CR-1", "tipo": "humano"}]}
    assert validar_contrato(c) is True


# --- C2-1 + C2-9: crear contrato, criterio vago → humano ---

def test_c2_1_crear_contrato_ok(tmp_path, monkeypatch):
    monkeypatch.setattr("atlas_controller.STATE_DIR", tmp_path)
    tid = crear_contrato("orden X", [
        {"id": "CR-1", "descripcion": "x", "tipo": "archivo",
         "verificacion": {"ruta": "noexiste", "contiene": "x"}, "estado": "PENDIENTE"}
    ])
    p = tmp_path / f"{tid}.json"
    assert p.exists()
    c = json.loads(p.read_text(encoding="utf-8"))
    assert c["estado"] == "EN_CURSO"
    assert c["criterios"][0]["tipo"] == "archivo"


def test_c2_9_criterio_sin_verificacion_degrada_a_humano(tmp_path, monkeypatch):
    monkeypatch.setattr("atlas_controller.STATE_DIR", tmp_path)
    tid = crear_contrato("orden", [
        {"id": "CR-1", "descripcion": "vago", "tipo": "archivo",
         # sin "verificacion"
         "estado": "PENDIENTE"}
    ])
    c = json.loads((tmp_path / f"{tid}.json").read_text(encoding="utf-8"))
    assert c["criterios"][0]["tipo"] == "humano"


# --- C2-6: escalada por max_intentos ---

def test_c2_6_escalada_por_max_intentos(tmp_path, monkeypatch):
    monkeypatch.setattr("atlas_controller.STATE_DIR", tmp_path)
    monkeypatch.setattr("atlas_controller.VAULT_TASKS_DIR", tmp_path)
    tid = crear_contrato("imposible", [
        {"id": "CR-1", "descripcion": "x", "tipo": "archivo",
         "verificacion": {"ruta": "noexiste-zzz", "contiene": "x"}, "estado": "PENDIENTE"}
    ], max_intentos=1, timeout_min=1)
    ctrl = AtlasController(tid)
    ctrl.turno_agente = lambda c, p: None  # sin opencode
    result = ctrl.correr()
    assert result["estado"] == "ESCALADA"
    assert result["progreso_pct"] < 100


# --- C2-2: close() solo por controller ---

def test_c2_2_cierre_solo_por_controller(tmp_path, monkeypatch):
    monkeypatch.setattr("atlas_controller.STATE_DIR", tmp_path)
    monkeypatch.setattr("atlas_controller.VAULT_TASKS_DIR", tmp_path)
    tid = crear_contrato("ok", [
        {"id": "CR-1", "descripcion": "x", "tipo": "humano", "estado": "PENDIENTE"}
    ])
    ctrl = AtlasController(tid)
    ctrl.turno_agente = lambda c, p: None
    result = ctrl.correr()
    assert result["estado"] == "TERMINADA"
    assert (tmp_path / f"{tid}.json").exists()


# --- C2-8: contrato archivado en bóveda ---

def test_c2_8_archivado_en_boveda(tmp_path, monkeypatch):
    monkeypatch.setattr("atlas_controller.STATE_DIR", tmp_path)
    monkeypatch.setattr("atlas_controller.VAULT_TASKS_DIR", tmp_path)
    tid = crear_contrato("test", [
        {"id": "CR-1", "tipo": "humano", "estado": "PENDIENTE"}
    ])
    ctrl = AtlasController(tid)
    ctrl.turno_agente = lambda c, p: None
    ctrl.correr()
    assert (tmp_path / f"{tid}.json").exists()
    archived = json.loads((tmp_path / f"{tid}.json").read_text(encoding="utf-8"))
    assert archived["estado"] == "TERMINADA"
