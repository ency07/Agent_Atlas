Launchers de Atlas
===================

Carpeta con accesos directos (archivos .bat) para lanzar cada componente de Atlas con doble clic.
Ninguno abre ventana de consola (usan pythonw, sin ventana). El dashboard ademas abre el navegador solo.

Archivos:
- start_all.bat          -> Lanza TODOS los componentes a la vez.
- start_dashboard.bat    -> Dashboard web + API en http://127.0.0.1:4100 (abre el navegador).
- start_chat.bat         -> Ventana flotante de chat (Atlas Chat).
- start_activity.bat     -> Daemon de actividad (captura ventana activa cada 10s).
- start_supervisor.bat   -> Supervisor de auto-reparacion.
- start_mcp.bat          -> MCP Daemon persistente (MCPs calientes, sin cold-start).

Uso:
  1. Abre esta carpeta (E:\Agente_IA\Launchers).
  2. Haz doble clic en el .bat que necesites.
  3. No aparece ninguna ventana: el proceso corre en segundo plano.
  4. Para detener un componente, cierra su proceso desde el Administrador de tareas
     (ej. pythonw.exe con atlas_web_server.py) o reinicia el equipo.

Notas:
- Usan 'pythonw' que en PATH es el Python correcto (hermes-agent venv, Python 3.11) con todas las dependencias.
- El .venv del proyecto (E:\Agente_IA\.venv) NO funciona y NO se usa en estos launchers.
- Si ya hay una instancia corriendo (ej. opencode serve en puerto 4096), los scripts la reutilizan.
- Para produccion, las tareas programadas de Windows ya arrancan los daemons al logon;
  estos .bat son para arranque manual / pruebas.
