---
id: 20260817-200655-n8n-opera-browser-operator-config
type: fact
project: default
tags: []
created: 2026-08-18T01:06:55+00:00
source: opencode
status: active
links:
---

Configuración rápida para usar n8n con la función Browser Operator de Opera.

1. Instalar n8n y arrancarlo (`n8n start`).
2. Actualizar Opera a la versión que incluye Browser Operator (sidebar > ícono).
3. El operator expone un endpoint local, por defecto `http://127.0.0.1:3005/api/operator/run`.
4. Importar el workflow `n8n_opera_workflow.json` en la interfaz de n8n (Menú Import).
5. El nodo HTTP Request envía un POST con un prompt natural, ej:
   {"prompt": "Abre https://example.com y devuelve el título"}.
6. La respuesta contiene el título u otra información devuelta por Opera.

La arquitectura mantiene todo el tráfico en localhost, respetando la privacidad de Opera.
