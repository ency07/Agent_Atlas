---
name: ejecucion-verificada
description: "Usar al ejecutar CUALQUIER tarea que modifique o configure programas, archivos o el PC del usuario. Obligatoria antes de tocar UI, apps o configs."
---

# Ejecucion Verificada (MASTER)

Protocolo obligatorio para toda tarea que toque programas/archivos/PC.

## 1. Orden de trabajo
Antes de ejecutar, construir la orden estructurada:
- **Objetivo**: que se quiere lograr (no la frase literal)
- **Alcance**: que se tocara y que NO
- **Profundidad**: nivel L0-L3
- **Entregable**: formato y destino
- **Criterios de aceptacion**: como se sabra que quedo bien

Si hay ambiguedad critica -> preguntar UNA vez.

## 2. Programa registrado
- Leer `preferences/programas.md`.
- Si el programa NO esta registrado -> preguntar UNA vez y registrar.

## 3. Runbook
- Buscar en skill `runbooks` uno aplicable.
- Si existe -> seguirlo.
- Si no -> planificar pasos con criterio de exito POR PASO.

## 4. Loop ejecutar -> verificar (cascada)
Ejecutar UN paso. Verificar en cascada:
1. **API/CLI** (mas confiable)
2. **UIA** (`read_ui_state`)
3. **OCR/captura + vision** (`screen_capture` + `ocr_screen`)
4. **Teclado/mouse** (windows MCP)

## 5. Fallo
- Reintentar con alternativa (max 2 veces).
- Segundo fallo -> checkpoint + reportar con evidencia.
- **NUNCA exito falso.**

## 6. Dialogos nativos
- Detectar con UIA/OCR.
- Operar con teclado/mouse via windows MCP.

## 7. Verificacion final
- Contra criterios de aceptacion de la orden.

## 8. Runbook nuevo
- Si el procedimiento fue nuevo y exitoso -> guardar runbook.

## 9. Entrega
- Ritual del skill `entrega`.
