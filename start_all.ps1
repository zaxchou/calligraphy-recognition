#Requires -Version 5.1
<#
.SYNOPSIS
    One-click start all services (Windows)
.DESCRIPTION
    Starts in order:
      1. Qdrant (port 6333)
      2. Redis (port 6379)
      3. FastAPI backend (port 8001)
      4. Celery Worker (async task processing)
      5. Tubi Worker (tubi analysis queue processing)
      6. Frontend dev server (port 3000)
    First run auto-downloads Redis.
    Each service runs in its own window.
.EXAMPLE
    .\start_all.ps1
    .\start_all.ps1 -SkipFrontend
    .\start_all.ps1 -SkipRedis
#>

param(
    [switch]$SkipQdrant,
    [switch]$SkipRedis,
    [switch]$SkipCelery,
    [switch]$SkipTubi,
    [switch]$SkipFastAPI,
    [switch]$SkipFrontend
)

$ErrorActionPreference = 'Continue'
$ProjectDir = $PSScriptRoot
$BackendDir = Join-Path $ProjectDir 'backend'
$FrontendDir = Join-Path $ProjectDir 'frontend'
$RedisPort = 6379
$ApiPort = 8001
$FrontendPort = 3000
$QdrantPort = 6333

Write-Host ''
Write-Host '============================================' -ForegroundColor Cyan
Write-Host '  Calligraphy System - One-Click Start' -ForegroundColor Cyan
Write-Host '============================================' -ForegroundColor Cyan
Write-Host ''

# ========== 1. Qdrant ==========
if (-not $SkipQdrant) {
    Write-Host '[1/6] Starting Qdrant ...' -ForegroundColor Yellow
    & (Join-Path $ProjectDir 'start_qdrant_windows.ps1')
    try {
        $conn = New-Object System.Net.Sockets.TcpClient('127.0.0.1', $QdrantPort)
        $conn.Close()
        Write-Host "[OK] Qdrant running (port $QdrantPort)" -ForegroundColor Green
    } catch {
        Write-Host '[WARN] Qdrant failed to start. Composition analysis will not work.' -ForegroundColor Red
    }
} else {
    Write-Host '[1/6] Skip Qdrant (-SkipQdrant)' -ForegroundColor DarkGray
}

Write-Host ''

# ========== 2. Redis ==========
if (-not $SkipRedis) {
    Write-Host '[2/6] Starting Redis ...' -ForegroundColor Yellow
    & (Join-Path $ProjectDir 'start_redis_windows.ps1')
    try {
        $conn = New-Object System.Net.Sockets.TcpClient('127.0.0.1', $RedisPort)
        $conn.Close()
        Write-Host "[OK] Redis running (port $RedisPort)" -ForegroundColor Green
    } catch {
        Write-Host '[FAIL] Redis failed to start. Subsequent services require Redis.' -ForegroundColor Red
        exit 1
    }
} else {
    Write-Host '[2/6] Skip Redis (-SkipRedis)' -ForegroundColor DarkGray
}

Write-Host ''

# ========== 3. FastAPI Backend ==========
# FastAPI must start BEFORE Celery/Tubi workers to avoid killing them
if (-not $SkipFastAPI) {
    Write-Host '[3/6] Starting FastAPI backend ...' -ForegroundColor Yellow

    # Kill old uvicorn zombie processes (only uvicorn, not workers)
    Write-Host "[FastAPI] Cleaning up old uvicorn processes ..." -ForegroundColor DarkGray
    $uvicornProcs = Get-CimInstance Win32_Process | Where-Object {
        $_.Name -like 'python*.exe' -and (
            $_.CommandLine -like '*uvicorn*app.main*' -or
            $_.CommandLine -like '*uvicorn*app.main:app*'
        )
    }
    if ($uvicornProcs) {
        Write-Host "[FastAPI] Found $($uvicornProcs.Count) old uvicorn process(es), killing ..." -ForegroundColor Yellow
        $uvicornProcs | ForEach-Object {
            try {
                Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
                Write-Host "[FastAPI]   Killed PID $($_.ProcessId)" -ForegroundColor DarkGray
            } catch {
                Write-Host "[FastAPI]   PID $($_.ProcessId) already dead" -ForegroundColor DarkGray
            }
        }
        Start-Sleep -Seconds 2
    }

    # Also kill by port (in case process doesn't match patterns above)
    Write-Host "[FastAPI] Checking port $ApiPort ..." -ForegroundColor DarkGray
    $listening = Get-NetTCPConnection -LocalPort $ApiPort -State Listen -ErrorAction SilentlyContinue
    if ($listening) {
        Write-Host "[FastAPI] Port $ApiPort in use, killing processes ..." -ForegroundColor Yellow
        $listening | ForEach-Object {
            try {
                Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue
                Write-Host "[FastAPI]   Killed PID $($_.OwningProcess)" -ForegroundColor DarkGray
            } catch {
                Write-Host "[FastAPI]   PID $($_.OwningProcess) already dead" -ForegroundColor DarkGray
            }
        }
        Start-Sleep -Seconds 2
    }

    # Re-check port
    $still = Get-NetTCPConnection -LocalPort $ApiPort -State Listen -ErrorAction SilentlyContinue
    if ($still) {
        Write-Host "[FastAPI] Port $ApiPort still held, trying backup port ..." -ForegroundColor Yellow
        $ApiPort = 8002
    }

    # Find Python
    $pythonCmd = 'python'
    $venvPython = Join-Path $BackendDir 'venv\Scripts\python.exe'
    if (Test-Path $venvPython) {
        $pythonCmd = $venvPython
        Write-Host '[FastAPI] Using venv' -ForegroundColor DarkGray
    }

    $args = @('-m', 'uvicorn', 'app.main:app', '--host', '0.0.0.0', '--port', $ApiPort, '--log-level', 'info')
    $psi = New-Object System.Diagnostics.ProcessStartInfo
    $psi.FileName = $pythonCmd
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
    Write-Host '[3/6] Skip FastAPI (-SkipFastAPI)' -ForegroundColor DarkGray
}

Write-Host ''

# ========== 4. Celery Worker ==========
if (-not $SkipCelery) {
    Write-Host '[4/6] Starting Celery Worker ...' -ForegroundColor Yellow
    & (Join-Path $ProjectDir 'start_celery_windows.ps1')
    Write-Host '[OK] Celery Worker launched (check its window)' -ForegroundColor Green
} else {
    Write-Host '[4/6] Skip Celery Worker (-SkipCelery)' -ForegroundColor DarkGray
}

Write-Host ''

# ========== 5. Tubi Worker ==========
if (-not $SkipTubi) {
    Write-Host '[5/6] Starting Tubi Worker ...' -ForegroundColor Yellow
    & (Join-Path $ProjectDir 'start_tubi_windows.ps1')
    Write-Host '[OK] Tubi Worker launched (check its window)' -ForegroundColor Green
} else {
    Write-Host '[5/6] Skip Tubi Worker (-SkipTubi)' -ForegroundColor DarkGray
}

Write-Host ''

# ========== 6. Frontend ==========
if (-not $SkipFrontend) {
    Write-Host '[6/6] Starting Frontend dev server ...' -ForegroundColor Yellow

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

    $viteBin = Join-Path $FrontendDir 'node_modules\.bin\vite.cmd'
    $feArgs = @('--host', '0.0.0.0', '--port', $FrontendPort)
    $psi = New-Object System.Diagnostics.ProcessStartInfo
    $psi.FileName = $viteBin
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
    Write-Host '[6/6] Skip Frontend (-SkipFrontend)' -ForegroundColor DarkGray
}

Write-Host ''
Write-Host '============================================' -ForegroundColor Cyan
Write-Host '  All services started!' -ForegroundColor Green
Write-Host ''
Write-Host "  Qdrant:     http://localhost:$QdrantPort/dashboard"
Write-Host "  Redis:      localhost:$RedisPort"
Write-Host "  FastAPI:    http://localhost:$ApiPort"
Write-Host "  API Docs:   http://localhost:$ApiPort/docs"
Write-Host '  Celery:     Worker window'
Write-Host '  Tubi:       Worker window'
Write-Host "  Frontend:   http://localhost:$FrontendPort"
Write-Host ''
Write-Host '  Close each window to stop its service.' -ForegroundColor DarkGray
Write-Host '============================================' -ForegroundColor Cyan
