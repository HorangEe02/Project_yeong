param(
    [string]$TaskName = "LemonAid Chatbot Unknown Backlog Report",
    [string]$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path,
    [string]$At = "09:30"
)

$ErrorActionPreference = "Stop"

$runner = Join-Path $RepoRoot "backend\scripts\write_chatbot_unknown_backlog_report.ps1"
if (-not (Test-Path -LiteralPath $runner)) {
    throw "Report runner not found: $runner"
}

$action = New-ScheduledTaskAction `
    -Execute "powershell.exe" `
    -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$runner`" -RepoRoot `"$RepoRoot`""
$trigger = New-ScheduledTaskTrigger -Daily -At $At
$principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Limited

Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $action `
    -Trigger $trigger `
    -Principal $principal `
    -Description "Writes the Lemon Aid chatbot unknown knowledge backlog report every day." `
    -Force | Out-Null

Write-Output "Registered scheduled task '$TaskName' for daily $At."
