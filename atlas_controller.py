"""
Atlas Controller — Bucle de Cierre Forzoso (C2)
El agente NO cierra tareas. Cierra el controller con evidencia.
"""
import json
import subprocess
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import List

from atlas_verifier import Verifier
import atlas_verifier
from atlas_log import get_logger

logger = get_logger("controller")

ROOT = Path(__file__).resolve().parent
STATE_DIR = ROOT / "memory_data" / "state" / "tasks"
VAULT_TASKS_DIR = ROOT / "memory_data" / "vault" / "global" / "tasks"
TRUST_LOG = ROOT / "memory_data" / "state" / "trust_log.jsonl"
STATE_DIR.mkdir(parents=True, exist_ok=True)
VAULT_TASKS_DIR.mkdir(parents=True, exist_ok=True)


class AtlasController:
    def __init__(self, task_id: str):
        self.task_id = task_id
        self.state_path = STATE_DIR / f"{task_id}.json"
        self.verifier = Verifier()

    def load(self) -> dict:
        return json.loads(self.state_path.read_text(encoding="utf-8"))

    def save(self, c: dict):
        self.state_path.write_text(
            json.dumps(c, indent=2, ensure_ascii=False), encoding="utf-8")

    def turno_agente(self, c: dict, pendientes: List[dict]):
        prompt = (
            f"CONTRATO {c['task_id']}. Orden: {c['orden_literal']}. "
            f"Pendientes: {[(p['id'],p['descripcion']) for p in pendientes]}. "
            f"Evidencia previa: {c['evidencias'][-3:]}. "
            f"Intento {c['intentos']+1}/{c['max_intentos']}. "
            "Resuelve SOLO los pendientes. No declares éxito: verificador lo comprobará."
        )
        logger.info(f"[{c['task_id']}] turno {c['intentos']+1}: {len(pendientes)} pendientes")
        try:
            subprocess.run(["opencode", "run", prompt], timeout=600,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception as e:
            logger.warning(f"[{c['task_id']}] turno fallo: {e}")

    def verificar(self, c: dict):
        for cr in c["criterios"]:
            if cr["estado"] in ("OK", "HUMANO"):
                continue
            if cr["tipo"] == "humano":
                cr["estado"], cr["evidencia"] = "HUMANO", "pendiente de usuario"
                continue
            r = self.verifier.ejecutar(cr)
            cr["estado"] = "OK" if r.ok else "FAIL"
            cr["evidencia"] = r.evidencia
        ok_n = sum(1 for x in c["criterios"] if x["estado"] in ("OK", "HUMANO"))
        c["progreso_pct"] = round(100 * ok_n / len(c["criterios"])) if c["criterios"] else 100
        return c

    def critic(self, c: dict) -> dict:
        """C2-4: modelo aparte con JSON forzado.
        v1: simula PASS si todo OK; queda integrable con orquestador/routing.
        """
        if c["progreso_pct"] == 100:
            return {"pass": True, "huecos": []}
        return {"pass": False, "huecos": []}

    def registrar_claim(self, c: dict, agente_dijo_listo: bool = False):
        if agente_dijo_listo and c["progreso_pct"] < 100:
            with open(TRUST_LOG, "a", encoding="utf-8") as f:
                f.write(json.dumps({"task": c["task_id"],
                                    "pct_real": c["progreso_pct"],
                                    "ts": datetime.now().isoformat()}) + "\n")

    def escalar(self, c: dict):
        c["estado"] = "ESCALADA"
        fails = [x["id"] for x in c["criterios"] if x["estado"] == "FAIL"]
        reporte = {"task_id": c["task_id"], "pct": c["progreso_pct"],
                   "fails": fails, "intentos": c["intentos"]}
        logger.error(f"ESCALADA {c['task_id']}: {reporte}")
        self.save(c)
        self.archivar(c)
        return c

    def cerrar(self, c: dict):
        c["estado"] = "TERMINADA"
        c["cerrado_en"] = datetime.now().isoformat()
        self.save(c)
        self.archivar(c)
        logger.info(f"CIERRE {c['task_id']}: {c['progreso_pct']}%")
        return c

    def archivar(self, c: dict):
        (VAULT_TASKS_DIR / f"{c['task_id']}.json").write_text(
            json.dumps(c, indent=2, ensure_ascii=False), encoding="utf-8")

    def correr(self):
        c = self.load()
        while c["estado"] == "EN_CURSO":
            if c["intentos"] >= c["max_intentos"]:
                return self.escalar(c)
            try:
                timeout_dt = datetime.fromisoformat(c.get("timeout", "2099-12-31T23:59:59"))
            except ValueError:
                timeout_dt = datetime.max
            if datetime.now() > timeout_dt:
                return self.escalar(c)
            pendientes = [x for x in c["criterios"]
                          if x["estado"] not in ("OK", "HUMANO")]
            if not pendientes:
                return self.cerrar(c)
            self.turno_agente(c, pendientes)
            c["intentos"] += 1
            c = self.verificar(c)
            self.registrar_claim(c)
            self.save(c)
            if c["progreso_pct"] == 100:
                q = self.critic(c)
                if q["pass"]:
                    return self.cerrar(c)
                c["evidencias"].append({"huecos": q["huecos"],
                                        "ts": datetime.now().isoformat()})
            time.sleep(2)
        return c


def crear_contrato(orden: str, criterios: list,
                   max_intentos: int = 5, timeout_min: int = 20) -> str:
    """C2-1: contrato antes de ejecutar. Criterio sin verificacion → tipo 'humano'."""
    task_id = f"T-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    for cr in criterios:
        if cr["tipo"] != "humano" and not cr.get("verificacion"):
            cr["tipo"] = "humano"  # C2-9
    c = {"task_id": task_id, "orden_literal": orden, "estado": "EN_CURSO",
         "criterios": criterios, "progreso_pct": 0, "intentos": 0,
         "max_intentos": max_intentos,
         "timeout": (datetime.now() + timedelta(minutes=timeout_min)).isoformat(),
         "evidencias": [], "creado_en": datetime.now().isoformat()}
    (STATE_DIR / f"{task_id}.json").write_text(
        json.dumps(c, indent=2, ensure_ascii=False), encoding="utf-8")
    logger.info(f"contrato creado {task_id}")
    return task_id


def validar_contrato(c: dict) -> bool:
    """C2-1: contrato sin criterios → rechazo."""
    return bool(c.get("criterios"))


# --- Liviano: fast-path L0/L1 (sin contrato, sin crítico) ---
def es_liviano(contract: dict) -> bool:
    """True si el contrato es L0 o L1 (no requiere contrato formal)."""
    return contract.get("nivel") in ("L0", "L1")


def ejecutar_liviano(contract: dict, verifier=None) -> dict:
    """Fast-path para L0/L1: ejecuta directo sin contrato ni crítico.

    Returns dict con nivel, resultado, evidencia, exito_falso.
    """
    from datetime import datetime
    nivel = contract.get("nivel", "L1")
    criterios = contract.get("criterios", [])

    # Verificación barata L0: check de 1 línea
    evidencias = []
    for cr in criterios:
        if cr["tipo"] == "humano":
            evidencias.append({"id": cr["id"], "ok": True, "evidencia": "humano (skip)"})
            continue
        if verifier is None:
            verifier = atlas_verifier.Verifier()
        r = verifier.ejecutar(cr)
        evidencias.append({"id": cr["id"], "ok": r.ok, "evidencia": r.evidencia})

    all_ok = all(e["ok"] for e in evidencias) if evidencias else True
    return {
        "nivel": nivel,
        "resultado": "OK" if all_ok else "FAIL",
        "evidencias": evidencias,
        "exito_falso": False,
        "ts": datetime.now().isoformat(),
    }
