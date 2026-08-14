<#
.SYNOPSIS
Test que verifica que la generacion de opencode.jsonc (usada por setup.ps1
via scripts\New-OpencodeConfig.ps1) SIEMPRE produce JSONC valido.

Cubre los escenarios:
  A. 3 providers (omniroute + 9router + ollama) + mcp_windows detectado
  B. Solo ollama (fallback) sin mcp_windows
  C. Regresion de la coma: el bloque "provider" inyectado termina con ',' antes de "model"
  D. Template sin linea "model"  -> debe fallar (regex no matchea)
  E. Template con JSON invalido  -> debe fallar (validacion JSON)

Uso:  powershell -ExecutionPolicy Bypass -File tests\setup-ps1-jsonc-validation.ps1
Exit code 0 = todo OK, 1 = alguna comprobacion fallo.
#>

param(
    [string]$RepoRoot = (Split-Path -Parent $PSScriptRoot)
)

$ErrorActionPreference = "Stop"
$script:passed = 0
$script:failed = 0

function Assert-True {
    param([bool]$Condition, [string]$Message)
    if ($Condition) {
        Write-Host "  [OK] $Message" -ForegroundColor Green
        $script:passed++
    } else {
        Write-Host "  [FAIL] $Message" -ForegroundColor Red
        $script:failed++
    }
}

function Assert-Throws {
    param([scriptblock]$Action, [string]$Message)
    try {
        & $Action
        Write-Host "  [FAIL] $Message (no lanzo excepcion)" -ForegroundColor Red
        $script:failed++
    } catch {
        Write-Host "  [OK] $Message (excepcion: $($_.Exception.Message))" -ForegroundColor Green
        $script:passed++
    }
}

# ---------- 0. Cargar la MISMA funcion que usa setup.ps1 ----------
Write-Host "==> Cargando scripts\New-OpencodeConfig.ps1 (misma funcion que setup.ps1)" -ForegroundColor Cyan
$funcFile = Join-Path $RepoRoot "scripts\New-OpencodeConfig.ps1"
if (-not (Test-Path $funcFile)) {
    Write-Error "No existe $funcFile. El test no puede continuar."
    exit 1
}
. $funcFile

$templatePath = Join-Path $RepoRoot "templates\opencode.jsonc.example"
$pyBin = "E:\Agente_IA\.venv\Scripts\python.exe"
$root = "E:\Agente_IA"
$mcpWin = Join-Path $root "mcp_windows"

function Parse-Jsonc {
    param([string]$Content)
    $clean = $Content -replace '(?m)^\s*//[^\r\n]*', '' -replace '^\uFEFF', ''
    return $clean | ConvertFrom-Json
}

# ---------- A. 3 providers + mcp_windows ----------
Write-Host "`n[Escenario A] omniroute + 9router + ollama, mcp_windows detectado..." -ForegroundColor Cyan
$providersA = @{
    omniroute = @{
        name = "OmniRoute"
        npm  = "@ai-sdk/openai-compatible"
        options = @{ baseURL = "http://localhost:20128/v1"; apiKey = "{env:OMNIROUTE_API_KEY}" }
        models  = @{
            "best-coding"      = @{ name = "best-coding (OmniRoute)" }
            "auto/best-coding" = @{ name = "auto/best-coding" }
        }
    }
    ninerouter = @{
        name = "9Router"
        npm  = "@ai-sdk/openai-compatible"
        options = @{ baseURL = "http://localhost:4000/v1" }
        models  = @{ "openai/gpt-4o" = @{ name = "GPT-4o (9Router)" } }
    }
    ollama = @{
        name = "Ollama"
        npm  = "@ai-sdk/openai-compatible"
        options = @{ baseURL = "http://localhost:11434/v1" }
        models  = @{ "phi4-mini" = @{ name = "phi4-mini" } }
    }
}
$cfgA = New-OpencodeConfigJsonc -TemplatePath $templatePath -ProjectRoot $root -PythonBin $pyBin -Providers $providersA -DefaultModel "auto/best-coding" -McpWindowsRoot $mcpWin
$jsonA = Parse-Jsonc $cfgA

Assert-True ($null -ne $jsonA.provider) "A1: provider presente"
Assert-True ($jsonA.provider.PSObject.Properties.Name.Count -eq 3) "A2: 3 providers inyectados"
Assert-True ($jsonA.model -eq "auto/best-coding") "A3: model = auto/best-coding"
Assert-True ($null -ne $jsonA.mcp) "A4: mcp presente"
Assert-True ($jsonA.mcp."corel-draw".enabled -eq $true) "A5: MCP corel-draw activo (mcp_windows detectado)"
Assert-True (-not $cfgA.Contains("%%")) "A6: sin placeholders residuales (%%...%%)"

# ---------- B. Solo ollama, sin mcp_windows ----------
Write-Host "`n[Escenario B] solo ollama (fallback), sin mcp_windows..." -ForegroundColor Cyan
$providersB = @{
    ollama = @{
        name = "Ollama"
        npm  = "@ai-sdk/openai-compatible"
        options = @{ baseURL = "http://localhost:11434/v1" }
        models  = @{ "phi4-mini" = @{ name = "phi4-mini" } }
    }
}
$cfgB = New-OpencodeConfigJsonc -TemplatePath $templatePath -ProjectRoot $root -PythonBin $pyBin -Providers $providersB -DefaultModel "ollama/phi4-mini" -McpWindowsRoot ""
$jsonB = Parse-Jsonc $cfgB

Assert-True ($jsonB.provider.PSObject.Properties.Name.Count -eq 1) "B1: solo 1 provider"
Assert-True ($jsonB.model -eq "ollama/phi4-mini") "B2: model = ollama/phi4-mini"
Assert-True ($null -eq $jsonB.mcp."corel-draw") "B3: corel-draw eliminado sin mcp_windows"
Assert-True (-not $cfgB.Contains("%%")) "B4: sin placeholders residuales"

# ---------- C. Regresion de la coma (bug original) ----------
Write-Host "`n[Escenario C] el bloque provider inyectado termina con ',' antes de 'model'..." -ForegroundColor Cyan
$cleanA = $cfgA -replace '(?m)^\s*//[^\r\n]*', ''
$cleanB = $cfgB -replace '(?m)^\s*//[^\r\n]*', ''
Assert-True ($cleanA -match '\},\s*\r?\n\s*"model"\s*:') "C1: coma presente tras provider en A (falla = CommaExpected)"
Assert-True ($cleanB -match '\},\s*\r?\n\s*"model"\s*:') "C2: coma presente tras provider en B"
Assert-True (([regex]::Matches($cleanA, '"provider"\s*:')).Count -eq 1) "C3: 'provider' aparece exactamente 1 vez (no hay bloque duplicado)"

# ---------- D. Template sin linea "model" -> debe fallar ----------
Write-Host "`n[Escenario D] template roto sin linea 'model'..." -ForegroundColor Cyan
$noModelFile = Join-Path $PSScriptRoot "fixtures\template_nomodel.jsonc"
Assert-Throws {
    New-OpencodeConfigJsonc -TemplatePath $noModelFile -ProjectRoot $root -PythonBin $pyBin -Providers $providersB -DefaultModel "ollama/phi4-mini" -McpWindowsRoot ""
} "D1: falla si el regex no matcheo (modelo no inyectado)"

# ---------- E. Template con JSON invalido -> debe fallar ----------
Write-Host "`n[Escenario E] template con JSON invalido (coma final en mcp)..." -ForegroundColor Cyan
$invalidFile = Join-Path $PSScriptRoot "fixtures\template_invalid.jsonc"
Assert-Throws {
    New-OpencodeConfigJsonc -TemplatePath $invalidFile -ProjectRoot $root -PythonBin $pyBin -Providers $providersB -DefaultModel "ollama/phi4-mini" -McpWindowsRoot ""
} "E1: falla con JSON invalido (evita configs rotas en disco)"

# ---------- Resumen ----------
Write-Host "`n======================================" -ForegroundColor Cyan
Write-Host "RESULTADO: $($script:passed) OK, $($script:failed) FAIL" -ForegroundColor $(if ($script:failed -eq 0) { "Green" } else { "Red" })
Write-Host "======================================" -ForegroundColor Cyan
if ($script:failed -gt 0) { exit 1 }
exit 0
