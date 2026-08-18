# ============================================================
# register_atlas_tasks.ps1 — Registra las tareas ONLOGON de Atlas
# ------------------------------------------------------------
# Crea/actualiza tareas programadas de Windows para los procesos
# de Atlas (overlay, orders, ui_manager).
# Uso:  powershell -ExecutionPolicy Bypass -File register_atlas_tasks.ps1
# ============================================================
$ErrorActionPreference = "Continue"
$ROOT = Split-Path -Parent $PSScriptRoot

$name1 = "AtlasOverlay"
$name2 = "AtlasOrders"
$name3 = "AtlasUIManager"

$tasks = @(
  @($name1, "start_atlas_overlay.vbs"),
  @($name2, "start_atlas_orders.vbs"),
  @($name3, "start_atlas_ui_manager.vbs")
)

foreach ($t in $tasks) {
    $taskName = $t[0]
    $vbs = $t[1]
    $vbsPath = Join-Path $ROOT $vbs
    if (-not (Test-Path $vbsPath)) {
        Write-Host "[SKIP] $taskName - falta $vbs" -ForegroundColor Yellow
        continue
    }
    $action = "wscript.exe `"$vbsPath`""
    $cmd = "schtasks /Create /TN `"$taskName`" /SC ONLOGON /RL LIMITED /F /TR `"$action`""
    & cmd /c $cmd | Out-Null
    if ($LASTEXITCODE -eq 0) {
        Write-Host "[OK]   $taskName registrada (ONLOGON)" -ForegroundColor Green
    } else {
        $msg = "[FAIL] " + $taskName + " no se pudo registrar (exit " + $LASTEXITCODE + ")"
        Write-Host $msg -ForegroundColor Red
    }
}
