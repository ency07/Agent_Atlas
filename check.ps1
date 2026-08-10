# ============================================================
# check.ps1 — Diagnostico del ecosistema Atlas
# Uso:  powershell -ExecutionPolicy Bypass -File check.ps1
# Devuelve 0 si todo ok, 1 si hay algo roto (los detalles se imprimen).
# ============================================================
$ErrorActionPreference = "Continue"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$fails = 0
function Report($ok, $msg) {
    if ($ok) { Write-Host "  [OK]   $msg" -ForegroundColor Green }
    else { Write-Host "  [FAIL] $msg" -ForegroundColor Red; $script:fails++ }
}

$ROOT = $PSScriptRoot
Write-Host "==> Diagnostico Atlas en: $ROOT" -ForegroundColor Cyan

# ---------- Herramientas ----------
Write-Host "`n[Herramientas]"
Report ([bool](Get-Command node -ErrorAction SilentlyContinue)) "node (npm)"
Report ([bool](Get-Command opencode -ErrorAction SilentlyContinue)) "opencode CLI"
Report ([bool](Get-Command python -ErrorAction SilentlyContinue)) "python en PATH"

# ---------- Puerto omniroute (proveedor de modelos, opcional) ----------
Write-Host "`n[Proveedor de modelos]"
$omniroute = Test-NetConnection -ComputerName 127.0.0.1 -Port 20128 -WarningAction SilentlyContinue
Report ($omniroute.TcpTestSucceeded) "omniroute localhost:20128 (proveedor auto/*)"

# ---------- Entorno Python ----------
Write-Host "`n[Entorno Python]"
$pyBin = Join-Path $ROOT ".venv\Scripts\python.exe"
if (Test-Path $pyBin) {
    Report $true "venv presente: $pyBin"
    $mcp = & $pyBin -c "import mcp; print('ok')" 2>$null
    Report ($mcp -match "ok") "paquete 'mcp' instalado en el venv"
    $gitmcp = & $pyBin -m pip show mcp-server-git 2>$null
    Report ($gitmcp -match "Name") "paquete 'mcp-server-git'"
    $wv = & $pyBin -c "import webview; print('ok')" 2>$null
    Report ($wv -match "ok") "paquete 'pywebview' (chat flotante F2)"
} else {
    Report $false "venv en $pyBin (corre setup.ps1)"
}

# ---------- Server de memoria ----------
Write-Host "`n[Server de memoria]"
$serverPy = Join-Path $ROOT "mcp_memory_server.py"
if (Test-Path $serverPy) {
    Report $true "mcp_memory_server.py presente"
    $health = & $pyBin $serverPy --cli health 2>&1
    Report ($health -match "ok|OK|healthy") "memory_health: $health"
} else {
    Report $false "faltan archivos del proyecto"
}

# ---------- Config opencode ----------
Write-Host "`n[Config opencode]"
$cfg = Join-Path $env:USERPROFILE ".config\opencode\opencode.jsonc"
if (Test-Path $cfg) {
    $raw = Get-Content $cfg -Raw
    Report (-not $raw.Contains("%%")) "opencode.jsonc generado sin placeholders pendientes"
    Report ($raw -match "memory") "MCP memory declarado en opencode.jsonc"
} else {
    Report $false "opencode.jsonc no existe en $cfg (corre setup.ps1)"
}

Write-Host "`n"
if ($fails -eq 0) {
    Write-Host "==> TODO OK." -ForegroundColor Green
    exit 0
} else {
    Write-Host "==> $fails punto(s) con fallo. Revisa docs/TROUBLESHOOTING.md" -ForegroundColor Red
    exit 1
}
