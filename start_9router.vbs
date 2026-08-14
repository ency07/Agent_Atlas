' ============================================================
' start_9router.vbs — Lanza 9Router (proxy de modelos) sin consola.
' Corre en puerto 4000 (evita conflicto con OmniRoute :20128).
' Invocacion:  wscript.exe start_9router.vbs
' ============================================================
Option Explicit
Dim WshShell, npmCmd, args
Set WshShell = CreateObject("WScript.Shell")
' shim npm 9router.cmd (node global)
npmCmd = "C:\Users\Administrator\AppData\Roaming\npm\9router.cmd"
args = "--port 4000 --host 127.0.0.1 --no-browser --tray --skip-update"
' window style 0 = oculto; bWaitOnReturn = False (no bloquea)
WshShell.Run """" & npmCmd & """ " & args, 0, False