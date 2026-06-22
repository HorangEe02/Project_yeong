param(
    [string]$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path,
    [string]$EnvFile = "",
    [string]$OutputPath = "",
    [string]$PythonCommand = "python"
)

$ErrorActionPreference = "Stop"

if (-not $EnvFile) {
    $EnvFile = Join-Path $RepoRoot "backend\.env"
}
if (-not $OutputPath) {
    $OutputPath = Join-Path $RepoRoot "docs\Integration-docs\chatbot-unknown-backlog-report.md"
}

$reportScript = Join-Path $RepoRoot "backend\scripts\report_chatbot_unknown_backlog.py"
if (-not (Test-Path -LiteralPath $reportScript)) {
    throw "Report script not found: $reportScript"
}
if (-not (Test-Path -LiteralPath $EnvFile)) {
    throw "Env file not found: $EnvFile"
}

& $PythonCommand $reportScript `
    --env-file $EnvFile `
    --format markdown `
    --output $OutputPath

if ($LASTEXITCODE -ne 0) {
    throw "Chatbot unknown backlog report failed with exit code $LASTEXITCODE"
}

Write-Output "Chatbot unknown backlog report ready: $OutputPath"
