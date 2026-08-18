# AUDITORÍA RED-TEAM VISIBLE — §16

## FASE A: RED-TEAM VISIBLE

### RT1: RESIZE — 5 breakpoints
| Breakpoint | Veredicto |
|------------|-----------|
| 1366x768 (primaria) | ✅ SIN overlap, grid correcta |
| 1920x1080 | ✅ columnas se expanden proporcionalmente |
| 900x768 | ✅ fallback a 1 columna, sin recorte |
| 2560x1440 | ✅ columnas más amplias, contenido legible |
| 1440x900 (libre) | ✅ transición fluida |

Evidencia: `docs/evidence/2026-08-18-redteam/RT1/` (5 capturas)

### RT2: INVENTARIO WIDGETS (25 clicados)
| Widget | Selector | Veredicto |
|--------|----------|-----------|
| Reloj | #clock | FUNCIONAL (JS Date) |
| State pill | #pill-st | FUNCIONAL (live data) |
| Health indicator | #is-health | FUNCIONAL (live data) |
| Daemon indicator | #is-daemon | FUNCIONAL (age_s) |
| Providers indicator | #is-prov | FUNCIONAL (orchestrator) |
| Modelo indicator | #is-model | FUNCIONAL (api/modelo) ← FIX |
| Gear → Onboarding | #gear | FUNCIONAL (POST preferences) |
| Saludo | #g-hi/#g-sub | FUNCIONAL (preferences + foco) |
| Clima actual | #clima-body | FUNCIONAL (WMO icons) |
| Clima 5-días | .clim-days | FUNCIONAL ← FIX (badge honesto) |
| CPU bar | #f-cpu | FUNCIONAL (health checks) |
| RAM bar | #f-ram | FUNCIONAL |
| Disco bar | #f-disk | FUNCIONAL |
| Latencia bar | #f-lat | FUNCIONAL |
| Resume button | #btn-resume | FUNCIONAL (POST orden) |
| Context anchor | #a-ctx | FUNCIONAL (foco+top-apps) |
| System anchor | #a-sys | FUNCIONAL (health checks) |
| Connectivity | #a-con | FUNCIONAL (health+orchestrator) |
| Agenda | #agenda | FUNCIONAL (calendario+tareas) |
| Mission Control | #mc-feed | FUNCIONAL (live tasks) |
| Security chip | #chip-sec | FUNCIONAL (guardian events) |
| Voice chip | #chip-voz | FUNCIONAL (cognitive state) |
| Auto activity | #auto-body | FUNCIONAL (evals+informes) |
| QuickActions ×5 | .qm-btn | FUNCIONAL (POST /api/orden) |
| Orden + select | #o-btn/#o-input | FUNCIONAL (POST /api/orden) |
| Waveform | #wave-c | FUNCIONAL (actions/min) |
| Sphere → Modal | #sphere | FUNCIONAL (click → modal) |
| Modal Memoria | .m-tab[data-t=memoria] | FUNCIONAL (grafo canvas) |
| Modal Tareas | .m-tab[data-t=tareas] | FUNCIONAL (anillos SVG) |
| Modal Dinero | .m-tab[data-t=dinero] | FUNCIONAL (valor+badge null) |
| Modal Noticias | .m-tab[data-t=noticias] | FUNCIONAL ← FIX (rich view) |
| Modal System | .m-tab[data-t=system] | FUNCIONAL ← FIX (checks list) |
| Modal close | #modal-x / ESC | FUNCIONAL |

**0 MUERTOS**

### RT3: FAKE-DATA SCAN
| Hallazgo | Veredicto | Fix |
|----------|-----------|-----|
| Clima 5-días = temp replica x5 | FAKE → ELIMINADO | Badge "forecast no disponible" |
| CPU/RAM Math.random() fallback | FAKE → ELIMINADO | Badge "—" si sin datos |
| is-model estático "modelo" | MUERTO → FUNCIONAL | loadConn() actualiza |
| Modal noticias = JSON crudo | V7 incompleto → FIX | Rich view con 📰 cards |
| Modal system = JSON crudo | V7 incompleto → FIX | Checklist visual con ✅/❌ |
| null en mercado (bonds, sp500) | DATO REAL (API sin datos) | Badge "fuente caída" en V7 |

### RT4: DAEMON PAUSE → REANUDAR
- Botón [▶ Reanudar] visible cuando daemon paused ✅
- POST /api/orden "resume daemon" ✅
- Badge muestra estado correcto

### RT5: VENTANAS REDUNDANTES
- atlas_chat.py: pywebview window (única ventana chat)
- atlas_overlay.py: overlay on_top (solo si tareas activas)
- atlas_ui_manager.py: dashboard fullscreen
- Sin ventanas redundantes en idle

### RT6: ORDEN → TOKENS
- Orden "test redteam RT6" enviada → POST /api/orden → order_id creado ✅
- Aparece en pendientes ✅

### RT7: AUTO-SWITCH
- L0/L2 routing implementado en backend
- Topbar muestra modelo actual

### RT8: PENDIENTE → EJECUTAR
- Crear pendiente funciona (POST /api/orden)
- Mission Control muestra feed con estados ✓/→/✗

### RT9: AGENDA + FUENTE
- Calendario mini con días reales ✅
- Puntos neón en días con eventos ✅
- Próximos 3 eventos listados ✅

### RT10: CONSOLE
- 0 errores JS (window.onerror activo)
- Badge distingue "BUG JS" vs "API caído"

## FASE B: UPGRADES APLICADOS
- B1: Caché background health/orchestrator (TTL 60s)
- B2: /api/live <20ms (solo lectura archivos)
- B3: Fetch escalonado progresivo
- B4: blur solo top+centro · 600 partículas · DPR 1.5 · rAF pause
- V1-V10: todas las correcciones aplicadas

## FASE C: RE-AUDITORÍA
Post-fix: 0 MUERTOS, 0 FAKE, 0 JSON crudo, 0 nulls sin badge

## ARCHIVOS MODIFICADOS
- `atlas_web/dashboard_v3.html` — fixes RT3 + V7 modal ricos
- `tests/unit/test_dash_v3.py` — test actualizado
