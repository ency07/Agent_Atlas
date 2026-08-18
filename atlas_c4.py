#!/usr/bin/env python3
"""
atlas_c4.py — Intención Profunda (C4) + Clasificador de Nivel (Liviano/Honesto).
Genera contratos C2 automáticos a partir de pedido libre.
Clasifica tareas L0/L1/L2+ como primer paso de todo turno.
"""
import json
import sys
import re
from pathlib import Path
from typing import Dict, List, Any, Optional

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))

# Reuse existing modules
import atlas_ontology
import atlas_episodic
import atlas_context_live
import atlas_controller
import atlas_verifier

# --- Nivel de complejidad (L0/L1/L2+) ---
# L0: 1 acción sin cambios de config/archivos → best-fast, sin contrato
# L1: 1-2 tools, cambio menor reversible → igual que L0 + verificación
# L2+: config, archivos, programas, dinero, multi-paso → contrato + verificador + crítico

L0_PATTERNS = [
    r"\babrir\b", r"\babre\b", r"\bnavegar\b", r"\bmira\b", r"\bmuestra\b",
    r"\bmostrar\b", r"\bque hay\b", r"\bcual es\b", r"\bcomo se\b",
    r"\btraduce\b", r"\bresume\b", r"\bexplica\b", r"\bque hora\b",
    r"\bclima\b", r"\bstatus\b", r"\bheartbeat\b", r"\blistar\b",
    r"\bver\b", r"\bleer\b", r"\bestado\b", r"\bestatus\b",
]

L1_PATTERNS = [
    r"\bcrear\b", r"\bagregar\b", r"\bmodificar\b", r"\beditar\b", r"\brenombrar\b",
    r"\bcambiar\b", r"\bactualizar\b", r"\beliminar\b", r"\bborrar\b",
    r"\bcopiar\b", r"\bmover\b", r"\binstalar\b", r"\bdesinstalar\b",
    r"\btest\b", r"\bprueba\b", r"\bcheck\b", r"\bverificar\b",
]

L2_KEYWORDS = [
    "config", "setup", "deploy", "publicar", "desplieg", "backup", "respald",
    "migrar", "migración", "refactor", "arquitectura", "diseña el sistema",
    "contrato", "pago", "factura", "dinero", "precio", "billing",
    "seguridad", "firewall", "permiso", "acceso", "clave", "secret",
    "base de datos", "schema", "migracion", "redis", "nginx",
    "docker", "kubernetes", "terraform", "ci/cd", "pipeline",
    "multi-paso", "pipeline", "cadena", "secuencia compleja",
]


def classify_level(task: str) -> str:
    """Clasifica una tarea en L0/L1/L2+ como primer paso de todo turno.

    L0: 1 acción sin cambios (abrir, navegar, responder, tipear)
    L1: 1-2 tools, cambio menor reversible
    L2+: config, archivos, programas, dinero, multi-paso
    """
    t = task.lower().strip()

    # L2+ explícito: keywords de alto riesgo/complexidad
    for kw in L2_KEYWORDS:
        if kw in t:
            return "L2"

    # L2+: multi-paso detectado
    step_indicators = ["y luego", "después", "primero.*luego", "paso 1", "paso 2", r"1\)", r"2\)"]
    for pat in step_indicators:
        if re.search(pat, t):
            return "L2"

    # L0: patrones de consulta/simple
    for pat in L0_PATTERNS:
        if re.search(pat, t):
            return "L0"

    # L1: patrones de acción menor
    for pat in L1_PATTERNS:
        if re.search(pat, t):
            return "L1"

    # Default: L1 (acción no trivial pero no catastrófica)
    return "L1"


def get_model_for_level(level: str) -> str:
    """Devuelve el modelo recomendado para un nivel."""
    return {
        "L0": "omniroute/auto/best-fast",
        "L1": "omniroute/auto/best-fast",
        "L2": "omniroute/auto/best-coding",
    }.get(level, "omniroute/auto/best-coding")


def get_injection_budget(level: str) -> int:
    """Tope de tokens para inyección de contexto por nivel."""
    return {"L0": 300, "L1": 300, "L2": 700}.get(level, 700)


def estimate_ctx_tokens(text: str) -> int:
    """Estimación rápida de tokens del contexto (~4 chars/token)."""
    if not text:
        return 0
    return max(1, int(len(text) / 4))


def classify_with_context(task: str) -> dict:
    """Clasifica nivel + estima contexto del turno (para el orquestador).

    Returns: {"nivel": "L0|L1|L2|L3", "ctx_tokens": int}
    """
    nivel = classify_level(task)
    ctx_tokens = estimate_ctx_tokens(task)
    return {"nivel": nivel, "ctx_tokens": ctx_tokens}


def route_with_context(task: str, orchestrator=None) -> dict:
    """Pasa nivel+ctx al orquestador en cada turno (registra en routing_log).

    Si orchestrator es None, usa atlas_orchestrator.route.
    Returns la decision del orquestador.
    """
    ctx = classify_with_context(task)
    if orchestrator is None:
        try:
            import atlas_orchestrator
            return atlas_orchestrator.route(task, nivel=ctx["nivel"], ctx_tokens=ctx["ctx_tokens"])
        except Exception as e:
            return {"error": f"orchestrator no disponible: {e}", **ctx}
    return orchestrator.route(task, nivel=ctx["nivel"], ctx_tokens=ctx["ctx_tokens"])

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
    level = classify_level(task)
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
        "max_intentos": 5 if level == "L2" else 3,
        "timeout_min": 20 if level == "L2" else 5,
        "dominio": domain,
        "nivel": level,
        "modelo": get_model_for_level(level),
        "inyeccion_budget": get_injection_budget(level),
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