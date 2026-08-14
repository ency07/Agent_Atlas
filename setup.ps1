# ============================================================
# setup.ps1 — Bootstrap de Atlas en un PC nuevo
# Uso:  powershell -ExecutionPolicy Bypass -File setup.ps1
#       powershell -ExecutionPolicy Bypass -File setup.ps1 -InstallF2
# Pre-requisitos: Node.js >= 20, Python >= 3.11 en PATH.
# No toca secretos. Genera %USERPROFILE%\.config\opencode\opencode.jsonc
# a partir de templates/opencode.jsonc.example resolviendo rutas.
# -InstallF2: ademas registra la tarea de Windows que abre el chat
#   flotante (atlas_chat.py) al iniciar sesion.
# ============================================================
param([switch]$InstallF2)
$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$ROOT = $PSScriptRoot
Write-Host "==> Atlas bootstrap en: $ROOT" -ForegroundColor Cyan

# ---------- 1. Pre-requisitos ----------
Write-Host "`n[1/10] Verificando pre-requisitos..." -ForegroundColor Yellow

function Find-Command($name) {
    $c = Get-Command $name -ErrorAction SilentlyContinue
    if ($c) { return $c.Source }
    return $null
}

$node = Find-Command "node"
if (-not $node) { Write-Host "FALTA: Node.js. Instala desde https://nodejs.org y reintenta." -ForegroundColor Red; exit 1 }
Write-Host "  node -> $node"

$python = Find-Command "python"
if (-not $python) { Write-Host "FALTA: Python. Instala 3.11+ desde https://python.org y reintenta." -ForegroundColor Red; exit 1 }
Write-Host "  python -> $python"

# ---------- 1b. Detección de proveedores de modelos (omniroute / 9router) ----------
Write-Host "`n[1b] Detectando proveedores de modelos (opcionales)..." -ForegroundColor Yellow

# omniroute: npm global o proceso corriendo en :20128
$omnirouteInstalled = (Find-Command "omniroute") -or (Test-NetConnection -ComputerName 127.0.0.1 -Port 20128 -WarningAction SilentlyContinue).TcpTestSucceeded
if ($omnirouteInstalled) {
    Write-Host "  omniroute: DETECTADO" -ForegroundColor Green
} else {
    Write-Host "  omniroute: NO detectado" -ForegroundColor Yellow
}

# 9router: verificar si existe binario o proceso
$ninerouterInstalled = (Find-Command "9router") -or (Test-NetConnection -ComputerName 127.0.0.1 -Port 4000 -WarningAction SilentlyContinue).TcpTestSucceeded
if ($ninerouterInstalled) {
    Write-Host "  9router: DETECTADO" -ForegroundColor Green
} else {
    Write-Host "  9router: NO detectado" -ForegroundColor Yellow
}

# Ollama fallback
$ollamaRunning = (Test-NetConnection -ComputerName 127.0.0.1 -Port 11434 -WarningAction SilentlyContinue).TcpTestSucceeded
if ($ollamaRunning) {
    Write-Host "  Ollama: ACTIVO (puerto 11434)" -ForegroundColor Green
} else {
    Write-Host "  Ollama: NO detectado" -ForegroundColor Yellow
}

# ---------- 2. opencode CLI ----------
Write-Host "`n[2/8] opencode CLI..." -ForegroundColor Yellow
$oc = Find-Command "opencode"
if (-not $oc) {
    Write-Host "  instalando opencode-ai (npm global)..."
    npm install -g opencode-ai
    $oc = Find-Command "opencode"
    if (-not $oc) { Write-Host "ERROR: no se pudo instalar opencode." -ForegroundColor Red; exit 1 }
} else {
    Write-Host "  opencode ya instalado -> $oc"
}

# ---------- 3. venv + deps Python ----------
Write-Host "`n[3/8] Entorno Python..." -ForegroundColor Yellow
$venv = Join-Path $ROOT ".venv"
if (-not (Test-Path (Join-Path $venv "Scripts\python.exe"))) {
    Write-Host "  creando venv en $venv"
    & $python -m venv $venv
}
$pyBin = Join-Path $venv "Scripts\python.exe"
if (-not (Test-Path $pyBin)) { Write-Host "ERROR: fallo al crear el venv." -ForegroundColor Red; exit 1 }
Write-Host "  python venv -> $pyBin"
if (Test-Path (Join-Path $ROOT "requirements.txt")) {
    Write-Host "  instalando requirements.txt..."
    & $pyBin -m pip install --upgrade pip
    & $pyBin -m pip install -r (Join-Path $ROOT "requirements.txt")
}

# ---------- 4. Config opencode ----------
Write-Host "`n[4/10] Generando opencode.jsonc..." -ForegroundColor Yellow
$cfgDir = Join-Path $env:USERPROFILE ".config\opencode"
$cfgFile = Join-Path $cfgDir "opencode.jsonc"
New-Item -ItemType Directory -Path $cfgDir -Force | Out-Null

# MCP de windows/corel/playwright-visual: opcional. Ahora consolidado dentro del repo (mcp_windows/).
$mcpWin = ""
foreach ($cand in @((Join-Path $ROOT "mcp_windows"), "E:\MCP\mcp-windows-ai", "D:\MCP\mcp-windows-ai", (Join-Path $ROOT "..\mcp-windows-ai"))) {
    if (Test-Path (Join-Path $cand "mcp_windows_server.py")) { $mcpWin = $cand; break }
}

# Cargar generador de config (extraido para poder testearlo de forma aislada:
# tests\setup-ps1-jsonc-validation.ps1 usa exactamente la misma funcion)
. (Join-Path $ROOT "scripts\New-OpencodeConfig.ps1")

# ----- Proveedores de modelos (dinámico según detección) -----
$providers = @{}
$modelDefault = "ollama/phi4-mini"

# omniroute
if ($omnirouteInstalled) {
    $providers["omniroute"] = @{
        name = "OmniRoute"
        npm = "@ai-sdk/openai-compatible"
        options = @{ baseURL = "http://localhost:20128/v1"; apiKey = "{env:OMNIROUTE_API_KEY}" }
        models = @{
            "best-coding" = @{ name = "best-coding (OmniRoute)" }
            "best-reasoning" = @{ name = "best-reasoning (OmniRoute)" }
            "best-chat" = @{ name = "best-chat (OmniRoute)" }
            "best-fast" = @{ name = "best-fast (OmniRoute)" }
            "best-vision" = @{ name = "best-vision (OmniRoute)" }
            "auto/best-coding" = @{ name = "auto/best-coding" }
            "auto/best-reasoning" = @{ name = "auto/best-reasoning" }
            "auto/best-chat" = @{ name = "auto/best-chat" }
            "auto/best-fast" = @{ name = "auto/best-fast" }
            "auto/best-vision" = @{ name = "auto/best-vision" }
        }
    }
    $modelDefault = "auto/best-coding"
    Write-Host "  Provider: omniroute (modelos auto/*)" -ForegroundColor Green
}

# 9router
if ($ninerouterInstalled) {
    $providers["ninerouter"] = @{
        name = "9Router"
        npm = "@ai-sdk/openai-compatible"
        options = @{ baseURL = "http://localhost:4000/v1"; apiKey = "{env:NINEROUTER_API_KEY}" }
        models = @{
            "anthropic/claude-sonnet-4-20250514" = @{ name = "Claude Sonnet 4 (9Router)" }
            "anthropic/claude-opus-4-20250514" = @{ name = "Claude Opus 4 (9Router)" }
            "openai/gpt-4o" = @{ name = "GPT-4o (9Router)" }
            "gemini/gemini-2.5-pro" = @{ name = "Gemini 2.5 Pro (9Router)" }
            "ag/gemini-3.6-flash-high" = @{ name = "Gemini 3.6 Flash (9Router)" }
            "blackbox/deepseek-v4-flash" = @{ name = "DeepSeek V4 Flash (9Router)" }
            "glm-cn/glm-4.5-air" = @{ name = "GLM 4.5 Air (9Router)" }
            "alicode-intl/kimi-k2.5" = @{ name = "Kimi K2.5 (9Router)" }
            "blackbox/gpt-5.5" = @{ name = "GPT-5.5 (9Router)" }
        }
    }
    Write-Host "  Provider: 9router (catálogo real 679 modelos)" -ForegroundColor Green
}

# Ollama (siempre como fallback)
$providers["ollama"] = @{
    npm = "@ai-sdk/openai-compatible"
    name = "Ollama"
    options = @{ baseURL = "http://localhost:11434/v1" }
    models = @{
        "phi4-mini" = @{ name = "phi4-mini" }
        "mistral:7b" = @{ name = "mistral:7b" }
        "llama3.2:3b" = @{ name = "llama3.2:3b" }
        "gemma3:4b" = @{ name = "gemma3:4b" }
        "gemma3:1b" = @{ name = "gemma3:1b" }
    }
}
if (-not $omnirouteInstalled -and -not $ninerouterInstalled) {
    Write-Host "  Provider: ollama (fallback)" -ForegroundColor Yellow
}

# Generar config: New-OpencodeConfigJsonc inyecta el bloque provider (con coma
# final) + la linea "model", y lanza excepcion si el JSONC resultante no es valido.
$template = New-OpencodeConfigJsonc -TemplatePath (Join-Path $ROOT "templates\opencode.jsonc.example") -ProjectRoot $ROOT -PythonBin $pyBin -Providers $providers -DefaultModel $modelDefault -McpWindowsRoot $mcpWin
Write-Host "  validación JSON: OK"

if ($mcpWin) {
    Write-Host "  MCP windows-ai -> $mcpWin"
} else {
    Write-Host "  MCP windows-ai: no detectado -> MCP corel/windows/playwright-visual DESHABILITADOS" -ForegroundColor DarkYellow
}
Set-Content -Path $cfgFile -Value $template -Encoding UTF8
Write-Host "  generado: $cfgFile (provider: $($modelDefault))"

# ---------- 5. Skill memory ----------
Write-Host "`n[5/8] Instalando skill memory..." -ForegroundColor Yellow
$skillDir = Join-Path $cfgDir "skills\memory"
New-Item -ItemType Directory -Path $skillDir -Force | Out-Null
Copy-Item (Join-Path $ROOT "templates\skills\memory\SKILL.md") (Join-Path $skillDir "SKILL.md") -Force
Write-Host "  skill -> $skillDir\SKILL.md"

# ---------- 5a. Skill orquestador ----------
$stateDir = Join-Path $ROOT "memory_data\state"
New-Item -ItemType Directory -Path $stateDir -Force | Out-Null
$orchSkill = Join-Path $cfgDir "skills\atlas_orchestrator"
New-Item -ItemType Directory -Path $orchSkill -Force | Out-Null
Copy-Item (Join-Path $ROOT "templates\skills\atlas_orchestrator\SKILL.md") (Join-Path $orchSkill "SKILL.md") -Force
Write-Host "  skill orquestador -> $orchSkill\SKILL.md"

# mapa de capacidades de modelos (orquestador)
$capsFile = Join-Path $stateDir "model_capabilities.json"
if (Test-Path (Join-Path $ROOT "templates\model_capabilities.json.example")) {
    if (-not (Test-Path $capsFile)) {
        Copy-Item (Join-Path $ROOT "templates\model_capabilities.json.example") $capsFile -Force
        Write-Host "  model_capabilities.json creado (orquestador)"
    } else {
        Write-Host "  model_capabilities.json ya existe"
    }
}

# ---------- 5b. Config guardián + búsqueda ----------
Write-Host "`n[5b] Config guardián + búsqueda..." -ForegroundColor Yellow
$stateDir = Join-Path $ROOT "memory_data\state"
New-Item -ItemType Directory -Path $stateDir -Force | Out-Null

$guardianFile = Join-Path $stateDir "guardian.json"
if (-not (Test-Path $guardianFile)) {
    @{
        level = "guard"
        whitelist_binaries = @("python","node","npm","git","pip","wscript","powershell","cmd")
        whitelist_processes = @("python.exe","node.exe","code.exe","powershell.exe","cmd.exe")
        allowed_dirs = @($ROOT, (Join-Path $env:USERPROFILE "Documents"))
        blocked_ops = @("run_script","process_kill","registry_write")
        confirm_destructive = $true
    } | ConvertTo-Json -Depth 4 | Set-Content -Path $guardianFile -Encoding UTF8
    Write-Host "  guardian.json creado (nivel: guard)"
} else {
    Write-Host "  guardian.json ya existe"
}

$searchFile = Join-Path $stateDir "search.json"
if (-not (Test-Path $searchFile)) {
    @{
        searxng_url = ""
        timeout_ddgs = 15
        timeout_searxng = 10
        max_results = 10
    } | ConvertTo-Json | Set-Content -Path $searchFile -Encoding UTF8
    Write-Host "  search.json creado (SearXNG desactivado, solo ddgs)"
} else {
    Write-Host "  search.json ya existe"
}

# ---------- 5c. Reglas de foco (F3) ----------
$focoTemplate = Join-Path $ROOT "templates\foco_rules.json.example"
$focoFile = Join-Path $stateDir "foco_rules.json"
if (Test-Path $focoTemplate) {
    if (-not (Test-Path $focoFile)) {
        Copy-Item $focoTemplate $focoFile -Force
        Write-Host "  foco_rules.json creado (modo: soft)"
    } else {
        Write-Host "  foco_rules.json ya existe"
    }
} else {
    Write-Host "  AVISO: templates\foco_rules.json.example no existe" -ForegroundColor DarkYellow
}

# ---------- 6. Git hook (F1) ----------
Write-Host "`n[6/8] Git hook (core.hooksPath)..." -ForegroundColor Yellow
Push-Location $ROOT
git config core.hooksPath hooks
$hookOk = git config --get core.hooksPath
Pop-Location
if ($hookOk -eq "hooks") {
    Write-Host "  core.hooksPath -> hooks (post-commit activo)"
} else {
    Write-Host "  AVISO: no se pudo configurar core.hooksPath" -ForegroundColor DarkYellow
}

# ---------- 7. Backup diario (F1) ----------
Write-Host "`n[7/9] Backup diario (Task Scheduler)..." -ForegroundColor Yellow
$vbsBk = Join-Path $ROOT "start_atlas_backup.vbs"
if (Test-Path $vbsBk) {
    $vbsBkSafe = $vbsBk.Replace("`"", "`"`"")
    & schtasks /Create /TN "AtlasBackup" /TR "wscript.exe `"$vbsBkSafe`"" /SC DAILY /ST 03:00 /F | Out-Null
    if ($LASTEXITCODE -eq 0) {
        Write-Host "  tarea AtlasBackup registrada (diario 03:00)"
    } else {
        Write-Host "  AVISO: no se pudo registrar tarea de backup (schtasks exit=$LASTEXITCODE)" -ForegroundColor DarkYellow
    }
} else {
    Write-Host "  AVISO: start_atlas_backup.vbs no encontrado" -ForegroundColor DarkYellow
}

# ---------- 7b. Backup cifrado (age, F1) ----------
Write-Host "`n[7b/10] Backup cifrado con age..." -ForegroundColor Yellow
$vbsEnc = Join-Path $ROOT "start_atlas_encrypted_backup.vbs"
if (Test-Path $vbsEnc) {
    $vbsEncSafe = $vbsEnc.Replace("`"", "`"`"")
    & schtasks /Create /TN "AtlasEncryptedBackup" /TR "wscript.exe `"$vbsEncSafe`"" /SC DAILY /ST 03:30 /F | Out-Null
    if ($LASTEXITCODE -eq 0) {
        Write-Host "  tarea AtlasEncryptedBackup registrada (diario 03:30, cifrado age)"
    } else {
        Write-Host "  AVISO: no se pudo registrar tarea AtlasEncryptedBackup (schtasks exit=$LASTEXITCODE)" -ForegroundColor DarkYellow
    }
} else {
    Write-Host "  AVISO: start_atlas_encrypted_backup.vbs no encontrado" -ForegroundColor DarkYellow
}
if (Test-Path (Join-Path $ROOT ".age_keys\public_key.txt")) {
    Write-Host "  [OK] Clave pública age presente: $((Get-Content (Join-Path $ROOT '.age_keys\public_key.txt')).Trim())"
} else {
    Write-Host "  AVISO: no hay claves age. Genera: python atlas_backup_encrypted.py generate" -ForegroundColor DarkYellow
}

# ---------- 8. Daemon actividad (F2) ----------
Write-Host "`n[8/9] Daemon actividad (F2)..." -ForegroundColor Yellow
$actVbs = Join-Path $ROOT "start_atlas_activity.vbs"
if (Test-Path $actVbs) {
    $action = New-ScheduledTaskAction -Execute 'wscript.exe' -Argument "`"$actVbs`""
    $trigger = New-ScheduledTaskTrigger -AtLogOn
    $settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit (New-TimeSpan -Hours 0) -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1)
    Register-ScheduledTask -TaskName 'AtlasActivity' -Action $action -Trigger $trigger -Settings $settings -Force | Out-Null
    $task = Get-ScheduledTask -TaskName 'AtlasActivity' -ErrorAction SilentlyContinue
    if ($task) {
        Write-Host "  tarea AtlasActivity registrada via wscript (autostart al iniciar sesion, restart on failure)"
    } else {
        Write-Host "  AVISO: no se pudo registrar tarea AtlasActivity" -ForegroundColor DarkYellow
    }
} else {
    Write-Host "  AVISO: start_atlas_activity.vbs no encontrado" -ForegroundColor DarkYellow
}

# ---------- 9. Recordatorio rotacion de secretos (produccion) ----------
Write-Host "`n[9/10] Recordatorio rotacion secretos (semanal)..." -ForegroundColor Yellow
$remVbs = Join-Path $ROOT "start_secret_reminder.vbs"
if (Test-Path $remVbs) {
    $actionRem = New-ScheduledTaskAction -Execute 'wscript.exe' -Argument "`"$remVbs`""
    $triggerRem = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Sunday -At '09:00'
    $settingsRem = New-ScheduledTaskSettingsSet -ExecutionTimeLimit (New-TimeSpan -Minutes 5)
    Register-ScheduledTask -TaskName 'AtlasSecretReminder' -Action $actionRem -Trigger $triggerRem -Settings $settingsRem -Force | Out-Null
    $taskRem = Get-ScheduledTask -TaskName 'AtlasSecretReminder' -ErrorAction SilentlyContinue
    if ($taskRem) {
        Write-Host "  tarea AtlasSecretReminder registrada (domingo 09:00)"
    } else {
        Write-Host "  AVISO: no se pudo registrar AtlasSecretReminder" -ForegroundColor DarkYellow
    }
} else {
    Write-Host "  AVISO: start_secret_reminder.vbs no encontrado" -ForegroundColor DarkYellow
}

# ---------- 9b. Supervisor auto-reparación (F1) ----------
Write-Host "`n[9b/10] Supervisor auto-reparación..." -ForegroundColor Yellow
$supVbs = Join-Path $ROOT "start_atlas_supervisor.vbs"
if (Test-Path $supVbs) {
    $actionSup = New-ScheduledTaskAction -Execute 'wscript.exe' -Argument "`"$supVbs`""
    $triggerSup = New-ScheduledTaskTrigger -AtLogOn
    $settingsSup = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit (New-TimeSpan -Hours 0) -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1)
    Register-ScheduledTask -TaskName 'AtlasSupervisor' -Action $actionSup -Trigger $triggerSup -Settings $settingsSup -Force | Out-Null
    $taskSup = Get-ScheduledTask -TaskName 'AtlasSupervisor' -ErrorAction SilentlyContinue
    if ($taskSup) {
        Write-Host "  tarea AtlasSupervisor registrada (autostart al iniciar sesion, restart on failure)"
    } else {
        Write-Host "  AVISO: no se pudo registrar AtlasSupervisor" -ForegroundColor DarkYellow
    }
} else {
    Write-Host "  AVISO: start_atlas_supervisor.vbs no encontrado" -ForegroundColor DarkYellow
}

# ---------- 9c. Rotación de logs (F1) ----------
Write-Host "`n[9c/10] Rotación de logs..." -ForegroundColor Yellow
$logVbs = Join-Path $ROOT "start_atlas_logrotate.vbs"
if (Test-Path $logVbs) {
    $actionLog = New-ScheduledTaskAction -Execute 'wscript.exe' -Argument "`"$logVbs`""
    $triggerLog = New-ScheduledTaskTrigger -Daily -At '04:00'
    $settingsLog = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit (New-TimeSpan -Hours 1)
    Register-ScheduledTask -TaskName 'AtlasLogRotate' -Action $actionLog -Trigger $triggerLog -Settings $settingsLog -Force | Out-Null
    $taskLog = Get-ScheduledTask -TaskName 'AtlasLogRotate' -ErrorAction SilentlyContinue
    if ($taskLog) {
        Write-Host "  tarea AtlasLogRotate registrada (diario 04:00, mantiene 7 dias)"
    } else {
        Write-Host "  AVISO: no se pudo registrar AtlasLogRotate" -ForegroundColor DarkYellow
    }
} else {
    Write-Host "  AVISO: start_atlas_logrotate.vbs no encontrado" -ForegroundColor DarkYellow
}

# ---------- 9d. Boot check E2E (F1) ----------
Write-Host "`n[9d/10] Boot check E2E..." -ForegroundColor Yellow
$bootVbs = Join-Path $ROOT "start_atlas_bootcheck.vbs"
if (Test-Path $bootVbs) {
    $actionBoot = New-ScheduledTaskAction -Execute 'wscript.exe' -Argument "`"$bootVbs`""
    $triggerBoot = New-ScheduledTaskTrigger -AtLogOn
    $settingsBoot = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit (New-TimeSpan -Hours 0) -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1)
    Register-ScheduledTask -TaskName 'AtlasBootCheck' -Action $actionBoot -Trigger $triggerBoot -Settings $settingsBoot -Force | Out-Null
    $taskBoot = Get-ScheduledTask -TaskName 'AtlasBootCheck' -ErrorAction SilentlyContinue
    if ($taskBoot) {
        Write-Host "  tarea AtlasBootCheck registrada (autostart al iniciar sesion, toast verde/rojo)"
    } else {
        Write-Host "  AVISO: no se pudo registrar AtlasBootCheck" -ForegroundColor DarkYellow
    }
} else {
    Write-Host "  AVISO: start_atlas_bootcheck.vbs no encontrado" -ForegroundColor DarkYellow
}

# ---------- 9e. Sync capacidades (MEDIA) ----------
Write-Host "`n[9e/10] Sync capacidades de modelos (semanal)..." -ForegroundColor Yellow
$syncVbs = Join-Path $ROOT "start_atlas_sync_caps.vbs"
if (Test-Path $syncVbs) {
    $actionSync = New-ScheduledTaskAction -Execute 'wscript.exe' -Argument "`"$syncVbs`""
    $triggerSync = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Monday -At '03:15'
    $settingsSync = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit (New-TimeSpan -Hours 1)
    Register-ScheduledTask -TaskName 'AtlasSyncCapabilities' -Action $actionSync -Trigger $triggerSync -Settings $settingsSync -Force | Out-Null
    $taskSync = Get-ScheduledTask -TaskName 'AtlasSyncCapabilities' -ErrorAction SilentlyContinue
    if ($taskSync) {
        Write-Host "  tarea AtlasSyncCapabilities registrada (lunes 03:15, refresca model_capabilities.json)"
    } else {
        Write-Host "  AVISO: no se pudo registrar AtlasSyncCapabilities" -ForegroundColor DarkYellow
    }
} else {
    Write-Host "  AVISO: start_atlas_sync_caps.vbs no encontrado" -ForegroundColor DarkYellow
}

# ---------- 9f. Benchmark proveedores (MEDIA) ----------
Write-Host "`n[9f/10] Benchmark de proveedores (semanal)..." -ForegroundColor Yellow
$benchVbs = Join-Path $ROOT "start_atlas_benchmark.vbs"
if (Test-Path $benchVbs) {
    $actionBench = New-ScheduledTaskAction -Execute 'wscript.exe' -Argument "`"$benchVbs`""
    $triggerBench = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Monday -At '03:20'
    $settingsBench = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit (New-TimeSpan -Hours 1)
    Register-ScheduledTask -TaskName 'AtlasBenchmark' -Action $actionBench -Trigger $triggerBench -Settings $settingsBench -Force | Out-Null
    $taskBench = Get-ScheduledTask -TaskName 'AtlasBenchmark' -ErrorAction SilentlyContinue
    if ($taskBench) {
        Write-Host "  tarea AtlasBenchmark registrada (lunes 03:20, latencia + exito en routing_log)"
    } else {
        Write-Host "  AVISO: no se pudo registrar AtlasBenchmark" -ForegroundColor DarkYellow
    }
} else {
    Write-Host "  AVISO: start_atlas_benchmark.vbs no encontrado" -ForegroundColor DarkYellow
}

# ---------- 10. Diagnostico ----------
Write-Host "`n[10/10] Diagnostico..." -ForegroundColor Yellow
& (Join-Path $ROOT "check.ps1")

Write-Host "`n==> Listo. Proximos pasos:" -ForegroundColor Green
Write-Host "  1. Ejecuta:  opencode   (en cualquier carpeta; la memoria carga sola)"
Write-Host "  2. Verifica la memoria:  opencode run 'dime donde quedamos'"
Write-Host "  3. Chat flotante:  python atlas_chat.py  (o .\start_atlas_chat.vbs)"
Write-Host "  4. Backup manual:  python mcp_memory_server.py --cli backup"
Write-Host "  5. Revisa docs/PUESTA_EN_MARCHA.md si algo falla."
