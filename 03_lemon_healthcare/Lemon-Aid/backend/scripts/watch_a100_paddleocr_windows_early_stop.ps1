<#
.SYNOPSIS
Watch a Windows A100 PaddleOCR recognition run and stop it after stale evals.

.DESCRIPTION
PaddleOCR saves the best checkpoint as the suffix-free prefix `best_accuracy`
with `.pdparams/.pdopt/.states` files. Its public recognition training guide
documents evaluation cadence and best checkpoint saving, but does not expose a
first-class early-stopping switch. This watcher reads only sanitized train logs,
compares the latest evaluated epoch with the best epoch, and stops only matching
PaddleOCR processes for the requested run suffix.
#>

param(
    [string]$WorkspaceRoot = "G:\lemon-aid\paddleocr_rec_work",
    [string]$RunSuffix = "v2_clean",

    [ValidateRange(1, 100)]
    [int]$PatienceEpochs = 5,

    [ValidateRange(1, 100)]
    [int]$MinEvaluatedEpoch = 5,

    [ValidateRange(10, 3600)]
    [int]$PollSeconds = 60,

    [switch]$Once,
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"

if ([string]::IsNullOrWhiteSpace($RunSuffix)) {
    throw "RunSuffix is required."
}

$paddleRoot = Join-Path $WorkspaceRoot "PaddleOCR"
$outputName = "supplement_rec_crawling_$RunSuffix"
$outputDir = Join-Path $paddleRoot "output\$outputName"
$trainLog = Join-Path $outputDir "train.log"
$statusPath = Join-Path $WorkspaceRoot "early_stop.$RunSuffix.status.json"

function Get-RunProgress {
    if (-not (Test-Path -LiteralPath $trainLog -PathType Leaf)) {
        return [PSCustomObject]@{
            status = "waiting_for_train_log"
            train_log = $trainLog
        }
    }

    $latestTrainEpoch = $null
    $latestEvalEpoch = $null
    $latestEvalAcc = $null
    $latestEvalNormEditDis = $null
    $bestEpoch = $null
    $bestAcc = $null
    $bestNormEditDis = $null

    foreach ($line in Get-Content -LiteralPath $trainLog -Tail 4000) {
        if ($line -match "epoch:\s*\[(\d+)/(\d+)\]") {
            $latestTrainEpoch = [int]$Matches[1]
        }
        elseif ($line -match "cur metric,\s*acc:\s*([0-9.]+),\s*norm_edit_dis:\s*([0-9.]+)") {
            $latestEvalEpoch = $latestTrainEpoch
            $latestEvalAcc = [double]$Matches[1]
            $latestEvalNormEditDis = [double]$Matches[2]
        }
        elseif ($line -match "best metric,\s*acc:\s*([0-9.]+).*norm_edit_dis:\s*([0-9.]+).*best_epoch:\s*(\d+)") {
            $bestAcc = [double]$Matches[1]
            $bestNormEditDis = [double]$Matches[2]
            $bestEpoch = [int]$Matches[3]
        }
    }

    if ($null -eq $latestEvalEpoch -or $null -eq $bestEpoch) {
        return [PSCustomObject]@{
            status = "waiting_for_eval_metric"
            latest_train_epoch = $latestTrainEpoch
            train_log = $trainLog
        }
    }

    $staleEpochs = $latestEvalEpoch - $bestEpoch
    [PSCustomObject]@{
        status = "ready"
        latest_train_epoch = $latestTrainEpoch
        latest_eval_epoch = $latestEvalEpoch
        latest_eval_acc = $latestEvalAcc
        latest_eval_norm_edit_dis = $latestEvalNormEditDis
        best_epoch = $bestEpoch
        best_acc = $bestAcc
        best_norm_edit_dis = $bestNormEditDis
        stale_eval_epochs = $staleEpochs
        patience_epochs = $PatienceEpochs
        min_evaluated_epoch = $MinEvaluatedEpoch
        train_log = $trainLog
    }
}

function Get-MatchingTrainingProcesses {
    $escapedOutputName = [regex]::Escape($outputName)
    Get-CimInstance Win32_Process | Where-Object {
        $_.CommandLine -and
        $_.CommandLine -match "\\.venv-paddle-rec-v2-clean\\Scripts\\python\.exe" -and
        $_.CommandLine -match "tools\\train\.py" -and
        $_.CommandLine -match $escapedOutputName
    }
}

function Stop-MatchingTrainingProcesses {
    param([object[]]$Processes)

    $stopped = @()
    foreach ($process in $Processes) {
        $stopped += [PSCustomObject]@{
            pid = $process.ProcessId
            name = $process.Name
        }
        if (-not $DryRun) {
            Stop-Process -Id $process.ProcessId -Force
        }
    }
    return $stopped
}

function Write-Status {
    param([hashtable]$Payload)

    $Payload["checked_at"] = (Get-Date).ToString("o")
    $Payload["run_suffix"] = $RunSuffix
    $Payload["output_name"] = $outputName
    $Payload["dry_run"] = [bool]$DryRun
    $Payload | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $statusPath -Encoding UTF8
    $Payload | ConvertTo-Json -Depth 6
}

function Invoke-EarlyStopCheck {
    $progress = Get-RunProgress
    $payload = @{
        progress = $progress
        action = "none"
        stopped_processes = @()
    }

    if ($progress.status -ne "ready") {
        Write-Status -Payload $payload
        return
    }

    $shouldStop = (
        $progress.latest_eval_epoch -ge $MinEvaluatedEpoch -and
        $progress.stale_eval_epochs -ge $PatienceEpochs
    )
    $payload["should_stop"] = $shouldStop

    if (-not $shouldStop) {
        Write-Status -Payload $payload
        return
    }

    $matches = @(Get-MatchingTrainingProcesses)
    $payload["matched_process_count"] = $matches.Count
    if ($matches.Count -eq 0) {
        $payload["action"] = "stop_requested_but_no_matching_process"
        Write-Status -Payload $payload
        return
    }

    $payload["action"] = if ($DryRun) { "would_stop" } else { "stopped" }
    $payload["stopped_processes"] = @(Stop-MatchingTrainingProcesses -Processes $matches)
    Write-Status -Payload $payload
}

do {
    Invoke-EarlyStopCheck
    if ($Once) {
        break
    }
    Start-Sleep -Seconds $PollSeconds
} while ($true)
