# 📋 Gobernanza de Desarrollo (Protocolo de IA) — Atlas

Este documento define las reglas de compromiso obligatorias para cualquier
interacción con el código base o los entregables de Atlas. **Toda intervención
debe seguir este flujo y cerrar con evidencia verificable.**

---

## Punto de Control de Cierre (Hard Stop)

No cierres la tarea. Para darla por terminada debes entregar un **Reporte de Verificación de Cierre** completo, ejecutable y verificable.

Este punto de control es bloqueante. Si falta cualquiera de los elementos obligatorios, el estado de cierre debe ser:

```text
FAIL
```

o uno de los estados de bloqueo aplicables:

```text
BLOCKED_BY_ENVIRONMENT
BLOCKED_BY_AMBIGUITY
BLOCKED_BY_PERMISSION
BLOCKED_BY_MISSING_DEPENDENCY
```

Nunca puede cerrarse como completado si existe evidencia parcial, ausente o no reproducible.

---

### Contenido mínimo del Reporte de Verificación de Cierre

#### 1. ARCHIVOS

Lista de archivos o artefactos creados, modificados o eliminados.

Debe incluir:

- Ruta exacta.
- Acción: `created`, `modified`, `deleted`, `renamed`, `config`, `doc`, `test`, `migration`, `script`, etc.
- Componente, módulo o herramienta responsable.
- Motivo del cambio.

Formato:

```markdown
| Ruta exacta | Acción | Componente / herramienta | Motivo |
|---|---|---|---|
| src/auth/login.ts | modified | Módulo de autenticación | Validación de entrada y rate limit |
| tests/auth/login.spec.ts | created | Suite de pruebas | Cobertura de caso feliz y fallo |
| docs/traceability.md | modified | Trazabilidad | Actualización de REQ-014 |
```

Si el cambio no involucra archivos, declarar:

```text
N/A — Justificación: ...
```

---

#### 2. EVIDENCIA EJECUTADA

Entregar salidas reales, no explicaciones.

No se aceptan frases como:

- "Se ejecutó correctamente."
- "Todo quedó funcionando."
- "Las pruebas pasaron."
- "Parece correcto."

Se aceptan comandos, salidas, logs, reportes, artefactos o evidencias reproducibles.

Incluir únicamente los controles que apliquen al cambio:

- Build / compilación / parse.
- Lint / formato / validación estática.
- Instalación o verificación de dependencias.
- Tests unitarios.
- Tests de integración.
- Tests de regresión.
- Validación de secretos.
- Escaneo de vulnerabilidades.
- Validación de esquema / migración.
- Prueba de rollback.
- Arranque del servicio.
- Health check.
- Readiness check.
- Verificación de logs estructurados.
- Verificación de rate limiting.
- Prueba manual reproducible si no existe automatización.
- Verificación de rendimiento si aplica.
- Validación de UI / render / preview si aplica.
- Validación documental si el cambio es documental.

Formato:

```markdown
| Control | Comando / acción | Salida real | Resultado |
|---|---|---|---|
| Build | `npm run build` | `compiled successfully` | PASS |
| Lint | `npm run lint` | `0 errors, 0 warnings` | PASS |
| Tests | `npm test` | `18 passed, 0 failed, 0 skipped` | PASS |
| Secret scan | `gitleaks detect` | `no leaks found` | PASS |
| Health check | `curl localhost:3000/health/ready` | `{"status":"ok"}` | PASS |
```

Si una salida es demasiado extensa, se admite:

```text
Extracto relevante + ruta del artefacto completo
```

Ejemplo:

```markdown
Salida completa: artifacts/build/2026-06-17-build.log
Extracto:
BUILD SUCCESS in 42s
```

Si una salida contiene secretos, tokens, contraseñas o datos sensibles, deben redactarse antes de incluirse. Indicar:

```text
Salida redactada por seguridad.
```

---

#### 3. TESTS

Entregar el comando exacto de pruebas y el resultado real.

Formato mínimo:

```markdown
Comando:
`...`

Salida real:
```text
...
```

Resumen:
- Passed: X
- Failed: Y
- Skipped: Z
- Flaky: W
```

Reglas:

- Si existen tests automatizados, son obligatorios.
- Si el proyecto no tiene framework de pruebas, la primera tarea debe ser incorporar el estándar del stack.
- Si no se puede automatizar, debe entregarse una verificación manual reproducible.
- Un test skipped sin justificación formal se considera fallo de cierre.
- Un test intermitente se considera fallo hasta que se estabilice o se aísle con ADR/deuda registrada.

---

#### 4. GUARDIANES Y CLASIFICACIÓN DE RIESGO

Este punto reemplaza cualquier validación informal por una verificación de controles automáticos y riesgo.

Debe entregarse una tabla con:

- Cambio u operación.
- Nivel de riesgo.
- Si requiere confirmación humana.
- Guardián / control automático aplicado.
- Evidencia.

Formato:

```markdown
| Cambio / operación | Riesgo | Requiere confirmación | Guardián / control | Evidencia |
|---|---:|---|---|---|
| Cambio en validación de login | LOW | NO | Unit tests + lint + secret scan | PASS |
| Migración de esquema | HIGH | SÍ | Migration dry-run + rollback plan | PASS |
| Cambio en política de permisos | HIGH | SÍ | Authz tests + revisión manual | PASS |
```

Niveles de riesgo:

```text
LOW
MEDIUM
HIGH
```

Definición universal:

| Riesgo | Definición | Confirmación |
|---|---|---|
| LOW | Cambio reversible, acotado, sin impacto en seguridad, datos críticos, compatibilidad o producción. | No requiere confirmación adicional si pasa controles automáticos y evidencia verificable. |
| MEDIUM | Cambio que afecta comportamiento observable, configuración, contratos, rendimiento, datos no críticos o documentación operativa. | Requiere evidencia reforzada; puede requerir aprobación según proyecto. |
| HIGH | Cambio destructivo, irreversible, relacionado con secretos, autorización, datos sensibles, producción, migraciones críticas o superficie pública de seguridad. | Requiere confirmación humana explícita, ADR o aprobación formal. |

Prohibido clasificar como `LOW`:

- Borrado o mutación irreversible de datos.
- Cambios en autenticación o autorización.
- Cambios en secretos, tokens, claves o credenciales.
- Migraciones destructivas sin rollback probado.
- Cambios en producción sin plan de reversión.
- Cambios que rompen compatibilidad de API, esquema, contratos o configuración.
- Cambios que afectan logging, auditoría o monitoreo de eventos críticos.

Si no existe guardián automático, declarar:

```text
NO_AUTOMATED_GUARD
```

Si el cambio es `MEDIUM` o `HIGH` y no existe guardián automático, debe registrarse como deuda operativa o ADR.

---

#### 5. TRAZABILIDAD

Entregar la ruta exacta o enlace donde queda registrada la trazabilidad del cambio.

Formato mínimo:

```markdown
- REQ: REQ-XXX
- TASK: TASK-XXX
- ADR: ADR-XXX o N/A
- COMMIT/PR: hash, enlace o N/A si no aplica
- TEST: TEST-XXX o ruta de tests
- TRACE: docs/traceability.md, PR description, issue, archivo de tareas o equivalente
```

La trazabilidad debe conectar:

```text
Requisito → Decisión → Tarea → Implementación → Test → Evidencia → Auditoría → Cierre
```

Si falta trazabilidad, la tarea no puede cerrarse.

---

#### 6. BLOQUEOS

Declarar explícitamente qué no se pudo verificar y por qué.

Formato:

```markdown
| Elemento | Estado | Motivo | Impacto | Acción |
|---|---|---|---|---|
| Test de integración con API externa | BLOCKED_BY_ENVIRONMENT | No hay credenciales de prueba | Alto | Solicitar entorno sandbox |
| Prueba de rollback | BLOCKED_BY_PERMISSION | Sin acceso al entorno de despliegue | Crítico | Aprovisionar acceso |
```

Estados permitidos:

```text
BLOCKED_BY_ENVIRONMENT
BLOCKED_BY_AMBIGUITY
BLOCKED_BY_PERMISSION
BLOCKED_BY_MISSING_DEPENDENCY
```

Reglas:

- Un bloqueo crítico impide el cierre.
- Un bloqueo no crítico puede permitir cierre solo si se registra como deuda operativa con responsable, riesgo, mitigación y fecha.
- No se permite ocultar bloqueos bajo una declaración de éxito.

---

### Declaración final de cierre

El reporte debe terminar con un estado explícito:

```text
CIERRE: PASS
```

o

```text
CIERRE: FAIL
```

o

```text
CIERRE: BLOCKED_BY_ENVIRONMENT
CIERRE: BLOCKED_BY_AMBIGUITY
CIERRE: BLOCKED_BY_PERMISSION
CIERRE: BLOCKED_BY_MISSING_DEPENDENCY
```

Prohibido cerrar con:

- "Debería funcionar."
- "Creo que está bien."
- "Parece correcto."
- "Probablemente esté bien."
- "Lo probé por encima."
- "No debería fallar."
- "Quedó listo."
- "Funciona en mi máquina."

Solo se aceptan:

```text
Comandos.
Salidas reales.
Rutas exactas.
Tests.
Logs.
Artefactos.
Evidencia verificable.
```

---

### Regla universal de equivalencia

Si el proyecto no es código, o usa una tecnología donde alguno de estos puntos no aplica directamente, se debe entregar una evidencia equivalente.

Ejemplos:

| Proyecto | Evidencia equivalente |
|---|---|
| Documento | Lint, preview, validación de enlaces, revisión de estructura. |
| Datos | Validación de esquema, conteos, checksums, muestra anonimizada. |
| Infraestructura | Plan dry-run, diff, validación de estado, rollback plan. |
| Automatización | Ejecución en modo seco, logs de ejecución, salida esperada. |
| Hardware/embedded | Simulación, build de firmware, validación de artefacto, checklist reproducible. |
| API | Contrato, tests de endpoint, health check, logs de request. |
| UI | Build, tests de render, captura reproducible, validación de accesibilidad si aplica. |

Si no existe evidencia equivalente posible, debe declararse:

```text
BLOCKED_BY_ENVIRONMENT
```

o el bloqueo correspondiente.
