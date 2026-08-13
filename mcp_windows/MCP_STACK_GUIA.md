# 🧩 Guía de Uso — MCP Stack completo (7 MCPs × 3 agentes)

> Actualizado 2026-07-30: los **7 MCPs** (Windows, CorelDRAW, Git, Playwright, Ollama,
> GitHub, Supabase) ahora están configurados en paridad en los **3 agentes** que usas:
> **Claude Code**, **OpenCode** y **Hermes Agent**. Cualquiera de los 3 puede, en teoría,
> manejar todas las mismas herramientas — la diferencia entre agentes es el modelo
> ("cerebro") detrás, no las tools disponibles.
>
> Regla de origen único: `mcp_windows_server.py` y `mcp_corel_server.py` viven **solo**
> en `E:\MCP\mcp-windows-ai\` (repo con git). Ningún agente debe apuntar a copias sueltas
> en Desktop/Temp — se encontró y corrigió una ruta rota en OpenCode que apuntaba a un
> archivo del Escritorio ya borrado.

## ⚠️ Importante: "control" no es igual para todos los MCPs

- **CorelDRAW MCP** = control profundo real vía **COM Automation** — llama a la API interna
  de la aplicación (crear capas, leer shapes, ejecutar macros VBA). Preciso y confiable.
- **Windows MCP** = control genérico pero **"a ciegas"** — simula mouse/teclado
  (`pyautogui`), mueve ventanas por título, ejecuta comandos de CLI, lee/escribe archivos.
  Sirve para abrir programas, automatizar tareas simples, generar documentos — pero
  **no tiene el mismo nivel de precisión que Corel** con programas que no tienen COM/API
  propia (ej. no puede "leer" el estado interno de VS Code como sí lee capas en Corel).
  Para editores de código, lo más confiable sigue siendo editar archivos directo + Git,
  no simular clics.

## Estado por agente (2026-07-30)

| MCP | Claude Code | OpenCode | Hermes |
|---|---|---|---|
| `windows` (44 tools) | ✅ Conectado | ✅ Configurado | ✅ Habilitado (44/44) |
| `corel-draw` (18 tools) | ✅ Conectado | ✅ Configurado (ruta corregida) | ✅ Habilitado (18/18) |
| `git` | ✅ Conectado | ✅ Configurado | ✅ Habilitado (12/12) |
| `playwright` | ✅ Conectado | ✅ Configurado | ✅ Habilitado (24/24) |
| `ollama` | ✅ Conectado | ✅ Configurado | ✅ Habilitado (9/9) |
| `github` | ⚠️ Pendiente OAuth | ⚠️ Pendiente OAuth | ⚠️ Guardado, disabled (pendiente OAuth) |
| `supabase` | ✅ Conectado (scope proyecto ERP) | ✅ Configurado | ⚠️ Guardado, disabled (pendiente OAuth) |

**GitHub y Supabase en Hermes/OpenCode** necesitan autorización OAuth por navegador la
próxima vez que se use esa tool en una sesión interactiva de cada agente (mismo patrón
que ya se resolvió en Claude Code).

## Ver estado de todos

```bash
# Claude Code
claude mcp list

# Hermes
hermes mcp list

# OpenCode: revisar directamente el bloque "mcp" en
# C:\Users\Administrator\.config\opencode\opencode.jsonc
```

```
git: ... - ✔ Connected
playwright: ... - ✔ Connected
ollama: ... - ✔ Connected
github: ... - ⚠ Pendiente OAuth
supabase: ... - ✔ Connected
```

---

## 1. 🗂️ Git MCP — auditar repos locales

**Qué hace:** lee estado, diffs, log e historial de commits de un repo git local. Solo lectura de metadatos (no hace push/pull, no toca red).

**Instalado como:** `git` (venv hermes + `mcp_server_git`, scope global).

### Ejemplos de uso (le escribes esto a Claude):

```
Revisa el estado de git en E:\MCP\mcp-windows-ai y dime si hay cambios sin commitear
```

```
Muéstrame el diff sin commitear de E:\Macros_Corel
```

```
Dame el log de los últimos 10 commits del repo del ERP
```

```
¿Qué archivos cambiaron en el commit d283f98 del ERP?
```

**Caso real para ti:** antes de cada `git push`, pídele "revisa qué se va a subir" — te lista status + diff sin que tengas que escribir comandos.

---

## 2. 🎭 Playwright MCP — testing, scraping, PDF de páginas web

**Qué hace:** controla un navegador real (Chromium) — navega, hace clic, llena formularios, toma screenshots, exporta a PDF. Oficial de Microsoft, sin credenciales.

**Instalado como:** `playwright` (`npx @playwright/mcp@latest`, scope global).

### Ejemplos de uso:

```
Abre localhost:3000/dashboard y toma una captura de pantalla
```

```
Ve a la página de login del ERP, llena usuario "test@test.com" y contraseña
"123456", haz clic en "Ingresar" y dime si funcionó
```

```
Navega a https://docs.supabase.com y busca información sobre RLS policies
```

```
Genera un PDF de la página localhost:3000/dashboard/invoices
```

**Caso real para ti:** verificar visualmente que un cambio en el ERP (ej. el dashboard de facturas) se ve bien, **sin abrir tú mismo el navegador** — Claude navega, hace clic, y te reporta o muestra captura.

**⚠️ Precaución:** no le pidas que navegue a sitios no confiables ni que ingrese credenciales reales tuyas (bancos, email personal) — el browser tiene acceso completo a lo que cargue.

---

## 3. 🦙 Ollama MCP — gestionar modelos locales

**Qué hace:** lista, consulta y gestiona los modelos Ollama corriendo en tu PC directamente desde Claude Code (sin abrir terminal aparte).

**Instalado como:** `ollama` (`npx ollama-mcp-server`, scope global). Requiere que `ollama serve` esté corriendo (normalmente arranca solo).

### Ejemplos de uso:

```
Lista los modelos de Ollama que tengo instalados
```

```
Pregúntale a qwen2.5-coder:7b cómo optimizar esta función SQL: [pega el código]
```

```
Compara qué tan rápido responde phi4-mini vs qwen2.5:3b con el mismo prompt
```

```
¿Cuánto espacio en disco ocupan mis modelos de Ollama?
```

**Caso real para ti:** delegar tareas simples/repetitivas a un modelo local (gratis, privado) en vez de gastar cuota de Claude — por ejemplo, pedirle a `qwen2.5-coder` que revise sintaxis básica antes de pedírtelo a Claude.

---

## 4. 🐙 GitHub MCP — issues, PRs, repos (⚠️ pendiente activar)

**Qué hace:** buscar código, leer/crear issues y PRs, gestionar repos de GitHub directamente. Servidor oficial hosteado por GitHub (`api.githubcopilot.com`).

**Instalado como:** `github` (HTTP remoto, scope global). **Requiere autorización OAuth** — la próxima vez que abras Claude Code en modo interactivo y uses una tool de GitHub, te va a mostrar un link para loguearte con tu cuenta y autorizar. Solo se hace una vez.

### Ejemplos de uso (una vez autorizado):

```
Lista los issues abiertos en ency07/mcp-windows-ai
```

```
Busca PRs pendientes de revisar en Macros_CorelDraw
```

```
Crea un issue en mcp-windows-ai: "Reimplementar POD_Color_v2.bas" con la
descripción de las 6 funciones pendientes
```

```
¿Cuál fue el último commit pusheado a main en Macros_CorelDraw?
```

**Precaución:** dale acceso de **solo lectura** cuando sea posible (buscar, listar) — evita pedirle que haga merge o cierre PRs automáticamente sin que tú revises primero.

---

## 5. 🗄️ Supabase MCP — auditar y consultar el ERP

**Qué hace:** ejecutar queries SQL, ver esquema de tablas, revisar logs y advisors (alertas de seguridad/performance) de tu proyecto Supabase del ERP.

**Instalado como:** `supabase` (HTTP oficial, scope **proyecto ERP** — solo funciona cuando trabajas en ese directorio). Ya estaba conectado antes de esta sesión.

### Ejemplos de uso:

```
Lista todas las tablas del proyecto Supabase del ERP
```

```
¿Hay alertas de seguridad (advisors) pendientes en el proyecto?
```

```
Ejecuta: SELECT count(*) FROM invoices WHERE status = 'BORRADOR'
```

```
Revisa los logs de errores recientes del proyecto
```

```
Genera los tipos TypeScript actualizados desde el esquema de la BD
```

**Caso real para ti:** repetir las auditorías tipo "cross-tenant leak" (como la de 2026-07-23) de forma más directa, sin depender de un agente que ejecute SQL manualmente — Claude puede consultar la BD real en vivo.

**⚠️ Precaución:** antes de pedir cambios de esquema (`apply_migration`) revisa que estés en el proyecto correcto — los cambios van directo a la BD remota, no hay "modo prueba" local a menos que uses branches de Supabase.

---

## 🚫 MCPs evaluados y descartados (por ahora)

| MCP | Por qué no |
|-----|-----------|
| npm/publish | Puede publicar paquetes públicos maliciosos si el token se filtra |
| Oracle Cloud | Acceso completo y destructivo a infraestructura de producción |
| n8n | No confirmado uso activo — evaluar si se necesita más adelante |
| PDF genérico (md-to-pdf, etc.) | Redundante — ya tienes `pdf_create` en `mcp_windows_server.py` |

---

## 📌 Resumen rápido — cuál usar para qué

| Necesito... | Uso este MCP |
|-------------|-------------|
| Ver qué cambié antes de comitear | **Git** |
| Probar visualmente el ERP en el navegador | **Playwright** |
| Consultar un modelo local gratis | **Ollama** |
| Ver/crear issues o PRs | **GitHub** (tras autorizar) |
| Auditar o consultar la BD del ERP | **Supabase** |
| Automatizar CorelDRAW | Tu propio `mcp_corel_server.py` (ver `GUIA_USO.md`) |
| Crear documentos/PDF/Excel | Tu propio `mcp_windows_server.py` (ver `GUIA_USO.md`) |

---

**Última actualización:** 2026-07-30 — stack instalado y verificado (Git, Playwright, Ollama conectados; GitHub pendiente OAuth; Supabase ya activo).
