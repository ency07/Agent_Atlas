@echo off
setlocal
cd /d "E:\Agente_IA"
start "Atlas Supervisor" /D "E:\Agente_IA" pythonw atlas_supervisor.py
endlocal
exit /b 0
