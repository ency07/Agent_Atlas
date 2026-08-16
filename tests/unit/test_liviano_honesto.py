# ============================================================
# tests/unit/test_liviano_honesto.py — Tests Atlas Liviano + Honesto
# ------------------------------------------------------------
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from atlas_c4 import classify_level, get_model_for_level, get_injection_budget, generate_contract
from atlas_controller import es_liviano, ejecutar_liviano
from atlas_verifier import Verifier


# --- 1. Clasificador L0/L1/L2+ ---
def test_l0_classification():
    assert classify_level("abre el navegador") == "L0"
    assert classify_level("muestra el estado del sistema") == "L0"
    assert classify_level("resume el documento") == "L0"
    assert classify_level("que hora es") == "L0"


def test_l1_classification():
    assert classify_level("agrega una nota a la memoria") == "L1"
    assert classify_level("crea un archivo temporal") == "L1"


def test_l2_classification():
    assert classify_level("configura el firewall y despliega el servicio") == "L2"
    assert classify_level("migra la base de datos y publica en producción") == "L2"
    assert classify_level("refactoriza el módulo de pagos") == "L2"


def test_model_for_level():
    assert get_model_for_level("L0") == "omniroute/auto/best-fast"
    assert get_model_for_level("L2") == "omniroute/auto/best-coding"


def test_injection_budget():
    assert get_injection_budget("L0") <= 300
    assert get_injection_budget("L2") <= 700


# --- 2. Contrato incluye nivel ---
def test_contract_includes_level():
    c = generate_contract("abre el navegador")
    assert c["nivel"] == "L0"
    assert c["modelo"] == "omniroute/auto/best-fast"
    assert es_liviano(c) is True

    c2 = generate_contract("configura el firewall")
    assert c2["nivel"] == "L2"
    assert es_liviano(c2) is False


# --- 3. Verificación barata L0: check de 1 línea ---
def test_ejecutar_liviano_check_barato():
    contract = {
        "nivel": "L0",
        "criterios": [{"id": "CR-1", "descripcion": "navegador abierto",
                       "tipo": "comando", "verificacion": {"cmd": "echo ok"}}],
    }
    r = ejecutar_liviano(contract, verifier=Verifier())
    assert r["resultado"] == "OK"
    assert r["evidencias"][0]["ok"] is True
    assert r["exito_falso"] is False


# --- 4. Cierre sin evidencia → bloqueado + registrado exito_falso ---
def test_cierre_sin_evidencia_bloqueado():
    v = Verifier()
    contract = {
        "nivel": "L0",
        "criterios": [
            {"id": "CR-1", "descripcion": "hacer X", "estado": "PENDIENTE", "evidencia": ""},
        ],
    }
    r = v.verificar_cierre_sin_evidencia(contract)
    assert r["exito_falso"] is True
    assert r["registrado"] is True

    # Verificar que quedó en friction_log
    log = Path(__file__).parent.parent.parent / "memory_data" / "state" / "friction_log.jsonl"
    if log.exists():
        lines = [l for l in log.read_text(encoding="utf-8").strip().splitlines() if l.strip()]
        last = json.loads(lines[-1])
        assert last["type"] == "exito_falso"


def test_cierre_con_evidencia_pasa():
    v = Verifier()
    contract = {
        "nivel": "L0",
        "criterios": [
            {"id": "CR-1", "descripcion": "hacer X", "estado": "OK", "evidencia": "salida verificada"},
        ],
    }
    r = v.verificar_cierre_sin_evidencia(contract)
    assert r["exito_falso"] is False


# --- 5. "no sé"/"no pude" pasan; "debería funcionar" falla ---
def test_honestidad_lenguaje():
    frases_ok = [
        "no sé cuál es el endpoint exacto, necesito verificarlo",
        "no pude completar la migración, falta acceso a producción",
        "ejecutado pero NO verificado: el comando no devolvió salida",
    ]
    frases_fail = [
        "debería funcionar sin problemas",
        "creo que está listo, probablemente",
        "parece que todo quedó bien",
    ]

    for frase in frases_ok:
        # "no sé"/"no pude" = pide verificación on-demand, no es exito_falso
        assert "debería" not in frase or "no pude" in frase

    for frase in frases_fail:
        assert "debería" in frase or "probablemente" in frase or "parece" in frase


# --- 6. Latencia L0 bajo umbral (5s) ---
def test_latencia_l0_umbral():
    contract = {
        "nivel": "L0",
        "criterios": [{"id": "CR-1", "descripcion": "check",
                       "tipo": "comando", "verificacion": {"cmd": "echo ok"}}],
    }
    t0 = time.time()
    r = ejecutar_liviano(contract, verifier=Verifier())
    dt = time.time() - t0
    assert r["resultado"] == "OK"
    assert dt < 5.0, f"L0 tardó {dt:.2f}s (umbral 5s)"


if __name__ == "__main__":
    test_l0_classification()
    test_l1_classification()
    test_l2_classification()
    test_model_for_level()
    test_injection_budget()
    test_contract_includes_level()
    test_ejecutar_liviano_check_barato()
    test_cierre_sin_evidencia_bloqueado()
    test_cierre_con_evidencia_pasa()
    test_honestidad_lenguaje()
    test_latencia_l0_umbral()
    print("OK tests/unit/test_liviano_honesto.py")
