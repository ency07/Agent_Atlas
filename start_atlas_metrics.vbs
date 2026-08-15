Set WshShell = WScript.CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")

' --- Config ---
ROOT = fso.GetParentFolderName(WScript.ScriptFullName)
PYTHON = ROOT & "\.venv\Scripts\python.exe"
SCRIPT = ROOT & "\atlas_metrics.py"
LOG_FILE = ROOT & "\logs\metrics_launcher.log"

' --- Log ---
Sub WriteLog(message)
    Dim logFile
    Set logFile = fso.OpenTextFile(LOG_FILE, 8, True)
    logFile.WriteLine "[" & Now & "] " & message
    logFile.Close
End Sub

' --- Ejecutar: ingesta + reporte semanal ---
On Error Resume Next
WriteLog "Iniciando ingesta y reporte de metricas..."
WshShell.Run """" & PYTHON & """ """ & SCRIPT & """ ingest", 0, False
WshShell.Run """" & PYTHON & """ """ & SCRIPT & """ report --period week --by-model", 0, False
If Err.Number <> 0 Then
    WriteLog "ERROR: " & Err.Description
Else
    WriteLog "Metricas iniciadas"
End If
On Error GoTo 0