' ============================================================
' start_atlas_backup.vbs — Ejecuta backup de Atlas sin consola.
' Se ejecuta via Windows Task Scheduler (diario).
' Uso manual:  wscript.exe start_atlas_backup.vbs
' ============================================================
Option Explicit
Dim WshShell, root, pythonw, script, cmd
Set WshShell = CreateObject("WScript.Shell")
root = CreateObject("Scripting.FileSystemObject").GetParentFolderName(WScript.ScriptFullName)
pythonw = root & "\.venv\Scripts\python.exe"
script = root & "\mcp_memory_server.py"

' Ejecuta --cli backup; no bloquea
cmd = """" & pythonw & """ """ & script & """ --cli backup"
WshShell.Run cmd, 0, False
