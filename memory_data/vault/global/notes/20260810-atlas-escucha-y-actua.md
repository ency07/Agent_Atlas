---
id: 20260810-atlas-escucha-y-actua
type: note
project: global
tags: [f2, futuro, voz, agente, acciones]
created: 2026-08-10T14:55:00+00:00
source: opencode
status: idea
---

## Intencion futura: Atlas escucha y actua

El usuario lo pidio explicitamente: "para un futuro la idea es que [Atlas]
escuche y actué. Tenelo presente."

Esto significa que el chat flotante (F2) no debe quedarse solo en texto:
- **Escuchar**: entrada por voz (micrófono) → transcripción → chat.
- **Actuar**: el agente debe poder ejecutar acciones en el sistema (abrir apps,
  mover ventanas, automatizar tareas de Windows), no solo responder.

Implicaciones de diseno para cuando se ataque:
- F3/F4 ya preveen "captura de actividad" y "acciones"; la UI debe sumar
  entrada de voz (por ej. pywebview + Web Speech API / reconocedor local) y
  salida hablada (TTS).
- "Actuar" en Windows: el repo hermano `E:\MCP\mcp-windows-ai` ya tiene
  servers MCP de windows/corel-draw/playwright-visual que pueden ejecutar
  acciones. El chat flotante puede exponer esas tools.
- Mantener la arquitectura: opencode serve como motor, ventana pywebview como
  piel. Solo hay que añadir captura de voz y llamadas a las tools MCP.

Cuando se retome, este es el norte: el chat flotante pasa de "responde" a
"escucha y hace".
