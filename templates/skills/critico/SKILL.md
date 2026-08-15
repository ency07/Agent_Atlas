---
name: critico
description: "Usar ANTES de entregar cualquier entregable. Pase de auditoria con modelo DISTINTO al generador."
---

# Critico

Pase de auditoria pre-entrega (REQ-C7).

## Regla de oro
El CRITICO lo hace un modelo/agente DISTINTO al que genero el entregable.
Nunca auto-auditar el propio trabajo sin separacion.

## Checklist
- [ ] Sin placeholders (TODO, XXX, Lorem, "pendiente de...").
- [ ] Sin invencion: toda afirmacion tiene fuente o evidencia.
- [ ] Sin huecos: ninguna seccion vacia o "ver anexo" sin anexo.
- [ ] Maquetacion: HTML offline funcional, tablas alineadas, SVG legible.
- [ ] Resumen ejecutivo PRIMERO con conclusiones.
- [ ] Recomendaciones P1/P2/P3 accionables.
- [ ] Limitaciones y fuentes jerarquizadas.
- [ ] Coherente con la orden de trabajo (objetivo/alcance/nivel).
- [ ] Datos vs opinion separados.
- [ ] Redaccion de datos sensibles (REQ-C14) verificada.

## Si detecta problemas
- Exigir correccion ANTES de mostrar al usuario.
- Devolver al generador con lista concreta de fallos.

## Evidencia
- El pase critico deja nota en la boveda: `type=audit`, resultado PASS/FAIL + hallazgos.
