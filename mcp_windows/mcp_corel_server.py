#!/usr/bin/env python3
"""
MCP CorelDRAW Automation Server
================================
Servidor MCP para controlar CorelDRAW (v25 verificado) via COM automation.

API verificada empíricamente contra CorelDRAW Graphics Suite 2024 (v25.0):
  - Late binding (Dispatch dinámico) — gencache falla con coercion de tipos
  - Texto: shape.Text.Story.Font = "Impact" (string), .Size (pt), .Bold (bool)
  - Relleno: shape.Fill.UniformColor.RGBAssign(r, g, b)
  - Tamaño página: doc.ActivePage.SetSize(w, h)  (SetPageDimensions NO existe)
  - Export: doc.ExportBitmap con los 16 parámetros posicionales
            (los 2 últimos son objetos → pasar None explícitamente)
  - Coordenadas: origen en ESQUINA INFERIOR IZQUIERDA, unidades del doc (mm)

Tools POD Suite (E:\Macros_Corel):
  corel_run_vba_macro ejecuta cualquier macro instalada via GMSManager.
"""

import json
import sys
from pathlib import Path

try:
    import pythoncom
    import win32com.client
    WIN32COM_AVAILABLE = True
except ImportError:
    WIN32COM_AVAILABLE = False

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("CorelDRAW Automation Server")

# ── Constantes COM verificadas en CorelDRAW v25 ──────────────────────────────
CDR_UNIT = {"mm": 3, "in": 1}          # cdrMillimeter=3, cdrInch=1
CDR_FILTER = {"png": 802, "jpg": 774, "tiff": 287, "bmp": 2}
CDR_RGB = 4                             # cdrRGBColorImage
CDR_CMYK = 5                            # cdrCMYKColorImage
CDR_CURRENT_PAGE = 1
CDR_SELECTION = 2
CDR_NORMAL_AA = 1                       # cdrNormalAntiAliasing

# ── Conexión COM (singleton con reconexión) ──────────────────────────────────
_corel_app = None


def _get_app():
    """Obtiene (o crea) la conexión con CorelDRAW. Reconecta si se perdió."""
    global _corel_app
    if not WIN32COM_AVAILABLE:
        raise RuntimeError("pywin32 no instalado: pip install pywin32")
    pythoncom.CoInitialize()
    if _corel_app is None:
        _corel_app = win32com.client.Dispatch("CorelDRAW.Application")
        try:
            _corel_app.Visible = True
        except Exception:
            pass
    else:
        # Verificar que la conexión sigue viva
        try:
            _ = _corel_app.VersionMajor
        except Exception:
            _corel_app = win32com.client.Dispatch("CorelDRAW.Application")
            try:
                _corel_app.Visible = True
            except Exception:
                pass
    return _corel_app


def _get_doc(require: bool = True):
    """Documento activo. Error claro si no hay ninguno abierto."""
    app = _get_app()
    doc = app.ActiveDocument
    if doc is None and require:
        raise RuntimeError("No hay documento abierto. Usa corel_create_document primero.")
    return doc


def _hex_to_rgb(color_hex: str) -> tuple:
    """'#FF5500' → (255, 85, 0)"""
    h = color_hex.lstrip("#")
    return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))


def _err(e: Exception) -> str:
    return json.dumps({"error": str(e)}, ensure_ascii=False)


def _get_shape(index: int):
    """Shape por indice (1-based) en la capa activa. Error claro si no existe."""
    doc = _get_doc()
    layer = doc.ActiveLayer
    if index < 1 or index > layer.Shapes.Count:
        raise RuntimeError(
            f"Indice de shape invalido: {index} "
            f"(hay {layer.Shapes.Count} shapes en la capa activa, usa corel_list_objects)")
    return layer.Shapes.Item(index)


def _build_shape_range(indices: list):
    """Construye un ShapeRange COM a partir de indices (para group/align/etc)."""
    app = _get_app()
    doc = _get_doc()
    layer = doc.ActiveLayer
    rng = app.CreateShapeRange()
    for idx in indices:
        rng.Add(_get_shape(idx))
    return rng


# ═════════════════════════════════════════════════════════════════════════════
# 1. DOCUMENTOS
# ═════════════════════════════════════════════════════════════════════════════

@mcp.tool()
def corel_ping() -> str:
    """Verifica conexión con CorelDRAW y devuelve la versión instalada."""
    try:
        app = _get_app()
        return json.dumps({
            "success": True,
            "version": f"{app.VersionMajor}.{app.VersionMinor}",
            "documents_open": app.Documents.Count,
        }, ensure_ascii=False)
    except Exception as e:
        return _err(e)


@mcp.tool()
def corel_create_document(name: str = "Diseño", width: float = 210,
                          height: float = 297, units: str = "mm") -> str:
    """
    Crea un documento nuevo en CorelDRAW.

    Args:
        name: Nombre del documento
        width: Ancho (default 210 = A4 vertical en mm)
        height: Alto (default 297)
        units: "mm" o "in"
    """
    try:
        app = _get_app()
        doc = app.CreateDocument()
        doc.Unit = CDR_UNIT.get(units, 3)
        doc.ActivePage.SetSize(width, height)
        doc.Name = name
        return json.dumps({
            "success": True, "name": name,
            "width": width, "height": height, "units": units,
        }, ensure_ascii=False)
    except Exception as e:
        return _err(e)


@mcp.tool()
def corel_open_document(file_path: str) -> str:
    """Abre un archivo .cdr existente."""
    try:
        p = Path(file_path).expanduser().resolve()
        if not p.exists():
            return json.dumps({"error": f"No existe: {file_path}"})
        app = _get_app()
        doc = app.OpenDocument(str(p))
        return json.dumps({"success": True, "name": doc.Name, "path": str(p)},
                          ensure_ascii=False)
    except Exception as e:
        return _err(e)


@mcp.tool()
def corel_save_document(file_path: str = "") -> str:
    """
    Guarda el documento activo.

    Args:
        file_path: Ruta .cdr destino. Vacío = guardar en la ubicación actual.
    """
    try:
        doc = _get_doc()
        if file_path:
            app = _get_app()
            p = Path(file_path).expanduser().resolve()
            p.parent.mkdir(parents=True, exist_ok=True)
            # BUG real (verificado via type-lib): SaveAs exige un objeto
            # SaveAsOptions COM por referencia como 2do parametro — pasar solo
            # el path tronaba con "The Python instance can not be converted to
            # a COM object". El objeto se crea con app.CreateStructSaveAsOptions().
            opts = app.CreateStructSaveAsOptions()
            opts.Overwrite = True
            doc.SaveAs(str(p), opts)
            return json.dumps({"success": True, "path": str(p)}, ensure_ascii=False)
        doc.Save()
        return json.dumps({"success": True, "action": "saved_in_place"},
                          ensure_ascii=False)
    except Exception as e:
        return _err(e)


@mcp.tool()
def corel_close_document(save: bool = True) -> str:
    """Cierra el documento activo."""
    try:
        doc = _get_doc()
        name = doc.Name
        if save:
            doc.Save()
        doc.Close()
        return json.dumps({"success": True, "closed": name, "saved": save},
                          ensure_ascii=False)
    except Exception as e:
        return _err(e)


@mcp.tool()
def corel_get_document_info() -> str:
    """Información del documento activo: nombre, tamaño, páginas, capas, objetos."""
    try:
        doc = _get_doc()
        page = doc.ActivePage
        layers = []
        for i in range(1, page.Layers.Count + 1):
            layer = page.Layers.Item(i)
            layers.append({"name": layer.Name, "shapes": layer.Shapes.Count})
        return json.dumps({
            "name": doc.Name,
            "file": f"{doc.FilePath}{doc.FileName}" if doc.FileName else "",
            "pages": doc.Pages.Count,
            "page_width": round(page.SizeWidth, 2),
            "page_height": round(page.SizeHeight, 2),
            "layers": layers,
        }, ensure_ascii=False, indent=2)
    except Exception as e:
        return _err(e)


@mcp.tool()
def corel_create_layer(name: str) -> str:
    """
    Crea una capa nueva (con nombre) en la pagina activa y la deja como capa activa.
    Util para aislar cada elemento/efecto de una composicion compleja sin pelear con
    el reordenamiento dinamico de indices de shapes en una sola capa compartida.
    """
    try:
        doc = _get_doc()
        page = doc.ActivePage
        layer = page.CreateLayer(name)
        layer.Activate()
        return json.dumps({"success": True, "name": layer.Name}, ensure_ascii=False)
    except Exception as e:
        return _err(e)


@mcp.tool()
def corel_select_layer(name: str) -> str:
    """Activa (selecciona) una capa existente por nombre exacto."""
    try:
        doc = _get_doc()
        page = doc.ActivePage
        layer = page.Layers.Item(name)
        layer.Activate()
        return json.dumps({"success": True, "active_layer": doc.ActiveLayer.Name},
                          ensure_ascii=False)
    except Exception as e:
        return _err(e)


@mcp.tool()
def corel_list_layers() -> str:
    """Lista las capas de la pagina activa, con su nombre y cantidad de shapes."""
    try:
        doc = _get_doc()
        page = doc.ActivePage
        layers = []
        for i in range(1, page.Layers.Count + 1):
            layer = page.Layers.Item(i)
            layers.append({"index": i, "name": layer.Name,
                           "shapes": layer.Shapes.Count,
                           "active": layer.Name == doc.ActiveLayer.Name})
        return json.dumps({"count": len(layers), "layers": layers},
                          ensure_ascii=False, indent=2)
    except Exception as e:
        return _err(e)


# ═════════════════════════════════════════════════════════════════════════════
# 2. OBJETOS (texto, formas)
# ═════════════════════════════════════════════════════════════════════════════

@mcp.tool()
def corel_add_text(text: str, x: float = 0, y: float = 0,
                   font_name: str = "Arial", font_size: float = 24,
                   color_hex: str = "#000000", bold: bool = False,
                   italic: bool = False) -> str:
    """
    Crea texto artístico en el documento activo.

    Args:
        text: Contenido del texto
        x: Posición X en unidades del doc (mm) desde la izquierda
        y: Posición Y desde el BORDE INFERIOR (origen abajo-izquierda)
        font_name: Fuente instalada (ej: "Arial", "Impact", "Arial Black")
        font_size: Tamaño en puntos
        color_hex: Color de relleno "#FF0000"
        bold: Negrita
        italic: Cursiva
    """
    try:
        doc = _get_doc()
        shape = doc.ActiveLayer.CreateArtisticText(x, y, text)
        story = shape.Text.Story
        story.Font = font_name
        story.Size = font_size
        if bold:
            story.Bold = True
        if italic:
            story.Italic = True
        r, g, b = _hex_to_rgb(color_hex)
        shape.Fill.UniformColor.RGBAssign(r, g, b)
        return json.dumps({
            "success": True, "text": text, "font": font_name,
            "size_pt": font_size, "color": color_hex,
        }, ensure_ascii=False)
    except Exception as e:
        return _err(e)


@mcp.tool()
def corel_add_rectangle(x: float, y: float, width: float, height: float,
                        fill_hex: str = "#1a5276", outline_width: float = 0,
                        outline_hex: str = "#000000") -> str:
    """
    Crea un rectángulo (útil para fondos y bloques de color).

    Args:
        x: Esquina izquierda (unidades del doc)
        y: Esquina INFERIOR (origen abajo-izquierda)
        width: Ancho
        height: Alto
        fill_hex: Color de relleno
        outline_width: Grosor de contorno (0 = sin contorno)
        outline_hex: Color del contorno
    """
    try:
        doc = _get_doc()
        shape = doc.ActiveLayer.CreateRectangle2(x, y, width, height)
        r, g, b = _hex_to_rgb(fill_hex)
        shape.Fill.UniformColor.RGBAssign(r, g, b)
        if outline_width > 0:
            shape.Outline.Width = outline_width
            ro, go, bo = _hex_to_rgb(outline_hex)
            shape.Outline.Color.RGBAssign(ro, go, bo)
        else:
            shape.Outline.SetNoOutline()
        return json.dumps({"success": True, "shape": "rectangle",
                           "size": [width, height]}, ensure_ascii=False)
    except Exception as e:
        return _err(e)


@mcp.tool()
def corel_add_ellipse(x: float, y: float, width: float, height: float,
                      fill_hex: str = "#e67e22") -> str:
    """Crea una elipse o círculo (width=height para círculo)."""
    try:
        doc = _get_doc()
        # BUG real (verificado via type-lib): CreateEllipse2 NO toma
        # (x, y, width, height) como CreateRectangle2 — toma
        # (CenterX, CenterY, RadiusX, RadiusY). Sin esta conversion el
        # shape sale con el doble de tamaño y desplazado.
        cx = x + width / 2
        cy = y + height / 2
        rx = width / 2
        ry = height / 2
        shape = doc.ActiveLayer.CreateEllipse2(cx, cy, rx, ry)
        r, g, b = _hex_to_rgb(fill_hex)
        shape.Fill.UniformColor.RGBAssign(r, g, b)
        return json.dumps({"success": True, "shape": "ellipse"},
                          ensure_ascii=False)
    except Exception as e:
        return _err(e)


@mcp.tool()
def corel_list_objects() -> str:
    """Lista los objetos de la capa activa del documento."""
    try:
        doc = _get_doc()
        shapes = []
        for i in range(1, doc.ActiveLayer.Shapes.Count + 1):
            sh = doc.ActiveLayer.Shapes.Item(i)
            shapes.append({
                "index": i,
                "name": sh.Name,
                "type": str(sh.Type),
                "x": round(sh.PositionX, 2),
                "y": round(sh.PositionY, 2),
                "width": round(sh.SizeWidth, 2),
                "height": round(sh.SizeHeight, 2),
            })
        return json.dumps({"count": len(shapes), "shapes": shapes},
                          ensure_ascii=False, indent=2)
    except Exception as e:
        return _err(e)


@mcp.tool()
def corel_select_all() -> str:
    """Selecciona todos los objetos de la página activa."""
    try:
        app = _get_app()
        doc = _get_doc()
        doc.ActivePage.Shapes.All().CreateSelection()
        return json.dumps({"success": True,
                           "selected": app.ActiveSelectionRange.Count},
                          ensure_ascii=False)
    except Exception as e:
        return _err(e)


@mcp.tool()
def corel_delete_selection() -> str:
    """Elimina los objetos seleccionados."""
    try:
        app = _get_app()
        _get_doc()
        count = app.ActiveSelectionRange.Count
        app.ActiveSelectionRange.Delete()
        return json.dumps({"success": True, "deleted": count}, ensure_ascii=False)
    except Exception as e:
        return _err(e)


@mcp.tool()
def corel_convert_to_curves() -> str:
    """
    Convierte los textos seleccionados a curvas (preprensa POD).
    Esencial antes de exportar para impresión.
    """
    try:
        app = _get_app()
        _get_doc()
        converted = 0
        for i in range(1, app.ActiveSelectionRange.Count + 1):
            shape = app.ActiveSelectionRange.Shapes.Item(i)
            try:
                shape.ConvertToCurves()
                converted += 1
            except Exception:
                pass  # No es texto, se omite
        return json.dumps({"success": True, "converted": converted},
                          ensure_ascii=False)
    except Exception as e:
        return _err(e)


@mcp.tool()
def corel_center_on_page() -> str:
    """Centra la selección en la página (horizontal y vertical)."""
    try:
        app = _get_app()
        doc = _get_doc()
        sel = app.ActiveSelectionRange
        if sel.Count == 0:
            return json.dumps({"error": "No hay nada seleccionado"})
        page = doc.ActivePage
        new_x = (page.SizeWidth - sel.SizeWidth) / 2
        new_y = (page.SizeHeight - sel.SizeHeight) / 2
        sel.PositionX = new_x
        sel.PositionY = new_y
        return json.dumps({"success": True, "x": round(new_x, 2),
                           "y": round(new_y, 2)}, ensure_ascii=False)
    except Exception as e:
        return _err(e)


# ═════════════════════════════════════════════════════════════════════════════
# 3. CURVAS Y RELLENOS AVANZADOS (Capa 1: diseño real, no solo primitivas)
# ═════════════════════════════════════════════════════════════════════════════

@mcp.tool()
def corel_add_curve(points: list, closed: bool = False,
                    fill_hex: str = "", stroke_hex: str = "#000000",
                    stroke_width: float = 0.5) -> str:
    """
    Crea una forma a partir de una lista de segmentos — rectos y/o curvas Bezier
    cubicas — lo que permite tanto iconos geometricos duros como formas organicas
    suaves (hojas, petalos, letras a mano, lineas fluidas abstractas).

    Args:
        points: Lista de segmentos. El primero es el punto de inicio [x, y].
            Cada segmento siguiente puede ser:
            - [x, y] (2 valores) -> linea recta hasta (x, y)
            - [x, y, cp1x, cp1y, cp2x, cp2y] (6 valores) -> curva Bezier cubica
              hasta (x, y), con cp1/cp2 como puntos de control ABSOLUTOS (no
              relativos). Se puede mezclar libremente lineas y curvas en la
              misma forma.
            Ej: [[0,0], [50,50], [100,0,60,40,90,10]] (linea + curva)
        closed: True cierra la forma en poligono (puede rellenarse), False = linea abierta
        fill_hex: Color de relleno si closed=True (vacio = sin relleno)
        stroke_hex: Color de la linea/contorno
        stroke_width: Grosor de linea (0 = sin contorno)
    """
    try:
        if len(points) < 2:
            return json.dumps({"error": "Se necesitan al menos 2 puntos"})
        doc = _get_doc()
        # BUG real (verificado via type-lib): Layer.CreateCurve(Source) exige
        # un objeto Curve YA CONSTRUIDO como argumento — no crea uno vacio sin
        # args (eso lanza "Numero de parametros no valido"). El objeto Curve
        # standalone se arma con doc.CreateCurve() (app.CreateCurve() tambien
        # existe pero pide un Document por referencia, no sirve aqui).
        curve = doc.CreateCurve()
        x0, y0 = points[0][0], points[0][1]
        subpath = curve.CreateSubPath(x0, y0)
        for seg in points[1:]:
            if len(seg) == 2:
                subpath.AppendLineSegment(seg[0], seg[1])
            elif len(seg) == 6:
                # AppendCurveSegment2(x, y, cp1x, cp1y, cp2x, cp2y) — verificado
                # via type-lib: puntos de control ABSOLUTOS (no la variante
                # AppendCurveSegment sin sufijo, que usa longitud+angulo polar).
                subpath.AppendCurveSegment2(seg[0], seg[1], seg[2], seg[3], seg[4], seg[5])
            else:
                return json.dumps({"error": f"Segmento invalido (debe ser 2 o 6 valores): {seg}"})
        if closed:
            subpath.Closed = True
        shape = doc.ActiveLayer.CreateCurve(curve)
        if closed and fill_hex:
            r, g, b = _hex_to_rgb(fill_hex)
            shape.Fill.UniformColor.RGBAssign(r, g, b)
        else:
            shape.Fill.SetNoFill()
        if stroke_width > 0:
            shape.Outline.Width = stroke_width
            rs, gs, bs = _hex_to_rgb(stroke_hex)
            shape.Outline.Color.RGBAssign(rs, gs, bs)
        else:
            shape.Outline.SetNoOutline()
        return json.dumps({"success": True, "shape": "curve",
                           "shape_index": doc.ActiveLayer.Shapes.Count,
                           "points": len(points), "closed": closed},
                          ensure_ascii=False)
    except Exception as e:
        return _err(e)


@mcp.tool()
def corel_set_fill_gradient(shape_index: int, color_start_hex: str = "",
                            color_end_hex: str = "", angle: float = 0,
                            fill_type: str = "linear", stops: list = None,
                            opacity: int = 0) -> str:
    """
    Aplica un degradado (fountain fill) a un shape existente. Soporta el caso
    simple de 2 colores (start/end) o un degradado multi-color via 'stops'.

    Args:
        shape_index: Indice del shape (ver corel_list_objects)
        color_start_hex: Color inicial del degradado (ignorado si se pasa 'stops')
        color_end_hex: Color final del degradado (ignorado si se pasa 'stops')
        angle: Angulo en grados (0 = izquierda a derecha)
        fill_type: "linear", "radial", "conical" o "square"
        stops: Opcional. Lista de [posicion_0_a_100, color_hex] para degradados
               de mas de 2 colores (arcoiris, atardeceres). Debe incluir 0 y 100
               como minimo, ej: [[0,"#FF0000"],[50,"#FFFF00"],[100,"#0000FF"]].
               Si se pasa, color_start_hex/color_end_hex se ignoran.
        opacity: 0-100, transparencia uniforme aplicada sobre todo el degradado
                 (0 = opaco/sin cambio, 100 = totalmente transparente)
    """
    try:
        app = _get_app()
        shape = _get_shape(shape_index)
        # BUG real (verificado via type-lib): ApplyFountainFill exige EXACTAMENTE
        # 10 parametros posicionales — (StartColor, EndColor, Type, Angle, Steps,
        # EdgePad, MidPoint, BlendType, CenterOffsetX, CenterOffsetY) — no los 4
        # que tenia el codigo original. StartColor/EndColor deben ser objetos
        # Color COM (via app.CreateRGBColor), no floats/ints — pasar primitivos
        # ahi es lo que producia "The Python instance can not be converted to a
        # COM object". Type va de 1 a 4 (no 0-3) y EdgePad debe estar en 0-49.
        type_map = {"linear": 1, "radial": 2, "conical": 3, "square": 4}
        ft = type_map.get(fill_type, 1)

        sorted_stops = sorted(stops, key=lambda s: s[0]) if stops else None
        if sorted_stops:
            r1, g1, b1 = _hex_to_rgb(sorted_stops[0][1])
            r2, g2, b2 = _hex_to_rgb(sorted_stops[-1][1])
        else:
            r1, g1, b1 = _hex_to_rgb(color_start_hex)
            r2, g2, b2 = _hex_to_rgb(color_end_hex)
        start_color = app.CreateRGBColor(r1, g1, b1)
        end_color = app.CreateRGBColor(r2, g2, b2)
        shape.Fill.ApplyFountainFill(start_color, end_color, ft, angle, 256,
                                     0, 0, 0, 0.0, 0.0)

        if sorted_stops and len(sorted_stops) > 2:
            # BUG real (verificado via type-lib): Fill.Fountain.Colors.Add(Color,
            # Position) — Position es entero 0-100 (no float 0-1), y la coleccion
            # es 0-INDEXADA (a diferencia de casi todo lo demas en esta API, que
            # es 1-indexado) — Colors.Item(1) lanza "Index fuera de rango" con
            # solo 2 stops porque los indices validos son 0 y 1.
            colors = shape.Fill.Fountain.Colors
            for pos, color_hex in sorted_stops[1:-1]:
                r, g, b = _hex_to_rgb(color_hex)
                colors.Add(app.CreateRGBColor(r, g, b), int(round(pos)))

        if opacity > 0:
            shape.Transparency.ApplyUniformTransparency(opacity)

        return json.dumps({"success": True, "shape_index": shape_index,
                           "gradient": fill_type, "opacity": opacity,
                           "stops": len(sorted_stops) if sorted_stops else 2},
                          ensure_ascii=False)
    except Exception as e:
        return _err(e)


@mcp.tool()
def corel_set_fill_solid(shape_index: int, color_hex: str = "", opacity: int = 0,
                         pattern_bitmap_path: str = "") -> str:
    """
    Cambia el relleno de un shape existente a un color solido, o a una textura
    de bitmap repetible (pattern fill) si se pasa pattern_bitmap_path.

    Args:
        shape_index: Indice del shape
        color_hex: Color de relleno solido (ignorado si se pasa pattern_bitmap_path)
        opacity: 0-100, transparencia uniforme (0 = opaco/sin cambio, 100 =
                 totalmente transparente). Verificado empiricamente: la escala
                 de Shape.Transparency.ApplyUniformTransparency va de 0 a 100,
                 no 0-255.
        pattern_bitmap_path: Opcional. Ruta a un PNG/JPG existente — lo aplica
                 como relleno de patron/textura repetible dentro del shape
                 (verificado: Fill.ApplyPatternFill acepta la ruta como string
                 plano, no requiere un objeto Image COM). Util para texturas
                 tipo grunge/papel/ruido dentro de un icono o letra.
    """
    try:
        shape = _get_shape(shape_index)
        if pattern_bitmap_path:
            p = Path(pattern_bitmap_path).expanduser().resolve()
            if not p.exists():
                return json.dumps({"error": f"No existe: {pattern_bitmap_path}"})
            app = _get_app()
            c1 = app.CreateRGBColor(0, 0, 0)
            c2 = app.CreateRGBColor(255, 255, 255)
            # Type=2 = bitmap pattern (verificado visualmente); FrontColor/
            # EndColor solo aplican a patrones vectoriales de 2 colores, se
            # ignoran para bitmap pero el metodo los exige igual.
            shape.Fill.ApplyPatternFill(2, str(p), 1, c1, c2, False)
        elif color_hex:
            r, g, b = _hex_to_rgb(color_hex)
            shape.Fill.UniformColor.RGBAssign(r, g, b)
        if opacity > 0:
            shape.Transparency.ApplyUniformTransparency(opacity)
        return json.dumps({"success": True, "shape_index": shape_index,
                           "color": color_hex, "opacity": opacity,
                           "pattern": bool(pattern_bitmap_path)}, ensure_ascii=False)
    except Exception as e:
        return _err(e)


@mcp.tool()
def corel_set_stroke(shape_index: int, color_hex: str = "#000000",
                     width: float = 0.5, none: bool = False) -> str:
    """
    Ajusta el contorno (outline/stroke) de un shape existente.

    Args:
        shape_index: Indice del shape
        color_hex: Color del contorno
        width: Grosor del contorno
        none: True = quita el contorno por completo
    """
    try:
        shape = _get_shape(shape_index)
        if none:
            shape.Outline.SetNoOutline()
            return json.dumps({"success": True, "shape_index": shape_index,
                               "outline": "none"}, ensure_ascii=False)
        shape.Outline.Width = width
        r, g, b = _hex_to_rgb(color_hex)
        shape.Outline.Color.RGBAssign(r, g, b)
        return json.dumps({"success": True, "shape_index": shape_index,
                           "color": color_hex, "width": width},
                          ensure_ascii=False)
    except Exception as e:
        return _err(e)


# ═════════════════════════════════════════════════════════════════════════════
# 4. COMPOSICIÓN Y TRANSFORMACIÓN (Capa 2: precisión y estructura)
# ═════════════════════════════════════════════════════════════════════════════

@mcp.tool()
def corel_select_shapes(indices: list) -> str:
    """
    Selecciona shapes especificos por indice (ver corel_list_objects).
    Necesario antes de operaciones que dependen de la seleccion activa
    en la UI (ej: corel_convert_to_curves, corel_center_on_page).

    Args:
        indices: Lista de indices, ej: [1, 3, 4]
    """
    try:
        rng = _build_shape_range(indices)
        rng.CreateSelection()
        return json.dumps({"success": True, "selected": len(indices)},
                          ensure_ascii=False)
    except Exception as e:
        return _err(e)


@mcp.tool()
def corel_align_objects(indices: list, alignment: str) -> str:
    """
    Alinea varios shapes entre si (clave para que un diseño se vea "limpio"
    y no descuadrado). Origen del doc: esquina inferior izquierda.

    Args:
        indices: Lista de indices de shapes a alinear (minimo 2)
        alignment: "left", "right", "center_h", "top", "bottom", "center_v"
    """
    try:
        if len(indices) < 2:
            return json.dumps({"error": "Se necesitan al menos 2 shapes"})
        doc = _get_doc()
        layer = doc.ActiveLayer
        shapes = [layer.Shapes.Item(i) for i in indices]

        if alignment == "left":
            target = min(s.PositionX for s in shapes)
            for s in shapes:
                s.PositionX = target
        elif alignment == "right":
            target = max(s.PositionX + s.SizeWidth for s in shapes)
            for s in shapes:
                s.PositionX = target - s.SizeWidth
        elif alignment == "center_h":
            centers = [s.PositionX + s.SizeWidth / 2 for s in shapes]
            target = sum(centers) / len(centers)
            for s in shapes:
                s.PositionX = target - s.SizeWidth / 2
        elif alignment == "top":
            target = max(s.PositionY + s.SizeHeight for s in shapes)
            for s in shapes:
                s.PositionY = target - s.SizeHeight
        elif alignment == "bottom":
            target = min(s.PositionY for s in shapes)
            for s in shapes:
                s.PositionY = target
        elif alignment == "center_v":
            centers = [s.PositionY + s.SizeHeight / 2 for s in shapes]
            target = sum(centers) / len(centers)
            for s in shapes:
                s.PositionY = target - s.SizeHeight / 2
        else:
            return json.dumps({"error": f"Alineacion invalida: {alignment}"})

        return json.dumps({"success": True, "aligned": len(indices),
                           "alignment": alignment}, ensure_ascii=False)
    except Exception as e:
        return _err(e)


@mcp.tool()
def corel_distribute_objects(indices: list, direction: str = "horizontal") -> str:
    """
    Distribuye espaciado uniforme entre varios shapes.

    Args:
        indices: Lista de indices de shapes (minimo 3 para que tenga efecto)
        direction: "horizontal" o "vertical"
    """
    try:
        if len(indices) < 3:
            return json.dumps({"error": "Se necesitan al menos 3 shapes"})
        doc = _get_doc()
        layer = doc.ActiveLayer
        shapes = [layer.Shapes.Item(i) for i in indices]

        if direction == "horizontal":
            shapes.sort(key=lambda s: s.PositionX)
            left = shapes[0].PositionX
            right = shapes[-1].PositionX + shapes[-1].SizeWidth
            total = sum(s.SizeWidth for s in shapes)
            gap = (right - left - total) / (len(shapes) - 1)
            x = left
            for s in shapes:
                s.PositionX = x
                x += s.SizeWidth + gap
        elif direction == "vertical":
            shapes.sort(key=lambda s: s.PositionY)
            bottom = shapes[0].PositionY
            top = shapes[-1].PositionY + shapes[-1].SizeHeight
            total = sum(s.SizeHeight for s in shapes)
            gap = (top - bottom - total) / (len(shapes) - 1)
            y = bottom
            for s in shapes:
                s.PositionY = y
                y += s.SizeHeight + gap
        else:
            return json.dumps({"error": f"Direccion invalida: {direction}"})

        return json.dumps({"success": True, "distributed": len(indices),
                           "direction": direction}, ensure_ascii=False)
    except Exception as e:
        return _err(e)


@mcp.tool()
def corel_duplicate_shape(shape_index: int, offset_x: float = 10,
                          offset_y: float = 0) -> str:
    """
    Duplica un shape con un desplazamiento (patrones, simetria, series).

    Args:
        shape_index: Indice del shape a duplicar
        offset_x: Desplazamiento horizontal del duplicado
        offset_y: Desplazamiento vertical del duplicado
    """
    try:
        shape = _get_shape(shape_index)
        shape.Duplicate(offset_x, offset_y)
        doc = _get_doc()
        new_index = doc.ActiveLayer.Shapes.Count
        return json.dumps({"success": True, "new_shape_index": new_index,
                           "offset": [offset_x, offset_y]},
                          ensure_ascii=False)
    except Exception as e:
        return _err(e)


@mcp.tool()
def corel_transform_shape(shape_index: int, rotate_deg: float = 0,
                          scale_x: float = 1.0, scale_y: float = 1.0,
                          flip_h: bool = False, flip_v: bool = False,
                          skew_x_deg: float = 0, skew_y_deg: float = 0) -> str:
    """
    Rota, escala, refleja o inclina (skew) un shape existente.

    Args:
        shape_index: Indice del shape
        rotate_deg: Grados a rotar
        scale_x: Factor de escala horizontal (1.0 = sin cambio)
        scale_y: Factor de escala vertical (1.0 = sin cambio)
        flip_h: Reflejar horizontalmente (espejo)
        flip_v: Reflejar verticalmente
        skew_x_deg: Inclinacion horizontal en grados (shear) — verificado:
                    Shape.Skew(AngleX, AngleY), 2 argumentos simples
        skew_y_deg: Inclinacion vertical en grados (shear)
    """
    try:
        shape = _get_shape(shape_index)
        if rotate_deg != 0:
            shape.Rotate(rotate_deg)
        if scale_x != 1.0 or scale_y != 1.0:
            shape.SizeWidth = shape.SizeWidth * scale_x
            shape.SizeHeight = shape.SizeHeight * scale_y
        if flip_h:
            shape.Flip(1)
        if flip_v:
            shape.Flip(2)
        if skew_x_deg != 0 or skew_y_deg != 0:
            shape.Skew(skew_x_deg, skew_y_deg)
        return json.dumps({"success": True, "shape_index": shape_index,
                           "rotate_deg": rotate_deg,
                           "scale": [scale_x, scale_y],
                           "flip": [flip_h, flip_v],
                           "skew": [skew_x_deg, skew_y_deg]}, ensure_ascii=False)
    except Exception as e:
        return _err(e)


@mcp.tool()
def corel_boolean_operation(shape_index_1: int, shape_index_2: int = 0,
                            operation: str = "union",
                            direction: str = "outside", steps: int = 3,
                            offset: float = 3.0, color_hex: str = "#ffffff",
                            color2_hex: str = "", offset_x: float = 3.0,
                            offset_y: float = -3.0, opacity: int = 60,
                            feather: float = 15.0, depth: float = 30.0,
                            bevel_only: bool = False, bevel_depth: float = 3.0,
                            bevel_angle: float = 45.0, lens_type: int = 1,
                            rate: float = 50.0, amplitude: float = 5.0,
                            frequency: int = 10, twist_angle: float = 90.0) -> str:
    """
    Combina/transforma shapes: operaciones booleanas clasicas, composicion
    (powerclip) y efectos avanzados (Contour/DropShadow/Blend/Extrude+Bevel/
    Lens/Distort). Todo consolidado en una sola tool para evitar que el
    cliente MCP tenga que redescubrir tools nuevas (los nombres de metodo
    COM reales son Create*, no Apply*, verificados empiricamente).

    Args:
        shape_index_1: Shape base ("union"/"subtract"/"intersect"), CONTENIDO
                       para "powerclip", o el UNICO shape para los efectos
                       (contour/drop_shadow/extrude/lens/distort_*)
        shape_index_2: Shape 2, CONTENEDOR para "powerclip", o el shape
                       objetivo para "blend" (no usado en el resto)
        operation: "union", "subtract", "intersect", "powerclip" (mete
            shape_index_1 dentro del contorno de shape_index_2, centrado),
            "contour", "drop_shadow", "blend", "extrude", "lens",
            "distort_pushpull", "distort_zipper", "distort_twister"

        --- parametros especificos por efecto (ignorados si no aplican) ---
        contour: direction ("outside"=halo hacia afuera/glow economico,
            "inside"=anillos hacia adentro), steps, offset (distancia entre
            anillos), color_hex (color final), color2_hex (color intermedio
            opcional, si vacio usa color_hex)
        drop_shadow: offset_x, offset_y, opacity (0-100), feather (difuminado),
            color_hex (color de la sombra)
        blend: steps (pasos intermedios), shape_index_2 (obligatorio)
        extrude: depth, color_hex (color base), color2_hex (color de
            sombreado, si vacio usa color_hex), bevel_only (True = solo
            relieve/emboss sin extrusion visible), bevel_depth, bevel_angle
        lens: lens_type (entero 1-7 — mapeo exacto de cada tipo NO confirmado
            empiricamente, verificar visualmente con corel_screenshot_canvas;
            el shape con lens debe estar delante en z-order de lo que se
            quiere ver a traves), rate (intensidad), color_hex (color base)
        distort_pushpull / distort_zipper / distort_twister: amplitude
            (intensidad, pushpull y zipper), frequency (solo zipper),
            twist_angle (solo twister). El origen se calcula automaticamente
            en el centro de shape_index_1.
    """
    try:
        doc = _get_doc()
        app = _get_app()
        layer = doc.ActiveLayer
        shape1 = layer.Shapes.Item(shape_index_1)

        if operation in ("union", "subtract", "intersect", "powerclip"):
            shape2 = layer.Shapes.Item(shape_index_2)
            if operation == "union":
                shape1.Weld(shape2)
            elif operation == "subtract":
                shape1.Trim(shape2)
            elif operation == "intersect":
                shape1.Intersect(shape2)
            elif operation == "powerclip":
                # BUG real (verificado via type-lib + prueba visual): el metodo
                # es Shape.AddToPowerClip(ContainerShape, CenterInContainer) y
                # se llama sobre el CONTENIDO, pasando el CONTENEDOR como
                # argumento — al reves de lo intuitivo. Se probo primero
                # container.AddToPowerClip(content) y NO recorto nada (el
                # contenido se veia completo, sin mascara); invertido a
                # content.AddToPowerClip(container) si recorta correctamente.
                shape1.AddToPowerClip(shape2, True)

        elif operation == "contour":
            # BUG real (verificado via type-lib + prueba visual): el metodo es
            # Shape.CreateContour(Direction, Offset, Steps, BlendType,
            # OutlineColor, FillColor, FillColor2, SpacingAccel, ColorAccel,
            # EndCapType, CornerType, MiterLimit) — 12 params, TODOS
            # obligatorios (los "defaults" del type-lib no son usables via
            # dynamic dispatch, igual que en ApplyFountainFill). Direction=1
            # confirmado visualmente como "outside", 2 como "inside".
            dir_map = {"outside": 1, "inside": 2}
            d = dir_map.get(direction, 1)
            r1, g1, b1 = _hex_to_rgb(color_hex)
            r2, g2, b2 = _hex_to_rgb(color2_hex) if color2_hex else (r1, g1, b1)
            outline_c = app.CreateRGBColor(0, 0, 0)
            fill_c = app.CreateRGBColor(r1, g1, b1)
            fill_c2 = app.CreateRGBColor(r2, g2, b2)
            shape1.CreateContour(d, offset, steps, 0, outline_c, fill_c, fill_c2,
                                 0, 0, 2, 4, 0.0)

        elif operation == "drop_shadow":
            r, g, b = _hex_to_rgb(color_hex)
            shadow_c = app.CreateRGBColor(r, g, b)
            # Shape.CreateDropShadow(Type, Opacity, Feather, OffsetX, OffsetY,
            # Color, FeatherType, FeatherEdge, PerspectiveAngle,
            # PerspectiveStretch, Fade, MergeMode) — verificado, produce
            # sombra suave difuminada correctamente con estos valores base.
            shape1.CreateDropShadow(0, opacity, feather, offset_x, offset_y,
                                    shadow_c, 4, 0, -45.0, 1.0, 1, 0)

        elif operation == "blend":
            if not shape_index_2:
                return json.dumps({"error": "shape_index_2 requerido para 'blend'"})
            target = layer.Shapes.Item(shape_index_2)
            # Shape.CreateBlend(Shape, Steps, ColorBlendType, Mode, Spacing,
            # Angle, Loop, Path, RotateShapes, SpacingAccel, ColorAccel,
            # AccelSize) — cuelga de Shape (no de Application), a diferencia
            # de lo que sugeriria el patron de CreateCurve.
            shape1.CreateBlend(target, steps, 0, 0, 0.0, 0.0, False, None,
                               False, 0, 0, 0)

        elif operation == "extrude":
            r1, g1, b1 = _hex_to_rgb(color_hex)
            r2, g2, b2 = _hex_to_rgb(color2_hex) if color2_hex else (r1, g1, b1)
            base_c = app.CreateRGBColor(r1, g1, b1)
            shade_c = app.CreateRGBColor(r2, g2, b2)
            bevel_c = app.CreateRGBColor(255, 255, 255)
            # No existe un efecto "Bevel" standalone en esta version de la API
            # — el bisel/relieve solo se expone como parte de CreateExtrude
            # (BevelDepth/BevelAngle/BevelColor/BevelOnly). bevel_only=True da
            # el look de relieve/emboss sin extrusion 3D visible.
            shape1.CreateExtrude(0, 0, 0, 0, depth, 1, base_c, shade_c,
                                 bevel_depth, bevel_angle, bevel_c, bevel_only)

        elif operation == "lens":
            r, g, b = _hex_to_rgb(color_hex)
            # BUG real: Color1/Color2 deben ser objetos Color COM reales — pasar
            # None (aunque el type-lib marque el arg como "opcional con default
            # None") lanza un TypeError de coercion en vez de usar un default.
            c1 = app.CreateRGBColor(r, g, b)
            c2 = app.CreateRGBColor(r, g, b)
            shape1.CreateLens(lens_type, rate, c1, c2, 0)

        elif operation in ("distort_pushpull", "distort_zipper", "distort_twister"):
            cx = shape1.PositionX + shape1.SizeWidth / 2
            cy = shape1.PositionY + shape1.SizeHeight / 2
            if operation == "distort_pushpull":
                shape1.CreatePushPullDistortion(cx, cy, amplitude)
            elif operation == "distort_zipper":
                shape1.CreateZipperDistortion(cx, cy, amplitude, frequency,
                                              False, False, False)
            else:
                shape1.CreateTwisterDistortion(cx, cy, twist_angle)
        else:
            return json.dumps({"error": f"Operacion invalida: {operation}"})

        new_index = doc.ActiveLayer.Shapes.Count
        return json.dumps({"success": True, "operation": operation,
                           "result_shape_index": new_index},
                          ensure_ascii=False)
    except Exception as e:
        return _err(e)


@mcp.tool()
def corel_group_shapes(indices: list) -> str:
    """Agrupa varios shapes en un solo grupo (moverlos/escalarlos como unidad)."""
    try:
        rng = _build_shape_range(indices)
        rng.Group()
        doc = _get_doc()
        new_index = doc.ActiveLayer.Shapes.Count
        return json.dumps({"success": True, "grouped": len(indices),
                           "group_shape_index": new_index},
                          ensure_ascii=False)
    except Exception as e:
        return _err(e)


@mcp.tool()
def corel_ungroup_shape(shape_index: int) -> str:
    """Desagrupa un shape agrupado previamente."""
    try:
        shape = _get_shape(shape_index)
        shape.Ungroup()
        return json.dumps({"success": True, "ungrouped": shape_index},
                          ensure_ascii=False)
    except Exception as e:
        return _err(e)


@mcp.tool()
def corel_set_z_order(shape_index: int, order: str = "front",
                      reference_shape_index: int = 0) -> str:
    """
    Cambia el orden de apilado (que va adelante/atras) de un shape.

    Args:
        shape_index: Indice del shape
        order: "front", "back", "forward" (un paso), "backward" (un paso) - pila global.
               "before" o "after" (requiere reference_shape_index) - coloca shape_index
               justo detras/delante de OTRO shape especifico. Mas robusto que la pila
               global cuando los indices se reordenan tras cada operacion.
        reference_shape_index: Indice del shape de referencia (solo para "before"/"after")
    """
    try:
        shape = _get_shape(shape_index)
        if order == "front":
            shape.OrderToFront()
        elif order == "back":
            shape.OrderToBack()
        elif order == "forward":
            # BUG real (verificado via type-lib): OrderForward()/OrderBackward() no
            # existen en la interfaz real de Shape - los metodos son OrderForwardOne()
            # y OrderBackOne() (con sufijo "One"/"Back", no "Forward"/"Backward").
            shape.OrderForwardOne()
        elif order == "backward":
            shape.OrderBackOne()
        elif order in ("before", "after"):
            if not reference_shape_index:
                return json.dumps({"error": "reference_shape_index requerido para 'before'/'after'"})
            ref_shape = _get_shape(reference_shape_index)
            # OrderFrontOf/OrderBackOf toman un objeto Shape COM directo, no un enum -
            # "after" (delante de la referencia) -> OrderFrontOf; "before" (detras) -> OrderBackOf.
            if order == "after":
                shape.OrderFrontOf(ref_shape)
            else:
                shape.OrderBackOf(ref_shape)
        else:
            return json.dumps({"error": f"Orden invalido: {order}"})
        return json.dumps({"success": True, "shape_index": shape_index,
                           "order": order}, ensure_ascii=False)
    except Exception as e:
        return _err(e)


@mcp.tool()
def corel_set_position(shape_index: int, x: float, y: float) -> str:
    """Posiciona un shape existente en coordenadas exactas (origen abajo-izquierda)."""
    try:
        shape = _get_shape(shape_index)
        shape.PositionX = x
        shape.PositionY = y
        return json.dumps({"success": True, "shape_index": shape_index,
                           "x": x, "y": y}, ensure_ascii=False)
    except Exception as e:
        return _err(e)


@mcp.tool()
def corel_set_size(shape_index: int, width: float, height: float) -> str:
    """Redimensiona un shape existente a un ancho/alto exacto."""
    try:
        shape = _get_shape(shape_index)
        shape.SizeWidth = width
        shape.SizeHeight = height
        return json.dumps({"success": True, "shape_index": shape_index,
                           "width": width, "height": height},
                          ensure_ascii=False)
    except Exception as e:
        return _err(e)


# ═════════════════════════════════════════════════════════════════════════════
# 5. FEEDBACK VISUAL (Capa 3: la IA "ve" el diseño mientras lo construye)
# ═════════════════════════════════════════════════════════════════════════════

@mcp.tool()
def corel_screenshot_canvas(dpi: int = 150) -> str:
    """
    Exporta la pagina actual como PNG de vista previa para que la IA (con
    vision) pueda "ver" el diseño mientras lo construye y ajustarlo antes
    de seguir — en vez de construir todo a ciegas con solo coordenadas.

    Flujo recomendado: crear/editar shapes -> corel_screenshot_canvas() ->
    leer la imagen resultante con la tool de lectura de archivos -> evaluar
    si se ve bien (composicion, color, proporciones) -> ajustar -> repetir.

    Siempre sobrescribe el mismo archivo (no acumula versiones).

    Args:
        dpi: Resolucion de la vista previa (150 = rapido y suficiente para evaluar)
    """
    try:
        preview_dir = Path.home() / "corel_preview"
        preview_dir.mkdir(parents=True, exist_ok=True)
        preview_path = preview_dir / "preview.png"
        result = _export_bitmap(str(preview_path), CDR_FILTER["png"], dpi,
                                False, False)
        result["path"] = str(preview_path)
        result["note"] = "Lee este archivo PNG para ver el estado actual del diseño"
        return json.dumps(result, ensure_ascii=False)
    except Exception as e:
        return _err(e)


# ═════════════════════════════════════════════════════════════════════════════
# 6. EXPORTACIÓN
# ═════════════════════════════════════════════════════════════════════════════

def _export_bitmap(file_path: str, filter_id: int, dpi: int,
                   transparent: bool, selection_only: bool) -> dict:
    """Receta verificada: ExportBitmap con los 16 parámetros posicionales."""
    doc = _get_doc()
    range_type = CDR_SELECTION if selection_only else CDR_CURRENT_PAGE
    flt = doc.ExportBitmap(
        file_path, filter_id, range_type, CDR_RGB,
        0, 0,                    # SizeX, SizeY (0 = automático según DPI)
        dpi, dpi,                # ResolutionX, ResolutionY
        CDR_NORMAL_AA,           # AntiAliasing
        False,                   # Dithered
        transparent,             # Transparent
        False,                   # UseColorProfile
        False,                   # MaintainLayers
        0,                       # Compression
        None, None,              # 2 parámetros objeto (obligatorio pasar None)
    )
    flt.Finish()
    return {"success": True, "path": file_path, "dpi": dpi}


@mcp.tool()
def corel_export_png(file_path: str, dpi: int = 300,
                     transparent: bool = True,
                     selection_only: bool = False) -> str:
    """
    Exporta el documento (o selección) a PNG.

    Args:
        file_path: Ruta del .png destino
        dpi: Resolución (300 para impresión POD, 150 para web, 72 borrador)
        transparent: Fondo transparente (True para POD)
        selection_only: Exportar solo lo seleccionado
    """
    try:
        p = Path(file_path).expanduser().resolve()
        p.parent.mkdir(parents=True, exist_ok=True)
        result = _export_bitmap(str(p), CDR_FILTER["png"], dpi,
                                transparent, selection_only)
        result["size_bytes"] = p.stat().st_size
        return json.dumps(result, ensure_ascii=False)
    except Exception as e:
        return _err(e)


@mcp.tool()
def corel_export_jpg(file_path: str, dpi: int = 300) -> str:
    """Exporta el documento a JPG (sin transparencia)."""
    try:
        p = Path(file_path).expanduser().resolve()
        p.parent.mkdir(parents=True, exist_ok=True)
        result = _export_bitmap(str(p), CDR_FILTER["jpg"], dpi, False, False)
        result["size_bytes"] = p.stat().st_size
        return json.dumps(result, ensure_ascii=False)
    except Exception as e:
        return _err(e)


@mcp.tool()
def corel_publish_pdf(file_path: str) -> str:
    """
    Publica el documento como PDF (vectorial, para imprenta).

    Args:
        file_path: Ruta del .pdf destino
    """
    try:
        doc = _get_doc()
        p = Path(file_path).expanduser().resolve()
        p.parent.mkdir(parents=True, exist_ok=True)
        doc.PublishToPDF(str(p))
        return json.dumps({"success": True, "path": str(p),
                           "size_bytes": p.stat().st_size}, ensure_ascii=False)
    except Exception as e:
        return _err(e)


# ═════════════════════════════════════════════════════════════════════════════
# 7. MACROS VBA (POD SUITE)
# ═════════════════════════════════════════════════════════════════════════════

@mcp.tool()
def corel_run_vba_macro(macro_name: str, gms_project: str = "GlobalMacros") -> str:
    """
    Ejecuta una macro VBA instalada en CorelDRAW (POD Suite Pro).

    Args:
        macro_name: "Modulo.Funcion" — ejemplos de POD Suite:
            EXPORTACIÓN:
              "POD_EXPORT_V2.BatchExport"        → exporta a 8 plataformas POD
              "POD_EXPORT_V2.QuickExportJPG"     → JPG 300dpi rápido
              "POD_EXPORT_V2.IncrementalSave"    → guarda nombre_v01, _v02...
              "POD_EXPORT.LimpiarPreprensa"      → textos a curvas + limpieza
            COLOR:
              "POD_COLOR_V2.SwapDarkLight"       → invierte blanco↔negro
              "POD_COLOR_V2.ColorClickSelect"    → selecciona por color
              "POD_COLOR_V2.AjustarHSL"          → ajuste HSL global
            TATTOO DEFORMER (requiere texto seleccionado):
              "POD_Tattoo.ApplyArch"             → arco
              "POD_Tattoo.ApplySkew"             → inclinación
              "POD_Tattoo.ApplyBarrel"           → abombado
              "POD_Tattoo.ApplyFlag"             → bandera/onda
              "POD_Tattoo.BuildS1Composition"    → composición completa
              "POD_Tattoo.GenerateDarkLightVersions" → 3 páginas: original/dark/light
            TIPOGRAFÍA:
              "POD_TYPO_V2.AplicarEstiloGrungeUrban"   → Impact 72pt
              "POD_TYPO_V2.AplicarEstiloCoreRefined"   → Trajan premium
              "POD_TYPO_V2.AplicarEstiloMinimalVector" → Helvetica spacing
        gms_project: Proyecto GMS donde viven las macros (default "GlobalMacros")

    NOTA: muchas macros POD abren InputBox/MsgBox — el usuario los completa.
    """
    try:
        app = _get_app()
        try:
            app.GMSManager.RunMacro(gms_project, macro_name)
        except Exception as e1:
            # Reintentar con el nombre de proyecto alternativo común
            try:
                app.GMSManager.RunMacro("POD", macro_name)
            except Exception:
                raise RuntimeError(
                    f"No se pudo ejecutar '{macro_name}' en '{gms_project}' ni en 'POD'. "
                    f"Verifica que POD Suite esté instalada (Herramientas → Macros). "
                    f"Error original: {e1}"
                )
        return json.dumps({"success": True, "macro": macro_name,
                           "note": "La macro puede mostrar diálogos al usuario"},
                          ensure_ascii=False)
    except Exception as e:
        return _err(e)


# ═════════════════════════════════════════════════════════════════════════════
# PUNTO DE ENTRADA
# ═════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    print("=" * 60)
    print("  MCP CorelDRAW Automation Server")
    print("  Ejecutando... Esperando conexión del cliente MCP")
    print("=" * 60)
    print("")
    print("  [D] Documentos:     create, open, save, close, info")
    print("  [T] Objetos:        add_text, rectangle, ellipse, list, select,")
    print("                      delete, convert_to_curves, center_on_page")
    print("  [C] Curvas/Rellenos: add_curve, fill_gradient, fill_solid, stroke")
    print("  [X] Composición:    select_shapes, align, distribute, duplicate,")
    print("                      transform, boolean_operation, group/ungroup,")
    print("                      z_order, set_position, set_size")
    print("  [F] Feedback:       screenshot_canvas (vista previa para la IA)")
    print("  [E] Exportación:    PNG (300dpi transparente), JPG, PDF vectorial")
    print("  [V] VBA/POD:        run_vba_macro (POD Suite Pro)")
    print("")
    print("  Total: 34 tools (18 originales + 16 nuevas: Capas 1, 2 y 3)")
    print("")

    mcp.run(transport="stdio")
