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
$ninerouter = Test-NetConnection -ComputerName 127.0.0.1 -Port 4000 -WarningAction SilentlyContinue
Report ($ninerouter.TcpTestSucceeded) "9router localhost:4000 (proveedor catálogo 679)"

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

# ---------- Búsqueda web + guardián (Bloque A/C) ----------
Write-Host "`n[Búsqueda web + guardián]"
$searchPy = Join-Path $ROOT "atlas_search.py"
if (Test-Path $searchPy) {
    Report $true "atlas_search.py presente"
    $ddgs = & $pyBin -c "import ddgs; print('ok')" 2>$null
    Report ($ddgs -match "ok") "paquete 'ddgs' (búsqueda web)"
} else {
    Report $false "atlas_search.py ausente"
}
$guardianPy = Join-Path $ROOT "atlas_guardian.py"
if (Test-Path $guardianPy) {
    Report $true "atlas_guardian.py presente"
    $gjson = Join-Path $ROOT "memory_data\state\guardian.json"
    Report (Test-Path $gjson) "guardian.json config"
    if (Test-Path $gjson) {
        $gcfg = Get-Content $gjson -Raw | ConvertFrom-Json
        Report ($gcfg.level -in @("relax","guard","strict")) "nivel guardián: $($gcfg.level)"
    }
} else {
    Report $false "atlas_guardian.py ausente"
}

# ---------- Foco (F3) ----------
Write-Host "`n[Foco F3]"
$focoPy = Join-Path $ROOT "foco_rules.py"
if (Test-Path $focoPy) {
    Report $true "foco_rules.py presente"
    $fr = & $pyBin $focoPy --validate 2>$null
    Report ($fr -match "^OK") "reglas foco válidas (mode $((Get-Content (Join-Path $ROOT 'memory_data\state\foco_rules.json') -Raw -ErrorAction SilentlyContinue | ConvertFrom-Json).mode))"
    $ftest = & $pyBin $focoPy --test 2>$null
    Report ($ftest -match "7/7") "tests clasificador (7/7)"
} else {
    Report $false "foco_rules.py ausente"
}
$focoServer = Join-Path $ROOT "atlas_foco.py"
if (Test-Path $focoServer) {
    Report $true "atlas_foco.py presente (MCP foco)"
} else {
    Report $false "atlas_foco.py ausente"
}
$fjson = Join-Path $ROOT "memory_data\state\foco_rules.json"
if (Test-Path $fjson) {
    $fcfg = Get-Content $fjson -Raw | ConvertFrom-Json
    Report ($fcfg.mode -in @("off","soft","strict")) "nivel foco: $($fcfg.mode)"
} else {
    Report $false "foco_rules.json config ausente (corre setup.ps1)"
}

# ---------- Orquestador (O1) ----------
Write-Host "`n[Orquestador O1]"
$capFile = Join-Path $ROOT "memory_data\state\model_capabilities.json"
if (Test-Path $capFile) {
    $caps = Get-Content $capFile -Raw | ConvertFrom-Json
    Report ($null -ne $caps.models -and $null -ne $caps.task_to_model) "model_capabilities.json (modelos + routing)"
    Report ($caps.regla_dorada) "regla dorada presente (vision=false nunca en tareas visuales)"
} else {
    Report $false "model_capabilities.json ausente (corre setup.ps1)"
}
$orchSkill = Join-Path $ROOT "skills\atlas_orchestrator\SKILL.md"
Report (Test-Path $orchSkill) "skill atlas_orchestrator presente"
$orchSkillCfg = Join-Path $env:USERPROFILE ".config\opencode\skills\atlas_orchestrator\SKILL.md"
Report (Test-Path $orchSkillCfg) "skill instalado en config de opencode"

# Orquestador completo (MCP con deteccion en vivo)
$orchPy = Join-Path $ROOT "atlas_orchestrator.py"
if (Test-Path $orchPy) {
    Report $true "atlas_orchestrator.py presente (MCP, deteccion en vivo)"
    $oprov = & $pyBin -c "import sys; sys.path.insert(0, r'$ROOT'); import os; os.environ['MEMORY_ROOT']=r'$ROOT\memory_data'; import atlas_orchestrator as o; print(' '.join(sorted(o.active_models())))" 2>$null
    if ($LASTEXITCODE -eq 0 -and $oprov) {
        Report $true "orquestador detecta proveedores activos ($(($oprov -split ' ').Count) modelos)"
    } else {
        Report $false "orquestador sin proveedores activos (levanta omniroute/ollama)"
    }
} else {
    Report $false "atlas_orchestrator.py ausente"
}

# ---------- Health / semáforo (S1) ----------
Write-Host "`n[Health / semáforo S1]"
$healthPy = Join-Path $ROOT "atlas_health.py"
if (Test-Path $healthPy) {
    Report $true "atlas_health.py presente (MCP + semaforo)"
    $hres = & $pyBin $healthPy --cli 2>$null | Out-String
    if ($LASTEXITCODE -eq 0) {
        Report $true "health check: TODO OK (green/yellow)"
    } else {
        Report $false "health check: hay fallos criticos"
    }
} else {
    Report $false "atlas_health.py ausente"
}

# ---------- MCP windows consolidado ----------
Write-Host "`n[MCP windows consolidado]"
$mcpWinDir = Join-Path $ROOT "mcp_windows"
$mcpWinCore = Join-Path $mcpWinDir "mcp_windows_server.py"
$mcpCorel = Join-Path $mcpWinDir "mcp_corel_server.py"
$mcpPw = Join-Path $mcpWinDir "mcp_playwright_visual_server.py"
Report (Test-Path $mcpWinCore) "mcp_windows consolidado en repo (mcp_windows/)"
Report (Test-Path $mcpCorel) "mcp_corel_server.py presente"
Report (Test-Path $mcpPw) "mcp_playwright_visual_server.py presente"
if (Test-Path $mcpWinCore) {
    $cfgLocal = Join-Path $env:USERPROFILE ".config\opencode\opencode.jsonc"
    if (Test-Path $cfgLocal) {
        $cfgText = Get-Content $cfgLocal -Raw
        # en JSON la ruta aparece con backslashes escapados (doble barra)
        $jsonPath = $mcpWinCore.Replace("\", "\\")
        Report ($cfgText.Contains($jsonPath)) "config local apunta a mcp_windows consolidado"
    }
}

# ---------- Dashboard web (datos reales) ----------
Write-Host "`n[Dashboard web]"
$webPy = Join-Path $ROOT "atlas_web_server.py"
Report (Test-Path $webPy) "atlas_web_server.py presente (dashboard + /api/*)"
Report (Test-Path (Join-Path $ROOT "start_atlas_web.vbs")) "start_atlas_web.vbs presente"
$taskWeb = Get-ScheduledTask -TaskName "AtlasWeb" -ErrorAction SilentlyContinue
Report ($null -ne $taskWeb) "tarea AtlasWeb en Task Scheduler (autostart)"
$webLive = $false
try { $null = Invoke-RestMethod "http://127.0.0.1:4100/api/overview" -TimeoutSec 3; $webLive = $true } catch {}
Report $webLive "dashboard respondiendo en :4100"

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
$argsBk = if ($taskBk) { $taskBk.Actions[0].Arguments } else { "" }
Report (-not [string]::IsNullOrWhiteSpace($argsBk)) "tarea AtlasBackup con script apuntado (Args no vacio)"
Report (Test-Path (Join-Path $ROOT "start_atlas_backup.vbs")) "start_atlas_backup.vbs existe"
$bkCount = (Get-ChildItem (Join-Path $ROOT "memory_data\backup\atlas_*.zip") -ErrorAction SilentlyContinue).Count
Report ($bkCount -gt 0) "backups existentes: $bkCount"

# ---------- Validacion global: ninguna tarea Atlas con Args vacio ----------
Write-Host "`n[Validacion tareas Atlas (anti-args-vacio)]"
$allAtlas = @("AtlasChat","AtlasActivity","AtlasBackup","AtlasSecretReminder")
$broken = 0
foreach ($tn in $allAtlas) {
    $tt = Get-ScheduledTask -TaskName $tn -ErrorAction SilentlyContinue
    if (-not $tt) { Report $false "tarea $tn no registrada"; $broken++ ; continue }
    $aa = $tt.Actions[0].Arguments
    if ([string]::IsNullOrWhiteSpace($aa)) { Report $false "tarea $tn con Args VACIOS (wscript sin script)"; $broken++ }
    else { Report $true "tarea $tn con script correcto" }
}
if ($broken -eq 0) { Report $true "ninguna tarea Atlas con Args vacio" }

# ---------- Daemon actividad (F2) ----------
Write-Host "`n[Daemon actividad F2]"
$taskAct = Get-ScheduledTask -TaskName "AtlasActivity" -ErrorAction SilentlyContinue
Report ($null -ne $taskAct) "tarea AtlasActivity en Task Scheduler"
Report (Test-Path (Join-Path $ROOT "atlas_activity.py")) "atlas_activity.py presente"
$hb = Join-Path $ROOT "memory_data\state\daemon.heartbeat"
if (Test-Path $hb) {
    $hbAge = (Get-Date) - (Get-Item $hb).LastWriteTime
    Report ($hbAge.TotalSeconds -lt 120) "heartbeat daemon fresco ($([int]$hbAge.TotalSeconds)s atras)"
} else {
    Report $false "sin heartbeat (daemon no ha corrido)"
}

# ---------- Produccion: logs, errores, rotacion, rollback ----------
Write-Host "`n[Produccion (logs/errores/rotacion/rollback)]"
Report (Test-Path (Join-Path $ROOT "atlas_log.py")) "atlas_log.py (logs estructurados JSON)"
Report (Test-Path (Join-Path $ROOT "atlas_monitor.py")) "atlas_monitor.py (errores + rate limit)"
$errFile = Join-Path $ROOT "logs\errors.jsonl"
if (Test-Path $errFile) {
    $errCount = (Get-Content $errFile -ErrorAction SilentlyContinue | Measure-Object).Count
    Report ($errCount -le 50) "errores registrados ultimas 24h: $errCount (log JSON)"
} else {
    Report $true "sin errores registrados (logs/errors.jsonl)"
}
$rotFile = Join-Path $ROOT "memory_data\state\secret_rotation.json"
if (Test-Path $rotFile) {
    $rot = Get-Content $rotFile -Raw | ConvertFrom-Json
    $next = [datetime]$rot.next_due
    $remaining = [int]($next - (Get-Date)).TotalDays
    Report ($remaining -gt 0) "rotacion de secretos: faltan $remaining dias (next: $($next.ToString('yyyy-MM-dd')))"
} else {
    Report $false "sin calendario de rotacion de secretos (corre --cli secret_rotation)"
}
Push-Location $ROOT
$tags = git tag 2>$null
Pop-Location
Report ($tags -match "stable-f1f2") "git tag de rollback 'stable-f1f2' presente"
Report (Test-Path (Join-Path $ROOT "HANDOFF.md")) "HANDOFF.md con plan de rollback"
$taskRem = Get-ScheduledTask -TaskName "AtlasSecretReminder" -ErrorAction SilentlyContinue
Report ($null -ne $taskRem) "recordatorio semanal de rotacion de secretos registrado"

# ---------- Config opencode ----------
Write-Host "`n[Config opencode]"
$cfg = Join-Path $env:USERPROFILE ".config\opencode\opencode.jsonc"
if (Test-Path $cfg) {
    $raw = Get-Content $cfg -Raw
    Report ($raw -notmatch "%%") "opencode.jsonc generado sin placeholders pendientes"
    Report ($raw -match "memory") "MCP memory declarado en opencode.jsonc"
} else {
    Report $false "opencode.jsonc no existe en $cfg (corre setup.ps1)"
}

# Test: setup.ps1 genera opencode.jsonc valido (regresion: coma tras provider)
$testGen = Join-Path $ROOT 'tests/test_setup_config.ps1'
if (Test-Path $testGen) {
    & $testGen
    Report ($LASTEXITCODE -eq 0) "setup.ps1 genera JSONC valido (test generacion)"
} else {
    Report $false "test generacion JSONC no encontrado: $testGen"
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
