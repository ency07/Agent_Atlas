# 📘 Guía Completa de MCPs — Qué Hace Cada Uno

> Documentación detallada de los **7 MCPs configurados** en Claude Code, OpenCode y Hermes.
> Cada MCP es un servidor que expone "herramientas" (tools) que la IA puede usar.
> Esta guía explica qué hace cada tool, cuándo usarla, y ejemplos reales.

---

## 📋 Tabla de Contenidos

1. [Windows MCP](#-1-windows-mcp) — 44 herramientas para automatizar Windows
2. [CorelDRAW MCP](#-2-corel-draw-mcp) — 18 herramientas para diseño + macros POD
3. [Git MCP](#-3-git-mcp) — 12 herramientas para control de versiones
4. [Playwright MCP](#-4-playwright-mcp) — 24 herramientas para navegador + web scraping
5. [Ollama MCP](#-5-ollama-mcp) — 9 herramientas para ejecutar modelos locales
6. [GitHub MCP](#-6-github-mcp) — Gestión de repos, issues, PRs (pendiente OAuth)
7. [Supabase MCP](#-7-supabase-mcp) — 30+ herramientas para base de datos + edge functions

---

## 🪟 1. WINDOWS MCP

**Ruta:** `E:\MCP\mcp-windows-ai\mcp_windows_server.py`
**Total de herramientas:** 44
**Propósito:** Automatizar tareas genéricas de Windows — ejecutar programas, generar documentos, gestionar archivos, capturar pantalla, controlar mouse/teclado.

### Categorías de herramientas

#### 🪟 Gestión de Ventanas (6 tools)

| Herramienta | Qué hace | Ejemplo de uso |
|---|---|---|
| `list_windows()` | Lista todas las ventanas abiertas con sus títulos | "¿Qué programas tengo abiertos?" |
| `focus_window(title)` | Activa (enfoca) una ventana por su título | "Abre VS Code" (si ya está abierto) |
| `move_window(title, x, y)` | Mueve una ventana a posición (x, y) en píxeles | "Coloca Explorer a la izquierda (0,0)" |
| `resize_window(title, width, height)` | Redimensiona una ventana | "Hazme Explorer de 800x600" |
| `minimize_window(title)` | Minimiza una ventana | "Minimiza Chrome" |
| `maximize_window(title)` | Maximiza una ventana | "Maximiza Word" |
| `close_window(title)` | Cierra una ventana (sin confirmación) | "Cierra el Bloc de notas" |
| `get_active_window()` | Obtiene el título de la ventana activa actual | "¿Qué ventana tengo adelante?" |

**Ejemplo completo:**
```
👤 Abre 3 exploradores de carpeta lado a lado

Claude:
→ list_windows() [encuentra qué hay abierto]
→ focus_window("Explorer") [activa el primero]
→ resize_window("Explorer", 500, 600) [lo redimensiona a 500x600]
→ move_window("Explorer", 0, 0) [lo mueve a esquina superior izquierda]
→ [abre 2 exploradores más con open_program]
→ move_window("explorer.exe #2", 500, 0) [segundo en el medio]
→ move_window("explorer.exe #3", 1000, 0) [tercero a la derecha]
```

#### 🖱️ Mouse y Teclado (8 tools)

| Herramienta | Qué hace | Ejemplo de uso |
|---|---|---|
| `mouse_move(x, y, duration=0.5)` | Mueve cursor a (x, y) en segundos | "Lleva el mouse al centro" |
| `mouse_click(x, y, button="left")` | Clickea en (x, y): "left", "right", "middle" | "Haz click derecho en (100, 200)" |
| `mouse_scroll(clicks, x, y)` | Scroll rueda del mouse: +clicks hacia arriba, -clicks abajo | "Scroll hacia abajo 5 veces" |
| `mouse_position()` | Devuelve posición actual del cursor | "¿Dónde está el mouse?" |
| `mouse_drag(x, y, button, duration)` | Arrastra: click sostenido + movimiento | "Arrastra de A a B" |
| `keyboard_type(text, interval=0.05)` | Escribe texto carácter a carácter | "Escribe 'Hola Mundo'" |
| `keyboard_hotkey(keys)` | Ejecuta combinación: "ctrl+c", "alt+tab", etc. | "Presiona Ctrl+S para guardar" |
| `keyboard_press(key, presses=1)` | Presiona una sola tecla N veces | "Presiona Enter 3 veces" |

**Ejemplo completo:**
```
👤 Abre Notepad, escribe algo, guarda y cierra

Claude:
→ open_program("notepad.exe")
→ [espera 1 segundo a que cargue]
→ keyboard_type("Mi primer script automatizado")
→ keyboard_hotkey("ctrl+s") [abre diálogo guardar]
→ keyboard_type("mi_archivo.txt")
→ keyboard_hotkey("enter") [confirma]
→ keyboard_hotkey("alt+f4") [cierra Notepad]
```

#### 📁 Archivos y Carpetas (7 tools)

| Herramienta | Qué hace | Ejemplo de uso |
|---|---|---|
| `file_list(path)` | Lista archivos y carpetas en una ruta | "¿Qué hay en Documentos?" |
| `file_read(path)` | Lee el contenido completo de un archivo .txt | "Lee el contenido de config.json" |
| `file_write(path, content)` | Escribe (y crea si no existe) un archivo | "Crea archivo.txt con esto" |
| `file_delete(path)` | Elimina un archivo (⚠️ sin papelera) | "Borra el archivo temporal" |
| `file_copy(source, destination)` | Copia un archivo | "Copia documento.txt a Desktop" |
| `folder_create(path)` | Crea una carpeta (y padres si falta) | "Crea C:\Users\Admin\reportes\2026" |
| `folder_create(path)` | Idem | |

**Ejemplo completo:**
```
👤 Crea una estructura de carpetas para un proyecto

Claude:
→ folder_create("C:\Users\Admin\ProyectoX\src")
→ folder_create("C:\Users\Admin\ProyectoX\tests")
→ folder_create("C:\Users\Admin\ProyectoX\docs")
→ file_write("C:\Users\Admin\ProyectoX\README.md", "# ProyectoX\n...")
→ file_write("C:\Users\Admin\ProyectoX\src\main.py", "print('Hola')")
```

#### ⚙️ Procesos (3 tools)

| Herramienta | Qué hace | Ejemplo de uso |
|---|---|---|
| `process_list()` | Lista todos los procesos en ejecución con PID | "¿Qué procesos están corriendo?" |
| `process_start(command, args)` | Inicia un programa/comando | "Arranca python script.py" |
| `process_kill(pid)` | Mata un proceso por su PID (⚠️ sin confirmación) | "Termina el PID 1234" |

**Ejemplo completo:**
```
👤 Compila un programa C++ y si falla, mata el proceso

Claude:
→ process_start("gcc", "programa.c -o programa.exe")
→ [si falla]
→ process_list() [encuentra el PID de gcc]
→ process_kill(5678) [mata el proceso]
```

#### 💻 Sistema (2 tools)

| Herramienta | Qué hace | Ejemplo de uso |
|---|---|---|
| `system_info()` | Devuelve info del PC: CPU, RAM, disco, SO | "¿Cuánta RAM libre tengo?" |
| `screenshot()` | Captura pantalla y guarda como PNG | "Haz una captura de pantalla" |

#### 🔊 Multimedia (1 tool)

| Herramienta | Qué hace | Ejemplo de uso |
|---|---|---|
| `volume_set(level)` | Ajusta volumen del sistema 0-100 | "Sube el volumen a 50%" |

#### 📊 Documentos Office (4 tools)

| Herramienta | Qué hace | Ejemplo de uso |
|---|---|---|
| `docx_create(path, content)` | Crea documento Word (.docx) con párrafos, tablas, estilos | "Haz un informe de ventas en Word" |
| `xlsx_create(path, content)` | Crea Excel (.xlsx) con datos, fórmulas (SUM, AVERAGE), formato | "Crea un sheet con ingresos/egresos" |
| `pptx_create(path, content)` | Crea presentación PowerPoint (.pptx) con diapositivas, tablas | "Haz 5 slides sobre marketing" |
| `pdf_create(path, content)` | Crea PDF (.pdf) con membrete, tablas, texto formato | "Genera factura en PDF" |

**Formato especial:** `content` es JSON/dict con estructura específica por tipo:
```json
{
  "title": "Mi Informe",
  "paragraphs": ["Párrafo 1", "Párrafo 2"],
  "tables": [
    {
      "headers": ["Mes", "Venta"],
      "rows": [["Enero", "1000"], ["Febrero", "1500"]]
    }
  ]
}
```

#### 🌐 Web (2 tools)

| Herramienta | Qué hace | Ejemplo de uso |
|---|---|---|
| `open_url(url)` | Abre URL en navegador predeterminado | "Abre https://github.com" |
| `web_fetch(url, max_chars=8000)` | Descarga y parsea página web como texto/Markdown | "Descarga el contenido de ejemplo.com" |

#### 🔧 Otros (7 tools)

| Herramienta | Qué hace | Ejemplo de uso |
|---|---|---|
| `run_command(command, timeout=30)` | Ejecuta comando de CMD y devuelve salida | "Ejecuta `dir` y dame el listado" |
| `run_script(script_path, args)` | Ejecuta script Batch (.bat) o PowerShell (.ps1) | "Corre mi_script.bat" |
| `open_program(program, file_path, arguments)` | Abre un programa, opcionalmente con archivo | "Abre documento.docx con Word" |
| `list_installed_programs()` | Lista programas instalados (desde Registro Windows) | "¿Qué programas tengo?" |
| `type_in_program(program_title, text, delay)` | Busca ventana, la enfoca, y escribe texto | "Escribe 'hola' en Notepad" |
| `clipboard_get()` | Lee contenido del portapapeles | "¿Qué hay en el portapapeles?" |
| `clipboard_set(content)` | Copia contenido al portapapeles | "Copia esto al portapapeles" |
| `notify(title, message, duration)` | Muestra notificación del sistema Windows | "Notifica 'Descarga completada'" |
| `get_wifi_info()` | Info de red WiFi actual | "¿A qué WiFi estoy conectado?" |
| `registry_read(key_path, value_name)` | Lee valor del Registro de Windows | "Lee HKEY_LOCAL_MACHINE\SOFTWARE\..." |

---

## 🎨 2. COREL DRAW MCP

**Ruta:** `E:\MCP\mcp-windows-ai\mcp_corel_server.py`
**Total de herramientas:** 18
**Propósito:** Control profundo de CorelDRAW via **COM Automation** + ejecución de macros VBA POD Suite.
**Nota importante:** NO es "simular clicks" — es acceso real a la API interna de CorelDRAW.

### Categorías de herramientas

#### 📋 Documento (5 tools)

| Herramienta | Qué hace | Ejemplo de uso |
|---|---|---|
| `corel_ping()` | Verifica si CorelDRAW está abierto y devuelve versión | "¿Está CorelDRAW corriendo?" |
| `corel_create_document()` | Crea documento nuevo en blanco | "Abre un documento nuevo" |
| `corel_open_document(file_path)` | Abre archivo .cdr existente | "Abre diseño.cdr" |
| `corel_save_document(file_path)` | Guarda documento activo (crea si no existe) | "Guarda como mi_diseño.cdr" |
| `corel_close_document()` | Cierra documento sin guardar (⚠️ cuidado) | "Cierra el documento" |
| `corel_get_document_info()` | Devuelve info: nombre, tamaño, nº páginas, capas | "Dame info del documento actual" |

#### ✏️ Texto y Objetos (4 tools)

| Herramienta | Qué hace | Ejemplo de uso |
|---|---|---|
| `corel_add_text(text, x, y, font, size, bold, italic)` | Crea texto artístico en coordenadas x,y | "Añade texto 'HOLA' en Impact 48pt" |
| `corel_add_rectangle(x, y, width, height, fill_color)` | Crea rectángulo (útil para fondos) | "Dibuja rectángulo azul 200x100" |
| `corel_add_ellipse(x, y, width, height, fill_color)` | Crea círculo/elipse | "Dibuja círculo rojo de 100x100" |
| `corel_list_objects()` | Lista objetos de la capa activa (nombre, tipo, posición) | "¿Qué objetos hay en la página?" |
| `corel_select_all()` | Selecciona todos los objetos | "Selecciona todo" |
| `corel_delete_selection()` | Elimina objetos seleccionados | "Borra lo seleccionado" |

#### 🎭 Transformaciones (3 tools)

| Herramienta | Qué hace | Ejemplo de uso |
|---|---|---|
| `corel_convert_to_curves()` | Convierte texto seleccionado a curvas (preprensa) | "Convierte el texto a curvas" |
| `corel_center_on_page()` | Centra selección horizontal y verticalmente | "Centra en la página" |
| `corel_export_png(dpi, transparent_bg)` | Exporta documento a PNG con DPI y fondo | "Exporta a PNG 300dpi sin fondo" |
| `corel_export_jpg(dpi, quality)` | Exporta a JPG (sin transparencia) | "Exporta JPG 90% calidad" |
| `corel_publish_pdf(file_path)` | Publica como PDF vectorial (para imprenta) | "Publica como PDF para imprenta" |

#### 🔧 Macros VBA (1 tool)

| Herramienta | Qué hace | Ejemplo de uso |
|---|---|---|
| `corel_run_vba_macro(module_name.macro_name)` | Ejecuta una macro VBA instalada en el document | "Ejecuta POD_Tattoo.OpenScriptTattooDeformer" |

**Las macros disponibles desde POD Suite (que instalaste):**
- `POD_Export.QuickExportPNG` — exporta rápido a PNG Redbubble
- `POD_Color_V2.SwapDarkLight` — invierte colores oscuro/claro
- `POD_Typo_v2.AplicarEstiloGrungeUrban` — aplica estilo de tipografía
- `POD_Tattoo.OpenScriptTattooDeformer` — deformaciones para tattoos
- Y 40+ macros más

**Ejemplo completo:**
```
👤 Crea un diseño de camiseta: rectángulo azul + texto "HUSTLE HARD"
   y exporta a Redbubble en PNG

Claude:
→ corel_create_document() [documento nuevo]
→ corel_add_rectangle(100, 100, 1000, 1000, "blue") [fondo azul]
→ corel_add_text("HUSTLE HARD", 500, 500, "Impact", 96, True, False)
→ corel_run_vba_macro("POD_Typo_v2.AplicarEstiloGrungeUrban") 
  [aplica estilo grunge]
→ corel_export_png(300, True) [exporta PNG 300dpi con fondo transparente]
→ corel_save_document("camiseta_hustle.cdr")
```

---

## 📦 3. GIT MCP

**Ruta:** via Python MCP server (`mcp_server_git`)
**Total de herramientas:** 12
**Propósito:** Control de versiones — ver cambios, comitear, hacer push, ver historial.

### Todas las herramientas

| Herramienta | Qué hace | Ejemplo de uso |
|---|---|---|
| `git_status()` | Muestra archivos modificados, no rastreados, staged | "¿Qué cambios hay?" |
| `git_diff(path)` | Muestra diferencias en archivo (sin staged) | "Muestra cambios en archivo.py" |
| `git_diff_staged()` | Muestra cambios que ya hiciste stage | "¿Qué cambios estoy a punto de comitear?" |
| `git_diff_unstaged()` | Muestra cambios sin stage | "¿Qué edité que no está staged?" |
| `git_add(path)` | Añade archivo a staging area | "Prepara archivo.py para comitear" |
| `git_commit(message)` | Crea commit con mensaje | "Comitea: 'feat: agregar validación'" |
| `git_log(path, max_count)` | Muestra historial de commits | "Dame los últimos 10 commits" |
| `git_show(ref)` | Muestra contenido de un commit específico | "Muestra el commit abc123" |
| `git_branch()` | Lista ramas locales y cuál está activa | "¿Qué rama estoy usando?" |
| `git_checkout(branch)` | Cambia a otra rama | "Cambia a rama develop" |
| `git_create_branch(branch_name)` | Crea una rama nueva | "Crea rama feature/nuevo-modulo" |
| `git_reset(ref)` | Revierte cambios a un commit anterior | "Vuelve al commit xyz789" |

**Ejemplo completo:**
```
👤 Haz cambios a un archivo, prepáralo, comitea y sube a GitHub

Claude:
→ git_status() [ve qué cambió]
→ git_diff_unstaged() [ve exactamente qué editaste]
→ git_add("archivo.py") [lo prepara]
→ git_commit("fix: arreglar bug de validación") [lo comitea]
→ [luego subes con Bash: git push]
```

---

## 🌐 4. PLAYWRIGHT MCP

**Ruta:** via NPX (`@playwright/mcp@latest`)
**Total de herramientas:** 24
**Propósito:** Automatización de navegador — abrir web, hacer clicks, llenar formularios, scraping, screenshots.

### Categorías de herramientas

#### 🔌 Navegador Básico (5 tools)

| Herramienta | Qué hace | Ejemplo de uso |
|---|---|---|
| `browser_open(url)` | Abre navegador y va a URL | "Abre https://google.com" |
| `browser_close()` | Cierra navegador | "Cierra el navegador" |
| `browser_navigate(url)` | Va a URL (navegador ya abierto) | "Navega a Wikipedia" |
| `browser_navigate_back()` | Botón atrás | "Vuelve a la página anterior" |
| `browser_tabs()` | Lista tabs abiertos | "¿Qué tabs tengo abiertos?" |

#### 🖱️ Interacción (8 tools)

| Herramienta | Qué hace | Ejemplo de uso |
|---|---|---|
| `browser_click(selector)` | Clickea elemento CSS selector | "Clickea el botón .submit" |
| `browser_type(selector, text)` | Escribe en un input/textarea | "Escribe 'correo@ejemplo.com' en #email" |
| `browser_fill_form(fields)` | Rellena múltiples campos de una | "Llena nombre, email, teléfono" |
| `browser_select_option(selector, value)` | Selecciona opción en dropdown | "Elige 'Colombia' en #país" |
| `browser_drag(from_selector, to_selector)` | Arrastra un elemento a otro | "Arrastra imagen de A a B" |
| `browser_hover(selector)` | Mueve mouse sobre elemento | "Hover en el menú dropdown" |
| `browser_press_key(key)` | Presiona tecla: "Enter", "Escape", "Tab" | "Presiona Enter" |
| `browser_scroll(selector)` | Scroll para hacer visible elemento | "Scroll hasta el footer" |

#### 📊 Lectura (6 tools)

| Herramienta | Qué hace | Ejemplo de uso |
|---|---|---|
| `browser_find(text)` | Encuentra elemento por texto | "¿Dónde está 'Comprar'?" |
| `browser_take_screenshot()` | Captura pantalla | "Haz screenshot de la página" |
| `browser_get_text(selector)` | Lee texto de un elemento | "¿Dice qué en el h1?" |
| `browser_snapshot()` | Guarda snapshot para comparar cambios | "Guarda estado de la página" |
| `browser_console_messages()` | Lee mensajes de consola (errores, logs) | "¿Hay errores en consola?" |
| `browser_network_requests()` | Lista requests HTTP hechas | "¿Qué endpoints llamó la página?" |
| `browser_evaluate(code)` | Ejecuta JavaScript en la página | "Devuelve document.title" |

#### ⏳ Espera (3 tools)

| Herramienta | Qué hace | Ejemplo de uso |
|---|---|---|
| `browser_wait_for(selector)` | Espera a que aparezca elemento | "Espera al botón .cargar" |
| `browser_wait_for_text(text)` | Espera a que aparezca texto | "Espera a 'Carga completa'" |
| `browser_wait_for_timeout(ms)` | Espera X milisegundos | "Espera 2 segundos" |

**Ejemplo completo:**
```
👤 Abre Google, busca "Python", va al primer resultado y guarda screenshot

Claude:
→ browser_open("https://google.com")
→ browser_type("input[name=q]", "Python") [rellena buscador]
→ browser_press_key("Enter") [busca]
→ browser_wait_for("a[href*=python.org]") [espera resultado]
→ browser_click("a[href*=python.org]") [clickea Python.org]
→ browser_wait_for_timeout(2000) [espera carga]
→ browser_take_screenshot() [captura]
```

---

## 🦙 5. OLLAMA MCP

**Ruta:** via NPX (`ollama-mcp-server`)
**Total de herramientas:** 9
**Propósito:** Gestionar y ejecutar modelos locales de Ollama (sin gastar cuota de Claude).

### Herramientas

| Herramienta | Qué hace | Ejemplo de uso |
|---|---|---|
| `ollama_list()` | Lista modelos descargados e instalados | "¿Qué modelos tengo?" |
| `ollama_pull(model_name)` | Descarga un modelo (llama2, mistral, phi4, etc.) | "Descarga phi4-mini" |
| `ollama_rm(model_name)` | Borra un modelo local (libera espacio) | "Borra llama2" |
| `ollama_show(model_name)` | Muestra info del modelo: parámetros, tamaño, etc. | "Info de phi4-mini" |
| `ollama_run(model, prompt)` | Ejecuta modelo con un prompt | "Usa phi4 para escribir poema" |
| `ollama_chat_completion(model, messages)` | Chat multi-turno con el modelo | "Charla con mistral:7b" |
| `ollama_create(model_name, modelfile)` | Crea modelo personalizado | "Crea modelo con parámetros custom" |
| `ollama_push(model_name, registry)` | Sube modelo a registry | "Sube a Ollama Hub" |
| `ollama_cp(source, destination)` | Copia un modelo (para variar parámetros) | "Copia phi4-mini a phi4-fast" |

**Ejemplo completo:**
```
👤 Lista modelos, corre phi4 en una tarea simple

Claude:
→ ollama_list() [ve modelos disponibles]
→ ollama_run("phi4-mini", "¿Cuál es la capital de Francia?")
→ [resultado: "París"]
```

---

## 🐙 6. GITHUB MCP

**Ruta:** URL HTTP (`https://api.githubcopilot.com/mcp/`)
**Total de herramientas:** ~20
**Estado:** ⚠️ **Pendiente OAuth** — necesita autorizarse por navegador la primera vez.
**Propósito:** Gestionar repos GitHub — crear issues, PRs, ver commits, colaborar.

### Herramientas (principales)

| Herramienta | Qué hace | Ejemplo de uso |
|---|---|---|
| `github_list_repositories()` | Lista tus repos | "¿Qué repos tengo?" |
| `github_get_repository_details(owner, repo)` | Info del repo: descripción, URL, stars | "Dame info de ency07/mcp-windows-ai" |
| `github_create_issue(owner, repo, title, body)` | Crea un issue nuevo | "Crea issue 'Bug: servidor no inicia'" |
| `github_list_issues(owner, repo)` | Lista issues (abiertos, cerrados) | "¿Qué issues tengo abiertos?" |
| `github_get_issue(owner, repo, issue_number)` | Lee detalles de un issue | "Lee issue #5" |
| `github_create_pull_request(owner, repo, title, head, base)` | Crea una PR | "Abre PR desde rama feature a main" |
| `github_list_pull_requests(owner, repo)` | Lista PRs | "¿Qué PRs tengo?" |
| `github_merge_pull_request(owner, repo, pr_number)` | Fusiona una PR | "Fusiona PR #3" |
| `github_list_commits(owner, repo)` | Lista commits | "Últimos 10 commits" |
| `github_get_file_contents(owner, repo, path)` | Lee contenido de archivo en GitHub | "Lee README.md de mcp-windows-ai" |

**Ejemplo completo (una vez autorizado):**
```
👤 Crea un issue en tu repo para un bug encontrado

Claude:
→ github_create_issue("ency07", "mcp-windows-ai", 
                      "Bug: Windows MCP falla con rutas largas",
                      "Cuando la ruta excede 260 caracteres...")
```

---

## 🗄️ 7. SUPABASE MCP

**Ruta:** URL HTTP con project_ref (`https://mcp.supabase.com/mcp?project_ref=jcsjfvrfsohahnoovjgf`)
**Total de herramientas:** 30+
**Estado:** ⚠️ **Pendiente OAuth en Hermes/OpenCode** (Claude Code ya tiene acceso vía proyecto ERP)
**Propósito:** Auditar BD, ejecutar queries SQL, edge functions, migraciones.

### Categorías de herramientas

#### 📊 Lectura de Esquema (3 tools)

| Herramienta | Qué hace | Ejemplo de uso |
|---|---|---|
| `supabase_list_tables()` | Lista todas las tablas de la BD | "¿Qué tablas hay?" |
| `supabase_list_extensions()` | Lista extensiones PostgreSQL activas | "¿Qué extensiones tiene?" |
| `supabase_list_migrations()` | Lista migraciones aplicadas | "¿Qué migraciones corrieron?" |

#### 🔍 Queries (2 tools)

| Herramienta | Qué hace | Ejemplo de uso |
|---|---|---|
| `supabase_execute_sql(query)` | Ejecuta SQL directo contra la BD | "SELECT COUNT(*) FROM usuarios" |
| `supabase_search_docs(query)` | Busca en docs de Supabase | "¿Cómo configuro RLS?" |

#### 🚀 Edge Functions (3 tools)

| Herramienta | Qué hace | Ejemplo de uso |
|---|---|---|
| `supabase_list_edge_functions()` | Lista funciones serverless desplegadas | "¿Qué edge functions tengo?" |
| `supabase_get_edge_function(name)` | Lee código de una edge function | "Muestra código de send-email" |
| `supabase_deploy_edge_function(name, code)` | Crea o actualiza edge function | "Despliega nueva función webhook" |

#### 🔐 Ramas (Dev/Prod) (5 tools)

| Herramienta | Qué hace | Ejemplo de uso |
|---|---|---|
| `supabase_list_branches()` | Lista ramas de DB (main, dev, staging) | "¿Qué ramas tengo?" |
| `supabase_create_branch(name)` | Crea rama nueva para testing | "Crea rama staging" |
| `supabase_delete_branch(name)` | Borra rama (⚠️ destruye datos) | "Borra rama test-123" |
| `supabase_merge_branch(source, target)` | Fusiona cambios de una rama a otra | "Fusiona dev a main" |
| `supabase_rebase_branch(branch)` | Rebasa rama sobre cambios principales | "Rebasa staging" |

#### 📊 Observabilidad (2 tools)

| Herramienta | Qué hace | Ejemplo de uso |
|---|---|---|
| `supabase_get_logs()` | Lee logs de error/warning de la BD | "¿Hay errores en los logs?" |
| `supabase_get_advisors()` | Lee recomendaciones de performance | "¿Cómo optimizo la BD?" |

#### 📋 Otros (4 tools)

| Herramienta | Qué hace | Ejemplo de uso |
|---|---|---|
| `supabase_get_project_url()` | Devuelve URL de conexión | "Dame la URL del proyecto" |
| `supabase_get_publishable_keys()` | Devuelve claves públicas para clientes | "¿Cuál es la anon key?" |
| `supabase_apply_migration(sql)` | Aplica una migración SQL | "Aplica migración add_users_table" |
| `supabase_generate_typescript_types()` | Genera tipos TS del esquema | "Genera tipos de la BD" |

**Ejemplo completo (acceso al ERP):**
```
👤 Audita qué usuarios hay en el ERP y cuántos tienen activos

Claude:
→ supabase_execute_sql("SELECT COUNT(*) as total FROM auth.users")
→ supabase_execute_sql("SELECT id, email, created_at FROM auth.users LIMIT 10")
→ supabase_get_logs() [ve si hay errores recientes]
```

---

## 🎯 MATRIZ DE DECISIÓN: ¿QUÉ MCP USAR?

| Necesidad | Usa este MCP | Ejemplo |
|---|---|---|
| **Automatizar Windows genérico** | Windows | Crear carpetas, generar Excel, abrir programas |
| **Diseño en CorelDRAW / POD** | CorelDRAW | Crear diseño, exportar PNG, aplicar macros |
| **Control de versiones (Git)** | Git | Ver cambios, commitear, historial |
| **Web scraping / testing web** | Playwright | Llenar formularios, extraer datos, screenshots |
| **Ejecutar modelos IA locales** | Ollama | Generar texto sin internet, tareas rápidas |
| **Gestionar GitHub (issues, PRs)** | GitHub | Crear/cerrar issues, abrir PRs, colaborar |
| **Auditar base de datos / SQL** | Supabase | Ver esquema, ejecutar queries, edge functions |

---

## 📝 NOTAS IMPORTANTES

### Control "profundo" vs "a ciegas"
- **CorelDRAW:** Control real vía COM → sabe qué capas, shapes, textos hay
- **Windows:** Control "a ciegas" vía pyautogui → simula mouse/teclado, frágil si UI cambia
- **Playwright:** Control web preciso vía selectores CSS
- **Git/GitHub/Supabase:** APIs documentadas, 100% confiable

### Niveles de confianza (en orden)
1. 🟢 **Máximo:** CorelDRAW, Git, Supabase, GitHub (APIs reales)
2. 🟡 **Alto:** Playwright (web es dinámico pero selectores son precisos)
3. 🟠 **Medio:** Windows (funciona pero frágil a cambios UI)
4. 🔴 **Variable:** Ollama (depende del modelo — phi4 es bueno, qwen3:0.6b es malo con tools)

### Combinaciones útiles
```
Caso: Generar reportes de ventas en Excel + subirlos a GitHub
MCPs: Windows (crear Excel) + Git (comitear) + GitHub (crear issue de aprobación)

Caso: Scraping de web + guardar en BD
MCPs: Playwright (extraer datos) + Supabase (guardar en BD)

Caso: Diseño POD + test automático
MCPs: CorelDRAW (crear) + Windows (captura) + Playwright (verificar web)
```

---

## ⚡ ACCESO RÁPIDO: COMANDOS DE LOS 3 AGENTES

```bash
# Claude Code (interactivo en terminal)
claude

# OpenCode (TUI)
opencode

# Hermes (tu asistente)
hermes chat
```

**Archivos `.bat` en el Escritorio para arrancar:**
- `Abrir_ClaudeCode.bat`
- `Abrir_OpenCode.bat`
- `Abrir_Hermes.bat`

---

**Última actualización:** 2026-07-30 23:50
**Autor:** Claude Code + Documentación automática
