---
type: preference
scope: global
tags: [style,delivery,defaults]
---

# Perfil de estilo y preferencias de entrega

## Defaults del usuario
- **Nivel por defecto:** L2 (ejecutivo, 2-3 rondas, 2 fuentes/afirmacion)
- **Formato por defecto:** HTML single-file offline (DOCX solo si se pide)
- **Nunca entregar:** .txt plano sin formato
- **Idioma:** espanol
- **Tono:** datos > adjetivos, frases cortas, sin relleno

## Estilo de informes
- Resumen ejecutivo PRIMERO (5-10 lineas, conclusiones antes que hallazgos)
- Tablas para comparativas, SVG inline para series temporales
- Fuentes numeradas inline, jerarquizadas en anexo
- Prohibido: "en el mundo dinamico de hoy", frases sin dato, placeholders TODO
- Recomendaciones: priorizadas P1/P2/P3, accionables, con responsable y plazo

## Feedback del usuario ( REQ-C12 )
- Cada correccion del usuario se guarda como nota `type=feedback` en la boveda
- Despues de 3+ feedbacks, revisar y ajustar este archivo
- Los entregables calificados "asi si" se guardan como exemplar en `vault/global/templates/exemplars/`
