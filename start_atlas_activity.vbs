' ============================================================
' start_atlas_activity.vbs — Lanza el daemon de actividad Atlas sin consola.
' Usa pythonw.exe del .venv del proyecto (creado por setup.ps1).
' El daemon incluye la bandeja de sistema (pystray).
' Invocacion:  wscript.exe start_atlas_activity.vbs
' ============================================================
Option Explicit
Dim WshShell, root, pythonw, script, cmd
Set WshShell = CreateObject("WScript.Shell")
root = CreateObject("Scripting.FileSystemObject").GetParentFolderName(WScript.ScriptFullName)
pythonw = root & "\.venv\Scripts\pythonw.exe"
script = root & "\atlas_activity.py"

If CreateObject("Scripting.FileSystemObject").FileExists(pythonw) Then
    cmd = """" & pythonw & """ """ & script & """"
Else
    ' fallback: pythonw del PATH (si no hay .venv, ej. antes de setup.ps1)
    cmd = "pythonw """ & script & """"
End If

' window style 0 = oculto; bWaitOnReturn = False (no bloquea)
WshShell.Run cmd, 0, False
