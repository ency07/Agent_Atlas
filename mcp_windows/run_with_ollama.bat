@echo off
title MCP Windows AI - Controla Windows con IA Local
color 0A
chcp 65001 >nul

:: ==========================================================================
:: MCP Windows + Ollama
:: Controla Windows con IA Local desde CMD
:: ==========================================================================

:MENU
cls
echo ================================================================================
echo                         MCP WINDOWS AI - OLLAMA
echo                 Controla Windows con Inteligencia Artificial Local
echo ================================================================================
echo.
echo  [1] 🚀 Iniciar sesion interactiva (Windows + Archivos + Web + Memoria)
echo  [2] 🔧 Iniciar solo el servidor MCP Windows (modo debug)
echo  [3] 📥 Instalar/Actualizar dependencias
echo  [4] 🔍 Probar conexion con Ollama
echo  [5] 📋 Listar herramientas disponibles
echo  [6] 🔄 Instalar servidores MCP oficiales (filesystem, fetch)
echo  [7] 📖 Ver documentacion
echo  [0] Salir
echo.
set /p opcion="Selecciona una opcion: "

:: Extraer el primer carácter para permitir argumentos extra
set opcion_num=%opcion:~0,1%

if "%opcion_num%"=="1" goto START_INTERACTIVE
if "%opcion_num%"=="2" goto START_SERVER
if "%opcion_num%"=="3" goto INSTALL_DEPS
if "%opcion_num%"=="4" goto TEST_OLLAMA
if "%opcion_num%"=="5" goto LIST_TOOLS
if "%opcion_num%"=="6" goto INSTALL_OFFICIAL
if "%opcion_num%"=="7" goto SHOW_HELP
if "%opcion_num%"=="0" goto EOF
goto MENU

:START_INTERACTIVE
:: Extraer argumentos extra después del número
set EXTRA_ARGS=%opcion:~2%
if "%EXTRA_ARGS%"=="" set EXTRA_ARGS=%*
cls
echo.
echo ================================================================================
echo              INICIANDO SESION INTERACTIVA MCP + OLLAMA
echo ================================================================================
echo.
echo  Esta opcion inicia el cliente interactivo que conecta:
echo    - Ollama (modelos de IA local)
echo    - MCP Windows Server (control de Windows)
echo.
echo  Asegurate de que Ollama este ejecutandose (ollama serve)
echo  o simplemente abre otra terminal y ejecuta: ollama run llama3.2
echo.
echo  Para elegir otro modelo, usa: 0 1 --model llama3.2:latest
echo  Para modo automatico (sin aprobacion): 0 1 --auto
echo.
echo  Presiona Ctrl+C en cualquier momento para salir.
echo.
pause
cls
echo === INICIANDO ===
python mcp_ollama_client.py %EXTRA_ARGS%
if %errorlevel% neq 0 (
    echo.
    echo ⚠️  Error al iniciar el cliente.
    echo Asegurate de tener las dependencias instaladas (opcion 3).
    pause
)
goto MENU

:START_SERVER
cls
echo.
echo ================================================================================
echo              INICIANDO SERVIDOR MCP DE WINDOWS (MODO DEBUG)
echo ================================================================================
echo.
echo  Este modo inicia solo el servidor MCP para depuracion.
echo  Conectate desde cualquier cliente MCP (Claude Desktop, etc.)
echo  usando: python mcp_windows_server.py
echo.
pause
cls
echo === INICIANDO SERVIDOR MCP ===
python mcp_windows_server.py
pause
goto MENU

:INSTALL_DEPS
cls
echo.
echo ================================================================================
echo              INSTALANDO DEPENDENCIAS
echo ================================================================================
echo.
echo  Las siguientes dependencias son necesarias:
echo    - mcp (SDK de Model Context Protocol)
echo    - pyautogui (control de mouse/teclado)
echo    - pygetwindow (gestion de ventanas)
echo    - psutil (informacion del sistema)
echo    - pyperclip (portapapeles)
echo    - pywin32 (API nativa de Windows)
echo    - Pillow (procesamiento de imagenes)
echo    - requests (comunicacion con Ollama)
echo.
pause
cls
pip install -r requirements.txt
if %errorlevel% equ 0 (
    echo.
    echo ✅ Dependencias instaladas correctamente.
) else (
    echo.
    echo ⚠️  Hubo un error. Intentando con pip3...
    pip3 install -r requirements.txt
)
pause
goto MENU

:TEST_OLLAMA
cls
echo.
echo ================================================================================
echo              VERIFICANDO CONEXION CON OLLAMA
echo ================================================================================
echo.
echo  Verificando que Ollama este corriendo en http://localhost:11434...
echo.
python -c "
import requests
try:
    r = requests.get('http://localhost:11434/api/tags', timeout=5)
    if r.status_code == 200:
        models = r.json().get('models', [])
        print('✅ Ollama esta corriendo correctamente!')
        print(f'   Modelos disponibles: {len(models)}')
        for m in models:
            print(f'   - {m[\"name\"]}')
    else:
        print(f'❌ Respuesta inesperada: {r.status_code}')
except requests.ConnectionError:
    print('❌ No se pudo conectar a Ollama.')
    print('   Asegurate de que Ollama este instalado y ejecutandose.')
    print('   1. Descarga: https://ollama.com/download')
    print('   2. Ejecuta: ollama serve')
except Exception as e:
    print(f'❌ Error: {e}')
"
echo.
pause
goto MENU

:LIST_TOOLS
cls
echo.
echo ================================================================================
echo              HERRAMIENTAS DEL SERVIDOR MCP WINDOWS
echo ================================================================================
echo.
echo  🪟  GESTION DE VENTANAS
echo     list_windows     - Lista todas las ventanas abiertas
echo     focus_window     - Activa/enfoca una ventana
echo     move_window      - Mueve una ventana de posicion
echo     resize_window    - Redimensiona una ventana
echo     minimize_window  - Minimiza una ventana
echo     maximize_window  - Maximiza una ventana
echo     close_window     - Cierra una ventana
echo     get_active_window- Obtiene la ventana activa actual
echo.
echo  🖱️  CONTROL DE MOUSE
echo     mouse_move       - Mueve el cursor
echo     mouse_click      - Hace click
echo     mouse_scroll     - Hace scroll
echo     mouse_position   - Posicion actual del cursor
echo     mouse_drag       - Arrastra el mouse
echo.
echo  ⌨️  CONTROL DE TECLADO
echo     keyboard_type    - Escribe texto
echo     keyboard_hotkey  - Ejecuta atajos de teclado
echo     keyboard_press   - Presiona una tecla
echo.
echo  📁  OPERACIONES DE ARCHIVOS
echo     file_list       - Lista archivos en un directorio
echo     file_read       - Lee un archivo
echo     file_write      - Escribe/Crea un archivo
echo     file_delete     - Elimina un archivo/directorio
echo     file_copy       - Copia archivos/directorios
echo     folder_create   - Crea un directorio
echo.
echo  🔧  GESTION DE PROCESOS
echo     process_list    - Lista procesos en ejecucion
echo     process_kill    - Mata un proceso por PID
echo     process_start   - Inicia un programa
echo.
echo  ℹ️  INFORMACION DEL SISTEMA
echo     system_info     - Informacion detallada del sistema
echo     screenshot      - Toma captura de pantalla
echo     clipboard_get   - Obtiene el portapapeles
echo     clipboard_set   - Establece el portapapeles
echo     open_url        - Abre URL en el navegador
echo     run_command     - Ejecuta comando en CMD
echo     volume_set      - Ajusta el volumen del sistema
echo     get_wifi_info   - Informacion de WiFi
echo.
echo  📋  REGISTRO
echo     registry_read   - Lee el registro de Windows
echo.
echo  🔔  NOTIFICACIONES
echo     notify          - Muestra notificacion del sistema
echo.
pause
goto MENU

:SHOW_HELP
cls
echo.
echo ================================================================================
echo           GUIA RAPIDA - MCP WINDOWS AI
echo ================================================================================
echo.
echo  REQUISITOS:
echo    1. Python 3.10+ instalado
echo    2. Ollama instalado (https://ollama.com/download)
echo    3. Un modelo de IA descargado (ej: llama3.2, mistral, qwen2.5)
echo.
echo  INSTALACION RAPIDA:
echo    1. Ejecuta este batch
echo    2. Selecciona opcion 3 (Instalar dependencias)
echo    3. Selecciona opcion 4 (Probar conexion Ollama)
echo    4. Selecciona opcion 1 (Iniciar sesion interactiva)
echo.
echo  EJEMPLOS DE USO:
echo    - "Abre el bloc de notas y escribe 'Hola Mundo'"
echo    - "Lista los archivos del escritorio"
echo    - "¿Cuanta memoria RAM tiene mi PC?"
echo    - "Crea una carpeta llamada proyectos en el escritorio"
echo    - "Ejecuta ipconfig en la terminal"
echo    - "Saca una captura de pantalla"
echo    - "Cierra todas las ventanas del navegador"
echo.
echo  COMPATIBILIDAD CON CLAUDE DESKTOP:
echo    Si usas Claude Desktop, configura el MCP server en:
echo    %APPDATA%\Claude\claude_desktop_config.json
echo    Usando: python mcp_windows_server.py
echo.
echo  MODELOS RECOMENDADOS PARA OLLAMA:
echo    - llama3.2        (bueno para funciones)
echo    - mistral         (rapido y ligero)
echo    - qwen2.5:7b      (excelente en function calling)
echo    - deepseek-r1:8b  (buen razonamiento)
echo.
pause
goto MENU

:INSTALL_OFFICIAL
cls
echo.
echo ================================================================================
echo              INSTALANDO SERVIDORES MCP OFICIALES
echo ================================================================================
echo.
echo  Esto instalara los servidores MCP oficiales via npx:
echo    - @modelcontextprotocol/server-filesystem  (archivos)
echo    - @modelcontextprotocol/server-fetch       (web)
echo.
echo  Nota: npx descarga automaticamente al ejecutar,
echo  pero podemos precargarlos ahora.
echo.
pause
cls
echo.
echo ================================================================================
echo              SERVIDORES MCP OFICIALES
echo ================================================================================
echo.
echo  Los servidores oficiales se descargan automaticamente via npx
echo  la primera vez que se usan (opcion 1).
echo.
echo  Servidores configurados:
echo    - @modelcontextprotocol/server-filesystem  (archivos)
echo    - @modelcontextprotocol/server-fetch       (web)
echo.
echo  No es necesario instalarlos manualmente.
echo.
echo  Para USARLOS simplemente inicia la sesion interactiva (opcion 1)
echo  y el Multi-Server Manager los lanzara automaticamente.
echo.
pause
goto MENU

:EOF
cls
echo.
echo Gracias por usar MCP Windows AI!
echo.
exit /b 0
