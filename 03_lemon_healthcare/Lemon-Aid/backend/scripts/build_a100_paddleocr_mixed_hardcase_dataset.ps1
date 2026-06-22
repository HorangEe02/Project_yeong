<#
.SYNOPSIS
Build a PaddleOCR recognition dataset that preserves the base dictionary while
oversampling train-only hardcase line crops.

.DESCRIPTION
The hardcase-only recognition dataset has a small character dictionary, which
reinitializes the recognition head and makes the model unsuitable as a direct
production recognizer. This script creates a mixed dataset from the full base
dataset plus train-only hardcase crops. By default it writes the union
dictionary. Use -PreserveBaseDictOnly when fine-tuning from a checkpoint whose
recognition head must keep the base dictionary size.

The script prints only counts and paths needed for operator verification. It
does not print label text, raw OCR text, provider payloads, or image contents.
#>

param(
    [string]$WorkspaceRoot = "G:\lemon-aid\paddleocr_rec_work",
    [string]$BaseDatasetVersion = "v2",
    [string]$HardcaseDatasetVersion = "v6_train_hardcase_stage6_20260617",
    [string]$OutputDatasetVersion = "v7_mix_v2_hardcase_stage6_20260618",
    [ValidateRange(1, 64)]
    [int]$HardcaseTrainRepeat = 8,
    [ValidateRange(1, 16)]
    [int]$HardcaseValRepeat = 1,
    [switch]$PreserveBaseDictOnly
)

$ErrorActionPreference = "Stop"

$datasetRoot = Join-Path $WorkspaceRoot "rec_dataset"
$baseDir = Join-Path $datasetRoot $BaseDatasetVersion
$hardcaseDir = Join-Path $datasetRoot $HardcaseDatasetVersion
$outputDir = Join-Path $datasetRoot $OutputDatasetVersion

$baseTrain = Join-Path $baseDir "rec\rec_gt_train.txt"
$baseVal = Join-Path $baseDir "rec\rec_gt_val.txt"
$baseDict = Join-Path $baseDir "dict.txt"
$hardcaseTrain = Join-Path $hardcaseDir "rec\rec_gt_train.txt"
$hardcaseVal = Join-Path $hardcaseDir "rec\rec_gt_val.txt"
$hardcaseDict = Join-Path $hardcaseDir "dict.txt"

function Assert-Leaf {
    param([string]$Path, [string]$Name)
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        throw "$Name is missing."
    }
}

function Assert-Container {
    param([string]$Path, [string]$Name)
    if (-not (Test-Path -LiteralPath $Path -PathType Container)) {
        throw "$Name is missing."
    }
}

function Get-TextLineCount {
    param([string]$Path)
    $count = 0
    Get-Content -LiteralPath $Path -ReadCount 1000 -Encoding UTF8 | ForEach-Object {
        $count += $_.Count
    }
    return $count
}

function Get-DictSet {
    param([string]$DictPath)
    $set = [System.Collections.Generic.HashSet[string]]::new()
    foreach ($line in Get-Content -LiteralPath $DictPath -Encoding UTF8) {
        if ([string]::IsNullOrEmpty($line)) {
            continue
        }
        [void]$set.Add($line)
    }
    return $set
}

function Test-LabelSupportedByDict {
    param([string]$Label, [System.Collections.Generic.HashSet[string]]$AllowedChars)
    if ($null -eq $AllowedChars) {
        return $true
    }
    for ($index = 0; $index -lt $Label.Length; $index++) {
        $char = $Label.Substring($index, 1)
        if (-not $AllowedChars.Contains($char)) {
            return $false
        }
    }
    return $true
}

function Convert-HardcaseLabelPath {
    param(
        [string]$Line,
        [string]$Split,
        [System.Collections.Generic.HashSet[string]]$AllowedChars
    )
    if ([string]::IsNullOrWhiteSpace($Line)) {
        return $null
    }
    $parts = $Line -split "`t", 2
    if ($parts.Count -ne 2) {
        throw "Hardcase label row does not have two tab-separated columns."
    }
    $sourcePrefix = "rec/images/$Split/"
    $targetPrefix = "rec/images/hardcase_$Split/"
    if (-not $parts[0].StartsWith($sourcePrefix)) {
        throw "Unexpected hardcase relative image path prefix."
    }
    if (-not (Test-LabelSupportedByDict -Label $parts[1] -AllowedChars $AllowedChars)) {
        return $null
    }
    $relativeName = $parts[0].Substring($sourcePrefix.Length)
    return ($targetPrefix + $relativeName + "`t" + $parts[1])
}

function Add-RepeatedHardcaseRows {
    param(
        [string]$SourceLabelPath,
        [string]$TargetLabelPath,
        [string]$Split,
        [int]$Repeat,
        [System.Collections.Generic.HashSet[string]]$AllowedChars
    )
    $rows = Get-Content -LiteralPath $SourceLabelPath -Encoding UTF8
    $added = 0
    $skippedUnique = 0
    for ($index = 0; $index -lt $Repeat; $index++) {
        foreach ($row in $rows) {
            $converted = Convert-HardcaseLabelPath -Line $row -Split $Split -AllowedChars $AllowedChars
            if ($null -ne $converted) {
                Add-Content -LiteralPath $TargetLabelPath -Encoding UTF8 -Value $converted
                $added += 1
            } elseif ($index -eq 0 -and -not [string]::IsNullOrWhiteSpace($row)) {
                $skippedUnique += 1
            }
        }
    }
    return [ordered]@{
        added_rows = $added
        skipped_unique_rows = $skippedUnique
    }
}

function Write-UnionDict {
    param([string]$BaseDictPath, [string]$HardcaseDictPath, [string]$OutputDictPath)
    $seen = [System.Collections.Generic.HashSet[string]]::new()
    $ordered = [System.Collections.Generic.List[string]]::new()
    foreach ($path in @($BaseDictPath, $HardcaseDictPath)) {
        foreach ($line in Get-Content -LiteralPath $path -Encoding UTF8) {
            if ([string]::IsNullOrEmpty($line)) {
                continue
            }
            if ($seen.Add($line)) {
                $ordered.Add($line)
            }
        }
    }
    Set-Content -LiteralPath $OutputDictPath -Encoding UTF8 -Value $ordered
}

Assert-Container -Path $baseDir -Name "base dataset"
Assert-Container -Path $hardcaseDir -Name "hardcase dataset"
Assert-Leaf -Path $baseTrain -Name "base train label"
Assert-Leaf -Path $baseVal -Name "base val label"
Assert-Leaf -Path $baseDict -Name "base dict"
Assert-Leaf -Path $hardcaseTrain -Name "hardcase train label"
Assert-Leaf -Path $hardcaseVal -Name "hardcase val label"
Assert-Leaf -Path $hardcaseDict -Name "hardcase dict"

if (Test-Path -LiteralPath $outputDir) {
    throw "output dataset already exists."
}

New-Item -ItemType Directory -Force -Path $outputDir | Out-Null

$robocopyArgs = @($baseDir, $outputDir, "/E", "/NFL", "/NDL", "/NJH", "/NJS", "/NP")
& robocopy @robocopyArgs | Out-Null
if ($LASTEXITCODE -gt 7) {
    throw "robocopy base dataset failed with exit_code=$LASTEXITCODE"
}

$hardcaseTrainImages = Join-Path $hardcaseDir "rec\images\train"
$hardcaseValImages = Join-Path $hardcaseDir "rec\images\val"
$outputHardcaseTrainImages = Join-Path $outputDir "rec\images\hardcase_train"
$outputHardcaseValImages = Join-Path $outputDir "rec\images\hardcase_val"
New-Item -ItemType Directory -Force -Path $outputHardcaseTrainImages | Out-Null
New-Item -ItemType Directory -Force -Path $outputHardcaseValImages | Out-Null

& robocopy $hardcaseTrainImages $outputHardcaseTrainImages /E /NFL /NDL /NJH /NJS /NP | Out-Null
if ($LASTEXITCODE -gt 7) {
    throw "robocopy hardcase train images failed with exit_code=$LASTEXITCODE"
}
& robocopy $hardcaseValImages $outputHardcaseValImages /E /NFL /NDL /NJH /NJS /NP | Out-Null
if ($LASTEXITCODE -gt 7) {
    throw "robocopy hardcase val images failed with exit_code=$LASTEXITCODE"
}

$outputTrain = Join-Path $outputDir "rec\rec_gt_train.txt"
$outputVal = Join-Path $outputDir "rec\rec_gt_val.txt"
$outputDict = Join-Path $outputDir "dict.txt"

Copy-Item -LiteralPath $baseTrain -Destination $outputTrain -Force
Copy-Item -LiteralPath $baseVal -Destination $outputVal -Force

$allowedChars = $null
if ($PreserveBaseDictOnly) {
    $allowedChars = Get-DictSet -DictPath $baseDict
}

$hardcaseTrainSummary = Add-RepeatedHardcaseRows -SourceLabelPath $hardcaseTrain -TargetLabelPath $outputTrain -Split "train" -Repeat $HardcaseTrainRepeat -AllowedChars $allowedChars
$hardcaseValSummary = Add-RepeatedHardcaseRows -SourceLabelPath $hardcaseVal -TargetLabelPath $outputVal -Split "val" -Repeat $HardcaseValRepeat -AllowedChars $allowedChars
if ($PreserveBaseDictOnly) {
    Copy-Item -LiteralPath $baseDict -Destination $outputDict -Force
} else {
    Write-UnionDict -BaseDictPath $baseDict -HardcaseDictPath $hardcaseDict -OutputDictPath $outputDict
}

$summary = [ordered]@{
    schema_version = "a100-paddleocr-mixed-hardcase-dataset-v1"
    base_dataset_version = $BaseDatasetVersion
    hardcase_dataset_version = $HardcaseDatasetVersion
    output_dataset_version = $OutputDatasetVersion
    hardcase_train_repeat = $HardcaseTrainRepeat
    hardcase_val_repeat = $HardcaseValRepeat
    preserve_base_dict_only = [bool]$PreserveBaseDictOnly
    train_rows = Get-TextLineCount -Path $outputTrain
    val_rows = Get-TextLineCount -Path $outputVal
    dict_rows = Get-TextLineCount -Path $outputDict
    base_train_rows = Get-TextLineCount -Path $baseTrain
    base_val_rows = Get-TextLineCount -Path $baseVal
    base_dict_rows = Get-TextLineCount -Path $baseDict
    hardcase_train_rows = Get-TextLineCount -Path $hardcaseTrain
    hardcase_val_rows = Get-TextLineCount -Path $hardcaseVal
    hardcase_dict_rows = Get-TextLineCount -Path $hardcaseDict
    hardcase_train_added_rows = $hardcaseTrainSummary.added_rows
    hardcase_val_added_rows = $hardcaseValSummary.added_rows
    hardcase_train_skipped_unique_rows = $hardcaseTrainSummary.skipped_unique_rows
    hardcase_val_skipped_unique_rows = $hardcaseValSummary.skipped_unique_rows
    holdout_leakage_expected = $false
    label_text_printed = $false
    raw_ocr_text_printed = $false
    provider_payload_printed = $false
}

$summaryPath = Join-Path $outputDir "mixed_dataset_summary.json"
$summary | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $summaryPath -Encoding UTF8
Write-Host ($summary | ConvertTo-Json -Compress -Depth 4)
