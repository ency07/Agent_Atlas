Set WshShell = WScript.CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")

' --- Config ---
ROOT = fso.GetParentFolderName(WScript.ScriptFullName)
PYTHON = ROOT & "\.venv\Scripts\python.exe"
SCRIPT = ROOT & "\atlas_backup_encrypted.py"
LOG_FILE = ROOT & "\logs\encrypted_backup_launcher.log"

' --- Clave pública (configurable) ---
' Si existe backups_encrypted_recipient.txt la lee; si no, intenta leerla de .age_keys/public_key.txt
PUB_KEY = ""
recipient_file = ROOT & "\backups_encrypted_recipient.txt"
If fso.FileExists(recipient_file) Then
    PUB_KEY = Trim(fso.OpenTextFile(recipient_file, 1).ReadAll)
Else
    key_file = ROOT & "\.age_keys\public_key.txt"
    If fso.FileExists(key_file) Then
        PUB_KEY = Trim(fso.OpenTextFile(key_file, 1).ReadAll)
    End If
End If

' --- Log ---
Sub WriteLog(message)
    Dim logFile
    Set logFile = fso.OpenTextFile(LOG_FILE, 8, True)
    logFile.WriteLine "[" & Now & "] " & message
    logFile.Close
End Sub

' --- Ejecutar ---
On Error Resume Next
If PUB_KEY = "" Then
    WriteLog "ERROR: no hay clave pública. Genera primero: python atlas_backup_encrypted.py generate"
    WScript.Quit 1
End If

WriteLog "Iniciando backup cifrado..."
WshShell.Run """" & PYTHON & """ """ & SCRIPT & """ backup --recipient """ & PUB_KEY & """ --out-dir backups_encrypted --keep 14", 0, False
If Err.Number <> 0 Then
    WriteLog "ERROR: " & Err.Description
Else
    WriteLog "Backup cifrado iniciado"
End If
On Error GoTo 0