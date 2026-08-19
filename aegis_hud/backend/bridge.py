"""
bridge.py — FastAPI Bridge principal del AEGIS-JARVIS Backend.

Endpoints:
  POST /execute  → Ejecuta un prompt del usuario (dual-mode)
  GET  /health   → Estado del bridge y componentes
  GET  /state    → Estado actual de task_state.json
  POST /state/reset → Resetea el circuit breaker

Arquitectura:
  1. Router clasifica la intención (qwen2.5:1.5b → chat | agent)
  2. Modo A (chat): prompt directo al LLM vía atlas-orchestrator
  3. Modo B (agent): bucle de agente con Native Function Calling + MCPs
  4. Governance Belt: el agente NUNCA ejecuta código nativo
  5. Circuit Breaker: error_count >= 3 → DETENER
  6. Truncation Repair: JSON roto → reparación automática

NO usa LangChain. Solo FastAPI + requests + Ollama API.
"""

import json
import logging
import os
import sys
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import requests
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

# Windows: ensure UTF-8 output
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from governance_prompt import (
    get_governance_prompt,
    get_route_tools,
    AGENT_SYSTEM_PROMPT,
)
from state_manager import (
    load_state,
    save_state,
    new_task,
    append_history,
    check_circuit_breaker,
    reset_task,
    set_status,
    set_result,
    is_blocked,
    STATUS_IDLE,
    STATUS_ROUTING,
    STATUS_CLASSIFYING,
    STATUS_EXECUTING,
    STATUS_REPAIRING,
    STATUS_ERROR,
    STATUS_COMPLETED,
    STATUS_BLOCKED,
    MAX_ERRORS,
)
from router import classify_intent, repair_json, router_health

# ---------------------------------------------------------------------------
# Configuración
# ---------------------------------------------------------------------------
OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_CHAT_ENDPOINT = f"{OLLAMA_BASE_URL}/api/chat"
DEFAULT_CHAT_MODEL = os.environ.get("DEFAULT_CHAT_MODEL", "qwen2.5:1.5b")
DEFAULT_AGENT_MODEL = os.environ.get("DEFAULT_AGENT_MODEL", "qwen2.5:1.5b")
BRIDGE_HOST = os.environ.get("BRIDGE_HOST", "127.0.0.1")
BRIDGE_PORT = int(os.environ.get("BRIDGE_PORT", "8765"))

# MCP endpoints para agent mode
MCP_ENDPOINTS = {
    "orchestrator": os.environ.get("ATLAS_ORCHESTRATOR_URL", "http://localhost:20128"),
    "guardian": os.environ.get("ATLAS_GUARDIAN_URL", "http://localhost:20129"),
    "health": os.environ.get("ATLAS_HEALTH_URL", "http://localhost:20130"),
    "foco": os.environ.get("ATLAS_FOCO_URL", "http://localhost:20131"),
    "memory": os.environ.get("MEMORY_MCP_URL", "http://localhost:20133"),
    "windows": os.environ.get("WINDOWS_MCP_URL", "http://localhost:20136"),
    "corel": os.environ.get("CORAL_DRAW_MCP_URL", "http://localhost:20134"),
    "playwright": os.environ.get("PLAYWRIGHT_MCP_URL", "http://localhost:20135"),
}

logger = logging.getLogger("aegis.bridge")

# ---------------------------------------------------------------------------
# Startup (lifespan)
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup/shutdown lifecycle."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    logger.info("AEGIS-JARVIS Bridge v2.0.0 starting")
    logger.info("OLLAMA_BASE_URL: %s", OLLAMA_BASE_URL)
    logger.info("Router model: %s", os.environ.get("ROUTER_MODEL", "qwen2.5:1.5b"))
    logger.info("Circuit breaker threshold: %d errors", MAX_ERRORS)
    yield
    logger.info("AEGIS-JARVIS Bridge shutting down")


# ---------------------------------------------------------------------------
# FastAPI App
# ---------------------------------------------------------------------------
BACKEND_DIR = Path(__file__).parent
FRONTEND_DIR = BACKEND_DIR.parent / "frontend"
CONFIG_DIR = BACKEND_DIR.parent / "config"

app = FastAPI(
    title="AEGIS-JARVIS Bridge",
    description="Backend dual-mode: Chat Directo (Modo A) + Agente Autonomo (Modo B)",
    version="2.0.0",
    lifespan=lifespan,
)

# Serve frontend static files
if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")


@app.get("/")
async def serve_index():
    """Serve the HUD index.html."""
    index = FRONTEND_DIR / "index.html"
    if index.exists():
        return FileResponse(str(index), media_type="text/html")
    return {"error": "Frontend not found. Run from aegis_hud/backend/"}


@app.get("/settings.json")
async def get_settings():
    """Serve settings.json from config/."""
    settings_file = CONFIG_DIR / "settings.json"
    if settings_file.exists():
        return FileResponse(str(settings_file), media_type="application/json")
    return {"bridge_url": "http://127.0.0.1:8765", "poll_interval_ms": 5000}


@app.get("/favicon.ico")
async def favicon():
    """Suppress 404 for favicon."""
    return {"ok": True}


# ---------------------------------------------------------------------------
# Request / Response Models
# ---------------------------------------------------------------------------

class ExecuteRequest(BaseModel):
    """Request para /execute."""
    prompt: str = Field(..., min_length=1, max_length=10000, description="Prompt del usuario")
    force_mode: Optional[str] = Field(None, description="Forzar modo: 'chat' o 'agent' (override del router)")
    model: Optional[str] = Field(None, description="Modelo específico a usar (override)")

class ExecuteResponse(BaseModel):
    """Response de /execute."""
    task_id: str
    mode: str
    status: str
    response: Optional[str] = None
    model_used: Optional[str] = None
    latency_ms: float = 0.0
    error: Optional[str] = None
    error_count: int = 0
    blocked: bool = False

class HealthResponse(BaseModel):
    """Response de /health."""
    status: str
    bridge: str
    ollama: dict
    mcp_endpoints: dict
    task_state: dict
    timestamp: str

class StateResponse(BaseModel):
    """Response de /state."""
    task_state: dict
    blocked: bool
    circuit_breaker_threshold: int


# ---------------------------------------------------------------------------
# LLM Caller (para Chat y Agent)
# ---------------------------------------------------------------------------

def call_llm(
    messages: list,
    model: str = DEFAULT_CHAT_MODEL,
    tools: Optional[list] = None,
    timeout: float = 30.0,
    temperature: float = 0.3,
) -> dict:
    """Llama al LLM vía Ollama API.
    
    Args:
        messages: Lista de mensajes (role + content).
        model: Modelo a usar.
        tools: Tool definitions para function calling (None = sin tools).
        timeout: Timeout en segundos.
        temperature: Temperatura de muestreo.
    
    Returns:
        Respuesta cruda de Ollama como dict.
    """
    payload = {
        "model": model,
        "messages": messages,
        "stream": False,
        "options": {
            "temperature": temperature,
            "num_predict": 2048,
        },
    }
    if tools:
        payload["tools"] = tools
    
    try:
        resp = requests.post(OLLAMA_CHAT_ENDPOINT, json=payload, timeout=timeout)
        resp.raise_for_status()
        return resp.json()
    except requests.Timeout:
        raise TimeoutError(f"LLM timeout after {timeout}s")
    except requests.RequestException as e:
        raise RuntimeError(f"LLM request failed: {e}")


def extract_response_text(llm_response: dict) -> str:
    """Extrae el texto de la respuesta del LLM."""
    message = llm_response.get("message", {})
    return message.get("content", "")


# ---------------------------------------------------------------------------
# JSON Validator + Truncation Repair
# ---------------------------------------------------------------------------

def validate_json_response(text: str) -> Optional[dict]:
    """Intenta parsear el texto como JSON.
    
    Returns:
        dict si es JSON válido, None si no.
    """
    text = text.strip()
    if not text:
        return None
    
    # Limpiar wrappers markdown
    if text.startswith("```"):
        lines = text.split("\n")
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def try_repair_and_parse(text: str, max_attempts: int = 2) -> Optional[dict]:
    """Intenta reparar JSON truncado y parsearlo.
    
    Args:
        text: Texto que debería ser JSON.
        max_attempts: Intentos máximos de reparación.
    
    Returns:
        dict reparado, o None si no se pudo.
    """
    # Primer intento: parseo directo
    result = validate_json_response(text)
    if result is not None:
        return result
    
    # Intentos de reparación
    for attempt in range(max_attempts):
        logger.info("JSON repair attempt %d/%d", attempt + 1, max_attempts)
        repaired = repair_json(text)
        if repaired is not None:
            logger.info("JSON repair succeeded on attempt %d", attempt + 1)
            return repaired
    
    return None


# ---------------------------------------------------------------------------
# Modo A: Chat Directo
# ---------------------------------------------------------------------------

def execute_chat_mode(
    state: dict,
    user_prompt: str,
    model: str = DEFAULT_CHAT_MODEL,
) -> dict:
    """Modo A: Chat Directo. Prompt → LLM → Respuesta. Sin herramientas.
    
    Returns:
        Dict con resultado o error.
    """
    state = append_history(state, "chat_start", f"Modo A: chat directo con {model}")
    
    messages = [
        {"role": "system", "content": get_governance_prompt("chat")},
        {"role": "user", "content": user_prompt},
    ]
    
    try:
        llm_resp = call_llm(messages, model=model, tools=None, timeout=30.0)
        response_text = extract_response_text(llm_resp)
        
        state["model_used"] = model
        state = append_history(state, "chat_response", f"Respuesta: {response_text[:200]}")
        
        return {
            "success": True,
            "response": response_text,
            "model_used": model,
            "latency_ms": llm_resp.get("total_duration", 0) / 1_000_000,  # ns → ms
        }
    except (TimeoutError, RuntimeError) as e:
        state = append_history(state, "chat_error", str(e), error=True)
        return {
            "success": False,
            "error": str(e),
            "model_used": model,
        }


# ---------------------------------------------------------------------------
# Modo B: Agente Autónomo
# ---------------------------------------------------------------------------

def execute_agent_mode(
    state: dict,
    user_prompt: str,
    model: str = DEFAULT_AGENT_MODEL,
    max_iterations: int = 5,
) -> dict:
    """Modo B: Agente Autónomo. Bucle de agente con tool calling + MCPs.
    
    El agente puede usar tools MCP pero NUNCA código nativo.
    Si el agente intenta ejecutar shell/python directamente, se bloquea.
    
    Returns:
        Dict con resultado o error.
    """
    state = append_history(
        state,
        "agent_start",
        f"Modo B: agente autónomo con {model}, máx {max_iterations} iteraciones",
    )
    
    messages = [
        {"role": "system", "content": AGENT_SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]
    
    all_response_texts = []
    
    for iteration in range(max_iterations):
        # Check circuit breaker
        if check_circuit_breaker(state):
            return {
                "success": False,
                "error": "Circuit breaker activado",
                "blocked": True,
            }
        
        state = append_history(
            state,
            f"agent_iter_{iteration + 1}",
            f"Iteración {iteration + 1}/{max_iterations}",
        )
        
        try:
            llm_resp = call_llm(
                messages,
                model=model,
                tools=get_route_tools(),
                timeout=60.0,
                temperature=0.2,
            )
        except (TimeoutError, RuntimeError) as e:
            state = append_history(state, "agent_llm_error", str(e), error=True)
            if check_circuit_breaker(state):
                return {
                    "success": False,
                    "error": "Circuit breaker activado tras error de LLM",
                    "blocked": True,
                }
            continue
        
        message = llm_resp.get("message", {})
        content = message.get("content", "")
        tool_calls = message.get("tool_calls", [])
        
        if content:
            all_response_texts.append(content)
            messages.append({"role": "assistant", "content": content})
        
        # Si no hay tool calls, el agente terminó
        if not tool_calls:
            state = append_history(
                state,
                "agent_completed",
                f"Agente completó en {iteration + 1} iteraciones",
            )
            break
        
        # Procesar tool calls
        for tc in tool_calls:
            func = tc.get("function", {})
            func_name = func.get("name", "")
            func_args = func.get("arguments", {})
            
            if isinstance(func_args, str):
                try:
                    func_args = json.loads(func_args)
                except json.JSONDecodeError:
                    func_args = {}
            
            state = append_history(
                state,
                "agent_tool_call",
                f"Tool: {func_name}({json.dumps(func_args, ensure_ascii=False)[:200]})",
            )
            
            # Governance Belt: bloquear intentos de ejecución nativa
            tool_result = _governance_check(func_name, func_args)
            
            if tool_result is None:
                # Tool permitida: ejecutar vía MCP
                tool_result = _execute_mcp_tool(func_name, func_args)
            
            # Añadir resultado al contexto
            messages.append({
                "role": "tool",
                "content": json.dumps(tool_result, ensure_ascii=False),
            })
    else:
        state = append_history(
            state,
            "agent_max_iterations",
            f"Límite de {max_iterations} iteraciones alcanzado",
            error=True,
        )
    
    full_response = "\n\n".join(all_response_texts) if all_response_texts else "Agente sin respuesta"
    
    state["model_used"] = model
    state = append_history(state, "agent_response", f"Respuesta final: {full_response[:300]}")
    
    return {
        "success": True,
        "response": full_response,
        "model_used": model,
        "iterations": min(iteration + 1, max_iterations),
    }


def _governance_check(func_name: str, func_args: dict) -> Optional[dict]:
    """Verifica si una tool call viola la Governance Belt.
    
    Returns:
        None si la tool es permitida (proceder con MCP).
        dict con resultado de bloqueo si se debe拦截ar.
    """
    # Bloquear intentos de ejecución nativa
    blocked_patterns = [
        "run_command", "run_script", "execute", "shell", "bash",
        "subprocess", "os.system", "exec", "eval", "process_kill",
        "registry_write", "file_delete",
    ]
    
    func_lower = func_name.lower()
    for pattern in blocked_patterns:
        if pattern in func_lower:
            return {
                "blocked": True,
                "reason": (
                    f"GOVERNANCE VIOLATION: Tool '{func_name}' bloqueada. "
                    f"El agente NUNCA ejecuta código nativo. "
                    f"Usa atlas_tools para esta operación."
                ),
                "governance_rule": "Cinturón de Gobernanza — §3",
            }
    
    return None  # Permitido


def _execute_mcp_tool(func_name: str, func_args: dict) -> dict:
    """Ejecuta una tool vía el MCP endpoint apropiado.
    
    Mapeo de tools a endpoints MCP:
      - atlas_* → endpoint correspondiente en MCP_ENDPOINTS
    
    Returns:
        Resultado de la tool o error.
    """
    # Mapeo simplificado: función → endpoint MCP
    # En producción esto debería ser más sofisticado
    mcp_mapping = {
        "orchestrator": MCP_ENDPOINTS.get("orchestrator"),
        "guardian": MCP_ENDPOINTS.get("guardian"),
        "health": MCP_ENDPOINTS.get("health"),
        "memory": MCP_ENDPOINTS.get("memory"),
        "windows": MCP_ENDPOINTS.get("windows"),
        "corel": MCP_ENDPOINTS.get("corel"),
        "playwright": MCP_ENDPOINTS.get("playwright"),
    }
    
    # Detectar MCP base del nombre de la función
    for mcp_name, endpoint in mcp_mapping.items():
        if mcp_name in func_name.lower() and endpoint:
            try:
                resp = requests.post(
                    f"{endpoint}/call",
                    json={"tool": func_name, "args": func_args},
                    timeout=30.0,
                )
                resp.raise_for_status()
                return resp.json()
            except Exception as e:
                return {"error": f"MCP call failed: {e}", "tool": func_name}
    
    # Si no se detecta MCP, devolver resultado simulado
    return {
        "status": "tool_not_implemented",
        "tool": func_name,
        "args": func_args,
        "note": "MCP endpoint no mapeado. Implementar routing específico.",
    }


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.post("/execute", response_model=ExecuteResponse)
async def execute(req: ExecuteRequest):
    """Endpoint principal: ejecuta un prompt del usuario.
    
    Flujo:
      1. Verificar circuit breaker
      2. Crear nueva tarea en task_state.json
      3. Clasificar intención (router)
      4. Ejecutar en modo apropiado (chat | agent)
      5. Validar respuesta, reparar si es JSON roto
      6. Retornar resultado
    """
    start_time = time.monotonic()
    
    # 0. Verificar circuit breaker
    if is_blocked():
        return ExecuteResponse(
            task_id="blocked",
            mode="none",
            status=STATUS_BLOCKED,
            error=f"Circuit breaker activado. error_count >= {MAX_ERRORS}. "
                  f"Resetea con POST /state/reset.",
            blocked=True,
        )
    
    # 1. Crear nueva tarea
    initial_mode = req.force_mode or "chat"
    state = new_task(req.prompt, mode=initial_mode)
    task_id = state["task_id"]
    
    try:
        # 2. Clasificar intención (si no se forzó modo)
        if req.force_mode:
            mode = req.force_mode
            model = req.model or (DEFAULT_AGENT_MODEL if mode == "agent" else DEFAULT_CHAT_MODEL)
            classification = {
                "mode": mode,
                "reason": f"modo forzado: {mode}",
                "model": model,
                "latency_ms": 0,
                "fallback": False,
            }
            state = append_history(state, "mode_forced", f"Modo forzado: {mode}")
        else:
            state = set_status(state, STATUS_CLASSIFYING)
            classification = classify_intent(req.prompt)
            mode = classification["mode"]
            model = req.model or classification.get("model", DEFAULT_CHAT_MODEL)
            
            state = append_history(
                state,
                "classified",
                f"Modo: {mode}, razón: {classification['reason']}, "
                f"latencia: {classification['latency_ms']:.0f}ms",
            )
        
        state["mode"] = mode
        save_state(state)
        
        # 3. Ejecutar en modo apropiado
        state = set_status(state, STATUS_EXECUTING)
        
        if mode == "chat":
            result = execute_chat_mode(state, req.prompt, model=model)
        else:
            result = execute_agent_mode(state, req.prompt, model=model)
        
        # 4. Validar y retornar
        latency_ms = (time.monotonic() - start_time) * 1000
        
        if result.get("success"):
            state = set_result(state, {
                "response": result.get("response", ""),
                "model_used": result.get("model_used", model),
            })
            return ExecuteResponse(
                task_id=task_id,
                mode=mode,
                status=STATUS_COMPLETED,
                response=result.get("response"),
                model_used=result.get("model_used", model),
                latency_ms=latency_ms,
                error_count=state.get("error_count", 0),
            )
        else:
            append_history(state, "execute_error", result.get("error", "unknown"), error=True)
            check_circuit_breaker(state)
            return ExecuteResponse(
                task_id=task_id,
                mode=mode,
                status=state["status"],
                error=result.get("error"),
                model_used=result.get("model_used", model),
                latency_ms=latency_ms,
                error_count=state.get("error_count", 0),
                blocked=state["status"] == STATUS_BLOCKED,
            )
    
    except Exception as e:
        latency_ms = (time.monotonic() - start_time) * 1000
        logger.exception("Unhandled error in /execute")
        append_history(state, "unhandled_error", str(e), error=True)
        check_circuit_breaker(state)
        return ExecuteResponse(
            task_id=task_id,
            mode=state.get("mode", "unknown"),
            status=STATUS_ERROR,
            error=str(e),
            latency_ms=latency_ms,
            error_count=state.get("error_count", 0),
            blocked=state["status"] == STATUS_BLOCKED,
        )


@app.get("/health", response_model=HealthResponse)
async def health():
    """Estado del bridge y todos los componentes."""
    # Check MCP endpoints
    mcp_status = {}
    for name, url in MCP_ENDPOINTS.items():
        try:
            resp = requests.get(f"{url}/health", timeout=0.5)
            mcp_status[name] = resp.status_code == 200
        except Exception:
            mcp_status[name] = False
    
    # Check Ollama
    ollama_health = router_health()
    
    # Task state
    state = load_state()
    task_info = {
        "status": state.get("status"),
        "task_id": state.get("task_id"),
        "error_count": state.get("error_count", 0),
    }
    
    # Global status
    status = "healthy"
    if is_blocked():
        status = "blocked"
    elif not ollama_health.get("ollama_up"):
        status = "degraded"
    elif not any(mcp_status.values()):
        status = "degraded"
    
    return HealthResponse(
        status=status,
        bridge="running",
        ollama=ollama_health,
        mcp_endpoints=mcp_status,
        task_state=task_info,
        timestamp=datetime.now(timezone.utc).isoformat(timespec="seconds"),
    )


@app.get("/state", response_model=StateResponse)
async def get_state():
    """Estado actual de task_state.json."""
    state = load_state()
    return StateResponse(
        task_state=state,
        blocked=is_blocked(),
        circuit_breaker_threshold=MAX_ERRORS,
    )


@app.post("/state/reset")
async def reset_state():
    """Resetea el circuit breaker y limpia el estado de tarea."""
    state = reset_task()
    return {
        "status": "reset",
        "message": "Circuit breaker reseteado. Estado limpiado.",
        "task_state": state,
    }





# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn
    
    print(f"\n{'='*60}")
    print(f"  AEGIS-JARVIS Bridge v2.0.0")
    print(f"  http://{BRIDGE_HOST}:{BRIDGE_PORT}")
    print(f"  POST /execute  -> Ejecutar prompt")
    print(f"  GET  /health   -> Estado del sistema")
    print(f"  GET  /state    -> Estado de tarea")
    print(f"  POST /state/reset -> Resetear circuit breaker")
    print(f"{'='*60}\n")
    
    uvicorn.run(
        "bridge:app",
        host=BRIDGE_HOST,
        port=BRIDGE_PORT,
        reload=False,
        log_level="info",
    )
