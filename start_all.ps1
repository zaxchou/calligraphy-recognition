#Requires -Version 5.1
<#
.SYNOPSIS
    One-click start all services (Windows)
.DESCRIPTION
    Starts in order:
      1. Redis (port 6379)
      2. Celery Worker (async task processing)
      3. FastAPI backend (port 8001)
      4. Frontend dev server (port 3000)
    First run auto-downloads Redis.
    Each service runs in its own window.
.EXAMPLE
    .\start_all.ps1
    .\start_all.ps1 -SkipFrontend
    .\start_all.ps1 -SkipRedis
#>

param(
    [switch]$SkipRedis,
    [switch]$SkipCelery,
    [switch]$SkipFastAPI,
    [switch]$SkipFrontend
)

$ErrorActionPreference = 'Stop'
$ProjectDir = $PSScriptRoot
$BackendDir = Join-Path $ProjectDir 'backend'
$FrontendDir = Join-Path $ProjectDir 'frontend'
$RedisPort = 6379
$ApiPort = 8001
$FrontendPort = 3000

Write-Host ''
Write-Host '============================================' -ForegroundColor Cyan
Write-Host '  Calligraphy System - One-Click Start' -ForegroundColor Cyan
Write-Host '============================================' -ForegroundColor Cyan
Write-Host ''

# ========== 1. Redis ==========
if (-not $SkipRedis) {
    Write-Host '[1/4] Starting Redis ...' -ForegroundColor Yellow
    & (Join-Path $ProjectDir 'start_redis_windows.ps1')
    if ($LASTEXITCODE -ne 0) {
        Write-Host '[FAIL] Redis failed to start. Subsequent services require Redis.' -ForegroundColor Red
        exit 1
    }
} else {
    Write-Host '[1/4] Skip Redis (-SkipRedis)' -ForegroundColor DarkGray
}

Write-Host ''

# ========== 2. Celery Worker ==========
if (-not $SkipCelery) {
    Write-Host '[2/4] Starting Celery Worker ...' -ForegroundColor Yellow
    & (Join-Path $ProjectDir 'start_celery_windows.ps1')
    if ($LASTEXITCODE -ne 0) {
        Write-Host '[FAIL] Celery Worker failed to start' -ForegroundColor Red
        exit 1
    }
} else {
    Write-Host '[2/4] Skip Celery Worker (-SkipCelery)' -ForegroundColor DarkGray
}

Write-Host ''

# ========== 3. FastAPI Backend ==========
if (-not $SkipFastAPI) {
    Write-Host '[3/4] Starting FastAPI backend ...' -ForegroundColor Yellow

    # Kill old process on port
    $portInUse = Get-NetTCPConnection -LocalPort $ApiPort -ErrorAction SilentlyContinue | Where-Object { $_.State -eq 'Listen' }
    if ($portInUse) {
        Write-Host "[FastAPI] Port $ApiPort in use, killing old process ..." -ForegroundColor Yellow
        $portInUse | ForEach-Object {
            try {
                Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue
            } catch {}
        }
        Start-Sleep -Seconds 2
    }

    # Find Python
    $pythonCmd = 'python'
    $venvPython = Join-Path $BackendDir 'venv\Scripts\python.exe'
    if (Test-Path $venvPython) {
        $pythonCmd = $venvPython
        Write-Host '[FastAPI] Using venv' -ForegroundColor DarkGray
    }

    $args = @('-m', 'uvicorn', 'app.main:app', '--host', '0.0.0.0', "--port $ApiPort", '--reload', '--log-level', 'info')
    $psi = New-Object System.Diagnostics.ProcessStartInfo
    $psi.FileName = 'python'
    $psi.Arguments = $args -join ' '
    $psi.WorkingDirectory = $BackendDir
    $psi.UseShellExecute = $true
    $psi.WindowStyle = 'Normal'
    [System.Diagnostics.Process]::Start($psi) | Out-Null

    Start-Sleep -Seconds 3

    # Verify
    try {
        $conn = New-Object System.Net.Sockets.TcpClient('127.0.0.1', $ApiPort)
        $conn.Close()
        Write-Host "[FastAPI] Backend started (port $ApiPort)" -ForegroundColor Green
    } catch {
        Write-Host '[FastAPI] Backend may still be starting. Check the FastAPI window.' -ForegroundColor Yellow
    }
} else {
    Write-Host '[3/4] Skip FastAPI (-SkipFastAPI)' -ForegroundColor DarkGray
}

Write-Host ''

# ========== 4. Frontend ==========
if (-not $SkipFrontend) {
    Write-Host '[4/4] Starting Frontend dev server ...' -ForegroundColor Yellow

    # Check node_modules
    if (-not (Test-Path (Join-Path $FrontendDir 'node_modules'))) {
        Write-Host '[Frontend] Installing dependencies (npm install) ...' -ForegroundColor Yellow
        Push-Location $FrontendDir
        cmd /c 'npm install'
        Pop-Location
    }

    # Kill old process on port
    $fePortInUse = Get-NetTCPConnection -LocalPort $FrontendPort -ErrorAction SilentlyContinue | Where-Object { $_.State -eq 'Listen' }
    if ($fePortInUse) {
        Write-Host "[Frontend] Port $FrontendPort in use, killing old process ..." -ForegroundColor Yellow
        $fePortInUse | ForEach-Object {
            try {
                Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue
            } catch {}
        }
        Start-Sleep -Seconds 2
    }

    $feArgs = @('vite', '--host', '0.0.0.0', "--port $FrontendPort")
    $psi = New-Object System.Diagnostics.ProcessStartInfo
    $psi.FileName = 'npx'
    $psi.Arguments = $feArgs -join ' '
    $psi.WorkingDirectory = $FrontendDir
    $psi.UseShellExecute = $true
    $psi.WindowStyle = 'Normal'
    [System.Diagnostics.Process]::Start($psi) | Out-Null

    Start-Sleep -Seconds 3

    # Verify
    try {
        $conn = New-Object System.Net.Sockets.TcpClient('127.0.0.1', $FrontendPort)
        $conn.Close()
        Write-Host "[Frontend] Dev server started (port $FrontendPort)" -ForegroundColor Green
    } catch {
        Write-Host '[Frontend] May still be starting. Check the Frontend window.' -ForegroundColor Yellow
    }
} else {
    Write-Host '[4/4] Skip Frontend (-SkipFrontend)' -ForegroundColor DarkGray
}

Write-Host ''
Write-Host '============================================' -ForegroundColor Cyan
Write-Host '  All services started!' -ForegroundColor Green
Write-Host ''
Write-Host "  Redis:      localhost:$RedisPort"
Write-Host '  Celery:    Worker window'
Write-Host "  FastAPI:    http://localhost:$ApiPort"
Write-Host "  API Docs:   http://localhost:$ApiPort/docs"
Write-Host "  Frontend:   http://localhost:$FrontendPort"
Write-Host ''
Write-Host '  Close each window to stop its service.' -ForegroundColor DarkGray
Write-Host '============================================' -ForegroundColor Cyan
