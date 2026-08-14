Set WshShell = WScript.CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")

' --- Config ---
ROOT = "E:\Agente_IA"
PYTHON = ROOT & "\.venv\Scripts\python.exe"
SCRIPT = ROOT & "\atlas_benchmark.py"
LOG = ROOT & "\logs\benchmark_launcher.log"

' --- Log ---
Sub Log(message)
    Dim logFile
    Set logFile = fso.OpenTextFile(LOG, 8, True)
    logFile.WriteLine "[" & Now & "] " & message
    logFile.Close
End Sub

' --- Ejecutar (3 rondas) ---
On Error Resume Next
Log "Iniciando benchmark de proveedores (3 rondas)..."
WshShell.Run """" & PYTHON & """ """ & SCRIPT & """ --repeat 3", 0, False
If Err.Number <> 0 Then
    Log "ERROR: " & Err.Description
Else
    Log "Benchmark iniciado"
End If
On Error GoTo 0