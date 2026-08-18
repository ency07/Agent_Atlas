@echo off
setlocal
cd /d "E:\Agente_IA"
start "Atlas MCP Daemon" /D "E:\Agente_IA" pythonw atlas_mcp_daemon.py
endlocal
exit /b 0
