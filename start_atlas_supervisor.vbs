Set WshShell = WScript.CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")

' --- Config ---
ROOT = fso.GetParentFolderName(WScript.ScriptFullName)
PYTHON = ROOT & "\.venv\Scripts\python.exe"
SCRIPT = ROOT & "\atlas_supervisor.py"
LOG_FILE = ROOT & "\logs\supervisor_launcher.log"

' --- Log ---
Sub WriteLog(message)
    Dim logFile
    Set logFile = fso.OpenTextFile(LOG_FILE, 8, True)
    logFile.WriteLine "[" & Now & "] " & message
    logFile.Close
End Sub

' --- Ejecutar ---
On Error Resume Next
WriteLog "Iniciando supervisor..."
WshShell.Run """" & PYTHON & """ """ & SCRIPT & """", 0, False
If Err.Number <> 0 Then
    WriteLog "ERROR: " & Err.Description
    WScript.Echo "Error al iniciar supervisor: " & Err.Description
Else
    WriteLog "Supervisor iniciado"
End If
On Error GoTo 0
