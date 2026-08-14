Set WshShell = WScript.CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")

' --- Config ---
ROOT = "E:\Agente_IA"
PYTHON = ROOT & "\.venv\Scripts\python.exe"
SCRIPT = ROOT & "\atlas_sync_capabilities.py"
LOG = ROOT & "\logs\sync_capabilities_launcher.log"

' --- Log ---
Sub Log(message)
    Dim logFile
    Set logFile = fso.OpenTextFile(LOG, 8, True)
    logFile.WriteLine "[" & Now & "] " & message
    logFile.Close
End Sub

' --- Ejecutar ---
On Error Resume Next
Log "Iniciando sync de capacidades..."
WshShell.Run """" & PYTHON & """ """ & SCRIPT & """", 0, False
If Err.Number <> 0 Then
    Log "ERROR: " & Err.Description
Else
    Log "Sync de capacidades iniciado"
End If
On Error GoTo 0