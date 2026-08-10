' ============================================================
' start_atlas_chat.vbs — Lanza el chat flotante Atlas sin consola.
' Usa pythonw.exe del .venv del proyecto (creado por setup.ps1).
' Invocacion:  wscript.exe start_atlas_chat.vbs
' ============================================================
Option Explicit
Dim WshShell, root, pythonw, script, cmd
Set WshShell = CreateObject("WScript.Shell")
root = CreateObject("Scripting.FileSystemObject").GetParentFolderName(WScript.ScriptFullName)
pythonw = root & "\.venv\Scripts\pythonw.exe"
script = root & "\atlas_chat.py"

If CreateObject("Scripting.FileSystemObject").FileExists(pythonw) Then
    cmd = """" & pythonw & """ """ & script & """"
Else
    ' fallback: python del PATH (si no hay .venv, ej. antes de setup.ps1)
    cmd = "pythonw """ & script & """"
End If

' window style 0 = oculto; bWaitOnReturn = False (no bloquea)
WshShell.Run cmd, 0, False
