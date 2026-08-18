@echo off
setlocal
cd /d "E:\Agente_IA"
start "Atlas Dashboard" /D "E:\Agente_IA" pythonw atlas_web_server.py --port 4100
start "" powershell -WindowStyle Hidden -NoProfile -Command "Start-Sleep -Seconds 3; Start-Process 'http://127.0.0.1:4100'"
endlocal
exit /b 0
