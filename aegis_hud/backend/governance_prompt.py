"""
governance_prompt.py — Inyección de reglas de gobernanza Atlas.

El agente en Modo B (Autónomo) NUNCA ejecuta código nativo.
Todas las acciones del SO pasan por los MCPs de Atlas.
Este módulo genera el system prompt obligatorio para cada modo.
"""

# ---------------------------------------------------------------------------
# System prompt del Modo B (Agente Autónomo)
# Inyectado SIEMPRE que se activa el bucle de agente.
# ---------------------------------------------------------------------------
AGENT_SYSTEM_PROMPT = """You are Atlas, an autonomous agent operating in a strict security environment.

CRITICAL RULES — NEVER VIOLATE:
1. NEVER execute raw shell commands (bash, python, subprocess, os.system, exec, eval).
2. ALWAYS use the provided atlas_tools for any system interaction.
3. NEVER write files directly. Use atlas_mcp tools.
4. NEVER kill processes directly. Use atlas_guardian.
5. NEVER access the registry. Use atlas_guardian.
6. NEVER install packages without guardian approval.
7. If a tool fails, report it to the user. Do NOT retry with raw commands.
8. All destructive operations require explicit user confirmation.

AVAILABLE TOOLS (via MCP):
- atlas_guardian: Security validation for all operations.
- atlas_orchestrator: Model routing and provider management.
- atlas_health: System health monitoring.
- atlas_foco: Focus metrics and discipline control.
- atlas_memory: Persistent memory (vault, notes, sessions).
- atlas_windows: Windows automation (UIA, screenshots, input).
- atlas_corel: CorelDRAW automation.
- atlas_playwright: Browser automation.

You are operating under GOVERNANCE protocol. Every action is auditable.
"""


# ---------------------------------------------------------------------------
# System prompt del Modo A (Chat Directo)
# Más liviano, sin herramientas, solo conversación.
# ---------------------------------------------------------------------------
CHAT_SYSTEM_PROMPT = """You are Atlas, a direct conversational assistant.
Respond clearly and concisely. No tool calls. No system actions.
If the user asks for something that requires system interaction,
tell them it needs to be escalated to autonomous mode (Modo B).
"""


# ---------------------------------------------------------------------------
# Prompt de reparación de JSON truncado
# Se usa cuando el LLM devuelve JSON incompleto.
# ---------------------------------------------------------------------------
REPAIR_JSON_PROMPT_TEMPLATE = """The following JSON response was truncated or broken.
Reconstruct it into valid JSON. Return ONLY the repaired JSON, nothing else.

Broken JSON:
{broken_json}

Requirements:
- Must be valid, parseable JSON
- Preserve the original structure and keys
- If a tool_call was incomplete, complete it reasonably
- Return ONLY the JSON object, no explanation
"""


# ---------------------------------------------------------------------------
# Tool definitions para Ollama Native Function Calling
# Estas son las herramientas virtuales que el router usa para clasificar.
# ---------------------------------------------------------------------------
ROUTE_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "route_to_simple_chat",
            "description": "Route to direct chat (Mode A). Use for greetings, simple questions, explanations, summaries, and any task that does NOT require system actions, file manipulation, or multi-step automation.",
            "parameters": {
                "type": "object",
                "properties": {
                    "reason": {
                        "type": "string",
                        "description": "Brief explanation of why this is a simple chat task"
                    }
                },
                "required": ["reason"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "route_to_complex_agent",
            "description": "Route to autonomous agent (Mode B). Use for tasks requiring system actions: file operations, process management, web browsing, design, coding with execution, multi-step automation, or any task that needs MCP tools.",
            "parameters": {
                "type": "object",
                "properties": {
                    "reason": {
                        "type": "string",
                        "description": "Brief explanation of why this needs autonomous agent mode"
                    },
                    "estimated_steps": {
                        "type": "integer",
                        "description": "Estimated number of tool calls needed (1-10)"
                    }
                },
                "required": ["reason"]
            }
        }
    }
]


def get_governance_prompt(mode: str = "agent") -> str:
    """Devuelve el system prompt de gobernanza para el modo dado.
    
    Args:
        mode: "agent" (Modo B) o "chat" (Modo A)
    
    Returns:
        System prompt apropiado.
    """
    if mode == "agent":
        return AGENT_SYSTEM_PROMPT
    return CHAT_SYSTEM_PROMPT


def get_repair_prompt(broken_json: str) -> str:
    """Genera el prompt para reparar JSON truncado.
    
    Args:
        broken_json: El JSON roto o incompleto del LLM.
    
    Returns:
        Prompt listo para enviar al modelo de respaldo.
    """
    return REPAIR_JSON_PROMPT_TEMPLATE.format(broken_json=broken_json)


def get_route_tools() -> list:
    """Devuelve las tool definitions para Ollama Native Function Calling."""
    return ROUTE_TOOLS
