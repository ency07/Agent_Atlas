@echo off
title Atlas - Iniciar Todo
call "%~dp0start_dashboard.bat"
call "%~dp0start_chat.bat"
call "%~dp0start_activity.bat"
call "%~dp0start_supervisor.bat"
call "%~dp0start_mcp.bat"
echo Todos los componentes lanzados.
endlocal
exit /b 0
