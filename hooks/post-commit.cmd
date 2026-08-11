@echo off
rem ============================================================
rem post-commit.cmd — Atlas git hook (portable, versionado)
rem Registra en inbox/ un evento 'commit' tras cada commit.
rem Se activa via:  git config core.hooksPath hooks
rem
rem Robusto: nunca bloquea el commit (el hook falla en silencio,
rem y memory_health detecta el backlog del inbox).
rem ============================================================
setlocal

rem --- root del repo (la carpeta que contiene .git) ---
for /f "delims=" %%R in ('git rev-parse --show-toplevel 2^>nul') do set "ROOT=%%R"
if not defined ROOT exit /b 0

set "PY=%ROOT%\.venv\Scripts\python.exe"
if not exist "%PY%" exit /b 0

rem --- datos del ultimo commit (hash + mensaje) ---
for /f "delims=" %%H in ('git rev-parse --short HEAD 2^>nul') do set "HASH=%%H"
set "MSG="
for /f "usebackq delims=" %%M in (`git log -1 --format=%%s 2^>nul`) do set "MSG=%%M"

rem --- archivos tocados en el commit (csv, corto) ---
set "FILES="
for /f "usebackq delims=" %%F in (`git diff-tree --no-commit-id --name-only -r HEAD 2^>nul`) do call :addfile "%%F"
if defined FILES set "FILES=%FILES:~0,-1%"

rem --- escribir el evento (no bloquea si falla) ---
"%PY%" "%ROOT%\mcp_memory_server.py" --git agente_ia "%HASH%" "%MSG%" "%FILES%" >nul 2>&1
exit /b 0

:addfile
set "FILES=%FILES%%~1,"
exit /b 0
