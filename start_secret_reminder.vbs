' ============================================================
' start_secret_reminder.vbs — Recordatorio semanal de rotacion de secretos.
' Solo muestra un aviso si la rotacion esta vencida (90 dias).
' Invocacion:  wscript.exe start_secret_reminder.vbs
' ============================================================
Option Explicit
Dim WshShell, root, pythonw, script, cmd
Set WshShell = CreateObject("WScript.Shell")
root = CreateObject("Scripting.FileSystemObject").GetParentFolderName(WScript.ScriptFullName)
pythonw = root & "\.venv\Scripts\pythonw.exe"
script = root & "\atlas_secret_reminder.py"

If CreateObject("Scripting.FileSystemObject").FileExists(pythonw) Then
    cmd = """" & pythonw & """ """ & script & """"
Else
    cmd = "pythonw """ & script & """"
End If

' window style 0 = oculto; bWaitOnReturn = True (espera el resultado)
WshShell.Run cmd, 0, True
