# ============================================================
# New-OpencodeConfig.ps1 — Generador de opencode.jsonc (JSONC válido)
# ------------------------------------------------------------
# Extraido de setup.ps1 para poder testearlo de forma aislada.
# Usado por:
#   - setup.ps1      (generacion en vivo durante bootstrap)
#   - tests\setup-ps1-jsonc-validation.ps1  (validacion automatica)
#
# La funcion:
#   1. Lee el template templates\opencode.jsonc.example
#   2. Sustituye %%PYTHON_BIN%% / %%PROJECT_ROOT%% / %%MCP_WINDOWS_AI%%
#   3. Inyecta el bloque "provider" (con coma final) + la linea "model"
#   4. Verifica que el modelo se inyecto de verdad (regex matcheo)
#   5. Valida que el resultado final sea JSON parseable ANTES de devolverlo
#   -> lanza excepcion si algo falla, asi nunca se escribe una config rota.
# ============================================================
function New-OpencodeConfigJsonc {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)]
        [string]$TemplatePath,

        [Parameter(Mandatory = $true)]
        [string]$ProjectRoot,

        [Parameter(Mandatory = $true)]
        [string]$PythonBin,

        [Parameter(Mandatory = $true)]
        [hashtable]$Providers,

        [Parameter(Mandatory = $true)]
        [string]$DefaultModel,

        [string]$McpWindowsRoot = ""
    )

    # Rutas con \ escapadas para JSON
    $pyEsc = $PythonBin.Replace("\", "\\")
    $rootEsc = $ProjectRoot.Replace("\", "\\")

    # 1. Template base
    $template = Get-Content -Path $TemplatePath -Raw
    $template = $template.Replace("%%PYTHON_BIN%%", $pyEsc)
    $template = $template.Replace("%%PROJECT_ROOT%%", $rootEsc)

    # 2. MCP de windows/corel/playwright-visual (opcional)
    if ($McpWindowsRoot) {
        $template = $template.Replace("%%MCP_WINDOWS_AI%%", $McpWindowsRoot.Replace("\", "\\"))
    } else {
        $template = $template -replace '"(corel-draw|windows|playwright-visual)"\s*:\s*\{[^}]*\},\s*', ""
        $template = $template.Replace("%%MCP_WINDOWS_AI%%", "")
    }

    # 3. Proveedores -> JSON compacto
    $providerJson = $Providers | ConvertTo-Json -Depth 10 -Compress
    $providerJson = $providerJson -replace '\\\\', '\\'

    # 4. Inyectar providers + model en el template (regex probado, soporta PS 5.1).
    #    Reemplaza TODO el bloque provider + la linea "model" en una sola pasada.
    #    La coma tras el bloque provider es OBLIGATORIA: sin ella el JSONC es invalido.
    $providerBlock = '"provider": ' + $providerJson + ','
    $template = $template -replace '(?s)"provider"\s*:\s*\{.*?\},\s*\n\s*"model"\s*:\s*"[^"]*"', ($providerBlock + "`n  `"model`": `"$DefaultModel`"")

    # 5. Guarda anti-regresion: si el regex no matcheo (template cambiado),
    #    el bloque provider/modelo no se inyecto y hay que fallar fuerte.
    if (-not $template.Contains('"model": "' + $DefaultModel + '"')) {
        throw "El modelo '$DefaultModel' no se inyecto en la plantilla (regex no matcheo). Revisa templates\opencode.jsonc.example"
    }

    # 6. Validar que el JSONC final sea parseable (quita comentarios y BOM)
    $jsonProbe = $template -replace '(?m)^\s*//[^\r\n]*', '' -replace '^\uFEFF', ''
    try {
        $null = $jsonProbe | ConvertFrom-Json
    } catch {
        throw "La config generada no es JSON valido: $($_.Exception.Message)"
    }

    return $template
}
