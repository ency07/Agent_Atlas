"""
router.py — Clasificador de intención con qwen2.5:1.5b vía Ollama.

Usa Native Function Calling de Ollama para clasificar la intención
del usuario en dos categorías:
  - route_to_simple_chat  → Modo A (Chat Directo)
  - route_to_complex_agent → Modo B (Agente Autónomo)

Fail-safe:
  - Si el modelo tarda >2s → asume route_to_simple_chat
  - Si falla la llamada → asume route_to_simple_chat
  - Si el JSON de respuesta está roto → intenta reparación

NO usa LangChain. Solo requests + Ollama API nativa.
"""

import json
import os
import time
import logging
from typing import Optional

import requests

from governance_prompt import get_route_tools

# ---------------------------------------------------------------------------
# Configuración
# ---------------------------------------------------------------------------
OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
ROUTER_MODEL = os.environ.get("ROUTER_MODEL", "qwen2.5:1.5b")
ROUTER_TIMEOUT = float(os.environ.get("ROUTER_TIMEOUT", "2.0"))  # segundos
OLLAMA_CHAT_ENDPOINT = f"{OLLAMA_BASE_URL}/api/chat"

logger = logging.getLogger("aegis.router")


# ---------------------------------------------------------------------------
# Clasificación
# ---------------------------------------------------------------------------

def classify_intent(user_prompt: str) -> dict:
    """Clasifica la intención del usuario usando Ollama Native Function Calling.
    
    Args:
        user_prompt: El texto del usuario.
    
    Returns:
        {
            "mode": "chat" | "agent",
            "reason": str,
            "estimated_steps": int | None,
            "latency_ms": float,
            "model": str,
            "fallback": bool,  # True si se usó fail-safe
        }
    """
    start = time.monotonic()
    
    # Preparar el request para Ollama Native Function Calling
    payload = {
        "model": ROUTER_MODEL,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are an intent classifier. Analyze the user's message "
                    "and decide if it needs simple chat (route_to_simple_chat) "
                    "or autonomous agent tools (route_to_complex_agent). "
                    "Simple: greetings, questions, explanations, summaries. "
                    "Complex: file operations, system commands, browsing, "
                    "coding with execution, design, multi-step automation."
                ),
            },
            {
                "role": "user",
                "content": user_prompt,
            },
        ],
        "tools": get_route_tools(),
        "stream": False,
        "options": {
            "temperature": 0.1,
            "num_predict": 200,
        },
    }
    
    try:
        response = requests.post(
            OLLAMA_CHAT_ENDPOINT,
            json=payload,
            timeout=ROUTER_TIMEOUT,
        )
        response.raise_for_status()
        data = response.json()
    except requests.Timeout:
        elapsed = (time.monotonic() - start) * 1000
        logger.warning(
            "Router timeout (%.0fms > %.0fms). Usando fallback: chat",
            elapsed, ROUTER_TIMEOUT * 1000,
        )
        return _fallback_result(elapsed, "timeout")
    except requests.RequestException as e:
        elapsed = (time.monotonic() - start) * 1000
        logger.error("Router request failed: %s. Usando fallback: chat", e)
        return _fallback_result(elapsed, f"request_error: {e}")
    
    elapsed = (time.monotonic() - start) * 1000
    
    # Parsear la respuesta de Ollama
    return _parse_ollama_response(data, elapsed)


def _parse_ollama_response(data: dict, elapsed_ms: float) -> dict:
    """Extrae la clasificación de la respuesta de Ollama.
    
    Ollama Native Function Calling devuelve:
    {
        "message": {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {
                    "function": {
                        "name": "route_to_simple_chat",
                        "arguments": {"reason": "..."}
                    }
                }
            ]
        }
    }
    """
    message = data.get("message", {})
    tool_calls = message.get("tool_calls", [])
    
    if not tool_calls:
        # Sin tool_calls: interpretar como chat simple
        logger.info("Sin tool_calls en respuesta. Fallback: chat")
        return {
            "mode": "chat",
            "reason": "sin tool_calls en respuesta del router",
            "estimated_steps": None,
            "latency_ms": elapsed_ms,
            "model": data.get("model", ROUTER_MODEL),
            "fallback": True,
        }
    
    # Tomar el primer tool_call
    tool_call = tool_calls[0]
    func = tool_call.get("function", {})
    func_name = func.get("name", "")
    func_args = func.get("arguments", {})
    
    # Si arguments viene como string (JSON), parsearlo
    if isinstance(func_args, str):
        try:
            func_args = json.loads(func_args)
        except json.JSONDecodeError:
            func_args = {}
    
    if func_name == "route_to_simple_chat":
        return {
            "mode": "chat",
            "reason": func_args.get("reason", "clasificado como chat simple"),
            "estimated_steps": None,
            "latency_ms": elapsed_ms,
            "model": data.get("model", ROUTER_MODEL),
            "fallback": False,
        }
    elif func_name == "route_to_complex_agent":
        return {
            "mode": "agent",
            "reason": func_args.get("reason", "clasificado como tarea compleja"),
            "estimated_steps": func_args.get("estimated_steps"),
            "latency_ms": elapsed_ms,
            "model": data.get("model", ROUTER_MODEL),
            "fallback": False,
        }
    else:
        # Tool call desconocido: fallback a chat
        logger.warning("Tool call desconocido: %s. Fallback: chat", func_name)
        return {
            "mode": "chat",
            "reason": f"tool_call desconocido: {func_name}",
            "estimated_steps": None,
            "latency_ms": elapsed_ms,
            "model": data.get("model", ROUTER_MODEL),
            "fallback": True,
        }


def _fallback_result(elapsed_ms: float, reason: str) -> dict:
    """Resultado de fail-safe: asume chat simple."""
    return {
        "mode": "chat",
        "reason": f"fail-safe: {reason}",
        "estimated_steps": None,
        "latency_ms": elapsed_ms,
        "model": ROUTER_MODEL,
        "fallback": True,
    }


# ---------------------------------------------------------------------------
# Reparación de JSON truncado (para el bridge)
# ---------------------------------------------------------------------------

def repair_json(broken_json: str, timeout: float = 3.0) -> Optional[dict]:
    """Intenta reparar un JSON truncado usando qwen2.5:1.5b.
    
    Args:
        broken_json: El JSON roto o incompleto.
        timeout: Timeout en segundos.
    
    Returns:
        JSON reparado como dict, o None si falla.
    """
    from governance_prompt import get_repair_prompt
    
    prompt = get_repair_prompt(broken_json)
    
    payload = {
        "model": ROUTER_MODEL,
        "messages": [
            {"role": "user", "content": prompt},
        ],
        "stream": False,
        "options": {
            "temperature": 0.0,
            "num_predict": 1024,
        },
    }
    
    try:
        response = requests.post(
            OLLAMA_CHAT_ENDPOINT,
            json=payload,
            timeout=timeout,
        )
        response.raise_for_status()
        data = response.json()
        content = data.get("message", {}).get("content", "").strip()
        
        # Limpiar posibles wrappers markdown
        if content.startswith("```"):
            lines = content.split("\n")
            # Quitar primera y última línea si son fences
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            content = "\n".join(lines).strip()
        
        return json.loads(content)
    except Exception as e:
        logger.error("JSON repair failed: %s", e)
        return None


# ---------------------------------------------------------------------------
# Health check del router
# ---------------------------------------------------------------------------

def router_health() -> dict:
    """Verifica si Ollama y el modelo del router están disponibles."""
    try:
        # Check Ollama is up
        resp = requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=2.0)
        resp.raise_for_status()
        models = [m.get("name", "") for m in resp.json().get("models", [])]
        model_available = any(ROUTER_MODEL in m for m in models)
        return {
            "ollama_up": True,
            "model": ROUTER_MODEL,
            "model_available": model_available,
            "installed_models": models,
            "endpoint": OLLAMA_BASE_URL,
        }
    except Exception as e:
        return {
            "ollama_up": False,
            "model": ROUTER_MODEL,
            "model_available": False,
            "installed_models": [],
            "endpoint": OLLAMA_BASE_URL,
            "error": str(e),
        }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Uso: python router.py \"mensaje del usuario\"")
        print("     python router.py --health")
        sys.exit(1)
    
    if sys.argv[1] == "--health":
        import pprint
        pprint.pprint(router_health())
        sys.exit(0)
    
    prompt = " ".join(sys.argv[1:])
    result = classify_intent(prompt)
    
    print(f"\n{'='*60}")
    print(f"Prompt: {prompt}")
    print(f"Modo:   {result['mode'].upper()}")
    print(f"Razón:  {result['reason']}")
    print(f"Modelo: {result['model']}")
    print(f"Latencia: {result['latency_ms']:.0f}ms")
    print(f"Fallback: {result['fallback']}")
    if result.get("estimated_steps"):
        print(f"Pasos estimados: {result['estimated_steps']}")
    print(f"{'='*60}")
