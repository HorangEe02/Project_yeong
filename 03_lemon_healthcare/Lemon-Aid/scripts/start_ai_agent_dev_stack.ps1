param(
  [string]$WorkspaceRoot = (Resolve-Path "$PSScriptRoot\..").Path,
  [int]$PostgresPort = 55432,
  [int]$FastApiPort = 18080,
  [string]$SglangBaseUrl = "http://127.0.0.1:30000/v1",
  [string]$SglangModel = "Qwen/Qwen2.5-0.5B-Instruct",
  [string]$FlutterWebOrigin = "http://localhost:52100",
  [switch]$Foreground
)

$ErrorActionPreference = "Stop"

$pgBin = "C:\Users\KDS13\anaconda3\envs\lemon-sglang\Library\bin"
$pgData = Join-Path $WorkspaceRoot ".local\postgres-dev-data"
$pgLog = Join-Path $WorkspaceRoot ".local\postgres-dev.log"
$apiOutLog = Join-Path $WorkspaceRoot ".local\fastapi-dev.out.log"
$apiErrLog = Join-Path $WorkspaceRoot ".local\fastapi-dev.err.log"
$backendRoot = Join-Path $WorkspaceRoot "backend"
$nutritionRoot = Join-Path $backendRoot "Nutrition-backend"
$aiAgentSrc = Join-Path $backendRoot "ai_agent_chat\src"
$databaseName = "lemon_agent_dev"
$databaseUrl = "postgresql+asyncpg://postgres@127.0.0.1:$PostgresPort/$databaseName"

New-Item -ItemType Directory -Force -Path (Join-Path $WorkspaceRoot ".local") | Out-Null

if (-not (Test-Path (Join-Path $pgData "PG_VERSION"))) {
  New-Item -ItemType Directory -Force -Path $pgData | Out-Null
  & (Join-Path $pgBin "initdb.exe") -D $pgData -U postgres -A trust | Out-Host
}

$pgOpen = Test-NetConnection -ComputerName 127.0.0.1 -Port $PostgresPort -InformationLevel Quiet
if (-not $pgOpen) {
  & (Join-Path $pgBin "pg_ctl.exe") -D $pgData -l $pgLog -o "-p $PostgresPort" start | Out-Host
}

$env:PGPASSWORD = ""
$previousErrorActionPreference = $ErrorActionPreference
$ErrorActionPreference = "Continue"
$createdbOutput = & (Join-Path $pgBin "createdb.exe") -h 127.0.0.1 -p $PostgresPort -U postgres $databaseName 2>&1
$createdbExitCode = $LASTEXITCODE
$ErrorActionPreference = $previousErrorActionPreference
if ($createdbExitCode -ne 0 -and (($createdbOutput -join "`n") -notmatch "already exists")) {
  throw ($createdbOutput -join "`n")
}

$env:PYTHONPATH = "$nutritionRoot;$aiAgentSrc;$backendRoot"
$env:DATABASE_URL = $databaseUrl
$env:AUTH_MODE = "disabled"
$env:ALLOWED_ORIGINS = "[`"$FlutterWebOrigin`",`"http://127.0.0.1:52100`"]"
$env:LLM_PROVIDER = "sglang"
$env:SGLANG_BASE_URL = $SglangBaseUrl
$env:SGLANG_MODEL = $SglangModel
$env:SGLANG_API_KEY = "EMPTY"  # pragma: allowlist secret
$env:ALLOW_EXTERNAL_LLM = "false"
$env:LOG_LEVEL = "INFO"

Push-Location $backendRoot
try {
  python -m alembic -c alembic.ini upgrade head | Out-Host
}
finally {
  Pop-Location
}

$apiOpen = Test-NetConnection -ComputerName 127.0.0.1 -Port $FastApiPort -InformationLevel Quiet
if (-not $apiOpen) {
  if ($Foreground) {
    Write-Output "Starting FastAPI in foreground. Keep this PowerShell open; press Ctrl+C to stop FastAPI."
    Push-Location $nutritionRoot
    try {
      python -m uvicorn src.main:app --host 127.0.0.1 --port $FastApiPort --log-level info
    }
    finally {
      Pop-Location
    }
    exit 0
  }
  else {
    Start-Process `
      -FilePath python `
      -ArgumentList "-m", "uvicorn", "src.main:app", "--host", "127.0.0.1", "--port", "$FastApiPort", "--log-level", "info" `
      -WorkingDirectory $nutritionRoot `
      -RedirectStandardOutput $apiOutLog `
      -RedirectStandardError $apiErrLog `
      -WindowStyle Hidden
  }
}

$deadline = (Get-Date).AddSeconds(20)
do {
  Start-Sleep -Milliseconds 500
  try {
    $health = Invoke-RestMethod -Uri "http://127.0.0.1:$FastApiPort/health" -TimeoutSec 2
    if ($health.status -eq "ok") {
      Write-Output "AI Agent dev stack ready: http://127.0.0.1:$FastApiPort"
      exit 0
    }
  }
  catch {
  }
} while ((Get-Date) -lt $deadline)

Write-Error "FastAPI did not become healthy. Check $apiErrLog and $apiOutLog"
exit 1
