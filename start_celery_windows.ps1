#Requires -Version 5.1
<#
.SYNOPSIS
    Start Celery Worker (Windows)
.DESCRIPTION
    - Checks Redis is running first
    - Uses --pool=solo (required on Windows)
    - Opens a new console window for the worker
.NOTES
    Run start_redis_windows.ps1 first
#>

$ErrorActionPreference = 'Stop'
$BackendDir = Join-Path $PSScriptRoot 'backend'
$RedisPort = 6379

# ---------- Check Redis ----------
try {
    $conn = New-Object System.Net.Sockets.TcpClient('127.0.0.1', $RedisPort)
    $conn.Close()
    Write-Host '[Celery] Redis connection OK' -ForegroundColor Green
} catch {
    Write-Host "[Celery] Redis not running (port $RedisPort unreachable)" -ForegroundColor Red
    Write-Host '[Celery] Please run first: .\start_redis_windows.ps1' -ForegroundColor Yellow
    exit 1
}

# ---------- Find Python ----------
Push-Location $BackendDir
$pythonCmd = $null
if (Get-Command python -ErrorAction SilentlyContinue) {
    $pythonCmd = 'python'
} elseif (Get-Command python3 -ErrorAction SilentlyContinue) {
    $pythonCmd = 'python3'
} else {
    Write-Host '[Celery] Python not found, please install and add to PATH' -ForegroundColor Red
    Pop-Location
    exit 1
}

# Check for virtual environment
$venvPython = Join-Path $BackendDir 'venv\Scripts\python.exe'
if (Test-Path $venvPython) {
    Write-Host '[Celery] venv detected, using virtual environment' -ForegroundColor Yellow
    $pythonCmd = $venvPython
}

Pop-Location

# ---------- Start Celery Worker ----------
Write-Host '[Celery] Starting Celery Worker (--pool=solo for Windows) ...' -ForegroundColor Green

$celeryCmd = "$pythonCmd -m celery -A app.core.celery_app worker --loglevel=info --pool=solo"
Start-Process powershell -ArgumentList '-NoExit', '-Command', "cd '$BackendDir'; Write-Host '=== Celery Worker ===' -ForegroundColor Cyan; $celeryCmd" -WindowStyle Normal

Start-Sleep -Seconds 3
Write-Host '[Celery] Worker launched in a new window' -ForegroundColor Green
Write-Host '[Celery] Note: Keep the Worker window open. Closing it stops task processing.' -ForegroundColor Yellow
