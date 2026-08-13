' ============================================================
' start_atlas_web.vbs — Lanza el dashboard web de Atlas sin consola.
' Usa pythonw.exe del .venv del proyecto (creado por setup.ps1).
' Invocacion:  wscript.exe start_atlas_web.vbs
' ============================================================
Option Explicit
Dim fso, root, pythonw, host
Set fso = CreateObject("Scripting.FileSystemObject")
root = fso.GetParentFolderName(WScript.ScriptFullName)
pythonw = root & "\.venv\Scripts\pythonw.exe"
host = WScript.Arguments.Named("host")
If host = "" Then host = "127.0.0.1"
If Not fso.FileExists(pythonw) Then
    WScript.Echo "No existe " & pythonw & ". Corre setup.ps1 primero."
    WScript.Quit 1
End If
CreateObject("WScript.Shell").Run """" & pythonw & """ """ & root & "\atlas_web_server.py"" --port 4100", 0, False