# FIX — Pestañas Fantasma + Dashboard Lento §16

## Resumen Ejecutivo
Se identificó y corrigió el loop infinito de pestañas fantasma (5 puntos de `webbrowser.open`) y se optimizó el rendimiento del dashboard (caché background, fetch paralelo, blur reducido, partículas ≤600).

## Bloque A: PESTAÑAS FANTASMA

### A1: Loop identificado
- **atlas_chat.py:526** — fallback webbrowser cuando pywebview falla
- **atlas_overlay.py:97** — fallback HWND no encontrado
- **atlas_overlay.py:244** — fallback webview
- **atlas_ui_manager.py:150** — fallback UI_V3=0
- **atlas_ui_manager.py:176** — fallback webview
- **Causa raíz**: supervisor reinicia componente → fallo webview → abre tab → repite

### A2: Solución
- Eliminados 5 `webbrowser.open()` reemplazados por `log.error()` con tag A2-fix
- Añadido rate-limiter en supervisor: max 3 reinicios/hora/componente
- Backoff exponencial: `cooldown = max(2, restart_count * 2)` minutos

### A3: Cooldown chat
- Añadido `_check_cooldown()` / `_set_cooldown()` en atlas_chat.py
- Cooldown de 5 min tras reinicio exitoso
- Si chat cae y supervisor lo reinicia, cooldown evita reinicio inmediato

## Bloque B: LENTITUD

### B1: Caché background
- Thread daemon `_bg_refresh()` refresca health/orchestrator cada 60s
- `/api/health`: de **4770ms → 1ms** (caché)
- `/api/orchestrator`: de timeout → **2ms** (caché)
- Requests NUNCA bloquean en chequeo de providers

### B2: /api/live optimizado
- Eliminado `_call_attr("atlas_health", "health_report")` del request
- Usa caché `_BG_CACHE["health"]` en vez de llamada síncrona
- **15ms** (target <50ms) ✅

### B3: Frontend progresivo
- Arranque escalonado: 0ms → 50ms → 150ms → 300ms → 500ms
- Fetch en paralelo (XHR non-blocking, sin await secuencial)
- Render progresivo: crítico primero, gadgets después

### B4: Perf visual
- **blur(14px)** solo en topbar + centro (2 paneles, no 9)
- Left/right/bottom: `background: rgba()` sin backdrop-filter
- **Partículas**: de 1200 → **600** (50% reducción)
- **DPR cap**: `Math.min(devicePixelRatio, 1.5)` en esfera + waveform
- **rAF pausa**: `if(document.hidden) return` en waveAni()

## Tests (14/14 PASS)
Todos los tests de `test_dash_v3.py` pasan sin regresión.

## Evidencia
- 📸 `docs/evidence/2026-08-18-fix-tabs-perf/1366x768.png` — dashboard optimizado
- Console 0 errores (visual_audit alerts=0)
- Timing: /api/live 15ms, /api/health 1ms (cached), /api/orchestrator 2ms (cached)

## Archivos modificados
- `atlas_web_server.py` — caché background + handlers optimizados
- `atlas_web/dashboard_v3.html` — blur reducido, particles 600, DPR 1.5, fetch progresivo
- `atlas_chat.py` — eliminado webbrowser fallback, añadido cooldown
- `atlas_overlay.py` — eliminados 2 webbrowser.open
- `atlas_ui_manager.py` — eliminados 2 webbrowser.open
- `atlas_supervisor.py` — rate-limiter max 3 reinicios/hora

## Gate
**VIS-001**: pendiente aprobación visual del usuario.
