# 📋 DEBT.md — Registro Único de Deuda Técnica

**Fuente única de verdad para toda deuda. Una entrada = un ID. Colisión de IDs = fallo bloqueante.**

---

## DEBT-001 — Falta autenticación en endpoints HTTP locales de servidores MCP
- **Origen:** Auditoría Intrínseca / Phase 0
- **Descripción:** Endpoints :4096 (chat), :4100 (web), :4102 (health), :4103 (orchestrator) expuestos en localhost sin auth
- **Impacto:** Cualquier proceso local puede invocar tools MCP
- **Mitigación actual:** Solo localhost (no expuesto a red)
- **Responsable:** Atlas Core
- **Fecha objetivo:** 2026-08-30
- **Estado:** ABIERTO

---

## DEBT-002 — Rotación de logs sin límite de tamaño en `logs/`
- **Origen:** Auditoría Intrínseca / Phase 0
- **Descripción:** Logs crecen indefinidamente; `atlas_logrotate.py` existe pero no configurado como tarea
- **Impacto:** Disco lleno silencioso
- **Mitigación:** Registrar tarea `AtlasLogRotate` (diario 04:00, retención 7 días)
- **Responsable:** Atlas Ops
- **Fecha objetivo:** 2026-08-25
- **Estado:** MITIGADO (tarea programada en setup.ps1)

---

## DEBT-003 — Dependencia estricta de WebView2 para chat flotante
- **Origen:** Auditoría Intrínseca / Phase 0
- **Descripción:** `atlas_chat.py` falla si WebView2 no está instalado
- **Impacto:** Chat no arranca en máquinas limpias
- **Mitigación:** Fallback a navegador por defecto implementado en `_on_loaded`
- **Responsable:** Atlas UI
- **Fecha objetivo:** 2026-08-20
- **Estado:** RESUELTO (fallback implementado)

---

## DEBT-004 — Ausencia de tests unitarios para `atlas_activity.py`
- **Origen:** Auditoría Intrínseca / Phase 0
- **Descripción:** Daemon crítico sin cobertura de tests
- **Impacto:** Regresiones en captura de ventana no detectadas
- **Responsable:** QA
- **Fecha objetivo:** 2026-09-05
- **Estado:** ABIERTO

---

## DEBT-005 — `model_capabilities.json` desactualizado vs proveedores reales
- **Origen:** Hallazgo I-01 (declaración 100% falsa)
- **Descripción:** Mapa de capacidades no sincronizado automáticamente; `atlas_sync_capabilities.py` existe pero no verificado
- **Impacto:** Orquestador usa heurísticas en lugar de datos reales
- **Responsable:** Atlas Core
- **Fecha objetivo:** 2026-08-28
- **Estado:** ABIERTO

---

## DEBT-006 — Backup age vs zip: confusión en restauración
- **Origen:** Hallazgo I-03 (backups age vs zip sin aclarar)
- **Descripción:** Dos sistemas de backup (`atlas_backup_encrypted.py` + `mcp_memory_server.py backup`) sin documentación de cuándo usar cada uno
- **Impacto:** Operador no sabe qué restaurar en incidente
- **Responsable:** Atlas Ops
- **Fecha objetivo:** 2026-08-22
- **Estado:** ABIERTO

---

## DEBT-007 — `atlas_web_server.py` sin ficha C2 en intrínseco
- **Origen:** Hallazgo I-04 (ficha de atlas_web_server con endpoints C2 faltante)
- **Descripción:** Endpoints `/api/tareas`, `/api/pendientes`, `/api/trust`, `/api/informes`, `/api/evals` no auditados
- **Impacto:** C2 no puede verificar contratos desde dashboard
- **Responsable:** Atlas Core
- **Fecha objetivo:** 2026-08-18
- **Estado:** ABIERTO

---

## DEBT-008 — IDs de deuda dispersos (ATLAS_INTRINSECO vs DEBT.md)
- **Origen:** Hallazgo I-02 (colisión de IDs)
- **Descripción:** DEBT-001..010 en intrínseco vs hallazgos I-01..I-05 sin unificación
- **Impacto:** Doble registro, búsqueda falla
- **Responsable:** Atlas Core
- **Fecha objetivo:** 2026-08-15 (HOY - esta unificación)
- **Estado:** CERRADO (unificados en este archivo)

---

## DEBT-009 — `atlas_supervisor.py` no reinicia `atlas_controller` (demand=True)
- **Origen:** Código `atlas_supervisor.py` línea 120
- **Descripción:** Controller marcado como `demand=True` → supervisor no lo auto-reinicia
- **Impacto:** Si controller muere en medio de contrato C2, no se recupera solo
- **Responsable:** Atlas Core
- **Fecha objetivo:** 2026-08-30
- **Estado:** ABIERTO

---

## DEBT-010 — Falta rate limiting en endpoints HTTP internos
- **Origen:** GOVERNANCE.md §48
- **Descripción:** Endpoints :4100, :4102, :4103 sin rate limiting
- **Impacto:** DoS local posible
- **Responsable:** Atlas Core
- **Fecha objetivo:** 2026-09-10
- **Estado:** ABIERTO

---

## DEBT-011 — `atlas_metrics.py` y `atlas_benchmark.py` no integrados en auto-modelo C3v2
- **Origen:** SPEC_C3v2 §04 "Integra, NO reconstruyas"
- **Descripción:** Métricas de uso/costo y benchmark existen pero no alimentan `model_capabilities.json` ni `self_model.json`
- **Impacto:** Auto-modelo decide sin datos de costo/latencia reales
- **Responsable:** Atlas Core
- **Fecha objetivo:** 2026-09-01
- **Estado:** ABIERTO

---

## DEBT-012 — `friction_log` no existe (requerido por SPEC_P P-2)
- **Origen:** SPEC_P REQ P-2
- **Descripción:** Archivo `state/friction_log.jsonl` y endpoint `/api/friction` no implementados
- **Impacto:** Sin baseline de fricciones → no se puede medir mejora C3v2/C4
- **Responsable:** Atlas P
- **Fecha objetivo:** 2026-08-20
- **Estado:** ABIERTO

---

## DEBT-013 — Streaming/progreso/ETA en chat no implementado (SPEC_P P-1)
- **Origen:** SPEC_P REQ P-1
- **Descripción:** Turnos >10s sin feedback visible; `api.js` wrapper no emite progreso
- **Impacto:** Usuario percibe cuelgue
- **Responsable:** Atlas UI
- **Fecha objetivo:** 2026-08-22
- **Estado:** ABIERTO

---

## DEBT-014 — Panel de métricas de fricción semanal en dashboard :4100 (SPEC_P P-3)
- **Origen:** SPEC_P REQ P-3
- **Descripción:** Dashboard no muestra tendencia de fricciones
- **Impacto:** No hay juez para C3v2/C4
- **Responsable:** Atlas P
- **Fecha objetivo:** 2026-08-25
- **Estado:** ABIERTO

---

## DEBT-015 — MCPs persistentes sin cold start (SPEC_P P-4)
- **Origen:** SPEC_P REQ P-4
- **Descripción:** Primer tool de sesión >1s por cold start de MCP servers
- **Impacto:** Latencia percibida
- **Responsable:** Atlas Core
- **Fecha objetivo:** 2026-08-28
- **Estado:** ABIERTO

---

## DEBT-016 — Baseline de fricciones no publicada (SPEC_P P-5)
- **Origen:** SPEC_P REQ P-5
- **Descripción:** Sin medición previa, no se puede demostrar −50% tras C3v2+C4
- **Responsable:** Atlas P
- **Fecha objetivo:** 2026-08-20
- **Estado:** ABIERTO

---

## DEBT-017 — Snapshot TTL + invalidación + on-demand (SPEC_C3v2 C3-1)
- **Origen:** SPEC_C3v2 REQ C3-1
- **Descripción:** `atlas_env.py` no existe; snapshot de entorno no invalidado por eventos
- **Impacto:** Agente cita scans obsoletos
- **Responsable:** Atlas C3
- **Fecha objetivo:** 2026-09-05
- **Estado:** ABIERTO

---

## DEBT-018 — Inyección por relevancia por código (SPEC_C3v2 C3-2)
- **Origen:** SPEC_C3v2 REQ C3-2
- **Descripción:** Tarea menciona Corel → slice Corel sin slice trading; log de inyección requerido
- **Responsable:** Atlas C3
- **Fecha objetivo:** 2026-09-08
- **Estado:** ABIERTO

---

## DEBT-019 — Auto-modelo de capacidades real (SPEC_C3v2 C3-3)
- **Origen:** SPEC_C3v2 REQ C3-3
- **Descripción:** Consulta "¿puedes usar X deshabilitado?" → responde NO según `enabled` en opencode.jsonc
- **Responsable:** Atlas C3
- **Fecha objetivo:** 2026-09-01
- **Estado:** ABIERTO

---

## DEBT-020 — Ontología personal en `preferences/ontologia.md` (SPEC_C3v2 C3-4)
- **Origen:** SPEC_C3v2 REQ C3-4
- **Descripción:** "mi navegador"=X, "la app de diseño"=Corel, "el panel"=:4100 resueltos sin preguntar
- **Responsable:** Atlas C3
- **Fecha objetivo:** 2026-08-25
- **Estado:** ABIERTO

---

## DEBT-021 — Memoria episódica (SPEC_C3v2 C3-5)
- **Origen:** SPEC_C3v2 REQ C3-5
- **Descripción:** Pedido similar a contrato pasado → lo cita (éxito/fallo/runbook)
- **Responsable:** Atlas C3
- **Fecha objetivo:** 2026-09-10
- **Estado:** ABIERTO

---

## DEBT-022 — Contexto vivo (SPEC_C3v2 C3-6)
- **Origen:** SPEC_C3v2 REQ C3-6
- **Descripción:** Turno inicia conociendo % activo y errores recientes
- **Responsable:** Atlas C3
- **Fecha objetivo:** 2026-09-05
- **Estado:** ABIERTO

---

## DEBT-023 — Redacción por proveedor (SPEC_C3v2 C3-7)
- **Origen:** SPEC_C3v2 REQ C3-7
- **Descripción:** Slice local completo; slice cloud sin rutas/puertos/inventario
- **Responsable:** Atlas C3
- **Fecha objetivo:** 2026-09-08
- **Estado:** ABIERTO

---

## DEBT-024 — Aprendizaje de fallos en vivo (SPEC_C3v2 C3-8)
- **Origen:** SPEC_C3v2 REQ C3-8
- **Descripción:** Tool falla → invalida snapshot-parcial + friction_log + no reintenta igual
- **Responsable:** Atlas C3
- **Fecha objetivo:** 2026-09-10
- **Estado:** ABIERTO

---

## DEBT-025 — self_model.json sembrado del intrínseco corregido (SPEC_C3v2 C3-9)
- **Origen:** SPEC_C3v2 REQ C3-9 / T-C3-0
- **Descripción:** 25 componentes con capacidades+fallos; T-C3-0 cerrado bajo contrato C2
- **Responsable:** Atlas C3
- **Fecha objetivo:** 2026-08-18 (después de T-C3-0)
- **Estado:** ABIERTO

---

## DEBT-026 — Gestión de contexto sesiones largas (SPEC_C3v2 C3-10)
- **Origen:** SPEC_C3v2 REQ C3-10
- **Descripción:** Sesión 2h sin degradación medible (resumen deslizante)
- **Responsable:** Atlas C3
- **Fecha objetivo:** 2026-09-15
- **Estado:** ABIERTO

---

## DEBT-027 — Descomposición pragmática a resultado (SPEC_C4 C4-1)
- **Origen:** SPEC_C4 REQ C4-1
- **Descripción:** "configura extensión" → criterios de resultado, no pasos de clic
- **Responsable:** Atlas C4
- **Fecha objetivo:** 2026-09-15
- **Estado:** CERRADO (implementado en atlas_c4.py + test)

---

## DEBT-028 — Restricciones implícitas en contrato (SPEC_C4 C4-2)
- **Origen:** SPEC_C4 REQ C4-2
- **Descripción:** Contrato incluye "no romper lo que funciona" sin que se diga
- **Responsable:** Atlas C4
- **Fecha objetivo:** 2026-09-15
- **Estado:** CERRADO (implementado en atlas_c4.py + test)

---

## DEBT-029 — Contrato C2 auto-generado (SPEC_C4 C4-3)
- **Origen:** SPEC_C4 REQ C4-3
- **Descripción:** Pedido libre → contrato con criterios ejecutables sin edición manual
- **Responsable:** Atlas C4
- **Fecha objetivo:** 2026-09-15
- **Estado:** CERRADO (implementado en atlas_c4.py + test)

---

## DEBT-030 — Clarificación solo crítica (SPEC_C4 C4-4)
- **Origen:** SPEC_C4 REQ C4-4
- **Descripción:** Ambiguo → máx 1 pregunta + supuestos declarados
- **Responsable:** Atlas C4
- **Fecha objetivo:** 2026-09-15
- **Estado:** CERRADO (implementado en atlas_c4.py + test)

---

## DEBT-031 — Dominio correcto (SPEC_C4 C4-5)
- **Origen:** SPEC_C4 REQ C4-5
- **Descripción:** Pedidos de trading/POD/contenido usan jerga y métricas del usuario
- **Responsable:** Atlas C4
- **Fecha objetivo:** 2026-09-15
- **Estado:** CERRADO (implementado en atlas_c4.py + test)

---

## DEBT-032 — Integración de atlas_metrics / atlas_benchmark como fuentes del auto‑modelo (C3‑3)
- **Origen:** E‑05 (requerimiento de evidencia)
- **Descripción:** `atlas_capabilities_real.py` debe consumir métricas de latencia/éxito de `atlas_metrics` y resultados de `atlas_benchmark` para enriquecer el mapa de capacidades reales.
- **Responsable:** Atlas Core
- **Fecha objetivo:** 2026-09-01
- **Estado:** ABIERTO

---

## ÍNDICE POR CATEGORÍA

| Categoría | IDs |
|-----------|-----|
| Infra/Endpoints | 001, 010 |
| Logs/Observabilidad | 002, 012, 013, 014 |
| Backup/Restore | 006 |
| Testing/QA | 004 |
| Capabilities/Sync | 005, 011, 017, 019, 032 |
| Auto-Modelo C3v2 | 017–026 |
| Intención C4 | 027–031 |
| UI/Chat | 003, 013 |
| Supervisor/Recovery | 009 |
| Métricas/Benchmark | 011 |
| Friction/Percepción P | 012–016 |

---

## REGLA DE COLISIÓN
> **Antes de añadir una nueva deuda:** buscar en este archivo si el ID ya existe. Si existe, actualizar la entrada existente. **Nunca crear ID duplicado.**

---

## DEBT-033 — Ollama: falta qwen2.5:7b como fallback offline L2/L3
- **Origen:** Routing Liviano + Honesto (§16, 2026-08-16)
- **Descripción:** El fallback offline de L2/L3 necesita `qwen2.5:7b` en Ollama; el `1.5b` no razona L2+. RAM libre era 6.1GB (umbral 8GB) → se difiere el pull.
- **Impacto:** Sin red, L2/L3 no tienen fallback (escalan en vez de razonar a ciegas, comportamiento correcto pero sin recuperación offline).
- **Mitigación:** `ollama pull qwen2.5:7b` cuando RAM libre ≥ 8GB y registrarlo como `offline_fallback_l2`.
- **Responsable:** Atlas Ops
- **Fecha objetivo:** 2026-09-01
- **Estado:** ABIERTO