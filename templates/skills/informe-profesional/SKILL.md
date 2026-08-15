---
name: informe-profesional
description: "Usar cuando el usuario pida informe, reporte, analisis, comparativa o documento. Aplica estandar de 6 bloques y maquetacion profesional."
---

# Informe Profesional

Estándar de entrega de documentos (REQ-C6).

## 1. Orden de trabajo + nivel
- Nivel default: L2 (consultar `preferences/style_profile.md`).
- L0: listado rapido. L1: basico. L2: ejecutivo (2-3 rondas). L3: exhaustivo.

## 2. Estructura obligatoria (6 bloques)
1. **Resumen ejecutivo** — conclusiones PRIMERO, 5-10 lineas
2. **Contexto y objetivo**
3. **Desarrollo / Hallazgos**
4. **Comparativa y evidencia** (tabla para comparativas, SVG inline para series)
5. **Recomendaciones** — priorizadas P1/P2/P3, accionables, con responsable y plazo
6. **Limitaciones y fuentes** — jerarquizadas, numeradas inline

## 3. Maquetacion
- **HTML single-file** sin dependencias externas (abrible offline) usando
  plantilla `vault/global/templates/informe_6_bloques.html`.
- DOCX via windows MCP si el usuario lo prefiere.
- MD en boveda SIEMPRE.

## 4. Pase critico
- Skill `critico` (modelo DISTINTO) ANTES de mostrar.

## 5. Versionado
- `-v1`, `-v2` si hay feedback.
- Exemplar si el usuario califica "asi si" -> `templates/exemplars/`.

## 6. Publicacion
- Guardar en `vault/outputs/`.
- Publicar en dashboard (`publish_report`).
- Commit si aplica.
