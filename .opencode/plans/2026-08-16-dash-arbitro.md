# PLAN — DASH v3 + UX ÁRBITRO · integrado con fixes de red-team

**Fecha:** 2026-08-16 · **Estado:** PLAN (pre-ejecución)

---

## Inventario del estado actual

### Archivos existentes (reutilizar)
| Archivo | Rol | Relevancia |
|---|---|---|
| `atlas_web_server.py` | Servidor :4100, 15 endpoints | Agregar `/api/live`, `/api/mercado`, `/api/noticias`, `/api/clima`, `/api/grafo`, `/api/orden`, `/api/confirmaciones`, `/api/task_heartbeat/{id}`, `/api/ui_config` |
| `atlas_web/dashboard.html` (v2) | Dashboard actual 388 líneas | Reemplazar con v3 si `UI_V3=1`; fallback si `UI_V3=0` |
| `atlas_web/api.js` | Wrapper UI→opencode serve | Reutilizar patrón fetch |
| `atlas_supervisor.py` | COMPONENTS dict, monitor loop 30s | Agregar `overlay`, `orders`, `ui_manager` |
| `atlas_controller.py` | C2 contrato→verificar→cerrar/escalar | Reutilizar `crear_contrato()`, `ejecutar_liviano()`, `verificar()` |
| `atlas_c4.py` | Clasificador L0/L1/L2+ | Reutilizar `classify_level()`, `generate_contract()` |
| `atlas_health.py` | `health_report()` → checks[] | Consumir desde `/api/live` |
| `atlas_foco.py` | `foco_daily_summary()` MCP+CLI | Consumir desde `/api/foco` (ya existe) |
| `atlas_activity.py` | Daemon heartbeat → `state/daemon.heartbeat` | Consumir para `daemon_age_s` en `/api/live` |
| `atlas_chat.py` | pywebview face (567 líneas) | Patrón a seguir: `webview.create_window`, `OVERLAY_JS`, `Api` class, `set_window_icon` |
| `atlas_guardian.py` | `guardian_check()` MCP | Integrar en flujo de permisos overlay |
| `atlas_log.py` | `get_logger(source)` logs JSON | Usar en todos los nuevos módulos |
| `atlas_monitor.py` | `track_error()` | Usar en overlay + ui_manager |
| `atlas_verifier.py` | Verificador por tipo C2 | Integrar en `atlas_orders.py` |

### Archivos NUEVOS a crear
| Archivo | Descripción | Líneas aprox |
|---|---|---|
| `atlas_ui_manager.py` | FULL↔EXEC, HWND en ui_config, minimise/restore, pin | ~250 |
| `atlas_overlay.py` | Overlay on_top 380px, pulso+task+permisos | ~300 |
| `atlas_orders.py` | Drenador de órdenes: lee state/orders/ → C4 → ejecuta | ~200 |
| `atlas_web/dashboard_v3.html` | Dashboard v3: radial, vistas ricas, order bar | ~800 |
| `atlas_web/algorithmic_art.js` | Fondo procedural una vez | ~100 |
| `memory_data/state/ui_config.json` | UI_V3, HWND, flags | ~20 |
| `tests/unit/test_dash_v3.py` | Tests dashboard v3 | ~200 |
| `tests/unit/test_ui_arbitro.py` | Tests UX árbitro | ~250 |

### Directorios NUEVOS
| Directorio | Propósito |
|---|---|
| `memory_data/state/orders/` | Cola de órdenes (atomic write por archivo) |
| `memory_data/state/task_heartbeat/` | Heartbeat por tarea (atomic write temp+rename) |
| `memory_data/state/confirmaciones/` | Respuestas de permisos desde overlay |

---

## FASE 1 — Infraestructura base (sin UI)

### P1.1 `memory_data/state/ui_config.json`

```json
{
  "UI_V3": 1,
  "HWND": null,
  "face_fullscreen": true,
  "overlay_on_top": true,
  "overlay_width": 380,
  "overlay_height": 600,
  "poll_live_ms": 2000,
  "poll_slow_ms": 30000,
  "art_bg_asset": "algorithmic_art.png",
  "permission_timeout_s": 60,
  "max_graph_nodes": 150,
  "news_sources": [
    "https://feeds.bbci.co.uk/news/technology/rss.xml",
    "https://rss.nytimes.com/services/xml/rss/nyt/Technology.xml"
  ]
}
```

- **Rollback**: `UI_V3=0` → sirve `dashboard.html` (v2)
- **Escritura**: solo `atlas_ui_manager.py` y `atlas_overlay.py` (no concurrente)
- **Lectura**: dashboard v3 lee al cargar, overlay lee cada 2s

### P1.2 `atlas_web_server.py` — nuevos endpoints

**Todos en el mismo archivo** (regla: no crear servidores nuevos).

#### Adaptador base (reutilizable)
```python
_adaptador_cache = {}
_adaptador_ts = {}

def _adaptador_stale(key, fetch_fn, ttl_s=900):
    """Intenta fetch_fn(); fallo → caché + stale=True."""
    now = time.time()
    if key in _adaptador_ts and now - _adaptador_ts[key] < ttl_s:
        return _adaptador_cache.get(key), False
    try:
        data = fetch_fn()
        _adaptador_cache[key] = data
        _adaptador_ts[key] = now
        return data, False
    except Exception:
        return _adaptador_cache.get(key), True
```

#### Endpoints nuevos

| Endpoint | Método | Fetch | Caché | Timeout |
|---|---|---|---|---|
| `/api/live` | GET | health_report + tasks + task_heartbeat | 0 (fresco) | 2s |
| `/api/mercado` | GET | stooq (bonds, S&P500) + CoinGecko (BTC) | 15min | 10s |
| `/api/noticias` | GET | xml.etree parse RSS (fuentes en ui_config) | 30min | 10s |
| `/api/clima` | GET | open-meteo (temp, humedad, viento, hourly) | 30min | 10s |
| `/api/grafo` | GET | memory.db FTS5 + graph.json (top 150 nodos) | 15min | 10s |
| `/api/orden` | POST | → state/orders/ (atomic write) | — | — |
| `/api/confirmaciones` | POST | → state/confirmaciones/ (atomic write) | — | — |
| `/api/confirmaciones/{id}` | GET | lee state/confirmaciones/{id}.json | 0 | — |
| `/api/task_heartbeat/{id}` | GET | lee state/task_heartbeat/{id}.json | 0 | — |
| `/api/ui_config` | GET/POST | lee/escribe ui_config.json | 0 | — |

#### `/api/live` — estructura
```json
{
  "health_status": "green|yellow|red",
  "daemon_age_s": 15,
  "tasks_active": 2,
  "tasks": [
    {
      "task_id": "T-...",
      "orden": "instalar extensión X",
      "estado": "EN_CURSO",
      "pct": 60,
      "step": "verificando CR-2",
      "eta_s": 45,
      "last_action": "ejecutando shell: npm install",
      "heartbeat_age_s": 5
    }
  ],
  "permissions_pending": [
    {"id": "PERM-...", "task_id": "T-...", "detail": "L2+ requiere confirmación", "created": "..."}
  ],
  "last_action_ts": "2026-08-16T12:00:00",
  "timestamp": "2026-08-16T12:00:02"
}
```

**Clasificación de heartbeat**:
- `age < 60s` → 🟢 vivo
- `age 60-120s` → 🟡 posiblemente pegado
- `age > 120s` → 🔴 pegado

#### `/api/orden` — POST
Request:
```json
{"texto": "instala la extensión X", "prioridad": "normal"}
```
Response:
```json
{
  "ok": true,
  "order_id": "ORD-20260816-120000",
  "preview": {"nivel": "L1", "criterios": [...], "modelo": "auto/best-fast"},
  "requires_confirmation": false
}
```
L2+ → `requires_confirmation: true` → overlay muestra preview + [Ejecutar]

#### `/api/orden` — Doble Enter en 2s
Frontend: si el usuario presiona Enter dos veces en <2s, se interpreta como confirmación de contrato L2+.

### P1.3 `state/task_heartbeat/<task_id>.json`

Escritura atómica (temp + rename):
```json
{
  "task_id": "T-...",
  "last_beat": "2026-08-16T12:00:00",
  "writers": ["controller", "mcp_c3", "verifier", "model_stream"],
  "current_step": "verificando CR-2",
  "eta_s": 45,
  "tokens_alive": true
}
```

**Escritores**:
1. `atlas_controller.py`: al inicio de `turno_agente()`
2. MCPs (C3): al completar un paso
3. `atlas_verifier.py`: al verificar un criterio
4. Stream del modelo: cada token → `tokens_alive=true` (si `tokens_alive=true`, NO pegado aunque age >60s)

**Criterio de "pegado"**:
```
pegado = heartbeat_age > 60s AND NOT tokens_alive
stale_yellow = pegado AND heartbeat_age < 120s
stale_red = pegado AND heartbeat_age >= 120s
```

### P1.4 `state/orders/` — cola de órdenes

Cada orden = 1 archivo JSON atómico:
```
state/orders/ORD-20260816-120000.json
```

```json
{
  "order_id": "ORD-...",
  "texto": "instala la extensión X",
  "nivel": "L1",
  "estado": "PENDIENTE|EN_EJECUCION|COMPLETADA|DENEGADA",
  "created": "2026-08-16T12:00:00",
  "completed": null,
  "result": null,
  "contract": null
}
```

### P1.5 `atlas_orders.py` — drenador de órdenes

**Loop**:
1. Escanea `state/orders/` → archivos `PENDIENTE`
2. Para cada uno:
   a. Clasifica: `atlas_c4.classify_level(texto)` + `atlas_c4.generate_contract(texto)`
   b. Actualiza `nivel` + `contract` en el JSON (atomic write)
   c. L0/L1: ejecuta `atlas_controller.ejecutar_liviano(contract)` → resultado directo
   d. L2+: escribe preview → espera confirmación (60s timeout → DENY)
   e. Actualiza `task_heartbeat/` en cada paso
   f. Mueve a `COMPLETADA` o `DENEGADA`

**Registrar en supervisor COMPONENTS + ONLOGON** (ver P4.1).

**Log propio**: `logs/orders.log` via `atlas_log.get_logger("orders")`

---

## FASE 2 — Dashboard v3 (A1, A2, A6)

### P2.1 `atlas_web/dashboard_v3.html` — cara visual

**Estructura**:
```
<body> (dark #0d1117, Segoe UI)
  ├── <canvas id="art-bg"> (algorithmic_art.js, 1 vez)
  ├── #hud (flex column, z-index alto, pointer-events none en bg)
  │   ├── #header (Atlas · heartbeat · reloj · status)
  │   ├── #main (flex row)
  │   │   ├── #radial-container (SVG o canvas, nodos radiales)
  │   │   │   ├── .node.module (Memoria, Tareas, Dinero, Foco, Salud, Noticias, Clima, Cerebro, Informes)
  │   │   │   ├── .node.adapter (Mercado, Noticias RSS, Clima API)
  │   │   │   └── center-pulse (heartbeat pulsatil)
  │   │   └── #sidebar (panel derecho, slide-in al clickear nodo)
  │   │       ├── .view-memoria (grafo force-directed con vis-network lite o D3 force)
  │   │       ├── .view-tareas (anillos C2 con progreso circular)
  │   │       ├── .view-dinero (sparklines canvas: BTC, S&P, bonds)
  │   │       ├── .view-noticias (tarjetas RSS con imagen si hay)
  │   │       ├── .view-clima (weather card con hourly chart)
  │   │       ├── .view-foco (barra productivo vs distracción)
  │   │       ├── .view-cerebro (orquestador: modelo activo + providers)
  │   │       ├── .view-informes (lista con links a /informe/*)
  │   │       ├── .view-salud (health checks: nombre + ok/fail + detail)
  │   │       └── .view-pendiente (escaladas + gates humanos)
  │   └── #order-bar (input [Escribe una orden...] + btn [Enviar])
  └── #status-bar (última actualización · server · poll info)
```

**Colores** (reutilizar de `dashboard.html`):
- `--green: #3fb950` · `--yellow: #d29922` · `--red: #f85149` · `--accent: #58a6ff` · `--muted: #8b949e`

**Nodos radiales** (A2):
- SVG namespace: nodos son `<circle>` + `<text>`
- Centro: heartbeat circle con `fill` = health_status color
- Anillo 1: módulos principales (~9 nodos, radio r1)
- Anillo 2: adaptadores (~3 nodos, radio r2)
- Cada nodo: `<circle>` coloreado por estado real (GET /api/live + /api/health)
- Click en nodo → abre `#sidebar` con `.view-*` correspondiente
- **TOPE**: 150 nodos → truncar con pausa si la UI está oculta

**Carga progresiva (A3)**:
1. Render inmediato: skeleton loaders (divs grises con shimmer)
2. 0-2s: fetch `/api/live` → actualiza nodos + sidebar
3. 2-10s: fetch datos lentos (`/api/mercado`, `/api/noticias`, `/api/clima`)
4. Nunca bloquea render; si un adaptador falla → badge "hace X min"

**Order bar (A4)**:
- Input + Enter → POST `/api/orden`
- Si respuesta `requires_confirmation=true` → muestra preview + [Ejecutar]
- Doble Enter en 2s → confirmación (2do Enter = click en [Ejecutar])

### P2.2 `atlas_web/algorithmic_art.js` — fondo estático

**UNA vez** al DOMContentLoaded:
```javascript
(function() {
  const canvas = document.getElementById('art-bg');
  const ctx = canvas.getContext('2d');
  canvas.width = window.innerWidth;
  canvas.height = window.innerHeight;
  // Dibujar puntos + líneas de conexión (simula grafo)
  // Colores: #161b22, #1f2630, acentos sutiles #58a6ff20
  // ~200 puntos, ~100 líneas, opacidad baja (0.05-0.15)
})();
```
No se re-ejecuta. Es decoración estática.

### P2.3 Pywebview face fullscreen (A1)

`atlas_ui_manager.py` abre la ventana fullscreen:
```python
import webview
from atlas_log import get_logger

log = get_logger("ui_manager")

class UiApi:
    def __init__(self):
        self._win = None
    def set_window(self, w):
        self._win = w
    def close(self):
        if self._win: self._win.destroy()
    def minimize(self):
        if self._win: self._win.minimize()
    def restore(self):
        if self._win: self._win.restore()

def main():
    config = json.loads(UI_CONFIG_PATH.read_text(encoding="utf-8"))
    if not config.get("UI_V3"):
        log.info("UI_V3=0 → usando dashboard v2 (fallback)")
        # Abrir dashboard.html en navegador o ventana simple
        return
    api = UiApi()
    win = webview.create_window(
        "Atlas Dashboard v3",
        "http://127.0.0.1:4100/",
        fullscreen=True,
        on_top=False,
        background_color="#0d1117",
        js_api=api,
    )
    api.set_window(win)
    # Guardar HWND para ui_manager
    def on_loaded():
        hwnd = int(win.native.Handle.ToInt64())
        config["HWND"] = hwnd
        UI_CONFIG_PATH.write_text(json.dumps(config, indent=2))
    win.events.loaded += on_loaded
    webview.start()
```

---

## FASE 3 — UX Árbitro (B1, B2, B3, B4)

### P3.1 `atlas_ui_manager.py` — gestor FULL↔EXEC

**Modos**:
- **FULL**: dashboard v3 en fullscreen (modo normal)
- **EXEC**: ventana minimizada a taskbar cuando hay tarea L1+ activa

**Flujo**:
1. Arranca con `UI_V3=1` → abre fullscreen
2. Al recibir señal de tarea L1+: `win.minimize()` → HWND guardado
3. Al tarea TERMINADA: `win.restore()` (defer 2s, sin robar foco si foreground es fullscreen de otro app)
4. Pin "mantener visible": override que impide minimize

**Señales** (recibe via `/api/ui_config` POST o lectura periódica de `ui_config.json`):
- `minimize_on_task=true` → minimiza
- `restore_on_complete=true` → restaura
- `pin_visible=true` → no minimiza

**Integración con supervisor** (ver P4.1).

### P3.2 `atlas_overlay.py` — overlay siempre-visible

**Configuración**:
- `on_top=True`, ancho=380px, alto=auto (~500-600px)
- Posición: esquina superior derecha
- `frameless=True`, `resizable=False`

**Contenido** (HTML inyectado vía OVERLAY_JS):
```
┌──────────────────────────────┐
│  Atlas · 🟢              [×] │
│  ● pulso heartbeat          │
│                              │
│  T-20260816-120000          │
│  verificando CR-2 · 45s ETA │
│  Última: ejecutando npm...  │
│                              │
│  ┌─ Permisos pendientes ───┐ │
│  │ L2+ requiere OK         │ │
│  │ [Permitir][Denegar][Ver]│ │
│  └─────────────────────────┘ │
│                              │
│  ▼ colapsar                  │
└──────────────────────────────┘
```

**Polling**: fetch `/api/live` cada 2s
**Fallback**: si `:4100` cae → "sin conexión" (nunca verde falso)
**Click** → abre ventana FULL (restaura `HWND` de `ui_config.json`)
**Colapsar** → oculta contenido, solo muestra header + pulso

**Registrar en supervisor** (ver P4.1).

### P3.3 Heartbeat por tarea (B3)

**Lectura en `/api/live`**:
```python
def _task_hearbeats():
    hb_dir = STATE_DIR / "task_heartbeat"
    tasks = []
    if hb_dir.exists():
        for f in hb_dir.glob("*.json"):
            try:
                hb = json.loads(f.read_text(encoding="utf-8"))
                age = (datetime.now() - datetime.fromisoformat(hb["last_beat"])).total_seconds()
                alive = hb.get("tokens_alive", False)
                pegado = age > 60 and not alive
                if age > 120 and not alive:
                    status = "red"
                elif age > 60 and not alive:
                    status = "yellow"
                else:
                    status = "green"
                tasks.append({**hb, "heartbeat_age_s": int(age), "heartbeat_status": status})
            except Exception:
                continue
    return tasks
```

**Botones** (cuando 🔴):
- **[Reintentar]** → re-inyectar pendientes C2 (vuelve a `turno_agente`)
- **[Ver]** → abre FULL con vista detallada de la tarea
- **[Escalar]** → `estado = ESCALADA`
- **[Pausar]** → pausa la tarea

### P3.4 Pegado/permiso-esperado → friction_log (B4)

```python
# En atlas_overlay.py o atlas_orders.py:
friction_write("espera", detail="permiso pendiente 45s", 
               meta={"task_id": "T-...", "type": "permission"})
friction_write("espera", detail="tarea pegada 120s sin respuesta",
               meta={"task_id": "T-..."})
```

---

## FASE 4 — Integración supervisor + tests

### P4.1 `atlas_supervisor.py` — COMPONENTS actualizado

```python
COMPONENTS = {
    # ... existentes (activity, web, orchestrator, controller)
    "overlay": {
        "cmd": [PYTHON, "atlas_overlay.py"],
        "cwd": ROOT,
        "log": "overlay.log",
        "health_name": "overlay",
        "onlogon": True,
    },
    "orders": {
        "cmd": [PYTHON, "atlas_orders.py"],
        "cwd": ROOT,
        "log": "orders.log",
        "health_name": "orders_drainger",
        "onlogon": True,
    },
    "ui_manager": {
        "cmd": [PYTHON, "atlas_ui_manager.py"],
        "cwd": ROOT,
        "log": "ui_manager.log",
        "health_name": "ui_manager",
        "onlogon": True,
    },
}
```

Cada componente nuevo:
- Tiene entrada en COMPONENTS
- Tiene `onlogon: True` → registrado en Task Scheduler
- Tiene log propio en `logs/<name>.log`
- Se verifica con health check (port open o proceso vivo)

**Tareas ONLOGON** (XML pattern igual a `atlas_eval.py:schedule()`):
```python
# Crear tareas AtlasOverlay, AtlasOrders, AtlasUIManager
# Trigger: ONLOGON
# Command: pythonw atlas_<nombre>.py
```

### P4.2 `tests/unit/test_dash_v3.py` — Tests del dashboard

| Test | Qué verifica |
|---|---|
| `test_adaptador_caido_cache_badge` | Adaptador caído → datos stale + badge "hace X min" |
| `test_api_mercado_ok` | GET /api/mercado → 200 con datos o stale=True |
| `test_api_noticias_ok` | GET /api/noticias → 200 con items o stale=True |
| `test_api_clima_ok` | GET /api/clima → 200 con temperature o stale=True |
| `test_api_grafo_tope_nodos` | GET /api/grafo → ≤150 nodos |
| `test_api_orden_idempotente` | POST /api/orden same text → order_id válido |
| `test_api_orden_preview_l2` | L2+ → preview con criterios + requires_confirmation=true |
| `test_api_live_estructura` | GET /api/live → health_status + tasks + timestamp |
| `test_ui_v3_rollback` | UI_V3=0 → sirve dashboard v2 (dashboard.html) |
| `test_algorithmic_art_una_vez` | Canvas se dibuja solo 1 vez (sin re-ejecución) |
| `test_order_bar_doble_enter` | Doble Enter en <2s = confirmación |
| `test_heartbeat_lee_task` | task_heartbeat/{id} → JSON válido |

### P4.3 `tests/unit/test_ui_arbitro.py` — Tests del árbitro

| Test | Qué verifica |
|---|---|
| `test_heartbeat_stale_yellow` | heartbeat age 60-120s sin tokens_alive → 🟡 |
| `test_heartbeat_stale_red` | heartbeat age >120s sin tokens_alive → 🔴 |
| `test_stream_vivo_no_pegado` | tokens_alive=true aunque age >60s → 🟢 |
| `test_permiso_timeout_deny` | confirmación sin respuesta 60s → DENY |
| `test_overlay_sin_4100` | :4100 caído → overlay "sin conexión" |
| `test_full_exec_full` | FULL → EXEC (minimiza) → FULL (restore) con mock |
| `test_overlay_permission_allow` | POST /api/confirmaciones allow=true → COMPLETADA |
| `test_overlay_permission_deny` | POST /api/confirmaciones allow=false → DENEGADA |
| `test_orders_drenador_l0` | order L0 → ejecuta sin contrato (fast-path) |
| `test_orders_drenador_l2_preview` | order L2 → genera preview + espera confirmación |
| `test_grafo_tope_150` | >150 nodos → trunca a 150 |
| `test_overlay_colapsable` | Click ▼ colapsa contenido, solo header |
| `test_ui_manager_hwnd_guardado` | Al abrir face → HWND en ui_config.json |
| `test_foco_stale_badge` | foco adaptador caído → stale=True |

---

## FASE 5 — Evidencia + cierre (§16)

### P5.1 Capturas (evidencia visual)
1. Cara fullscreen con 3 vistas ricas (Memoria, Tareas, Noticias)
2. Orden real ejecutada visible (L0 fast-path)
3. Overlay durante tarea minimizada
4. Pegado simulado (heartbeat stale → 🔴)
5. Permiso desde overlay ([Permitir] clicked)

### P5.2 `docs/verification/2026-08-16-dash-arbitro.md`

**Formato** (mismo que `2026-08-16-routing-liviano.md`):
```markdown
# DASH v3 + UX ÁRBITRO — Verificación §16

**Fecha:** 2026-08-16 · **Gate:** suite verde + evidencia + panel funcional

## 1. Dashboard v3
<tabla features, capturas>

## 2. Adaptadores
<stooq, CoinGecko, RSS, open-meteo, tabla stale badge>

## 3. Órdenes
<flujo POST /api/orden → C4 → fast-path/preview>

## 4. Overlay
<380px on_top, polling 2s, colapsable>

## 5. Heartbeat por tarea
<escritores, lectura, clasificación>

## 6. UI Manager
<FULL↔EXEC, HWND, restore>

## 7. Tests (N tests)
<tabla>

## 8. Evidencia
<capturas>

## 9. Evals E6-E8
<resultados>

## 10. Cierre
- [x] ...
**Gate: PASS**
```

### P5.3 Evals E6-E8 (atlas_eval.py)

Añadir al RUBRICA + CASES de `atlas_eval.py`:

| ID | Nombre | Target | Max |
|---|---|---|---|
| E6 | dashboard-live | `/api/live` → 200 con `health_status` + `tasks` | 2 |
| E7 | orden-l0 | `POST /api/orden` L0 → fast-path OK sin contrato | 2 |
| E8 | overlay-activo | `atlas_overlay.py` proceso vivo (PID o ui_config) | 2 |

```python
RUBRICA["E6"] = {"name": "dashboard-live", "target": "/api/live responde con health_status y tasks", "max": 2}
RUBRICA["E7"] = {"name": "orden-l0", "target": "POST /api/orden L0 ejecuta fast-path sin contrato", "max": 2}
RUBRICA["E8"] = {"name": "overlay-activo", "target": "atlas_overlay.py proceso vivo", "max": 2}

def run_case_e6():
    import urllib.request
    try:
        r = urllib.request.urlopen("http://127.0.0.1:4100/api/live", timeout=5)
        data = json.loads(r.read())
        if data.get("health_status") and "tasks" in data:
            return 2, ""
        return 1, f"live incompleto: {list(data.keys())}"
    except Exception as e:
        return 0, str(e)

def run_case_e7():
    import urllib.request
    try:
        req = urllib.request.Request("http://127.0.0.1:4100/api/orden",
            data=json.dumps({"texto": "abre el navegador"}).encode(),
            headers={"Content-Type": "application/json"})
        r = urllib.request.urlopen(req, timeout=15)
        data = json.loads(r.read())
        if data.get("ok") and data.get("preview", {}).get("nivel") == "L0":
            return 2, ""
        return 1, f"orden: {data}"
    except Exception as e:
        return 0, str(e)

def run_case_e8():
    import psutil
    for p in psutil.process_iter(['cmdline']):
        try:
            if p.info['cmdline'] and 'atlas_overlay.py' in ' '.join(p.info['cmdline']):
                return 2, ""
        except Exception:
            continue
    return 1, "overlay no encontrado"
```

---

## Orden de ejecución

| Fase | Dependencias | Tiempo estimado | Archivos tocados |
|---|---|---|---|
| P1 (infra) | Ninguna | 1h | `atlas_web_server.py` (nuevos endpoints), `ui_config.json`, dirs |
| P2 (dash v3) | P1 | 2h | `dashboard_v3.html`, `algorithmic_art.js`, `atlas_ui_manager.py` |
| P3 (árbitro) | P1, parcial P2 | 1.5h | `atlas_overlay.py`, `atlas_orders.py`, `atlas_controller.py` (hb) |
| P4 (tests) | P1-P3 | 1h | `test_dash_v3.py`, `test_ui_arbitro.py`, `atlas_supervisor.py` |
| P5 (evidencia) | P4 | 0.5h | `verification/2026-08-16-dash-arbitro.md`, `atlas_eval.py` (E6-E8) |

**Total estimado: ~6h**

---

## Reglas de implementación

1. **Atomic write**: temp + rename en todo inter-proceso (task_heartbeat, orders, confirmaciones, ui_config)
2. **Nunca JSON compartido concurrente**: si hay escritores paralelos → JSONL append-only
3. **Permiso sin respuesta en 60s** → default DENY
4. **CPU**: face <5% idle, overlay <1%, grafo tope 150 nodos + pausa si oculta
5. **Evidencia sobre opinión**: todo claim → evidencia (captura, test output, JSON)
6. **H-101**: no mentir, no cerrar sin evidencia real
7. **Suite sin regresión**: tests existentes no se rompen (correr suite completa antes/después)
8. **Rollback**: `UI_V3=0` en `ui_config.json` restaura dashboard v2
9. **Logs**: `atlas_log.get_logger()` en todos los nuevos módulos
10. **Errors**: `atlas_monitor.track_error()` en overlay + ui_manager
