# Informe MCPs — Ecosistema Atlas / AEGIS-JARVIS

> Generado: 2026-08-19
> Ruta: `E:\Agente_IA\docs\INFORME_MCPs.md`

---

## Resumen Ejecutivo

El ecosistema Atlas dispone de **9 servidores MCP** (Model Context Protocol) que operan como microservicios independientes comunicandose via stdio o HTTP. Cada uno gestiona un dominio especifico del sistema.

| # | MCP | Archivo | Puerto | Tools | Funcion principal |
|---|-----|---------|--------|-------|-------------------|
| 1 | atlas-orchestrator | `atlas_orchestrator.py` | stdio | 7 | Routing inteligente de modelos IA |
| 2 | atlas_guardian | `atlas_guardian.py` | 4098 | 6 | Firewall de operaciones del sistema |
| 3 | atlas-health | `atlas_health.py` | stdio | 2 | Semaforo de salud del ecosistema |
| 4 | atlas_foco | `atlas_foco.py` | 4100 | 5 | Metricas de foco y disciplina |
| 5 | atlas_search | `atlas_search.py` | 4099 | 3 | Busqueda web + investigacion |
| 6 | Atlas Memory Server | `mcp_memory_server.py` | stdio | 15+ | Memoria persistente (vault + SQLite) |
| 7 | MCP Windows | `mcp_windows/mcp_windows_server.py` | stdio | 15+ | Automatizacion de Windows (UIA, input) |
| 8 | CorelDRAW Automation | `mcp_windows/mcp_corel_server.py` | stdio | 15+ | Automatizacion de CorelDRAW |
| 9 | Playwright Visual | `mcp_windows/mcp_playwright_visual_server.py` | stdio | 11 | Automatizacion de navegador + auditoria visual |

---

## 1. atlas-orchestrator — Orquestador de Modelos

**Archivo:** `E:\Agente_IA\atlas_orchestrator.py`
**Puerto:** stdio (MCP) / 4103 (HTTP)
**Tools MCP:** 7

### Que hace
Detecta en vivo cuales proveedores de modelos IA estan activos (omniroute, 9router, ollama) y decide automaticamente el MEJOR modelo para cada tarea, basado en:
- **Nivel de complejidad** (L0/L1/L2/L3) — clasificado por atlas_c4
- **Capacidad requerida** (vision, coding, reasoning, speed)
- **Contexto estimado** (tokens del prompt vs ventana del modelo)
- **Costo** (gratis primero, fallback a pago)

### Tools disponibles

| Tool | Descripcion |
|------|-------------|
| `orchestrator_available()` | Lista proveedores ACTIVOS y modelos disponibles (sin falsos positivos) |
| `orchestrator_analyze(task, nivel, ctx_tokens)` | Analiza tarea y sugiere el mejor modelo activo |
| `orchestrator_route(task, nivel, ctx_tokens)` | Igual que analyze + registra decision en routing_log.json |
| `orchestrator_report(limit)` | Historial de routing y salud de providers |
| `orchestrator_provider_health()` | Estado de cada provider: fallos, cooldown, ultimo error |
| `orchestrator_register_error(provider, error)` | Registra fallo real de un provider (lo degrada si es persistente) |
| `orchestrator_register_success(provider)` | Marca provider como OK (resetea fallos consecutivos) |

### Circuit Breaker
- 3 fallos consecutivos → cooldown de 5 minutos
- Fallback chain: omniroute → 9router → ollama → offline (phi4 local)
- L2+ sin provider → ESCALAR (no razonar a ciegas con 1.5b)

### Caché
- Modelos instalados: cache de 15s para no golpear la API en cada llamada
- Routing log: ultimas 500 entradas en `memory_data/state/routing_log.json`

---

## 2. atlas_guardian — Firewall de Seguridad

**Archivo:** `E:\Agente_IA\atlas_guardian.py`
**Puerto:** 4098 (HTTP)
**Tools MCP:** 6

### Que hace
Valida SIEMPRE antes de ejecutar cualquier operacion del sistema. Es el "cinturon de gobernanza" que impide que el agente ejecute codigo nativo peligroso.

### Niveles de seguridad

| Nivel | Comportamiento |
|-------|---------------|
| `relax` | Todo permitido, solo registra en logs |
| `guard` | Lista blanca de binarios; acciones sensibles → confirma con usuario (DEFAULT) |
| `strict` | Solo acciones de bajo riesgo; bloquea run_script/process_kill/registry_write |

### Tools disponibles

| Tool | Descripcion |
|------|-------------|
| `guardian_check(operation, params)` | Valida si una operacion esta permitida. Retorna: allowed, reason, requires_confirmation |
| `guardian_set_level(level)` | Cambia nivel: relax / guard / strict |
| `guardian_get_config()` | Devuelve configuracion actual |
| `guardian_add_whitelist(cmd, list_type)` | Anade binario/proceso a lista blanca |
| `guardian_remove_whitelist(cmd, list_type)` | Quita de lista blanca |
| `guardian_add_allowed_dir(path)` | Anade directorio permitido para file_delete |

### Configuracion (`state/guardian.json`)
```json
{
  "level": "guard",
  "whitelist_binaries": ["python", "node", "npm", "git", "pip", "wscript", "powershell", "cmd"],
  "whitelist_processes": ["python.exe", "node.exe", "code.exe", "powershell.exe", "cmd.exe"],
  "allowed_dirs": ["E:\\Agente_IA", "C:\\Users\\Administrator\\Documents"],
  "blocked_ops": ["run_script", "process_kill", "registry_write"],
  "confirm_destructive": true
}
```

### Auditoria
Cada intento bloqueado se registra como nota en el vault de memoria via `tool_note_save` con tags `guardian,audit,blocked`.

---

## 3. atlas-health — Semaforo de Salud

**Archivo:** `E:\Agente_IA\atlas_health.py`
**Puerto:** stdio (MCP) / 4102 (HTTP)
**Tools MCP:** 2

### Que hace
Verifica TODOS los componentes del ecosistema y devuelve un semaforo global:
- **green** → todo OK
- **yellow** → hay alertas (componentes no criticos caidos)
- **red** → fallos criticos (providers de modelos caidos)

### Tools disponibles

| Tool | Descripcion |
|------|-------------|
| `health_status()` | Semaforo global + detalle por componente |
| `health_check(name)` | Chequea un componente especifico (vacio = todos) |

### Componentes verificados

| Componente | Critico | Que verifica |
|------------|---------|-------------|
| daemon_activity | Si | Heartbeat del daemon de actividad (age < 120s) |
| omniroute | Si | Puerto 20128 + API /v1/models responde |
| ollama | No | Puerto 11434 + API /api/tags responde |
| venv_python | Si | Existe `.venv/Scripts/python.exe` |
| state_dir | Si | Existe `memory_data/state/` |
| config_guardian | No | Existe `state/guardian.json` |
| config_foco | No | Existe `state/foco_rules.json` |
| config_search | No | Existe `state/search.json` |
| inbox_pending | No | < 20 eventos pendientes en inbox/ |

---

## 4. atlas_foco — Metricas de Foco

**Archivo:** `E:\Agente_IA\atlas_foco.py`
**Puerto:** 4100 (HTTP)
**Tools MCP:** 5

### Que hace
Mide y controla la productividad del usuario. Clasifica el tiempo de uso de aplicaciones en categorias (productivo, distraccion, social, etc.) y genera reportes diarios.

### Tools disponibles

| Tool | Descripcion |
|------|-------------|
| `foco_set_mode(mode)` | Cambia modo: off (solo medir) / soft (avisos, default) / strict (agresivo) |
| `foco_get_rules()` | Devuelve reglas actuales (categorias, umbrales, excepciones) |
| `foco_daily_summary(date)` | Resumen del dia: tiempo productivo vs fugado + top apps |
| `foco_override(app, category)` | Override manual: fuerza categoria de una app |
| `foco_backfill(limit, force)` | Clasifica eventos historicos sin categoria |

### Configuracion (`state/foco_rules.json`)
- Modo de operacion
- Categorias con apps asociadas (productivo, social, distraction, etc.)
- Umbrales de tiempo por categoria
- Presupuesto diario de distraccion

### Base de datos
SQLite en `memory_data/state/memory.db` — tabla `events` con clasificacion por app, titulo de ventana, categoria y duracion.

---

## 5. atlas_search — Busqueda Web

**Archivo:** `E:\Agente_IA\atlas_search.py`
**Puerto:** 4099 (HTTP)
**Tools MCP:** 3

### Que hace
Busqueda en internet con cadena de respaldo automatica: DuckDuckGo → SearXNG → DuckDuckGo HTML scrape. Tambien investigacion academica.

### Tools disponibles

| Tool | Descripcion |
|------|-------------|
| `web_search(query, max_results)` | Busqueda general con 3 fuentes en cascada |
| `web_research(topic, depth)` | Investigacion profunda: busca + resume + guarda en vault |
| `web_research_academic(query, max_results, databases)` | Busqueda academica (CrossRef, arXiv) |

### Cadenas de respaldo
1. **DuckDuckGo** (lib `ddgs`) — rapido, sin API key
2. **SearXNG** (self-hosted) — si esta configurado en `state/search.json`
3. **DuckDuckGo HTML** (scrape) — fallback duro sin dependencias

### Configuracion (`state/search.json`)
```json
{
  "searxng_url": "",
  "timeout_ddgs": 15,
  "timeout_searxng": 10,
  "max_results": 10
}
```

---

## 6. Atlas Memory Server — Memoria Persistente

**Archivo:** `E:\Agente_IA\mcp_memory_server.py`
**Puerto:** stdio (MCP)
**Tools MCP:** 15+

### Que hace
El "cerebro" del sistema. Almacena todo de forma persistente:
- **Vault Obsidian**: notas markdown con frontmatter YAML (abre directo en Obsidian)
- **SQLite**: eventos, sesiones, indices FTS5 para busqueda full-text
- **Grafo de conocimiento**: nodos y aristas derivados de links entre notas

### Tools disponibles

| Tool | Descripcion |
|------|-------------|
| `tool_init(project, project_root)` | Inicializa proyecto en el vault |
| `tool_note_save(title, body, type, project, tags)` | Guarda nota (decision, fact, preference, summary, etc.) |
| `tool_note_search(query, project, limit, scope)` | Busqueda full-text en notas |
| `tool_session_start(project, note)` | Inicia sesion de trabajo |
| `tool_session_end(session_id, summary)` | Cierra sesion con resumen |
| `tool_session_recover(project)` | Recupera sesiones huerfanas |
| `tool_event_ingest(project)` | Ingesta eventos desde inbox/ |
| `tool_pref_set(key, value, project)` | Guarda preferencia (key-value) |
| `tool_pref_get(key, project)` | Lee preferencias |
| `tool_graph_query(node, project, depth)` | Consulta grafo de conocimiento |
| `tool_graph_rebuild(project)` | Reconstruye grafo desde notas |
| `tool_summary(project, budget)` | Resumen del contexto del proyecto |
| `tool_health()` | Salud de la memoria (DB, inbox, daemon, secretos) |
| `tool_gc(keep_days)` | Limpieza de eventos viejos |
| `tool_projects(limit)` | Lista todos los proyectos con memoria |
| `tool_backup(keep)` | Backup zip de vault + DB |
| `tool_restore(backup_file)` | Restaura desde backup |

### Estructura del vault
```
memory_data/vault/
├── global/
│   ├── preferences/    # identity.md, user_name.md, ciudad.md
│   ├── notes/          # notas globales
│   └── decisions/      # decisiones globales
├── <proyecto>/
│   ├── MEMORY.md       # indice ligero
│   ├── notes/
│   ├── decisions/
│   ├── facts/
│   ├── sessions/
│   ├── preferences/
│   └── graph.json      # grafo derivado
└── outputs/            # informes publicados
```

### Seguridad
- Redaccion automatica de secretos (sk-*, tokens, passwords) en toda escritura
- Rutas validadas contra traversal (`Path.is_relative_to`)
- Proyectos sanitizados con regex

---

## 7. MCP Windows — Automatizacion de Windows

**Archivo:** `E:\Agente_IA\mcp_windows\mcp_windows_server.py`
**Puerto:** stdio (MCP)
**Tools MCP:** 15+

### Que hace
Automatizacion completa de Windows: mouse, teclado, ventanas, procesos, screenshots, OCR, y ejecucion de scripts (si guardian lo permite).

### Tools disponibles

| Tool | Descripcion |
|------|-------------|
| `mouse_move(x, y, duration)` | Mueve el mouse a coordenadas |
| `mouse_click(x, y, button)` | Click izquierdo/derecho/medio |
| `mouse_scroll(clicks, x, y)` | Scroll vertical/horizontal |
| `mouse_position()` | Posicion actual del mouse |
| `mouse_drag(x, y, button, duration)` | Arrastra el mouse |
| `keyboard_type(text, interval)` | Escribe texto con el teclado |
| `keyboard_hotkey(keys)` | Combinacion de teclas (ej: "ctrl+c") |
| `keyboard_press(key, presses)` | Presiona una tecla |
| `ocr_screen(region, language)` | OCR de pantalla (via Tesseract) |
| `web_fetch(url, max_chars)` | Obtiene contenido de una URL |
| + screenshot, window management, process management, etc. |

### Seguridad
Cada operacion pasa por `atlas_guardian.check()` antes de ejecutarse. En modo `guard`, las acciones destructivas requieren confirmacion del usuario.

---

## 8. CorelDRAW Automation — Automatizacion de CorelDRAW

**Archivo:** `E:\Agente_IA\mcp_windows\mcp_corel_server.py`
**Puerto:** stdio (MCP)
**Tools MCP:** 15+

### Que hace
Automatizacion completa de CorelDRAW via COM (Windows). Permite crear, editar y exportar disenos programaticamente.

### Tools disponibles

| Tool | Descripcion |
|------|-------------|
| `corel_ping()` | Verifica si CorelDRAW esta abierto |
| `corel_create_document(name, width, height)` | Crea documento nuevo |
| `corel_open_document(file_path)` | Abre archivo .cdr |
| `corel_save_document(file_path)` | Guarda documento |
| `corel_close_document(save)` | Cierra documento |
| `corel_get_document_info()` | Info del documento activo |
| `corel_create_layer(name)` | Crea capa nueva |
| `corel_select_layer(name)` | Selecciona capa |
| `corel_list_layers()` | Lista capas |
| `corel_add_text(text, x, y, font, size)` | Agrega texto |
| `corel_add_rectangle(x, y, w, h)` | Agrega rectangulo |
| `corel_add_ellipse(x, y, w, h)` | Agrega elipse |
| `corel_list_objects()` | Lista objetos en la pagina |
| `corel_select_all()` | Selecciona todo |
| `corel_delete_selection()` | Elimina seleccion |
| `corel_align_objects(indices, alignment)` | Alinea objetos |
| `corel_duplicate_shape(idx, offset_x, offset_y)` | Duplica forma |
| `corel_transform_shape(idx, rotate, scale_x, scale_y)` | Transforma forma |
| `corel_boolean_operation(idx1, idx2, operation)` | Operaciones booleanas (union, subtract, intersect) |
| `corel_group_shapes(indices)` | Agrupa formas |
| `corel_ungroup_shape(idx)` | Desagrupa |
| `corel_set_fill_gradient(idx, ...)` | Relleno degradado |
| `corel_set_fill_solid(idx, color_hex)` | Relleno solido |
| `corel_set_stroke(idx, color_hex, width)` | Borde/contorno |

### Capacidades avanzadas
- Curvas bezier con puntos de control
- Operaciones booleanas (union, resta, interseccion, exclusiva)
- Transformaciones (rotar, escalar, sesgar)
- Alineacion y distribucion
- Control de capas y orden Z

---

## 9. Playwright Visual — Automatizacion de Navegador

**Archivo:** `E:\Agente_IA\mcp_windows\mcp_playwright_visual_server.py`
**Puerto:** stdio (MCP)
**Tools MCP:** 11

### Que hace
Automatizacion de navegador con Playwright + auditoria visual. Permite navegar, interactuar, capturar y analizar paginas web.

### Tools disponibles

| Tool | Descripcion |
|------|-------------|
| `pw_start(url, headless, width, height)` | Inicia navegador y navega a URL |
| `pw_close()` | Cierra navegador |
| `pw_goto(url)` | Navega a URL |
| `pw_click(selector, timeout_ms)` | Click en elemento CSS |
| `pw_fill(selector, text, timeout_ms)` | Rellena campo de texto |
| `pw_press(key)` | Presiona tecla |
| `pw_screenshot(selector, full_page)` | Captura de pantalla (elemento o pagina completa) |
| `pw_ancestors(selector, css_vars)` | Arbol de ancestros CSS de un elemento |
| `pw_computed_style(selector, properties)` | Estilos computados de un elemento |
| `pw_visual_audit(selector, is_overlay, css_vars)` | Auditoria visual: colores, contraste, tamanos |
| `pw_diff(baseline_path, selector, threshold)` | Dif visual: compara estado actual vs baseline |

### Auditoria visual
El `pw_visual_audit` verifica:
- Paleta de colores usada
- Contraste de texto vs fondo (WCAG)
- Tamanos de fuente
- Espaciado y margenes
- Bordes y border-radius
- Opacidad y blur

### Dif visual
`pw_diff` compara una imagen baseline con el estado actual y detecta cambios visuales con umbral configurable.

---

## Integracion entre MCPs

```
┌─────────────────────────────────────────────────────────┐
│                    AEGIS-JARVIS HUD                       │
│                    (bridge.py :8765)                      │
└──────────┬──────────────────────────────┬───────────────┘
           │                              │
    ┌──────▼──────┐              ┌────────▼────────┐
    │   Router     │              │  Agent Mode      │
    │  (qwen2.5)   │              │  (Bucle tools)   │
    └──────┬──────┘              └────────┬────────┘
           │                              │
           │    ┌─────────────────────────┤
           │    │                         │
    ┌──────▼────▼───────┐    ┌───────────▼──────────┐
    │ atlas-orchestrator │    │  Governance Belt     │
    │ (elige modelo)     │    │  (bloquea nativo)    │
    └───────────────────┘    └───────────┬──────────┘
                                         │
                    ┌────────────────────┬┴───────────────┐
                    │                    │                  │
             ┌──────▼──────┐    ┌───────▼───────┐  ┌──────▼──────┐
             │   guardian   │    │    memory      │  │   windows   │
             │  (valida)    │    │  (persiste)    │  │ (automatiza)│
             └─────────────┘    └───────────────┘  └──────┬──────┘
                                                          │
                                              ┌───────────┼───────────┐
                                              │           │           │
                                       ┌──────▼──┐ ┌─────▼─────┐ ┌───▼──────┐
                                       │  corel   │ │playwright │ │  search  │
                                       │ (diseño) │ │ (naveg)   │ │  (web)   │
                                       └─────────┘ └───────────┘ └──────────┘
```

### Flujo tipico de una orden
1. Usuario escribe orden en el HUD
2. **Router** clasifica intencion (qwen2.5:1.5b → chat o agent)
3. Si es agent → **orchestrator** elige el mejor modelo
4. **Guardian** valida que la operacion este permitida
5. Agente ejecuta tools via MCPs (windows, corel, playwright, etc.)
6. **Memory** persiste resultados y crea notas
7. **Health** monitorea que todo funcione
8. **Foco** registra tiempo de productividad

---

## Puertos y Endpoints

| MCP | Puerto MCP | Puerto HTTP | CLI |
|-----|-----------|-------------|-----|
| atlas-orchestrator | stdio | 4103 | `python atlas_orchestrator.py --cli` |
| atlas_guardian | stdio | 4098 | `python atlas_guardian.py` |
| atlas-health | stdio | 4102 | `python atlas_health.py --cli` |
| atlas_foco | stdio | 4100 | `python atlas_foco.py --cli daily` |
| atlas_search | stdio | 4099 | `python atlas_search.py` |
| memory | stdio | — | `python mcp_memory_server.py --cli health` |
| windows | stdio | — | `python mcp_windows/mcp_windows_server.py` |
| corel | stdio | — | `python mcp_windows/mcp_corel_server.py` |
| playwright | stdio | — | `python mcp_windows/mcp_playwright_visual_server.py` |
| **bridge (AEGIS)** | — | **8765** | `python aegis_hud/backend/bridge.py` |

---

## Como levantar todo

```bash
# 1. Backend AEGIS (HUD + API)
cd E:\Agente_IA\aegis_hud\backend
python bridge.py

# 2. MCPs individuales (via opencode o manualmente)
cd E:\Agente_IA
python atlas_orchestrator.py          # MCP stdio
python atlas_guardian.py              # MCP stdio
python atlas_health.py --cli          # CLI rapido
python atlas_foco.py --cli daily      # Resumen de hoy
python mcp_memory_server.py           # MCP stdio

# 3. MCPs de Windows (requieren Windows)
python mcp_windows/mcp_windows_server.py
python mcp_windows/mcp_corel_server.py
python mcp_windows/mcp_playwright_visual_server.py
```

---

*Fin del informe.*
