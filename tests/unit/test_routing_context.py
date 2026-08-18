# ============================================================
# tests/unit/test_routing_context.py — Tests routing liviano+honesto
# nivel × contexto × costo
# ------------------------------------------------------------
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import atlas_orchestrator as ao
from atlas_c4 import classify_level, classify_with_context, estimate_ctx_tokens


def _pool():
    """Pool falso determinista (sin depender de providers vivos)."""
    return {
        "omniroute/auto/best-fast": {"coding": 0.5, "speed": 1.0, "context_ok": False, "context_window": 1048576},
        "omniroute/auto/best-coding": {"coding": 0.95, "speed": 0.7, "context_ok": True, "context_window": 1048576},
        "omniroute/auto/best-reasoning": {"coding": 0.8, "reasoning": 0.98, "speed": 0.5, "context_ok": True, "context_window": 1048576},
        "omniroute/auto/best-vision": {"coding": 0.6, "vision": True, "speed": 0.7, "context_ok": True, "context_window": 1048576},
        "omniroute/oc/north-mini-code-free": {"coding": 0.95, "speed": 0.9, "context_ok": True, "context_window": 200000},
        "omniroute/oc/deepseek-v4-flash-free": {"coding": 0.5, "speed": 0.9, "context_ok": True, "context_window": 1000000},
        "omniroute/opencode-go/deepseek-v4-flash": {"coding": 0.95, "speed": 0.9, "context_ok": True, "context_window": 1000000},
        "ollama/qwen2.5:1.5b": {"coding": 0.4, "speed": 0.9, "context_ok": True, "context_window": 32768},
    }


# --- 1. L0 + contexto grande -> NO best-fast (context_ok=false bloqueado) ---
def test_l0_contexto_grande_no_best_fast():
    ctx_grande = 1_500_000  # mayor que cualquier ventana real
    pick = ao.best_model_for(None, _pool(), nivel="L0", ctx_tokens=ctx_grande)
    # si nadie aguanta, cae al de mayor ventana pero NUNCA best-fast (context_ok=false)
    assert pick is not None
    assert pick["model"] != "omniroute/auto/best-fast", "best-fast context_ok=false no debe elegirse"
    assert pick["capability"]["context_ok"] is not False


def test_l0_contexto_normal_no_best_fast():
    # contexto normal pero best-fast sigue bloqueado por context_ok=false
    pick = ao.best_model_for(None, _pool(), nivel="L0", ctx_tokens=1000)
    assert pick["model"] != "omniroute/auto/best-fast"


# --- 2. L0 chico -> modelo gratis rapido ---
def test_l0_chico_gratis_rapido():
    pick = ao.best_model_for(None, _pool(), nivel="L0", ctx_tokens=500)
    assert pick["model"] == "omniroute/oc/north-mini-code-free", pick
    assert "gratis" in pick["reason"]


def test_l1_chico_gratis_o_fallback_pago():
    pool = dict(_pool())
    pool.pop("omniroute/oc/north-mini-code-free")
    pool.pop("omniroute/oc/deepseek-v4-flash-free")
    pick = ao.best_model_for(None, pool, nivel="L1", ctx_tokens=500)
    assert "breaker" in pick["reason"] or "fallback" in pick["reason"]


# --- 3. best-research ausente del mapa ---
def test_best_research_ausente():
    caps = ao.load_capabilities().get("models", {})
    assert "omniroute/auto/best-research" not in caps, "referencia muerta debe estar eliminada"
    # template tambien limpio
    tmpl = json.loads(Path("E:/Agente_IA/templates/model_capabilities.json.example").read_text(encoding="utf-8-sig"))
    assert "omniroute/auto/best-research" not in tmpl.get("models", {})
    t2m = tmpl.get("task_to_model", {})
    for v in t2m.values():
        assert "best-research" not in v, f"task_to_model referencia muerta: {v}"


# --- 4. Template parsea y apunta a providers vivos ---
def test_template_providers_vivos():
    tmpl = Path("E:/Agente_IA/templates/opencode.jsonc.example").read_text(encoding="utf-8-sig")
    # jsonc: quitar comentarios de linea
    lines = [l for l in tmpl.splitlines() if not l.strip().startswith("//")]
    body = "\n".join(lines)
    d = json.loads(body)
    assert "omniroute" in d["provider"], "omniroute debe estar en template"
    assert d["provider"]["omniroute"]["options"]["baseURL"].endswith(":20128/v1")
    assert "auto/best-coding" in d["model"], "model por defecto debe ser omniroute/auto/best-coding"
    # modelo por defecto debe existir en el provider declarado
    model_ref = d["model"].split("/", 1)
    assert model_ref[0] == "omniroute"
    assert model_ref[1] in d["provider"]["omniroute"]["models"]


# --- 5. Sin providers -> L2+ escala (no responde a ciegas) ---
def test_sin_providers_l2_escala(monkeypatch):
    monkeypatch.setattr(ao, "active_providers", lambda: {
        "omniroute": {"alive": False, "installed_models": [], "in_cooldown": False, "cooldown_left_s": 0, "port": 20128, "api": "http://localhost:20128/v1"},
        "9router": {"alive": False, "installed_models": [], "in_cooldown": False, "cooldown_left_s": 0, "port": 4000, "api": "http://localhost:4000/v1"},
        "ollama": {"alive": True, "installed_models": ["qwen2.5:1.5b"], "in_cooldown": False, "cooldown_left_s": 0, "port": 11434, "api": "http://localhost:11434/v1"},
    })
    monkeypatch.setattr(ao, "active_models", lambda: {
        "ollama/qwen2.5:1.5b": {"coding": 0.4, "speed": 0.9, "context_ok": True, "context_window": 32768},
    })
    res = ao.analyze("configura el firewall y despliega el servicio", nivel="L2")
    assert res["decision"]["action"] == "escalate", res["decision"]
    # L0 offline SI responde con el 1.5b
    res0 = ao.analyze("abre el navegador", nivel="L0")
    assert res0["decision"]["action"] == "proceed"
    assert res0["decision"]["suggested_model"] == "ollama/qwen2.5:1.5b"


# --- 6. clasificador de nivel estima contexto y lo pasa ---
def test_clasificador_estima_contexto():
    ctx = classify_with_context("abre el navegador")
    assert ctx["nivel"] == "L0"
    assert ctx["ctx_tokens"] > 0
    assert ctx["ctx_tokens"] == estimate_ctx_tokens("abre el navegador")


if __name__ == "__main__":
    test_l0_contexto_grande_no_best_fast()
    test_l0_contexto_normal_no_best_fast()
    test_l0_chico_gratis_rapido()
    test_l1_chico_gratis_o_fallback_pago()
    test_best_research_ausente()
    test_template_providers_vivos()
    test_sin_providers_l2_escala()
    test_clasificador_estima_contexto()
    print("OK tests/unit/test_routing_context.py")
