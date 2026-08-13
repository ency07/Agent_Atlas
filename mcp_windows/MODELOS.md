# 🤖 Guía de Modelos Ollama para MCP Windows AI

> Archivo de referencia rápida: qué modelo usar según la tarea.
> Hardware de este PC: **20GB RAM / Intel HD 4600 (sin GPU dedicada)** → todo corre por CPU.

---

## 📊 Modelos instalados en este PC

| Modelo | Tamaño | Velocidad (CPU) | Inteligencia | Uso recomendado |
|--------|--------|-----------------|--------------|-----------------|
| `qwen2.5-coder:7b` | 4.7 GB | 🐢 Lento (5-15s) | ⭐⭐⭐⭐⭐ | Automatización, código, workflows |
| `phi4-mini:latest` | 2.5 GB | 🚶 Medio | ⭐⭐⭐⭐ | Equilibrio general |
| `llama3.2:3b` | 2.0 GB | 🏃 Rápido | ⭐⭐⭐ | Tareas simples del día a día |
| `qwen2.5:3b` | 1.9 GB | 🏃 Rápido | ⭐⭐⭐ | Alternativa a llama3.2 |
| `qwen3:1.7b` | 1.4 GB | ⚡ Muy rápido | ⭐⭐ | Pruebas, comandos básicos |

> Eliminados el 2026-07-28 por no servir para tool-calling: `qwen3:0.6b`, `gemma3:1b`.

---

## 🥇 Comandos para iniciar el cliente

### Opción 1 — Máxima inteligencia (recomendado para workflows)
```bash
python mcp_ollama_client.py --model qwen2.5-coder:7b
```
Ideal para: crear documentos, scripts, automatización de varios pasos, Excel con fórmulas, PowerPoint.

### Opción 2 — Equilibrio velocidad/inteligencia
```bash
python mcp_ollama_client.py --model phi4-mini
```
Ideal para: uso diario, abrir programas, organizar archivos, consultas del sistema.

### Opción 3 — Máxima velocidad
```bash
python mcp_ollama_client.py --model llama3.2:3b
```
Ideal para: comandos simples, listar archivos, mover ventanas, capturas de pantalla.

### Opción 4 — Modo automático (sin confirmaciones, ¡cuidado!)
```bash
python mcp_ollama_client.py --model phi4-mini --auto
```
⚠️ Solo usar en tareas seguras. Desactiva el sistema de aprobación.

### Menú interactivo
```bash
run_with_ollama.bat
```

---

## 🎯 Regla rápida de decisión

```
¿La tarea necesita crear documentos/scripts/código?  → qwen2.5-coder:7b
¿Es una mezcla de varias cosas?                      → phi4-mini
¿Es algo simple y quiero respuesta ya?               → llama3.2:3b
```

---

## 💡 Consejos para CPU (sin GPU)

1. **Cierra programas pesados** antes de usar el modelo 7B (Chrome con muchas pestañas, juegos).
2. **El primer mensaje siempre tarda más** (el modelo se carga en RAM). Los siguientes son más rápidos.
3. **Frases cortas y directas** funcionan mejor que párrafos largos.
4. Si el modelo se "traba", escribe `reset` en la sesión para limpiar el historial.
5. Para tareas largas, divide en pasos: primero "crea el Excel", luego "ahora agrégale las fórmulas".

---

## 🔒 Niveles de aprobación (sistema de seguridad)

| Nivel | Qué hace | Ejemplos |
|-------|----------|----------|
| 🟢 BAJO | Automático | listar archivos, info del sistema, capturas |
| 🟡 MEDIO | Enter para aprobar | clicks, escribir texto, mover ventanas |
| 🟠 ALTO | Escribir `y` | crear/editar archivos, ejecutar scripts |
| 🔴 CRÍTICO | Escribir `CONFIRMAR` | borrar archivos, matar procesos, comandos shell |
