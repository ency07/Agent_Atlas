Set WshShell = WScript.CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")

' --- Config ---
ROOT = "E:\Agente_IA"
PYTHON = ROOT & "\.venv\Scripts\python.exe"
SCRIPT = ROOT & "\atlas_bootcheck.py"
LOG = ROOT & "\logs\bootcheck_launcher.log"

' --- Log ---
Sub Log(message)
    Dim logFile
    Set logFile = fso.OpenTextFile(LOG, 8, True)
    logFile.WriteLine "[" & Now & "] " & message
    logFile.Close
End Sub

' --- Ejecutar ---
On Error Resume Next
Log "Iniciando boot check..."
WshShell.Run """" & PYTHON & """ """ & SCRIPT & """", 0, False
If Err.Number <> 0 Then
    Log "ERROR: " & Err.Description
Else
    Log "Boot check iniciado"
End If
On Error GoTo 0