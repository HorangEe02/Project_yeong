<#
.SYNOPSIS
Run the Windows A100 PaddleOCR recognition preflight, dataset gate, smoke, full,
or export step.

.DESCRIPTION
This operator script is intended for the VS Code Remote SSH terminal on the A100
Windows server. It performs count-only dataset validation before any training,
keeps preflight usable before the private dataset has been copied, and never
prints label text or provider payloads.

Official references:
- https://www.paddleocr.ai/latest/en/version3.x/installation.html
- https://www.paddleocr.ai/latest/en/version2.x/ppocr/model_train/recognition.html
- https://www.paddlepaddle.org.cn/documentation/docs/install/pip/windows-pip_en.html
- https://raw.githubusercontent.com/PaddlePaddle/PaddleOCR/main/configs/rec/PP-OCRv5/multi_language/korean_PP-OCRv5_mobile_rec.yml
#>

param(
    [ValidateSet("preflight", "dataset", "smoke", "full", "export")]
    [string]$Mode = "preflight",

    [string]$WorkspaceRoot = "G:\lemon-aid\paddleocr_rec_work",
    [string]$DatasetVersion = "v2",
    [string]$RunSuffix = "v2_clean",
    [string]$PythonExe = "",
    [string]$GpuId = "0",
    [int]$BatchSize = 128,
    [int]$Epochs = 100,
    [double]$LearningRate = 0.0005,
    [int]$ExpectedTrainRows = 70778,
    [int]$ExpectedValRows = 6828,
    [int]$ExpectedDictRows = 1066,
    [string]$PretrainedModel = "pretrain\korean_PP-OCRv5_mobile_rec_pretrained",
    [string]$PretrainedModelUrl = "https://paddle-model-ecology.bj.bcebos.com/paddlex/official_pretrained_model/korean_PP-OCRv5_mobile_rec_pretrained.pdparams"
)

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"

if ([string]::IsNullOrWhiteSpace($RunSuffix)) {
    $RunSuffix = $DatasetVersion
}
if ([string]::IsNullOrWhiteSpace($PythonExe)) {
    $PythonExe = Join-Path $WorkspaceRoot ".venv-paddle-rec-v2-clean\Scripts\python.exe"
}

$DatasetDir = Join-Path $WorkspaceRoot "rec_dataset\$DatasetVersion"
$PaddleOCRRoot = Join-Path $WorkspaceRoot "PaddleOCR"
$CountGateScript = Join-Path $PSScriptRoot "validate_paddleocr_rec_dataset_counts.py"
$CountGateSummary = Join-Path $WorkspaceRoot "paddleocr-rec-crawling-$DatasetVersion-count-gate.json"
$TrainLabel = Join-Path $DatasetDir "rec\rec_gt_train.txt"
$ValLabel = Join-Path $DatasetDir "rec\rec_gt_val.txt"
$DictFile = Join-Path $DatasetDir "dict.txt"
$SmokeOutput = "output\supplement_rec_crawling_${RunSuffix}_smoke"
$FullOutput = "output\supplement_rec_crawling_$RunSuffix"

function Format-InvariantDecimal {
    param([double]$Value)

    return $Value.ToString("0.################", [System.Globalization.CultureInfo]::InvariantCulture)
}

function Get-TextLineCount {
    param([string]$Path)

    $count = 0
    Get-Content -LiteralPath $Path -ReadCount 1000 -Encoding UTF8 | ForEach-Object {
        $count += $_.Count
    }
    return $count
}

function Assert-FileLineCount {
    param(
        [string]$Path,
        [int]$Expected,
        [string]$Name
    )

    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        throw "$Name file is missing."
    }
    $actual = Get-TextLineCount -Path $Path
    Write-Host "$Name lines: $actual"
    if ($actual -ne $Expected) {
        throw "$Name line count mismatch. expected=$Expected actual=$actual"
    }
}

function Assert-DatasetGate {
    Write-Host "Checking count-only dataset gate..."
    if (Test-Path -LiteralPath $CountGateScript -PathType Leaf) {
        & $PythonExe $CountGateScript `
            --dataset-dir $DatasetDir `
            --expected-train-rows $ExpectedTrainRows `
            --expected-val-rows $ExpectedValRows `
            --expected-dict-rows $ExpectedDictRows `
            --summary-output $CountGateSummary
        if ($LASTEXITCODE -ne 0) {
            throw "Dataset count gate failed."
        }
        Write-Host "Dataset gate passed."
        return
    }

    Assert-FileLineCount -Path $TrainLabel -Expected $ExpectedTrainRows -Name "train"
    Assert-FileLineCount -Path $ValLabel -Expected $ExpectedValRows -Name "val"
    Assert-FileLineCount -Path $DictFile -Expected $ExpectedDictRows -Name "dict"
    Write-Host "Dataset gate passed."
}

function Assert-ExportInputs {
    Write-Host "Checking export inputs..."
    Assert-FileLineCount -Path $DictFile -Expected $ExpectedDictRows -Name "dict"
    $bestCheckpoint = Join-Path $PaddleOCRRoot "$FullOutput\best_accuracy"
    $bestParams = "$bestCheckpoint.pdparams"
    if (-not (Test-Path -LiteralPath $bestParams -PathType Leaf)) {
        throw "best_accuracy checkpoint parameters are missing: $bestParams"
    }
    Write-Host "Export inputs passed. checkpoint_prefix=$bestCheckpoint"
}

function Resolve-PaddleOCRConfig {
    $candidates = @(
        "configs\rec\PP-OCRv5\multi_language\korean_PP-OCRv5_mobile_rec.yml"
    )
    foreach ($candidate in $candidates) {
        $path = Join-Path $PaddleOCRRoot $candidate
        if (Test-Path -LiteralPath $path -PathType Leaf) {
            return $candidate
        }
    }
    throw "korean_PP-OCRv5_mobile_rec.yml was not found under the PaddleOCR checkout."
}

function Resolve-PretrainedModel {
    if ([string]::IsNullOrWhiteSpace($PretrainedModel)) {
        return ""
    }

    $modelPrefix = $PretrainedModel
    if ($modelPrefix.EndsWith(".pdparams")) {
        $modelPrefix = $modelPrefix.Substring(0, $modelPrefix.Length - ".pdparams".Length)
    }

    $modelFile = "$modelPrefix.pdparams"
    if ([System.IO.Path]::IsPathRooted($modelFile)) {
        $modelFilePath = $modelFile
    }
    else {
        $modelFilePath = Join-Path $PaddleOCRRoot $modelFile
    }

    if (-not (Test-Path -LiteralPath $modelFilePath -PathType Leaf)) {
        Write-Host "Downloading Korean PP-OCRv5 pretrained recognition weights..."
        $modelParent = Split-Path -Parent $modelFilePath
        New-Item -ItemType Directory -Force -Path $modelParent | Out-Null
        Invoke-WebRequest -Uri $PretrainedModelUrl -OutFile $modelFilePath
    }

    return $modelPrefix
}

function Invoke-CudaPreflight {
    Write-Host "Running NVIDIA/Paddle CUDA preflight..."
    Write-Host "Python executable: $PythonExe"
    & $PythonExe --version
    nvidia-smi
    & $PythonExe -c "import paddle; print('cuda', paddle.is_compiled_with_cuda()); print('gpus', paddle.device.cuda.device_count()); paddle.utils.run_check()"
}

function Invoke-PaddleOCRTrain {
    param(
        [string]$OutputDir,
        [int]$EpochCount
    )

    if (-not (Test-Path -LiteralPath $PaddleOCRRoot -PathType Container)) {
        throw "PaddleOCR root is missing."
    }

    Push-Location $PaddleOCRRoot
    try {
        $env:CUDA_VISIBLE_DEVICES = $GpuId
        $configPath = Resolve-PaddleOCRConfig
        $pretrainedModelArg = Resolve-PretrainedModel
        $learningRateArg = Format-InvariantDecimal -Value $LearningRate
        $trainArgs = @(
            "tools\train.py",
            "-c", $configPath,
            "-o",
            "Global.pretrained_model=$pretrainedModelArg",
            "Global.save_model_dir=$OutputDir",
            "Global.epoch_num=$EpochCount",
            "Global.character_dict_path=$DictFile",
            "Global.use_space_char=True",
            "Optimizer.lr.learning_rate=$learningRateArg",
            "Train.dataset.data_dir=$DatasetDir",
            "Train.dataset.label_file_list=['$TrainLabel']",
            "Eval.dataset.data_dir=$DatasetDir",
            "Eval.dataset.label_file_list=['$ValLabel']",
            "Train.loader.batch_size_per_card=$BatchSize",
            "Train.loader.num_workers=0",
            "Eval.loader.num_workers=0"
        )
        & $PythonExe @trainArgs
    }
    finally {
        Pop-Location
    }
}

function Invoke-PaddleOCRExport {
    Push-Location $PaddleOCRRoot
    try {
        $configPath = Resolve-PaddleOCRConfig
        $exportArgs = @(
            "tools\export_model.py",
            "-c", $configPath,
            "-o",
            "Global.pretrained_model=$FullOutput\best_accuracy",
            "Global.character_dict_path=$DictFile",
            "Global.save_inference_dir=$FullOutput\best_accuracy\inference"
        )
        & $PythonExe @exportArgs
    }
    finally {
        Pop-Location
    }
}

switch ($Mode) {
    "preflight" {
        Invoke-CudaPreflight
    }
    "dataset" {
        Assert-DatasetGate
    }
    "smoke" {
        Invoke-CudaPreflight
        Assert-DatasetGate
        Invoke-PaddleOCRTrain -OutputDir $SmokeOutput -EpochCount 1
    }
    "full" {
        Invoke-CudaPreflight
        Assert-DatasetGate
        Invoke-PaddleOCRTrain -OutputDir $FullOutput -EpochCount $Epochs
    }
    "export" {
        Assert-ExportInputs
        Invoke-PaddleOCRExport
    }
}
