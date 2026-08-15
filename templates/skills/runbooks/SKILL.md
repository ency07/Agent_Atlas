---
name: runbooks
description: "Usar ANTES de ejecutar procedimientos repetidos (instalar extension, exportar diseno, publicar informe) y DESPUES de uno exitoso nuevo."
---

# Runbooks

Procedimientos verificados y reutilizables (REQ-C11).

## Formato
`vault/<proyecto>/runbooks/<nombre>.md`

```markdown
---
type: runbook
status: verified        # verified | stale
programa: <nombre>
version_programa: <v>  # ej: Chrome 128
ultima_verificacion: <fecha>
tags: []
---

# <Nombre>

## Objetivo
<que logra>

## Pasos
1. <accion> — <criterio de exito del paso>
2. ...

## Verificacion final
- <que comprueba que quedo bien>

## Reintentos conocidos
- <fallo comun> -> <solucion>
```

## Ciclo
- **verified** -> reusado -> **stale** si cambia version del programa
- Al usar un runbook stale -> re-verificar antes de ejecutar.
- Solo guardar runbooks que se hayan ejecutado EXITOSAMENTE al menos 1 vez.
