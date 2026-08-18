' ============================================================
' start_atlas_orders.vbs — Lanza el drenador de órdenes Atlas sin consola.
' Usa pythonw.exe del .venv del proyecto (creado por setup.ps1).
' Invocacion:  wscript.exe start_atlas_orders.vbs
' ============================================================
Option Explicit
Dim WshShell, root, pythonw, script, cmd
Set WshShell = CreateObject("WScript.Shell")
root = CreateObject("Scripting.FileSystemObject").GetParentFolderName(WScript.ScriptFullName)
pythonw = root & "\.venv\Scripts\pythonw.exe"
script = root & "\atlas_orders.py"

If CreateObject("Scripting.FileSystemObject").FileExists(pythonw) Then
    cmd = """" & pythonw & """ """ & script & """"
Else
    cmd = "pythonw """ & script & """"
End If

WshShell.Run cmd, 0, False
