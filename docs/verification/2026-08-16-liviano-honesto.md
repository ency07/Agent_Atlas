# Atlas Liviano + Honesto — Verificación §16

**Fecha:** 2026-08-16 · **Gate:** suite verde + evidencia + panel latencia por nivel

## Objetivo

Recuperar fluidez y velocidad en tareas simples SIN recuperar el vicio de mentir o dejar a medias.
La livianidad se aplica al **proceso** (modelo, inyección, contratos, críticos); la honestidad y la evidencia **no se negocian**.

## Clasificación por nivel (`atlas_c4.py:classify_level`)

| Nivel | Definición | Modelo | Inyección | Contrato/Crítico |
|---|---|---|---|---|
| **L0** | 1 acción sin cambios de config/archivos | `auto/best-fast` | ≤300 tokens | Sin contrato, sin crítico |
| **L1** | 1-2 tools, cambio menor reversible | `auto/best-fast` | ≤300 tokens | Igual L0 + verificación |
| **L2+** | config, archivos, programas, dinero, multi-paso | `auto/best-coding` | ≤700 tokens | Contrato C2 + verificador + crítico |

- `max_intentos` = 3 para L0/L1, 5 para L2+ (fue 5 fijo).
- `timeout_min` = 5 para L0/L1, 20 para L2+ (fue 20 fijo).

## Fast-path (`atlas_controller.py:es_liviano / ejecutar_liviano`)

- L0/L1 **saltan** el bucle de contrato formal: `ejecutar_liviano()` corre los criterios directo.
- Verificación barata L0: check de 1 línea (comando/ventana/endpoint) — no bloquea el turno.
- L2+ conserva el flujo completo C2 (contrato + `Verifier` + crítico).

## Honestidad en DOS capas

### Capa código — `atlas_verifier.py:verificar_cierre_sin_evidencia()`
- Detecta cierre de criterio sin evidencia (estado no-OK y sin evidencia) para L0/L1.
- Si detecta → devuelve `exito_falso=True` y **registra en `memory_data/state/friction_log.jsonl`** (type `exito_falso`).
- L2+ no se afecta (contrato formal ya exige evidencia).

### Capa panel — `atlas_web/dashboard.html`
- Nuevo endpoint tipo válido `exito_falso` en `atlas_web_server.py`.
- Banner rojo "ALERTA: Éxito falso detectado" en el dashboard, auto-refresh 30s.

## Tests (`tests/unit/test_liviano_honesto.py` — 11)

| Test | Qué verifica |
|---|---|
| `test_l0_classification` | abrir/navegar/status → L0 |
| `test_l1_classification` | crear/agregar → L1 |
| `test_l2_classification` | firewall+deploy/migrar/refactor → L2 |
| `test_model_for_level` | L0→best-fast, L2→best-coding |
| `test_injection_budget` | L0≤300, L2≤700 |
| `test_contract_includes_level` | contrato lleva `nivel` + `es_liviano()` |
| `test_ejecutar_liviano_check_barato` | check de 1 línea devuelve OK sin contrato |
| `test_cierre_sin_evidencia_bloqueado` | cierre sin evidencia → exito_falso + registrado en friction_log |
| `test_cierre_con_evidencia_pasa` | con evidencia → pasa |
| `test_honestidad_lenguaje` | "no sé/no pude" pasan; "debería/probablemente/parece" fallan |
| `test_latencia_l0_umbral` | L0 ejecuta < 5s |

## Resultados

```
tests/unit/test_liviano_honesto.py ... 11 passed in 0.32s
tests/unit/test_c4.py + test_c2_controller.py + test_p_friction.py ... 24 passed
suite completa: 170 passed
```

## Evidencia de latencia L0

El test `test_latencia_l0_umbral` mide el fast-path completo (clasificación + verificación barata)
y exige < 5s. Se cumple (0.32s en suite completa).

## Cierre

- [x] Clasificador L0/L1/L2+ como primer paso
- [x] Fast-path L0/L1 sin contrato/crítico
- [x] Verificación barata L0 (1 línea)
- [x] Honestidad código (exito_falso → excepción) + panel (banner rojo)
- [x] Tests verdes + latencia bajo umbral
- [x] Reporte §16

**Gate: PASS** — livianidad implementada y MEDIDA. Prohibido declarar livianidad sin evidencia.
