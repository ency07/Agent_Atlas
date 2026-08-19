<#
.SYNOPSIS
Rollback automatizado AEGIS-JARVIS HUD usando rollback_config.json
#>
param(
    [string]$ConfigPath = "E:\Agente_IA\aegis_hud\rollback_config.json"
)

if (-not (Test-Path $ConfigPath)) {
    Write-Error "No existe $ConfigPath"
    exit 1
}

$cfg = Get-Content $ConfigPath | ConvertFrom-Json

Write-Host "Iniciando rollback a $cfg.git_tag..."

# 1. Detener procesos HUD
Get-Process | Where-Object {$_.Path -like "*aegis_hud*"} | Stop-Process -Force -ErrorAction SilentlyContinue

# 2. Restaurar git
cd $cfg.project_root
git reset --hard $cfg.git_tag
git clean -fd

# 3. Restaurar memory_data
if (Test-Path $cfg.backup_dir) {
    Remove-Item "$cfg.project_root\memory_data" -Recurse -Force -ErrorAction SilentlyContinue
    Copy-Item "$cfg.backup_dir\memory_data" "$cfg.project_root\memory_data" -Recurse -Force
    Write-Host "memory_data restaurado desde $cfg.backup_dir"
}

# 4. Limpiar whitelist guardian (opcional, manual)
Write-Host "Revisar whitelist guardian manualmente:"
Write-Host "  atlas-guardian_guardian_remove_whitelist --cmd uvicorn.exe --list_type binaries"
Write-Host "  atlas-guardian_guardian_remove_whitelist --cmd uvicorn.exe --list_type processes"

Write-Host "Rollback completado"