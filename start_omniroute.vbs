' ============================================================
' start_omniroute.vbs — Lanza OmniRoute (proxy de modelos) sin consola.
' Replica el comando actual: node --max-old-space-size=4096 server-ws.mjs
' (default puerto 20128). Usado por tarea AtlasOmniRoute (ONLOGON).
' Invocacion:  wscript.exe start_omniroute.vbs
' ============================================================
Option Explicit
Dim WshShell, node, modulePath, args
Set WshShell = CreateObject("WScript.Shell")
' node del PATH (shim de npm usa node del sistema)
node = "node.exe"
modulePath = "C:\Users\Administrator\AppData\Roaming\npm\node_modules\omniroute\dist\server-ws.mjs"
args = "--max-old-space-size=4096 """ & modulePath & """"
' window style 0 = oculto; bWaitOnReturn = False (no bloquea)
WshShell.Run """" & node & """ " & args, 0, False