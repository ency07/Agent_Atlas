<# 
.SYNOPSIS
Instalador AEGIS-JARVIS HUD - Capa visual para ecosistema Atlas MCP
.REQUIREMENTS
- Windows 10/11, PowerShell 5.1+
- Python 3.10+ en PATH
- Acceso a E:\Agente_IA (ecosistema Atlas base)
#>

param(
    [string]$ProjectRoot = "E:\Agente_IA",
    [string]$HudDir = "E:\Agente_IA\aegis_hud",
    [switch]$ForceReinstall
)

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"

Write-Host "============================================================"
Write-Host "         AEGIS-JARVIS HUD INSTALADOR v1.0.0"
Write-Host "============================================================"

# --- 1. Verificaciones previas ---
Write-Host "`n[1/6] Verificando prerrequisitos..."

$pythonPath = (Get-Command python -ErrorAction SilentlyContinue).Source
if (-not $pythonPath) { $pythonPath = (Get-Command python3 -ErrorAction SilentlyContinue).Source }
if (-not $pythonPath) {
    Write-Error "Python no encontrado en PATH. Instala Python 3.10+ desde python.org"
    exit 1
}
$pyVersion = python --version 2>&1
Write-Host "  Python: $pyVersion"

$uvPath = (Get-Command uv -ErrorAction SilentlyContinue).Source
$useUv = $null -ne $uvPath
if ($useUv) { Write-Host "  uv detectado: $uvPath" }
else { Write-Host "  uv no encontrado, usando venv estandar" }

# Verificar que el ecosistema Atlas existe
if (-not (Test-Path "$ProjectRoot\memory_data")) {
    Write-Error "No se detecta ecosistema Atlas en $ProjectRoot"
    exit 1
}
Write-Host "  Ecosistema Atlas detectado"

# --- 2. Crear entorno virtual aislado ---
Write-Host "`n[2/6] Creando entorno virtual en $HudDir\.venv..."

if (Test-Path "$HudDir\.venv") {
    if ($ForceReinstall) {
        Write-Host "  Eliminando .venv anterior..."
        Remove-Item "$HudDir\.venv" -Recurse -Force -ErrorAction SilentlyContinue
    } else {
        Write-Host "  .venv ya existe. Usa -ForceReinstall para recrear."
    }
}

if (-not (Test-Path "$HudDir\.venv")) {
    if ($useUv) {
        & uv venv "$HudDir\.venv" --python $pythonPath
    } else {
        & $pythonPath -m venv "$HudDir\.venv"
    }
    Write-Host "  Entorno virtual creado"
}

# --- 3. Instalar dependencias ---
Write-Host "`n[3/6] Instalando dependencias..."

$packages = @(
    "pyqt6==6.6.1",
    "fastapi==0.111.0",
    "uvicorn[standard]==0.30.1",
    "pydantic==2.7.4",
    "pydantic-settings==2.3.3",
    "requests==2.32.3",
    "python-dotenv==1.0.1",
    "psutil==5.9.8"
)

foreach ($pkg in $packages) {
    Write-Host "  Instalando $pkg..."
    if ($useUv) {
        & uv pip install --python "$HudDir\.venv\Scripts\python.exe" $pkg
    } else {
        & "$HudDir\.venv\Scripts\pip.exe" install $pkg
    }
}
Write-Host "  Dependencias instaladas"

# --- 4. Generar .env si no existe ---
Write-Host "`n[4/6] Configurando variables de entorno..."

$envFile = "$HudDir\.env"
if (-not (Test-Path $envFile)) {
    $envContent = @"
# AEGIS-JARVIS HUD Configuration
ATLAS_ORCHESTRATOR_URL=http://localhost:20128
ATLAS_GUARDIAN_URL=http://localhost:20129
ATLAS_HEALTH_URL=http://localhost:20130
ATLAS_FOCO_URL=http://localhost:20131
ATLAS_SEARCH_URL=http://localhost:20132
MEMORY_MCP_URL=http://localhost:20133
CORAL_DRAW_MCP_URL=http://localhost:20134
PLAYWRIGHT_MCP_URL=http://localhost:20135
WINDOWS_MCP_URL=http://localhost:20136
SUPABASE_MCP_URL=http://localhost:20137
HUD_HOST=127.0.0.1
HUD_PORT=8765
HUD_LOG_LEVEL=INFO
"@
    $envContent | Set-Content $envFile -Encoding UTF8
    Write-Host "  .env creado"
} else {
    Write-Host "  .env ya existe, se omite"
}

# --- 5. Verificar instalación ---
Write-Host "`n[5/6] Verificando instalación..."

& "$HudDir\.venv\Scripts\python.exe" -c "import PyQt6, fastapi, uvicorn, pydantic, requests; print('Todos los imports OK')"
if ($LASTEXITCODE -ne 0) {
    Write-Error "Fallo verificacion de imports"
    exit 1
}

# --- 6. Verificar archivos auxiliares ---
Write-Host "`n[6/6] Verificando archivos auxiliares..."
$auxFiles = @("rollback_config.json", "rollback.ps1", "docs\DEBT.md", "run_hud.ps1")
foreach ($f in $auxFiles) {
    if (Test-Path "$HudDir\$f") { Write-Host "  OK: $f" }
    else { Write-Host "  FALTA: $f" }
}

# Reporte final
Write-Host "`n============================================================"
Write-Host "           INSTALACION COMPLETADA EXITOSAMENTE"
Write-Host "============================================================"

Write-Host "`nUbicacion HUD: $HudDir"
Write-Host "Python: $HudDir\.venv\Scripts\python.exe"
Write-Host "Para ejecutar: .\run_hud.ps1"

Write-Host "`nACCION REQUERIDA: Anadir a atlas-guardian whitelist"
Write-Host "Ejecuta ESTOS comandos en tu terminal Atlas:"

$newBinaries = @("uvicorn.exe", "python.exe")
$newProcesses = @("python.exe", "uvicorn.exe")

foreach ($bin in $newBinaries) {
    Write-Host "  atlas-guardian_guardian_add_whitelist --cmd $bin --list_type binaries"
}
foreach ($proc in $newProcesses) {
    Write-Host "  atlas-guardian_guardian_add_whitelist --cmd $proc --list_type processes"
}

Write-Host "`nDirectorios permitidos a anadir:"
Write-Host "  atlas-guardian_guardian_add_allowed_dir --path $HudDir"
Write-Host "  atlas-guardian_guardian_add_allowed_dir --path $HudDir\.venv"