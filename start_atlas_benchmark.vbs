Set WshShell = WScript.CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")

' --- Config ---
ROOT = fso.GetParentFolderName(WScript.ScriptFullName)
PYTHON = ROOT & "\.venv\Scripts\python.exe"
SCRIPT = ROOT & "\atlas_benchmark.py"
LOG_FILE = ROOT & "\logs\benchmark_launcher.log"

' --- Log ---
Sub WriteLog(message)
    Dim logFile
    Set logFile = fso.OpenTextFile(LOG_FILE, 8, True)
    logFile.WriteLine "[" & Now & "] " & message
    logFile.Close
End Sub

' --- Ejecutar (3 rondas) ---
On Error Resume Next
WriteLog "Iniciando benchmark de proveedores (3 rondas)..."
WshShell.Run """" & PYTHON & """ """ & SCRIPT & """ --repeat 3", 0, False
If Err.Number <> 0 Then
    WriteLog "ERROR: " & Err.Description
Else
    WriteLog "Benchmark iniciado"
End If
On Error GoTo 0