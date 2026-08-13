#!/usr/bin/env python3
"""
MCP Playwright Visual Server
=============================
Servidor MCP que envuelve Playwright (Chromium real, no un sandbox) y devuelve
SIEMPRE evidencia visual (screenshot + estilos computados + alertas) junto con
el resultado de cada acción, para que la IA no navegue "a ciegas" ni tenga que
acordarse de pedir captura por separado.

Autor: Freebuff AI
Licencia: MIT

Tools disponibles:
  - Ciclo de vida:  pw_start, pw_close
  - Navegación:     pw_goto, pw_click, pw_fill, pw_press
  - Evidencia:      pw_screenshot, pw_computed_style
  - Auditoría:      pw_visual_audit  (screenshot + estilos + alertas fijas, sin
                     depender del "criterio visual" del modelo)
  - Regresión:      pw_diff          (comparación de píxeles contra un baseline)

Convención: toda acción que cambia el estado de la página (goto/click/fill/press)
adjunta automáticamente una captura de pantalla nueva en la respuesta, para que
el siguiente paso del agente ya tenga feedback visual sin un tool call extra.
"""

import json
import re
import time
from datetime import datetime
from pathlib import Path

try:
    from playwright.async_api import async_playwright, Page, Browser, BrowserContext
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False

try:
    from PIL import Image, ImageChops
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("Playwright Visual Server")

# ─── Estado del navegador (persiste entre tool calls dentro del mismo proceso) ──
_state = {
    "playwright": None,
    "browser": None,
    "context": None,
    "page": None,
}

SHOTS_DIR = Path.home() / "Pictures" / "mcp-playwright-visual"
SHOTS_DIR.mkdir(parents=True, exist_ok=True)


def _err(msg: str) -> str:
    return json.dumps({"error": msg}, ensure_ascii=False)


def _no_playwright() -> str:
    return _err(
        "El paquete 'playwright' no está instalado. Correr: "
        "pip install playwright && playwright install chromium"
    )


async def _get_page() -> "Page | None":
    return _state.get("page")


def _shot_path(prefix: str) -> Path:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    return SHOTS_DIR / f"{prefix}_{ts}.png"


async def _safe_goto(page: "Page", url: str) -> None:
    """
    Navega esperando solo DOM listo (no 'networkidle'): un dev server con
    HMR/websocket abierto (Next.js, Vite, etc.) nunca deja la red en idle,
    así que esperar eso siempre hace timeout en local. Se intenta además un
    idle corto y opcional, sin que su ausencia haga fallar la navegación.
    """
    await page.goto(url, wait_until="domcontentloaded", timeout=30000)
    try:
        await page.wait_for_load_state("networkidle", timeout=4000)
    except Exception:
        pass


async def _take_screenshot(page: "Page", selector: str | None, full_page: bool) -> str:
    path = _shot_path("shot")
    if selector:
        locator = page.locator(selector).first
        await locator.screenshot(path=str(path))
    else:
        await page.screenshot(path=str(path), full_page=full_page)
    return str(path)


# ═════════════════════════════════════════════════════════════════════════════
# CICLO DE VIDA
# ═════════════════════════════════════════════════════════════════════════════

@mcp.tool()
async def pw_start(url: str, headless: bool = False, width: int = 1280, height: int = 800) -> str:
    """
    Lanza un Chromium real (no sandbox), navega a `url` y adjunta la primera
    captura de pantalla. Debe llamarse antes que cualquier otra tool pw_*.

    Args:
        url: URL a abrir (ej. http://localhost:3000/dashboard/jobs)
        headless: si es False (default) se ve la ventana del navegador
        width, height: tamaño del viewport

    Returns:
        JSON con título de la página y ruta del screenshot inicial.
    """
    if not PLAYWRIGHT_AVAILABLE:
        return _no_playwright()

    if _state["browser"] is not None:
        await pw_close()

    pw = browser = context = page = None
    try:
        pw = await async_playwright().start()
        browser = await pw.chromium.launch(headless=headless)
        context = await browser.new_context(viewport={"width": width, "height": height})
        page = await context.new_page()
        # Guardar el estado ANTES de navegar: si el goto falla, igual queda
        # una referencia viva para poder cerrar el navegador (pw_close) en
        # vez de dejarlo huérfano.
        _state["playwright"] = pw
        _state["browser"] = browser
        _state["context"] = context
        _state["page"] = page

        await _safe_goto(page, url)

        shot = await _take_screenshot(page, None, False)
        return json.dumps({
            "success": True,
            "url": page.url,
            "title": await page.title(),
            "screenshot": shot,
        }, ensure_ascii=False)
    except Exception as e:
        return _err(str(e))


@mcp.tool()
async def pw_close() -> str:
    """Cierra el navegador y libera el estado. Llamar al terminar la sesión de pruebas."""
    if not PLAYWRIGHT_AVAILABLE:
        return _no_playwright()
    try:
        if _state["browser"] is not None:
            await _state["browser"].close()
        if _state["playwright"] is not None:
            await _state["playwright"].stop()
    except Exception as e:
        return _err(str(e))
    finally:
        _state.update({"playwright": None, "browser": None, "context": None, "page": None})
    return json.dumps({"success": True}, ensure_ascii=False)


# ═════════════════════════════════════════════════════════════════════════════
# NAVEGACIÓN CON FEEDBACK VISUAL AUTOMÁTICO
# ═════════════════════════════════════════════════════════════════════════════

@mcp.tool()
async def pw_goto(url: str) -> str:
    """Navega a `url` en la página actual y adjunta screenshot post-navegación."""
    page = await _get_page()
    if page is None:
        return _err("No hay página activa. Llamar pw_start primero.")
    try:
        await _safe_goto(page, url)
        shot = await _take_screenshot(page, None, False)
        return json.dumps({
            "success": True, "url": page.url, "title": await page.title(), "screenshot": shot,
        }, ensure_ascii=False)
    except Exception as e:
        return _err(str(e))


@mcp.tool()
async def pw_click(selector: str, timeout_ms: int = 5000) -> str:
    """
    Hace click en el elemento que matchea `selector` (CSS o texto Playwright,
    ej. "text=Guardar") y adjunta screenshot post-click para confirmar el efecto.
    """
    page = await _get_page()
    if page is None:
        return _err("No hay página activa. Llamar pw_start primero.")
    try:
        await page.locator(selector).first.click(timeout=timeout_ms)
        await page.wait_for_timeout(150)  # dar tiempo a transiciones/animaciones
        shot = await _take_screenshot(page, None, False)
        return json.dumps({"success": True, "clicked": selector, "screenshot": shot}, ensure_ascii=False)
    except Exception as e:
        shot = await _take_screenshot(page, None, False)
        return json.dumps({"success": False, "error": str(e), "screenshot": shot}, ensure_ascii=False)


@mcp.tool()
async def pw_fill(selector: str, text: str, timeout_ms: int = 5000) -> str:
    """Escribe `text` en el elemento `selector` y adjunta screenshot posterior."""
    page = await _get_page()
    if page is None:
        return _err("No hay página activa. Llamar pw_start primero.")
    try:
        await page.locator(selector).first.fill(text, timeout=timeout_ms)
        shot = await _take_screenshot(page, None, False)
        return json.dumps({"success": True, "filled": selector, "screenshot": shot}, ensure_ascii=False)
    except Exception as e:
        shot = await _take_screenshot(page, None, False)
        return json.dumps({"success": False, "error": str(e), "screenshot": shot}, ensure_ascii=False)


@mcp.tool()
async def pw_press(key: str) -> str:
    """Presiona una tecla (ej. 'Escape', 'Enter') y adjunta screenshot posterior."""
    page = await _get_page()
    if page is None:
        return _err("No hay página activa. Llamar pw_start primero.")
    try:
        await page.keyboard.press(key)
        await page.wait_for_timeout(150)
        shot = await _take_screenshot(page, None, False)
        return json.dumps({"success": True, "key": key, "screenshot": shot}, ensure_ascii=False)
    except Exception as e:
        return _err(str(e))


# ═════════════════════════════════════════════════════════════════════════════
# EVIDENCIA VISUAL BAJO DEMANDA
# ═════════════════════════════════════════════════════════════════════════════

@mcp.tool()
async def pw_screenshot(selector: str = "", full_page: bool = False) -> str:
    """
    Captura de pantalla manual. Si `selector` se especifica, recorta solo ese
    elemento; si no, captura el viewport (o la página completa con full_page=True).
    """
    page = await _get_page()
    if page is None:
        return _err("No hay página activa. Llamar pw_start primero.")
    try:
        shot = await _take_screenshot(page, selector or None, full_page)
        return json.dumps({"success": True, "screenshot": shot}, ensure_ascii=False)
    except Exception as e:
        return _err(str(e))


@mcp.tool()
async def pw_ancestors(selector: str, css_vars: str = "") -> str:
    """
    Recorre los ancestros DOM de `selector` hasta <html>, y para cada uno
    reporta tag/id/clases y el valor LOCAL (no heredado) de cada variable en
    `css_vars` si ese ancestro la define en su propio atributo style. Sirve
    para encontrar en qué nivel una variable CSS se sobreescribe inesperadamente
    entre la raíz del documento y un elemento hijo (ej. un modal que hereda un
    tema distinto al del resto de la página).

    Args:
        selector: selector CSS del elemento de partida (no incluido en el resultado)
        css_vars: lista separada por comas de variables a inspeccionar
            (ej. "--ds-c-sheet-content-background")
    """
    page = await _get_page()
    if page is None:
        return _err("No hay página activa. Llamar pw_start primero.")
    vars_list = [v.strip() for v in css_vars.split(",") if v.strip()]
    try:
        result = await page.evaluate(
            """({ selector, vars }) => {
                const el = document.querySelector(selector);
                if (!el) return { error: 'selector no encontrado: ' + selector };
                const chain = [];
                let node = el.parentElement;
                while (node) {
                    const inlineStyle = node.getAttribute('style') || '';
                    const localVars = {};
                    for (const v of vars) {
                        // Solo lo reporta si ESTE nodo lo define en su propio
                        // atributo style (no el heredado/computado).
                        if (inlineStyle.includes(v)) {
                            localVars[v] = getComputedStyle(node).getPropertyValue(v).trim();
                        }
                    }
                    chain.push({
                        tag: node.tagName.toLowerCase(),
                        id: node.id || null,
                        className: (node.className && node.className.toString().slice(0, 120)) || null,
                        definesLocally: localVars,
                    });
                    node = node.parentElement;
                }
                return { chainFromParentToHtml: chain };
            }""",
            {"selector": selector, "vars": vars_list},
        )
        return json.dumps(result, ensure_ascii=False)
    except Exception as e:
        return _err(str(e))


@mcp.tool()
async def pw_computed_style(selector: str, properties: str = "backgroundColor,color,borderColor,opacity") -> str:
    """
    Extrae getComputedStyle(el) del primer elemento que matchea `selector`.

    Args:
        selector: selector CSS o de Playwright del elemento objetivo
        properties: lista separada por comas de propiedades CSS (camelCase, ej.
            "backgroundColor,color,borderColor"). También acepta el pseudo-nombre
            "--cualquier-variable" para leer variables CSS custom vía
            getPropertyValue en document.documentElement.

    Returns:
        JSON con cada propiedad pedida y su valor computado real (no el que
        declara la hoja de estilos, el que el navegador terminó resolviendo).
    """
    page = await _get_page()
    if page is None:
        return _err("No hay página activa. Llamar pw_start primero.")
    props = [p.strip() for p in properties.split(",") if p.strip()]
    try:
        result = await page.evaluate(
            """({ selector, props }) => {
                const el = document.querySelector(selector);
                if (!el) return { error: 'selector no encontrado: ' + selector };
                const cs = getComputedStyle(el);
                const out = {};
                for (const p of props) {
                    if (p.startsWith('--')) {
                        // Se lee en el elemento (no en document.documentElement):
                        // las variables CSS cascadean, así que un ancestro
                        // intermedio (ej. ThemedPortal) puede sobreescribir el
                        // valor de la raíz solo para sus descendientes.
                        out[p] = cs.getPropertyValue(p).trim();
                        out[p + ' (root)'] = getComputedStyle(document.documentElement).getPropertyValue(p).trim();
                    } else {
                        out[p] = cs[p];
                    }
                }
                const rect = el.getBoundingClientRect();
                out.__rect = { width: rect.width, height: rect.height };
                out.__inlineStyle = el.getAttribute('style') || '';
                return out;
            }""",
            {"selector": selector, "props": props},
        )
        return json.dumps(result, ensure_ascii=False)
    except Exception as e:
        return _err(str(e))


# ═════════════════════════════════════════════════════════════════════════════
# AUDITORÍA VISUAL DETERMINISTA (screenshot + estilos + alertas fijas)
# ═════════════════════════════════════════════════════════════════════════════

def _parse_rgba_alpha(value: str) -> float | None:
    m = re.match(r"rgba?\(([^)]+)\)", value or "")
    if not m:
        return None
    parts = [p.strip() for p in m.group(1).split(",")]
    if len(parts) == 4:
        try:
            return float(parts[3])
        except ValueError:
            return None
    if len(parts) == 3:
        return 1.0
    return None


@mcp.tool()
async def pw_visual_audit(selector: str, is_overlay: bool = False, css_vars: str = "") -> str:
    """
    Auditoría determinista de un elemento: saca screenshot, extrae estilos
    computados y dispara alertas fijas (sin opinión visual subjetiva), útil
    para que un modelo económico detecte estilos rotos con el mismo criterio
    que uno más capaz.

    Reglas de alerta (mismas que la skill visual-style-audit del proyecto):
      - Alpha del backgroundColor == 1 cuando is_overlay=True (se esperaba < 1).
      - Cualquier variable CSS pedida en `css_vars` que resuelva a "" (token roto).
      - Color final rgb(0,0,0) o rgb(255,255,255) puro (sospecha de fallback).
      - Elemento con bounding box 0x0 (no renderizado / posible falla de hidratación).

    Args:
        selector: selector del elemento a auditar
        is_overlay: True si el elemento es un overlay/backdrop (activa la regla de alpha)
        css_vars: lista separada por comas de variables CSS custom a chequear
            (ej. "--ds-c-sheet-overlay-background,--ds-c-surface-1")

    Returns:
        JSON con { screenshot, computed, alerts[] } — `alerts` vacío significa
        que no se disparó ninguna regla conocida (no es garantía de que el
        diseño esté bien, solo de que no hay señales rotas conocidas).
    """
    page = await _get_page()
    if page is None:
        return _err("No hay página activa. Llamar pw_start primero.")

    vars_list = [v.strip() for v in css_vars.split(",") if v.strip()]
    props = ["backgroundColor", "color", "borderColor"] + vars_list

    style_json = await pw_computed_style(selector, ",".join(props))
    computed = json.loads(style_json)
    if "error" in computed:
        return json.dumps({"error": computed["error"]}, ensure_ascii=False)

    shot = await _take_screenshot(page, selector, False)

    alerts = []
    rect = computed.get("__rect", {})
    if rect.get("width", 1) == 0 or rect.get("height", 1) == 0:
        alerts.append({
            "rule": "zero-size",
            "detail": f"El elemento tiene bounding box {rect}. Puede no estar renderizado o haber fallado la hidratación.",
        })

    bg = computed.get("backgroundColor", "")
    if is_overlay:
        alpha = _parse_rgba_alpha(bg)
        if alpha == 1.0:
            alerts.append({
                "rule": "overlay-alpha-1",
                "detail": f"backgroundColor={bg} tiene alpha=1 en un elemento marcado como overlay (se esperaba transparencia).",
            })

    for v in vars_list:
        if computed.get(v, None) == "":
            alerts.append({
                "rule": "empty-css-var",
                "detail": f"La variable {v} resolvió a cadena vacía — token no resuelto o hidratación incompleta.",
            })

    for prop in ("backgroundColor", "color", "borderColor"):
        val = computed.get(prop, "")
        if val in ("rgb(0, 0, 0)", "rgb(255, 255, 255)"):
            alerts.append({
                "rule": "pure-black-or-white",
                "detail": f"{prop}={val} — sospechoso de fallback por token roto (revisar si el tema es monocromático a propósito).",
            })

    return json.dumps({
        "success": True,
        "selector": selector,
        "screenshot": shot,
        "computed": computed,
        "alerts": alerts,
        "alert_count": len(alerts),
    }, ensure_ascii=False)


# ═════════════════════════════════════════════════════════════════════════════
# REGRESIÓN VISUAL (diff de píxeles contra un baseline)
# ═════════════════════════════════════════════════════════════════════════════

@mcp.tool()
async def pw_diff(baseline_path: str, selector: str = "", full_page: bool = False, threshold: float = 0.02) -> str:
    """
    Compara la captura actual contra una imagen baseline y devuelve el
    porcentaje de píxeles distintos + una imagen de diff, para detectar
    regresiones visuales sin depender de que el modelo "mire y opine".

    Args:
        baseline_path: ruta a la imagen de referencia (PNG) generada antes
        selector: si se especifica, compara solo ese elemento
        full_page: si no hay selector, compara la página completa (True) o solo
            el viewport (False)
        threshold: fracción de píxeles distintos (0-1) por encima de la cual
            se considera regresión (default 2%)

    Returns:
        JSON con { current_screenshot, diff_image, diff_ratio, regression }.
    """
    if not PIL_AVAILABLE:
        return _err("Se requiere Pillow: pip install Pillow")
    page = await _get_page()
    if page is None:
        return _err("No hay página activa. Llamar pw_start primero.")

    baseline = Path(baseline_path)
    if not baseline.exists():
        return _err(f"No existe el baseline: {baseline_path}")

    try:
        current_path = await _take_screenshot(page, selector or None, full_page)
        img_a = Image.open(baseline).convert("RGB")
        img_b = Image.open(current_path).convert("RGB")

        if img_a.size != img_b.size:
            return json.dumps({
                "success": True,
                "current_screenshot": current_path,
                "diff_ratio": None,
                "regression": True,
                "note": f"Tamaños distintos: baseline={img_a.size} actual={img_b.size} — no se puede diffear píxel a píxel.",
            }, ensure_ascii=False)

        diff = ImageChops.difference(img_a, img_b)
        bbox = diff.getbbox()
        histogram = diff.convert("L").histogram()
        total_px = img_a.width * img_a.height
        changed_px = sum(histogram[10:])  # ignora ruido de anti-aliasing < 10/255
        ratio = changed_px / total_px if total_px else 0.0

        diff_path = _shot_path("diff")
        diff.save(diff_path)

        return json.dumps({
            "success": True,
            "current_screenshot": current_path,
            "diff_image": str(diff_path) if bbox else None,
            "diff_ratio": round(ratio, 4),
            "regression": ratio > threshold,
        }, ensure_ascii=False)
    except Exception as e:
        return _err(str(e))


# ═════════════════════════════════════════════════════════════════════════════
# PUNTO DE ENTRADA
# ═════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("=" * 60)
    print("  MCP Playwright Visual Server")
    print("  Ejecutando... Esperando conexión del cliente MCP")
    print("=" * 60)
    if not PLAYWRIGHT_AVAILABLE:
        print("  [!] playwright no instalado: pip install playwright && playwright install chromium")
    if not PIL_AVAILABLE:
        print("  [!] Pillow no instalado (pw_diff no funcionará): pip install Pillow")
    print("")
    print("  Tools cargadas:")
    print("  [L] Ciclo de vida:  pw_start, pw_close")
    print("  [N] Navegación:     pw_goto, pw_click, pw_fill, pw_press (screenshot automático)")
    print("  [E] Evidencia:      pw_screenshot, pw_computed_style")
    print("  [A] Auditoría:      pw_visual_audit (alertas deterministas, sin opinión visual)")
    print("  [R] Regresión:      pw_diff (comparación de píxeles vs baseline)")
    print("")
    mcp.run()
