---
name: entrega
description: "Usar al finalizar toda tarea con entregable. Ritual de persistencia y presentacion."
---

# Entrega

Ritual de cierre de tarea con entregable (REQ-C8).

## 1. Persistir
- Guardar HTML en `vault/outputs/<nombre>-v<version>.html`.
- Guardar MD en `vault/<proyecto>/notes/<nombre>.md`.
- Si aplica DOCX -> copiar a `vault/outputs/`.

## 2. Publicar
- Llamar `publish_report(html_path, title, level)` para que quede en el dashboard.

## 3. Grafo
- Si se creo una nota nueva, verificar que el grafo se actualizo.

## 4. Mensaje final al usuario
Formato:
```
Listo.
- Publicado en dashboard
- Archivado en vault/outputs/
- Cubri: A, B, C
- Exclui: D (alcance)
- Limitaciones: X
- Fuentes: N (en anexo)
```

## 5. Versionado
- Primera entrega: `-v1`.
- Con feedback: `-v2`, `-v3`.
- Exemplar calificado "asi si": copiar a `templates/exemplars/` como referencia.
