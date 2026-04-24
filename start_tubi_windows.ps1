#Requires -Version 5.1
<#
.SYNOPSIS
    Start Tubi Worker (Windows)
.DESCRIPTION
    - Checks Redis is running first
    - Runs tubi_worker.py as a standalone process (brpoplpush queue)
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
    Write-Host '[Tubi] Redis connection OK' -ForegroundColor Green
} catch {
    Write-Host "[Tubi] Redis not running (port $RedisPort unreachable)" -ForegroundColor Red
    Write-Host '[Tubi] Please run first: .\start_redis_windows.ps1' -ForegroundColor Yellow
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
    Write-Host '[Tubi] Python not found, please install and add to PATH' -ForegroundColor Red
    Pop-Location
    exit 1
}

# Check for virtual environment
$venvPython = Join-Path $BackendDir 'venv\Scripts\python.exe'
if (Test-Path $venvPython) {
    Write-Host '[Tubi] venv detected, using virtual environment' -ForegroundColor Yellow
    $pythonCmd = $venvPython
}

Pop-Location

# ---------- Start Tubi Worker ----------
Write-Host '[Tubi] Starting Tubi Worker (tubi_worker.py) ...' -ForegroundColor Green

$tubiArgs = @('tubi_worker.py')
$psi = New-Object System.Diagnostics.ProcessStartInfo
$psi.FileName = $pythonCmd
$psi.Arguments = $tubiArgs -join ' '
$psi.WorkingDirectory = $BackendDir
$psi.UseShellExecute = $true
$psi.WindowStyle = 'Normal'
[System.Diagnostics.Process]::Start($psi) | Out-Null

Start-Sleep -Seconds 2
Write-Host '[Tubi] Worker launched in a new window' -ForegroundColor Green
Write-Host '[Tubi] Note: Keep the Worker window open. Closing it stops tubi analysis.' -ForegroundColor Yellow
