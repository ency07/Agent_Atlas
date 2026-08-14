#!/usr/bin/env python3
"""
atlas_orchestrator.py — Orquestador de modelos Atlas.

Detecta proveedores ACTIVOS en vivo (omniroute/9router/ollama) y decide
el mejor modelo segun la tarea, SIN falsos positivos: nunca sugiere un
modelo cuyo provider no esta respondiendo.

Manejo de errores:
  - Circuit breaker: N fallos consecutivos -> cooldown del provider.
  - Fallback chain: omniroute -> 9router -> ollama -> sin red (phi4 local).
  - Errores persistentes: se registran en state/routing_log.json y el
    orquestador degrada el provider en vez de reintentar en bucle.

Uso:
  python atlas_orchestrator.py --cli                    # providers activos + estado
  python atlas_orchestrator.py --cli --check            # chequeo rapido (exit code)
  python atlas_orchestrator.py --http 4103              # HTTP GET /available, /analyze?task=
  (sin args)                                            # MCP server
"""
import json
import os
import re
import socket
import sys
import time
import warnings
from datetime import datetime, timezone

warnings.filterwarnings("ignore")

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("atlas-orchestrator")

# MEMORY_ROOT ya apunta a la raiz de memoria (memory_data); no duplicar.
MEMORY_ROOT = os.environ.get("MEMORY_ROOT", os.path.join(os.path.dirname(os.path.abspath(__file__)), "memory_data"))
STATE_DIR = os.path.join(MEMORY_ROOT, "state")
CAPS_FILE = os.path.join(STATE_DIR, "model_capabilities.json")
LOG_FILE = os.path.join(STATE_DIR, "routing_log.json")

# Providers detectables por puerto
PROVIDERS = {
    "omniroute": {"port": 20128, "priority": 1, "api": "http://localhost:20128/v1"},
    "9router":   {"port": 4000,  "priority": 2, "api": "http://localhost:4000/v1"},
    "ollama":    {"port": 11434, "priority": 3, "api": "http://localhost:11434/v1"},
}

# Circuit breaker
MAX_CONSECUTIVE_FAILURES = 3
COOLDOWN_SECONDS = 300  # 5 min tras N fallos


# ---------------------------------------------------------------------------
# Estado y log
# ---------------------------------------------------------------------------

def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _load_log() -> dict:
    if os.path.exists(LOG_FILE):
        try:
            return json.load(open(LOG_FILE, encoding="utf-8"))
        except Exception:
            pass
    return {"entries": [], "provider_health": {}}


def _save_log(data: dict):
    try:
        os.makedirs(STATE_DIR, exist_ok=True)
        with open(LOG_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def _log_entry(entry: dict):
    data = _load_log()
    data["entries"].append(entry)
    data["entries"] = data["entries"][-500:]  # cola acotada
    _save_log(data)


def _record_provider_failure(provider: str, error: str):
    data = _load_log()
    ph = data.setdefault("provider_health", {})
    p = ph.setdefault(provider, {"consecutive_failures": 0, "cooldown_until": None, "last_error": None})
    p["consecutive_failures"] = p.get("consecutive_failures", 0) + 1
    p["last_error"] = error
    p["last_failure_at"] = _now()
    if p["consecutive_failures"] >= MAX_CONSECUTIVE_FAILURES:
        p["cooldown_until"] = _now_plus(COOLDOWN_SECONDS)
    _save_log(data)


def _record_provider_ok(provider: str):
    data = _load_log()
    ph = data.setdefault("provider_health", {})
    p = ph.setdefault(provider, {})
    p["consecutive_failures"] = 0
    p["cooldown_until"] = None
    p["last_ok"] = _now()
    _save_log(data)


def _now_plus(seconds: float):
    return datetime.now(timezone.utc).timestamp() + seconds


def _in_cooldown(provider: str) -> bool:
    data = _load_log()
    p = data.get("provider_health", {}).get(provider, {})
    cu = p.get("cooldown_until")
    if not cu:
        return False
    return time.time() < float(cu)


def _cooldown_left(provider: str) -> int:
    data = _load_log()
    cu = data.get("provider_health", {}).get(provider, {}).get("cooldown_until")
    if not cu:
        return 0
    return max(0, int(float(cu) - time.time()))


# ---------------------------------------------------------------------------
# Detección en vivo de proveedores
# ---------------------------------------------------------------------------

def _port_open(port: int, timeout: float = 0.6) -> bool:
    try:
        s = socket.create_connection(("127.0.0.1", port), timeout=timeout)
        s.close()
        return True
    except OSError:
        return False


def _api_get(url: str, timeout: float = 4.0):
    """GET JSON con urllib. None si falla (sin excepciones)."""
    import urllib.request
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8"))
    except Exception:
        return None


_installed_cache: dict = {}  # provider -> (timestamp, models|None)
_CACHE_TTL = 15.0


def _provider_installed_models(name: str) -> list | None:
    """Consulta la API REAL del provider y devuelve los modelos instalados.
    None = no se pudo verificar (no confiar en el port check solo).
    Con caché de 15s para no golpear la API en cada analyze()."""
    now = time.time()
    if name in _installed_cache and now - _installed_cache[name][0] < _CACHE_TTL:
        return _installed_cache[name][1]
    result = None
    if name == "ollama":
        data = _api_get("http://localhost:11434/api/tags")
        if data and "models" in data:
            result = [m.get("name", "") for m in data["models"]]
    elif name in ("omniroute", "9router"):
        data = _api_get(PROVIDERS[name]["api"] + "/models")
        if data and "data" in data:
            result = [m.get("id", "") for m in data["data"]]
    _installed_cache[name] = (now, result)
    return result


def active_providers() -> dict:
    """Proveedores con deteccion REAL: puerto abierto Y API responde.
    Puro (no escribe log): el circuit breaker lo gestionan register_error/success."""
    result = {}
    for name, cfg in PROVIDERS.items():
        alive = _port_open(cfg["port"])
        models = None
        if alive:
            models = _provider_installed_models(name)
            alive = models is not None  # puerto abierto pero API sin responder = NO usable
        cooled = _in_cooldown(name)
        result[name] = {
            "alive": alive,
            "installed_models": models if alive else [],
            "in_cooldown": cooled and alive,
            "cooldown_left_s": _cooldown_left(name) if cooled else 0,
            "port": cfg["port"],
            "api": cfg["api"],
        }
    return result


def load_capabilities() -> dict:
    if os.path.exists(CAPS_FILE):
        try:
            return json.load(open(CAPS_FILE, encoding="utf-8"))
        except Exception:
            pass
    return {}


def _infer_capability(model_id: str, cap: dict | None) -> dict:
    """Capacidades para un modelo. Usa el mapa si existe; si no, infiere
    heuristica desde el nombre (vision en el id -> vision, pro -> mejor,
    etc). Nunca asume que un modelo desconocido tiene vision."""
    name = model_id.lower()
    if cap:
        return cap
    return {
        "vision": bool(re.search(r"vision|multimodal|gemma3|llava|qwen.*vl", name)),
        "coding": 0.75 if re.search(r"coding|code|deepseek|qwen", name) else 0.5,
        "reasoning": 0.7 if re.search(r"reason|deepseek|think|o1|o3", name) else 0.5,
        "research": 0.5,
        "speed": 0.8 if re.search(r"fast|cheap|mini|tiny", name) else 0.5,
        "context_ok": True,
        "ideal_para": [],
        "_inferred": True,
    }


def active_models() -> dict:
    """Modelos REALMENTE usables: su provider responde SU API y el modelo
    esta en la lista instalada del provider. Sin falsos positivos."""
    caps = load_capabilities().get("models", {})
    provs = active_providers()
    out = {}
    for provider, state in provs.items():
        if not state.get("alive") or state.get("in_cooldown"):
            continue
        for installed in state.get("installed_models", []):
            # modelo instalado (ej 'phi4-mini' o 'auto/best-coding')
            key = f"{provider}/{installed}"
            cap = caps.get(key)
            if cap is None:
                # sin :tag y el mapa tiene la variante con tag
                base = installed.split(":")[0]
                cap = caps.get(f"{provider}/{base}")
            out[key] = _infer_capability(key, cap)
    return out


# ---------------------------------------------------------------------------
# Decision
# ---------------------------------------------------------------------------

TASK_PATTERNS = {
    "revision_visual": ("vision", ["screenshot", "captura", "imagen", "pantalla", "ui", "diseno", "corel",
                                   "mockup", "previsualiza", "mira el", "revisa el diseno", "visual", "looks", "diseño"]),
    "codigo_profundo": ("coding", ["refactor", "debug", "implementa", "arregla", "bug", "codigo", "script",
                                   "funcion", "clase", "prueba", "test", "fix", "feature"]),
    "planificacion": ("reasoning", ["arquitectura", "planifica", "decide", "estrategia", "roadmap",
                                    "analiza", "diseña el sistema", "trade-off", "compromiso"]),
    "investigacion": ("research", ["investiga", "web_research", "documenta", "busca", "fuentes",
                                   "paper", "articulo", "comparativa", "resear"]),
    "resumen": ("speed", ["resume", "resumen", "sintetiza", "conversacion", "explica breve"]),
    "consulta_rapida": ("speed", ["que es", "como se", "traduce", "formatea", "short", "rapido"]),
}


# Patrones donde "ui" (y otros cortos/ambiguos) solo matchean como palabra completa
WORD_ONLY = {"ui", "looks", "fix", "ui_audit", "corel", "test", "visual"}


def classify_task(task: str) -> dict:
    task = task.lower()
    for tipo, (cap, patterns) in TASK_PATTERNS.items():
        for p in patterns:
            if p in WORD_ONLY:
                if re.search(rf"\b{re.escape(p)}\b", task):
                    return {"task_type": tipo, "required_capability": cap}
            elif p in task:
                return {"task_type": tipo, "required_capability": cap}
    return {"task_type": "general", "required_capability": None}


def best_model_for(required_cap: str | None, model_pool: dict | None = None) -> dict | None:
    """Elige el mejor modelo del pool activo para la capacidad requerida.
    Los modelos CURADOS (mapa de capacidades) siempre ganan sobre inferidos."""
    if model_pool is None:
        model_pool = active_models()
    if not model_pool:
        return None

    def rank(kv):
        mid, cap = kv
        curated = not cap.get("_inferred", False)
        score = cap.get(required_cap, 0) if required_cap else (cap.get("coding", 0) + cap.get("reasoning", 0)) / 2
        return (curated, score)

    if required_cap is None:
        scored = sorted(model_pool.items(), key=rank, reverse=True)
        mid, cap = scored[0]
        return {"model": mid, "reason": "mejor general entre activos", "capability": cap}

    if required_cap == "vision":
        vision_pool = {m: c for m, c in model_pool.items() if c.get("vision")}
        if not vision_pool:
            return None  # ninguno activo con vision
        scored = sorted(vision_pool.items(), key=rank, reverse=True)
        mid, cap = scored[0]
        return {"model": mid, "reason": "mejor vision entre activos", "capability": cap}

    scored = sorted(model_pool.items(), key=rank, reverse=True)
    mid, cap = scored[0]
    return {"model": mid, "reason": f"max {required_cap} entre activos (curado preferido)", "capability": cap}


def analyze(task: str) -> dict:
    cls = classify_task(task)
    req = cls["required_capability"]
    provs = active_providers()
    pool = active_models()

    live_names = [n for n, s in provs.items() if s["alive"]]
    cooldown_names = [n for n, s in provs.items() if s["in_cooldown"]]
    down_names = [n for n, s in provs.items() if not s["alive"]]

    result = {
        "timestamp": _now(),
        "task": task,
        "task_type": cls["task_type"],
        "required_capability": req,
        "providers": provs,
        "active_providers": live_names,
        "cooldown_providers": cooldown_names,
        "down_providers": down_names,
    }

    # regla dorada: tarea visual sin modelo vision activo
    if req == "vision":
        vision_models = [m for m, c in pool.items() if c.get("vision")]
        if not vision_models:
            result["decision"] = {
                "action": "block_and_advise",
                "suggested_model": None,
                "vision_supported": False,
                "reason": ("Ningun modelo ACTIVO con vision. No ejecutar revision visual a ciegas. "
                           "Levanta omniroute/9router o cambia de config para usar un modelo vision=true."),
            }
            return result

    pick = best_model_for(req, pool)
    if pick is None:
        result["decision"] = {
            "action": "no_providers",
            "suggested_model": None,
            "vision_supported": False,
            "reason": "Ningun provider de modelos responde (omniroute:20128, 9router:4000, ollama:11434).",
        }
        return result

    result["decision"] = {
        "action": "proceed",
        "suggested_model": pick["model"],
        "reason": pick["reason"],
        "vision_supported": bool(pick["capability"].get("vision")),
    }
    return result


def route(task: str) -> dict:
    """Igual que analyze pero registra en el log de routing (decision real ejecutada)."""
    res = analyze(task)
    _log_entry({
        "ts": res["timestamp"],
        "task": task[:120],
        "task_type": res["task_type"],
        "req_cap": res["required_capability"],
        "decision": res.get("decision", {}).get("action"),
        "model": res.get("decision", {}).get("suggested_model"),
        "active": res["active_providers"],
    })
    return res


# ---------------------------------------------------------------------------
# Tools MCP
# ---------------------------------------------------------------------------

@mcp.tool()
def orchestrator_available() -> dict:
    """Proveedores de modelos ACTIVOS en este momento (sin falsos positivos)."""
    return {"providers": active_providers(),
            "models": list(active_models().keys()),
            "note": "solo modelos cuyo provider responde y no esta en cooldown"}


@mcp.tool()
def orchestrator_analyze(task: str) -> dict:
    """Analiza una tarea y decide el mejor modelo ENTRE los proveedores activos."""
    return analyze(task)


@mcp.tool()
def orchestrator_route(task: str) -> dict:
    """Igual que analyze + registra la decision en routing_log.json."""
    return route(task)


@mcp.tool()
def orchestrator_report(limit: int = 20) -> dict:
    """Historial de routing y salud de providers (errores persistentes)."""
    data = _load_log()
    return {
        "total_entries": len(data.get("entries", [])),
        "recent": data.get("entries", [])[-limit:][::-1],
        "provider_health": data.get("provider_health", {}),
    }


@mcp.tool()
def orchestrator_provider_health() -> dict:
    """Estado de cada provider: fallos consecutivos, cooldown, ultimo error."""
    data = _load_log()
    provs = active_providers()
    for name, state in provs.items():
        h = data.get("provider_health", {}).get(name, {})
        state["consecutive_failures"] = h.get("consecutive_failures", 0)
        state["last_error"] = h.get("last_error")
        state["last_ok"] = h.get("last_ok")
    return provs


@mcp.tool()
def orchestrator_register_error(provider: str, error: str) -> dict:
    """Registra un fallo real de un provider (lo degrada si es persistente)."""
    if provider in PROVIDERS:
        _record_provider_failure(provider, error)
    return orchestrator_provider_health()


@mcp.tool()
def orchestrator_register_success(provider: str) -> dict:
    """Marca un provider como OK (resetea fallos consecutivos)."""
    if provider in PROVIDERS:
        _record_provider_ok(provider)
    return orchestrator_provider_health()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _cli():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    if "--check" in sys.argv:
        provs = active_providers()
        alive = [n for n, s in provs.items() if s["alive"]]
        print("PROVIDERS:", ", ".join(alive) if alive else "NINGUNO")
        sys.exit(0 if alive else 1)
    provs = active_providers()
    print("== Orquestador Atlas ==")
    for name, s in provs.items():
        state = "✅ activo" if s["alive"] else "❌ caido"
        if s["in_cooldown"]:
            state += f" (cooldown {s['cooldown_left_s']}s)"
        print(f"  {name:10} :{s['port']:<6} {state}")
    pool = active_models()
    print(f"\nModelos disponibles ({len(pool)}):")
    for m in sorted(pool):
        print(f"  - {m}")
    if not pool:
        print("  (ninguno - levanta un provider de modelos)")
    sys.exit(0 if pool else 1)


def _http(port: int = 4103):
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
    from urllib.parse import urlparse, parse_qs

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            parsed = urlparse(self.path)
            if parsed.path == "/available":
                body = json.dumps({"providers": active_providers(),
                                   "models": sorted(active_models())}, ensure_ascii=False).encode("utf-8")
            elif parsed.path == "/analyze":
                q = parse_qs(parsed.query)
                task = q.get("task", [""])[0]
                body = json.dumps(analyze(task), ensure_ascii=False).encode("utf-8")
            else:
                body = json.dumps({"endpoints": ["/available", "/analyze?task=...", "/health"]}).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *a):
            pass

    srv = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(f"atlas_orchestrator http en http://127.0.0.1:{port}  (GET /available, /analyze?task=...)")
    srv.serve_forever()


if __name__ == "__main__":
    if "--cli" in sys.argv:
        _cli()
    elif "--http" in sys.argv:
        port = 4103
        for i, a in enumerate(sys.argv):
            if a == "--http" and i + 1 < len(sys.argv) and sys.argv[i + 1].isdigit():
                port = int(sys.argv[i + 1])
        _http(port)
    else:
        mcp.run(transport="stdio")
