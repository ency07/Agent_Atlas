Set WshShell = WScript.CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")

' --- Config ---
ROOT = "E:\Agente_IA"
PYTHON = ROOT & "\.venv\Scripts\python.exe"
SCRIPT = ROOT & "\atlas_metrics.py"
LOG = ROOT & "\logs\metrics_launcher.log"

' --- Log ---
Sub Log(message)
    Dim logFile
    Set logFile = fso.OpenTextFile(LOG, 8, True)
    logFile.WriteLine "[" & Now & "] " & message
    logFile.Close
End Sub

' --- Ejecutar: ingesta + reporte semanal ---
On Error Resume Next
Log "Iniciando ingesta y reporte de metricas..."
WshShell.Run """" & PYTHON & """ """ & SCRIPT & """ ingest", 0, False
WshShell.Run """" & PYTHON & """ """ & SCRIPT & """ report --period week --by-model", 0, False
If Err.Number <> 0 Then
    Log "ERROR: " & Err.Description
Else
    Log "Metricas iniciadas"
End If
On Error GoTo 0