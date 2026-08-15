Set WshShell = WScript.CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")

' --- Config ---
ROOT = fso.GetParentFolderName(WScript.ScriptFullName)
PYTHON = ROOT & "\.venv\Scripts\python.exe"
SCRIPT = ROOT & "\atlas_bootcheck.py"
LOG_FILE = ROOT & "\logs\bootcheck_launcher.log"

' --- Log ---
Sub WriteLog(message)
    Dim logFile
    Set logFile = fso.OpenTextFile(LOG_FILE, 8, True)
    logFile.WriteLine "[" & Now & "] " & message
    logFile.Close
End Sub

' --- Ejecutar ---
On Error Resume Next
WriteLog "Iniciando boot check..."
WshShell.Run """" & PYTHON & """ """ & SCRIPT & """", 0, False
If Err.Number <> 0 Then
    WriteLog "ERROR: " & Err.Description
Else
    WriteLog "Boot check iniciado"
End If
On Error GoTo 0