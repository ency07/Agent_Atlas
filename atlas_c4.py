#!/usr/bin/env python3
"""
atlas_c4.py — Intención Profunda (C4).
Genera contratos C2 automáticos a partir de pedido libre.
"""
import json
import sys
import re
from pathlib import Path
from typing import Dict, List, Any

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))

# Reuse existing modules
import atlas_ontology
import atlas_episodic
import atlas_context_live
import atlas_controller
import atlas_verifier

# --- Dominio de conocimiento ---
DOMAIN_KEYWORDS = {
    "trading": ["trading", "trade", "posición", "entrada", "salida", "stop", "riesgo", "r-multiple", "setup"],
    "pod": ["pod", "print on demand", "diseño", "nicho", "merch", "publicar", "export"],
    "contenido": ["contenido", "post", "video", "guion", "gancho", "cta", "retención", "publicar"],
}

def detect_domain(task: str) -> str:
    t = task.lower()
    for domain, kws in DOMAIN_KEYWORDS.items():
        if any(kw in t for kw in kws):
            return domain
    return "general"

# --- Restricciones implícitas por perfil ---
IMPLICIT_CONSTRAINTS = [
    "no_romper_lo_que_funciona",
    "no_preguntar_obviedades",
    "no_demoras_innecesarias",
    "usar_herramientas_habilitadas",
    "respetar_guardian",
]

def build_implicit_constraints(domain: str) -> List[str]:
    constraints = IMPLICIT_CONSTRAINTS.copy()
    if domain == "trading":
        constraints += ["validar_riesgo_R", "confirmar_entrada_salida"]
    elif domain == "pod":
        constraints += ["verificar_derechos_imagen", "formato_exportacion"]
    elif domain == "contenido":
        constraints += ["incluir_gancho", "cta_claro"]
    return constraints

# --- Descomposición pragmática a resultado ---
def decompose_to_result(task: str, domain: str) -> List[Dict[str, Any]]:
    """
    Convierte el pedido en criterios de RESULTADO (no pasos de clic).
    """
    criteria = []
    t = task.lower()
    # heurísticas simples
    if "configur" in t or "setup" in t:
        criteria.append({"id": "CR-1", "descripcion": "Configuración aplicada y funcional", "tipo": "humano", "verificacion": ""})
    if "publica" in t or "deploy" in t or "desplieg" in t:
        criteria.append({"id": "CR-2", "descripcion": "Recurso accesible en producción", "tipo": "http", "verificacion": "curl -s -o /dev/null -w '%{http_code}' URL | grep 200"})
    if "backup" in t or "respald" in t:
        criteria.append({"id": "CR-3", "descripcion": "Backup creado y verificable", "tipo": "shell", "verificacion": "python atlas_backup_encrypted.py list --out-dir /backup | grep atlas_backup"})
    if "analiz" in t or "revis" in t:
        criteria.append({"id": "CR-4", "descripcion": "Informe generado con hallazgos", "tipo": "humano", "verificacion": ""})
    # default: at least one generic criterion
    if not criteria:
        criteria.append({"id": "CR-1", "descripcion": f"Resultado esperado: {task}", "tipo": "humano", "verificacion": ""})
    return criteria

# --- Clarificación estratégica (máx 1 pregunta) ---
def ask_clarification(task: str, domain: str) -> List[str]:
    questions = []
    t = task.lower()
    if "modelo" in t and "cual" not in t:
        questions.append("¿Qué modelo prefieres? (auto/best-coding, auto/best-vision, etc.)")
    if "backup" in t and "age" not in t and "zip" not in t:
        questions.append("¿Backup cifrado (age) o plano (zip)?")
    # limit to 1
    return questions[:1]

# --- Generador de contrato C2 auto ---
def generate_contract(task: str) -> Dict[str, Any]:
    """
    Entrada: pedido libre en lenguaje natural.
    Salida: dict listo para atlas_controller.crear_contrato (order, criterios, max_intentos, timeout_min).
    """
    domain = detect_domain(task)
    implicit = build_implicit_constraints(domain)
    criteria = decompose_to_result(task, domain)
    # add implicit constraints as human criteria
    for i, ic in enumerate(implicit, start=len(criteria)+1):
        criteria.append({"id": f"CR-{i}", "descripcion": ic, "tipo": "humano", "verificacion": ""})
    clarifications = ask_clarification(task, domain)
    assumptions = []
    if "modelo" not in task.lower():
        assumptions.append("Asumo modelo por defecto auto/best-coding según opencode.jsonc")
    if "age" not in task.lower() and "zip" not in task.lower():
        assumptions.append("Asumo backup zip plano (mcp_memory_server backup) salvo que se indique age")
    # Build contract dict similar to atlas_controller.crear_contrato expectations
    contract = {
        "orden_literal": task,
        "criterios": criteria,
        "max_intentos": 5,
        "timeout_min": 20,
        "dominio": domain,
        "clarificaciones": clarifications,
        "supuestos": assumptions,
    }
    return contract

# --- CLI / MCP tool wrapper ---
def c4_generate_contract(task: str) -> str:
    contract = generate_contract(task)
    return json.dumps(contract, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python atlas_c4.py \"pedido libre\"")
        sys.exit(1)
    task = " ".join(sys.argv[1:])
    print(c4_generate_contract(task))