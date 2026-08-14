# ============================================================
# test_setup_config.ps1 - Verifica que setup.ps1 SIEMPRE genera
# opencode.jsonc VALIDO (regresion: coma tras el bloque provider).
# Uso:  powershell -NoProfile -ExecutionPolicy Bypass -File tests/test_setup_config.ps1
# NO toca la config real: la generacion se redirige a un archivo temporal.
# ============================================================
$ErrorActionPreference = "Stop"
$script:fail = 0

function Assert-True {
    param([bool]$Cond, [string]$Msg)
    if ($Cond) { Write-Host "  [OK]   $Msg" -ForegroundColor Green }
    else { Write-Host "  [FAIL] $Msg" -ForegroundColor Red; $script:fail++ }
}

$setup = Get-Content 'E:/Agente_IA/setup.ps1' -Raw
$start = $setup.IndexOf('# ---------- 4. Config opencode ----------')
$endMark = 'Write-Host "  generado: $cfgFile (provider: $($modelDefault))"'
$end = $setup.IndexOf($endMark)
if ($start -lt 0 -or $end -lt 0) {
    Write-Host "ERROR: no se encontro el bloque de generacion en setup.ps1" -ForegroundColor Red
    exit 2
}
$block = $setup.Substring($start, ($end + $endMark.Length) - $start)

$tmp = Join-Path $env:TEMP 'atlas_test_opencode.jsonc'
$block = $block.Replace('Set-Content -Path $cfgFile -Value $template -Encoding UTF8', "Set-Content -Path '$tmp' -Value `$template -Encoding UTF8")

function Test-Generation {
    param([string]$Name, [bool]$OmniRoute, [bool]$NineRouter, [string]$ExpectedModel, [bool]$NoMcpWin)

    Write-Host "==> Escenario: $Name"
    $blockRun = $block
    if ($NoMcpWin) {
        $blockRun = $blockRun.Replace('Test-Path (Join-Path $cand "mcp_windows_server.py")', '$false')
    }

    $pre = @'
$ROOT = 'E:/Agente_IA'
$pyBin = Join-Path $ROOT '.venv/Scripts/python.exe'
$omnirouteInstalled = %%OMNI%%
$ninerouterInstalled = %%NINE%%
$ollamaRunning = $true
'@
    $pre = $pre.Replace('%%OMNI%%', ('$' + $OmniRoute)).Replace('%%NINE%%', ('$' + $NineRouter))

    $genScript = Join-Path $env:TEMP "atlas_test_generate_$PID.ps1"
    [System.IO.File]::WriteAllText($genScript, ($pre + "`n" + $blockRun))
    & $genScript
    Remove-Item $genScript -ErrorAction SilentlyContinue

    $gen = Get-Content $tmp -Raw
    $probe = $gen -replace '(?m)^\s*//[^\r\n]*', '' -replace '^\uFEFF', ''
    $j = $null
    try { $j = $probe | ConvertFrom-Json } catch { $j = $null }

    Assert-True ($null -ne $j) "JSONC generado es parseable"
    if ($null -eq $j) { return }
    Assert-True ($null -ne $j.provider) "existe el bloque provider"
    Assert-True ($j.model -eq $ExpectedModel) "model esperado: $ExpectedModel"

    $commaOk = (($gen -notmatch '}}\r?\n\s*"model"') -and ($gen -match '}},\r?\n\s*"model"'))
    Assert-True $commaOk "coma presente entre provider y model (regresion)"

    Assert-True ($gen -notmatch '%%[A-Z_]+%%') "sin placeholders pendientes"

    if ($NoMcpWin) {
        Assert-True (($null -eq $j.mcp.'corel-draw') -and ($null -eq $j.mcp.'windows') -and ($null -eq $j.mcp.'playwright-visual')) "MCP corel/windows/playwright-visual excluidos sin mcp_windows"
    } else {
        Assert-True ($null -ne $j.mcp.'corel-draw') "MCP corel-draw presente"
    }
}

Test-Generation "todos los proveedores + mcp_windows" $true $true "auto/best-coding" $false
Test-Generation "sin routers (fallback ollama)" $false $false "ollama/phi4-mini" $false
Test-Generation "sin mcp_windows (regex exclusion)" $true $true "auto/best-coding" $true

Remove-Item $tmp -ErrorAction SilentlyContinue

if ($script:fail -gt 0) {
    Write-Host "`nRESULTADO: $script:fail fallo(s)" -ForegroundColor Red
    exit 1
}
Write-Host "`nRESULTADO: OK - setup.ps1 genera JSONC valido en todos los escenarios" -ForegroundColor Green
exit 0