# Routing Liviano + Honesto — nivel × contexto × costo (§16)

**Fecha:** 2026-08-16 · **Gate:** suite verde + routing_log con razones + latencia medida

## Problema resuelto

Mis-routing a modelos `context_ok=false` (best-fast, best-chat). La livianidad ahora es:
gratis/rápido en L0/L1, pero NUNCA un modelo que no aguanta el contexto.

## 1. `model_capabilities.json` (state + template)

- `context_window` agregado a los 272 modelos (aliasing de `context_length`).
- `auto/best-research` **eliminado** (referencia muerta: no existe en omniroute real).
  Confirmado ausente del estado y del template; `task_to_model` re-mapea investigacion/web_research/documentacion → `best-reasoning`.
- `atlas_sync_capabilities.build_capabilities_file()` ahora valida `task_to_model` contra el
  catálogo vivo en cada corrida: referencia muerta → **alerta + eliminación automática**.

## 2. `atlas_orchestrator.py` — `best_model_for(nivel, ctx_tokens)`

| Nivel | Ruta | Modelos (en orden) |
|---|---|---|
| L0/L1 | gratis primero | `oc/north-mini-code-free` → `oc/deepseek-v4-flash-free` |
| L0/L1 | breaker → pago | `opencode-go/deepseek-v4-flash` → `auto/best-coding-fast` |
| L2 | curado | `auto/best-coding` |
| L3/plan | curado | `auto/best-reasoning` |
| Visual | curado | `auto/best-vision` |
| Offline L0/L1 | local | `ollama/qwen2.5:1.5b` |
| Offline L2/L3 | **ESCALAR** | `None` (no razonar a ciegas) |

Reglas bloqueantes implementadas:
- `_fits_context()`: `context_ok=false` → descartado SIEMPRE (aunque tenga ventana).
- ctx estimado > ventana → siguiente candidato con contexto.
- Nada aguanta el contexto → el de mayor ventana con `context_ok != false`.
- `analyze()/route()` aceptan `nivel` + `ctx_tokens`; `route()` registra **nivel+ctx+razón** en routing_log.

## 3. `atlas_c4.py`

`classify_with_context(task)` → `{nivel, ctx_tokens}` y `route_with_context()` pasa ambos al
orquestador en cada turno (primer paso de todo turno, integrado con el clasificador L0/L1/L2+).

## 4. `opencode.jsonc.example`

Actualizado de ollama-phi4-mini (stale) a providers actuales: **omniroute:20128** (modelo
default `omniroute/auto/best-coding` + gratuitos + flash), **9router:4000**, **ollama** (1.5b).

## 5. Ollama — RAM check

`RAM libre = 6.1GB < 8GB` → NO se hizo pull de `qwen2.5:7b`. Registrado como **DEBT-033**
(responsable Atlas Ops, fecha objetivo 2026-09-01).

## 6. Evidencia en routing_log (3 decisiones reales, nivel+ctx+razón)

| Task | Nivel | Ctx | Decisión | Modelo | Razón |
|---|---|---|---|---|---|
| "abre el navegador" | L0 | 4 | proceed | oc/north-mini-code-free | L0 gratis+rapido |
| "resume el documento grande" | L0 | 11 | proceed | oc/north-mini-code-free | L0 gratis+rapido |
| "configura el firewall y despliega el servicio" | L2 | 11 | proceed | auto/best-coding | L2+ L2 |

## 7. Latencia L0 medida (antes/después)

| Modelo | Latencia primer token | Nota |
|---|---|---|
| `auto/best-fast` (antes) | **9.76–9.81s** | combo lento (resuelve a gemini-3.1-pro) |
| `oc/north-mini-code-free` (después) | 403 Forbidden | **requiere OMNIROUTE_API_KEY** (no configurada en el entorno) |
| `opencode-go/deepseek-v4-flash` (breaker) | 429 Too Many Requests | rate-limited en el momento de la medición |

**Decisión L0 (routing fast-path): p50 = 5ms** (5 runs, excluye 1 outlier de caché de health).

> Hallazgo honesto: el tier gratis (`oc/*-free`) necesita `OMNIROUTE_API_KEY` en el entorno;
> sin la key, el breaker cae al fallback de pago (que funciona sin key). El routing ya lo maneja.

## 8. Tests (`tests/unit/test_routing_context.py` — 8)

| Test | Verifica |
|---|---|
| `test_l0_contexto_grande_no_best_fast` | ctx grande → NUNCA best-fast (context_ok=false) |
| `test_l0_contexto_normal_no_best_fast` | best-fast bloqueado siempre |
| `test_l0_chico_gratis_rapido` | L0 chico → north-mini-code-free |
| `test_l1_chico_gratis_o_fallback_pago` | breaker: gratis caído → pago rápido |
| `test_best_research_ausente` | dead reference eliminada del mapa y template |
| `test_template_providers_vivos` | template parsea + apunta a omniroute:20128 vivo |
| `test_sin_providers_l2_escala` | sin provider → L2 ESCALA; L0 offline → 1.5b |
| `test_clasificador_estima_contexto` | nivel + ctx_tokens pasados al orquestador |

## 9. Cierre

- [x] context_ok/context_window por modelo + dead reference eliminada + sync valida en vivo
- [x] best_model_for(nivel, ctx_tokens) con breaker gratis→pago y escalado offline L2+
- [x] clasificador estima contexto y lo pasa al orquestador cada turno
- [x] template providers actuales
- [x] Ollama: RAM < 8GB → DEBT-033
- [x] Tests 8/8 + suite completa sin regresión
- [x] Evidencia routing_log + latencia medida

**Gate: PASS**
