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
if (-not (Test-Path $pyBin)) {
    # fallback: python del PATH (util antes de correr setup.ps1)
    $pyInPath = Get-Command python -ErrorAction SilentlyContinue
    if ($pyInPath) { $pyBin = $pyInPath.Source }
}
if (Test-Path $pyBin) {
    $isVenv = $pyBin -like "*.venv*"
    Report $true "$(if ($isVenv) {'venv presente'} else {'python del PATH (sin .venv, corre setup.ps1)'}): $pyBin"
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

# ---------- Git hook (F1) ----------
Write-Host "`n[Git hook F1]"
Push-Location $ROOT
$hookPath = git config --get core.hooksPath 2>$null
Pop-Location
Report ($hookPath -eq "hooks") "core.hooksPath = $hookPath"
Report (Test-Path (Join-Path $ROOT "hooks\post-commit")) "hooks/post-commit existe"

# ---------- Backup (F1) ----------
Write-Host "`n[Backup F1]"
$taskBk = Get-ScheduledTask -TaskName "AtlasBackup" -ErrorAction SilentlyContinue
Report ($null -ne $taskBk) "tarea AtlasBackup en Task Scheduler"
Report (Test-Path (Join-Path $ROOT "start_atlas_backup.vbs")) "start_atlas_backup.vbs existe"
$bkCount = (Get-ChildItem (Join-Path $ROOT "memory_data\backup\atlas_*.zip") -ErrorAction SilentlyContinue).Count
Report ($bkCount -gt 0) "backups existentes: $bkCount"

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

# ---------- Chat flotante (F2) ----------
Write-Host "`n[Chat flotante F2]"
Report (Test-Path (Join-Path $ROOT "atlas_chat.py")) "atlas_chat.py presente"
Report (Test-Path (Join-Path $ROOT "start_atlas_chat.vbs")) "start_atlas_chat.vbs presente"
$f2 = Test-NetConnection -ComputerName 127.0.0.1 -Port 4096 -WarningAction SilentlyContinue
if ($f2.TcpTestSucceeded) {
    Report $true "opencode serve activo en 127.0.0.1:4096"
} else {
    Report $true "opencode serve 127.0.0.1:4096 apagado (normal si el chat no esta abierto)"
}

Write-Host "`n"
if ($fails -eq 0) {
    Write-Host "==> TODO OK." -ForegroundColor Green
    exit 0
} else {
    Write-Host "==> $fails punto(s) con fallo. Revisa docs/TROUBLESHOOTING.md" -ForegroundColor Red
    exit 1
}
