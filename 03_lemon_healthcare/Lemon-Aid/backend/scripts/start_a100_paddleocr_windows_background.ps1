<#
.SYNOPSIS
Start the Windows A100 PaddleOCR operator script as a detached background run.

.DESCRIPTION
This launcher uses Win32_Process.Create instead of Start-Process because SSH
sessions on the Windows A100 host can drop or truncate redirected child output.
It keeps all output in a mode-specific combined log under the A100 workspace and
does not print private labels, crop paths, or provider payloads.
#>

param(
    [ValidateSet("dataset", "smoke", "full", "export", "early-stop")]
    [string]$Mode = "full",

    [string]$WorkspaceRoot = "G:\lemon-aid\paddleocr_rec_work",
    [string]$RepoRoot = "G:\lemon-aid",
    [string]$DatasetVersion = "v2",
    [string]$RunSuffix = "v2_clean",
    [int]$BatchSize = 128,
    [int]$Epochs = 100,
    [double]$LearningRate = 0.0005,
    [int]$ExpectedTrainRows = 70778,
    [int]$ExpectedValRows = 6828,
    [int]$ExpectedDictRows = 1066,
    [string]$PretrainedModel = "pretrain\korean_PP-OCRv5_mobile_rec_pretrained",
    [ValidateRange(1, 100)]
    [int]$EarlyStopPatienceEpochs = 5,
    [ValidateRange(10, 3600)]
    [int]$EarlyStopPollSeconds = 60
)

$ErrorActionPreference = "Stop"

$runScriptPath = Join-Path $RepoRoot "backend\scripts\run_a100_paddleocr_windows_training.ps1"
$watchScriptPath = Join-Path $RepoRoot "backend\scripts\watch_a100_paddleocr_windows_early_stop.ps1"
$workdir = $RepoRoot

if ($Mode -eq "early-stop") {
    $scriptPath = $watchScriptPath
    $logPath = Join-Path $WorkspaceRoot "early_stop.$RunSuffix.combined.log"
    if (-not (Test-Path -LiteralPath $scriptPath -PathType Leaf)) {
        throw "A100 early-stop watcher is missing: $scriptPath"
    }
    $command = 'cmd.exe /c powershell -NoProfile -ExecutionPolicy Bypass -File "{0}" -RunSuffix {1} -PatienceEpochs {2} -PollSeconds {3} > "{4}" 2>&1' -f $scriptPath, $RunSuffix, $EarlyStopPatienceEpochs, $EarlyStopPollSeconds, $logPath
}
else {
    $scriptPath = $runScriptPath
    $logPath = Join-Path $WorkspaceRoot "$Mode.$RunSuffix.combined.log"
    if (-not (Test-Path -LiteralPath $scriptPath -PathType Leaf)) {
        throw "A100 run script is missing: $scriptPath"
    }
    $command = 'cmd.exe /c powershell -NoProfile -ExecutionPolicy Bypass -File "{0}" -Mode {1} -DatasetVersion {2} -RunSuffix {3} -BatchSize {4} -Epochs {5} -LearningRate {6} -ExpectedTrainRows {7} -ExpectedValRows {8} -ExpectedDictRows {9} -PretrainedModel "{10}" > "{11}" 2>&1' -f $scriptPath, $Mode, $DatasetVersion, $RunSuffix, $BatchSize, $Epochs, $LearningRate, $ExpectedTrainRows, $ExpectedValRows, $ExpectedDictRows, $PretrainedModel, $logPath
}

$result = Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments @{
    CommandLine = $command
    CurrentDirectory = $workdir
}

if ($result.ReturnValue -ne 0) {
    throw "Win32_Process.Create failed. return_value=$($result.ReturnValue)"
}

Write-Host "created mode=$Mode process_id=$($result.ProcessId) return_value=$($result.ReturnValue) log=$logPath"
